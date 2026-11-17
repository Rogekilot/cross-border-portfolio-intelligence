"""Tests for .claude/hooks/guard_bash.py (G-1, 2026-10-22).

Run with the hook's own interpreter (python3, not the product's uv env):
    python3 -m unittest discover -s tests/harness

Each case runs the hook as Claude Code does: a JSON payload on stdin, exit 0 = allow,
exit 2 = deny. "Repo" cases must stay blocked; "scratch" cases are false positives the
earlier version produced (all taken from real subagent commands, shortened).
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(os.environ.get("GUARD_BASH_HOOK")  # a candidate version, before it is installed
            or Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "guard_bash.py")
REPO = "/Users/someone/Desktop/Fin Web"


def run_hook(command, subagent=True):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if subagent:
        payload["agent_type"] = "engineer"
    proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stderr


class GuardBashCase(unittest.TestCase):
    def assertAllowed(self, command):
        code, err = run_hook(command)
        self.assertEqual(code, 0, f"expected allow, got: {err}\n--- command:\n{command}")

    def assertBlocked(self, command):
        code, err = run_hook(command)
        self.assertEqual(code, 2, f"expected block\n--- command:\n{command}")
        self.assertIn("BLOCKED (guard_bash)", err)


class MainSession(GuardBashCase):
    def test_main_session_is_not_restricted(self):
        code, _ = run_hook(f'sed -i "" s/a/b/ src/x.py; echo x > STATUS.md', subagent=False)
        self.assertEqual(code, 0)


class RepoWritesStayBlocked(GuardBashCase):
    def test_shell_forms(self):
        for cmd in [
            "sed -i '' 's/a/b/' src/performance/manifest.py",
            "sed -i.bak 's/a/b/' src/a.py 2>/dev/null",
            "cat >> implementation/FEATURE_TECH_PLAN.md <<'EOF'\nmore\nEOF",
            "echo x > STATUS.md",
            "cp $TMPDIR/new.py src/risk/engine.py",
            f'cp "$TMPDIR/b.json" "{REPO}/data/marketdata/BENCHMARKS.json"',
            "mkdir -p designs/hg1-revision/direction-a",
            "rm -rf src/old",
            "chmod +x scripts/run.sh",
            "mv $TMPDIR/x.py tests/product/x.py",
            "tee src/a.py < $TMPDIR/a.py",
        ]:
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd)

    def test_working_directory_and_variables(self):
        for cmd in [
            "cd $TMPDIR && cd \"%s\" && sed -i '' s/a/b/ src/a.py" % REPO,
            "cd $TMPDIR/x && cd .. && cd .. && rm -rf src",
            "(cd $TMPDIR && echo ok); rm -rf src",            # a subshell's cd does not leak
            "S=$TMPDIR/x; S=src; rm -rf $S",                  # reassigned to a repo path
            "VAR=$TMPDIR/x rm -rf $VAR",                      # prefix assignment is not a shell var
            "rm -rf $TMPDIR/../../Users/someone",             # `..` is never temp
            "rm -rf $UNKNOWN/src",
            "for f in src/a.py src/b.py; do rm $f; done",
            # a `cd` joined by `;`, a newline or `||` may have failed (review finding 2)
            "cd $TMPDIR/mut; sed -i '' s/a/b/ src/risk/x.py",
            "cd $TMPDIR/mut\nrm -rf src",
            "cd $TMPDIR/mut || true; rm -rf src",
            "cd $TMPDIR/mutbase; cp \"%s/src/a.py\" src/a.py" % REPO,
            "cd $TMPDIR/m && (ls; cd \"%s\" && x=$(pwd); rm -rf src)" % REPO,
            # smaller shell forms (review finding 6)
            "chmod -x scripts/run.sh",
            "chmod -w src/a.py",
            "echo x >| STATUS.md",
            "pushd $TMPDIR/x; popd; rm -rf src",
            "S=$TMPDIR/x; declare -x S=src; rm -rf $S",
            "D=$(mktemp -d -p src) && cp $TMPDIR/a.py $D/",
            # a `cd` inside a loop or if body (re-review finding 10)
            "for m in m1 m2; do cd $TMPDIR/$m; sed -i '' s/x/y/ src/risk/x.py; done",
            "if true; then cd $TMPDIR/m; rm -rf src; fi",
            "while read m; do\n  cd $TMPDIR/$m\n  rm -rf src\ndone < $TMPDIR/list",
            "cd $TMPDIR/m && for f in a b; do cp x $f; done; rm -rf src",
            # subshell and pipeline tracking (finding 11)
            "(for m in a; do echo; done); cd $TMPDIR/mut; rm -rf src",
            "(if true; then echo; fi); cd $TMPDIR/mut; rm -rf src",
            "cd $TMPDIR/m && (x=$(dirname $(pwd)); y=$((1+2))); rm -rf src",
            "cd $TMPDIR | cat && rm -rf src",
            # a heredoc inside a quoted command substitution (finding 13)
            "python3 -c \"$(cat <<'EOF'\nopen('src/a.py','w').write('x')\nEOF\n)\"",
        ]:
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd)

    def test_python_forms(self):
        for cmd in [
            "python3 - <<'EOF'\np='src/a.py'\ns=open(p).read()\nopen(p,'w').write(s)\nEOF",
            "python3 -c \"open('STATUS.md','a').write('x')\"",
            "python3 - <<'EOF'\nfrom pathlib import Path\nPath('src/x.py').write_text('x')\nEOF",
            "python3 - <<'EOF'\nimport shutil\nshutil.copy('/tmp/x', 'src/x.py')\nEOF",
            "python3 - <<'EOF'\nimport os\nos.remove('tests/product/test_a.py')\nEOF",
            "python3 - <<'EOF'\nfrom os import remove\nremove('tests/product/test_a.py')\nEOF",
            "python3 - <<'EOF'\nfrom shutil import copytree as ct\nct('/tmp/x', 'src/y')\nEOF",
            "python3 - <<'EOF'\nimport shutil as sh\nsh.rmtree('src')\nEOF",
            "python3 - <<'EOF'\nfrom pathlib import Path\n(Path('src') / 'x.py').write_text('x')\nEOF",
            "python3 - <<'EOF'\nfrom pathlib import Path\nwith Path('STATUS.md').open('a') as f:\n    f.write('x')\nEOF",
            # a local helper that writes its parameter, called with a repo path
            "python3 - <<'EOF'\ndef sub(path, a, b):\n    t=open(path).read()\n    open(path,'w').write(t.replace(a,b))\nsub('src/a.py','x','y')\nEOF",
            # sys.argv: the command passes a repo path
            "python3 - src/a.py <<'EOF'\nimport sys\nopen(sys.argv[1],'w').write('x')\nEOF",
            # a script written to scratch is judged when written, however it is run (finding 3)
            "cat > $TMPDIR/fix.py <<'E'\nopen('src/a.py','w').write('x')\nE\npython3 $TMPDIR/fix.py",
            "cat > $TMPDIR/fix.py <<'E'\nopen('src/a.py','w').write('x')\nE\ncd $TMPDIR && python3 fix.py",
            "cat > $TMPDIR/fix.py <<'E'\nopen('src/a.py','w').write('x')\nE\npython3 < $TMPDIR/fix.py",
            # inline code after a wrapper, and non-Python inline code (finding 4)
            "timeout 60 python3 -c \"open('STATUS.md','a').write('x')\"",
            "nohup python3 -c \"open('STATUS.md','a').write('x')\"",
            "echo a | xargs -n1 python3 -c \"open('src/a.py','w').write('x')\"",
            "uv run --with rich python -c \"open('src/a.py','w').write('x')\"",
            "ruby -e \"File.open('src/a.rb','w').write(1)\"",
            # Python shapes the trace must not wave through (finding 5)
            "python3 - <<'E'\nfrom pathlib import Path\nclass W:\n    def __init__(self,p): self.p=Path(p)\n"
            "    def save(self,t): self.p.write_text(t)\nW('src/a.py').save('x')\nE",
            "python3 - <<'E'\nimport os\ndef save(t, path='src/a.py'):\n    open(path,'w').write(t)\n"
            "save('x')\nsave('y', os.environ['TMPDIR'] + '/b')\nE",
            "python3 - <<'E'\nimport os\ndef save(path):\n    open(path,'w').write('x')\nw = save\n"
            "w('src/a.py')\nsave(os.environ['TMPDIR'] + '/b')\nE",
            "python3 - <<'E'\nimport gzip\ngzip.open('src/b.gz','wt').write('x')\nE",
            "python3 - <<'E'\nimport os\nopen(os.environ['TMPDIR'] + '/../../R/STATUS.md','a')\nE",
            "python3 - <<'E'\nimport os\np = os.environ['TMPDIR']\np += '/../../R/STATUS.md'\nopen(p,'a')\nE",
            "python3 - <<'E'\nimport os\np='src/a.py'\n[p for p in [os.environ['TMPDIR']]]\nopen(p,'w')\nE",
            "python3 - <<'E'\ndef f(fh=open('src/a.py','w')): pass\nE",
            "cd $TMPDIR && python3 - <<'E'\nimport contextlib\nwith contextlib.chdir('%s'):\n"
            "    open('src/a.py','w')\nE" % REPO,
            "cd $TMPDIR && python3 -W ignore - \"%s/src/a.py\" <<'E'\nimport sys\nopen(sys.argv[1],'w')\nE" % REPO,
            # a join with an absolute later part (finding 12)
            "python3 - <<'E'\nimport os\nfrom pathlib import Path\n"
            "Path(os.environ['TMPDIR'], '%s/STATUS.md').write_text('x')\nE" % REPO,
            "python3 - <<'E'\nimport os\nfrom pathlib import Path\n"
            "Path(os.environ['TMPDIR']).joinpath('%s/STATUS.md').write_text('x')\nE" % REPO,
            "python3 - <<'E'\nimport os, shutil, glob\nT = os.environ['TMPDIR']\n"
            "for p in glob.glob('%s/src/*.py'):\n    shutil.copy('/tmp/new.py', os.path.join(T, p))\nE" % REPO,
            # chdir back into the repository inside Python
            f"cd $TMPDIR && python3 - <<'EOF'\nimport os\nos.chdir('{REPO}')\nopen('src/a.py','w').write('x')\nEOF",
            # shell code passed with -c is checked too
            "bash -c 'echo x > src/a.py'",
        ]:
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd)

    def test_untraceable_python_write_keeps_the_old_rule(self):
        # The target cannot be traced and the code names the repository: blocked as before.
        self.assertBlocked("python3 - <<'EOF'\nimport json\nROOT='src/'\nfor p in json.load(open('x')):\n"
                           "    open(p,'w').write('')\nEOF")


class ScratchWritesAllowed(GuardBashCase):
    """G-1: false positives the earlier version produced."""

    def test_shell_forms(self):
        for cmd in [
            "chmod +x $TMPDIR/mutrun.sh",
            "cp -R . \"$TMPDIR/rv42base\" 2>/dev/null; echo copied",
            "cp src/a.py $TMPDIR/series.pristine 2>&1 | tail -1",
            "sed -i.bak 's/x/x/' /dev/null 2>/dev/null",
            'M="$TMPDIR/mut"; rm -rf "$M"; mkdir -p "$M"; cp -R src tests "$M"/ 2>&1 | tail -2',
            "SC=$TMPDIR/rv41 && mkdir -p $SC && rsync -a --exclude .git ./ $SC/base/",
            "D=$(mktemp -d) && cp src/a.py $D/ && rm -rf $D",
            "export W=$TMPDIR/w; cp -R src $W/",
            "cd \"$TMPDIR/rv41\" && rm -rf mut1 && cp -R base mut1 && cd mut1 && sed -i '' 's/a/b/' src/risk/x.py",
            "for m in m1 m2; do cd $TMPDIR/$m && sed -i '' s/x/y/ src/risk/x.py; done",
            "cd $TMPDIR/m && for f in a b; do cp x $f; done",
            "cd $TMPDIR/m && (x=$(dirname $(pwd)); cp a b) && rm -rf build",
            "cd $TMPDIR && cat > ext.swift <<'EOF'\nprint(1)\nEOF",
            "cd $TMPDIR/rv42/p && for f in a.py b.py; do cp \"$TMPDIR/rv41/$f\" .; done",
            "for d in $TMPDIR/a $TMPDIR/b; do rm -rf $d; done",
            "R=\"$TMPDIR/rv34\"; mk(){ cp -R \"$R/base\" \"$R/$1\"; }",
            "cd $TMPDIR/mutbase && cp \"%s/src/a.py\" src/a.py" % REPO,
            "cd $TMPDIR/m || exit 1; sed -i '' s/a/b/ src/x.py",
            "cd $TMPDIR; cp src/a.py x.py",  # $TMPDIR itself always exists
            "cd $TMPDIR/m && cat a | grep b && sed -i '' s/a/b/ src/x.py",
            "sed -n 1,5p src/a.py; cp src/a.py /tmp/claude-503/x/",
        ]:
            with self.subTest(cmd=cmd):
                self.assertAllowed(cmd)

    def test_python_reads_repo_writes_scratch(self):
        for cmd in [
            # the G-1 reviewer probe: imports from the repo, writes under mkdtemp
            "python3 - <<'EOF'\nimport os, sys, tempfile\nfrom pathlib import Path\n"
            f"sys.path.insert(0, '{REPO}/tests/product')\n"
            "base = Path(tempfile.mkdtemp(dir=os.environ['TMPDIR'])).resolve()\n"
            "victim = base / 'victim.txt'; victim.write_text('keep me')\n"
            "os.mkdir(base / 'rt', 0o700)\nEOF",
            # copy FROM the repository INTO scratch
            "python3 - <<'EOF'\nimport os, shutil\nT = os.environ['TMPDIR']\n"
            f"ROOT = '{REPO}'\nM = os.path.join(T, 'mut')\n"
            "shutil.copytree(os.path.join(ROOT, 'src'), os.path.join(M, 'src'))\nEOF",
            # read a repo file, write the edited copy to scratch
            "python3 - <<'EOF'\np='src/risk/engine.py'\nt=open(p).read()\n"
            "open('/tmp/claude-503/engine_new.py','w').write(t)\nEOF",
            # sys.argv carries temp paths
            "python3 - \"$TMPDIR/cp4p3/probe.json\" <<'EOF'\nimport json,sys\n"
            "d=json.load(open('methodology/x.json'))\njson.dump(d, open(sys.argv[1],'w'))\nEOF",
            # $TMPDIR inside a double-quoted -c is expanded by the shell
            "python3 -c \"import json\nfor f in ('a.json',):\n  json.dump({},open('$TMPDIR/'+f+'.ports','w'))\"",
            # a local helper that writes its parameter, called with temp paths
            "python3 - <<'EOF'\nimport os\nT = os.environ['TMPDIR'] + '/rv'\n"
            "def sub(path, old, new):\n    t = open(path).read()\n    open(path, 'w').write(t.replace(old, new))\n"
            "sub(f'{T}/s2/src/a.py', 'x', 'y')\nEOF",
            # relative writes after cd into scratch
            "cd \"$TMPDIR/rv\" && python3 - <<'EOF'\ns=open('e2e.py').read()\nopen('e2e.py','w').write(s)\nEOF",
            # a scratch script written by a heredoc, judged when written
            "cat > \"$TMPDIR/mutate.py\" <<'EOF'\nimport os, shutil\nT = os.environ['TMPDIR']\n"
            f"ROOT = '{REPO}'\nshutil.copytree(os.path.join(ROOT, 'src'), os.path.join(T, 'mut', 'src'))\n"
            "EOF\npython3 \"$TMPDIR/mutate.py\"",
            # a closure writing the enclosing function's parameter (finding 8: no crash)
            "python3 - <<'EOF'\nimport os\nT = os.environ['TMPDIR']\nopen(T + '/a', 'w')\n"
            "def outer(path):\n    def inner(): open(path, 'w').write('x')\n    inner()\nEOF",
            # read-only os.open (finding 9)
            "python3 - <<'EOF'\nimport os\nfd = os.open('src/a.py', os.O_RDONLY)\nEOF",
        ]:
            with self.subTest(cmd=cmd[:70]):
                self.assertAllowed(cmd)

    def test_known_false_positive_kept(self):
        # A heredoc script whose write target is only sys.argv cannot be traced when it is
        # written; the older rule refused it too.
        self.assertBlocked("cat > \"$TMPDIR/cp4/merge.py\" <<'EOF'\nimport json, sys\n"
                           "json.dump({}, open(sys.argv[3], 'w'))\nEOF\n"
                           "python3 \"$TMPDIR/cp4/merge.py\" \"$TMPDIR/a\" \"$TMPDIR/b\" \"$TMPDIR/c\"")


class ReadOnlyCommands(GuardBashCase):
    def test_reads_and_tests_pass(self):
        for cmd in [
            "git status --short && git diff --stat",
            "uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t .",
            "grep -rn 'x' src | head; sed -n 1,20p src/a.py",
            "python3 - <<'EOF'\nimport json\nprint(json.load(open('data/x.json')))\nEOF",
            "psql -h /tmp -c 'select 1' 2>&1 | tail -3",
        ]:
            with self.subTest(cmd=cmd):
                self.assertAllowed(cmd)


if __name__ == "__main__":
    unittest.main()
