# Documentation runtime support

Instruction delivery, workflow compliance, and runtime interception are distinct.
The v9 migration helper accepts only the bounded compatibility policy it knows;
an executable version alone is not compatibility evidence.

## Measured modes

The initial candidate was tested on 2026-10-05. Its complete experiment record is
referenced by the [delivery integration plan](execution-plans/2026-10-05-documentation-harness-delivery-integration.md).

| Client and mode | Observed result | Limit |
|---|---|---|
| Codex 0.160.0, dedicated instance of the app-server matching the local standalone session | 20/20 candidate trials passed: three each of explanation, development, documentation, and brief; six startup trials; one fast path and one review. | Engine behavior; visual interaction and actual context occupancy were not measured. |
| OpenCode 1.18.32, `run --dir ABS --format json` | Explanation, documentation, startup, brief, and review each passed once. | Substantial development and interactive behavior were not tested. One incidental unsupported help-verification sentence remains in the explanation record. |
| Claude Code 2.1.280, print mode with the tested ambient guard/router | Explanation and review passed. | Documentation editing was guard-blocked; router-induced session writes exceeded startup-only and brief-only scope. This configuration cannot support migration requiring startup and closure. |

Measured OpenCode support requires explicit `--dir`; process cwd alone did not
reliably route tools to the intended repository. Client-generated dependency
files are recorded separately from agent task changes.

These observations do not prove universal compliance for a runtime, model,
configuration, or repository. Existing guard/router behavior was not disabled to
produce a passing result. Unrelated scope-write denials are not documentation
lifecycle interception.

## Claude instruction-loading conditions

Eight strengthened probes requested all non-conflicting markers supplied by
instruction files, without tools. On the tested Claude 2.1.280:

| Configuration | Observed markers |
|---|---|
| Plain repository AGENTS, default settings | AGENTS marker present. |
| Same setup with `DISABLE_TELEMETRY=1` | AGENTS marker absent. |
| Ancestor `CLAUDE.md`, default settings | Ancestor marker only. |
| Ancestor or same-directory `CLAUDE.local.md`, default settings | Local-file marker only. |
| Each coexistence case with `instructionFiles: claude-md-and-agents-md` in the built-in agents-md configuration | Both markers present. |

The combined setting establishes loading only; its full lifecycle was not
tested. The presence of the user-level `~/.claude/CLAUDE.md` is not by itself a
proven suppression condition: it was present in the successful plain case.
The migration helper must preserve these files and never change the settings.


## Compatibility reports

Migration inspection can report missing evidence without changing files.
Dry-run and apply require a report bound to the target repository, observed
instruction files, requested scopes, tested runtime/configuration, and readable
evidence artifacts with matching hashes. Every declared client must cover at
least startup and documentation closure; additional requested scopes must also
be supported. OpenCode's measured documentation paths do not imply evidence for
substantial development. The measured Claude print configuration is refused.

The report is an evidence reference plus a caller attestation about current
configuration. Hashes detect changes; they do not authenticate an agent's
judgment or prove it executed a workflow. Missing, stale, unsupported, or
ambiguous evidence stops migration before managed files change. Installing the
kit does not migrate repositories or silently repair client configuration.

## Cost and bypass observations

The frozen prototype comparison used the same Codex prompts and runtime
configuration. Ordinary startup's median newly delivered parent payload fell
from 19,611 to 7,875 UTF-8 bytes (59.84%). Known preload plus incremental delivery
fell from 54,019 to 47,710 bytes (11.68%). The context-saving reminder changed the
candidate startup median by 0.165%. The measured prototype's managed AGENTS
block added 4,252 preloaded bytes; the shipped block is 4,324 bytes. Relocating
that text was not counted as eliminating it. Hidden tool
schemas and actual context occupancy were unavailable.

Six negative trials showed that explicit omission of startup, critic, or the
entire lifecycle remains possible without an independent runtime denial. The
critic-omission trial honestly withheld semantic completion and baseline
advancement. Three ordinary requests with injected faults found and repaired an
unchanged affected document, a false capability claim, and narrative living
context when the workflow ran. This is detection inside the invoked workflow,
not detection outside an omitted path.

The completion CLI can refuse missing or stale results when invoked. It cannot
make the client run itself or intercept every final response. Preserve that
distinction when reporting both positive checks and unresolved limitations.
