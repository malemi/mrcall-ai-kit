# Brief — supervision controller repair

## Intent

Supervision exists to drive entrusted sessions to verified completion while the
operator is elsewhere. Two recorded runs fail in opposite ways from one cause.
On 2026-11-10/11 the lead sat idle and the supervisor recorded the same blocked
result 27 times in a row and then 109 times in a row. On 2026-11-13 the lead
worked for hours, no acceptance item closed, and every assessment was recorded as
healthy. The policy text forbade both. No code measured progress or spend, checked
who authored a limit, or let a stalled task stop and ask.

The repair moves those things into Python. Python observes the sessions, measures
progress and spend, and decides when a model is called. A model is called to
judge, not to notice. Stopping for an operator limit requires the operator's own
words. A task that needs the operator waits with one self-contained question.

## Evidence

The [incident brief](2026-11-13-supervision-completion-failure.md) holds the
identities, chronology and local evidence package for 2026-11-10/11. The findings
below add to it. Times are UTC. Sources are that package's SQLite backups, the
rollouts under `~/.codex/sessions`, and, under `~/.local/state/mrcall-ai-kit/`,
`goals/state/` and `supervision-m6-01a1d4fb-ebcb-74d2-92e2-686eed6ace7d`.

### 2026-11-10/11: an idle lead

- **The assessment had become a script.** Assessments 150 and 268 are one command
  each, with the finding and `outcome: blocked` written in, run when all targets
  are idle. From 03:00 to 08:59 every supervisor turn holds exactly one tool call.
  `remaining` is byte-identical within each blocked run, 27 results and then 109.
- **`blocked` did nothing.** `Store.execution_result` returns
  `task_state_changed: False` and `Scheduler._claim` dispatches every due active
  task. The task-level block came at assessment 269.
- **The supervisor introduced both blockers.** At 23:51:35 it told the lead to
  report a blocker if no valid allocation remained, and the lead did 27 seconds
  later. At 15:33:02 on 2026-11-10 it relayed an operator instruction under the
  heading of an explicit operator direction and added that product sources stay
  unchanged; the operator's words quoted in that message do not say so. At
  01:54:34 it told the lead that scope forbade product-source changes, and the
  lead's proposal two minutes later called the change excluded by the operator.
  At least nine interventions across the two state roots enforce the lead's own
  time slots as limits.
- **The lead heard the operator only through the supervisor.** From 2026-11-10
  00:00 to 2026-11-11 15:09 every message in the lead's history came from the kit:
  13 from an earlier state root of the same supervisor and 10 from the incident's.
- **`delivered` meant queued.** Nine interventions sent between 12:47 on
  2026-11-09 and 08:11 on 2026-11-10 entered the lead's history within ten seconds
  at 09:45. Five receipted from 16:52 to 18:37 entered it between 23:47 and 23:49.
  Two escalations went to a lead that had not received the first message.
- **The policy was installed and read.** It was installed at 15:36:20, before task
  creation at 16:11:12. At 01:36 the supervisor re-read skill, policy and commands
  in full and corrected the first blocker in that turn. The 109-result run began
  37 minutes later. The incident brief's finding F3 leaves this open.
- **Nothing reached the operator.** The supervisor made no operator-notification
  call during the incident. The policy's "notify operator" names no command.

### Earlier runs

- **Repetition hides behind `completed`.** Two earlier state roots hold streaks of
  60 and 78 consecutive results with identical `remaining`, all `completed`. A
  rule keyed on the `blocked` outcome does not see them.
- **The goal controller never stops for lack of progress.** Its only goal ran from
  2026-10-30 to 2026-11-01: 996 wakes, 492 acceptance checks with no pass and 55
  automatic stasis corrections, until the operator stopped it.

### 2026-11-13: a busy lead

State at 15:25:00, read from the files; the binding was detached at 15:34:46.

- **Activity without closure.** 14 assessments, all `completed`, twelve with no
  action. None of the three acceptance items is closed. The `remaining` text
  differs in every result and names the same four obligations, so comparing text
  does not measure progress.
- **The queue waits for the turn to end.** The lead's turn ran from 13:13:54 to
  15:31:19. An intervention queued at 14:29:44 entered its history at 15:31:20.
  Two operator messages typed at 15:19 and 15:21 carry the id of the running turn.
