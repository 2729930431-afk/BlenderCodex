const fs = require("fs");
const net = require("net");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const childProcess = require("child_process");
const readline = require("readline");

const pluginRoot = path.resolve(__dirname, "..");
const bridgeScript = path.join(pluginRoot, "scripts", "blendercodex_bridge.py");
const humanoidRuntimeScript = path.join(
  pluginRoot,
  "skills",
  "humanoid-rigging",
  "scripts",
  "humanoid_rig_runtime.py",
);
function codexHome() {
  return process.env.CODEX_HOME || path.join(os.homedir(), ".codex");
}

function sessionFileFor(name = "default") {
  const safe = String(name || "default").replace(/[^a-zA-Z0-9_-]/g, "_") || "default";
  return path.join(codexHome(), "blendercodex", `bridge_session_${safe}.json`);
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function candidateBlenderPaths() {
  const candidates = [];
  const envPaths = [
    process.env.BLENDER_PATH,
    process.env.BLENDER_EXE,
  ].filter(Boolean);
  candidates.push(...envPaths);

  const pathEntries = String(process.env.PATH || "").split(path.delimiter).filter(Boolean);
  for (const entry of pathEntries) {
    candidates.push(path.join(entry, process.platform === "win32" ? "blender.exe" : "blender"));
  }

  if (process.platform === "win32") {
    const roots = [
      process.env.ProgramFiles,
      process.env["ProgramFiles(x86)"],
      process.env.LOCALAPPDATA,
    ].filter(Boolean);
    for (const root of roots) {
      const foundation = path.join(root, "Blender Foundation");
      if (!fs.existsSync(foundation)) {
        continue;
      }
      for (const entry of fs.readdirSync(foundation, { withFileTypes: true })) {
        if (entry.isDirectory()) {
          candidates.push(path.join(foundation, entry.name, "blender.exe"));
        }
      }
    }
  }

  return candidates;
}

function resolveExecutable(rawPath) {
  if (!rawPath) {
    return null;
  }
  const expanded = String(rawPath).replace(/^~(?=$|[\\/])/, os.homedir());
  const direct = path.resolve(expanded);
  const asDirectory = path.join(direct, process.platform === "win32" ? "blender.exe" : "blender");
  if (fs.existsSync(direct) && fs.statSync(direct).isFile()) {
    return direct;
  }
  if (fs.existsSync(asDirectory) && fs.statSync(asDirectory).isFile()) {
    return asDirectory;
  }
  return null;
}

function findBlender(args = {}) {
  const explicit = resolveExecutable(args.blenderPath);
  if (explicit) {
    return { path: explicit, source: "argument" };
  }
  const configPath = path.join(codexHome(), "blendercodex", "config.json");
  if (fs.existsSync(configPath)) {
    const config = readJson(configPath);
    const cached = resolveExecutable(config.path);
    if (cached) {
      return { ...config, path: cached };
    }
  }

  for (const candidate of candidateBlenderPaths()) {
    const resolved = resolveExecutable(candidate);
    if (resolved) {
      return { path: resolved, source: "node-search" };
    }
  }

  throw new Error("Blender executable not found. Pass blenderPath or set BLENDER_PATH.");
}

function waitForFile(file, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (fs.existsSync(file)) {
      return true;
    }
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
  }
  return false;
}

function shouldUseKeepAlive(args = {}) {
  return Boolean(args.keepAlive && args.background);
}

function splitCommandLine(commandLine) {
  const args = [];
  let current = "";
  let inQuotes = false;
  for (let index = 0; index < String(commandLine || "").length; index += 1) {
    const char = commandLine[index];
    if (char === "\"") {
      inQuotes = !inQuotes;
      continue;
    }
    if (/\s/.test(char) && !inQuotes) {
      if (current) {
        args.push(current);
        current = "";
      }
      continue;
    }
    current += char;
  }
  if (current) {
    args.push(current);
  }
  return args;
}

function blendFileFromArgs(args) {
  for (const arg of args.slice(1)) {
    if (arg === "--") {
      break;
    }
    if (/\.blend$/i.test(arg)) {
      return path.resolve(arg);
    }
  }
  return null;
}

