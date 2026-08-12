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
const tiledRoofLearning = read("skills/model-learning/references/verified-tiled-roof-and-openings.md");
const manifest = JSON.parse(read(".codex-plugin/plugin.json"));

assert.match(skill, /^---\nname: model-learning\n/m, "model-learning frontmatter is present");
assert.match(skill, /学习/, "Chinese learning trigger is present");
assert.match(skill, /Gather evidence/, "learning workflow collects evidence");
assert.match(skill, /Choose the storage target/, "learning workflow scopes storage");
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
  /Durable lessons must live in the loaded skill body/,
  "blendercodex skill promotes durable lessons into rules",
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
assert.match(blendercodexSkill, /rough width and `2\.0 m` rough height for every door and window/, "doors and windows default to 1x2 rough openings");
assert.match(hardSurface, /default rough opening for every door and window is `1\.0 m` wide by `2\.0 m` high/, "opening reference enforces the 1x2 default");
assert.match(tiledRoofLearning, /observed_problem/, "verified tiled-roof learning records the prior failure");
assert.match(tiledRoofLearning, /唐老三家屋顶_布尔原型1/, "verified learning records authoritative scene evidence");
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
  manifest.interface.capabilities.includes("User-edit learning loop"),
  "manifest advertises learning loop capability",
);
assert.ok(
  manifest.interface.defaultPrompt.some((prompt) => prompt.includes("$model-learning")),
  "manifest advertises model-learning default prompt",
);

console.log(JSON.stringify({ ok: true, checked: "model-learning skill" }, null, 2));
