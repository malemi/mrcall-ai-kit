#!/usr/bin/env python3
"""
doc-check.py — the documentation integrity gate of the mrcall-ai-kit doc-harness.

Single source of truth: one canonical index file (default `CLAUDE.md`) holds the
repo inventory / roles / ownership; the other docs point to it and never
duplicate it. This checker fails (exit 1) when the docs drift from that rule, so
rot cannot survive a `/doc-start`, a `/doc-end`, or (if a repo opts in) a
pre-commit hook.

Checks (which run depends on the repo's profile — see below):
  1. DEAD LINKS   (always) — every relative markdown link in README.md,
                  <index_file>, and docs/**/*.md must resolve on disk.
  2. LIVING CTX   (always) — docs/active-context.md carries only the canonical
                  `## State now` / `## Unresolved` / `## Next` sections. Any other
                  one is changelog drift; pruned narrative belongs in
                  docs/active-context-archive.md, which is not checked.
  3. INVENTORY    (meta mode only) — every independent sub-repo checked out under
                  the repo root must appear in <index_file>'s `## Services` table,
                  and every dir the table names must exist.
  4. NO DUP INDEX (meta mode only) — README.md / docs/README.md must NOT re-list
                  the repos in a table; the inventory lives ONLY in <index_file>.
  5. DOC SIZE     (always, ADVISORY) — names every doc past `doc_max_lines`.
                  Reported, never enforced: it never contributes to the exit code
                  (which still reflects checks 1-4 alone). Only a path, a line
                  count, and what reading it costs in bytes and estimated tokens
                  cross, so a session learns a doc has exploded without opening
                  it.
  6. TRACE NAMES  (always, ADVISORY) — names every work-trace file (a Markdown
                  file under docs/briefs/ or docs/execution-plans/) whose
                  filename lacks the `YYYY-MM-DD-` date prefix. Reported, never
                  enforced, for the same reason as check 5.
  7. SESSION STATUS (always) — every docs/sessions/*.md must carry a
                  frontmatter `status` of exactly `open` or `closed`; missing
                  or invalid is a gate failure. docs/sessions/ is the
                  short-lived, per-session sibling of active-context.md (the
                  opt-in model router's shared memory) — never read by
                  doc-start, the same way docs/projects/** is not.
  8. OPEN SESSIONS (always, ADVISORY) — counts docs/sessions/*.md still
                  `status: open`. Reported, never enforced: an open file is
                  normal mid-session and only becomes stale once its owning
                  session is long gone, which this check cannot determine —
                  see the `/router sweep` command for that judgment call.

Profile: an optional `docs/.doc-profile` file (simple `key = value` lines):
    harness_version   = 3                    (must match installed harness)
    schema_version    = 1                    (optional for legacy profiles)
    mode              = meta | leaf          (default: leaf — links only)
    index_file        = CLAUDE.md            (the single-source index)
    inventory_ignore  = dir1, dir2           (sub-repo dirs to skip in INVENTORY)
    build             = command              (optional metadata; never executed)
    smoke             = command              (optional metadata; never executed)
    index_max_lines   = 200                  (0 disables the thin-index check)
    doc_max_lines     = 400                  (0 disables the advisory size report)
A leaf repo (no sub-repos) only needs the DEAD LINKS check, so it needs no
profile at all. A meta-repo (one that checks out other repos) sets `mode = meta`.

Usage:  python3 doc-check.py [--repo PATH]     (exit 0 = clean)
Stdlib only, no network.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HARNESS_VERSION = 3
# Bytes per token: a stated convention for English prose, NOT a tokenizer result.
# It carries none of the argument — every size comparison is a ratio between two
# numbers produced by this divisor, so a wrong divisor cancels out.
BYTES_PER_TOKEN = 4
KNOWN_PROFILE_KEYS = {
    "harness_version", "schema_version", "mode", "index_file", "inventory_ignore",
    "build", "smoke", "index_max_lines", "doc_max_lines",
}
PLAN_STATUSES = {"planned", "active", "blocked", "completed", "superseded"}
SESSION_STATUSES = {"open", "closed"}
CONTEXT_SECTIONS = {"state now", "unresolved", "next"}
# Cold storage that grows by design — exempt from the advisory size report.
SIZE_EXEMPT = {"docs/active-context-archive.md"}
# Work traces (briefs and execution plans) are dated so they sort by workstream.
TRACE_DIRS = ("docs/briefs", "docs/execution-plans")
# Repo convention is the hyphenated ISO date (`2026-08-14-slug.md`); the old
# `^\d{8}` form never matched it and flagged every dated trace as undated.
TRACE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")


def repo_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path.cwd()


def read_profile(root: Path) -> tuple[dict[str, str], list[str], bool]:
    prof = root / "docs" / ".doc-profile"
    profile_exists = prof.exists()
    values: dict[str, str] = {
        "mode": "leaf", "index_file": "CLAUDE.md", "inventory_ignore": "",
        "index_max_lines": "200", "doc_max_lines": "400",
    }
    errors: list[str] = []
    if prof.exists():
        seen: set[str] = set()
        for number, line in enumerate(prof.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                errors.append(f"docs/.doc-profile:{number}: expected `key = value`")
                continue
            k, _, v = line.partition("=")
            key, value = k.strip(), v.strip()
            if key not in KNOWN_PROFILE_KEYS:
                errors.append(f"docs/.doc-profile:{number}: unknown key `{key}`")
            elif key in seen:
                errors.append(f"docs/.doc-profile:{number}: duplicate key `{key}`")
            else:
                seen.add(key)
                values[key] = value
    if values["mode"].lower() not in {"leaf", "meta"}:
        errors.append("docs/.doc-profile: `mode` must be `leaf` or `meta`")
    if "schema_version" in values and values["schema_version"] != "1":
        errors.append("docs/.doc-profile: `schema_version` must be `1`")
    index = root / values["index_file"]
    if profile_exists and (not values["index_file"] or not index.is_file()):
        errors.append(f"docs/.doc-profile: index file `{values['index_file']}` does not exist")
    elif profile_exists:
        if index.suffix.lower() != ".md":
            errors.append("docs/.doc-profile: `index_file` must be a Markdown (`.md`) file")
        try:
            index.resolve().relative_to(root.resolve())
        except ValueError:
            errors.append("docs/.doc-profile: `index_file` must stay inside the repo")
    for key in ("build", "smoke"):
        if key in values and not values[key]:
            errors.append(f"docs/.doc-profile: `{key}` must not be empty when present")
    for key in ("index_max_lines", "doc_max_lines"):
        try:
            if int(values[key]) < 0:
                raise ValueError
        except ValueError:
            errors.append(f"docs/.doc-profile: `{key}` must be a non-negative integer")
    if profile_exists:
        raw_version = values.get("harness_version")
        if raw_version is None:
            errors.append(
                "docs/.doc-profile: missing `harness_version`; repository docs use a "
                "legacy harness — explicitly migrate docs/ with the installed doc-create workflow"
            )
        else:
            try:
                profile_version = int(raw_version)
                if profile_version < 1:
                    raise ValueError
            except ValueError:
                errors.append("docs/.doc-profile: `harness_version` must be a positive integer")
            else:
                if profile_version < HARNESS_VERSION:
                    errors.append(
                        f"docs harness version {profile_version} is older than installed version "
                        f"{HARNESS_VERSION}; explicitly migrate docs/ with doc-create"
                    )
                elif profile_version > HARNESS_VERSION:
                    errors.append(
                        f"docs harness version {profile_version} is newer than installed version "
                        f"{HARNESS_VERSION}; upgrade the installed mrcall-ai-kit commands"
                    )
    return values, errors, profile_exists


def index_docs(root: Path, index_file: str) -> list[Path]:
    docs = [root / "README.md", root / index_file]
    docs_dir = root / "docs"
    if docs_dir.exists():
        docs += sorted(docs_dir.rglob("*.md"))
    seen, out = set(), []
    for p in docs:
        if p.exists() and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def canonical_repo_dirs(root: Path, index_file: str) -> set[str]:
    """Bare dir names from the `Path` column of the index's `## Services` table."""
    idx = root / index_file
    if not idx.exists():
        return set()
    lines = idx.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "## Services")
    except StopIteration:
        return set()
    names: set[str] = set()
    for ln in lines[start + 1:]:
        if ln.startswith("## "):
            break
        if not ln.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("Service", "---") or set(cells[0]) <= {"-", ":"}:
            continue
        m = re.search(r"`([^`]+)`", cells[1])
        if m:
            names.add(m.group(1).strip().strip("/").split("/")[0])
    return names