function mockedBlenderProcesses() {
  const raw = process.env.BLENDERCODEX_TEST_OPEN_BLEND_PROCESSES;
  if (!raw) {
    return null;
  }
  const parsed = JSON.parse(raw);
  return parsed.map((item, index) => {
    if (typeof item === "string") {
      return { pid: index + 1, commandLine: item };
    }
    return item;
  });
}

function runningBlenderProcesses() {
  const mocked = mockedBlenderProcesses();
  if (mocked) {
    return mocked;
  }
  if (process.platform === "win32") {
    const script = [
      "$items = Get-CimInstance Win32_Process -Filter \"name = 'blender.exe'\" | Select-Object ProcessId,CommandLine",
      "if ($null -eq $items) { '[]' } else { $items | ConvertTo-Json -Compress }",
    ].join("; ");
    const result = childProcess.spawnSync(
      "powershell.exe",
      ["-NoProfile", "-NonInteractive", "-Command", script],
      { encoding: "utf8", timeout: 5000, windowsHide: true },
    );
    if (result.status !== 0) {
      return [];
    }
    const output = String(result.stdout || "").trim();
    if (!output) {
      return [];
    }
    const parsed = JSON.parse(output);
    const rows = Array.isArray(parsed) ? parsed : [parsed];
    return rows.map((row) => ({ pid: row.ProcessId, commandLine: row.CommandLine || "" }));
  }

  if (process.platform === "linux" && fs.existsSync("/proc")) {
    const processes = [];
    for (const entry of fs.readdirSync("/proc", { withFileTypes: true })) {
      if (!entry.isDirectory() || !/^\d+$/.test(entry.name)) {
        continue;
      }
      try {
        const raw = fs.readFileSync(path.join("/proc", entry.name, "cmdline"), "utf8");
        const args = raw.split("\0").filter(Boolean);
        if (args.length && path.basename(args[0]).toLowerCase().startsWith("blender")) {
          processes.push({ pid: Number(entry.name), args, commandLine: args.join(" ") });
        }
      } catch (_) {}
    }
    return processes;
  }

  const result = childProcess.spawnSync("ps", ["-axo", "pid=,command="], {
    encoding: "utf8",
    timeout: 5000,
    windowsHide: true,
  });
  if (result.status !== 0) {
    return [];
  }
  return String(result.stdout || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => /\bblender(?:\.exe)?\b/i.test(line))
    .map((line) => {
      const match = line.match(/^(\d+)\s+(.*)$/);
      return match ? { pid: Number(match[1]), commandLine: match[2] } : null;
    })
    .filter(Boolean);
}

function inferOpenBlendFile() {
  const found = [];
  for (const processInfo of runningBlenderProcesses()) {
    const args = Array.isArray(processInfo.args) ? processInfo.args : splitCommandLine(processInfo.commandLine || "");
    const blendFile = blendFileFromArgs(args);
    if (!blendFile || !fs.existsSync(blendFile)) {
      continue;
    }
    found.push({ pid: processInfo.pid, blendFile });
  }

  const unique = new Map();
  for (const item of found) {
    const key = process.platform === "win32" ? item.blendFile.toLowerCase() : item.blendFile;
    if (!unique.has(key)) {
      unique.set(key, { blendFile: item.blendFile, pids: [] });
    }
    unique.get(key).pids.push(item.pid);
  }

  const projects = [...unique.values()];
  if (projects.length === 1) {
    return projects[0].blendFile;
  }
  if (projects.length > 1) {
    throw new Error(
      [
        "Multiple open Blender projects were detected. Pass blendFile explicitly.",
        ...projects.map((item) => `- ${item.blendFile} (pid: ${item.pids.join(", ")})`),
      ].join("\n"),
    );
  }
  return null;
}

