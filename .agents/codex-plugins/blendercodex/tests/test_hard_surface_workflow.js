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
assert.match(skill, /Architectural Opening Execution Policy/, "window execution policy is explicit");
assert.match(skill, /Continue directly by default/, "opening workflow executes through by default");
assert.match(skill, /Treat marker transforms as authoritative/, "live markers are authoritative");
assert.match(skill, /honor deleted markers as removed openings/, "deleted markers stay deleted");
assert.match(skill, /Treat doors and windows as distinct opening families/, "door and window defaults are separate families");
assert.match(skill, /standard single-leaf door rough opening of `1\.0 m` wide by `2\.1 m` high/, "door fallback is role-specific");
assert.match(skill, /standard window rough opening of `1\.2 m` wide by `1\.5 m` high with a `0\.9 m` sill/, "window fallback is role-specific");
assert.match(
  skill,
  /interior-ready only when it has a real usable cavity and paired exterior\/interior wall faces/i,
  "window work detects whether the target has a real interior shell",
);
assert.match(skill, /first hollow or open the existing volume/i, "missing interior structure is created before opening cuts");
assert.match(skill, /Do not invent rooms or partitions/i, "interior-first repair does not invent a layout");
assert.match(skill, /Only then cut each current live door\/window opening through both exterior and interior wall faces/i, "live openings are cut only after the shell is ready");
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
assert.match(rules, /A closed solid, exterior-only sheet, single facade face, or disconnected panel is not interior-ready/i, "non-interior targets are classified explicitly");
assert.match(rules, /Only after that validation, cut the current live door\/window markers through both exterior and interior wall faces/i, "the reusable workflow hollows before cutting doors and windows");
assert.match(rules, /no remaining solid plug behind the visible opening/i, "validation rejects one-face openings into solid geometry");
assert.match(rules, /Do not force orthogonal topology onto curved, sloped, triangular/i, "shape-required diagonals remain allowed");
assert.match(rules, /zero wire edges, zero degenerate faces/i, "mesh health checks are explicit");
assert.match(rules, /classify boundary and non-manifold edges by source/i, "intentional thresholds are distinguished from mesh defects");
assert.match(rules, /validated cavity and continuous inner wall surfaces/i, "shell readiness is validated before opening cuts");
assert.match(rules, /through the full wall thickness/i, "openings connect exterior to the cavity");
assert.match(rules, /UV_4m_world_standard/, "world-density UV standard remains mandatory");
assert.match(rules, /saved `.blend` can be reopened/i, "serialized result is verified");
assert.match(rules, /Never reuse one fallback width-and-height pair across both roles/, "shared door/window fallback is forbidden");
assert.match(rules, /write the same authoritative values to the opening custom properties/, "marker display and metadata must agree");

assert.match(
  internalStructure,
  /hard-surface-topology-and-openings\.md/,
  "internal structure routes opening and hard-surface work through the shared contract",
);
assert.ok(
  manifest.interface.capabilities.includes("Executable architectural-opening workflow"),
  "manifest advertises the executable opening workflow",
);
assert.ok(
  manifest.interface.capabilities.includes("Interior-first door/window opening workflow"),
  "manifest advertises the interior-first opening workflow",
);
assert.ok(
  manifest.interface.capabilities.includes("Distinct door and window opening defaults"),
  "manifest advertises distinct door and window defaults",
);
assert.ok(
  manifest.interface.capabilities.includes("Hard-surface topology standard"),
  "manifest advertises the hard-surface topology standard",
);
assert.match(manifest.version, /^0\.1\.0\+codex\.\d{14}$/, "plugin cachebuster uses a timestamp");

console.log(JSON.stringify({ ok: true, checked: "window and hard-surface workflow" }, null, 2));
