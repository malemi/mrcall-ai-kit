# Automatic av retirement

Automatic av is disabled. Doc-harness installation removes its owned
UserPromptSubmit, Stop and SessionEnd hooks from selected Codex and Claude
registries, and its owned OpenCode plugin registration. Fresh installs register
none; repeated installation keeps it off. Manual av remains available on demand.

No behavioural improvement or completion guarantee is claimed for the retired
automatic path.

## Installation and ownership

Use the ordinary installer for the desired runtimes:

```bash
./install.sh --environment all --features doc-harness --mode copy --on-exist backup --yes
```

The installer retains the management helper and legacy compatibility assets under
`~/.config/mrcall-ai-kit/auto-av/`, but does not install the automatic-av OpenCode
bundle or run npm for it. Existing inactive bundles and historical audit data are
preserved. Only exact owned registrations are removed; unrelated hooks and foreign
plugin paths remain untouched. Preserved foreign/modified helper or shared assets
prevent executing the helper and produce an explicit diagnostic instead.

Registration status can be checked without inference:

```bash
python3 ~/.config/mrcall-ai-kit/auto-av/auto_av.py status --runtime codex
python3 ~/.config/mrcall-ai-kit/auto-av/auto_av.py status --runtime claude
python3 ~/.config/mrcall-ai-kit/auto-av/auto_av.py status --runtime opencode
```

The retained helper can remove owned registrations with `off --runtime NAME`.
Its historical `on` operation is not part of installation and must not be used
to override the operator's disabled-automation choice. Cached command-hook calls
return `{}` immediately without reading stdin, writing state, selecting a model
or issuing diagnostics, including missing or malformed input. An already loaded
OpenCode plugin still requires native reload to unload its in-memory code.
Installation does not restart sessions or change native trust, credentials or
model budgets.

The rejected earlier completion certificate remains retired through its existing
inert compatibility path. The separate repository `doc-check.py --completion`
evidence API and required documentation reviews remain in force. Other hooks,
including optional sc and scope guard, are outside this retirement.

## Evidence and limits

The [retirement brief](briefs/2026-10-25-disable-automatic-av.md) and
[plan](execution-plans/2026-10-25-disable-automatic-av.md) define delivery.
Actual isolated-home installer tests cover fresh and owned-upgrade removal,
copy/symlink modes, repeated installation, foreign assets, manual av and absence
of automatic-av npm execution. Actual CLI regressions cover cached callbacks, malformed or missing input and
open stdin, with zero selector calls or state writes. Command-hook compatibility
is inert; registration removal does not establish unloading of an already loaded
OpenCode plugin.

The retained earlier [automatic-av brief](briefs/2026-10-21-automatic-av.md),
[plan](execution-plans/2026-10-21-automatic-av.md), and
[short-answer plan](execution-plans/2026-10-24-av-short-answers.md) describe the
superseded implementation and its measured limits; they are not activation
instructions for the current installer. No new paid model acceptance is needed
or claimed for registration retirement.
