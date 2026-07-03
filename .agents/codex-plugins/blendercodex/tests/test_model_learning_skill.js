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