function callBridge(method, params = {}, options = {}) {
  const sessionFile = options.sessionFile || sessionFileFor(options.sessionName);
  if (!fs.existsSync(sessionFile)) {
    throw new Error(`Bridge session file not found: ${sessionFile}. Start Blender with blendercodex_start_bridge first.`);
  }
  const session = readJson(sessionFile);
  const timeoutMs = Math.max(1000, Number(options.timeoutMs || 30000));
  const request = {
    id: crypto.randomUUID(),
    token: session.token,
    method,
    params,
    timeoutSeconds: Math.ceil(timeoutMs / 1000),
  };

  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host: session.host, port: session.port });
    let buffer = "";
    const timer = setTimeout(() => {
      socket.destroy();
      reject(new Error(`Bridge call timed out: ${method}`));
    }, timeoutMs + 1000);

    socket.setEncoding("utf8");
    socket.on("connect", () => {
      socket.write(`${JSON.stringify(request)}\n`, "utf8");
    });
    socket.on("data", (chunk) => {
      buffer += chunk;
      const newline = buffer.indexOf("\n");
      if (newline < 0) {
        return;
      }
      clearTimeout(timer);
      const line = buffer.slice(0, newline);
      socket.end();
      try {
        const response = JSON.parse(line);
        if (!response.ok) {
          reject(new Error(response.error || "Bridge call failed"));
        } else {
          resolve(response.result);
        }
      } catch (error) {
        reject(error);
      }
    });
    socket.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
  });
}

async function startBridge(args = {}) {
  if (!fs.existsSync(bridgeScript)) {
    throw new Error(`Bridge script not found: ${bridgeScript}`);
  }
  const blender = findBlender(args);
  const sessionName = args.sessionName || "default";
  const sessionFile = args.sessionFile ? path.resolve(String(args.sessionFile)) : sessionFileFor(sessionName);
  fs.mkdirSync(path.dirname(sessionFile), { recursive: true });
  try {
    fs.rmSync(sessionFile, { force: true });
  } catch (_) {}

  const bridgeArgs = [];
  if (args.background) {
    bridgeArgs.push("--factory-startup", "-b");
  }
  let blendFile = args.blendFile ? path.resolve(String(args.blendFile)) : null;
  if (!blendFile && !args.background) {
    blendFile = inferOpenBlendFile();
    if (!blendFile) {
      throw new Error("No .blend file was provided and no currently open Blender project could be inferred. Pass blendFile explicitly.");
    }
  }
  if (blendFile) {
    bridgeArgs.push(blendFile);
  }
  bridgeArgs.push("--python", bridgeScript, "--", "--session-file", sessionFile, "--session-name", String(sessionName));
  if (shouldUseKeepAlive(args)) {
    bridgeArgs.push("--keep-alive");
  }
  if (args.port) {
    bridgeArgs.push("--port", String(args.port));
  }
  if (args.host) {
    bridgeArgs.push("--host", String(args.host));
  }

  const child = childProcess.spawn(blender.path, bridgeArgs, {
    cwd: pluginRoot,
    detached: true,
    stdio: "ignore",
    windowsHide: false,
  });
  child.unref();

  const waitMs = Math.max(1000, Number(args.waitMs || 15000));
  if (!waitForFile(sessionFile, waitMs)) {
    throw new Error(`Bridge did not create a session file within ${waitMs} ms: ${sessionFile}`);
  }
  const ping = await callBridge("ping", {}, { sessionFile, timeoutMs: 5000 });
  return {
    started: true,
    blender,
    pid: child.pid,
    sessionFile,
    blendFile,
    ping,
  };
}

function pruneCollectionCode(target, keep) {
  return `
import bpy

target_name = ${JSON.stringify(target)}
keep_names = set(${JSON.stringify(keep)})
target = bpy.data.collections.get(target_name)
if target is None:
    raise ValueError(f"Target collection not found: {target_name}")

def walk_collection_objects(collection):
    objects = set(collection.objects)
    for child in collection.children:
        objects.update(walk_collection_objects(child))
    return objects

def walk_collection_tree(collection):
    collections = [collection]
    for child in collection.children:
        collections.extend(walk_collection_tree(child))
    return collections

protected_collections = set()
for child in target.children:
    if child.name in keep_names:
        protected_collections.update(walk_collection_tree(child))

def object_in_protected(obj):
    return any(collection in protected_collections for collection in obj.users_collection)

deleted_collections = []
deleted_objects = []
unlinked_objects = []
for child in sorted(list(target.children), key=lambda item: item.name):
    if child.name in keep_names:
        continue
    branch_collections = set(walk_collection_tree(child))
    for obj in sorted(walk_collection_objects(child), key=lambda item: item.name):
        if object_in_protected(obj):
            for user_collection in list(obj.users_collection):
                if user_collection in branch_collections:
                    user_collection.objects.unlink(obj)
            unlinked_objects.append(obj.name)
        else:
            deleted_objects.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in sorted(walk_collection_tree(child), key=lambda item: item.name, reverse=True):
        deleted_collections.append(collection.name)
        bpy.data.collections.remove(collection)

for obj in sorted(list(target.objects), key=lambda item: item.name):
    if obj.name in keep_names:
        continue
    if object_in_protected(obj):
        target.objects.unlink(obj)
        unlinked_objects.append(obj.name)
    else:
        deleted_objects.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)

bpy.context.view_layer.update()
RESULT = {
    "target": target_name,
    "keep": sorted(keep_names),
    "deleted_collections": deleted_collections,
    "deleted_objects": deleted_objects,
    "unlinked_shared_objects": unlinked_objects,
    "remaining_children": sorted(child.name for child in target.children),
    "remaining_objects": sorted(obj.name for obj in target.objects),
}
`;
}

