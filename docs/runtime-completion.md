# Automatic av for analysis and result reports

Production deployment is operator-authorized with a known OpenCode limitation:
the configured verification provider refuses its isolated request. Successful
real OpenCode acceptance is waived for this release, not claimed as passed.

Doc-harness installs a semantic selector and routes positive reports to the
canonical `shared/shortcuts/av.md` stance in the original answering session.
Complete answers of at most 300 Unicode code points bypass both classification
and automatic av, even when they contain findings. Count the raw answer,
including spaces and newlines; displayed line wrapping does not affect this
boundary. Manual av remains available regardless of answer length.
For longer answers, activate if and only if the response reports an analysis
or result. Mixed answers, status findings and analytical explanations qualify.
Pure acknowledgments, greetings, clarification
without findings, pause/cancel acknowledgments, quoted-only material, empty
answers and internal coordination without a user-facing report do not.

Selection returns APPLY or SKIP; it is not an answering-agent completion review.
There is no JSON self-certificate, task binding, delivery declaration or strict
exec wrapper. The separate repository `doc-check.py --completion` evidence API
and the documentation review lifecycle remain in force.

## Native paths

| Runtime measured for protocol | Selection | Positive continuation |
|---|---|---|
| Codex 0.163.0 | Ephemeral native CLI, inherited parent model where available, read-only and zero tools | Native Stop block resumes the original session with canonical av |
| Claude Code 2.1.296 | Tools-disabled native CLI, installed verify-role model from the operator budget | Native Stop block resumes the original session with canonical av |
| OpenCode 2.0.32 | Native stateless `generate.text` with the explicit installed verify-role model and isolated input; no tools/history | Native `session.prompt` with steer delivery into the original session |

These version identities describe measured integrations, not compatibility with
all versions. OpenCode 1 receives an explicit unavailable diagnostic and does
not load the v2 plugin. OpenCode's physical installed bundle needs npm and the
pinned `effect@4.0.0-beta.83` dependency.

Codex and Claude register owned UserPromptSubmit, Stop and SessionEnd commands.
They capture the current request and classify its complete text and the complete
outgoing answer as untrusted data. OpenCode obtains the current request and
answer from native session context. It resolves the installed verify agent model
explicitly and uses that provider's native credentials. Missing role/model or
credentials produce unavailable rather than a model switch. Doc-harness installs
that verify role even without the full workers feature. The length exemption is
mechanical and precedes semantic selection; prose keywords never select reports.
Missing or empty text returns quietly without classification. A short draft does
not consume a later eligible application in the same turn. Pending obsolete
selection cannot inject av when the current draft becomes exempt.

A positive selection supplies the canonical manual stance with a concrete
automatic task wrapper. The parent keeps its assignment, tools and authority:
it performs feasible authorized remaining work and verifies it. Adequate answers
stay unchanged. Question, brief and review scope, pauses, missing authority and
actual resource limits remain legitimate boundaries. It must not merely reply
that av was received. No private reasoning or semantic truth is certified.

## Limits and failure behavior

Answers within the exemption cost zero classifier generations. Normally each
longer outgoing answer costs one classifier generation, including negative
selections. OpenCode verification can use a paid provider even when
the answering model is free: the installed verify-role budget determines its
model; the plugin does not choose a cheaper model. A negative selection injects
no av and creates no extra parent turn. An exact negative callback replay is cached; a changed draft can
be selected again. At most one av continuation is sent per original user turn;
a genuine later user turn gets its own selection. Other hooks' continuation
flags do not count as this adapter's application.

Each selector gets one process/request attempt, 30 seconds including transport,
and at most 2 KiB of label output. Command transports also cap native transport
output at 256 KiB and kill/reap their process group on failure or cancellation.
OpenCode uses native Effect interruption. Its stateless API exposes no per-call
token setting: the 2 KiB returned label is validated after native completion.
A native delayed-provider fixture observes the upstream socket closing at its
30-second deadline.
Native provider behavior and its internal retries remain distinct from the adapter's one-attempt policy.

Timeout, invalid output, missing context or unsupported capability produces an
explicit availability diagnostic and no av injection. It never counts as a
successful review. New prompts/session cancellation invalidate pending selection;
obsolete results cannot inject av. The adapter does not guarantee perfect
semantic classification, model obedience or completion of every assignment.

