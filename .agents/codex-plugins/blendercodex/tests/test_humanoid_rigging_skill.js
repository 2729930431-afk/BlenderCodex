const assert = require("assert");
const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");

const pluginRoot = path.resolve(__dirname, "..");

function read(relativePath) {
  return fs.readFileSync(path.join(pluginRoot, relativePath), "utf8");
}

const skill = read("skills/humanoid-rigging/SKILL.md");
const fitting = read("skills/humanoid-rigging/references/humanoid-landmarks-and-fitting.md");
const learningPacket = read("skills/humanoid-rigging/references/learning-packet-pose-and-sagittal-fit.md");
const template = JSON.parse(read("skills/humanoid-rigging/references/female-humanoid-v1.json"));
const bodyPrior = JSON.parse(read("skills/humanoid-rigging/references/female-body-prior-v1.json"));
const runtime = read("skills/humanoid-rigging/scripts/humanoid_rig_runtime.py");
const assetPath = path.join(pluginRoot, "skills/humanoid-rigging/assets/female-humanoid-v1.blend");
const blendercodexSkill = read("skills/blendercodex/SKILL.md");
const manifest = JSON.parse(read(".codex-plugin/plugin.json"));

assert.match(skill, /^---\nname: humanoid-rigging\n/m, "humanoid-rigging frontmatter is present");
assert.match(skill, /人形识别/, "Chinese humanoid trigger is present");
assert.match(skill, /Recognition and landmark approval gate/, "landmark approval gate is documented");
assert.match(skill, /Fitting and binding approval gate/, "binding approval gate is documented");
assert.match(skill, /authoritative standard body skeleton/, "the blend asset is authoritative");
assert.match(skill, /Never reconstruct the exact rest rig from the JSON matrices/, "JSON reconstruction is forbidden");
assert.match(skill, /blendercodex_humanoid_analyze/, "specialized analysis RPC is documented");
assert.match(skill, /blendercodex_humanoid_bind_preview/, "duplicate-safe binding RPC is documented");
assert.match(fitting, /人形绑定标记_待确认/, "semantic marker collection is stable");
assert.match(fitting, /user-moved markers as authoritative/i, "user marker edits are authoritative");
assert.match(fitting, /never reconstruct the base rest rig from exported matrices/i, "fitting starts from copied Blender data");
assert.match(fitting, /Front-view agreement is not sufficient/i, "sagittal marker review is mandatory");
assert.match(fitting, /Clear copied `PoseBone\.matrix_basis` values/i, "fitted previews neutralize inherited pose channels");
assert.match(fitting, /evaluated Pose Position endpoints/i, "validation covers the constrained pose result");
assert.match(learningPacket, /topology-weighted clothing sections/i, "the verified sagittal failure is recorded");
assert.match(learningPacket, /Rest and Pose marker errors/i, "the learning packet records dual-position validation");
assert.ok(fs.existsSync(assetPath), "lossless humanoid rig asset exists");
assert.ok(fs.statSync(assetPath).size > 100000, "lossless humanoid rig asset is non-empty");

assert.strictEqual(template.schema_version, 1, "template schema is versioned");
assert.strictEqual(template.template_id, "female-humanoid-v1", "template id is stable");
assert.strictEqual(template.counts.source_bones, 94, "source bone count is recorded");
assert.strictEqual(template.counts.retained_bones, 76, "body skeleton retains 76 bones");
assert.strictEqual(template.counts.excluded_bones, 18, "18 hair bones are excluded");
assert.strictEqual(template.counts.deform_bones, 54, "deform count is stable");
assert.strictEqual(template.counts.control_bones, 22, "control/end count is stable");
assert.ok(template.bones.every((bone) => !bone.name.startsWith("头发")), "no hair bone is retained");
assert.ok(template.exclusion.excluded_bones.every((name) => name.startsWith("头发")), "only scoped hair bones are excluded");

assert.strictEqual(bodyPrior.schema_version, 1, "body prior schema is versioned");
assert.strictEqual(bodyPrior.prior_id, "female-body-prior-v1", "body prior id is stable");
assert.strictEqual(bodyPrior.counts.landmarks, 25, "body prior has all primary landmarks");
assert.ok(bodyPrior.counts.weighted_regions >= 40, "body prior records weighted deformation regions");
assert.ok(bodyPrior.body_proxy.objects.includes("手"), "hands are included in the body prior");
assert.ok(!bodyPrior.body_proxy.objects.some((name) => name.startsWith("头发")), "hair meshes are excluded from the body prior");
assert.ok(!bodyPrior.body_proxy.objects.includes("鞭子"), "accessory meshes are excluded from the body prior");

