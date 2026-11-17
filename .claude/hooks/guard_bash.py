#!/usr/bin/env python3
"""PreToolUse (Bash): specialist subagents change files only through Write/Edit.

Why: `guard_write.py` confines a subagent's Write/Edit calls to its own paths, but it cannot
see a shell command. Five times in CP1/CP2 a subagent wrote a file through Bash (heredoc
append, `python -c` rewrite, `sed -i`) against its brief. The content was right each time,
but nothing enforced the rule. Owner-approved 2026-10-01 (STATUS.md).

Rule: a SUBAGENT's Bash command is refused if it would create, modify, move or delete a
file outside the temp directories. Detected:
  - output redirection (`>`, `>>`, `>|`, `&>`, `N>`) to anything but /dev/null, /dev/std*,
    or a temp path;
  - in-place editors (`sed -i`, `perl -i`) and `tee`, `cp`, `mv`, `rm`, `rmdir`, `touch`,
    `mkdir`, `ln`, `chmod`, `chown`, `truncate`, `dd`, `install`, `rsync`, `patch`
    unless every path they change is a temp path;
  - code passed to an interpreter inline (`-c`/`-e`, anywhere in the command, wrappers such
    as `timeout` or `xargs` included) or as a heredoc, and every heredoc that `cat`/`tee`
    writes, judged when the command is written, not when it is run:
      * Python (if it parses): every file-writing call (open(..., 'w'/'a'/'x'),
        write_text, write_bytes, os.remove/unlink/rename/replace/makedirs, shutil
        copy/move/rmtree, Path.touch/mkdir/unlink/rename, ...) is traced to the path it
        writes. A write to a non-temp path is refused. Otherwise the older whole-code rule
        decides (a write API is allowed only if the code names a temp path and never the
        repository), EXCEPT that a write the trace shows to be temp is allowed even though
        the code names the repository, for example to read it. That exception applies
        only when the trace accounts for every write the whole-code rule sees and leaves
        none untraced. Where the trace is unsure, the older rule stands; where it shows a
        write outside temp (a relative path while the working directory is not known to
        be temp, say), it refuses even if the older rule would not have.
      * shell code for bash/sh/zsh: these same shell rules;
      * anything else (perl, ruby, node, text): the whole-code rule.
A temp path is $TMPDIR, /tmp, /private/tmp, /var/folders, a shell variable assigned one
earlier in the same command (`S=$TMPDIR/x`, `D=$(mktemp -d)`, `for d in $TMPDIR/a ...`),
or a relative path after `cd <temp> &&` (the `cd` counts only for commands joined to it by
`&&`, or after `cd <temp> || exit`; `cd $TMPDIR` or `cd /tmp` itself always succeeds). A
subshell's `cd` does not leak out. Any `..` makes a path non-temp.
Running tests, reading, grepping, git status/diff/log, psql queries and probes stay allowed.

The main session (no agent identity in the payload) is not restricted.

This is a speed bump against agent error, not a sandbox: a determined command can hide a
write (e.g. inside a test it creates, or a script run from a file). The OS sandbox still
protects Claude Code's own files under /tmp. False positives are expected occasionally;
the agent reports them to the main session instead of working around them.

G-1 (2026-10-22): the earlier whole-code and word-level rules refused subagent commands that
wrote only scratch files (`chmod +x $TMPDIR/x`, `cp ... "$M"/ 2>/dev/null`, a Python probe
that imports from the repository and writes under mkdtemp). Tests:
tests/harness/test_guard_bash.py; the replay of past subagent commands is in STATUS.md.

Failure direction: if this script errors on a SUBAGENT call, the call is denied; on the main
session it is allowed.

Exit 0 = allow. Exit 2 = deny; stderr is shown to the agent.
"""
import ast
import json
import re
import sys

AGENT_KEYS = ("agent_type", "agent_name", "subagent_type", "agent_id")

TEMP_PREFIXES = ("$TMPDIR", "${TMPDIR", "/tmp/", "/tmp", "/private/tmp", "/var/folders/")
TEMP_ROOTS = {"$TMPDIR", "${TMPDIR}", "/tmp", "/private/tmp"}  # always exist: `cd` succeeds
SINKS = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty")

