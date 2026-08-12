# BlenderCodex

BlenderCodex is a Codex plugin for generating, inspecting, and editing Blender
`.blend` projects from Codex. It uses local Blender execution for new files and
a temporary localhost RPC bridge for live editing. It does not install a
persistent Blender add-on.

## What It Provides

- `blendercodex`: create new Blender files or edit existing/open projects.
- `internal-structure`: add floor-aware building structure and stairs.
- `viewport-match`: compare a Blender viewport with a reference image.
- `screenshot-design-refine`: generate design references from Blender views.
- `model-learning`: classify verified modeling corrections and route them to the owning capability.
- `workflow-learning`: require every repeatable operation to become a runtime action, focused MCP route when applicable, fixture, and regression tests. Skill text and reference documents provide routing, policy, evidence, and limits; they do not count as executable learning.
- `architectural-openings`: create and apply role-specific door/window openings.
- `tiled-roof`: build editable pan-, cover-, and ridge-tile systems.
- `model-validation`: validate topology, world-density UVs, and stable signatures.
- `blendercodex_*` MCP tools for starting the temporary bridge, running Blender
  Python, saving files, and inspecting scenes.

## Install From This Repository

Clone the repository, then run from the repository root:

```powershell
codex plugin marketplace add .
codex plugin add blendercodex@blendercodex
```

Start a new Codex thread after installing so the new skills and MCP tools are
loaded.

## Repository Layout

```text
.agents/plugins/marketplace.json
.agents/codex-plugins/blendercodex/.codex-plugin/plugin.json
.agents/codex-plugins/blendercodex/.mcp.json
.agents/codex-plugins/blendercodex/scripts/
.agents/codex-plugins/blendercodex/skills/
.agents/codex-plugins/blendercodex/tests/
```

## Development Checks

```powershell
$plugin = '.\.agents\codex-plugins\blendercodex'
$env:PYTHONUTF8 = '1'
Get-ChildItem "$plugin\tests\*.js" | ForEach-Object { node $_.FullName; if ($LASTEXITCODE) { throw $_.FullName } }
python "$plugin\tests\test_architecture_executors.py"
python "$plugin\skills\blendercodex\tests\test_blender_locator.py"
python "$plugin\skills\blendercodex\tests\test_capture_blend_state.py"
foreach ($skill in 'architectural-openings','tiled-roof','model-validation','workflow-learning','model-learning','blendercodex') {
  uv run --with pyyaml python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" "$plugin\skills\$skill"
}
uv run --with pyyaml python "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" $plugin
```

The live Blender MCP tests require a local Blender executable. Set
`BLENDERCODEX_TEST_BLENDER` or `BLENDER_PATH` before running those tests.
Run the architecture integration fixture with:

```powershell
& $env:BLENDERCODEX_TEST_BLENDER --factory-startup -b --python .\.agents\codex-plugins\blendercodex\tests\test_architecture_runtime_blender.py
```
