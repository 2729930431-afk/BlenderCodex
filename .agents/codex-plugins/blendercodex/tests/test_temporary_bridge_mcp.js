const fs = require("fs");
const os = require("os");
const path = require("path");
const childProcess = require("child_process");

const pluginRoot = path.resolve(__dirname, "..");
const mcpServer = path.join(pluginRoot, "scripts", "blendercodex_mcp_server.js");
const workDir = fs.mkdtempSync(path.join(os.tmpdir(), "blendercodex-bridge-test-"));
fs.mkdirSync(workDir, { recursive: true });

const sessionFile = path.join(workDir, "temporary_bridge_session.json");
try {
  fs.rmSync(sessionFile, { force: true });
} catch (_) {}

function codexHome() {
  return process.env.CODEX_HOME || path.join(os.homedir(), ".codex");
}

function cachedBlenderPath() {
  const configPath = path.join(codexHome(), "blendercodex", "config.json");
  if (!fs.existsSync(configPath)) {
    return null;
  }
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  return config.path && fs.existsSync(config.path) ? config.path : null;
}

const blenderPath = process.env.BLENDERCODEX_TEST_BLENDER || process.env.BLENDER_PATH || cachedBlenderPath();
if (!blenderPath) {
  throw new Error("Set BLENDERCODEX_TEST_BLENDER or BLENDER_PATH, or cache Blender with BlenderCodex before running this test.");
}

const requests = [
  { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2024-11-05" } },
  { jsonrpc: "2.0", id: 2, method: "tools/list" },
  {
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: {
      name: "blendercodex_start_bridge",
      arguments: {
        blenderPath,
        sessionFile,
        sessionName: "temporary-bridge-test",
        background: true,
        keepAlive: true,
        waitMs: 20000,
      },
    },
  },
  {
    jsonrpc: "2.0",
    id: 4,
    method: "tools/call",
    params: {
      name: "blendercodex_run_python",
      arguments: {
        sessionFile,
        code: [
          "import bpy",
          "bpy.ops.mesh.primitive_cube_add(size=1, location=(2, 3, 4))",
          "bpy.context.object.name = 'TemporaryBridgeMcpCube'",
          "RESULT = {'created': bpy.context.object.name, 'object_count': len(bpy.context.scene.objects)}",
        ].join("\n"),
      },
    },
  },
  {
    jsonrpc: "2.0",
    id: 5,
    method: "tools/call",
    params: {
      name: "blendercodex_scene_summary",
      arguments: { sessionFile },
    },
  },
  {
    jsonrpc: "2.0",
    id: 6,
    method: "tools/call",
    params: {
      name: "blendercodex_shutdown_bridge",
      arguments: { sessionFile },
    },
  },
];

const input = requests.map((request) => JSON.stringify(request)).join("\n");
const result = childProcess.spawnSync("node", [mcpServer], {
  input,
  encoding: "utf8",
  timeout: 60000,
  windowsHide: true,
});

if (result.status !== 0) {
  throw new Error(`MCP server exited with ${result.status}\nSTDOUT:\n${result.stdout}\nSTDERR:\n${result.stderr}`);
}

const responses = result.stdout
  .trim()
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));

function byId(id) {
  const response = responses.find((item) => item.id === id);
  if (!response) {
    throw new Error(`Missing response id ${id}. Full output:\n${result.stdout}`);
  }
  return response;
}

function toolJson(id) {
  const response = byId(id);
  if (response.result && response.result.isError) {
    throw new Error(`Tool ${id} returned error:\n${response.result.content[0].text}`);
  }
  return JSON.parse(response.result.content[0].text);
}

if (!byId(2).result.tools.some((tool) => tool.name === "blendercodex_start_bridge")) {
  throw new Error("tools/list did not expose blendercodex_start_bridge");
}

const started = toolJson(3);
if (!started.started || !started.ping || !started.ping.pong) {
  throw new Error(`Bridge did not start cleanly: ${JSON.stringify(started)}`);
}

const run = toolJson(4);
if (!run.result || run.result.created !== "TemporaryBridgeMcpCube") {
  throw new Error(`run_python did not create expected cube: ${JSON.stringify(run)}`);
}

const summary = toolJson(5);
if (!summary.objects.some((object) => object.name === "TemporaryBridgeMcpCube")) {
  throw new Error("scene_summary did not include TemporaryBridgeMcpCube");
}

const shutdown = toolJson(6);
if (!shutdown.shutdown) {
  throw new Error(`Bridge did not shut down cleanly: ${JSON.stringify(shutdown)}`);
}

console.log(
  JSON.stringify(
    {
      ok: true,
      tool_count: byId(2).result.tools.length,
      object_count: summary.object_count,
      sessionFile,
    },
    null,
    2,
  ),
);

try {
  fs.rmSync(workDir, { recursive: true, force: true });
} catch (_) {}