def is_independent_repo(d: Path) -> bool:
    return d.is_dir() and (d / ".git").exists()


def check_dead_links(root: Path, index_file: str) -> list[str]:
    errors: list[str] = []
    for doc in index_docs(root, index_file):
        base = doc.parent
        for m in MD_LINK.finditer(doc.read_text(encoding="utf-8")):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0].strip()
            if not target:
                continue
            if not (base / target).exists():
                errors.append(f"{doc.relative_to(root)} → dead link: ({m.group(1)})")
    return errors


def size_note(doc: Path, text: str) -> str:
    """`<bytes> bytes, ~<tokens> tokens` — the quantity the limits do NOT measure.

    Both size limits count lines, and a context window is billed in bytes. The
    two do not track each other: 160 lines of dense tables outweigh 400 lines of
    prose, so a file can pass the thin-index check while being the single most
    expensive thing a session loads. Reporting only lines describes the file;
    reporting bytes and tokens describes what opening it does to the session,
    which is the number any decision here actually turns on.

    Bytes come from `stat` — the number `wc -c` prints, reproducible by hand
    without opening the file, which is the same standard the line count is held
    to. Not `len(text.encode())`: `read_text` translates CRLF, so re-encoding
    would under-report a file by one byte per line. `text` is only the fallback
    for a doc that was readable a moment ago and can no longer be stat'd.

    Tokens are bytes // BYTES_PER_TOKEN, a convention recorded as such in
    docs/documentation-harness.md, printed with a `~` because it is an estimate
    and never a tokenizer result.
    """
    try:
        size = doc.stat().st_size
    except OSError:
        size = len(text.encode("utf-8"))
    return f"{size:,} bytes, ~{size // BYTES_PER_TOKEN:,} tokens"


