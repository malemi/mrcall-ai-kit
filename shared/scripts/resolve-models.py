#!/usr/bin/env python3
"""Resolve each pinned role's model, for every budget on Claude and OpenCode.

A role declares requirements, never a model: `shared/roles/requirements.json`
holds each role's rule, index and floor per runtime, each runtime's price
ceiling per budget, and what every candidate must meet. This script reads
OpenRouter's catalogue (prices, context length, tool support) and its
benchmarks (the Artificial Analysis indices), joins them on `canonical_slug`,
and chooses a model for every runtime, budget and role:

- **maximise**: the highest score on the role's index among the candidates
  priced at or under the ceiling. A tie goes to the cheaper model.
- **satisfice**: the cheapest candidate at or under the ceiling whose score
  clears the role's floor. A tie goes to the higher score. When nothing clears
  the floor, the role takes the highest score under the ceiling, and the choice
  is marked below the floor.

When a role has no candidate under a budget's ceiling, that runtime's ceiling
for that budget is raised to the lowest price at which every role has one, and
the budget is marked raised. A role with no candidate at any price is a data
failure.

A price is US dollars per million output tokens (`pricing.completion`). Claude
Code's candidates are the catalogue's `anthropic/*` entries, written as Claude
model ids (`anthropic/claude-opus-5.5` becomes `claude-opus-5-5`). OpenCode's
are every entry, written `openrouter/<id>`; when `opencode` is on the PATH, only
the routes `opencode models` lists are candidates.

The run prints, for every Claude and OpenCode agent in
`shared/roles/agents.json` and every budget,
the model its rendering names now, the model resolved for it, and both prices.
It writes
`shared/roles/models.json` only with `--apply`. It degrades rather than
guesses: when a source cannot be read, or a role has no candidate at any price,
it exits 1 and leaves `models.json` as it was.

The benchmarks need an OpenRouter key, which is read from `OPENROUTER_API_KEY`
and from nowhere else. `--fixture <dir>` runs the same code from saved payloads;
`--save <dir>` saves what a run read, in the layout `--fixture` reads.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROLES = ROOT / "shared" / "roles"
REQUIREMENTS = ROLES / "requirements.json"
MANIFEST = ROLES / "agents.json"
MODELS = ROLES / "models.json"

DEFAULT_API = "https://openrouter.ai/api/v1"
# The API base can be pointed elsewhere, which is how the tests serve payloads
# from a local server.
API_ENV = "MRCALL_AI_KIT_OPENROUTER_API"
KEY_ENV = "OPENROUTER_API_KEY"

# The layout a fixture directory holds, and `--save` writes.
FIXTURE_CATALOGUE = "models.json"
FIXTURE_BENCHMARKS = "benchmarks.json"
FIXTURE_REACHABLE = "opencode-models.txt"
FIXTURE_READ_AT = "read-at.txt"

SCORE_SOURCE = "artificial-analysis"
INDEX_FIELDS = {
    "intelligence": "intelligence_index",
    "coding": "coding_index",
    "agentic": "agentic_index",
}
RULES = ("maximise", "satisfice")
RUNTIMES = ("claude", "opencode")
MILLION = Decimal(10) ** 6


class Refused(Exception):
    """A source could not be read, or the data cannot resolve a role."""


class ConfigError(Exception):
    """requirements.json or agents.json is not what this script reads."""


# ---------------------------------------------------------------- inputs


def load_requirements(path: pathlib.Path = REQUIREMENTS) -> dict:
    req = json.loads(path.read_text(encoding="utf-8"))
    common = req.get("common") or {}
    for field in ("tools", "min_context", "excluded_variants", "required_scores"):
        if field not in common:
            raise ConfigError(f"{path.name}: common.{field} is missing")
    for name in common["required_scores"]:
        if name not in INDEX_FIELDS:
            raise ConfigError(f"{path.name}: common.required_scores names unknown index {name!r}")
    runtimes = req.get("runtimes") or {}
    if not runtimes:
        raise ConfigError(f"{path.name}: no runtimes")
    for runtime, spec in runtimes.items():
        if runtime not in RUNTIMES:
            raise ConfigError(f"{path.name}: unknown runtime {runtime!r}")
        if not spec.get("ceilings"):
            raise ConfigError(f"{path.name}: {runtime} has no ceilings")
        for budget, ceiling in spec["ceilings"].items():
            if ceiling is not None and (isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)) or ceiling < 0):
                raise ConfigError(f"{path.name}: {runtime}.{budget} ceiling must be a price or null")
        if not spec.get("roles"):
            raise ConfigError(f"{path.name}: {runtime} has no roles")
        for role, rule in spec["roles"].items():
            where = f"{path.name}: {runtime}.{role}"
            if rule.get("rule") not in RULES:
                raise ConfigError(f"{where}: rule must be one of {', '.join(RULES)}")
            if rule.get("index") not in INDEX_FIELDS:
                raise ConfigError(f"{where}: index must be one of {', '.join(INDEX_FIELDS)}")
            if rule["rule"] == "satisfice" and not isinstance(rule.get("floor"), (int, float)):
                raise ConfigError(f"{where}: a satisfice rule needs a numeric floor")
    return req


def load_agents(req: dict, path: pathlib.Path = MANIFEST) -> list[dict]:
    """Agents with pinned models; Codex agents inherit the session model."""
    entries = json.loads(path.read_text(encoding="utf-8")).values()
    agents = sorted((e for e in entries if e["runtime"] != "codex"),
                    key=lambda e: (e["runtime"], e["name"]))
    for entry in agents:
        roles = req["runtimes"].get(entry["runtime"], {}).get("roles", {})
        if entry.get("role") not in roles:
            raise ConfigError(
                f"{path.name}: {entry['runtime']} agent {entry['name']} plays role "
                f"{entry.get('role')!r}, which requirements.json does not define")
    return agents


def current_model(entry: dict, budget: str) -> str | None:
    """The model an agent's rendering for a budget names now: what that
    budget runs today."""
    path = ROOT / entry["src"].format(budget=budget)
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("model:"):
            return line.split(":", 1)[1].strip() or None
    return None


# --------------------------------------------------------------- sources


def fetch(url: str, key: str | None = None) -> bytes:
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "mrcall-ai-kit resolve-models",
    })
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as err:
        raise Refused(f"cannot read {url}: HTTP {err.code}") from None
    except (urllib.error.URLError, OSError) as err:
        raise Refused(f"cannot read {url}: {getattr(err, 'reason', err)}") from None


def payload_list(raw: bytes, what: str) -> tuple[list, dict]:
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise Refused(f"cannot read the {what}: not JSON") from None
    data = doc.get("data") if isinstance(doc, dict) else None
    if not isinstance(data, list) or not data:
        raise Refused(f"cannot read the {what}: its `data` list is missing or empty")
    return data, doc


def complete_catalogue(doc: dict, data: list) -> None:
    """Refuse a catalogue that is one page of several, or shorter than it says."""
    links = doc.get("links") if isinstance(doc.get("links"), dict) else {}
    if links.get("next"):
        raise Refused("the catalogue came in pages (`links.next` is set), and a refresh reads one")
    total = doc.get("total_count")
    if isinstance(total, int) and total != len(data):
        raise Refused(f"the catalogue says it holds {total} entries and lists {len(data)}")


def complete_benchmarks(doc: dict, data: list) -> None:
    """Refuse benchmarks that cover fewer models than their `meta` counts."""
    meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
    count = meta.get("model_count")
    listed = len({r.get("model_permaslug") for r in data if isinstance(r, dict)})
    if isinstance(count, int) and count != listed:
        raise Refused(f"the benchmarks say they cover {count} models and list {listed}")


def opencode_models() -> bytes | None:
    """`opencode models`, or None when opencode is not on the PATH."""
    exe = shutil.which("opencode")
    if exe is None:
        return None
    try:
        run = subprocess.run([exe, "models"], stdin=subprocess.DEVNULL,
                             capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise Refused(f"cannot run `opencode models`: {err}") from None
    if run.returncode != 0:
        tail = run.stderr.decode("utf-8", "replace").strip()[-300:]
        raise Refused(f"`opencode models` exited {run.returncode}: {tail}")
    return run.stdout


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_sources(fixture: pathlib.Path | None) -> dict:
    """The raw payloads: from a fixture directory, or live."""
    if fixture is not None:
        def load(name: str, required: bool = True) -> bytes | None:
            path = fixture / name
            if path.is_file():
                return path.read_bytes()
            if required:
                raise Refused(f"cannot read {path}: no such file")
            return None
        read_at = load(FIXTURE_READ_AT, required=False)
        return {
            "catalogue": load(FIXTURE_CATALOGUE),
            "benchmarks": load(FIXTURE_BENCHMARKS),
            "reachable": load(FIXTURE_REACHABLE, required=False),
            "unchecked_because": f"the fixture holds no {FIXTURE_REACHABLE}",
            "read_at": read_at.decode("utf-8").strip() if read_at else None,
        }

    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise Refused(f"cannot read the benchmarks: {KEY_ENV} is not set")
    api = os.environ.get(API_ENV, DEFAULT_API).rstrip("/")
    read_at = now_utc()
    return {
        "catalogue": fetch(f"{api}/models"),
        "benchmarks": fetch(f"{api}/benchmarks", key),
        "reachable": opencode_models(),
        "unchecked_because": "opencode is not on the PATH",
        "read_at": read_at,
    }


def save_sources(raw: dict, where: pathlib.Path) -> None:
    where.mkdir(parents=True, exist_ok=True)
    (where / FIXTURE_CATALOGUE).write_bytes(raw["catalogue"])
    (where / FIXTURE_BENCHMARKS).write_bytes(raw["benchmarks"])
    if raw["reachable"] is not None:
        (where / FIXTURE_REACHABLE).write_bytes(raw["reachable"])
    if raw["read_at"]:
        (where / FIXTURE_READ_AT).write_text(raw["read_at"] + "\n", encoding="utf-8")


# ------------------------------------------------------------ candidates


def per_million(value: object) -> Decimal | None:
    """A catalogue price per token as dollars per million, or None when it is
    not a price: missing, unparseable, or negative (the catalogue writes -1 for
    a route whose price varies)."""
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not price.is_finite() or price < 0:
        return None
    return price * MILLION


def score(value: object) -> int | float | None:
    """A number as the source wrote it, or None when it is not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def scores_by_slug(benchmarks: list) -> tuple[dict, set]:
    """Artificial Analysis scores keyed by permaslug. A slug whose records
    disagree is returned apart, and no model is scored from it."""
    scores: dict[str, dict] = {}
    ambiguous: set[str] = set()
    for record in benchmarks:
        if not isinstance(record, dict) or record.get("source") != SCORE_SOURCE:
            continue
        slug = record.get("model_permaslug")
        if not slug:
            continue
        values = {name: score(record.get(field)) for name, field in INDEX_FIELDS.items()}
        if slug in scores and scores[slug] != values:
            ambiguous.add(slug)
        scores[slug] = values
    for slug in ambiguous:
        del scores[slug]
    return scores, ambiguous


