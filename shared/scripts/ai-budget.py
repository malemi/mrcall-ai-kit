#!/usr/bin/env python3
"""Show or switch this machine's budget for the kit's agents: low, medium, high.

The kit renders every agent once per budget, and an install puts every budget's
rendering of each agent it installs in `~/.config/mrcall-ai-kit/agents/`, with
the machine's budget at the runtime's own path. The budget lives in
`~/.config/mrcall-ai-kit/budget`; without that file the machine runs medium.

With a level, this script records it and moves each runtime agent file the
install log records to that level's installed rendering: it re-points a link in
symlink mode, and re-copies the installed rendering in copy mode, so a copy
install never reads the checkout. Each move replaces the file in one step and
is logged with the backup the install recorded for that path, so
`uninstall.sh` still removes exactly what is there and `--restore-backups` still
puts back what an `--on-exist backup` install moved aside. Without a level it
prints the budget and each installed agent's model. An unknown level, or a
rendering that is missing, changes nothing.

It never resolves a model and never needs a network, a key or the checkout's
sources: the models were chosen when the kit's maintainer refreshed them.

`--report`, which `/ai-budget` passes, prints every outcome on stdout and exits
0, a refusal included: OpenCode hands a command only the stdout of its shell
line and ignores the exit status, so a message on stderr would never reach the
reader. Run directly, the script keeps stderr and its exit status (2 for a bad
argument, 1 for a refusal).
"""
from __future__ import annotations

import datetime
import os
import pathlib
import sys
import tempfile

BUDGETS = ("low", "medium", "high")
DEFAULT = "medium"
HOME = pathlib.Path.home()
KIT = HOME / ".config" / "mrcall-ai-kit"
BUDGET_FILE = KIT / "budget"
MANIFEST = KIT / "installed.tsv"
RENDERINGS = KIT / "agents"
RUNTIMES = {  # runtime → where it reads agents, and its name in the output
    "claude": (HOME / ".claude" / "agents", "Claude Code"),
    "opencode": (HOME / ".config" / "opencode" / "agents", "OpenCode"),
}
# When a switch reaches a runtime, as measured on Claude Code 2.1.280 and
# OpenCode 1.17.18 (docs/known-issues-and-solutions.md). OpenCode reads its
# agents when its process starts, so a new session in a running OpenCode keeps
# the models that process started with.
TAKES_EFFECT = {
    "claude": "the next delegation runs on these models, in sessions already open too.",
    "opencode": "an OpenCode started from now on runs on these models; one already running "
                "keeps its old models, in new sessions too, until it is restarted.",
}


class Refused(Exception):
    """The switch cannot be made; nothing was changed."""


def installed() -> dict[pathlib.Path, tuple[str, str, str]]:
    """The install log's last line for each path: its mode, source and backup."""
    latest: dict[pathlib.Path, tuple[str, str, str]] = {}
    if not MANIFEST.is_file():
        return latest
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 4 and fields[2]:
            backup = fields[4] if len(fields) > 4 else ""
            latest[pathlib.Path(fields[2])] = (fields[1], fields[3], backup)
    return latest


def model_of(path: pathlib.Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "(unreadable)"
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("model:"):
            return line.split(":", 1)[1].strip()
    return "(no model)"


def still_the_kits(dest: pathlib.Path, mode: str, src: str) -> bool:
    """The file at a recorded path is still what the install put there."""
    if mode == "symlink":
        return dest.is_symlink() and os.readlink(dest) == src
    return dest.is_file() and not dest.is_symlink()


def agents(log: dict) -> list[dict]:
    """Each runtime agent file the install log records, with the renderings the
    install put in the kit's home for it."""
    found = []
    for dest, (mode, src, backup) in sorted(log.items()):
        if mode not in ("symlink", "copy") or dest.suffix != ".md":
            continue
        runtime = next((rt for rt, (where, _) in RUNTIMES.items() if dest.parent == where), None)
        if runtime is None:
            continue
        renderings = {}
        for budget in BUDGETS:
            path = RENDERINGS / runtime / budget / dest.name
            entry = log.get(path)
            if entry and entry[0] in ("symlink", "copy") and (path.exists() or path.is_symlink()):
                renderings[budget] = (path, entry[1])
        found.append({"runtime": runtime, "name": dest.stem, "dest": dest, "mode": mode,
                      "src": src, "backup": backup, "renderings": renderings,
                      "kits": still_the_kits(dest, mode, src)})
    return found


def current_budget() -> tuple[str, str]:
    """The machine's budget, and where it comes from."""
    if not BUDGET_FILE.is_file():
        return DEFAULT, f"the default: {BUDGET_FILE} is absent"
    value = BUDGET_FILE.read_text(encoding="utf-8").strip()
    return value, str(BUDGET_FILE)


def write_atomically(path: pathlib.Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, path)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True)
        raise


