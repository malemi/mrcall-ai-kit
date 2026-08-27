/** OpenCode 1.x scope-guard plugin. OpenCode 2's beta plugin API is unsupported. */
import type { Plugin } from "@opencode-ai/plugin"
import { spawnSync } from "node:child_process"
import { existsSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const BRIDGE = String.raw`
import importlib.util, json, sys
from pathlib import Path

core_path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("mrcall_scope_guard", core_path)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load scope-guard core")
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)
request = json.load(sys.stdin)
operation = request.get("operation", "decide")
if operation == "close":
    core.close_session("opencode", request["session_id"])
    print("{}")
    raise SystemExit(0)
tool = request["tool"]
args = request["args"]
cwd = Path(request["cwd"])
session = request["session_id"]
turn = request.get("turn_id", "")
if tool == "write":
    path = core.canonical_path(args.get("filePath", args.get("file_path", "")), cwd)
    content = args.get("content")
    if not isinstance(content, str):
        raise core.ScopeGuardError("write payload has no string content")
    mutations = [core.Mutation(path, "write", content)]
elif tool == "edit":
    path = core.canonical_path(args.get("filePath", args.get("file_path", "")), cwd)
    preimage = path.read_text(encoding="utf-8")
    old = args.get("oldString", args.get("old_string"))
    new = args.get("newString", args.get("new_string"))
    if not isinstance(old, str) or not isinstance(new, str):
        raise core.ScopeGuardError("edit payload needs string oldString and newString")
    postimage = core.apply_edit(preimage, old, new, args.get("replaceAll", args.get("replace_all")) is True)
    mutations = [core.Mutation(path, "edit", postimage)]
elif tool == "apply_patch":
    patch = args.get("patchText", args.get("patch", ""))
    if not isinstance(patch, str) or not patch:
        raise core.ScopeGuardError("apply_patch payload has no patchText")
    mutations = core.parse_apply_patch(patch, cwd)
else:
    print("{}")
    raise SystemExit(0)
decisions = [core.decide("opencode", session, mutation, full_attestation=False, turn_id=turn) for mutation in mutations]
protected = [decision for decision in decisions if decision.action != "ignore"]
denied = [decision for decision in protected if decision.action == "deny"]
selected = denied or protected
print(json.dumps({
    "action": "deny" if denied else ("allow" if protected else "ignore"),
    "message": "\n\n".join(decision.message for decision in selected if decision.message),
    "context": "\n\n".join(dict.fromkeys(decision.context for decision in protected if decision.context)),
}, separators=(",", ":")))
`

type BridgeResult = { action?: "ignore" | "allow" | "deny"; message?: string; context?: string }

function corePath(): string {
  if (process.env.MRCALL_SCOPE_GUARD_CORE) return process.env.MRCALL_SCOPE_GUARD_CORE
  const here = dirname(fileURLToPath(import.meta.url))
  const installed = resolve(here, "..", "scope_guard.py")
  const repository = resolve(here, "..", "..", "shared", "scripts", "scope_guard.py")
  return existsSync(installed) ? installed : repository
}

function runBridge(request: Record<string, unknown>): BridgeResult {
  const child = spawnSync("python3", ["-c", BRIDGE, corePath()], {
    input: JSON.stringify(request),
    encoding: "utf8",
  })
  if (child.status !== 0) {
    const detail = child.stderr.trim() || child.error?.message || `python bridge exited ${child.status}`
    throw new Error(`Scope guard failed closed: ${detail}`)
  }
  return JSON.parse(child.stdout || "{}") as BridgeResult
}

export const ScopeGuardPlugin: Plugin = async ({ directory }) => ({
  "tool.execute.before": async (input, output) => {
    if (!new Set(["write", "edit", "apply_patch"]).has(input.tool)) return
    const sessionID = (input as { sessionID?: string }).sessionID
    const identifiers = input as { messageID?: string; callID?: string }
    if (!sessionID) throw new Error("Scope guard failed closed: OpenCode supplied no sessionID")
    const decision = runBridge({
      tool: input.tool,
      args: output.args,
      cwd: directory,
      session_id: sessionID,
      // v1.17 supplies callID but not an assistant message ID. A new call is the
      // strongest stable proxy the v1 before-hook exposes for an intervening turn.
      turn_id: identifiers.messageID || identifiers.callID || "",
    })
    if (decision.action === "deny") throw new Error(decision.message || "Scope guard denied this mutation")
    // Stable OpenCode v1 has no supported before-hook field for injecting model
    // context on an allowed call. The first denial remains in conversation context.
  },
  event: async ({ event }) => {
    if (event.type !== "session.deleted") return
    const properties = (event as { properties?: { info?: { id?: string }; sessionID?: string } }).properties
    const sessionID = properties?.sessionID || properties?.info?.id
    if (sessionID) runBridge({ operation: "close", session_id: sessionID })
  },
})
