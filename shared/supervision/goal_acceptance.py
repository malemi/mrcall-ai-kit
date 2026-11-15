import datetime
import hashlib
import json
import math
import os
import pathlib
import shutil
import stat
import uuid

from goal_child import protected_path, run_child


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def directory_fd(path):
    path = pathlib.Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("input root must be absolute without parent traversal")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def root_identity(path):
    fd = directory_fd(path)
    try:
        info = os.fstat(fd)
        return {"device": info.st_dev, "inode": info.st_ino}
    finally:
        os.close(fd)


def executable_identity(path):
    resolved = protected_path(os.path.realpath(path), directory=False)
    return {"path": str(resolved), "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest()}


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode)


def tree_read(fd, destination=None):
    manifest = {}
    total = 0

    def visit(directory, prefix, target):
        nonlocal total
        before = os.fstat(directory)
        names = sorted(os.listdir(directory))
        for name in names:
            relative = f"{prefix}/{name}" if prefix else name
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                try:
                    if fingerprint(os.fstat(child)) != fingerprint(info):
                        raise ValueError("input directory changed during snapshot")
                    child_target = None if target is None else target / name
                    if child_target is not None:
                        child_target.mkdir(mode=0o700)
                    visit(child, relative, child_target)
                    if child_target is not None:
                        child_target.chmod(0o555)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                if len(manifest) >= 10000 or info.st_size > 67108864 or total + info.st_size > 268435456:
                    raise ValueError("input snapshot exceeds file or byte bound")
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
                try:
                    if fingerprint(os.fstat(child)) != fingerprint(info):
                        raise ValueError("input file replaced during snapshot")
                    chunks = []
                    length = 0
                    while True:
                        chunk = os.read(child, 1048576)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        length += len(chunk)
                        if length > info.st_size:
                            raise ValueError("input grew during snapshot")
                    content = b"".join(chunks)
                    if fingerprint(os.fstat(child)) != fingerprint(info) or fingerprint(os.stat(name, dir_fd=directory, follow_symlinks=False)) != fingerprint(info):
                        raise ValueError("input changed during snapshot")
                finally:
                    os.close(child)
                total += len(content)
                manifest[relative] = hashlib.sha256(content).hexdigest()
                if target is not None:
                    output = target / name
                    output.write_bytes(content)
                    output.chmod(0o555 if info.st_mode & 0o111 else 0o444)
            else:
                raise ValueError("input trees must contain only regular files and directories")
        if fingerprint(os.fstat(directory)) != fingerprint(before) or sorted(os.listdir(directory)) != names:
            raise ValueError("input tree changed during snapshot")

    visit(fd, "", destination)
    return manifest


def snapshot(source, destination, expected=None):
    fd = directory_fd(source)
    destination = pathlib.Path(destination)
    destination.mkdir(mode=0o700)
    try:
        manifest = tree_read(fd, destination)
        if tree_read(fd) != manifest:
            raise ValueError("input contents changed during snapshot")
        if expected is not None and manifest != expected:
            raise ValueError("checker manifest mismatch")
        destination.chmod(0o555)
        return manifest
    except BaseException:
        shutil.rmtree(destination)
        raise
    finally:
        os.close(fd)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate checker result field")
        result[key] = value
    return result


def expand(argv, paths):
    result = []
    for value in argv:
        for key, path in paths.items():
            value = value.replace("{" + key + "}", str(path))
        result.append(value)
    return result


