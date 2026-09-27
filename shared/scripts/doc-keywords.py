#!/usr/bin/env python3
"""doc-keywords: extract keywords from recent commits and check doc coverage.

Usage:
    python3 doc-keywords.py --repo <dir> [--range <rev>] [--docs-only]

Reads recent commits (default: baseline..HEAD from active-context.md, or
git rev-parse HEAD..HEAD if no baseline), extracts keywords from commit
messages, and checks whether those keywords appear in README.md and all
docs/*.md files. Prints a report of covered and uncovered keywords.
"""
import argparse
import subprocess
import re
import sys
import os
from pathlib import Path

# Common English stop words to skip when tokenizing commit messages
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "as", "is", "was", "are", "were",
    "been", "be", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "need",
    "dare", "ought", "used", "it", "its", "this", "that", "these", "those",
    "each", "every", "all", "both", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "because", "while", "where", "when", "how",
    "what", "which", "who", "whom", "into", "over", "after", "before",
    "between", "under", "again", "further", "then", "once", "here",
    "there", "why", "how", "also", "been", "being", "they", "them",
    "their", "he", "she", "him", "her", "his", "my", "your", "our",
    "we", "you", "i", "me", "us", "themselves", "himself", "herself",
    "ourselves", "yourselves", "itself", "myself", "yourself", "itself",
    "say", "says", "say", "shows", "show", "told", "record", "record",
    "keep", "keep", "test", "switch", "render", "render", "resolve",
    "switch", "retire", "name", "arm", "make", "hand", "complete",
    "advance", "advance", "consolidate", "check", "verify", "ensure",
}

def run_git(args, repo_dir):
    """Run a git command in the repo directory and return stdout."""
    result = subprocess.run(
        ["git", "-C", repo_dir] + args,
        capture_output=True, text=True
    )
    return result.stdout.strip()

def get_baseline(repo_dir):
    """Read doc_baseline_commit from docs/active-context.md frontmatter."""
    active = Path(repo_dir) / "docs" / "active-context.md"
    if not active.exists():
        return None
    content = active.read_text()
    # Extract doc_baseline_commit from frontmatter
    m = re.search(r'doc_baseline_commit:\s*(\S+)', content)
    if m:
        return m.group(1)
    return None

def get_commit_range(repo_dir, explicit_range=None):
    """Get the git range for commits to analyze."""
    if explicit_range:
        return explicit_range
    baseline = get_baseline(repo_dir)
    if baseline:
        try:
            run_git(["merge-base", "--is-ancestor", baseline, "HEAD"], repo_dir)
            return f"{baseline}..HEAD"
        except Exception:
            pass
    return "HEAD~10..HEAD"

def extract_keywords_from_commits(repo_dir, commit_range):
    """Extract keywords from commit messages in the given range."""
    log_output = run_git(["log", "--oneline", commit_range], repo_dir)
    if not log_output:
        return set()

    keywords = set()
    for line in log_output.split("\n"):
        if not line.strip():
            continue
        # Get the subject (first line)
        subject = line.split("\n")[0] if "\n" in line else line
        # Also get the body after the blank line
        body = ""
        if "\n\n" in line:
            body = line.split("\n\n", 1)[1]

        # Tokenize: split on non-alphanumeric boundaries, keep things like
        # /ai-budget, execute, verify, review, model, budget, etc.
        tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_-]*', subject)
        tokens += re.findall(r'/[A-Za-z][A-Za-z0-9-]*', subject)
        tokens += re.findall(r'[A-Za-z_][A-Za-z0-9_-]*', body)

        for token in tokens:
            lower = token.lower().strip("/")
            # Skip very short tokens, stop words, and common noise
            if len(lower) < 3:
                continue
            if lower in STOP_WORDS:
                continue
            # Skip pure verb forms that are too common
            if lower in {"run", "use", "see", "got", "new", "old", "set"}:
                continue
            keywords.add(lower)

    return keywords

def find_doc_files(repo_dir):
    """Find all doc files to check: README.md and docs/**/*.md."""
    docs = []
    # Root README.md
    readme = Path(repo_dir) / "README.md"
    if readme.exists():
        docs.append(("README.md", readme))
    # docs/**/*.md
    docs_dir = Path(repo_dir) / "docs"
    if docs_dir.exists():
        for md_file in sorted(docs_dir.rglob("*.md")):
            rel = str(md_file.relative_to(repo_dir))
            docs.append((rel, md_file))
    return docs

def read_file_content(path):
    """Read a file and return its content as lowercase text."""
    try:
        return path.read_text(errors="replace").lower()
    except Exception:
        return ""

def check_coverage(keywords, doc_files):
    """Check which keywords appear in which docs. Returns dict."""
    coverage = {kw: [] for kw in keywords}
    # Read all doc contents once
    contents = {}
    for name, path in doc_files:
        contents[name] = read_file_content(path)

    for kw in keywords:
        # Also check plural/singular variants and camelCase variants
        variants = [kw, kw + "s", kw + "es"]
        for name, content in contents.items():
            for variant in variants:
                if variant in content:
                    coverage[kw].append(name)
                    break

    return coverage

def main():
    parser = argparse.ArgumentParser(description="Check doc coverage of commit keywords")
    parser.add_argument("--repo", default=".", help="Repository directory")
    parser.add_argument("--range", help="Git range (e.g., baseline..HEAD)")
    parser.add_argument("--docs-only", action="store_true", help="Only check docs/ files")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    repo_dir = Path(args.repo).resolve()
    commit_range = get_commit_range(str(repo_dir), args.range)

    keywords = extract_keywords_from_commits(str(repo_dir), commit_range)
    doc_files = find_doc_files(str(repo_dir))
    coverage = check_coverage(keywords, doc_files)

    if args.json:
        import json
        # Convert to serializable format
        result = {
            "range": commit_range,
            "keywords": sorted(keywords),
            "coverage": {k: v for k, v in coverage.items()},
            "total_keywords": len(keywords),
            "covered": sum(1 for v in coverage.values() if v),
            "uncovered": sum(1 for v in coverage.values() if not v),
        }
        print(json.dumps(result, indent=2))
        return

    # Text output
    covered = {k: v for k, v in coverage.items() if v}
    uncovered = {k: v for k, v in coverage.items() if not v}

    print(f"=== Keyword Coverage Report ===")
    print(f"Range: {commit_range}")
    print(f"Keywords extracted: {len(keywords)}")
    print(f"Coverage: {len(covered)}/{len(keywords)} keywords appear in at least one doc")
    print()

    if covered:
        print("--- Covered keywords ---")
        for kw in sorted(covered):
            docs_list = ", ".join(covered[kw])
            print(f"  {kw}: found in {docs_list}")
        print()

    if uncovered:
        print("--- UNCOVERED keywords (not found in README.md or any docs/*.md) ---")
        for kw in sorted(uncovered):
            print(f"  ⚠️  {kw}: NOT found in any documentation")
        print()
        print("These keywords come from commit messages but appear in no doc.")
        print("Each uncovered keyword raises a question: is the omission justified,")
        print("or is documentation missing and needing an update?")

if __name__ == "__main__":
    main()