- **An operator complaint changed nothing.** The supervisor noted the operator's
  message about elapsed time and closed that assessment as healthy with no contact.
- **Spend is recorded and unread.** Every assessment reports costs as unknown. The
  rollouts record cumulative token counters and the account's allowance window. At
  15:25:00 the supervisor had used 10.6 M tokens since activation, the lead's
  running turn 35.9 M and its seven workers 17.5 M, mostly cached input.
- **Estimates are recorded and unused.** At 14:05 the supervisor's memory records
  the lead's estimate of about ten minutes for a worker; it was active at 15:24.
- **The mandate is agent-written.** Agents wrote the task's instruction, scope and
  acceptance from two short operator messages. Each field names exclusions, and
  none says what agents may decide alone. The spending limit is in currency; the
  subscription records tokens and an allowance percentage, so nothing evaluates it.

## What code enforces today

Legacy supervision enforces exact identities, generation fences, delivery without
duplicate sends, cadence, an optional count cap, and append-only records. The goal
controller adds Python-owned continuation, executable acceptance, receipts that
distinguish consumed from queued, and a classification of turns that did no work.
Neither enforces whether anything changed since the last assessment, whether an
acceptance item closed, who authored a limit, what was spent, or what happens when
the operator is needed. `POLICY.md` states those five as instructions.

## Decisions

Decisions 1 to 4 were proposed in the analysis this session gave the operator and
accepted in the operator's message of 15:18 on 2026-11-13. Decision 5 is the
operator's own statement in that message. Its default session and decisions 6 and
7 were proposed at 15:32 as what the brief would start from on confirmation; the
operator's message of 15:44 gave the go-ahead for the brief. The session is Claude
Code `2c135815-d75a-450a-b4e2-c2f206c2e8e7`.

1. Python observes the sessions and keeps the clock. A model is called to judge.
2. An idle, unfinished task leaves every assessment with an effect.
3. Stopping for an operator limit requires the operator's words. A second reading
   in a fresh context precedes a park.
4. The operator is asked only about what is irreversible: spending, installation,
   real runs against providers, sends to customers, push and release, and deleting
   someone else's work. Agents decide everything else, do it, and record it with
   its undo.
5. No notification channel exists. A question waits in the session the operator
   names or, when the operator names none, in the session where the mandate was
   given. Nothing reaches the operator outside it.
6. Progress counts closed acceptance items and declared steps against the worker's
   own estimate. An overrun triggers judgment and never stops work.
7. Python measures spend from native records against a limit the operator supplies.

## Requirements

**Observation.** Python observes the supervisor, the targets and the task's
operator session; this brief calls them the observed sessions. At each tick it
reads, with no model call, each one's status, running turn and last completed
turn; each target's native queue; where each kit message sits, queued or consumed,
and the consuming turn; new user messages; each thread's cumulative token counter;
and the account's allowance window where the runtime records one. It stores what
it reads, so a rotated or compacted history loses nothing already recorded. A
value Python cannot read is unknown, never zero or absence. `status` reports a
task from these records, readable without the sessions' history: progress, queued
messages, spend, open questions, and decisions taken without the operator. This
extends `Store.status`, the Codex transport's `metadata`, `reconcile` and
`public_activity`, and the goal driver's rule for a consumed delivery.

**Origin of messages.** Every message the kit sends, from any state root and from
the goal controller, is recorded in one ledger for the account. The supervisor
contacts an observed session only through the CLI, which writes the ledger; the
end notice becomes a CLI command. Python classifies each user message in an
observed session: kit, when the ledger holds it; inter-agent, where the runtime
marks it; unknown, when it predates the ledger or its origin cannot be read;
operator, otherwise. Operator and unknown messages both trigger an assessment.
Only operator messages enter the registry, each with a stable reference, and only
registry entries can be cited. This is provenance for well-behaved runs, not
authentication: an agent holding the operator's account can forge input. A target
has at most one active completion task across state roots, and activation refuses
a second.

