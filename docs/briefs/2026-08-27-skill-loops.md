# Skill loops: bounded repetition around reusable capabilities

**Date**: 2026-08-27

## Problem

AI-kit has skills, delegation, session memory, validation gates, and a
watchdog, but no common runtime for repeating work until an objective is met.
Putting an unconstrained prompt inside a `while` loop would add cost and risk
without making the system more capable: the reusable asset is the skill the
loop calls, while the loop should own only repetition, state, feedback, and
stopping.

## Direction

Introduce a thin loop runner that, on each iteration:

1. reads the objective and current state;
2. lets the model select one named skill from an explicit allowlist;
3. runs that skill and its validation feedback;
4. updates a living state snapshot;
5. continues, stops successfully, or reports that it is blocked.

Every loop contract must declare its callable skills, success evidence,
iteration and time limits, no-progress threshold, and actions that require a
human checkpoint. Logs remain complete and append-only; resumable state is a
small current snapshot rather than a transcript.

## First use case

Apply the model to the existing OpenCode orchestrator before adding cron or
background execution. Its loop would choose a skill, delegate work, validate
the result through existing gates, update state, and repeat. Completion must be
based on observable evidence, including the real user-facing execution path
where applicable, rather than a worker's claim.

Before doing this, resolve the existing orchestrator gaps around duplicate
verification, unbounded fan-out, non-resumable delegation, and divergent entry
points. A loop would otherwise amplify those costs and inconsistencies.

## Compounding step

A later `skill-harvest` capability may inspect completed difficult or repeated
work and propose a new skill, or an improvement to an existing one, together
with its acceptance check and known failure modes. Promotion should require
clear reuse value; it must not create a new skill after every session.

## Out of scope for the first iteration

- unattended cron execution;
- a general-purpose workflow language;
- unrestricted tool or skill selection;
- automatic skill creation without review;
- claims of cross-runtime support before real-client acceptance tests.

## Open questions

- Whether the loop contract belongs in skill metadata or in a separate,
  skill-referencing definition.
- Where resumable state should live across Claude Code, Codex, and OpenCode.
- Which runtime can expose reliable cost accounting in addition to iteration
  and wall-clock budgets.
