"""Content-bound completion records for doc-check.py; judgments remain attestations."""
from __future__ import annotations

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

LIMIT = "This CLI checks evidence coverage, hashes, and freshness. Lead context availability and reviewer judgments are attestations, not authenticated proof. A host can still skip this entire gate."
ORIENTATION = {"AGENTS.md", "docs/README.md", "docs/active-context.md", "docs/.doc-profile"}
BASELINE_KEYS = {b"doc_baseline_commit", b"doc_baseline_date"}


class Refusal(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def hashed(data):
    return hashlib.sha256(data).hexdigest()


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True)
    require(result.returncode == 0, result.stderr.decode(errors="replace").strip() or "Git command failed")
    return result.stdout


def committed_head(root):
    result = subprocess.run(["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=root, capture_output=True)
    require(result.returncode == 0, "completion requires an existing committed HEAD and ancestor base; unborn repositories cannot initialize or finalize evidence")
    return result.stdout.decode().strip()


def identity(root, task):
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", task or "")), "--task must be a simple nonempty task ID")
    require(Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve() == root, "--repo must be the worktree root")
    directory = str(Path(git(root, "rev-parse", "--absolute-git-dir").decode().strip()).resolve())
    return {"repo": str(root), "git_dir": directory, "task_id": task}


def no_symlinks(path):
    for part in (path, *path.parents):
        require(not part.is_symlink(), f"symlink evidence path refused: {part}")


def record_path(binding):
    path = Path(binding["git_dir"]) / "doc-completion" / (binding["task_id"] + ".json")
    no_symlinks(path)
    return path


@contextlib.contextmanager
def task_mutation_lock(binding):
    path = record_path(binding).with_suffix(".lock")
    no_symlinks(path)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Refusal("task mutation already in progress; retry this action after it finishes") from exc
        yield
    finally:
        os.close(descriptor)


def write_bytes(path, data, mode=0o600):
    no_symlinks(path)
    fd, temporary = tempfile.mkstemp(prefix=".doc-completion-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            os.fchmod(handle.fileno(), mode)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save(record):
    path = record_path(record["binding"])
    path.parent.mkdir(mode=0o700, exist_ok=True)
    write_bytes(path, packed(record) + b"\n")


def load(binding):
    path = record_path(binding)
    require(path.is_file(), "no record for this task; initialize only an authorized mutating task")
    record = json.loads(path.read_text())
    require(isinstance(record, dict), "record must be a JSON object")
    require(record.get("schema_version") == 1 and record.get("binding") == binding, "record schema/task/repository/worktree mismatch")
    require(isinstance(record.get("config"), dict) and isinstance(record.get("attestations"), dict) and isinstance(record.get("results"), dict), "invalid record structure")
    require(record.get("scope_digest") == hashed(packed({"binding": binding, "config": record["config"]})), "record scope/configuration binding changed")
    return record


def relative(value, allow_root=False):
    require(isinstance(value, str) and bool(value), "paths must be nonempty repository-relative strings")
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts and ".git" not in path.parts, f"path leaves repository content: {value}")
    result = path.as_posix()
    require(allow_root or result != ".", "a file path is required")
    return result


def paths(values, allow_root=False):
    require(isinstance(values, list), "expected a path list")
    return sorted({relative(value, allow_root) for value in values})


def file_digest(path):
    require(path.is_file(), f"required artifact does not exist: {path}")
    return hashed(path.read_bytes())


def workflows(config, checker):
    supplied = config["workflows"]
    require(isinstance(supplied, dict) and set(supplied) == {"doc_start", "doc_end", "doc_critic"}, "workflows must name doc_start, doc_end, and doc_critic")
    template = checker.find_harness_template()
    require(template is not None, "canonical managed block is unavailable")
    selected = {**supplied, "checker": str(Path(checker.__file__).resolve()), "completion": str(Path(__file__).resolve()), "managed_block": str(template.resolve())}
    result = {}
    for key, value in selected.items():
        path = Path(value)
        require(path.is_absolute(), f"workflow {key} must be an absolute path")
        result[key] = {"path": str(path.resolve()), "sha256": file_digest(path)}
    return result


def metadata(data, replacements=None, normalize=()):
    lines = data.splitlines(keepends=True)
    require(bool(lines) and lines[0].strip() == b"---", "finalization requires existing YAML frontmatter")
    found = set()
    closed = False
    output = [lines[0]]
    keys = set(normalize) | set(replacements or {})
    for number, line in enumerate(lines[1:], 1):
        if line.strip() == b"---":
            output.extend(lines[number:])
            closed = True
            break
        key, colon, value = line.partition(b":")
        name = key.strip()
        if colon and name in keys:
            require(name not in found, f"duplicate finalization field: {name.decode()}")
            found.add(name)
            ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
            replacement = b"<metadata>" if name in normalize else replacements[name]
            line = key + b": " + replacement + ending
        output.append(line)
    require(closed and found == keys, "finalization fields must already exist exactly once before review")
    return b"".join(output)


def metadata_values(data, keys):
    result = {}
    require(data.splitlines() and data.splitlines()[0].strip() == b"---", "concurrent metadata structure changed")
    closed = False
    for line in data.splitlines(keepends=True)[1:]:
        if line.strip() == b"---":
            closed = True
            break
        key, colon, value = line.partition(b":")
        if colon and key.strip() in keys:
            require(key.strip() not in result, "concurrent duplicate metadata field")
            result[key.strip()] = value.rstrip(b"\r\n")
    require(closed and set(result) == keys, "concurrent metadata structure changed")
    return result


def restore_metadata(current, original, published, keys):
    old = metadata_values(original, keys)
    expected = metadata_values(published, keys)
    actual = metadata_values(current, keys)
    require(actual == expected or actual == old, "concurrent metadata ownership conflict")
    if actual == old:
        return current
    result = []
    in_header = True
    for number, line in enumerate(current.splitlines(keepends=True)):
        if number and line.strip() == b"---":
            in_header = False
        key, colon, value = line.partition(b":")
        if in_header and colon and key.strip() in keys:
            ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
            line = key + b":" + old[key.strip()] + ending
        result.append(line)
    return b"".join(result)


def normalized_content(record, rel, data):
    if rel == "docs/active-context.md":
        return metadata(data, normalize=BASELINE_KEYS)
    transition = record["config"].get("plan_transition")
    if transition and rel == transition["path"]:
        return metadata(data, normalize={b"status"})
    return data


def working_file(root, rel, record, normalized=False):
    path = root / rel
    for parent in path.parents:
        if parent == root:
            break
        require(not parent.is_symlink(), f"cannot bind content under symlink directory: {rel}")
    if path.is_symlink():
        try:
            target = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise Refusal(f"cannot bind symlink target: {rel}: {exc}") from exc
        require(target.is_file(), f"cannot bind non-file symlink target: {rel}")
        data = target.read_bytes()
        if normalized:
            data = normalized_content(record, rel, data)
        return {"kind": "symlink", "sha256": hashed(os.fsencode(os.readlink(path))),
                "target": {"path": str(target), "sha256": hashed(data), "mode": stat.S_IMODE(target.stat().st_mode)}}
    if not path.exists():
        return None
    require(path.is_file(), f"cannot bind directory/submodule as file content: {rel}")
    data = path.read_bytes()
    if normalized:
        data = normalized_content(record, rel, data)
    return {"kind": "file", "sha256": hashed(data), "mode": stat.S_IMODE(path.stat().st_mode)}


def names(data):
    return {os.fsdecode(value) for value in data.split(b"\0") if value}


def snapshot(record, checker, normalized=False):
    root = Path(record["binding"]["repo"])
    config = record["config"]
    head = committed_head(root)
    require(subprocess.run(["git", "merge-base", "--is-ancestor", config["base"], head], cwd=root, capture_output=True).returncode == 0, "task base is no longer an ancestor of HEAD")
    committed = names(git(root, "diff", "--no-renames", "--name-only", "-z", config["base"], head, "--"))
    dirty = names(git(root, "diff", "--no-renames", "--name-only", "-z", "--"))
    staged = names(git(root, "diff", "--cached", "--no-renames", "--name-only", "-z", "--"))
    untracked = names(git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    tracked = names(git(root, "ls-files", "--cached", "-z"))
    changed = committed | dirty | staged | untracked
    scope = config["scope"]
    relevant = {rel for rel in tracked | untracked if any(part == "." or rel == part or rel.startswith(part + "/") for part in scope)}
    relevant |= changed | ORIENTATION | set(record.get("impact", {}).get("affected_docs", []))
    reviews = config.get("reviews", {})
    relevant |= set([reviews["brief"], reviews["plan"], *reviews["milestones"].values()]) if reviews else set()
    transition = config.get("plan_transition")
    if transition:
        relevant.add(transition["path"])
    working = {rel: working_file(root, rel, record, normalized) for rel in sorted(relevant)}
    if normalized:
        exempt = {"docs/active-context.md"} | ({transition["path"]} if transition else set())
        changed -= exempt
        untracked -= exempt
    return {"binding": record["binding"], "scope_digest": record["scope_digest"], "head": head, "base": config["base"],
            "workflows": workflows(config, checker), "index_content": hashed(git(root, "ls-files", "--stage", "-z")),
            "working": working, "changed_paths": sorted(changed), "untracked_paths": sorted(untracked),
            "reviewed_docs": record.get("impact", {}).get("affected_docs", []), "doc_impact": record.get("impact", {}).get("doc_impact"),
            "approved_versions": {key: {"artifact": value["artifact"], "source": value["source"], "scope_digest": value["scope_digest"]}
                                  for key, value in sorted(record["results"].items()) if "artifact" in value}}


def snapshot_digest(value):
    return hashed(packed(value))


def evidence_digest(record):
    return hashed(packed({"impact": record.get("impact"),
                          "attestations": {key: value for key, value in record["attestations"].items() if key != "startup"},
                          "results": {key: value for key, value in record["results"].items() if key != "final-review"}}))


def startup_digest(record, checker, documents):
    root = Path(record["binding"]["repo"])
    return hashed(packed({"binding": record["binding"], "workflows": workflows(record["config"], checker),
                         "documents": {rel: working_file(root, rel, record) for rel in documents}}))


def required(record):
    result = ["startup", "impact"]
    kind = record["config"]["kind"]
    if kind in {"development", "fastpath"}:
        result.append("focused")
    if kind != "fastpath" or record.get("impact", {}).get("doc_impact") is not False:
        result += ["reconciliation", "mechanical", "critic"]
    if kind == "development":
        result += ["brief-review", "plan-review"]
        result += ["milestone-review:" + key for key in record["config"]["reviews"]["milestones"]]
        result.append("final-review")
    return result


def init(binding, data, checker):
    require(isinstance(data, dict), "init requires a JSON object")
    require(data.get("kind") in {"documentation", "development", "fastpath"}, "only authorized documentation/development/fastpath mutations may create records")
    scope = paths(data.get("scope"), True)
    require(bool(scope), "task scope must not be empty")
    root = Path(binding["repo"])
    committed_head(root)
    base = git(root, "rev-parse", "--verify", str(data.get("base", "")) + "^{commit}").decode().strip()
    require(subprocess.run(["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=root, capture_output=True).returncode == 0, "base must be an existing ancestor of HEAD")
    config = {"kind": data["kind"], "scope": scope, "base": base, "workflows": data.get("workflows")}
    transition = data.get("plan_transition")
    if transition:
        require(transition.get("from") == "active" and transition.get("to") == "completed", "only a predeclared active -> completed plan transition is supported")
        config["plan_transition"] = {"path": relative(transition["path"]), "from": "active", "to": "completed"}
    if data["kind"] == "development":
        reviews = data.get("reviews", {})
        require(isinstance(reviews.get("milestones"), dict) and bool(reviews["milestones"]), "development requires explicit brief, plan, and milestone review artifacts")
        config["reviews"] = {"brief": relative(reviews.get("brief")), "plan": relative(reviews.get("plan")), "milestones": {key: relative(value) for key, value in sorted(reviews["milestones"].items())}}
    record = {"schema_version": 1, "binding": binding, "config": config, "scope_digest": hashed(packed({"binding": binding, "config": config})),
              "workflow_hashes": workflows(config, checker), "attestations": {}, "results": {}, "limit": LIMIT}
    path = record_path(binding)
    if path.exists():
        old = load(binding)
        require(old["config"] == config, "task already exists with a different immutable scope/configuration; use a new task ID")
        return old
    record["initial_snapshot"] = snapshot(record, checker)
    save(record)
    return record


def attestation(record, data, checker):
    require(data.get("producer") == "lead", "lead-only decisions require producer=lead")
    obligation = data.get("obligation")
    require(obligation in {"startup", "impact", "reconciliation"}, "invalid lead obligation")
    if obligation != "startup":
        record.pop("finalized", None)
    if obligation == "startup":
        documents = paths(data.get("documents"))
        require(ORIENTATION <= set(documents), "startup attestation must cover AGENTS, docs index, active context, and profile")
        require(data.get("available") is True and bool(data.get("context_id")), "lead must reload missing knowledge before attesting context availability")
        for rel in documents:
            file_digest(Path(record["binding"]["repo"]) / rel)
        value = {"producer": "lead", "documents": documents, "context_id": data["context_id"], "available": True,
                 "digest": startup_digest(record, checker, documents)}
    else:
        require(isinstance(data.get("reason"), str) and data["reason"].strip(), "lead decision requires an explicit reason")
        if obligation == "impact":
            require(isinstance(data.get("doc_impact"), bool), "impact requires doc_impact true or false")
            docs = paths(data.get("affected_docs", []))
            if record["config"]["kind"] != "fastpath" or data["doc_impact"]:
                docs = sorted(set(docs) | {"docs/active-context.md"})
            for rel in docs:
                file_digest(Path(record["binding"]["repo"]) / rel)
            require(bool(data.get("work_trace")), "impact requires an explicit work_trace decision/reference")
            record["impact"] = {"doc_impact": data["doc_impact"], "affected_docs": docs, "reason": data["reason"], "work_trace": data["work_trace"]}
        require("impact" in record, "record the lead impact decision before reconciliation")
        value = {"producer": "lead", "reason": data["reason"], "snapshot": snapshot_digest(snapshot(record, checker))}
    record["attestations"][obligation] = value
    save(record)


def run_check(record, action, data, checker):
    before = snapshot(record, checker)
    if action == "mechanical":
        argv = [sys.executable, str(Path(checker.__file__).resolve()), "--repo", record["binding"]["repo"], "--json"]
    else:
        argv = data.get("argv")
        require(isinstance(argv, list) and bool(argv) and all(isinstance(a, str) for a in argv), "focused check requires an explicit argv array")
    result = subprocess.run(argv, cwd=record["binding"]["repo"], capture_output=True)
    after = snapshot(record, checker)
    value = {"producer": "doc-check.py", "argv": argv, "exit_status": result.returncode, "stdout_sha256": hashed(result.stdout),
             "stderr_sha256": hashed(result.stderr), "snapshot": snapshot_digest(before), "content_unchanged": before == after}
    record["results"][action] = value
    record.pop("finalized", None)
    save(record)
    return {**value, "stdout": result.stdout.decode(errors="replace"), "stderr": result.stderr.decode(errors="replace")}


def prior_artifact(record, gate, gate_id):
    reviews = record["config"].get("reviews", {})
    if gate == "brief-review":
        require(gate_id == "brief", "brief-review requires gate_id=brief")
        return reviews.get("brief")
    if gate == "plan-review":
        require(gate_id == "plan", "plan-review requires gate_id=plan")
        return reviews.get("plan")
    if gate == "milestone-review":
        return reviews.get("milestones", {}).get(gate_id)
    return None


def register_result(record, filename, checker):
    path = Path(filename).resolve()
    data = json.loads(path.read_text())
    require(isinstance(data, dict), "review envelope must be a JSON object")
    require(data.get("schema_version") == 1, "review envelope requires schema_version 1")
    for key, value in record["binding"].items():
        require(data.get(key) == value, "review result task/repository/worktree mismatch")
    gate = data.get("gate_kind")
    require(gate in {"critic", "final-review", "brief-review", "plan-review", "milestone-review"}, "invalid review gate kind")
    require(isinstance(data.get("producer"), str) and data["producer"].strip(), "review result must name its actual producer")
    require(data.get("outcome") in {"APPROVED", "STALE", "REVISE", "UNVERIFIABLE"}, "invalid review outcome")
    deferrals = data.get("deferrals", [])
    require(isinstance(deferrals, list) and all(isinstance(d, dict) and bool(d.get("claim")) and bool(d.get("reason")) and d.get("nonblocking") is True for d in deferrals), "deferrals require claim, reason, and nonblocking=true; unmet required acceptance cannot be deferred")
    report = Path(data.get("report", ""))
    require(report.is_absolute(), "review report must reference an existing absolute artifact path")
    root = Path(record["binding"]["repo"])
    for artifact in (path, report):
        require(not artifact.resolve().is_relative_to(root) or artifact.resolve().is_relative_to(Path(record["binding"]["git_dir"])), "review evidence must live outside reviewed repository content")
    item = {"producer": data["producer"], "gate_kind": gate, "outcome": data["outcome"], "deferrals": deferrals,
            "envelope": {"path": str(path), "sha256": file_digest(path)}, "report": {"path": str(report.resolve()), "sha256": file_digest(report)}}
    if gate in {"critic", "final-review"}:
        require(data.get("snapshot") == snapshot_digest(snapshot(record, checker)), "review result snapshot is stale")
        item["snapshot"] = data["snapshot"]
        item["reviewed_docs"] = paths(data.get("reviewed_docs", []))
        item["shape"] = data.get("shape")
        if gate == "critic":
            require(data.get("skill") == "doc-critic", "critic result must explicitly attest invocation of doc-critic")
            item["skill"] = "doc-critic"
        if gate == "final-review":
            require(data.get("evidence_digest") == evidence_digest(record), "final review supporting evidence is stale or missing")
            item["evidence_digest"] = data["evidence_digest"]
            comparisons = data.get("approved_versions")
            require(isinstance(comparisons, list), "final review requires approved_versions comparisons")
            expected = {key: value for key, value in record["results"].items() if "artifact" in value}
            require(len(comparisons) == len(expected) and {value.get("gate_key") for value in comparisons} == set(expected), "final review must compare every approved gate version")
            for comparison in comparisons:
                previous = expected[comparison["gate_key"]]
                require(comparison.get("source") == previous["source"] and comparison.get("approved_sha256") == previous["artifact"]["sha256"] and comparison.get("current_sha256") == file_digest(root / previous["source"]), "final review approved/current version comparison is stale")
                require(comparison.get("scope_preserved") is True and comparison.get("substantive_changes") is False and bool(comparison.get("comparison_reason")), "substantive scope changes require fresh applicable review and approved-version reference")
            item["approved_versions"] = comparisons
        key = gate
    else:
        gate_id = data.get("gate_id")
        expected = prior_artifact(record, gate, gate_id)
        require(bool(expected) and data.get("scope_digest") == record["scope_digest"], "prior review scope/gate binding mismatch")
        artifact = data.get("artifact", {})
        approved = Path(artifact.get("path", ""))
        require(data.get("source") == expected and approved.is_absolute(), "prior review must bind its declared source and absolute approved version")
        require(not approved.resolve().is_relative_to(root) or approved.resolve().is_relative_to(Path(record["binding"]["git_dir"])), "approved version must be retained outside live repository content")
        require(artifact.get("sha256") == file_digest(approved), "prior review approved artifact/version is stale")
        item.update(artifact=artifact, source=expected, scope_digest=data["scope_digest"], gate_id=gate_id)
        key = gate + (":" + gate_id if gate == "milestone-review" else "")
    record["results"][key] = item
    record.pop("finalized", None)
    save(record)
    return key


def completion(record, checker, context_id, phase=None):
    current = snapshot(record, checker)
    digest = snapshot_digest(current)
    final = record.get("finalized", {})
    effective = final.get("before_digest") if final.get("after_digest") == digest else digest
    required_items = required(record)
    if phase == "pre-review":
        required_items = [key for key in required_items if key != "final-review"]
    failures = []
    completed = []
    deferrals = []
    if current["workflows"] != record["workflow_hashes"]:
        failures.append("workflow versions changed; task evidence requires fresh configuration and review")
    for key in required_items:
        value = record["attestations"].get(key) or record["results"].get(key)
        error = None
        if not value:
            error = "missing"
        elif key == "startup":
            if not context_id or context_id != value["context_id"] or not value.get("available"):
                error = "lead knowledge unavailable; personally reload required documents and attest the new context_id"
            else:
                expected = final.get("startup_digest") if final.get("after_digest") == digest else value["digest"]
                if startup_digest(record, checker, value["documents"]) != expected:
                    error = "orientation changed; reload affected documents"
        elif key in {"impact", "reconciliation", "mechanical", "focused", "critic", "final-review"} and value.get("snapshot") != effective:
            error = "stale content snapshot"
        if not error and key in {"mechanical", "focused"}:
            if value.get("exit_status") != 0 or value.get("content_unchanged") is not True:
                error = "actual command failed or changed reviewed content"
        if not error and (key.endswith("review") or key.startswith("milestone-review:") or key == "critic"):
            if value.get("outcome") != "APPROVED":
                error = "outcome " + str(value.get("outcome"))
            for label in ("envelope", "report"):
                ref = value[label]
                try:
                    if file_digest(Path(ref["path"])) != ref["sha256"]:
                        error = f"altered {label} artifact"
                except (OSError, Refusal):
                    error = f"missing {label} artifact"
            if key in {"critic", "final-review"}:
                if not set(record.get("impact", {}).get("affected_docs", [])) <= set(value.get("reviewed_docs", [])):
                    error = "review omits affected documentation"
                if key == "critic" and value.get("shape") != "pass":
                    error = "living-context shape is not verified"
            else:
                artifact = value["artifact"]
                if file_digest(Path(artifact["path"])) != artifact["sha256"]:
                    error = "approved artifact/version changed"
            if key == "final-review":
                if value.get("evidence_digest") != evidence_digest(record):
                    error = "supporting evidence changed after final review"
                for comparison in value.get("approved_versions", []):
                    expected_hash = comparison["current_sha256"]
                    if final.get("after_digest") == digest:
                        expected_hash = final.get("artifacts", {}).get(comparison["source"], expected_hash)
                    if file_digest(Path(record["binding"]["repo"]) / comparison["source"]) != expected_hash:
                        error = "current approved-source comparison changed"
            deferrals.extend(value.get("deferrals", []))
        if error:
            failures.append(key + ": " + error)
        else:
            completed.append(key)
    return {"passed": not failures, "phase": phase or "completion", "snapshot": digest, "evidence_digest": evidence_digest(record), "scope_digest": record["scope_digest"], "required": required_items,
            "completed": completed, "pending": [key for key in required_items if key not in completed], "reasons": failures,
            "deferrals": deferrals, "verification": "qualified" if deferrals else "evidence-consistent", "limit": LIMIT}


def finalize(record, checker, context_id):
    outcome = completion(record, checker, context_id)
    require(outcome["passed"], "completion refused: " + "; ".join(outcome["reasons"]))
    require("critic" in required(record), "fastpath without documentation impact has no baseline finalization")
    root = Path(record["binding"]["repo"])
    before = snapshot(record, checker)
    require(snapshot_digest(before) == outcome["snapshot"], "content changed after completion check")
    if record.get("finalized", {}).get("after_digest") == snapshot_digest(before):
        return {**outcome, "state": "already-finalized"}
    normalized = snapshot(record, checker, True)
    baseline = root / "docs/active-context.md"
    changes = [(baseline, metadata(baseline.read_bytes(), {b"doc_baseline_commit": before["head"].encode(), b"doc_baseline_date": datetime.date.today().isoformat().encode()}))]
    transition = record["config"].get("plan_transition")
    if transition:
        plan = root / transition["path"]
        parsed = checker.read_frontmatter(plan)
        require(parsed is not None and "status" not in parsed[1] and parsed[0].get("status") == "active", "planned status transition requires current status active")
        changes.insert(0, (plan, metadata(plan.read_bytes(), {b"status": b"completed"})))
    original = {str(path): (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) for path, _ in changes}
    for path, _ in changes:
        no_symlinks(path)
        require(os.access(path.parent, os.W_OK | os.X_OK, effective_ids=True), f"finalization cannot publish in directory: {path.parent}")
    require(snapshot(record, checker) == before, "content changed during finalization preflight")
    try:
        for number, (path, data) in enumerate(changes):
            write_bytes(path, data, original[str(path)][1])
            barrier = os.environ.get("MRCALL_DOC_COMPLETION_TEST_BARRIER")
            if barrier and number == 0:
                signal = Path(barrier)
                require(signal.is_absolute() and not signal.resolve().is_relative_to(root), "test barrier must be outside repository content")
                (signal / "published").write_text(str(path))
                with (signal / "continue").open("rb") as handle:
                    handle.read(1)
            require(snapshot(record, checker, True) == normalized, "non-metadata content changed during finalization")
            for published_path, published_data in changes[:number + 1]:
                keys = BASELINE_KEYS if published_path == baseline else {b"status"}
                require(metadata_values(published_path.read_bytes(), keys) == metadata_values(published_data, keys), "metadata changed during finalization")
        after = snapshot(record, checker)
        startup = record["attestations"]["startup"]
        record["finalized"] = {"before_digest": snapshot_digest(before), "after_digest": snapshot_digest(after), "baseline": before["head"],
                               "startup_digest": startup_digest(record, checker, startup["documents"]),
                               "artifacts": {str(path.relative_to(root)): hashed(data) for path, data in changes},
                               "dirty_paths": after["changed_paths"]}
        outcome = completion(record, checker, context_id)
        require(outcome["passed"], "finalization evidence changed: " + "; ".join(outcome["reasons"]))
        require(snapshot(record, checker) == after, "content changed during final evidence validation")
        save(record)
    except Exception as original_error:
        record.pop("finalized", None)
        failures = []
        for path, published in reversed(changes):
            old, _ = original[str(path)]
            try:
                current = path.read_bytes()
                keys = BASELINE_KEYS if path == baseline else {b"status"}
                restored = restore_metadata(current, old, published, keys)
                if restored != current:
                    write_bytes(path, restored, stat.S_IMODE(path.stat().st_mode))
            except (OSError, Refusal) as exc:
                failures.append(f"{path}: {exc}")
        if failures:
            raise Refusal(f"finalization failed: {original_error}; recovery incomplete: {'; '.join(failures)}") from original_error
        raise
    return {**outcome, "state": "finalized", "baseline": before["head"], "dirty_paths": after["changed_paths"], "baseline_meaning": "reviewed ancestor HEAD; dirty working content remains separate"}


def main(args, checker):
    result = {"action": args.completion, "passed": False, "reasons": [], "limit": LIMIT}
    try:
        root = checker.repo_root(args.repo)
        binding = identity(root, args.task)
        data = json.loads(Path(args.input).read_text()) if args.input else {}
        require(isinstance(data, dict), "completion input must be a JSON object")
        if args.completion not in {"recover", "check"}:
            _, profile_errors, _ = checker.read_profile(root)
            require(not profile_errors, "profile preflight refused: " + "; ".join(profile_errors))
        mutation = args.completion in {"init", "attest", "mechanical", "focused", "result", "finalize"}
        if args.completion == "init":
            require(data.get("kind") in {"documentation", "development", "fastpath"}, "only authorized documentation/development/fastpath mutations may create records")
            committed_head(root)
        with task_mutation_lock(binding) if mutation else contextlib.nullcontext():
            if args.completion == "init":
                record = init(binding, data, checker)
                result.update(passed=True, state="initialized", scope_digest=record["scope_digest"], required=required(record))
            else:
                record = load(binding)
                if args.completion == "attest":
                    attestation(record, data, checker)
                    result.update(passed=True, state="attested", obligation=data["obligation"])
                elif args.completion == "snapshot":
                    current = snapshot(record, checker)
                    result.update(passed=True, snapshot=snapshot_digest(current), evidence_digest=evidence_digest(record), scope_digest=record["scope_digest"], binding=binding, changed_paths=current["changed_paths"])
                elif args.completion in {"mechanical", "focused"}:
                    value = run_check(record, args.completion, data, checker)
                    result.update(passed=value["exit_status"] == 0 and value["content_unchanged"], command=value)
                elif args.completion == "result":
                    require(bool(args.input), "result requires --input review envelope")
                    result.update(passed=True, recorded=register_result(record, args.input, checker))
                elif args.completion in {"check", "recover"}:
                    result.update(completion(record, checker, args.context_id, args.phase))
                    if args.completion == "recover":
                        result["recovery"] = "Only this task was loaded. Records cannot restore unavailable lead knowledge; reload and attest a new context_id after context loss."
                elif args.completion == "finalize":
                    result.update(finalize(record, checker, args.context_id))
        result["record"] = str(record_path(binding))
    except (Refusal, OSError, ValueError, KeyError, TypeError) as exc:
        result["passed"] = False
        result["reasons"].append(str(exc))
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("doc-check: COMPLETION " + ("PASS" if result["passed"] else "REFUSED"))
        for key, value in result.items():
            if key != "passed":
                print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    return 0 if result["passed"] else 1