def check_index_thin(root: Path, index_file: str, maximum: int) -> list[str]:
    index = root / index_file
    if not maximum or not index.is_file():
        return []
    text = index.read_text(encoding="utf-8")
    count = len(text.splitlines())
    if count > maximum:
        return [
            f"{index_file} has {count} lines, {size_note(index, text)} "
            f"(thin-index limit: {maximum} lines; set `index_max_lines = 0` to disable)"
        ]
    return []


def check_doc_sizes(root: Path, index_file: str, maximum: int) -> list[str]:
    """ADVISORY — name every doc that has grown past `doc_max_lines`.

    Never a gate failure. Whether a long document should be split, trimmed, or
    left alone is a judgement the operator makes with knowledge the harness does
    not have; the only thing worth automating is that nobody has to notice the
    growth by accident. So this reports and stops there.

    It deliberately reports the path, the line count, the byte size and a token
    estimate, and NOTHING else. That is what lets it cover `docs/projects/**`,
    which a session must never open at start-up: knowing `<project>/status.md` is
    900 lines and ~14,000 tokens costs a dozen tokens, while reading it to find
    out costs those fourteen thousand. The size is what makes the line
    actionable — see `size_note`.

    `docs/active-context-archive.md` is exempt — it is cold storage that grows
    forever by design, so flagging it every run would be noise, not signal.

    Defensive throughout: an advisory that raises would take the whole gate down
    with it, turning "your doc is long" into a blocked commit and a `/doc-end`
    that cannot advance its baseline. Anything it cannot measure, it skips —
    a doc that is genuinely unreadable is already the other checks' business.
    """
    if maximum <= 0:                      # 0 disables it; a negative value is invalid
        return []                         # and separately reported by read_profile
    oversized: list[tuple[int, str, str]] = []
    for doc in index_docs(root, index_file):
        try:
            rel = doc.relative_to(root).as_posix()
        except ValueError:                # an index_file reached from outside the root
            rel = doc.as_posix()
        if rel in SIZE_EXEMPT:
            continue
        try:
            text = doc.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # `count("\n")` and not `splitlines()`: the latter also breaks on form
        # feeds and unicode separators, so it can report more lines than `wc -l`.
        # The number has to be one the operator can reproduce without opening it.
        count = text.count("\n")
        if count > maximum:
            oversized.append((count, rel, size_note(doc, text)))
    return [
        f"{rel}: {count} line{'' if count == 1 else 's'}, {note} "
        f"(advisory limit: {maximum} lines)"
        for count, rel, note in sorted(oversized, key=lambda item: (-item[0], item[1]))
    ]


