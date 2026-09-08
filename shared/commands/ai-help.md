---
description: List what mrcall-ai-kit has installed for the runtime you are in right now — commands, skills and agents, read from disk. Pass `all` to include the other runtimes.
allowed-tools: Bash(bash *)
---

Print the block below verbatim and stop. Do not re-read any file, do not
re-describe an entry, do not add a summary, a recommendation, or a closing line.
The listing arrives already formatted; relaying it is the whole job, and
anything you add is a description of the inventory rather than the inventory.

Argument: `$ARGUMENTS` — empty for this runtime only, `all` for every runtime
installed on this machine.

!`bash "$HOME/.config/mrcall-ai-kit/ai-help.sh" $ARGUMENTS`

If the block above is empty or reports a missing script, the kit is not
installed for this runtime: point at `./install.sh` in the mrcall-ai-kit repo
and say nothing else.

Descriptions are one line on purpose. This is an index, and an entry that needs
more than a line is asking to be opened rather than summarised here — including
the trigger an entry declares for itself, which lives in its own description.
