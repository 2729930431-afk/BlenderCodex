const fs = require("fs");
const os = require("os");
const path = require("path");
const childProcess = require("child_process");

const pluginRoot = path.resolve(__dirname, "..");
const mcpServer = path.join(pluginRoot, "scripts", "blendercodex_mcp_server.js");
const workDir = fs.mkdtempSync(path.join(os.tmpdir(), "blendercodex-open-project-test-"));
const sessionFile = path.join(workDir, "inferred_open_project_session.json");
const blendFile = path.join(workDir, "opened-project.blend");

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

function callMcp(requests, env = {}) {
  const input = requests.map((request) => JSON.stringify(request)).join("\n");
  const result = childProcess.spawnSync(process.execPath, [mcpServer], {
    input,
    encoding: "utf8",
    timeout: 60000,
    windowsHide: true,
    env: { ...process.env, ...env },
  });

  if (result.status !== 0) {
    throw new Error(`MCP server exited with ${result.status}\nSTDOUT:\n${result.stdout}\nSTDERR:\n${result.stderr}`);
  }

  return result.stdout
    .trim()
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function responseById(responses, id) {
  const response = responses.find((item) => item.id === id);
  if (!response) {
    throw new Error(`Missing response id ${id}:\n${JSON.stringify(responses, null, 2)}`);
  }
  return response;
}

function toolJson(responses, id) {
  const response = responseById(responses, id);
  if (response.result && response.result.isError) {
    throw new Error(`Tool ${id} returned error:\n${response.result.content[0].text}`);
  }
  return JSON.parse(response.result.content[0].text);
}

function stopPid(pid) {
  if (!pid) {
    return;
  }
  try {
    if (process.platform === "win32") {
      childProcess.spawnSync("taskkill.exe", ["/PID", String(pid), "/T", "/F"], { windowsHide: true });
    } else {
      process.kill(pid, "SIGTERM");
    }
  } catch (_) {}
}

const blenderPath = process.env.BLENDERCODEX_TEST_BLENDER || process.env.BLENDER_PATH || cachedBlenderPath();
if (!blenderPath) {
  throw new Error("Set BLENDERCODEX_TEST_BLENDER or BLENDER_PATH, or cache Blender with BlenderCodex before running this test.");
}

let startedPid = null;

try {
  const createBlend = childProcess.spawnSync(
    blenderPath,
    [
      "--factory-startup",
      "-b",
      "--python-expr",
      `import bpy; bpy.ops.wm.save_as_mainfile(filepath=${JSON.stringify(blendFile)})`,
    ],
    { encoding: "utf8", timeout: 60000, windowsHide: true },
  );
  if (createBlend.status !== 0 || !fs.existsSync(blendFile)) {
    throw new Error(`Failed to create test .blend\nSTDOUT:\n${createBlend.stdout}\nSTDERR:\n${createBlend.stderr}`);
  }

  const fakeOpenProcess = JSON.stringify([
    {
      pid: 4242,
      commandLine: `"${blenderPath}" "${blendFile}"`,
    },
  ]);

  const startResponses = callMcp(
    [
      { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2024-11-05" } },
      {
        jsonrpc: "2.0",
        id: 2,
        method: "tools/call",
        params: {
          name: "blendercodex_start_bridge",
          arguments: {
            blenderPath,
            sessionFile,
            sessionName: "open-project-inference-test",
            waitMs: 20000,
          },
        },
      },
    ],
    { BLENDERCODEX_TEST_OPEN_BLEND_PROCESSES: fakeOpenProcess },
  );

  const started = toolJson(startResponses, 2);
  startedPid = started.pid;
  if (path.resolve(started.blendFile) !== path.resolve(blendFile)) {
    throw new Error(`Expected inferred blendFile ${blendFile}, got ${started.blendFile}`);
  }
  if (!started.ping || !started.ping.pong || path.resolve(started.ping.file) !== path.resolve(blendFile)) {
    throw new Error(`Bridge did not open inferred .blend: ${JSON.stringify(started, null, 2)}`);
  }

  const shutdownResponses = callMcp([
    { jsonrpc: "2.0", id: 3, method: "initialize", params: { protocolVersion: "2024-11-05" } },
    {
      jsonrpc: "2.0",
      id: 4,
      method: "tools/call",
      params: {
        name: "blendercodex_shutdown_bridge",
        arguments: { sessionFile },
      },
    },
  ]);
  const shutdown = toolJson(shutdownResponses, 4);
  if (!shutdown.shutdown) {
    throw new Error(`Bridge did not shut down cleanly: ${JSON.stringify(shutdown)}`);
  }

  console.log(
    JSON.stringify(
      {
        ok: true,
        inferredBlendFile: started.blendFile,
        sessionFile,
      },
      null,
      2,
    ),
  );
} finally {
  stopPid(startedPid);
  try {
    fs.rmSync(workDir, { recursive: true, force: true });
  } catch (_) {}
}