def check_trace_naming(root: Path) -> list[str]:
    """ADVISORY — name every work-trace file whose filename lacks a date prefix.

    Briefs and execution plans are the durable trace of a workstream; the
    `YYYY-MM-DD-` prefix is what lets them sort chronologically and answer "when
    was this decided" without git archaeology. Advisory, not a failure:
    repositories predating the convention hold undated files whose renaming is
    the operator's call, and making the filename a gate failure would require a
    `harness_version` bump plus an explicit migration. A `README.md` inside
    either directory is routing, not a trace, and is exempt.
    """
    warnings: list[str] = []
    for rel_dir in TRACE_DIRS:
        base = root / rel_dir
        if not base.exists():
            continue
        for doc in sorted(base.rglob("*.md")):
            if doc.name.lower() == "readme.md":
                continue
            if not TRACE_NAME.match(doc.name):
                warnings.append(
                    f"{doc.relative_to(root).as_posix()}: work-trace file without "
                    "a `YYYY-MM-DD-` date prefix"
                )
    return warnings


def frontmatter(text: str) -> tuple[dict[str, str], set[str]] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    values: dict[str, str] = {}
    duplicates: set[str] = set()
    for line in lines[1:]:
        if line.strip() == "---":
            return values, duplicates
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            if key in values:
                duplicates.add(key)
            values[key] = value.strip().strip("\"'")
    return None


def check_plan_statuses(root: Path) -> list[str]:
    plans = root / "docs" / "execution-plans"
    if not plans.exists():
        return []
    errors: list[str] = []
    for plan in sorted(plans.rglob("*.md")):
        rel = plan.relative_to(root)
        parsed = frontmatter(plan.read_text(encoding="utf-8"))
        if parsed is None:
            errors.append(f"{rel}: missing YAML frontmatter with `status`")
            continue
        metadata, duplicates = parsed
        if "status" in duplicates:
            errors.append(f"{rel}: frontmatter must contain exactly one `status`")
        elif "status" not in metadata:
            errors.append(f"{rel}: frontmatter is missing `status`")
        elif metadata["status"].lower() not in PLAN_STATUSES:
            allowed = "|".join(sorted(PLAN_STATUSES))
            errors.append(f"{rel}: invalid status `{metadata['status']}` (expected {allowed})")
    return errors


def check_session_statuses(root: Path) -> list[str]:
    """docs/sessions/*.md is the router's shared-memory blackboard: one file
    per Claude Code session, `status: open` until `/doc-end` promotes it into
    active-context.md and flips it to `closed`. Same enforcement shape as
    execution-plan status — a gate failure, not an advisory, because an
    invalid value here is a typo in a file the harness itself writes, not a
    judgment call.
    """
    sessions = root / "docs" / "sessions"
    if not sessions.exists():
        return []
    errors: list[str] = []
    for session in sorted(sessions.glob("*.md")):
        rel = session.relative_to(root)
        parsed = frontmatter(session.read_text(encoding="utf-8"))
        if parsed is None:
            errors.append(f"{rel}: missing YAML frontmatter with `status`")
            continue
        metadata, duplicates = parsed
        if "status" in duplicates:
            errors.append(f"{rel}: frontmatter must contain exactly one `status`")
        elif "status" not in metadata:
            errors.append(f"{rel}: frontmatter is missing `status`")
        elif metadata["status"].lower() not in SESSION_STATUSES:
            allowed = "|".join(sorted(SESSION_STATUSES))
            errors.append(f"{rel}: invalid status `{metadata['status']}` (expected {allowed})")
    return errors


