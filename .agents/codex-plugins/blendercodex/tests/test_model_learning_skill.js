const assert = require("assert");
const fs = require("fs");
const path = require("path");

const pluginRoot = path.resolve(__dirname, "..");

function read(relativePath) {
  return fs.readFileSync(path.join(pluginRoot, relativePath), "utf8");
}

const skill = read("skills/model-learning/SKILL.md");
const packet = read("skills/model-learning/references/learning-packet.md");
const blendercodexSkill = read("skills/blendercodex/SKILL.md");
const standards = read("skills/blendercodex/references/modeling-standards.md");
const roofMirroring = read("skills/blendercodex/references/roof-origin-mirroring.md");
const tiledRoof = read("skills/blendercodex/references/tiled-roof-system.md");
const hardSurface = read("skills/blendercodex/references/hard-surface-topology-and-openings.md");
const fbxHierarchy = read("skills/blendercodex/references/fbx-unity-hierarchy.md");
const fbxLearning = read("skills/model-learning/references/verified-fbx-parenting.md");
const hollowShellLearning = read("skills/model-learning/references/verified-hollow-shell-openings.md");
const tiledRoofLearning = read("skills/tiled-roof/references/verified-tiled-roof-and-openings.md");
const openingSizeLearning = read("skills/architectural-openings/references/verified-distinct-opening-sizes.md");
const workflowLearning = read("skills/workflow-learning/SKILL.md");
const promotionSchema = read("skills/workflow-learning/references/executor-promotion-schema.md");
const openingRuntime = read("skills/architectural-openings/scripts/opening_runtime.py");
const roofRuntime = read("skills/tiled-roof/scripts/tiled_roof_runtime.py");
const manifest = JSON.parse(read(".codex-plugin/plugin.json"));

