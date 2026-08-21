---
description: Toggle the opt-in model router (Haiku session as classifier, delegating to pinned-model workers) — on, off, status, sweep, or unregister.
allowed-tools: Bash(python3 *) Bash(ls *) Bash(cat *) Bash(mkdir *) Bash(touch *) Bash(rm *) Bash(date *) Read
---

Manage the model router. The hook script lives at
`~/.config/mrcall-ai-kit/router-hook.py` (installed by `./install.sh --features router`).
It is dormant unless `~/.config/mrcall-ai-kit/router.on` exists — this command
is the only thing that creates, removes, or inspects that flag, and the only
thing that registers the hook in `~/.claude/settings.json`.

Argument: `$ARGUMENTS` — one of `on`, `off`, `status`, `sweep`, `unregister`.
No argument or an unrecognized one: show `status` and stop.

## Shared: locating the hook entry

Registration lives at `hooks.UserPromptSubmit` in `~/.claude/settings.json`, as
a matcher-group entry whose nested `hooks` array contains a command running
`router-hook.py` (UserPromptSubmit has no matcher support — omit `matcher`
entirely, per the Claude Code hooks schema):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "python3 /home/<user>/.config/mrcall-ai-kit/router-hook.py" } ] }
    ]
  }
}
```

To check whether it is already registered: read `~/.claude/settings.json` (if
it exists) and look for a `UserPromptSubmit` entry whose `hooks[].command`
contains the string `router-hook.py`. Absent file or absent key both mean "not
registered".

## `on`

1. Ensure `~/.config/mrcall-ai-kit/router-hook.py` exists; if not, stop and
   tell the user to run `./install.sh --features router` first.
2. If the hook is not yet registered: back up `~/.claude/settings.json` to
   `~/.claude/settings.json.bak` (only if the file exists), then merge the
   entry above into it with a small `python3 -c` snippet — read the existing
   JSON (or start from `{}`), ensure `hooks.UserPromptSubmit` is a list,
   append the entry if no existing one already references `router-hook.py`,
   write back with `json.dump(..., indent=2)`. Never touch any other key.
   If already registered, skip this step and say so.
3. `mkdir -p ~/.config/mrcall-ai-kit && touch ~/.config/mrcall-ai-kit/router.on`.
4. Report: flag created (or already was on); registration done, already
   present, or newly added this run; and — only when registration was newly
   added this run — that a session restart is needed for the hook to take
   effect. Always remind that the router only does something useful if the
   session model is Haiku (`/model haiku`, or launch with `claude --model
   claude-haiku-4-5`); it is a no-op directive on any other model.

## `off`

`rm -f ~/.config/mrcall-ai-kit/router.on`. Registration is left in place — the
hook is inert and free when the flag is absent. Report the flag is gone.

## `status`

Report: whether the flag exists; whether the hook is registered in
settings.json; if both, remind the flag alone does not help unless the session
model is Haiku.

## `sweep`

List every `docs/sessions/*.md` under the current repo with `status: open` in
its frontmatter. For each: the `session_id` and `started` fields, and whether
a matching transcript exists at
`~/.claude/projects/<cwd-with-slashes-and-dots-turned-to-dashes>/<session_id>.jsonl`
(Claude Code's transcript path convention) — if the transcript is missing, or
its mtime is older than 24 hours, flag the row `probably dead`; otherwise
`recent`. This is a report only: closing or promoting a session file is a
separate, deliberate act (via `/doc-end` in that session, or by hand) — never
delete or edit any session file here.

If `docs/sessions/` does not exist or has no `open` files, say so and stop.

## `unregister`

Remove the `router-hook.py` entry from `hooks.UserPromptSubmit` in
`~/.claude/settings.json` (back up first, same as `on`; if the array or the
`UserPromptSubmit` key becomes empty, remove it too — never leave a dangling
empty array). Then `rm -f ~/.config/mrcall-ai-kit/router.on`. This is the full
removal path: `uninstall.sh` only removes files it installed by path and
cannot revert a settings.json edit, so this command is how a `router`
uninstall actually completes.
