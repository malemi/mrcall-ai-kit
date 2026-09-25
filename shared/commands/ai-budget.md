---
description: Set how much this machine's kit agents may cost — low, medium or high — or, with no argument, show the budget and each installed agent's model.
allowed-tools: Bash(python3 *)
---

Print the block below verbatim and stop. Do not re-read any file, do not
re-describe a model, do not add a summary, a recommendation, or a closing line.
The script has already done the work; relaying what it printed is the whole
job.

Argument: `$ARGUMENTS` — `low`, `medium` or `high` to switch this machine's
budget, empty to show it.

!`python3 "$HOME/.config/mrcall-ai-kit/ai-budget.py" $ARGUMENTS`

If the block above is empty or reports a missing script, the kit is not
installed for this runtime: point at `./install.sh` in the mrcall-ai-kit repo
and say nothing else.

The budget is the only knob. Never choose a level for the user, and never name
a model to use instead: the kit chose each role's model for each budget.