const names = new Set(template.bones.map((bone) => bone.name));
assert.strictEqual(names.size, template.bones.length, "bone names are unique");
for (const bone of template.bones) {
  assert.ok(bone.parent === null || names.has(bone.parent), `parent exists for ${bone.name}`);
  assert.strictEqual(bone.head.length, 3, `head is recorded for ${bone.name}`);
  assert.strictEqual(bone.tail.length, 3, `tail is recorded for ${bone.name}`);
  assert.strictEqual(bone.matrix_local.length, 4, `rest matrix is recorded for ${bone.name}`);
}

for (const [role, boneName] of Object.entries(template.semantic_roles)) {
  assert.ok(names.has(boneName), `semantic role ${role} resolves to ${boneName}`);
}
for (const poseRow of template.pose) {
  assert.ok(names.has(poseRow.bone), `pose record resolves to ${poseRow.bone}`);
  for (const constraint of poseRow.constraints) {
    if (constraint.subtarget) assert.ok(names.has(constraint.subtarget), "constraint subtarget exists");
    if (constraint.pole_subtarget) assert.ok(names.has(constraint.pole_subtarget), "constraint pole exists");
  }
}

assert.match(runtime, /params\.get\("confirmed"\) is not True/, "runtime enforces explicit confirmation gates");
assert.match(runtime, /_verify_signature\(marker_collection\)/, "runtime rechecks the analyzed target signature");
assert.match(runtime, /duplicate\.data = source\.data\.copy\(\)/, "binding preview duplicates mesh datablocks");
assert.match(runtime, /_robust_midpoint/, "sagittal centers use robust front\/back bounds");
assert.match(runtime, /pose_bone\.matrix_basis = Matrix\.Identity\(4\)/, "fit previews clear copied pose bases");
assert.match(runtime, /_optimize_pole_angle/, "IK pole angles are solved against confirmed joints");
assert.match(runtime, /pose_marker_fit_error/, "validation checks evaluated pose endpoints");
assert.match(runtime, /sagittal_chain_discontinuity/, "validation rejects side-view spine discontinuities");
assert.doesNotMatch(runtime, /save_as_mainfile|save_mainfile/, "runtime never saves implicitly");

const mcpServer = path.join(pluginRoot, "scripts", "blendercodex_mcp_server.js");
const { humanoidRuntimeCode } = require(mcpServer);
const generatedRuntimeCode = humanoidRuntimeCode("fit_standard", { confirmed: true, includeFingers: false });
assert.match(generatedRuntimeCode, /json\.loads/, "MCP serializes booleans through JSON for Blender Python");
assert.doesNotMatch(generatedRuntimeCode, /PARAMS = \{[^\n]*\btrue\b/, "MCP does not emit JavaScript booleans as Python literals");
const mcpInput = [
  { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2024-11-05" } },
  { jsonrpc: "2.0", id: 2, method: "tools/list" },
].map((request) => JSON.stringify(request)).join("\n");
const mcpResult = childProcess.spawnSync("node", [mcpServer], { input: mcpInput, encoding: "utf8", timeout: 10000 });
assert.strictEqual(mcpResult.status, 0, mcpResult.stderr);
const mcpResponses = mcpResult.stdout.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
const listedTools = mcpResponses.find((response) => response.id === 2).result.tools;
const listedByName = new Map(listedTools.map((tool) => [tool.name, tool]));
for (const toolName of [
  "blendercodex_humanoid_analyze",
  "blendercodex_humanoid_fit_standard",
  "blendercodex_humanoid_validate",
  "blendercodex_humanoid_bind_preview",
]) {
  assert.ok(listedByName.has(toolName), `MCP exposes ${toolName}`);
}
assert.deepStrictEqual(listedByName.get("blendercodex_humanoid_fit_standard").inputSchema.required, ["confirmed"]);
assert.deepStrictEqual(listedByName.get("blendercodex_humanoid_bind_preview").inputSchema.required, ["confirmed"]);

assert.match(blendercodexSkill, /use the `humanoid-rigging` skill/i, "main skill routes humanoid work");
assert.ok(
  manifest.interface.capabilities.includes("Humanoid skeleton templates and gated rig fitting"),
  "manifest advertises humanoid rigging",
);
assert.ok(
  manifest.interface.defaultPrompt.some((prompt) => prompt.includes("$humanoid-rigging")),
  "manifest advertises the humanoid-rigging prompt",
);

console.log(JSON.stringify({ ok: true, checked: "humanoid-rigging skill" }, null, 2));