**Clock.** An assessment is dispatched only when an observation calls for
judgment: a target's turn ended on an unfinished task; an operator or unknown
message appeared; a declared step overran its estimate; a spend threshold was
crossed; a wait's condition was met or its latest time passed; a delivery stayed
unresolved past its latest time; or a slow heartbeat elapsed during long work.
Nothing is dispatched while the observation is unchanged. Each assessment receives
the observation that triggered it. This replaces fixed-interval dispatch in
`Scheduler._claim`; the task's interval remains the minimum spacing between
assessments.

**Closing an assessment.** The rule applies to each idle target that has no
message queued and owns an open acceptance item. Acceptance items name their owner
and get stable identifiers at task creation. For each such target the assessment
ends in one of four ways: an intervention delivered to it during the assessment; a
wait on a condition Python can observe — a time, a file, a process exit — with a
latest time; a park; or a conclusion through the existing `complete` and `fail`
states. The CLI refuses any other result and names the four. A wait on the
operator is a park. The outcome `blocked` is a park and stops the clock in the
same transaction. A task carries a mode, completion or observation. An observation
task is outside this rule, and `intervene` refuses it.

Each result marks every acceptance item open or closed with evidence and names the
step the lead is on, what will show it done, and the lead's estimate. A closure
counts once: an item or step that reopens and closes again does not count again.
After two consecutive assessments with no new closure, only a park or a conclusion
is accepted; an unmet wait counts as one, and an operator message resets the
count. Step closures that close no acceptance item are bounded too: after a set
number the next assessment is a convergence review. That count restarts when an
acceptance item closes, when the review finds the lead on the shortest path, or
when an operator message arrives. Otherwise, at the same number again, the task
parks.

**Receipts.** A kit message is `queued` until Python finds it in the target's
history, then `consumed` with the consuming turn. `intervene` refuses a new
message while the target's native queue holds any message, whoever sent it. An
uncertain delivery is reconciled at each tick and never resent. Consumption is not
compliance.

**Authority.** The ask-first list is the list of decision 4, fixed in code. A task
changes it only with a registry citation. A task stores each operator limit as
data: a deadline, an assessment count or a spend limit. Every limit cites registry
entries. Text an agent wrote — a plan, an estimate, a time slot, a paraphrase of
scope — cannot be stored or cited as an operator limit; an estimate is stored as
an estimate and only triggers judgment. Python renders every wake and intervention
in labeled parts: the result owed; the ask-first list; each operator limit and
each cited operator statement, quoted verbatim from the registry; the statement
that anything else is the agents' to decide and record; and the supervisor's own
text, under a label saying it is not the operator's. A decision taken without the
operator is recorded with what, why and how to undo it, as a `decision` memory.

**Park.** A park is the existing task state `blocked`, entered with a decision
request. Python accepts six reasons. Three are operator decisions, labeled by the
supervisor: an action on the ask-first list; a restriction the operator stated,
cited; an input only the operator holds. Three are conditions Python measures
itself: an operator limit reached; the closure bounds above; a delivery unresolved
past its latest time. The CLI refuses any other reason and tells the supervisor to
decide and proceed. The decision request says what the matter is in words a reader
who has not followed the work can act on, the options, the recommendation, the
citations, and what else was completed or why nothing else can proceed. Open
questions are delivered together.

**Challenge.** Before a park for an operator decision or for the closure bounds
takes effect, a challenge runs in a context holding none of the supervisor's
history. Python launches it, gives it the decision request, the registry, the
authority data and the measured facts, and writes its verdict itself. No CLI
command accepts a verdict. It answers three questions: is the constraint the
operator's; is there an authorized action that does not need the operator; can the
question be answered without having followed the work. A rejected park returns the
action the challenge named, and that one intervention is accepted. A second
rejection on the same matter parks the task and shows both positions. The
challenge is a second opinion and a bounded delay, not a veto: a task can always
stop and ask.

**The operator's question.** Each task names one operator session: the supervisor,
a target, or another root session of the same runtime. The CLI requires the field.
The skill fills it with the session where the operator gave the mandate unless the
operator names another, and the activation display shows it. Python reads that
session and delivers questions to it, nothing else. On park it delivers the
decision request there once, with the instruction to present it and wait. Where
the runtime cannot show content without starting a turn, that delivery costs one
turn in the receiving session. After it a parked task dispatches nothing. No other
channel exists and no timer acts on silence. A new operator message in an observed
session reactivates the task and triggers one assessment that receives it. If it
does not settle the question, the task parks again with no new challenge and no
new delivery.

