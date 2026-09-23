---
description: Toggle the re-read guard — before an answer reaches you, the session reads it back against a short checklist and fixes what fails. On, off, status, or unregister.
allowed-tools: Bash(python3 *) Bash(ls *) Bash(cat *) Bash(mkdir *) Bash(touch *) Bash(rm *) Read
---

Manage the re-read guard. The hook script lives at
`~/.config/mrcall-ai-kit/reread-hook.py` and its checklist at
`~/.config/mrcall-ai-kit/reread-checklist.md` (both installed by
`./install.sh --features reread`). The hook is dormant unless
`~/.config/mrcall-ai-kit/reread.on` exists — this command is the only thing that
creates, removes, or inspects that flag, and the only thing that registers the
hook in `~/.claude/settings.json`.

Argument: `$ARGUMENTS` — one of `on`, `off`, `status`, `unregister`.
No argument or an unrecognized one: show `status` and stop.

## What it does, when asked

The rules about how to answer are not new and are not in this hook. They live in
the managed `CLAUDE.md` a repository installs. The hook exists because by the end
of a long turn those rules are thousands of tokens behind, and a rule out of
sight is a rule not applied. On each finished answer the hook hands it back once,
with the checklist, and the session fixes what fails before the answer is shown.

It judges nothing and calls no model. It re-presents a list; the session does the
work, in the same turn, with the answer in front of it.

Cost: one extra pass of the model already running, on answers longer than
`SC_MIN_CHARS` (default 500). Short answers are skipped.

## What to print — read this before every verb

Everything below about flag files, `settings.json` and hook registration tells
**you** how to do the work. None of it is the answer. The answer is two clauses:
what state the guard is in, and the command that changes it. Print that, stop.

Never report the flag file, the install path, `settings.json`, registration, or
backups — not as detail, not as reassurance, not "for completeness". Two
exceptions, both narrow: say more when something is **broken**, and answer
whatever the user asks directly afterwards.

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

## `on`

Register the hook if no entry running `reread-hook.py` is present, then create
the flag. If `~/.config/mrcall-ai-kit/reread-hook.py` is missing, say the guard
is not installed and name `./install.sh --features reread`; do not create a flag
that points at nothing.

Print: `Re-read guard on. /sc off to stop it.`

## `off`

Remove the flag. Leave registration in place — a registered hook with no flag
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
named. They do not actually collide often, because `/nr` answers are short and
fall under the length threshold. If one does collide, `/sc off` for that turn.
This is a known edge, not a solved one.
