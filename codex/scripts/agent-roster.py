#!/usr/bin/env python3
"""Install or remove the kit-owned block in Codex's global AGENTS.md."""
from __future__ import annotations

import argparse
import pathlib

START = "<!-- mrcall-ai-kit:codex-agents:start -->"
END = "<!-- mrcall-ai-kit:codex-agents:end -->"


def changed(current: str, block: str, action: str) -> str:
    starts, ends = current.count(START), current.count(END)
    if starts != ends or starts > 1:
        raise ValueError("global AGENTS.md has incomplete or duplicate kit markers")
    if starts == 0:
        return block + current if action == "on" else current
    before, rest = current.split(START, 1)
    _, after = rest.split(END, 1)
    if action == "on":
        return before + block.rstrip("\n") + after
    return before + after.removeprefix("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("on", "off", "check"))
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home())
    parser.add_argument("--block", type=pathlib.Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--on-exist", choices=("skip", "overwrite", "backup"), default="overwrite")
    args = parser.parse_args()
    target = args.home / ".codex" / "AGENTS.md"
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    block = args.block.read_text(encoding="utf-8") if args.block else ""
    if args.action == "on" and (not block.startswith(START) or not block.rstrip().endswith(END)):
        parser.error("--block must contain the complete kit block")
    if args.action == "on" and args.on_exist == "skip" and START in current:
        return 0
    try:
        new = changed(current, block, "on" if args.action == "check" else args.action)
    except ValueError as error:
        parser.error(str(error))
    if args.action == "off" and START in current:
        installed = current.split(START, 1)[1].split(END, 1)[0]
        if START + installed + END != block.rstrip("\n"):
            print("KEPT modified global AGENTS.md kit block")
            return 0
    if args.action == "check" or new == current:
        return 0
    if args.dry_run:
        print(f"would {args.action} kit block in {target}")
        return 0
    if new:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new, encoding="utf-8")
    else:
        target.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
