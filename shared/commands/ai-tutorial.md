---
description: Explain what each installed capability is for and when to reach for it — one section per capability, only the ones you actually have. Pass a name for one section, or `all` for every runtime.
allowed-tools: Bash(bash *)
---

Print the block below verbatim and stop. Do not re-read any file, do not
re-describe a section, do not add a summary, a recommendation, or a closing
line. The text arrives already written; relaying it is the whole job.

Argument: `$ARGUMENTS` — empty for the capabilities installed in this runtime, a
capability name (`sc`, `router`, `doc-harness`, …) for that one section, or
`all` for every runtime on this machine.

!`bash "$HOME/.config/mrcall-ai-kit/ai-tutorial.sh" $ARGUMENTS`

If the block above is empty or reports a missing script, the kit is not
installed for this runtime: point at `./install.sh` in the mrcall-ai-kit repo
and say nothing else.

This answers "what is it for"; `/ai-help` answers "what do I have". Two
questions, two commands. If the user wanted the inventory, send them there
rather than summarising it here.