FILE_COMMANDS = {"tee", "cp", "mv", "rm", "rmdir", "touch", "mkdir", "ln", "chmod", "chown",
                 "truncate", "dd", "install", "rsync", "patch"}
INPLACE_COMMANDS = {"sed", "perl", "gsed"}
MODE_FLAGS = {"-R", "-f", "-v", "-h", "-H", "-L", "-P", "-c"}  # chmod/chown options
LEADING_WORDS = {"env", "command", "nice", "time", "xargs", "sudo", "exec", "then", "do", "else",
                 "elif", "if", "while", "until", "!", "{", "("}
PYTHON_OPTS_WITH_VALUE = {"-W", "-X", "-Q"}

WRITE_API = re.compile(
    r"""open\s*\([^,)]*,\s*['"][^'"]*[wax+][^'"]*['"]"""  # open(p, 'w'), open(p, "a+"): the MODE arg
    r"""|\.write_text\s*\(|\.write_bytes\s*\("""
    r"""|\bos\.(remove|unlink|rename|replace|makedirs|mkdir|rmdir|truncate)\s*\("""
    r"""|\bshutil\.(copy\w*|move|rmtree)\s*\("""
    r"""|\.(touch|unlink|mkdir|rmdir)\s*\("""   # Path methods; str.replace/rename are too common
    r"""|\bPath\([^)]*\)\.(rename|replace)\s*\("""
    r"""|\bmode\s*=\s*['"][wax]""",
    re.X,
)
REPO_MARKERS = re.compile(
    r"(^|[\s'\"(=/])(src|tests|methodology|implementation|reviews|decisions|specs|designs|data"
    r"|scripts|\.claude|_archive)/|STATUS\.md|CLAUDE\.md|pyproject\.toml|uv\.lock|Fin Web"
)
TEMP_MARKERS = re.compile(r"\$\{?TMPDIR|/tmp/|/private/tmp|/var/folders/|tempfile\.|mkdtemp|gettempdir"
                          r"|environ\s*\[\s*['\"]TMPDIR|environ\.get\(\s*['\"]TMPDIR|getenv\(\s*['\"]TMPDIR")
REDIRECT = re.compile(r"(?<![<>=\-])(?:\d|&)?>>?(?!&|\()\s*(\S+)")
NOT_WRITTEN = re.compile(r"\d*>&\d+|\d*<&\d+|<<<\s*\S+|<<-?\s*\S+|(?<!<)<\s*\S+")
INLINE = re.compile(r"\b(python[0-9.]*|perl|ruby|node|bash|sh|zsh)\b[^\n;|&]*?\s-(?:c|e)\s+(\x00Q\d+\x00)")


def deny(msg):
    print("BLOCKED (guard_bash): " + msg + "\n  Subagents change files only with Write/Edit, "
          "inside their write paths. Scratch files may go under $TMPDIR (a relative path "
          "counts as scratch only after `cd <temp> &&`). If this is a false positive, report "
          "it to the main session; do not work around it.", file=sys.stderr)
    sys.exit(2)


class State:
    """What the command has established so far: is the working directory a temp path, and
    which shell variables hold temp paths."""

    def __init__(self, cwd_temp=False, temp_vars=()):
        self.cwd_temp = cwd_temp
        self.temp_vars = set(temp_vars)

    def copy(self):
        return State(self.cwd_temp, self.temp_vars)


def no_dotdot(t):
    return ".." not in re.split(r"[/\\]", t)


def mktemp_is_temp(text):
    """`$(mktemp ...)`: temp unless -p/--tmpdir or a template points somewhere else."""
    args = text.split()[1:]
    for i, a in enumerate(args):
        if a in ("-p", "--tmpdir") and i + 1 < len(args):
            if not is_temp(args[i + 1]):
                return False
        elif a.startswith(("-p", "--tmpdir=")) and a not in ("-p", "--tmpdir"):
            if not is_temp(a.split("=", 1)[-1] if "=" in a else a[2:]):
                return False
        elif not a.startswith("-") and "/" in a and not is_temp(a):
            return False
    return True