def candidates(catalogue: list, benchmarks: list, common: dict) -> tuple[list[dict], set]:
    """Catalogue entries that meet what every role requires."""
    scores, ambiguous = scores_by_slug(benchmarks)
    out = []
    for entry in catalogue:
        if not isinstance(entry, dict):
            continue
        model = entry.get("id") or ""
        if any(model.endswith(variant) for variant in common["excluded_variants"]):
            continue
        slug_scores = scores.get(entry.get("canonical_slug"))
        if slug_scores is None:
            continue
        if common["tools"] and "tools" not in (entry.get("supported_parameters") or []):
            continue
        context = score(entry.get("context_length"))
        if context is None or context < common["min_context"]:
            continue
        pricing = entry.get("pricing") or {}
        price = per_million(pricing.get("completion"))
        if price is None:
            continue
        if any(slug_scores[name] is None for name in common["required_scores"]):
            continue
        out.append({
            "id": model,
            "price": price,
            "input_price": per_million(pricing.get("prompt")),
            "scores": slug_scores,
        })
    return out, ambiguous


def model_id(runtime: str, catalogue_id: str) -> str:
    """The id a runtime is given for a catalogue entry."""
    if runtime == "claude":
        return catalogue_id.split("/", 1)[1].replace(".", "-")
    return f"openrouter/{catalogue_id}"