Stop/event continuations can occur after the draft has been displayed. Actual
Codex JSON fixtures expose the draft and resumed response; Claude print fixtures
emit the final response. Interactive pre-display suppression is unverified.
Do not describe this integration as retracting or preventing a visible draft.

## Installation and ownership

Use the ordinary doc-harness installer for the selected runtimes:

```bash
./install.sh --environment all --features doc-harness --mode copy --on-exist backup --yes
```

Assets live under `~/.config/mrcall-ai-kit/auto-av/`; command hook registries are
Codex's selected `CODEX_HOME/hooks.json` and Claude's `~/.claude/settings.json`.
OpenCode uses an owned symlink under `~/.config/opencode/plugins/` to its physical
bundle. Registrations merge foreign entries. Preserved foreign or modified
helper/shared assets prevent automatic registration; an occupied foreign OpenCode
bundle is never passed to npm or claimed in the manifest. Installation does not
approve native
trust, edit trust stores or restart sessions. Establish reload and, for Codex,
approve the current definition through native `/hooks` before claiming operation.
Source-linked assets alone do not install newly added dependencies or registrations.

```bash
python3 ~/.config/mrcall-ai-kit/auto-av/auto_av.py status --runtime codex
python3 ~/.config/mrcall-ai-kit/auto-av/auto_av.py status --runtime claude
python3 ~/.config/mrcall-ai-kit/auto-av/auto_av.py status --runtime opencode
```

`off` removes only owned registrations; `on` restores them. Status establishes
registration, not native trust or execution. Private command state uses owned
0700 directories and 0600 files. `MRCALL_KIT_HOME` can isolate assets/state for
native trials without copying credentials. Uninstall preserves foreign files and
modified installed copies according to the installation manifest.

The rejected completion adapter's owned registrations are removed. Existing
owned executable paths become inert compatibility stubs returning `{}` for
cached hook commands until native reload. Review/bind/exec/on refuse explicitly;
modified foreign copies and historical audit data remain untouched. New installs
never register the retired path.

## Evidence

The approved [brief](briefs/2026-10-21-automatic-av.md) and
[plan](execution-plans/2026-10-21-automatic-av.md) define acceptance and limits.
Free checks exercise real copy/symlink installation, migration, native callbacks,
canonical body delivery, parent identity, classifier isolation, APPLY/SKIP counts,
replay/later-turn routing and cancellation. Native loopback providers establish
protocol execution, not semantic accuracy. Core tests and all 18 shell suites
pass; refreshed command-native fixtures retain request context and zero selector
tools, and the OpenCode positive fixture compares the actual canonical asset.

Four pre-exemption real-model conversations passed on Codex and Claude: each positive receives
one exact canonical av in the same parent, repairs and verifies the broken probe;
each acknowledgment receives zero av and no extra parent turn.

Current deterministic native fixtures cover the new 300/301-code-point boundary
on all three clients: 300 emoji code points produce zero selectors, zero av and
one parent response; 301-code-point APPLY/SKIP fixtures retain semantic routing
and canonical same-parent delivery. Python/Node checks cover the logging example,
Unicode, multiline, later eligibility and stale-selection cancellation. These
local-provider checks establish mechanics, not new real-model semantic accuracy.

OpenCode's configured native verify provider authenticates but returns an empty
response with `content_filter` / `refusal`. It supplies no classification label;
no av is injected and the negative trial does not start. The exact remote refusal
predicate is unestablished. The answering provider and verification model are not
silently changed to produce a passing result. Native free fixtures do establish
explicit role selection, zero tools/history, supported credential loading,
canonical same-parent delivery, actual shell repair and cancellation.

Actual acceptance forwarding is 23 requests across seven attempts, including the
retained provider-admission and test-authentication setup failures. The reviewed
ceiling remains 27; the stop-on-first-failure rule leaves the remaining allowance
unused. The operator authorizes release of this candidate with the disclosed
OpenCode limitation. The [plan](execution-plans/2026-10-21-automatic-av.md) retains
the failed evidence and qualified acceptance decision. No further inference is
authorized by its unused allowance. Native installation status does not establish
successful verification with the refusing provider or trust/reload in a session.

The [short-answer brief](briefs/2026-10-24-av-short-answers.md) and
[plan](execution-plans/2026-10-24-av-short-answers.md) supersede the original
all-report boundary. The historical trials above retain their original scope;
the short-answer change adds no paid acceptance requests.
