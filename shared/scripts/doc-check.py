#!/usr/bin/env python3
"""
doc-check.py — the documentation integrity gate of the mrcall-ai-kit doc-harness.

Single source of truth: one canonical index file (default `CLAUDE.md`) holds the
repo inventory / roles / ownership; the other docs point to it and never
duplicate it. This checker fails (exit 1) when the docs drift from that rule, so
rot cannot survive a `/doc-start`, a `/doc-end`, or (if a repo opts in) a
pre-commit hook.

Checks (which run depends on the repo's profile — see below):
  1. DEAD LINKS   (always) — every relative markdown link in the index docs
                  (README.md, <index_file>, docs/*.md) must resolve on disk.
  2. INVENTORY    (meta mode only) — every independent sub-repo checked out under
                  the repo root must appear in <index_file>'s `## Services` table,
                  and every dir the table names must exist.
  3. NO DUP INDEX (meta mode only) — README.md / docs/README.md must NOT re-list
                  the repos in a table; the inventory lives ONLY in <index_file>.

Profile: an optional `docs/.doc-profile` file (simple `key = value` lines):
    mode              = meta | leaf          (default: leaf — links only)
    index_file        = CLAUDE.md            (the single-source index)
    inventory_ignore  = dir1, dir2           (sub-repo dirs to skip in INVENTORY)
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


def read_profile(root: Path) -> dict[str, str]:
    prof = root / "docs" / ".doc-profile"
    values: dict[str, str] = {"mode": "leaf", "index_file": "CLAUDE.md", "inventory_ignore": ""}
    if prof.exists():
        for line in prof.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()
    return values


def index_docs(root: Path, index_file: str) -> list[Path]:
    docs = [root / "README.md", root / index_file]
    docs += sorted((root / "docs").glob("*.md"))
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
        sys.exit(f"doc-check: FATAL — meta mode but no `## Services` table in {index_file}")
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


def check_inventory(root: Path, index_file: str, ignore: set[str]) -> list[str]:
    errors: list[str] = []
    canonical = canonical_repo_dirs(root, index_file)
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
    prof = read_profile(root)
    index_file = prof["index_file"]
    meta = prof["mode"].lower() == "meta"
    ignore = {s.strip() for s in prof["inventory_ignore"].split(",") if s.strip()}

    groups = [("DEAD LINKS", check_dead_links(root, index_file))]
    if meta:
        groups.append(("INVENTORY DRIFT", check_inventory(root, index_file, ignore)))
        groups.append(("DUPLICATE INDEX", check_no_dup_index(root, index_file)))

    failed = [(name, errs) for name, errs in groups if errs]
    if not failed:
        print(f"doc-check: OK — {root.name} docs clean ({'meta' if meta else 'leaf'} mode).")
        return 0
    print("doc-check: FAILED\n")
    for name, errs in failed:
        print(f"  [{name}]")
        for e in errs:
            print(f"    - {e}")
        print()
    print(f"Fix the above (single source of truth = {index_file}) or the commit/step is blocked.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