def reachable_ids(raw: bytes | None) -> set[str] | None:
    if raw is None:
        return None
    ids = {line.strip() for line in raw.decode("utf-8", "replace").splitlines() if line.strip()}
    if not ids:
        raise Refused("`opencode models` listed no model")
    return ids


def runtime_pool(runtime: str, pool: list[dict], reachable: set[str] | None) -> list[dict]:
    if runtime == "claude":
        return [c for c in pool if c["id"].startswith("anthropic/")]
    if reachable is None:
        return list(pool)
    return [c for c in pool if model_id("opencode", c["id"]) in reachable]


# ------------------------------------------------------------- resolving


def choose(rule: dict, pool: list[dict]) -> tuple[dict, bool]:
    """The rule's choice from a non-empty pool, and whether it is below the
    floor. The last key of every ordering is the id, so a full tie still
    resolves the same way on every run."""
    index = rule["index"]

    def best(options: list[dict]) -> dict:
        return min(options, key=lambda c: (-c["scores"][index], c["price"], c["id"]))

    if rule["rule"] == "maximise":
        return best(pool), False
    clear = [c for c in pool if c["scores"][index] >= rule["floor"]]
    if clear:
        return min(clear, key=lambda c: (c["price"], -c["scores"][index], c["id"])), False
    return best(pool), True


