const assert = require("assert");
const fs = require("fs");
const path = require("path");

const pluginRoot = path.resolve(__dirname, "..");

function read(relativePath) {
  return fs.readFileSync(path.join(pluginRoot, relativePath), "utf8").replace(/\r\n/g, "\n");
}

const skill = read("skills/blendercodex/SKILL.md");
const rules = read("skills/blendercodex/references/hard-surface-topology-and-openings.md");
const internalStructure = read("skills/internal-structure/SKILL.md");
const manifest = JSON.parse(read(".codex-plugin/plugin.json"));

assert.match(skill, /window\/opening creation/i, "window work triggers the owning skill");
assert.match(skill, /any hard-surface mesh generation/i, "hard-surface work triggers the owning skill");
assert.match(skill, /Mandatory Window Opening Approval Gate/, "window approval gate is mandatory");
assert.match(
  skill,
  /Do not cut, boolean, delete, rebuild, or otherwise change the target wall mesh before confirmation/,
  "wall geometry remains unchanged until confirmation",
);
assert.match(skill, /Treat marker transforms as authoritative/, "confirmed live markers are authoritative");
assert.match(skill, /honor deleted markers as removed openings/, "deleted markers stay deleted");
assert.match(skill, /Mandatory Hard-Surface Topology Contract/, "hard-surface contract is mandatory");
assert.match(skill, /object-mode mesh copy or detached BMesh/, "substantial rewrites use a stable copy transaction");
assert.match(skill, /Save and reopen the serialized `.blend`/, "substantial rewrites are reload-verified");

assert.match(rules, /horizontal sill and head bands plus vertical jamb and bay strips/i, "opening topology follows feature bands");
assert.match(rules, /exterior and interior wall faces/i, "both wall sides are standardized");
assert.match(rules, /Do not force orthogonal topology onto curved, sloped, triangular/i, "shape-required diagonals remain allowed");
assert.match(rules, /zero wire edges, zero degenerate faces/i, "mesh health checks are explicit");
assert.match(rules, /boundary and non-manifold counts do not worsen/i, "topology health regression is checked");
assert.match(rules, /UV_4m_world_standard/, "world-density UV standard remains mandatory");
assert.match(rules, /saved `.blend` can be reopened/i, "serialized result is verified");

assert.match(
  internalStructure,
  /hard-surface-topology-and-openings\.md/,
  "internal structure routes opening and hard-surface work through the shared contract",
);
assert.ok(
  manifest.interface.capabilities.includes("Confirmed window-opening workflow"),
  "manifest advertises the window-confirmation workflow",
);
assert.ok(
  manifest.interface.capabilities.includes("Hard-surface topology standard"),
  "manifest advertises the hard-surface topology standard",
);
assert.match(manifest.version, /^0\.1\.0\+codex\.20260805\d{6}$/, "plugin cachebuster was updated");

console.log(JSON.stringify({ ok: true, checked: "window and hard-surface workflow" }, null, 2));
