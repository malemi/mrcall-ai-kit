# Scratch: supervision test pruning

Status: audit implemented; verification and review receipts are retained in the evidence root.

Scope: all 62 original tests in the eight `tests/test_supervision_*.py` files. No unrelated test suite is pruned. Before copies and inventory are retained in `/tmp/supervision-test-pruning-20261027/before/` and `before-tests.json`.

## Decision rule

A test earns its cost by exposing a distinct operational failure. A direct assertion of a literal, a validator type matrix or a second fake happy path is not equivalent to a functional acceptance scenario. Keep deterministic infrastructure regressions when they protect real outcomes, but do not label them proof of the supervisor’s judgment. Removing duplication is not a claim that every previous assertion remains covered.

## Why each standalone case can go

### `tests/test_supervision_control.py::test_intervention_replay_and_identity_collision` — consolidate

A second fake-transport happy path repeats delivery and replay already exercised by the actual CLI/Unix-socket case. Move the unique event-ID collision refusal and delivery-is-not-completion assertion into test_real_cli_intervention_and_read_through_native_protocol; no extra stand-alone test is needed.

### `tests/test_supervision_control.py::test_fenced_commands_do_not_call_transport` — consolidate

Direct function calls repeat the shared authority refusal already exercised by the CLI with an unavailable native executable. Extend test_real_cli_rejects_stale_execution_without_native_access to exercise detach as well as pause. This checks the user-visible refusal before any native access.

### `tests/test_supervision_cron.py::test_owned_idempotent_foreign_and_dry_run` — remove

InstallTests.test_copy_lifecycle and test_symlink_lifecycle already run the installer and CLI, verify dry-run has no effects, repeat activation, retain foreign cron content, use a state path containing spaces/percent, and remove only owned entries. The extra mocked-renderer roundtrip contributes no distinct operational outcome. Dedicated malformed-cron and environment cases remain.

### `tests/test_supervision_scheduler.py::test_busy_one_binding_and_deadline` — consolidate

Busy waiting, late assessment acceptance and continued scheduling already occur in stronger restart/recovery and real-CLI cases. Preserve its unique two-tasks/one-supervisor exclusion in test_busy_dispatch_deadline_survives_restart_then_idle. Keep the checkpoint/no-duplicate guarantee in the recovery scenario and actual CLI case.

### `tests/test_supervision_scheduler.py::test_definite_offline_then_recovery_same_event` — consolidate

The recovery/checkpoint/success scenario already performs this outage and recovery. Move the one unique same-event-ID assertion there. A second setup and independent fake-transport case is unnecessary.

### `tests/test_supervision_store.py::test_real_cli_optional_cap_validation_update_and_restart` — remove

Repeated null/integer roundtrips and a seven-value validator matrix mostly restate serialization and the integer validator. The actual CLI lifecycle retains one omitted-cap observation; scheduling beyond the former default and persisted finite-cap removal/fences remain in lifecycle scenarios. The invalid-cap type matrix and redundant explicit-null creation roundtrip are intentionally dropped, not claimed to remain equivalent coverage.

### `tests/test_supervision_store.py::test_later_success_keeps_unresolved_failure_memory` — consolidate

This case inserts two records and reads them back; it never runs or restores an assessment. Move failure-memory preservation into test_failure_survives_recovery_checkpoint_and_success, reopen the store and verify execution_read restores the unresolved failure alongside the later success for the next assessment.

### `tests/test_supervision_store.py::test_empty_v0_database_initialization_keeps_backup` — remove

The fixture contains only an empty SQLite header and checks its byte-for-byte backup plus a schema constant. It exercises no user data at risk and is not a migration acceptance test. Drop this narrow empty-header backup check explicitly; unsafe/newer schema refusal and foreign-file preservation remain. Populated migration coverage is not invented.

### `tests/test_supervision_store.py::test_execution_result_does_not_complete_assignment` — consolidate

The actual CLI/protocol case already completes an assessment with underlying work remaining and observes the task still active. Submit that result through the CLI too and retain task_state_changed=false there. The database-row-only duplicate no longer adds an outcome.

### `tests/test_supervision_transport.py::test_send_exact_identity_only_and_reconcile_without_resend` — consolidate

Successful exact-target send is already covered through the real CLI; reconciliation without a second send is covered by the lost-ack Unix-socket scenario. Preserve the no-extra-queue/start assertion in the lost-ack case and the assessment_completed=false transport receipt assertion in the real CLI tick case. Remove the separate happy-path repetition.

## Assertion-only trimming

