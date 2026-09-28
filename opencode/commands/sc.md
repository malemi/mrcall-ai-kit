---
description: Answer a question with one in-turn re-read against the installed checklist. Invoke as /sc <question>; no always-on mode.
---

Question: $ARGUMENTS

If the question is empty, reply with exactly one line: `Usage: /sc <question>`.
If the entire argument is `on`, `off`, `status`, or `unregister`, reply with
exactly one line: `This /sc supports questions only; use /sc <question>.` Stop
in either case. Ignore the sections below; they apply only to a question.

For a question, the installed procedure and checklist are inserted below when
this command is invoked. A shell block reads each file before the model
receives this prompt; no later tool read of those files is needed. The blocks
never include question text in a shell command.

Procedure:
!`if test -r "$HOME/.config/mrcall-ai-kit/sc-core.md" && test -s "$HOME/.config/mrcall-ai-kit/sc-core.md"; then cat "$HOME/.config/mrcall-ai-kit/sc-core.md"; else printf 'SC_CORE_MISSING\n'; fi`

Checklist:
!`if test -r "$HOME/.config/mrcall-ai-kit/reread-checklist.md" && test -s "$HOME/.config/mrcall-ai-kit/reread-checklist.md"; then cat "$HOME/.config/mrcall-ai-kit/reread-checklist.md"; else printf 'SC_CHECKLIST_MISSING\n'; fi`

If the procedure section says `SC_CORE_MISSING`, reply `The re-read procedure
is not installed; run ./install.sh --features reread.` and stop. If the
checklist section says `SC_CHECKLIST_MISSING`, reply `The re-read checklist is
not installed; run ./install.sh --features reread.` and stop. Otherwise follow
the supplied procedure with the supplied checklist. Do not claim a pass when
either installed file is unavailable.
