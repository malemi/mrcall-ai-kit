#!/usr/bin/env python3
"""Fixture tests for shared/scripts/resolve-models.py.

Every case runs the resolver as the maintainer does, through its command line,
inside a temporary copy of the kit's layout, so no case can touch the
repository's own `models.json`. The live path is exercised against a local HTTP
server and a stand-in `opencode` on the PATH; no case reaches the network.
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "shared" / "scripts" / "resolve-models.py"
COMMITTED_REQUIREMENTS = ROOT / "shared" / "roles" / "requirements.json"
COMMITTED_AGENTS = ROOT / "shared" / "roles" / "agents.json"
COMMITTED_MODELS = ROOT / "shared" / "roles" / "models.json"

REQUIREMENTS = {
    "common": {
        "tools": True,
        "min_context": 200000,
        "excluded_variants": [":batch", ":free"],
        "required_scores": ["intelligence"],
    },
    "runtimes": {
        "claude": {
            "ceilings": {"low": 10, "medium": 20, "high": None},
            "roles": {
                "execute": {"rule": "satisfice", "index": "coding", "floor": 73},
                "verify": {"rule": "maximise", "index": "intelligence"},
            },
        },
        "opencode": {
            "ceilings": {"low": 5, "medium": 20, "high": None},
            "roles": {
                "execute": {"rule": "satisfice", "index": "coding", "floor": 73},
                "plan": {"rule": "maximise", "index": "agentic"},
                "verify": {"rule": "maximise", "index": "intelligence"},
            },
        },
    },
}

AGENTS = {
    "claude--execute": {"runtime": "claude", "name": "execute", "role": "execute",
                        "src": "claude/agents/{budget}/execute.md", "blocks": []},
    "claude--verify": {"runtime": "claude", "name": "verify", "role": "verify",
                       "src": "claude/agents/{budget}/verify.md", "blocks": []},
    "opencode--execute": {"runtime": "opencode", "name": "execute", "role": "execute",
                          "src": "opencode/agents/{budget}/execute.md", "blocks": []},
    "opencode--plan": {"runtime": "opencode", "name": "plan", "role": "plan",
                       "src": "opencode/agents/{budget}/plan.md", "blocks": []},
    "opencode--verify": {"runtime": "opencode", "name": "verify", "role": "verify",
                         "src": "opencode/agents/{budget}/verify.md", "blocks": []},
}
BUDGETS = ("low", "medium", "high")

# (catalogue id, $ per million output tokens, intelligence, coding, agentic)
#
# What the rules make of this world:
#   claude   low $10   verify mid-2 (40)       execute mid-2 (71, below the floor)
#   claude   med $20   verify big-3.1 (55)     execute mid-2 (71, below the floor)
#   claude   high      verify big-3.1 (55)     execute huge-4 (78, $25)
#   opencode low $5    verify pricier-coder    plan pricier-coder   execute cheap-coder
#   opencode med $20   verify big-3.1          plan agent-max       execute cheap-coder
#   opencode high      verify big-3.1          plan agent-max       execute cheap-coder
BASE = [
    ("anthropic/claude-small-1", 4, 30, 60, 20),
    ("anthropic/claude-mid-2", 10, 40, 71, 40),
    ("anthropic/claude-big-3.1", 20, 55, None, None),
    ("anthropic/claude-huge-4", 25, 50, 78, 45),
    ("vendor/cheap-coder", 2, 35, 74, 30),
    ("vendor/pricier-coder", 4, 45, 80, 50),
    ("vendor/agent-max", 6, 45, None, 56),
]


def per_token(dollars_per_million: float) -> str:
    return format(Decimal(str(dollars_per_million)) / Decimal(10) ** 6, "f")


def entry(model: str, price: float, *, context: int = 200000, tools: bool = True,
          slug: str | None = None) -> dict:
    params = ["max_tokens", "temperature"] + (["tools", "tool_choice"] if tools else [])
    return {
        "id": model,
        "canonical_slug": slug or f"{model.split(':')[0]}-20260101",
        "context_length": context,
        "pricing": {"prompt": per_token(price / 5), "completion": per_token(price)},
        "supported_parameters": params,
    }


def record(slug: str, intelligence, coding, agentic) -> dict:
    return {
        "source": "artificial-analysis",
        "model_permaslug": slug,
        "intelligence_index": intelligence,
        "coding_index": coding,
        "agentic_index": agentic,
    }


def world(rows=BASE) -> tuple[list, list]:
    catalogue, benchmarks = [], []
    for model, price, intelligence, coding, agentic in rows:
        catalogue.append(entry(model, price))
        benchmarks.append(record(f"{model}-20260101", intelligence, coding, agentic))
    # A record from another source, for a model the rules choose: its fields
    # are not scores, and it must not unseat the Artificial Analysis record.
    benchmarks.append({"source": "design-arena", "model_permaslug": "vendor/cheap-coder-20260101",
                       "elo": 1400, "win_rate": 60.0})
    return catalogue, benchmarks


class Kit:
    """A temporary copy of the kit's layout, holding only what the resolver reads."""

    def __init__(self, base: Path, requirements: dict = REQUIREMENTS, agents: dict = AGENTS,
                 models: dict | None = None) -> None:
        """`models` gives an agent's current model, one for every budget or a
        dict per budget; an agent it does not name runs `old-model`."""
        self.root = base / "kit"
        (self.root / "shared" / "scripts").mkdir(parents=True)
        (self.root / "shared" / "roles").mkdir(parents=True)
        shutil.copy(RESOLVER, self.root / "shared" / "scripts" / "resolve-models.py")
        self.write_json("shared/roles/requirements.json", requirements)
        self.write_json("shared/roles/agents.json", agents)
        for agent in agents.values():
            model = (models or {}).get(f"{agent['runtime']}--{agent['name']}", "old-model")
            for budget in BUDGETS:
                current = model[budget] if isinstance(model, dict) else model
                path = self.root / agent["src"].format(budget=budget)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"---\ndescription: test\nmodel: {current}\n---\n\nbody\n",
                                encoding="utf-8")
        self.models = self.root / "shared" / "roles" / "models.json"

    def write_json(self, rel: str, data) -> None:
        (self.root / rel).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def run(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        base_env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
        return subprocess.run(
            [sys.executable, str(self.root / "shared" / "scripts" / "resolve-models.py"), *args],
            capture_output=True, text=True, env=base_env | (env or {}), timeout=120)

    def selection(self) -> dict:
        return json.loads(self.models.read_text(encoding="utf-8"))


def write_fixture(where: Path, catalogue: list, benchmarks: list, *,
                  reachable: list[str] | None = None, read_at: str | None = None) -> Path:
    where.mkdir(parents=True, exist_ok=True)
    (where / "models.json").write_text(json.dumps({"data": catalogue}), encoding="utf-8")
    (where / "benchmarks.json").write_text(
        json.dumps({"data": benchmarks, "meta": {"as_of": "2026-09-25T00:00:00Z"}}), encoding="utf-8")
    if reachable is not None:
        (where / "opencode-models.txt").write_text("\n".join(reachable) + "\n", encoding="utf-8")
    if read_at is not None:
        (where / "read-at.txt").write_text(read_at + "\n", encoding="utf-8")
    return where


def picks(selection: dict, runtime: str, role: str) -> dict:
    """Each budget's chosen catalogue id for one role."""
    return {budget: outcome["roles"][role]["catalogue_id"]
            for budget, outcome in selection["runtimes"][runtime].items()}


class ResolverCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def resolve(self, rows=BASE, *, extra_catalogue=(), extra_benchmarks=(), reachable=None,
                requirements=REQUIREMENTS) -> tuple[subprocess.CompletedProcess, dict | None]:
        catalogue, benchmarks = world(rows)
        catalogue += list(extra_catalogue)
        benchmarks += list(extra_benchmarks)
        kit = Kit(self.base / f"k{len(list(self.base.iterdir()))}", requirements=requirements)
        fixture = write_fixture(kit.root.parent / "fixture", catalogue, benchmarks, reachable=reachable)
        run = kit.run("--fixture", str(fixture), "--apply")
        return run, (kit.selection() if kit.models.exists() else None)


class Rules(ResolverCase):
    def test_maximise_takes_the_best_score_at_or_under_the_ceiling(self) -> None:
        run, sel = self.resolve()
        self.assertEqual(run.returncode, 0, run.stderr)
        # $4 at a $5 ceiling, then the $20 model at exactly the $20 ceiling.
        self.assertEqual(picks(sel, "opencode", "verify"), {
            "low": "vendor/pricier-coder", "medium": "anthropic/claude-big-3.1",
            "high": "anthropic/claude-big-3.1"})
        self.assertEqual(picks(sel, "opencode", "plan"), {
            "low": "vendor/pricier-coder", "medium": "vendor/agent-max", "high": "vendor/agent-max"})
        # $10 at exactly the $10 ceiling.
        self.assertEqual(picks(sel, "claude", "verify")["low"], "anthropic/claude-mid-2")

    def test_satisfice_takes_the_cheapest_model_that_clears_the_floor(self) -> None:
        run, sel = self.resolve()
        self.assertEqual(run.returncode, 0, run.stderr)
        # cheap-coder (74, $2) clears 73; pricier-coder scores 80 and costs more.
        self.assertEqual(set(picks(sel, "opencode", "execute").values()), {"vendor/cheap-coder"})
        for outcome in sel["runtimes"]["opencode"].values():
            self.assertFalse(outcome["roles"]["execute"]["below_floor"])

    def test_a_score_equal_to_the_floor_clears_it(self) -> None:
        run, sel = self.resolve(BASE + [("vendor/exactly-floor", 1, 30, 73, None)])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(set(picks(sel, "opencode", "execute").values()), {"vendor/exactly-floor"})

    def test_below_the_floor_takes_the_best_score_and_says_so(self) -> None:
        run, sel = self.resolve()
        self.assertEqual(run.returncode, 0, run.stderr)
        claude = sel["runtimes"]["claude"]
        for budget in ("low", "medium"):
            execute = claude[budget]["roles"]["execute"]
            # mid-2 (71) rather than the cheaper small-1 (60): nothing clears 73.
            self.assertEqual(execute["catalogue_id"], "anthropic/claude-mid-2")
            self.assertTrue(execute["below_floor"])
        self.assertEqual(claude["high"]["roles"]["execute"]["catalogue_id"], "anthropic/claude-huge-4")
        self.assertFalse(claude["high"]["roles"]["execute"]["below_floor"])
        self.assertIn("below the floor of 73", run.stdout)

    def test_an_empty_role_raises_the_ceiling_for_every_role(self) -> None:
        # At $5 no model has an agentic score, so plan has no candidate. The
        # lowest price at which every role has one is $6, and verify then takes
        # wise-6 at $6 rather than staying under the $5 it was given.
        rows = [
            ("vendor/cheap-coder", 2, 35, 74, None),
            ("vendor/pricier-coder", 4, 45, 80, None),
            ("vendor/wise-6", 6, 52, None, None),
            ("vendor/agent-max", 6, 45, None, 56),
            ("anthropic/claude-mid-2", 10, 40, 71, 40),
        ]
        run, sel = self.resolve(rows)
        self.assertEqual(run.returncode, 0, run.stderr)
        low = sel["runtimes"]["opencode"]["low"]
        self.assertEqual(low["ceiling"], 5)
        self.assertEqual(low["raised_to"], 6)
        self.assertEqual(low["roles"]["plan"]["catalogue_id"], "vendor/agent-max")
        self.assertEqual(low["roles"]["verify"]["catalogue_id"], "vendor/wise-6")
        self.assertEqual(low["roles"]["execute"]["catalogue_id"], "vendor/cheap-coder")
        self.assertIsNone(sel["runtimes"]["opencode"]["medium"]["raised_to"])
        self.assertIn("opencode / low: ceiling $5, raised to $6", run.stdout)


class TieBreaks(ResolverCase):
    def test_maximise_tie_goes_to_the_cheaper_model(self) -> None:
        # Same intelligence; the cheaper one sorts last by name, so only the
        # price can choose it.
        extra = [("vendor/a-dear-genius", 3, 60, None, None), ("vendor/z-cheap-genius", 2, 60, None, None)]
        run, sel = self.resolve(BASE + extra)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(picks(sel, "opencode", "verify")["low"], "vendor/z-cheap-genius")

    def test_satisfice_tie_goes_to_the_higher_score(self) -> None:
        extra = [("vendor/a-coder-74", 1, 30, 74, None), ("vendor/z-coder-77", 1, 30, 77, None)]
        run, sel = self.resolve(BASE + extra)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(set(picks(sel, "opencode", "execute").values()), {"vendor/z-coder-77"})


class Exclusions(ResolverCase):
    """Each excluded model would win its role if it were a candidate."""

    def assert_never_chosen(self, model: str, catalogue: dict, bench: dict) -> None:
        run, sel = self.resolve(extra_catalogue=[catalogue], extra_benchmarks=[bench])
        self.assertEqual(run.returncode, 0, run.stderr)
        chosen = {role["catalogue_id"] for rt in sel["runtimes"].values()
                  for outcome in rt.values() for role in outcome["roles"].values()}
        self.assertNotIn(model, chosen)

    def test_a_model_without_tools(self) -> None:
        self.assert_never_chosen("vendor/genius", entry("vendor/genius", 1, tools=False),
                                 record("vendor/genius-20260101", 99, 99, 99))

    def test_a_model_with_short_context(self) -> None:
        self.assert_never_chosen("vendor/genius", entry("vendor/genius", 1, context=199999),
                                 record("vendor/genius-20260101", 99, 99, 99))

    def test_exactly_the_minimum_context_is_enough(self) -> None:
        run, sel = self.resolve(extra_catalogue=[entry("vendor/genius", 1, context=200000)],
                                extra_benchmarks=[record("vendor/genius-20260101", 99, 99, 99)])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(picks(sel, "opencode", "verify")["low"], "vendor/genius")

    def test_batch_and_free_variants(self) -> None:
        for variant in ("vendor/genius:free", "vendor/genius:batch"):
            with self.subTest(variant=variant):
                self.assert_never_chosen(variant, entry(variant, 1),
                                         record("vendor/genius-20260101", 99, 99, 99))

    def test_a_model_without_a_score_on_the_role_index(self) -> None:
        # Cheapest, clears nothing because it has no coding score at all.
        run, sel = self.resolve(extra_catalogue=[entry("vendor/no-coding", 0.5)],
                                extra_benchmarks=[record("vendor/no-coding-20260101", 99, None, 99)])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("vendor/no-coding", picks(sel, "opencode", "execute").values())
        # The same model is a candidate where its index is scored.
        self.assertEqual(picks(sel, "opencode", "verify")["low"], "vendor/no-coding")

    def test_a_model_without_an_intelligence_score(self) -> None:
        self.assert_never_chosen("vendor/no-intelligence", entry("vendor/no-intelligence", 0.5),
                                 record("vendor/no-intelligence-20260101", None, 99, 99))

    def test_a_route_without_a_fixed_price(self) -> None:
        # The catalogue writes -1 for a route whose price varies.
        priceless = entry("vendor/genius", 1)
        priceless["pricing"]["completion"] = "-1"
        self.assert_never_chosen("vendor/genius", priceless, record("vendor/genius-20260101", 99, 99, 99))

    def test_records_that_disagree_score_nothing_and_are_named(self) -> None:
        run, sel = self.resolve(extra_catalogue=[entry("vendor/genius", 1)],
                                extra_benchmarks=[record("vendor/genius-20260101", 99, 99, 99),
                                                  record("vendor/genius-20260101", 98, 98, 98)])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotEqual(picks(sel, "opencode", "verify")["low"], "vendor/genius")
        self.assertIn("their benchmark records disagree: vendor/genius-20260101", run.stdout)

    def test_records_that_agree_still_score(self) -> None:
        run, sel = self.resolve(extra_catalogue=[entry("vendor/genius", 1)],
                                extra_benchmarks=[record("vendor/genius-20260101", 99, 99, 99),
                                                  record("vendor/genius-20260101", 99, 99, 99)])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(picks(sel, "opencode", "verify")["low"], "vendor/genius")

    def test_a_model_is_scored_by_its_canonical_slug(self) -> None:
        # The benchmark record carries the canonical slug, not the id.
        run, sel = self.resolve(
            extra_catalogue=[entry("vendor/genius", 1, slug="vendor/genius-long-name-20260301")],
            extra_benchmarks=[record("vendor/genius-long-name-20260301", 99, 99, 99),
                              record("vendor/genius", 1, 1, 1)])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(picks(sel, "opencode", "verify")["low"], "vendor/genius")
        self.assertEqual(sel["runtimes"]["opencode"]["low"]["roles"]["verify"]["score"], 99)


class Degrades(ResolverCase):
    """An unreadable source, or a role no model can fill, changes nothing."""

    SENTINEL = '{"kept": "byte for byte"}\n'

    def kit(self) -> Kit:
        kit = Kit(self.base / "kit-home")
        kit.models.write_text(self.SENTINEL, encoding="utf-8")
        return kit

    def assert_refused(self, run: subprocess.CompletedProcess, kit: Kit, says: str) -> None:
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn(says, run.stderr)
        self.assertIn("shared/roles/models.json is unchanged", run.stderr)
        self.assertEqual(kit.models.read_text(encoding="utf-8"), self.SENTINEL)

    def test_a_missing_or_broken_payload(self) -> None:
        kit = self.kit()
        catalogue, benchmarks = world()
        fixture = write_fixture(self.base / "fx", catalogue, benchmarks)
        (fixture / "benchmarks.json").unlink()
        self.assert_refused(kit.run("--fixture", str(fixture), "--apply"), kit, "benchmarks.json")
        (fixture / "benchmarks.json").write_text("<html>502</html>", encoding="utf-8")
        self.assert_refused(kit.run("--fixture", str(fixture), "--apply"), kit, "not JSON")
        for body in ('{"error": "unauthorized"}', '{"data": []}'):
            (fixture / "benchmarks.json").write_text(body, encoding="utf-8")
            self.assert_refused(kit.run("--fixture", str(fixture), "--apply"), kit,
                                "its `data` list is missing or empty")

    def test_no_key(self) -> None:
        kit = self.kit()
        run = kit.run("--apply", env={"MRCALL_AI_KIT_OPENROUTER_API": "http://127.0.0.1:9/api/v1",
                                      "PATH": str(self.base)})
        self.assert_refused(run, kit, "OPENROUTER_API_KEY is not set")

    def test_an_endpoint_that_errors(self) -> None:
        kit = self.kit()
        catalogue, benchmarks = world()
        with Server({"/api/v1/models": (200, {"data": catalogue}),
                     "/api/v1/benchmarks": (500, {"error": "boom"})}) as server:
            run = kit.run("--apply", env={"MRCALL_AI_KIT_OPENROUTER_API": server.api,
                                          "OPENROUTER_API_KEY": "test-key", "PATH": str(self.base)})
        self.assert_refused(run, kit, "HTTP 500")

    def test_opencode_models_that_fails(self) -> None:
        kit = self.kit()
        catalogue, benchmarks = world()
        bin_dir = fake_opencode(self.base / "bin", exit_code=3)
        with Server({"/api/v1/models": (200, {"data": catalogue}),
                     "/api/v1/benchmarks": (200, {"data": benchmarks})}) as server:
            run = kit.run("--apply", env={"MRCALL_AI_KIT_OPENROUTER_API": server.api,
                                          "OPENROUTER_API_KEY": "test-key", "PATH": str(bin_dir)})
        self.assert_refused(run, kit, "`opencode models` exited 3")

    def test_a_partial_payload(self) -> None:
        # One page of a paginated catalogue, a catalogue shorter than its own
        # count, and benchmarks covering fewer models than their count: each
        # would resolve on part of the data, and none says so by failing.
        kit = self.kit()
        catalogue, benchmarks = world()
        cases = [
            ({"data": catalogue, "links": {"next": "/api/v1/models?page=2"}},
             {"data": benchmarks}, "came in pages"),
            ({"data": catalogue, "total_count": len(catalogue) + 1},
             {"data": benchmarks}, f"says it holds {len(catalogue) + 1} entries"),
            ({"data": catalogue, "total_count": len(catalogue), "links": {"next": None}},
             {"data": benchmarks, "meta": {"model_count": 99}}, "cover 99 models"),
        ]
        for catalogue_doc, bench_doc, says in cases:
            with self.subTest(says=says):
                fixture = self.base / "fx"
                fixture.mkdir(exist_ok=True)
                (fixture / "models.json").write_text(json.dumps(catalogue_doc), encoding="utf-8")
                (fixture / "benchmarks.json").write_text(json.dumps(bench_doc), encoding="utf-8")
                self.assert_refused(kit.run("--fixture", str(fixture), "--apply"), kit, says)

    def test_a_role_with_no_candidate_at_any_price(self) -> None:
        kit = self.kit()
        rows = [(m, p, i, c, None) for m, p, i, c, _ in BASE]  # no agentic score anywhere
        catalogue, benchmarks = world(rows)
        fixture = write_fixture(self.base / "fx", catalogue, benchmarks)
        self.assert_refused(kit.run("--fixture", str(fixture), "--apply"), kit,
                            "opencode: no candidate at any price for plan")


class Ids(ResolverCase):
    def test_each_runtime_gets_its_own_id(self) -> None:
        run, sel = self.resolve()
        self.assertEqual(run.returncode, 0, run.stderr)
        claude = sel["runtimes"]["claude"]["medium"]["roles"]["verify"]
        self.assertEqual(claude["catalogue_id"], "anthropic/claude-big-3.1")
        self.assertEqual(claude["model"], "claude-big-3-1")
        opencode = sel["runtimes"]["opencode"]["medium"]["roles"]["verify"]
        self.assertEqual(opencode["model"], "openrouter/anthropic/claude-big-3.1")

    def test_claude_code_is_offered_only_claude_models(self) -> None:
        run, sel = self.resolve(BASE + [("vendor/genius", 1, 99, 99, 99)])
        self.assertEqual(run.returncode, 0, run.stderr)
        for outcome in sel["runtimes"]["claude"].values():
            for role in outcome["roles"].values():
                self.assertTrue(role["catalogue_id"].startswith("anthropic/"), role)
        self.assertEqual(picks(sel, "opencode", "verify")["low"], "vendor/genius")

    def test_opencode_is_offered_only_the_routes_opencode_lists(self) -> None:
        listed = [f"openrouter/{row[0]}" for row in BASE if row[0] != "anthropic/claude-big-3.1"]
        run, sel = self.resolve(reachable=["opencode/big-pickle", *listed])
        self.assertEqual(run.returncode, 0, run.stderr)
        # big-3.1 is not listed, so OpenCode's verify takes the next best, while
        # Claude Code, which never uses OpenCode's routes, keeps it.
        self.assertEqual(picks(sel, "opencode", "verify")["medium"], "vendor/pricier-coder")
        self.assertEqual(picks(sel, "claude", "verify")["medium"], "anthropic/claude-big-3.1")
        self.assertTrue(sel["opencode_models_checked"])
        self.assertIn("only those `opencode models` lists", run.stdout)

    def test_a_fixture_without_a_listing_leaves_the_routes_unchecked_and_says_so(self) -> None:
        run, sel = self.resolve()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(sel["opencode_models_checked"])
        self.assertIn("not checked, the fixture holds no opencode-models.txt", run.stdout)


class LivePath(ResolverCase):
    def test_the_key_goes_to_the_benchmarks_only_and_a_saved_run_replays(self) -> None:
        kit = Kit(self.base / "live", models={"claude--verify": "claude-mid-2",
                                              "opencode--execute": "openrouter/vendor/cheap-coder"})
        catalogue, benchmarks = world()
        listed = [f"openrouter/{row[0]}" for row in BASE if row[0] != "anthropic/claude-big-3.1"]
        bin_dir = fake_opencode(self.base / "bin", listing=listed)
        saved = self.base / "saved"
        with Server({"/api/v1/models": (200, {"data": catalogue}),
                     "/api/v1/benchmarks": (200, {"data": benchmarks,
                                                  "meta": {"as_of": "2026-09-25T00:01:54Z"}})}) as server:
            run = kit.run("--apply", "--save", str(saved),
                          env={"MRCALL_AI_KIT_OPENROUTER_API": server.api,
                               "OPENROUTER_API_KEY": "test-key", "PATH": str(bin_dir)})
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(server.auth["/api/v1/benchmarks"], "Bearer test-key")
        self.assertIsNone(server.auth["/api/v1/models"])
        live = kit.models.read_bytes()
        selection = json.loads(live)
        self.assertEqual(selection["as_of"]["benchmarks"], "2026-09-25T00:01:54Z")
        self.assertTrue(selection["opencode_models_checked"])
        self.assertEqual(picks(selection, "opencode", "verify")["medium"], "vendor/pricier-coder")
        # The saved payloads replay offline to the same bytes.
        kit.models.unlink()
        replay = kit.run("--fixture", str(saved), "--apply", env={"PATH": str(self.base)})
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(kit.models.read_bytes(), live)


class LiveWithoutOpencode(ResolverCase):
    def test_the_routes_are_unchecked_and_that_is_said(self) -> None:
        kit = Kit(self.base / "no-opencode")
        catalogue, benchmarks = world()
        with Server({"/api/v1/models": (200, {"data": catalogue}),
                     "/api/v1/benchmarks": (200, {"data": benchmarks})}) as server:
            run = kit.run("--apply", env={"MRCALL_AI_KIT_OPENROUTER_API": server.api,
                                          "OPENROUTER_API_KEY": "test-key", "PATH": str(self.base)})
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("not checked, opencode is not on the PATH", run.stdout)
        self.assertFalse(kit.selection()["opencode_models_checked"])


class Written(ResolverCase):
    def test_the_selection_is_readable_like_any_file_there(self) -> None:
        # mkstemp makes a file for its owner alone; models.json is not one.
        kit = Kit(self.base / "mode")
        catalogue, benchmarks = world()
        fixture = write_fixture(self.base / "fx", catalogue, benchmarks)
        self.assertEqual(kit.run("--fixture", str(fixture), "--apply").returncode, 0)
        reference = kit.models.with_name("reference")
        reference.write_text("", encoding="utf-8")
        self.assertEqual(kit.models.stat().st_mode & 0o777, reference.stat().st_mode & 0o777)


class Diff(ResolverCase):
    def test_a_run_without_apply_prints_the_change_and_writes_nothing(self) -> None:
        kit = Kit(self.base / "diff", models={"claude--verify": "claude-small-1",
                                              "opencode--execute": "openrouter/vendor/pricier-coder",
                                              "opencode--plan": "opencode/big-pickle"})
        before = '{"previous": "selection"}\n'
        kit.models.write_text(before, encoding="utf-8")
        catalogue, benchmarks = world()
        fixture = write_fixture(self.base / "fx", catalogue, benchmarks)
        run = kit.run("--fixture", str(fixture))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(kit.models.read_text(encoding="utf-8"), before)
        lines = run.stdout.splitlines()

        def row(runtime_budget: str, agent: str) -> list[str]:
            start = lines.index(next(l for l in lines if l.startswith(runtime_budget)))
            block = lines[start + 1:]
            block = block[:block.index("")] if "" in block else block
            return next(l for l in block if l.split()[1] == agent).split()

        # old model and its catalogue price, then the new model and its price
        self.assertEqual(row("claude / low", "verify")[3:7],
                         ["claude-small-1", "($4)", "->", "claude-mid-2"])
        self.assertEqual(row("claude / low", "verify")[7], "($10)")
        self.assertEqual(row("opencode / medium", "execute")[3:8],
                         ["openrouter/vendor/pricier-coder", "($4)", "->",
                          "openrouter/vendor/cheap-coder", "($2)"])
        # a route the catalogue does not price
        self.assertEqual(row("opencode / high", "plan")[3:5], ["opencode/big-pickle", "($?)"])
        self.assertIn("nothing written", run.stdout)

    def test_the_old_side_is_each_budget_own_rendering(self) -> None:
        kit = Kit(self.base / "per-budget", models={"opencode--verify": {
            "low": "openrouter/vendor/cheap-coder", "medium": "openrouter/vendor/agent-max",
            "high": "opencode/big-pickle"}})
        catalogue, benchmarks = world()
        fixture = write_fixture(self.base / "fx", catalogue, benchmarks)
        run = kit.run("--fixture", str(fixture))
        self.assertEqual(run.returncode, 0, run.stderr)
        olds, block = {}, None
        for line in run.stdout.splitlines():
            if " / " in line and not line.startswith(" "):
                block = line.split(":")[0]            # e.g. "opencode / low"
            elif block and block.startswith("opencode / ") and line.split()[1:2] == ["verify"]:
                olds[block.split(" / ")[1]] = line.split()[3]
        self.assertEqual(olds, {"low": "openrouter/vendor/cheap-coder",
                                "medium": "openrouter/vendor/agent-max", "high": "opencode/big-pickle"})


class VerifyNeverBelowExecute(ResolverCase):
    """AC7: in every budget and on both runtimes, verify's model scores at least
    as high as execute's on intelligence."""

    def assert_holds(self, selection: dict) -> None:
        for runtime, budgets in selection["runtimes"].items():
            for budget, outcome in budgets.items():
                roles = outcome["roles"]
                with self.subTest(runtime=runtime, budget=budget):
                    self.assertGreaterEqual(roles["verify"]["scores"]["intelligence"],
                                            roles["execute"]["scores"]["intelligence"])

    def test_on_fixtures(self) -> None:
        # The second world starves execute under $5 and offers it only a
        # smarter, dearer coder: every role must then choose under the raised
        # ceiling, or verify falls below execute.
        starved = [
            ("vendor/dim-1", 1, 20, None, 30),
            ("vendor/fair-4", 4, 35, None, 40),
            ("vendor/coder-6", 6, 60, 80, 45),
            ("anthropic/claude-mid-2", 10, 40, 74, 40),
        ]
        for rows in (BASE, starved):
            run, sel = self.resolve(rows)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assert_holds(sel)

    def test_on_the_committed_selection(self) -> None:
        self.assert_holds(json.loads(COMMITTED_MODELS.read_text(encoding="utf-8")))


class CommittedData(unittest.TestCase):
    def test_every_agent_role_is_resolved_and_no_other(self) -> None:
        # A role no agent plays would still take part in raising a ceiling.
        requirements = json.loads(COMMITTED_REQUIREMENTS.read_text(encoding="utf-8"))
        agents = json.loads(COMMITTED_AGENTS.read_text(encoding="utf-8")).values()
        for runtime, spec in requirements["runtimes"].items():
            played = {a["role"] for a in agents if a["runtime"] == runtime}
            self.assertEqual(set(spec["roles"]), played, runtime)
            self.assertEqual(list(spec["ceilings"]), ["low", "medium", "high"], runtime)

    def test_the_committed_selection_covers_every_runtime_budget_and_role(self) -> None:
        requirements = json.loads(COMMITTED_REQUIREMENTS.read_text(encoding="utf-8"))
        selection = json.loads(COMMITTED_MODELS.read_text(encoding="utf-8"))
        self.assertEqual(set(selection["runtimes"]), set(requirements["runtimes"]))
        for runtime, spec in requirements["runtimes"].items():
            self.assertEqual(list(selection["runtimes"][runtime]), list(spec["ceilings"]))
            for outcome in selection["runtimes"][runtime].values():
                self.assertEqual(set(outcome["roles"]), set(spec["roles"]))
        self.assertTrue(selection["as_of"]["benchmarks"])
        self.assertTrue(selection["as_of"]["catalogue"])


# ------------------------------------------------------------- helpers


def fake_opencode(bin_dir: Path, *, listing: list[str] = (), exit_code: int = 0) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "opencode"
    lines = "".join(f"echo '{m}'\n" for m in listing)
    script.write_text(f"#!/bin/sh\n[ \"$1\" = models ] || exit 64\n{lines}exit {exit_code}\n",
                      encoding="utf-8")
    script.chmod(0o755)
    return bin_dir


class Server:
    """A local stand-in for OpenRouter's two endpoints, recording each
    request's Authorization header."""

    def __init__(self, routes: dict[str, tuple[int, dict]]) -> None:
        self.routes = routes
        self.auth: dict[str, str | None] = {}

    def __enter__(self) -> "Server":
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                server.auth[self.path] = self.headers.get("Authorization")
                status, body = server.routes.get(self.path, (404, {"error": "no route"}))
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args) -> None:
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.api = f"http://127.0.0.1:{self.httpd.server_address[1]}/api/v1"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


if __name__ == "__main__":
    unittest.main()