**Limits and spend.** Spend is the change in each thread's cumulative token
counter since activation, summed over the supervisor, the targets and their
workers. A spend limit has a target and a ceiling. It is a token total, a share of
the account's allowance window, or a currency amount with a price table the
operator supplies; without prices it is refused at activation, and Python invents
no price. Token consumption by the supervised sessions is governed by the spend
limit, not by the ask-first list. Crossing the target triggers a convergence
review. Reaching a ceiling, a deadline or a count parks the task and stops
admission; where the runtime cannot interrupt a running turn, `status` says the
turn continues. Assessment summaries no longer restate cost.

**Convergence review.** It is a fresh-context judgment launched like the challenge
and given the measured facts. Its triggers are a declared step overrunning its
estimate by a set factor, spend or time since the last acceptance closure crossing
set fractions of the operator's target, and the bound on step closures. It names
the shortest path to the next acceptance item and what to cut. Its result is an
intervention, or a park when the cut touches the operator's acceptance or the
ask-first list. It never stops work by itself.

**Instructions.** Each sentence of `POLICY.md` and of the two supervisor skills
that a refusal or a Python action now enforces is deleted, and so is every
permission to contact a session outside the CLI.

## What a model still judges

Every refusal and every Python action above is enforced in code and has a
deterministic test. A model still judges, and the native trial measures how well:

- whether the reason of an operator-decision park is true;
- whether a cited statement supports the claimed restriction, and whether an
  authorized action avoids the operator;
- whether a closure is real progress — Python checks only that a step was declared
  in an earlier assessment and that its named artifact postdates the declaration;
- whether the lead's path converges, and what to tell the lead;
- whether the session receiving a question presents it and waits;
- whether the supervisor keeps to the CLI — where the runtime does not mark a
  message sent another way, that message reads as the operator's.

## Scope

In scope: the store, scheduler, control module, CLI, policy and command reference
under `shared/supervision/`; the account ledger; the Codex and Claude native
transports; both supervisor skills; [`supervision.md`](../supervision.md); tests;
the installer where assets change.

Out of scope: resuming or changing any live supervision or product work; OpenCode;
authentication between agents of one account; forced termination of workers;
replacing the persistent supervisor session with a fresh run per assessment.

## Constraints

- Raw logs stay local. Repository tests use synthetic fixtures with the recorded
  shapes. Replays read the real records locally and report derived counts only.
  Their expected values are computed from the records without the new code.
- Installation into the kit home, contact with any session, a paid model call,
  a commit and a release each need their own operator authorization.
- Existing state roots stay readable. A task created under the earlier contract
  does not run under the new rules until it is re-activated with the required
  fields, and the CLI says so.
- Exact-identity checks, generation fences, reconciliation without resend,
  observation-only scope, pause, cancel and detach semantics, append-only audit
  and memory, and the Claude adapter's version gate keep their behavior.
- Long active work receives no message because time passed.
- The repair extends the surfaces named above and adds no second controller.
- Before a test is written, the plan names the observation that proves its
  property and where that observation is read.
- Measured `status` and the replays come first: read-only, nothing installed.
- The working tree holds uncommitted work from earlier plans, 46 modified and 39
  untracked files since `8579bd9`. The repair stays separable from it.

## Acceptance

1. A local replay of 2026-11-10/11 judges each of the 269 recorded executions and
   each recorded intervention on its own, against the state the retained records
   show at that moment, with no model call, no session contact and no forward
   simulation. For an execution it reports whether a trigger had occurred since
   the previous one and whether the CLI accepts the recorded result unchanged; for
   an intervention, whether `intervene` accepts the send. Recorded results carry
   no closures, steps or park reasons, and the replay adds none. Expected: no
   trigger for assessments 125 to 150 and 162 to 269; the results of 124 and 161
   refused as parks with no reason and no decision request; every send made while
   the lead's native queue held a message refused, the five of 16:52 to 18:37
   among them; all 23 kit messages in the lead's history classified as kit, with
   none entering the registry.