- Scheduler health: remove the redundant exact 180-second grace-edge check and the `age_seconds == 50` arithmetic assertion. Keep actual lifecycle states: first tick pending, overdue first tick, active ticking, stopped ticking and detached.
- Transport read: drop the standalone invalid-sort-direction assertion from the busy/delta scenario. It only restates a two-value argument guard; ascending pagination and anchor preservation remain tested. This narrow validation check is intentionally dropped.

## Why the remaining cases stay

These rows make the audit exhaustive; they are not an instruction to add more tests.

### `tests/test_supervision_control.py`

| Case | Concrete risk / outcome retained |
|---|---|
| `test_uncertain_delivery_reconciles_once_never_resends` | Uncertain intervention survives restart and is reconciled once without duplicate action. |
| `test_crashed_intent_is_reconciled_without_send` | Crash after recording intent must not replay an action whose delivery is unknown. |
| `test_descendant_read_and_pagination` | Workers are readable only through verified ancestry; direct worker intervention and unrelated sessions are refused. |
| `test_real_cli_status_retains_uncertainty_after_detach` | The CLI retains an uncertain intervention receipt after supervision is detached. |
| `test_real_cli_rejects_stale_execution_without_native_access` | Actual commands refuse paused/detached authority before native access; absorbs the direct-function duplicate. |
| `test_real_cli_intervention_and_read_through_native_protocol` | Actual commands cross the socket protocol after checkpoint expiry, preserve intervention identity and keep the underlying task incomplete. |

### `tests/test_supervision_cron.py`

| Case | Concrete risk / outcome retained |
|---|---|
| `test_deactivate_owned_custom_roots_and_history` | Removing several owned schedules must preserve foreign cron blocks and each root’s memory. |
| `test_deactivate_owned_real_cli_and_failure_preserves_cron` | Real deactivation command removes owned entries; missing state must refuse cleanup without losing cron evidence. |
| `test_deactivate_owned_absent_cron_and_refused_write` | A missing cron utility or failed cron write must not silently erase recovery state. |
| `test_cron_large_environment_uses_short_path_and_absolute_codex` | Cron command construction must not inherit a huge developer PATH or lose the resolved native executable. |
| `test_malformed_and_newline_rejected` | Malformed ownership markers and newline/path injection must not create unintended cron commands. |
| `test_activation_detachment_no_native_work` | Direct activate/deactivate lifecycle remains covered separately from uninstall and must not launch model work. |

### `tests/test_supervision_harness.py`

| Case | Concrete risk / outcome retained |
|---|---|
| `test_operational_does_not_create_harness_record` | Read-only operational inspection must not invent a repository development record. |
| `test_missing_then_valid_then_stale_receipt` | Actual inspection must distinguish missing, valid and invalidated evidence without repository mutation. |
| `test_finalized_record_still_checks_current_content` | A finalized receipt must not certify source content changed after finalization. |
| `test_wrong_worktree_and_unsupported_profile` | Evidence for another worktree or unsupported profile must not be accepted. |

### `tests/test_supervision_install.py`

| Case | Concrete risk / outcome retained |
|---|---|
| `test_copy_lifecycle` | Actual copy install/activation/uninstall preserves foreign assets and retained state. |
| `test_symlink_lifecycle` | Actual symlink install/activation/uninstall exercises different ownership/removal semantics. |
| `test_unsupported_and_foreign_skip` | Unsupported runtimes and foreign skill files must not be overwritten by feature selection. |
| `test_missing_native_prerequisite_does_not_activate` | A failed native prerequisite must leave no active binding or new cron schedule. |
| `test_modified_executable_refuses_uninstall` | Uninstall must not execute or remove a foreign-modified helper while cron could depend on it. |

### `tests/test_supervision_runtime.py`

| Case | Concrete risk / outcome retained |
|---|---|
| `test_foreign_and_missing_runtime_refused_without_mutation` | Setup must not take over an unowned directory or create state through an unprepared runtime. |
| `test_owned_environment_runs_actual_cli_and_repeated_setup_is_idle` | The isolated dependency environment must run the actual CLI without reinstalling dependencies on repeated setup. |

### `tests/test_supervision_scheduler.py`

