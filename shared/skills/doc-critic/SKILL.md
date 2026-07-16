---
name: doc-critic
description: Verify documentation against code reality. Given the docs changed this session, flag any claim that describes a feature/endpoint/file/flag that does not exist or is not wired (dead code documented as live), plus non-English artifacts. Used by /doc-end before advancing the baseline.
---

# doc-critic — does the documentation match the code?

The mechanical gate (`doc-check.py`) catches dead links, inventory drift, and duplicate indexes. It CANNOT catch *semantic* drift: a doc that confidently describes something the code no longer does. That is the rot that survives for months — a dead pipeline documented as live, an architecture describing a service that was split, a "supported" flag that was removed. This skill is that check.

## When to run
Invoked by `/doc-end`, scoped to the **docs touched this session** (`git diff <doc_baseline_commit>..HEAD -- '*.md'`). Can also run standalone as a full-repo audit.

## What to verify — for each factual claim in the changed docs
Extract the concrete, checkable claims (not prose/opinion) and verify each against the actual code:

1. **Existence** — a named file / module / function / class / endpoint / env var / CLI flag / config key the doc mentions: does it exist? `grep`/`ls`/read to confirm. A doc naming `services/foo.py` or `POST /api/x` that isn't there is a defect.
2. **Wired, not dead** — does the described capability actually run? An endpoint that exists but 500s on every call (broken import), a tool defined but never registered, a method with zero callers — the doc must not present it as a live feature. Trace at least one caller / registration on the runtime path.
3. **Accurate shape** — counts ("9 tools"), routes, table/column names, ports, hosts: spot-check the load-bearing ones against source.
4. **Right owner** — does the doc attribute a capability to the correct service/repo? (e.g. after a split, don't describe repo A as doing what moved to repo B.)
5. **English** — is every artifact (docs, comments, script prompts) in English? Flag non-English content unless it is explicitly end-user-facing localized copy (a customer email, an `it-IT` UI string). The surrounding code/docs stay English.

## How to work (reflexion loop)
- For each claim: verdict `CONFIRMED` (matches code), `STALE` (code says otherwise — quote the file:line), or `UNVERIFIABLE` (say why; do not guess).
- Return the STALE + UNVERIFIABLE findings to `/doc-end`, which repairs the doc and re-runs this skill until zero STALE remain.
- **Never fabricate.** If you cannot verify a claim against code, mark it UNVERIFIABLE — do not invent a confirmation. Correctness over coverage.
- Prefer reading the real source over trusting a prior doc; the code wins over the doc every time.

## Output
A short list: `STALE: <claim> — code says <file:line: reality>` / `UNVERIFIABLE: <claim> — <why>`. If everything checks out: `Critic clean — N claims verified.`