class Acceptance:
    def __init__(self, config):
        self.config = config
        self.root = pathlib.Path(config["root"])

    def bind(self, contract):
        required = {"version", "candidate_root", "candidate_argv", "checker_root", "checker_manifest", "checker_argv", "timeout_seconds"}
        if not isinstance(contract, dict) or not required <= contract.keys() or contract.keys() - required - {"env"}:
            raise ValueError("invalid acceptance contract fields")
        if contract["version"] != 1:
            raise ValueError("unsupported acceptance version")
        for key in ("candidate_root", "checker_root"):
            value = contract[key]
            if not isinstance(value, str) or not os.path.isabs(value) or ".." in pathlib.Path(value).parts or "\0" in value:
                raise ValueError("invalid acceptance input root")
        for key in ("candidate_argv", "checker_argv"):
            argv = contract[key]
            if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and "\0" not in arg for arg in argv) or not os.path.isabs(argv[0]):
                raise ValueError("acceptance commands require absolute executable argv")
        checker = contract["checker_argv"]
        manifest = contract["checker_manifest"]
        if not isinstance(manifest, dict) or not manifest:
            raise ValueError("checker manifest must declare files")
        for path, checksum in manifest.items():
            relative = pathlib.PurePosixPath(path)
            if relative.is_absolute() or ".." in relative.parts or str(relative) != path or not path or not isinstance(checksum, str) or len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
                raise ValueError("invalid checker manifest")
        if len(checker) < 3 or checker[:2] != ["/usr/bin/python3", "-I"] or not checker[2].startswith("{checker}/") or checker[2][len("{checker}/"):] not in manifest:
            raise ValueError("checker must execute a pinned Python script with /usr/bin/python3 -I")
        timeout = contract["timeout_seconds"]
        if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
            raise ValueError("invalid acceptance timeout")
        env = contract.get("env", {})
        if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) and k and "=" not in k and "\0" not in k + v for k, v in env.items()):
            raise ValueError("invalid acceptance environment")
        bundle = self.root / "acceptance" / str(uuid.uuid4())
        copied = snapshot(contract["checker_root"], bundle, manifest)
        result = dict(contract)
        result.update(bundle_path=str(bundle), bundle_digest=digest(copied), executables={key: executable_identity(contract[key][0]) for key in ("candidate_argv", "checker_argv")})
        return result

    def run(self, goal, admission=None):
        receipt = {"id": str(uuid.uuid4()), "goal_id": goal["id"], "generation": goal["generation"], "acceptance_digest": goal["acceptance_digest"], "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "passed": False}
        run = self.root / "runs" / receipt["id"]
        run.mkdir(mode=0o755)
        run.chmod(0o755)
        receipt["run_path"] = str(run)
        try:
            bound = goal["acceptance"]
            if digest(bound) != goal["acceptance_digest"]:
                raise ValueError("bound acceptance digest mismatch")
            bundle = protected_path(bound["bundle_path"], directory=True)
            if bundle.parent != self.root / "acceptance":
                raise ValueError("checker bundle outside protected acceptance store")
            checker_manifest = snapshot(bundle, run / "checker", bound["checker_manifest"])
            if digest(checker_manifest) != bound["bundle_digest"]:
                raise ValueError("checker bundle digest mismatch")
            source_identity = root_identity(bound["candidate_root"])
            manifest = snapshot(bound["candidate_root"], run / "candidate")
            receipt["candidate_source_identity"] = source_identity
            for key, identity in bound["executables"].items():
                if executable_identity(bound[key][0]) != identity:
                    raise ValueError("bound executable identity changed")
            receipt.update(candidate_manifest=manifest, candidate_digest=digest(manifest), checker_bundle_digest=bound["bundle_digest"])
            scratch = run / "scratch"
            scratch.mkdir(mode=0o700)
            os.chown(scratch, self.config["agent_uid"], self.config["agent_gid"])
            result_path = run / "candidate-result.json"
            paths = {"candidate": run / "candidate", "checker": run / "checker", "result": result_path, "scratch": scratch}
            timeout = min(bound["timeout_seconds"], goal["limits"]["process_timeout_seconds"])
            result = run_child(expand(bound["candidate_argv"], paths), uid=self.config["agent_uid"], gid=self.config["agent_gid"], home=self.config["agent_home"], cwd=scratch, timeout=timeout, env=bound.get("env", {}), admission=admission)
            receipt["candidate_result"] = result
            result_path.write_bytes(canonical(result) + b"\n")
            result_path.chmod(0o444)
            verifier = run_child(expand(bound["checker_argv"], paths), uid=self.config["verifier_uid"], gid=self.config["verifier_gid"], home=self.config["verifier_home"], cwd=run / "checker", timeout=timeout, admission=admission)
            receipt["verifier_result"] = verifier
            try:
                assessment = json.loads(verifier["stdout"], object_pairs_hook=strict_object)
            except (ValueError, TypeError) as error:
                raise ValueError("checker output is not structured JSON") from error
            if not isinstance(assessment, dict) or set(assessment) != {"passed"} or type(assessment["passed"]) is not bool:
                raise ValueError("checker output must contain exactly a boolean passed field")
            current_fd = directory_fd(bound["candidate_root"])
            try:
                current_info = os.fstat(current_fd)
                current_identity = {"device": current_info.st_dev, "inode": current_info.st_ino}
                current_manifest = tree_read(current_fd)
                if tree_read(current_fd) != current_manifest:
                    raise ValueError("candidate source changed during final validation")
            finally:
                os.close(current_fd)
            receipt["current_candidate_manifest"] = current_manifest
            receipt["current_candidate_source_identity"] = current_identity
            if current_identity != source_identity or root_identity(bound["candidate_root"]) != source_identity or current_manifest != manifest:
                raise ValueError("candidate source changed while acceptance was running")
            for key, identity in bound["executables"].items():
                if executable_identity(bound[key][0]) != identity:
                    raise ValueError("bound executable identity changed during acceptance")
            receipt["passed"] = result["exit_code"] == 0 and result["termination"] is None and verifier["exit_code"] == 0 and verifier["termination"] is None and assessment["passed"]
            diagnostic = "Acceptance passed" if receipt["passed"] else "Acceptance failed: " + canonical({"candidate": result, "verifier": verifier}).decode()
        except Exception as error:
            diagnostic = "Acceptance unavailable: " + str(error)
        diagnostic = diagnostic[:16384]
        receipt["diagnostic"] = diagnostic
        evidence = self.root / "evidence" / (receipt["id"] + ".json")
        evidence.write_bytes(canonical(receipt) + b"\n")
        evidence.chmod(0o400)
        return {"passed": receipt["passed"], "receipt": receipt, "diagnostic": diagnostic}
