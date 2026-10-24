# Automatic av short-answer exemption

## Intent

Avoid reanalysing brief conversational reports such as the operator's logging
example. The operator explicitly changes the prior all-report boundary: short
answers must not trigger automatic av, even when they contain an analysis.

## Scope

Codex, Claude Code and OpenCode 2 skip automatic classification and av for a
complete outgoing answer of at most 300 Unicode code points, including spaces
and newlines. This approximates three displayed lines without depending on
window width or requiring literal line breaks. At 301 code points and above,
the existing semantic selection still decides whether the answer is a report.
No new configuration surface or model/provider change. Manual av is unchanged.

## Acceptance

- The quoted short logging response and 300-character answers cause zero
  selector calls and zero av continuations on all three native paths.
- 301-character reports still reach semantic selection; negative selections
  above the limit remain quiet. Unicode counting agrees across Python/JavaScript.
- A skipped short draft does not consume the turn's later eligible application.
  A pending old classification cannot inject av after the current draft becomes
  exempt. Existing cancellation, replay and once-per-turn limits are preserved.
- Actual command-hook/native-plugin fixtures prove the bypass and boundary using
  deterministic local providers. No paid model acceptance is needed.
- Current contracts, tests and fixtures distinguish this new exemption from the
  historical pre-exemption semantic trials. Preserve the known OpenCode waiver.

## Delivery and constraints

Develop in an isolated worktree because installed Python assets follow the main
checkout. Integrate only reviewed changes and update owned installed assets;
preserve foreign hooks, manual skills, trust and credentials. No engine, cron,
operational clone changes or restarts. No public release is requested by this
change. Existing native reload requirements remain explicit.