function humanoidRuntimeCode(action, args) {
  if (!fs.existsSync(humanoidRuntimeScript)) {
    throw new Error(`Humanoid rig runtime not found: ${humanoidRuntimeScript}`);
  }
  const runtimeArgs = { ...args };
  delete runtimeArgs.sessionName;
  delete runtimeArgs.sessionFile;
  delete runtimeArgs.timeoutMs;
  return [
    "import json as _blendercodex_json",
    `ACTION = ${JSON.stringify(String(action))}`,
    `PARAMS = _blendercodex_json.loads(${JSON.stringify(JSON.stringify(runtimeArgs))})`,
    `__file__ = ${JSON.stringify(humanoidRuntimeScript)}`,
    "with open(__file__, 'rb') as _blendercodex_runtime_file:",
    "    exec(compile(_blendercodex_runtime_file.read(), __file__, 'exec'), globals(), globals())",
  ].join("\n");
}

function toolResult(text, isError = false) {
  return {
    content: [{ type: "text", text: typeof text === "string" ? text : JSON.stringify(text, null, 2) }],
    isError,
  };
}

const tools = [
  {
    name: "blendercodex_start_bridge",
    description: "Start Blender with the temporary BlenderCodex RPC bridge for this Blender process only. This does not install a Blender add-on.",
    inputSchema: {
      type: "object",
      properties: {
        blendFile: { type: "string", description: "Optional .blend file to open in the bridged Blender UI. If omitted for visible bridge startup, the tool infers the user's currently open Blender project." },
        blenderPath: { type: "string", description: "Optional explicit blender.exe path." },
        sessionName: { type: "string", description: "Optional session name. Defaults to default." },
        sessionFile: { type: "string", description: "Optional explicit session JSON path." },
        waitMs: { type: "number", description: "How long to wait for the bridge session file." },
        background: { type: "boolean", description: "Start Blender in background mode. Intended for tests and automation." },
        keepAlive: { type: "boolean", description: "Keep background Blender alive for bridge calls. Only applies when background is true; visible UI bridge launches ignore it." },
      },
    },
  },
  {
    name: "blendercodex_bridge_ping",
    description: "Check whether the temporary BlenderCodex RPC bridge is reachable.",
    inputSchema: { type: "object", properties: { sessionName: { type: "string" }, sessionFile: { type: "string" } } },
  },
  {
    name: "blendercodex_scene_summary",
    description: "Return a live summary of the bridged Blender scene.",
    inputSchema: { type: "object", properties: { sessionName: { type: "string" }, sessionFile: { type: "string" } } },
  },
  {
    name: "blendercodex_run_python",
    description: "Run Blender Python in the live bridged Blender process. Set RESULT in the code to return structured data.",
    inputSchema: {
      type: "object",
      properties: {
        code: { type: "string" },
        sessionName: { type: "string" },
        sessionFile: { type: "string" },
        timeoutMs: { type: "number" },
      },
      required: ["code"],
    },
  },
  {
    name: "blendercodex_save",
    description: "Save the live bridged Blender file, optionally to a new filepath.",
    inputSchema: {
      type: "object",
      properties: {
        filepath: { type: "string" },
        sessionName: { type: "string" },
        sessionFile: { type: "string" },
        timeoutMs: { type: "number" },
      },
    },
  },
  {
    name: "blendercodex_open_file",
    description: "Open a .blend file in the live bridged Blender process.",
    inputSchema: {
      type: "object",
      properties: {
        filepath: { type: "string" },
        sessionName: { type: "string" },
        sessionFile: { type: "string" },
        timeoutMs: { type: "number" },
      },
      required: ["filepath"],
    },
  },
  {
    name: "blendercodex_shutdown_bridge",
    description: "Stop the temporary bridge for this Blender process. This does not close Blender; it only removes the temporary RPC listener.",
    inputSchema: {
      type: "object",
      properties: {
        sessionName: { type: "string" },
        sessionFile: { type: "string" },
        timeoutMs: { type: "number" },
      },
    },
  },
  {
    name: "blendercodex_prune_collection",
    description: "In the live bridged Blender scene, delete everything directly under a collection except named direct child collections or objects.",
    inputSchema: {
      type: "object",
      properties: {
        target: { type: "string" },
        keep: { type: "array", items: { type: "string" } },
        save: { type: "boolean" },
        sessionName: { type: "string" },
        sessionFile: { type: "string" },
        timeoutMs: { type: "number" },
      },
      required: ["target", "keep"],
    },
  },
  {
    name: "blendercodex_humanoid_analyze",
    description: "Analyze explicit or selected humanoid mesh objects, classify pose/confidence, and create semantic joint empties only. This does not create an armature, bind meshes, or save the file.",
    inputSchema: {
      type: "object",
      properties: {
        targetObjects: { type: "array", items: { type: "string" }, description: "Explicit mesh object names. If omitted, selected mesh objects are used." },
        targetCollection: { type: "string", description: "Alternative collection whose recursive mesh objects are the target." },
        excludeObjects: { type: "array", items: { type: "string" }, description: "Mesh names to exclude, such as hair or accessories." },
        armatureHint: { type: "string", description: "Optional existing armature used as high-confidence landmark evidence." },
        useExistingRigEvidence: { type: "boolean", description: "Use a compatible existing rig as landmark evidence. Defaults to true." },
        markerCollection: { type: "string", description: "Pending marker collection name." },
        createMarkers: { type: "boolean", description: "Create marker empties. Defaults to true." },
        replaceMarkers: { type: "boolean", description: "Explicitly discard and regenerate semantic markers. Defaults to false to preserve user edits." },
        includeFingers: { type: "boolean", description: "Create finger markers only when an existing compatible rig provides them." },
        maxPoints: { type: "number", description: "Maximum evaluated geometry samples." },
        priorPath: { type: "string", description: "Optional override for the heroine body-prior JSON." },
        sessionName: { type: "string" },
        sessionFile: { type: "string" },
        timeoutMs: { type: "number" },
      },
    },
  },
  {
    name: "blendercodex_humanoid_fit_standard",
    description: "After explicit marker approval, append the authoritative female humanoid Armature asset and fit it to the live semantic markers. This does not bind meshes or save the file.",
    inputSchema: {
      type: "object",
      properties: {
        confirmed: { type: "boolean", description: "Must be true only after the user explicitly confirms the current marker positions." },
        markerCollection: { type: "string" },
        previewName: { type: "string" },
        replacePreview: { type: "boolean" },
        allowLowConfidence: { type: "boolean", description: "Explicit override after manual marker review." },
        assetPath: { type: "string" },
        priorPath: { type: "string" },
        sessionName: { type: "string" },
        sessionFile: { type: "string" },
        timeoutMs: { type: "number" },
      },
      required: ["confirmed"],
    },
  },
  {
    name: "blendercodex_humanoid_validate",
    description: "Validate a fitted humanoid preview against the authoritative bone set, marker positions, constraints, excluded hair bones, and the unchanged target signature.",
    inputSchema: {
      type: "object",
      properties: {
        rigObject: { type: "string" },
        markerCollection: { type: "string" },
        sessionName: { type: "string" },
        sessionFile: { type: "string" },
        timeoutMs: { type: "number" },
      },
    },
  },
  {
    name: "blendercodex_humanoid_bind_preview",
    description: "After separate binding approval, create duplicate-safe skinned mesh previews using compatible existing groups or Blender automatic weights. Originals are not modified and the file is not saved.",
    inputSchema: {
      type: "object",
      properties: {
        confirmed: { type: "boolean", description: "Must be true only after the user explicitly confirms the fitted armature." },
        rigObject: { type: "string" },
        markerCollection: { type: "string" },
        method: { type: "string", enum: ["existing_groups", "automatic"], description: "Weight source for the duplicate preview." },
        previewCollection: { type: "string" },
        replacePreview: { type: "boolean" },
        sessionName: { type: "string" },
        sessionFile: { type: "string" },
        timeoutMs: { type: "number" },
      },
      required: ["confirmed"],
    },
  },
];