def is_temp(token, state=None):
    t = token.replace("'", "").replace('"', "")  # "$M"/ and '$TMPDIR'/x are one word to the shell
    if t in SINKS or t.startswith(TEMP_PREFIXES):
        return no_dotdot(t)
    if state is None:
        return False
    var = re.match(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?(/|$)", t)
    if var:
        return var.group(1) in state.temp_vars and no_dotdot(t)
    if t.startswith(("/", "~", "$", "`")) or not t:
        return False
    return state.cwd_temp and no_dotdot(t)


def split_heredocs(command):
    """Return (command without heredoc bodies, [bodies]) in order of appearance."""
    bodies = []
    lines = command.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        tags = re.findall(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", line)
        i += 1
        for tag in tags:
            body = []
            while i < len(lines) and lines[i].strip() != tag:
                body.append(lines[i])
                i += 1
            i += 1  # skip terminator
            bodies.append("\n".join(body))
    return "\n".join(out), bodies


def mask_quotes(text):
    """Replace quoted strings with placeholders; return (masked, {placeholder: original})."""
    table = {}

    def repl(m):
        key = f"\x00Q{len(table)}\x00"
        table[key] = m.group(0)
        return key

    masked = re.sub(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", repl, text)
    return masked, table


def unmask(token, table):
    for k, v in table.items():
        token = token.replace(k, v)
    return token


def legacy_allows(code):
    """The original whole-code rule: a write API is allowed only if the code names a temp
    path and never names the repository."""
    return not WRITE_API.search(code) or bool(TEMP_MARKERS.search(code) and not REPO_MARKERS.search(code))


# ---- Python: trace each write to the path it writes -------------------------------------

TEMP, OTHER = "temp", "other"
MODULES = {"os", "os.path", "shutil", "pathlib", "tempfile", "io", "sys", "json", "subprocess",
           "contextlib", "codecs", "builtins"}
TEMP_CALLS = {"mkdtemp", "mkstemp", "gettempdir", "TemporaryDirectory", "NamedTemporaryFile",
              "TemporaryFile", "SpooledTemporaryFile"}
PATH_FUNCS = {"Path", "PurePath", "PosixPath", "str", "os.fspath", "os.path.join",
              "os.path.abspath", "os.path.realpath", "os.path.normpath", "os.path.expanduser",
              "os.path.dirname", "os.path.expandvars", "pathlib.Path", "pathlib.PurePath", "pathlib.PosixPath"}
OS_FIRST = {"remove", "unlink", "rmdir", "removedirs", "makedirs", "mkdir", "truncate", "chmod",
            "chown", "lchmod", "utime", "mkfifo"}
OS_BOTH = {"rename", "replace", "renames"}
OS_SECOND = {"symlink", "link"}
SHUTIL_DST = {"copy", "copy2", "copyfile", "copytree", "copymode", "copystat"}
PATH_METHODS = {"write_text", "write_bytes", "touch", "mkdir", "unlink", "rmdir",
                "symlink_to", "hardlink_to", "link_to", "chmod", "lchmod"}
OPEN_NAMES = {"open", "io.open", "builtins.open", "codecs.open"}


def has_dotdot(node):
    """A string constant inside `node` that contains a `..` path part."""
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str) and not no_dotdot(n.value)
               for n in ast.walk(node))


class PyWrites(ast.NodeVisitor):
    def __init__(self, state, argv):
        self.state = state
        self.argv = list(argv)
        self.function = None    # (name, params, is_method) while inside a def
        self.class_depth = 0
        self.writes_param = {}  # local function name -> (params, {indices it writes})
        self.env = {}
        self.aliases = {}
        self.unknown = 0        # writes whose target the trace cannot resolve
        self.temp = 0           # writes traced to a temp path

    def dotted(self, node):
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        parts.append(self.aliases.get(node.id, node.id))
        return ".".join(reversed(parts))

    def is_module(self, node):
        return self.dotted(node) in MODULES

    def taint(self, node):
        if node is not None and has_dotdot(node):
            return OTHER
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and node.value:
                return TEMP if is_temp(node.value, self.state) else OTHER  # "$TMPDIR/x" via "..."
            return None
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.Constant):
                    if part.value:
                        return TEMP if is_temp(part.value, self.state) else OTHER
                    continue
                return self.taint(part.value)
            return None
        if isinstance(node, ast.Name):
            return self.env.get(node.id)
        if isinstance(node, ast.Subscript):
            key = node.slice
            if isinstance(key, ast.Index):  # Python < 3.9
                key = key.value
            base = self.dotted(node.value)
            if base == "os.environ":
                return TEMP if isinstance(key, ast.Constant) and key.value == "TMPDIR" else None
            if base == "sys.argv":  # the arguments the command passes
                if isinstance(key, ast.Constant) and isinstance(key.value, int) and 0 < key.value < len(self.argv):
                    return TEMP if is_temp(self.argv[key.value], self.state) else OTHER
                return None
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.taint(node.left)  # string concatenation stays under the left part
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return self.join_taint([node.left, node.right])
        if isinstance(node, (ast.IfExp, ast.BoolOp)):
            items = [node.body, node.orelse] if isinstance(node, ast.IfExp) else node.values
            found = {self.taint(i) for i in items}
            return found.pop() if len(found) == 1 else (OTHER if OTHER in found else None)
        if isinstance(node, ast.Call):
            name = self.dotted(node.func) or ""
            last = name.rsplit(".", 1)[-1]
            if last in TEMP_CALLS and name.startswith("tempfile.") or name in TEMP_CALLS:
                return TEMP
            if name in ("os.getenv", "os.environ.get"):
                arg = node.args[0] if node.args else None
                return TEMP if isinstance(arg, ast.Constant) and arg.value == "TMPDIR" else None
            if name in PATH_FUNCS:
                return self.join_taint(node.args) if node.args else None
            if isinstance(node.func, ast.Attribute) and not self.is_module(node.func.value):
                if node.func.attr == "joinpath":
                    return self.join_taint([node.func.value] + node.args)
                if node.func.attr in ("resolve", "absolute", "with_name", "with_suffix", "expanduser"):
                    return self.taint(node.func.value)
            return None
        if isinstance(node, ast.Attribute) and node.attr == "parent":
            return self.taint(node.value)
        return None

    def join_taint(self, parts):
        """os.path.join(a, b), Path(a, b), a / b: an absolute later part replaces `a`, so the
        result is `a`'s taint only if every later part is a relative string constant."""
        first = self.taint(parts[0])
        for part in parts[1:]:
            if not (isinstance(part, ast.Constant) and isinstance(part.value, str)
                    and not part.value.startswith(("/", "~", "$")) and no_dotdot(part.value)):
                return OTHER if first == OTHER else None
        return first

    def bind(self, target, value_taint):
        if isinstance(target, ast.Name):
            self.env[target.id] = value_taint
        elif isinstance(target, (ast.Tuple, ast.List, ast.Starred)):
            for elt in (target.elts if not isinstance(target, ast.Starred) else [target.value]):
                self.bind(elt, None)  # element-wise unpacking is not traced

    def sink(self, node, what):
        if node is None:
            self.unknown += 1
            return
        t = self.taint(node)
        if t == TEMP:
            self.temp += 1
            return
        if isinstance(t, tuple):
            if self.function and t[1] == self.function[0] and not self.function[2]:
                name, params, _ = self.function  # its own parameter: judged at each call
                self.writes_param.setdefault(name, (params, set()))[1].add(t[2])
            else:  # a method, or an enclosing function's parameter: calls are not traced
                self.unknown += 1
            return
        if t == OTHER:
            snippet = ast.get_source_segment(self.source, node) if hasattr(ast, "get_source_segment") else None
            deny(f"Python code {what} `{(snippet or '?')[:80]}`, which is not a temp path.")
        self.unknown += 1

    @staticmethod
    def arg(node, index, keyword):
        for kw in node.keywords:
            if kw.arg == keyword:
                return kw.value
        return node.args[index] if len(node.args) > index else None

    # visitors, in source order
    def visit_Import(self, node):
        for a in node.names:
            if a.asname:
                self.aliases[a.asname] = a.name

    def visit_ImportFrom(self, node):
        for a in node.names:
            if node.module:
                self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"

    def visit_FunctionDef(self, node):
        for expr in node.decorator_list + node.args.defaults + [d for d in node.args.kw_defaults if d]:
            self.visit(expr)
        params = [a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]
        saved, saved_function = dict(self.env), self.function
        self.env.update({p: ("param", node.name, i) for i, p in enumerate(params)})
        self.function = (node.name, params, self.class_depth > 0)
        depth, self.class_depth = self.class_depth, 0
        for stmt in node.body:
            self.visit(stmt)
        self.class_depth = depth
        self.env, self.function = saved, saved_function
        self.env[node.name] = None

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.class_depth += 1
        self.generic_visit(node)
        self.class_depth -= 1

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.writes_param:
            self.unknown += 1  # `w = save`, `map(save, ...)`: calls through it are not traced

    def visit_Lambda(self, node):
        saved = dict(self.env)
        self.env.update({a.arg: None for a in node.args.args})
        self.generic_visit(node)
        self.env = saved

    def visit_Assign(self, node):
        self.generic_visit(node)
        t = self.taint(node.value)
        for target in node.targets:
            if (isinstance(target, (ast.Tuple, ast.List)) and isinstance(node.value, (ast.Tuple, ast.List))
                    and len(target.elts) == len(node.value.elts)):
                for tt, vv in zip(target.elts, node.value.elts):
                    self.bind(tt, self.taint(vv))
            else:
                self.bind(target, t)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        if isinstance(node.target, ast.Name):
            current = self.env.get(node.target.id)
            self.env[node.target.id] = OTHER if has_dotdot(node.value) else current

    def visit_AnnAssign(self, node):
        self.generic_visit(node)
        if node.value is not None:
            self.bind(node.target, self.taint(node.value))

    def visit_NamedExpr(self, node):
        self.generic_visit(node)
        self.bind(node.target, self.taint(node.value))

    def visit_For(self, node):
        self.visit(node.iter)
        self.bind(node.target, self.iter_taint(node.iter))
        for stmt in node.body + node.orelse:
            self.visit(stmt)

    visit_AsyncFor = visit_For

    def iter_taint(self, node):
        """The taint of each item: a literal list of paths, or a temp directory's listing."""
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            found = {self.taint(e) for e in node.elts}
            return found.pop() if len(found) == 1 else (OTHER if OTHER in found else None)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("glob", "rglob", "iterdir")):
            return self.taint(node.func.value)
        return None

    def visit_ListComp(self, node):  # a comprehension has its own scope
        saved = dict(self.env)
        for gen in node.generators:
            self.visit(gen.iter)
            self.bind(gen.target, self.iter_taint(gen.iter))
            for cond in gen.ifs:
                self.visit(cond)
        for part in ([node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]):
            self.visit(part)
        self.env = saved

    visit_SetComp = visit_GeneratorExp = visit_DictComp = visit_ListComp

    def visit_With(self, node):
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self.bind(item.optional_vars, self.taint(item.context_expr))
        for stmt in node.body:
            self.visit(stmt)

    visit_AsyncWith = visit_With

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):  # a direct call by name is not an alias
            self.visit(node.func)
        for a in node.args + [kw.value for kw in node.keywords]:
            self.visit(a)
        name = self.dotted(node.func) or ""
        on_module = "." in name and name.rsplit(".", 1)[0] in MODULES  # also `from shutil import copytree`
        if on_module or isinstance(node.func, ast.Name):
            last = name.rsplit(".", 1)[-1]
        else:
            last = node.func.attr if isinstance(node.func, ast.Attribute) else ""  # (p / "x").write_text
        if last == "chdir" and (on_module or name in ("chdir",)):
            self.state = self.state.copy()  # later relative paths are relative to the new directory
            self.state.cwd_temp = self.taint(self.arg(node, 0, "path")) == TEMP
        elif isinstance(node.func, ast.Name) and node.func.id in self.writes_param:
            params, written = self.writes_param[node.func.id]
            for i in sorted(written):
                if i >= len(params):
                    self.unknown += 1
                    continue
                self.sink(self.arg(node, i, params[i]), f"passes to {node.func.id}(), which writes,")
        elif name in OPEN_NAMES:
            mode = self.arg(node, 1, "mode")
            if mode is None or (isinstance(mode, ast.Constant) and isinstance(mode.value, str)
                                and not re.search(r"[wax+]", mode.value)):
                return
            self.sink(self.arg(node, 0, "file"), "opens for writing")
        elif isinstance(node.func, ast.Attribute) and not on_module and last == "open":
            receiver = node.func.value
            if self.taint(receiver) is None and self.dotted(receiver):
                self.unknown += 1  # gzip.open, tarfile.open, obj.open: not a Path we can judge
                return
            mode = self.arg(node, 0, "mode")
            if mode is None or (isinstance(mode, ast.Constant) and isinstance(mode.value, str)
                                and not re.search(r"[wax+]", mode.value)):
                return
            self.sink(receiver, "opens for writing")
        elif on_module and name.startswith("os.") and last == "open":
            flags = self.arg(node, 1, "flags")
            text = ast.get_source_segment(self.source, flags) if flags is not None else ""
            if flags is None or not re.fullmatch(r"\s*os\.O_RDONLY\s*", text or ""):
                self.sink(self.arg(node, 0, "path"), "opens")
        elif on_module and name.startswith("os.") and last in OS_FIRST | OS_BOTH | OS_SECOND:
            if last in OS_FIRST or last in OS_BOTH:
                self.sink(self.arg(node, 0, "src" if last in OS_BOTH else "path"), f"calls os.{last} on")
            if last in OS_BOTH or last in OS_SECOND:
                self.sink(self.arg(node, 1, "dst"), f"calls os.{last} onto")
        elif on_module and name.startswith("shutil."):
            if last in SHUTIL_DST:
                self.sink(self.arg(node, 1, "dst"), f"calls shutil.{last} into")
            elif last == "move":
                self.sink(self.arg(node, 0, "src"), "moves")
                self.sink(self.arg(node, 1, "dst"), "moves into")
            elif last == "rmtree":
                self.sink(self.arg(node, 0, "path"), "removes")
        elif isinstance(node.func, ast.Attribute) and not on_module:
            receiver = node.func.value
            if last in PATH_METHODS:
                self.sink(receiver, f"calls .{last}() on")
            elif last in ("rename", "replace") and len(node.args) + len(node.keywords) == 1:
                self.sink(receiver, f"calls .{last}() on")  # str.replace takes two arguments
                self.sink(self.arg(node, 0, "target"), f"calls .{last}() onto")


