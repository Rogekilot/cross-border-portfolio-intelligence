# PD-0077 — The loader password is typed by the owner only

**Status:** accepted
**Date:** 2026-11-01
**Decided by:** the designated human product owner, in this chat.
**Recorded by:** the main session (PM). Recorded, not decided.
**Bears on:**
- [PD-0076](PD-0076-r6-install-plan-choices-a-to-e.md) choice B;
- `implementation/CP7_F1_R6_INSTALL_PLAN.md` section 3 B, section 6 and section 11;
- `implementation/CP7_F1_REAL_PATH_DESIGN.md` 1.2 rule 4 and 3.3;
- review TR6C-1 (`reviews/TECH_REVIEW.md`, "F1 R6 PD-0076 follow-up — review (2026-11-01)").

## Context

PD-0076 choice B is "You executor, agent loader": a named agent session may be given the loader password
for a load window only, by a prompt, never by a file. The engineer and then the independent reviewer found
that no route meets both B and design 1.2 rule 4:
- An agent session's shell has no terminal (`/dev/tty`: "Device not configured"; `getpass` hits end of file).
- Rule 4 rules out the environment, a project file, a passfile and a service file.
- Chat is the only remaining channel. It writes the password into the session transcript on disk, which
  every agent session of the same OS user can read, and it sends the password off the machine.

B says "may", so the owner typing the password personally is already within it.

## Decision

Question asked, verbatim:

> Choice B let an agent session hold the loader password during a window. The only way to get a password into an agent session is to type it in chat, which saves it in that session's transcript on disk (readable by every agent session of your user) and sends it off the machine. How should the loader password be handled?

Options shown, verbatim:
- **"I type it myself (Recommended)"**: "You type the loader password at the tool's prompt in your own terminal for each window; no agent session ever holds it. This is within B as decided (B says 'may'), costs nothing now, and the plan makes it the only route."
- **"Default to me; decide later"**: "The plan makes your own terminal the default, and any agent-held route waits for a separate decision before R8. Keeps B's option open without choosing a route now."
- **"Allow chat, accept the limit"**: "You may give an agent session the loader password in chat. Recorded limit: the password stays in the transcript file and leaves the machine; you rotate it with \password after the window. Not recommended."

**Answer, verbatim:** "I type it myself (Recommended)"

## Consequences

1. **The owner types the loader password, in the owner's own terminal, at the tool's prompt, for each
   window.** The only route is that prompt in the owner's terminal. No agent session holds the loader
   password, and none is given it in chat.
2. In practice this narrows PD-0076 B to "the owner alone" for both the executor and the loader. PD-0076 is
   unchanged as a record. An agent-held loader route would need a new owner decision.
3. The design 1.2 rule 4 limit for an agent-held loader credential no longer arises. The HG4 package states
   that the owner held both credentials.
4. Unchanged and still open:
   - R6R-L1: no tool performs the step (4a) registration. R8's plan must name or build one, and that tool
     must take its password from the owner's terminal prompt.
   - TR6R-L1: an UNKNOWN registration.