def resolve_runtime(runtime: str, spec: dict, pool: list[dict]) -> dict:
    roles = spec["roles"]
    eligible = {role: [c for c in pool if c["scores"][rule["index"]] is not None]
                for role, rule in roles.items()}
    empty = sorted(role for role, options in eligible.items() if not options)
    if empty:
        raise Refused(f"{runtime}: no candidate at any price for {', '.join(empty)}")

    budgets = {}
    for budget, ceiling in spec["ceilings"].items():
        cap = None if ceiling is None else Decimal(str(ceiling))
        raised_to = None
        if cap is not None and any(min(c["price"] for c in options) > cap
                                   for options in eligible.values()):
            cap = max(min(c["price"] for c in options) for options in eligible.values())
            raised_to = cap
        picks = {}
        for role, rule in roles.items():
            under = [c for c in eligible[role] if cap is None or c["price"] <= cap]
            pick, below = choose(rule, under)
            picks[role] = {"candidate": pick, "below_floor": below}
        budgets[budget] = {"ceiling": ceiling, "raised_to": raised_to, "roles": picks}
    return budgets


def resolve(req: dict, raw: dict) -> dict:
    catalogue, cat_doc = payload_list(raw["catalogue"], "catalogue")
    complete_catalogue(cat_doc, catalogue)
    benchmarks, bench_doc = payload_list(raw["benchmarks"], "benchmarks")
    complete_benchmarks(bench_doc, benchmarks)
    reachable = reachable_ids(raw["reachable"])
    pool, ambiguous = candidates(catalogue, benchmarks, req["common"])
    meta = bench_doc.get("meta") if isinstance(bench_doc.get("meta"), dict) else {}
    return {
        "catalogue": catalogue,
        "benchmarks_as_of": meta.get("as_of"),
        "read_at": raw["read_at"],
        "reachable": reachable,
        "unchecked_because": raw["unchecked_because"],
        "pool": pool,
        "ambiguous": ambiguous,
        "runtimes": {
            runtime: resolve_runtime(runtime, spec, runtime_pool(runtime, pool, reachable))
            for runtime, spec in req["runtimes"].items()
        },
    }


# --------------------------------------------------------------- outputs