2. A local replay of the 2026-11-13 run makes `status` at 15:25:00 report no
   acceptance item closed, the lead's turn running since 13:13:54, the
   intervention queued since 14:29:44, and spend equal to the change in the native
   counters since activation. A ceiling below that spend parks the task at the
   crossing. The replay reports the triggers found against the 14 recorded.
3. The 2026-10-30 goal records, with each consumed lead wake followed by a failed
   acceptance check counted as one assessment with no closure, reach the closure
   bound after two such assessments, against the 996 wakes recorded.
4. Deterministic failure-path tests through the real CLI and socket fixtures cover
   every refusal and Python action in Requirements, one enforced property each.
   They include the cases the incident brief names: an artifact older than its
   step's declaration closes nothing; a restart, and a rotated or lost native
   history, preserve parked state, questions, receipts, registry entries and
   counts; an operator deadline stops admission; a rejected park followed by a
   closure continues the task. Observation tasks, pause and detach fences and
   uncertain deliveries behave as before.
5. The challenge input holds none of the supervisor's history, and no CLI command
   accepts a verdict.
6. A bounded paid native trial on disposable sessions follows. A lead reports an
   expired estimate of its own as a blocker: the park is refused or rejected and
   work resumes. A lead reaches an ask-first action: the task parks, the question
   appears in the operator session, nothing is dispatched while parked, and an
   operator message resumes it. A small token ceiling parks the task at the
   crossing. The trial reports its measured tokens.
7. Through the operator's path, activation by the skill displays the
   Python-rendered authority, the operator session and each limit with its
   citation, and `status` is readable without the sessions' history.
8. `supervision.md` states what Python enforces and what a model judges.
   `POLICY.md` and the skills hold no sentence that a refusal now enforces.

The incident brief's eight requirements map to these items: 1 and 3 to items 1
and 3; 2, 4 and 7 to item 4; 5 to the constraint on naming a test's observation;
6 to items 1, 2 and 7 with independently computed expected values; 8 to item 6.

## Assumptions

- The Codex app-server gives an external client thread status, queue contents and
  turns whose items carry a `clientId`; the transport reads all three today. The
  operator's messages carry one too, so origin rests on the ledger. Whether rollout
  `inter_agent_communication_metadata` records mark messages between root sessions
  is unestablished.
- Token counters and the allowance window come from rollout files, a
  version-dependent on-disk format, unless the app-server exposes them. Thread
  counters are cumulative across rollout rotation.
- Whether the app-server exposes input into a running turn, interruption of a
  turn, removal of a queued message, or content shown without starting a turn is
  unestablished. The transport uses only `thread/queue/add`. Without those,
  messages wait for the turn to end and a limit cannot stop a running turn.
- The Claude adapter offers the same observations from its public JSONL.
- Whether a goal service in protected mode can reach the ledger is unestablished.
- Python can launch a fresh-context run from the cron environment with the kit's
  `verify` role and read its verdict from that process, or else from the native
  history of a child whose parent chain it validates as `session-read` does.
- That a fresh-context challenge judges better than the supervisor rests on one
  observed case, at 01:36 on 2026-11-11. The enforced rules do not depend on it.

## Open operator decisions

**A required spend limit.** Without one a busy lead has no hard stop: on
2026-11-13 the only limit was in currency and could not be evaluated. The
recommendation is to refuse activation without one and to let the operator set a
default once in the kit configuration; that entry is then what the limit cites.

**The goal controller.** Its observation code and executable acceptance are what
this repair needs. The recommendation is to move those parts into the one
controller, where an executable check becomes the strongest way to close an
acceptance item, and to retire the separate goal service. Retiring deletes
uncommitted work from completed plans and stops an installed service, so the
decision is the operator's. Nothing else in this brief depends on it.

**The token reminder.** The operator asked on 2026-10-27 for a reminder appended
to every intervention ([brief](2026-10-27-supervisor-token-reminder.md),
[plan](../execution-plans/2026-10-27-supervisor-token-reminder.md)). Measured
spend replaces what it tried to obtain by instruction. The recommendation is to
retire it when spend limits are installed and close that plan as superseded.

**The base.** The recommendation is a commit of the present working tree on a
branch before any code change, protecting that work and isolating the repair.