def check_open_sessions(root: Path) -> list[str]:
    """ADVISORY — count docs/sessions/*.md still `status: open`.

    An open file mid-session is normal, not drift; only a stale one — its
    owning session long dead — is worth attention, and this check has no way
    to tell the two apart (no PID, no lock, just a transcript mtime that means
    nothing for a session left idle rather than closed). So it counts and
    stops: judging which open files are actually stale is `/router sweep`'s
    job, with the transcript timestamps this check does not have.
    """
    sessions = root / "docs" / "sessions"
    if not sessions.exists():
        return []
    open_files: list[str] = []
    for session in sorted(sessions.glob("*.md")):
        parsed = frontmatter(session.read_text(encoding="utf-8"))
        metadata = parsed[0] if parsed else {}
        if metadata.get("status", "").lower() == "open":
            open_files.append(session.relative_to(root).as_posix())
    return [f"{rel}: session still open" for rel in open_files]


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def check_baseline(root: Path) -> list[str]:
    context = root / "docs" / "active-context.md"
    if not context.is_file():
        return []
    parsed = frontmatter(context.read_text(encoding="utf-8"))
    metadata = parsed[0] if parsed else {}
    baseline = metadata.get("doc_baseline_commit", "")
    if not baseline:
        return ["docs/active-context.md: missing frontmatter `doc_baseline_commit`"]
    if run_git(root, "rev-parse", "--is-inside-work-tree").returncode:
        return ["cannot validate doc baseline: repo is not a Git worktree"]
    if run_git(root, "cat-file", "-e", f"{baseline}^{{commit}}").returncode:
        return [f"docs/active-context.md: baseline commit `{baseline}` does not exist"]
    if run_git(root, "merge-base", "--is-ancestor", baseline, "HEAD").returncode:
        return [f"docs/active-context.md: baseline `{baseline}` is not an ancestor of HEAD"]
    return []


