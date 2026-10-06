---
name: doc-end
description: End repository work by reconciling living docs to code and session reality, running mechanical and semantic review, and advancing the baseline safely.
---

# Consolidate a documented work session

Read `WORKFLOW.md` in this skill directory completely, then execute that workflow.

The shared workflow may contain Claude-style command metadata or pre-injected shell snippets. Treat metadata as capability guidance and run indicated commands with Codex tools at the relevant step. When it requests `doc-critic`, load and invoke the current `doc-critic/SKILL.md`, preferring the repository-local copy when present. That file is the complete critic workflow; there is no sibling `WORKFLOW.md`. Preserve all verification and baseline rules.
