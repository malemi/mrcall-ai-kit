---
description: Answer with a re-read pass — before the answer reaches you, the session reads it back against a short checklist and fixes what fails. Takes the question as its argument; `on`/`off`/`status`/`unregister` manage the always-on mode instead.
allowed-tools: Bash(python3 *) Bash(ls *) Bash(cat *) Bash(mkdir *) Bash(touch *) Bash(rm *) Read
---

Answer a question with a re-read pass over the finished answer.

The hook script lives at `~/.config/mrcall-ai-kit/reread-hook.py` and its
checklist at `~/.config/mrcall-ai-kit/reread-checklist.md` (both installed by
`./install.sh --features reread`). It is dormant unless one of two flags exists
in that directory: `reread.once`, armed for a single answer and cleared by the
hook itself, or `reread.on`, which stays until switched off. This command is the
only thing that creates, removes or inspects either, and the only thing that
registers the hook in `~/.claude/settings.json`.

Argument: `$ARGUMENTS`.

- **Anything that is not a verb below is the question.** Arm the guard for this
  one answer, then answer the question. This is the common case and what the
  command is for: `/sc perché il cron non parte?`
- `on`, `off`, `status`, `unregister` manage the always-on mode.
- No argument at all: show `status` and stop.

## `<question>` — the one-shot, and the main path

Do these in order:

1. Make sure the hook is registered (see *Shared: locating the hook entry*). It
   is inert without a flag, costing one `Path.exists()` per turn, so registering
   it is not a commitment to anything.
2. `touch ~/.config/mrcall-ai-kit/reread.once`
3. Answer the question — the rest of `$ARGUMENTS` — normally.

Then stop thinking about it. The hook clears that flag itself when it fires, so
the arming never outlives the turn and never leaks into the next question.

Say nothing about any of this. No "arming the guard", no note that a re-read
will happen, no mention of the flag. The user asked a question and wants its
answer; the pass is machinery, and machinery that announces itself is noise.

## What it does, when asked

The rules about how to answer are not new and are not in this hook. They live in
the managed `CLAUDE.md` a repository installs. The hook exists because by the end
of a long turn those rules are thousands of tokens behind, and a rule out of
sight is a rule not applied. On each finished answer the hook hands it back once,
with the checklist, and the session fixes what fails before the answer is shown.

It judges nothing and calls no model. It re-presents a list; the session does the
work, in the same turn, with the answer in front of it.

Cost: one extra pass of the model already running, on answers longer than
`SC_MIN_CHARS` (default 500). Short answers are skipped, and the arming is spent
either way rather than waiting for a long enough answer to come along.

## What to print — for the verbs below, not for a question

When the argument is a question, the output is the answer to that question and
nothing else. This section does not apply to it.

For `on`, `off`, `status` and `unregister`: everything here about flag files,
`settings.json` and registration tells **you** how to do the work, and none of
it is the answer. The answer is two clauses — what state the guard is in, and
the command that changes it. Print that, stop.

Never report the flag file, the install path, `settings.json`, registration or
backups, not as detail and not as reassurance. One exception: say more when
something is **broken**, because the user cannot act on a problem they cannot
see.

## Shared: locating the hook entry

Registration lives at `hooks.Stop` in `~/.claude/settings.json`, as a
matcher-group entry whose nested `hooks` array contains a command running
`reread-hook.py`:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "python3 /home/<user>/.config/mrcall-ai-kit/reread-hook.py" } ] }
    ]
  }
}
```

Read the file with `python3 -c` and `json`, never by hand-editing text. Preserve
every other key exactly. Write it back with `json.dump(..., indent=2)`.

## `on` — always-on mode

For a stretch of work where every answer should get the pass, rather than the
one-shot above. Register the hook if no entry running `reread-hook.py` is
present, then create the persistent flag `~/.config/mrcall-ai-kit/reread.on`. If `~/.config/mrcall-ai-kit/reread-hook.py` is missing, say the guard
is not installed and name `./install.sh --features reread`; do not create a flag
that points at nothing.

Print: `Re-read guard on. /sc off to stop it.`

## `off`

Remove the persistent flag (`reread.on`). One-shot armings clear themselves and
need no cleanup here. Leave registration in place — a registered hook with no flag
costs one `Path.exists()` per turn, and re-registering is the part that touches
`settings.json`.

Print: `Re-read guard off. /sc on to start it again.`

## `status`

Report whether the guard is on or off. If it is registered but the script is
missing, or the flag exists with no registration, say that instead — those are
broken states and the user cannot act on what they cannot see.

Print one line: the state, and the command that changes it.

## `unregister`

Remove the flag and the `settings.json` entry. If removing the entry empties the
`Stop` array, remove the `Stop` key too rather than leaving an empty list.

Print: `Re-read guard removed from settings.`

## The one interaction worth knowing

`/nr` answers a question with no tools and instructs the session to name what it
could not check. The guard's first item asks the opposite — run the check you
named. With the one-shot as the main path the two barely meet: you would have to
type both. In always-on mode they can, though rarely, because `/nr` answers are
short and fall under the length threshold. If one does collide, `/sc off` for
that turn. This is a known edge, not a solved one.