def check_living_context(root: Path) -> list[str]:
    """`docs/active-context.md` is a snapshot, so its only `##` sections are the
    canonical three. Any other one is the append-only-changelog drift the living
    context must never accumulate; the pruned narrative belongs in
    `docs/active-context-archive.md`, which this check deliberately ignores.

    Headings are the objective half of the shape contract. Narrative prose and
    "too long for what it says" need judgment and stay with the semantic critic.
    """
    context = root / "docs" / "active-context.md"
    if not context.is_file():
        return []
    errors: list[str] = []
    fenced = False
    for number, raw in enumerate(context.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line.startswith("```") or line.startswith("~~~"):
            fenced = not fenced          # a `## ...` inside a code fence is content, not a heading
            continue
        if fenced or not line.startswith("## "):
            continue
        title = line[3:].strip()
        if title.lower() not in CONTEXT_SECTIONS:
            errors.append(
                f"docs/active-context.md:{number}: section `{title}` is not one of "
                "`State now` / `Unresolved` / `Next` — current material belongs folded "
                "into one of those, historical material in docs/active-context-archive.md"
            )
    return errors


def check_inventory(root: Path, index_file: str, ignore: set[str]) -> list[str]:
    errors: list[str] = []
    canonical = canonical_repo_dirs(root, index_file)
    if not canonical:
        return [f"meta mode requires a non-empty `## Services` table in {index_file}"]
    on_disk = {d.name for d in root.iterdir() if is_independent_repo(d) and d.name not in ignore}
    for repo in sorted(on_disk - canonical):
        errors.append(
            f"repo `{repo}/` is checked out under the repo root but is MISSING from "
            f"{index_file}'s `## Services` table (add it, or list it in inventory_ignore)"
        )
    for name in sorted(canonical):
        if not (root / name).exists():
            errors.append(
                f"{index_file} `## Services` lists `{name}/` but that directory does not exist (stale row)"
            )
    return errors


def check_no_dup_index(root: Path, index_file: str) -> list[str]:
    """README.md / docs/README.md must not carry a repo-inventory TABLE."""
    errors: list[str] = []
    repos = canonical_repo_dirs(root, index_file) - {"docs"}
    if not repos:
        return errors
    for rel in ("README.md", "docs/README.md"):
        doc = root / rel
        if not doc.exists():
            continue
        block: list[str] = []

        def flush(block: list[str]) -> None:
            joined = "\n".join(block)
            hits = {r for r in repos if re.search(rf"\b{re.escape(r)}\b", joined)}
            if len(hits) >= 3:
                errors.append(
                    f"{rel}: a markdown table lists {len(hits)} repos "
                    f"({', '.join(sorted(hits))}) — the repo inventory belongs ONLY in "
                    f"{index_file}; replace with a pointer"
                )

        for ln in doc.read_text(encoding="utf-8").splitlines():
            if ln.lstrip().startswith("|"):
                block.append(ln)
            elif block:
                flush(block)
                block = []
        if block:
            flush(block)
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Documentation integrity gate (mrcall-ai-kit).")
    ap.add_argument("--repo", help="repo root (default: git toplevel, else cwd)")
    args = ap.parse_args()

    root = repo_root(args.repo)
    prof, profile_errors, _ = read_profile(root)
    index_file = prof["index_file"]
    meta = prof["mode"].lower() == "meta"
    ignore = {s.strip() for s in prof["inventory_ignore"].split(",") if s.strip()}

    try:
        index_max_lines = int(prof["index_max_lines"])
    except ValueError:
        index_max_lines = 0
    try:
        doc_max_lines = int(prof["doc_max_lines"])
    except ValueError:
        doc_max_lines = 0
    groups = [
        ("PROFILE", profile_errors),
        ("DEAD LINKS", check_dead_links(root, index_file)),
        ("THIN INDEX", check_index_thin(root, index_file, index_max_lines)),
        ("PLAN STATUS", check_plan_statuses(root)),
        ("SESSION STATUS", check_session_statuses(root)),
        ("BASELINE", check_baseline(root)),
        ("LIVING CONTEXT", check_living_context(root)),
    ]
    if meta:
        groups.append(("INVENTORY DRIFT", check_inventory(root, index_file, ignore)))
        groups.append(("DUPLICATE INDEX", check_no_dup_index(root, index_file)))

    # Advisories, deliberately outside `groups`: they must never change the exit code.
    oversized = check_doc_sizes(root, index_file, doc_max_lines)
    undated = check_trace_naming(root)
    open_sessions = check_open_sessions(root)

    failed = [(name, errs) for name, errs in groups if errs]
    if not failed:
        print(
            f"doc-check: MECHANICAL GATE CLEAN — {root.name} "
            f"({'meta' if meta else 'leaf'} mode, harness v{HARNESS_VERSION})"
        )
    else:
        print("doc-check: MECHANICAL GATE FAILED")
        print("violations:")
        for name, errs in failed:
            print(f"  [{name}]")
            for e in errs:
                print(f"    - {e}")
    if oversized:
        print(f"advisory — {len(oversized)} oversized doc(s), NOT a gate failure:")
        for warning in oversized:
            print(f"    - {warning}")
    if undated:
        print(f"advisory — {len(undated)} undated work-trace file(s), NOT a gate failure:")
        for warning in undated:
            print(f"    - {warning}")
    if open_sessions:
        print(f"advisory — {len(open_sessions)} open session file(s), NOT a gate failure:")
        for warning in open_sessions:
            print(f"    - {warning}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