async function callTool(name, args = {}) {
  if (name === "blendercodex_start_bridge") {
    return toolResult(await startBridge(args));
  }
  const options = {
    sessionName: args.sessionName,
    sessionFile: args.sessionFile,
    timeoutMs: args.timeoutMs,
  };
  if (name === "blendercodex_bridge_ping") {
    return toolResult(await callBridge("ping", {}, options));
  }
  if (name === "blendercodex_scene_summary") {
    return toolResult(await callBridge("scene_summary", {}, options));
  }
  if (name === "blendercodex_run_python") {
    return toolResult(await callBridge("run_python", { code: String(args.code || "") }, options));
  }
  if (name === "blendercodex_save") {
    return toolResult(await callBridge("save", { filepath: args.filepath }, options));
  }
  if (name === "blendercodex_open_file") {
    return toolResult(await callBridge("open_file", { filepath: String(args.filepath || "") }, options));
  }
  if (name === "blendercodex_shutdown_bridge") {
    return toolResult(await callBridge("shutdown", {}, options));
  }
  if (name === "blendercodex_prune_collection") {
    const code = pruneCollectionCode(String(args.target), Array.isArray(args.keep) ? args.keep.map(String) : []);
    const result = await callBridge("run_python", { code }, options);
    if (args.save) {
      const save = await callBridge("save", {}, options);
      return toolResult({ prune: result, save });
    }
    return toolResult(result);
  }
  const humanoidActions = {
    blendercodex_humanoid_analyze: "analyze",
    blendercodex_humanoid_fit_standard: "fit_standard",
    blendercodex_humanoid_validate: "validate",
    blendercodex_humanoid_bind_preview: "bind_preview",
  };
  if (humanoidActions[name]) {
    const code = humanoidRuntimeCode(humanoidActions[name], args);
    return toolResult(await callBridge("run_python", { code }, options));
  }
  return toolResult(`Unknown tool: ${name}`, true);
}

