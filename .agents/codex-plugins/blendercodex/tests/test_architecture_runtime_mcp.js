const assert = require("assert");
const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");

const pluginRoot = path.resolve(__dirname, "..");
const mcpServer = path.join(pluginRoot, "scripts", "blendercodex_mcp_server.js");
const { workflowRuntimeCode } = require(mcpServer);

const expected = [
  "blendercodex_opening_markers_create",
  "blendercodex_opening_markers_inspect",
  "blendercodex_openings_apply",
  "blendercodex_tiled_roof_inspect",
  "blendercodex_tiled_roof_build",
  "blendercodex_tiled_roof_validate",
  "blendercodex_validate_model",
  "blendercodex_model_signature",
];

const input = [
  { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2024-11-05" } },
  { jsonrpc: "2.0", id: 2, method: "tools/list" },
].map((row) => JSON.stringify(row)).join("\n");
const result = childProcess.spawnSync(process.execPath, [mcpServer], { input, encoding: "utf8" });
assert.strictEqual(result.status, 0, result.stderr);
const responses = result.stdout.trim().split(/\r?\n/).map((line) => JSON.parse(line));
const listed = responses.find((row) => row.id === 2).result.tools;
const names = new Set(listed.map((tool) => tool.name));
for (const name of expected) assert.ok(names.has(name), `missing ${name}`);

assert.deepStrictEqual(
  listed.find((tool) => tool.name === "blendercodex_openings_apply").inputSchema.required,
  ["markerCollection"],
);
assert.strictEqual(
  listed.find((tool) => tool.name === "blendercodex_opening_markers_create")
    .inputSchema.properties.markers.items.additionalProperties,
  false,
);
assert.deepStrictEqual(
  listed.find((tool) => tool.name === "blendercodex_tiled_roof_build").inputSchema.required,
  ["domains"],
);
assert.ok(listed.find((tool) => tool.name === "blendercodex_openings_apply").inputSchema.properties.filepath);
assert.ok(listed.find((tool) => tool.name === "blendercodex_tiled_roof_build").inputSchema.properties.filepath);
assert.deepStrictEqual(
  listed.find((tool) => tool.name === "blendercodex_opening_markers_create")
    .inputSchema.properties.markers.items.required,
  ["role", "target"],
);
assert.deepStrictEqual(
  listed.find((tool) => tool.name === "blendercodex_opening_markers_create")
    .inputSchema.properties.markers.items.properties.role.enum,
  ["door", "window"],
);
assert.ok(
  listed.find((tool) => tool.name === "blendercodex_tiled_roof_build")
    .inputSchema.properties.domains.items.required.includes("roofObject"),
);
assert.strictEqual(
  listed.find((tool) => tool.name === "blendercodex_tiled_roof_build")
    .inputSchema.properties.domains.items.additionalProperties,
  false,
);

const runtimeCode = workflowRuntimeCode("openings", "markers_create", {
  markers: [{ role: "window" }],
  save: true,
  sessionFile: "discard-me",
});
assert.match(runtimeCode, /ACTION = "markers_create"/);
assert.match(runtimeCode, /json\.loads/);
assert.doesNotMatch(runtimeCode, /discard-me/);
assert.doesNotMatch(runtimeCode, /PARAMS = \{[^\n]*\btrue\b/);
assert.match(runtimeCode, /opening_runtime\.py/);

for (const relative of [
  "skills/architectural-openings/scripts/opening_runtime.py",
  "skills/tiled-roof/scripts/tiled_roof_runtime.py",
  "skills/model-validation/scripts/model_validation_runtime.py",
]) {
  const source = fs.readFileSync(path.join(pluginRoot, relative), "utf8");
  assert.doesNotMatch(source, /confirmed\s*\)/i, `${relative} must not require confirmation`);
}

console.log(JSON.stringify({ ok: true, tools: expected.length }, null, 2));