def check_python(code, where, state, argv=()):
    """Deny a traced write outside temp; otherwise the whole-code rule decides, relaxed only
    when every write it sees is traced to a temp path."""
    if legacy_allows(code):
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError):
            return
        visitor = PyWrites(state, argv)
        visitor.source = code
        visitor.visit(tree)  # may still deny a write traced outside temp
        return
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        deny(f"{where} calls a file-writing API outside $TMPDIR.")
    visitor = PyWrites(state, argv)
    visitor.source = code
    visitor.visit(tree)
    pending = sum(len(v[1]) for v in visitor.writes_param.values())
    seen = len(list(WRITE_API.finditer(code)))
    if visitor.unknown or visitor.temp < seen - pending or visitor.temp == 0:
        deny(f"{where} calls a file-writing API outside $TMPDIR (or one whose target "
             f"cannot be traced to a temp path).")


# ---- shell ------------------------------------------------------------------------------

def is_python(word):
    return bool(re.match(r"python(\d(\.\d+)?)?$", word.split("/")[-1]))


def python_argv(words, table):
    """sys.argv for `python [opts] - args...` or `python [opts] script args...`."""
    words = [unmask(w, table) for w in words]
    idx = next((i for i, w in enumerate(words) if is_python(w)), None)
    if idx is None:
        return []
    args = words[idx + 1:]
    while args and args[0].startswith("-") and args[0] != "-":
        if args[0] in ("-c", "-m"):
            return []
        opt = args.pop(0)
        if opt in PYTHON_OPTS_WITH_VALUE and args:
            args.pop(0)
    return args