function send(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

async function handleLine(line) {
  if (!line.trim()) {
    return;
  }
  let request;
  try {
    request = JSON.parse(line);
  } catch (_) {
    send({ jsonrpc: "2.0", error: { code: -32700, message: "Parse error" } });
    return;
  }

  const id = request.id;
  try {
    if (request.method === "initialize") {
      send({
        jsonrpc: "2.0",
        id,
        result: {
          protocolVersion: request.params && request.params.protocolVersion ? request.params.protocolVersion : "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: "BlenderCodex Temporary Bridge", version: "0.2.0" },
        },
      });
      return;
    }
    if (request.method === "notifications/initialized") {
      return;
    }
    if (request.method === "tools/list") {
      send({ jsonrpc: "2.0", id, result: { tools } });
      return;
    }
    if (request.method === "tools/call") {
      const params = request.params || {};
      const result = await callTool(params.name, params.arguments || {});
      send({ jsonrpc: "2.0", id, result });
      return;
    }
    send({ jsonrpc: "2.0", id, error: { code: -32601, message: `Method not found: ${request.method}` } });
  } catch (error) {
    send({
      jsonrpc: "2.0",
      id,
      result: toolResult(error && error.stack ? error.stack : String(error), true),
    });
  }
}

function main() {
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  let requestChain = Promise.resolve();

  rl.on("line", (line) => {
    requestChain = requestChain
      .then(() => handleLine(line))
      .catch((error) => {
        send({
          jsonrpc: "2.0",
          error: {
            code: -32603,
            message: error && error.stack ? error.stack : String(error),
          },
        });
      });
  });
}

if (require.main === module) {
  main();
}

module.exports = {
  humanoidRuntimeCode,
  shouldUseKeepAlive,
};
