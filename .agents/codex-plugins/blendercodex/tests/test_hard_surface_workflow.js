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
assert.match(skill, /usable cavity plus paired exterior\/interior wall faces/, "opening targets must be interior-ready");
assert.match(skill, /coherent thickness-aware hollow shell/, "non-ready targets become hollow shells before cutting");
assert.match(skill, /raw Boolean output as an intermediate at most/, "raw Boolean output is not delivery topology");
assert.match(skill, /Mandatory Hard-Surface Topology Contract/, "hard-surface contract is mandatory");
assert.match(skill, /object-mode mesh copy or detached BMesh/, "substantial rewrites use a stable copy transaction");
assert.match(skill, /Save and reopen the serialized `.blend`/, "substantial rewrites are reload-verified");

assert.match(rules, /horizontal sill and head bands plus vertical jamb and bay strips/i, "opening topology follows feature bands");
assert.match(rules, /facade-local/i, "opening bands remain local to their owning facade");
assert.match(rules, /do not project a building-wide Cartesian grid/i, "global cross-building topology grids are forbidden");
assert.match(rules, /first form continuous horizontal sill\/head bands, then form vertical jamb\/bay strips/i, "cleanup order preserves the learned band pattern");
assert.match(rules, /Reject any merge that would need a bridge diagonal/i, "coplanar cleanup cannot introduce bridge diagonals");
assert.match(rules, /structural elevation loop/i, "purposeful elevation loops survive coplanar cleanup");
assert.match(rules, /Do not dissolve an edge solely because its two coplanar faces can form one rectangle/i, "fewest faces is not the topology objective");
assert.match(rules, /oversized n-gon/i, "user-authored quad bands may replace oversized n-gons");
assert.match(rules, /exterior and interior wall faces/i, "both wall sides are standardized");
assert.match(rules, /visually open hole is not acceptance evidence/i, "visible-only cuts do not pass validation");
assert.match(rules, /diagonally bridges an opening corner/i, "facade bridge diagonals are explicitly rejected");
assert.match(rules, /Do not force orthogonal topology onto curved, sloped, triangular/i, "shape-required diagonals remain allowed");
assert.match(rules, /zero wire edges, zero degenerate faces/i, "mesh health checks are explicit");
assert.match(rules, /classify boundary and non-manifold edges by source/i, "intentional thresholds are distinguished from mesh defects");
assert.match(rules, /validated cavity and continuous inner wall surfaces/i, "shell readiness is validated before opening cuts");
assert.match(rules, /through the full wall thickness/i, "openings connect exterior to the cavity");
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
assert.match(manifest.version, /^0\.1\.0\+codex\.\d{14}$/, "plugin cachebuster uses a timestamp");

console.log(JSON.stringify({ ok: true, checked: "window and hard-surface workflow" }, null, 2));