def check(command, state=None):
    state = state or State()
    shell, bodies = split_heredocs(command)
    masked, table = mask_quotes(shell)
    masked = masked.replace(">|", "> ")  # noclobber override: still a redirect
    bodies = iter(bodies)
    stack = []

    # 1. Redirections, on the whole text (a `cd` cannot make an absolute target temp).
    parts = re.split(r"(&&|\|\||[;|\n])", masked)
    segments = parts[0::2]
    seps = parts[1::2] + [""]
    chain_base = state.cwd_temp  # the cwd if a `cd` in this && chain failed
    compounds = []  # chain_base saved at each open for/while/if/case: its body has its own chain
    prev_sep = ""

    for n, (segment, sep) in enumerate(zip(segments, seps)):
        stripped = segment.strip()
        for _ in range(re.match(r"^[\s({]*", stripped).group(0).count("(")):
            stack.append((state.copy(), chain_base))  # a subshell: its cd and variables do not leak
            chain_base = state.cwd_temp  # it starts in the directory it inherits

        for m in REDIRECT.finditer(segment):
            target = unmask(m.group(1), table).rstrip(";&|)")  # `>/dev/null;` targets /dev/null
            if not is_temp(target, state):
                deny(f"output redirection to `{target[:80]}`.")
        raw = unmask(segment, table)  # a heredoc inside "$(cat <<'EOF' ...)" counts too
        heredocs = len(re.findall(r"<<-?\s*\S", raw)) - len(re.findall(r"<<<", raw))
        out_targets = [unmask(m.group(1), table) for m in REDIRECT.finditer(segment)]
        plain = NOT_WRITTEN.sub(" ", REDIRECT.sub(" ", segment))

        words = plain.split()
        if words:
            words[-1] = re.sub(r"(?<=.)[)}]+$", "", words[-1])  # `cp a b)`: the `)` closes a subshell
        head = re.sub(r"^[({]+|[)};]+$", "", words[0]) if words else ""
        if head in ("for", "while", "until", "if", "case", "select"):
            compounds.append(chain_base)  # the body starts from here; `;` in it resets to here
            chain_base = state.cwd_temp
        elif head in ("done", "fi", "esac") and compounds:
            chain_base = compounds.pop() and chain_base
        while words:  # `(cd x`, `{ cmd`, `mk(){ cmd`
            first = re.sub(r"^[({]+|^[A-Za-z_][A-Za-z0-9_]*\(\)\{?", "", words[0])
            if first:
                words[0] = first
                break
            words.pop(0)
        made = re.match(r"^(?:export\s+|local\s+)?([A-Za-z_][A-Za-z0-9_]*)=\$\((mktemp\b[^)]*)\)$", stripped)
        if made:  # D=$(mktemp -d): split above as `D=$(mktemp` and `-d)`
            if mktemp_is_temp(unmask(made.group(2), table)):
                state.temp_vars.add(made.group(1))
            else:
                state.temp_vars.discard(made.group(1))
            words = []
        exported = bool(words) and words[0] in ("export", "local", "declare", "readonly", "typeset")
        if exported:
            words.pop(0)
            while words and words[0].startswith("-"):
                words.pop(0)
        while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
            name, value = words.pop(0).split("=", 1)
            if exported or not words:  # `VAR=x cmd` sets VAR for cmd only
                if is_temp(unmask(value, table), state):
                    state.temp_vars.add(name)
                else:
                    state.temp_vars.discard(name)
        while words and words[0] in LEADING_WORDS:
            words.pop(0)

        cmd = words[0].split("/")[-1] if words else ""
        args = [unmask(w, table) for w in words[1:]]
        paths = [a for a in args if not a.startswith("-")]

        # 2. State: cd, for-loops.
        if cmd in ("cd", "pushd") and "|" in (sep, prev_sep):
            pass  # a `cd` in a pipeline runs in a subshell: no effect
        elif cmd in ("cd", "pushd"):
            target = paths[0] if paths else ""
            state.cwd_temp = bool(paths) and is_temp(target, state)
            bare = target.replace('"', "").replace("'", "").rstrip("/") or "/"
            if bare in TEMP_ROOTS or re.fullmatch(r"(/private)?/tmp/claude-\d+", bare):
                chain_base = state.cwd_temp  # always exists: the cd cannot fail
            nxt = segments[n + 1].split() if n + 1 < len(segments) else []
            if sep == "||" and nxt[:1] in (["exit"], ["return"]):
                chain_base = state.cwd_temp  # `cd X || exit`: past here the cd succeeded
        elif cmd == "popd":
            state.cwd_temp = False
        elif cmd == "for" and len(args) >= 2 and args[1] == "in":
            items = args[2:]
            if items and all(is_temp(i, state) for i in items):
                state.temp_vars.add(args[0])
            else:
                state.temp_vars.discard(args[0])

        # 3. File-changing commands.
        elif cmd in INPLACE_COMMANDS:
            if any(a == "-i" or a.startswith("-i") or a.startswith("--in-place") for a in args):
                if not paths or not all(is_temp(p, state) for p in paths[-1:]):
                    deny(f"`{cmd} -i` edits a file in place.")
        elif cmd in FILE_COMMANDS:
            if cmd in ("cp", "rsync", "install"):
                dest = paths[-1:]  # copying FROM the repo is fine; the destination must be temp
            elif cmd == "dd":
                dest = [a[3:] for a in args if a.startswith("of=")]
            elif cmd in ("chmod", "chown"):
                dest = [a for a in args if a not in MODE_FLAGS][1:]  # first operand: mode or owner (`-x` too)
            elif cmd == "ln":
                dest = paths[-1:] if len(paths) > 1 else ["."]
            else:
                dest = paths
            if dest and not all(is_temp(p, state) for p in dest):
                deny(f"`{cmd}` changes `{next(p for p in dest if not is_temp(p, state))[:80]}`.")

        # 4. Code: inline (anywhere in the segment) and heredocs.
        for m in INLINE.finditer(segment):
            code = unmask(m.group(2), table)[1:-1]
            interp = m.group(1)
            if is_python(interp):
                check_python(code, "inline code", state)
            elif interp in ("bash", "sh", "zsh"):
                check(code, state.copy())
            elif not legacy_allows(code):
                deny("inline code calls a file-writing API outside $TMPDIR.")
        is_py = any(is_python(w) for w in words)
        is_sh = any(w.split("/")[-1] in ("bash", "sh", "zsh") for w in words)
        for _ in range(max(heredocs, 0)):
            body = next(bodies, None)
            if body is None:
                break
            if is_py:
                check_python(body, "heredoc code", state, python_argv(words, table))
            elif is_sh:
                check(body, state.copy())
            else:  # `cat > file`, `tee`, other consumers: judged now, as code if it parses
                where = "heredoc code" if not out_targets else f"heredoc written to `{out_targets[0][:60]}`"
                try:
                    ast.parse(body)
                except (SyntaxError, ValueError):
                    if not legacy_allows(body):
                        deny(f"{where} calls a file-writing API outside $TMPDIR.")
                else:
                    check_python(body, where, state)

        closing, previous = stripped, None
        while closing != previous:  # the `)` of `$(...)`, `$((...))` closes no subshell
            previous, closing = closing, re.sub(r"\$\(\([^()]*\)\)|\$\([^()]*\)", "", closing)
        for _ in range(re.search(r"[\s)}]*$", closing).group(0).count(")")):
            if stack:
                state, chain_base = stack.pop()

        prev_sep = sep
        if sep in ("", "&&", "|"):  # a pipeline runs only if the && chain got this far
            continue
        state.cwd_temp = state.cwd_temp and chain_base  # a `cd` in the chain may have failed
        chain_base = state.cwd_temp

    for body in bodies:  # heredocs not matched to a command: judged on their own
        try:
            ast.parse(body)
        except (SyntaxError, ValueError):
            if not legacy_allows(body):
                deny("heredoc code calls a file-writing API outside $TMPDIR.")
        else:
            check_python(body, "heredoc code", state)


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        sys.exit(0)  # cannot tell who is calling; the sandbox and other guards still apply
    is_subagent = any(payload.get(k) not in (None, "") for k in AGENT_KEYS)
    if not is_subagent:
        sys.exit(0)
    try:
        command = (payload.get("tool_input") or {}).get("command") or ""
        if not isinstance(command, str):
            deny("unreadable command.")
        check(command)
    except SystemExit:
        raise
    except Exception as exc:  # fail closed for subagents
        deny(f"the guard could not analyse the command ({type(exc).__name__}).")
    sys.exit(0)


if __name__ == "__main__":
    main()