def number(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    value = value.normalize()
    return int(value) if value == value.to_integral_value() else float(format(value, "f"))


def dollars(value: Decimal | int | float | None) -> str:
    if value is None:
        return "$?"
    text = format(Decimal(str(value)).normalize(), "f")
    return f"${text}"


def document(req: dict, result: dict) -> dict:
    """What models.json holds: the selection, and what it was chosen on."""
    runtimes = {}
    for runtime, budgets in result["runtimes"].items():
        rules = req["runtimes"][runtime]["roles"]
        runtimes[runtime] = {}
        for budget, outcome in budgets.items():
            roles = {}
            for role, picked in outcome["roles"].items():
                c = picked["candidate"]
                roles[role] = {
                    "model": model_id(runtime, c["id"]),
                    "catalogue_id": c["id"],
                    "rule": rules[role]["rule"],
                    "index": rules[role]["index"],
                    "score": c["scores"][rules[role]["index"]],
                    "scores": c["scores"],
                    "price": {"input": number(c["input_price"]), "output": number(c["price"])},
                    "below_floor": picked["below_floor"],
                }
            runtimes[runtime][budget] = {
                "ceiling": outcome["ceiling"],
                "raised_to": number(outcome["raised_to"]),
                "roles": roles,
            }
    return {
        "as_of": {"benchmarks": result["benchmarks_as_of"], "catalogue": result["read_at"]},
        "opencode_models_checked": result["reachable"] is not None,
        "runtimes": runtimes,
    }


def old_price(runtime: str, model: str | None, catalogue: list) -> Decimal | None:
    """The catalogue price of the model a generated file names now, when the
    catalogue has one: a Claude id maps back to its `anthropic/*` entry, an
    `openrouter/` route to its entry. Aliases and other providers' routes have
    no price the catalogue gives."""
    if not model:
        return None
    for entry in catalogue:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id") or ""
        if runtime == "claude":
            if cid.startswith("anthropic/") and ":" not in cid and model_id("claude", cid) == model:
                return per_million((entry.get("pricing") or {}).get("completion"))
        elif model == f"openrouter/{cid}":
            return per_million((entry.get("pricing") or {}).get("completion"))
    return None


def report(req: dict, agents: list[dict], result: dict) -> tuple[list[str], int, int]:
    """The printed refresh: per runtime and budget, each agent's model now and
    its resolved model, with both prices and what the choice rests on."""
    lines = [
        f"catalogue read {result['read_at'] or 'at an unrecorded time'}, "
        f"benchmarks as of {result['benchmarks_as_of'] or 'an unrecorded date'}",
        f"{len(result['pool'])} catalogue entries meet every role's common requirements",
    ]
    if result["ambiguous"]:
        lines.append("not scored, their benchmark records disagree: "
                     + ", ".join(sorted(result["ambiguous"])))
    if "opencode" in req["runtimes"]:
        if result["reachable"] is None:
            lines.append(f"OpenCode routes: not checked, {result['unchecked_because']}")
        else:
            routes = sum(1 for m in result["reachable"] if m.startswith("openrouter/"))
            lines.append(f"OpenCode routes: only those `opencode models` lists "
                         f"({routes} openrouter routes)")
    changed = total = 0
    for runtime, budgets in result["runtimes"].items():
        rules = req["runtimes"][runtime]["roles"]
        for budget, outcome in budgets.items():
            ceiling = outcome["ceiling"]
            head = f"{runtime} / {budget}: " + ("no ceiling" if ceiling is None else f"ceiling {dollars(ceiling)}")
            if outcome["raised_to"] is not None:
                head += f", raised to {dollars(outcome['raised_to'])} because a role had no candidate under it"
            rows = []
            for entry in (a for a in agents if a["runtime"] == runtime):
                role = entry["role"]
                picked = outcome["roles"][role]
                c = picked["candidate"]
                new = model_id(runtime, c["id"])
                old = current_model(entry, budget)
                changed += old != new
                total += 1
                rule = rules[role]
                note = f"{rule['index']} {c['scores'][rule['index']]:g}"
                if rule["index"] != "intelligence":
                    note += f", intelligence {c['scores']['intelligence']:g}"
                if picked["below_floor"]:
                    note += f", below the floor of {rule['floor']:g}"
                rows.append((
                    "=" if old == new else "~", entry["name"], role,
                    f"{old or '-'} ({dollars(old_price(runtime, old, result['catalogue']))})",
                    f"{new} ({dollars(c['price'])})", note))
            widths = [max(len(row[i]) for row in rows) for i in range(5)]
            lines += ["", head]
            for row in rows:
                lines.append("  " + "  ".join(
                    [row[0], row[1].ljust(widths[1]), row[2].ljust(widths[2]),
                     row[3].ljust(widths[3]), "->", row[4].ljust(widths[4]), row[5]]))
    return lines, changed, total


def write_atomically(path: pathlib.Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        # mkstemp creates the file for its owner alone; give it the mode any
        # file written here gets.
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, path)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Resolve each role's model per runtime and budget, print the change, "
                    "and write shared/roles/models.json only with --apply.")
    ap.add_argument("--apply", action="store_true",
                    help="write shared/roles/models.json")
    ap.add_argument("--fixture", type=pathlib.Path, metavar="DIR",
                    help="read saved payloads from DIR instead of the network")
    ap.add_argument("--save", type=pathlib.Path, metavar="DIR",
                    help="save the payloads this run read into DIR, in the layout --fixture reads")
    args = ap.parse_args(argv)

    try:
        req = load_requirements()
        agents = load_agents(req)
    except (ConfigError, OSError, ValueError, KeyError) as err:
        print(f"resolve-models: {err}", file=sys.stderr)
        return 2

    try:
        raw = read_sources(args.fixture)
        if args.save is not None:
            save_sources(raw, args.save)
        result = resolve(req, raw)
    except Refused as err:
        print(f"resolve-models: {err}. {MODELS.relative_to(ROOT)} is unchanged.", file=sys.stderr)
        return 1

    lines, changed, total = report(req, agents, result)
    print("\n".join(lines))
    print()
    print(f"{changed} of {total} agent models differ from what the agent files name now.")
    if args.apply:
        write_atomically(MODELS, json.dumps(document(req, result), indent=2) + "\n")
        print(f"wrote {MODELS.relative_to(ROOT)}")
    else:
        print(f"nothing written; run with --apply to write {MODELS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
