# Disable automatic av installation

## Intent

The operator rejects automatic av because it interrupts reports without reliably
improving task completion. Remove its automatic activation from the kit and
publish the change; manual av remains available.

## Scope and constraints

Doc-harness installation removes only owned automatic-av registrations for each
selected runtime instead of activating them. Fresh installs register none.
Retain the existing management helper for safe ownership-aware retirement and
historical assets; do not install the OpenCode plugin bundle or npm dependency
for automatic av. Preserve manual av, unrelated hooks, role settings, history,
credentials and other features. No operational clones or session restarts.
Existing loaded native plugins may need reload; do not claim instant unloading.

## Acceptance

Actual installer runs for Codex, Claude and OpenCode, copy and symlink modes,
leave zero automatic-av registrations on fresh installation and after upgrading
an owned prior installation. Unrelated hooks and foreign plugin paths survive.
Manual av remains installed and unchanged. Repeating installation cannot
reactivate automatic av or invoke npm for that retired plugin. Existing legacy
completion retirement remains intact. Current documentation describes disabled
automation rather than promising behavioural enforcement. Run applicable
checks, closure, commit and authorized public patch release.

## Assumptions

Retaining inactive source and management assets is compatible with removing the
hook; this is retirement of automatic installation, not deletion of audit data.
No further model acceptance is needed for deterministic registration removal.