assert.match(skill, /^---\nname: model-learning\n/m, "model-learning frontmatter is present");
assert.match(skill, /学习/, "Chinese learning trigger is present");
assert.match(skill, /Gather evidence/, "learning workflow collects evidence");
assert.match(skill, /Choose and implement the promotion target/, "learning workflow implements a scoped promotion target");
assert.match(skill, /runtime behavior/, "learning workflow requires executable behavior");
assert.match(skill, /executor-promotion-schema\.md/, "executable learning uses the workflow-learning packet schema");
assert.match(packet, /only for policy, model-local, or do-not-store lessons/i, "legacy packet is limited to non-executable lessons");
assert.match(promotionSchema, /runtime_action/, "executor packet declares a runtime action");
assert.match(workflowLearning, /document-only executable lesson must fail promotion/i, "document-only learning is rejected");
assert.match(openingRuntime, /def apply_openings/, "opening learning has a reusable executor");
assert.match(roofRuntime, /def build\(params\)/, "roof learning has a reusable executor");
assert.match(
  skill,
  /Do not create or update `\.memory\.md` as the default storage path/,
  "learning workflow avoids memory by default",
);
assert.match(packet, /observed_problem/, "learning packet records observed problem");
assert.match(packet, /future_rule/, "learning packet records future rule");
assert.match(packet, /scoped_skill_rule/, "learning packet supports scoped skill rules");
assert.ok(
  !fs.existsSync(path.join(pluginRoot, "skills/model-learning/.memory.md")),
  "model-learning does not depend on a memory file",
);
assert.match(
  blendercodexSkill,
  /not learned until it has an owning focused skill, runtime action, focused MCP tool when applicable, representative fixture, and regression tests/,
  "blendercodex requires executable promotion evidence",
);
assert.match(blendercodexSkill, /gabled house roofs/i, "gabled roof default is promoted");
assert.match(
  blendercodexSkill,
  /For every repeated brick or roof-tile element, use unapplied Blender Array modifiers/,
  "brick and roof-tile repetition keeps editable Array modifiers",
);
assert.match(
  blendercodexSkill,
  /parent them directly to the owning roof object/,
  "generated roof parts are direct children of the owning roof",
);
assert.match(
  blendercodexSkill,
  /Do not create a dedicated one-roof collection/,
  "generated roof systems do not create one-off collections",
);
assert.match(
  blendercodexSkill,
  /read `references\/roof-origin-mirroring\.md`/,
  "symmetric tiled roofs route through the focused mirroring workflow",
);
assert.match(blendercodexSkill, /瓦片屋顶 \(tiled roof\)/i, "unspecified roofs default to the named tiled-roof system");
assert.match(blendercodexSkill, /read `references\/tiled-roof-system\.md`/i, "roof work routes through the tiled-roof reference");
assert.match(tiledRoof, /Array along eave -> Array up slope -> Boolean Difference/, "L-roof tiles keep the verified modifier order");
assert.match(tiledRoof, /Choose the Boolean target independently per slope/, "L-roof cutter targets are selected per slope");
assert.match(tiledRoof, /Never copy one cutter target to every slope/, "L-roof workflow rejects the prior global-cutter failure");
assert.match(blendercodexSkill, /standard single-leaf door rough opening of `1\.0 m` wide by `2\.1 m` high/, "single-leaf doors have a dedicated default");
assert.match(blendercodexSkill, /standard window rough opening of `1\.2 m` wide by `1\.5 m` high with a `0\.9 m` sill/, "windows have a distinct dedicated default");
assert.match(hardSurface, /Never reuse one fallback width-and-height pair across both roles/, "opening reference forbids a shared door/window fallback");
assert.doesNotMatch(blendercodexSkill, /rough height for every door and window/, "the rejected shared 1x2 rule is absent");
assert.match(tiledRoofLearning, /observed_problem/, "verified tiled-roof learning records the prior failure");
assert.match(tiledRoofLearning, /唐老三家屋顶_布尔原型1/, "verified learning records authoritative scene evidence");
assert.match(openingSizeLearning, /artifact: .*方国伟家\.blend/, "opening-size correction records the authoritative scene");
assert.match(openingSizeLearning, /door and window roles must not share one fallback width-and-height pair/, "opening-size correction records the rejected failure mode");
assert.match(hollowShellLearning, /observed_problem/, "verified hollow-shell learning records the prior failure");
assert.match(hollowShellLearning, /唐老二主屋/, "verified hollow-shell learning records authoritative scene evidence");
assert.match(hollowShellLearning, /Raw Boolean output is only an intermediate/i, "verified learning rejects raw Boolean delivery topology");
assert.match(hollowShellLearning, /scoped_skill_rule/, "hollow-shell opening learning is correctly scoped");
assert.match(
  roofMirroring,
  /Place the building root object's origin at the roof-plan symmetry center/,
  "building origin anchors the roof mirror plane",
);
assert.match(
  roofMirroring,
  /Add one Mirror modifier after all Array modifiers/,
  "roof repetition is mirrored only after its editable arrays",
);
assert.match(
  roofMirroring,
  /Save and reopen the `.blend`/,
  "serialized roof conversion is reload-verified",
);
assert.match(
  blendercodexSkill,
  /FBX and Unity Hierarchy Safety/,
  "blendercodex routes FBX hierarchy edits through the safety workflow",
);
assert.match(
  fbxHierarchy,
  /matrix_parent_inverse = Matrix\.Identity\(4\)/,
  "FBX hierarchy workflow normalizes Blender parent inverses",
);
assert.match(
  fbxHierarchy,
  /apply_scale_options='FBX_SCALE_NONE'/,
  "FBX hierarchy workflow pins the export scale policy",
);
assert.match(
  fbxHierarchy,
  /Representative nested roof-owned objects should have unit local scale/,
  "Unity round-trip acceptance checks nested local scale",
);
assert.match(fbxLearning, /observed_problem/, "verified FBX learning records the problem");
assert.match(fbxLearning, /future_rule/, "verified FBX learning records the promoted rule");
assert.match(fbxLearning, /scoped_skill_rule/, "verified FBX learning is correctly scoped");
assert.match(standards, /triangular gable wall faces/i, "modeling standards include gable closure detail");
assert.ok(
  manifest.interface.capabilities.includes("Executable workflow-learning loop"),
  "manifest advertises learning loop capability",
);
assert.ok(
  manifest.interface.defaultPrompt.some((prompt) => prompt.includes("$model-learning")),
  "manifest advertises model-learning default prompt",
);

console.log(JSON.stringify({ ok: true, checked: "model-learning skill" }, null, 2));