def link_atomically(path: pathlib.Path, target: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.link")
    tmp.unlink(missing_ok=True)
    os.symlink(target, tmp)
    os.replace(tmp, path)


def log_line(mode: str, dest: pathlib.Path, src: str, backup: str) -> str:
    """A line in install.sh's format. The backup is the one the install recorded:
    a switch replaces the kit's file, never the operator's, so what an
    `--on-exist backup` install moved aside stays the file to restore."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{stamp}\t{mode}\t{dest}\t{src}\t{backup}\n"


def plan(level: str, found: list[dict]) -> list[tuple[dict, str, bytes | None]]:
    """What each agent becomes, checked in full before anything is written:
    (agent, the source to record, the bytes to copy or None for a link)."""
    moves, problems = [], []
    for agent in found:
        if not agent["kits"]:
            continue    # the operator's file now; left alone and listed
        rendering = agent["renderings"].get(level)
        if rendering is None:
            problems.append(f"{agent['dest']}: no {level} rendering in {RENDERINGS}")
            continue
        path, checkout_source = rendering
        if agent["mode"] == "symlink":
            if not os.path.exists(checkout_source):
                problems.append(f"{agent['dest']}: its {level} rendering links to "
                                f"{checkout_source}, which is gone")
                continue
            moves.append((agent, checkout_source, None))
        else:
            moves.append((agent, str(path), path.read_bytes()))
    if problems:
        raise Refused("cannot switch every agent, so none was switched:\n  "
                      + "\n  ".join(problems)
                      + "\nReinstall from the kit with ./install.sh --on-exist overwrite (or backup) to put "
                        "every budget's rendering in place; --on-exist skip leaves these files as they are.")
    return moves


def show(found: list[dict], budget: str) -> list[str]:
    lines = []
    for runtime, (_, label) in RUNTIMES.items():
        mine = [a for a in found if a["runtime"] == runtime]
        if not mine:
            continue
        lines.append(f"{label}:")
        width = max(len(a["name"]) for a in mine)
        for agent in mine:
            note = ""
            if not agent["kits"]:
                note = "  (not the kit's file any more: left alone)"
            else:
                rendering = agent["renderings"].get(budget)
                if rendering is None:
                    note = (f"  (installed without a {budget} rendering: reinstall with "
                            "--on-exist overwrite or backup to switch it)")
                else:
                    try:
                        same = agent["dest"].read_bytes() == rendering[0].read_bytes()
                    except OSError:
                        same = None
                    if same is None:
                        note = "  (unreadable: reinstall from the kit)"
                    elif not same:
                        note = f"  (not the {budget} rendering)"
            lines.append(f"  {agent['name']:<{width}}  {model_of(agent['dest'])}{note}")
    return lines


def main(argv: list[str]) -> int:
    report = bool(argv) and argv[0] == "--report"
    if report:
        argv = argv[1:]
    errors = sys.stdout if report else sys.stderr

    def failed(code: int) -> int:
        return 0 if report else code

    if len(argv) > 1:
        print("usage: ai-budget [low|medium|high]", file=errors)
        return failed(2)
    found = agents(installed())
    budget, source = current_budget()

    if not argv:
        valid = budget in BUDGETS
        print(f"Budget: {budget} ({source})" if valid
              else f"Budget: {source} says '{budget}', which is not one of {', '.join(BUDGETS)}")
        lines = show(found, budget if valid else DEFAULT)
        print("\n".join(lines) if lines else
              "No kit agents are installed; the next install places this budget's renderings.")
        return 0 if valid else failed(1)

    level = argv[0]
    if level not in BUDGETS:
        print(f"ai-budget: '{level}' is not a budget; use one of {', '.join(BUDGETS)}. "
              "Nothing was changed.", file=errors)
        return failed(2)
    try:
        moves = plan(level, found)
    except Refused as err:
        print(f"ai-budget: {err}", file=errors)
        return failed(1)

    KIT.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a", encoding="utf-8") as log:
        for agent, source_path, data in moves:
            if data is None:
                link_atomically(agent["dest"], source_path)
            else:
                write_atomically(agent["dest"], data)
            log.write(log_line(agent["mode"], agent["dest"], source_path, agent["backup"]))
            log.flush()
            agent["src"], agent["kits"] = source_path, True
    write_atomically(BUDGET_FILE, f"{level}\n".encode())

    was = budget if budget in BUDGETS else f"'{budget}'"
    print(f"Budget: {level}" + (" (unchanged)" if budget == level else f" (was {was})"))
    lines = show(found, level)
    print("\n".join(lines) if lines else
          "No kit agents are installed; the next install places this budget's renderings.")
    for runtime, (_, label) in RUNTIMES.items():
        if any(a["runtime"] == runtime for a in found):
            print(f"{label}: {TAKES_EFFECT[runtime]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
