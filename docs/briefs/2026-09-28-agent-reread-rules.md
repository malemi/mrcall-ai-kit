# Apply the sc checklist to every kit agent report

Date: 2026-09-28

## Intent

Every kit agent on Claude Code, OpenCode, and Codex should check its final
answer against the six rules in `shared/roles/reread-checklist.md`. The
operator explicitly requested this behavior across platforms after confirming
that the current profiles do not contain the complete checklist.

## Scope

- Compose the shipped checklist into the existing agent generation path,
  including OpenCode lead agents as well as role agents.
- Require one private pass over the final report before delivery. Preserve
  mandatory report headers, verdict position, and report length contracts.
- Regenerate agent definitions and the Claude Code preloaded role skill.
- Check the generated and installed artifacts and probe real clients where
  available. Update the documentation to describe the measured behavior.

## Constraints

- Keep `shared/roles/reread-checklist.md` as the single source of the six
  rules. Do not add a second hand-maintained checklist.
- The agent rule is always present in generated profiles; `$sc`, `/sc`, and
  their operator-only invocation semantics remain unchanged.
- The re-read is an instruction to the model, not a runtime interception.
  Do not claim that it guarantees every answer complies.
- Keep mandatory agent report schemas and the reviewer's verdict location.
- Do not alter unrelated working-tree changes or commit.

## Acceptance criteria

1. Generated Claude Code, OpenCode, and Codex role agents receive the full
   checklist through their existing composition routes. OpenCode leads also
   receive it.
2. Instructions say to apply the pass before every final report without
   announcing it. The answer-first rule uses the required report header or
   reviewer verdict when the agent has a fixed schema.
3. Generator drift checks fail if any rendering loses the checklist.
4. Installed-client evidence establishes which runtimes load the instructions
   and produce reports consistent with them. Documentation separates that
   observable behavior from the unobservable internal re-read pass.

## Material assumptions

- The request concerns the six shipped sc rules, not operator edits to the
  optional installed checklist. A generated profile is a snapshot until the
  kit is regenerated and reinstalled.
