# Roles: where an agent's own rules are written

An agent is a **job**, not a model. The rules that belong to a job are written
here once, and each runtime receives them the way that runtime allows.

**This is not the only file an agent obeys, and it does not restate the
others.** The *caller's* standing contract — when to ask, when to implement
directly, the review gate sequence, relaying a verdict in your own words —
lives in the managed `shared/templates/CLAUDE.md` that a repository installs.
A rule binds one side of the delegation or the other, and it is written on that
side only: `docs/model-router.md` states the split. When a rule here seems to be
missing, check the template before adding it.

## The files

| File | Who carries it |
|---|---|
| `common.md` | every role |
| `worker-report.md` | roles that report to a delegating session: `execute`, `verify`, `review` |
| `execute.md`, `verify.md`, `review.md`, `plan.md`, `orchestrate.md` | one role each |

A role file states the job and nothing else. Anything true of more than one role
belongs in `common.md` — that is the whole point of this directory, and the rule
it replaced was 836 lines of three blocks copied into nineteen files.

## How each runtime gets them

**Claude Code has a real include.** `skills:` frontmatter injects a skill's full
body into a subagent at startup — verified by probe, with a control. So the
shared files will ship as a skill that each role names, and nothing there needs
generating. *Not wired yet: that is milestone 2.*

**OpenCode has none, so its agent files are generated.** A markdown agent has
**no `prompt:` field** — the body is always the prompt — and `{file:}`
substitution belongs to `opencode.json`, passing through a markdown body as
literal text — *so each OpenCode agent file will be composed from these sources
and committed, which is milestone 3 and is not built yet.* Both facts were
established by probe on 1.17.18, not inferred:
`opencode debug agent <name>` resolves an agent without calling a model. The
documented frontmatter fields are `description`, `mode`, `model`, `temperature`
and `permission`; `tools:` is honoured too, so treat that list as documented
rather than exhaustive.

**A generated file is never hand-edited.** Edit the source here and regenerate.
A gate fails when a generated file and its sources disagree; without it the
drift this directory exists to end returns in a new place.

**Codex gets nothing from here** — the kit ships no Codex agent definitions.

## The model is not the identity

A role names the job. The model it runs on is a frontmatter field, set to the
tier the job needs, and on Claude Code a caller may override it per invocation.
Leaving it unset is not the neutral choice: an unset subagent model falls back
to the calling session's model, and the router runs that session on a cheap
model deliberately — so an unset judgment role would quietly run on the cheapest
model available, which the kit's own rules call a bug rather than a saving.