| Case | Concrete risk / outcome retained |
|---|---|
| `test_empty_real_cli_and_lock` | Empty real ticks make no native calls and a held scheduler lock prevents overlapping dispatch. |
| `test_real_cli_tick_through_native_rpc_fixture` | Actual tick routes one event through the native protocol and records delivery without certifying assessment completion. |
| `test_coalesce_clock_changes_and_callback` | Overdue intervals and clock reversal must not create a replay burst; a result cannot be recorded twice. |
| `test_busy_dispatch_deadline_survives_restart_then_idle` | Busy dispatch survives restart without duplicate work, then delivers once and serializes a second task for the same supervisor. |
| `test_detached_transport_read_makes_no_native_call` | Administrative transport-read has its own detached-binding boundary, separate from assessment commands. |
| `test_status_reports_scheduler_liveness_separately` | Clock health distinguishes waiting, healthy ticks, overdue ticks and detachment; exact grace-edge/arithmetic assertions are trimmed. |
| `test_retry_bound_and_recovery` | A persistent transport outage must not cause unlimited automatic retries or spending. |
| `test_crash_sending_reconciles_never_resends` | A scheduler crash during send must reconcile an ambiguous event rather than submit it again. |
| `test_uncertain_and_pause_fences` | Pause must invalidate an outstanding assessment even when delivery remains uncertain. |
| `test_uncapped_continues_beyond_old_default` | A concrete regression: the scheduler must actually pass the former 100-execution stop while the task remains active. |
| `test_persisted_cap_removal_preserves_history_and_fences` | A persisted operator cap must bind after reopen; removing it needs resume and must retain history and fence obsolete execution authority. |
| `test_failure_survives_recovery_checkpoint_and_success` | Outage, recovery, overdue checkpoint, later success and reopen must retain failure evidence and restore it to the next assessment. |
| `test_max_checks_oneshot_alignment_and_scope` | One-shot work must not repeat; explicit caps, UTC scheduling and exact administrative target scope remain enforced. |

### `tests/test_supervision_store.py`

| Case | Concrete risk / outcome retained |
|---|---|
| `test_real_cli_task_lifecycle_and_restart` | Actual CLI pause/resume/completion/reopen semantics reject evidence-free completion and preserve explicit task state. |
| `test_concurrent_updates_allow_one_revision_winner` | Two real CLI writers must not silently overwrite each other’s task revision. |
| `test_memory_supersession_survives_process_restart` | Corrections preserve historical memory, isolate scopes and retain append-only records across CLI processes. |
| `test_exact_bindings_and_private_files` | Wrong target bindings and unsafe state permissions must be refused; private files protect operational memory. |
| `test_symlink_and_newer_schema_refused` | Opening incompatible or symlinked state must not mutate foreign data. |
| `test_block_detach_and_stale_execution_results` | Detach invalidates pending work; reattachment must not silently resume it or accept stale results. |
| `test_blocked_metadata_survives_instruction_update_and_restart` | Updating instructions must not erase an unresolved blocker, its evidence or resumption condition. |

### `tests/test_supervision_transport.py`

| Case | Concrete risk / outcome retained |
|---|---|
| `test_busy_and_wrong_identity_do_not_submit` | A routine send must neither interrupt a busy supervisor nor target a mismatched session. |
| `test_explicit_intervention_can_queue_busy_and_delta_preserves_anchor` | Authorized busy-lead interventions and native ascending delta cursor mapping remain covered. |
| `test_lost_ack_is_uncertain_and_reconciles_from_history` | Actual socket acknowledgement loss must retain uncertainty, reconcile delivery and avoid a second submission. |
| `test_pagination_complete_before_absence_and_no_private_reasoning` | Incomplete pagination cannot establish absence; public reads exclude private reasoning. |
| `test_stuck_cursor_never_claims_absence` | A looping native cursor must fail as uncertain rather than create false absence or loop forever. |
| `test_large_history_read_and_reconciliation_preserve_complete_output` | The actual large-history regression must preserve full tool output and find delivered events. |
| `test_history_above_finite_receive_ceiling_is_incomplete_not_absent` | A refused oversized frame must not be mistaken for empty history or permission to resend. |
| `test_offline_or_public_socket_refuses_before_send` | Offline or unsafe public sockets must fail before any intervention is submitted. |
| `test_discovery_preserves_permission_diagnostic` | Native discovery must retain the actual permission failure needed for diagnosis. |

## Artifact retention

Keep all task-created temporary artifacts, before copies, scripts, logs and reviews. The operator explicitly requested no cleanup of these files.

## Evidence and limits

- Before: 62 cases. Previous unchanged-suite evidence: `/tmp/optional-cap-evidence/final-suite.log`. The configured repository build/mechanical check passes at task startup.
- Implemented removals: ten standalone cases; meaningful unique assertions are moved into existing functional cases. No new standalone test or new framework was added.
- After: 52 cases. Actual final command output and review outcomes are retained in `/tmp/supervision-test-pruning-20261027/`; completion requires their successful verification.
- The retained suite tests CLI, persistence, protocol, scheduler, installation and ownership mechanics. It does not prove that a model notices drift, chooses a useful intervention or guides work to completion. That requires external observation of real behavior and logs.
- No production code, installed file, native session or paid model test is changed or invoked by this cleanup. No commit or release.
