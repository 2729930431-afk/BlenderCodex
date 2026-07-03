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
- `model-learning`: promote verified modeling corrections into reusable rules.
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
python C:\Users\27299\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .\.agents\codex-plugins\blendercodex
node .\.agents\codex-plugins\blendercodex\tests\test_keepalive_visible_guard.js
node .\.agents\codex-plugins\blendercodex\tests\test_model_learning_skill.js
```

The live Blender MCP tests require a local Blender executable. Set
`BLENDERCODEX_TEST_BLENDER` or `BLENDER_PATH` before running those tests.

