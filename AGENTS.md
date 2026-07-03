# AGENTS.md

This repository contains the `blendercodex` Codex plugin.

Plugin assets:

- `.agents/plugins/marketplace.json` exposes this repository as a Codex plugin marketplace.
- `.agents/codex-plugins/blendercodex/.codex-plugin/plugin.json` is the plugin manifest.
- `.agents/codex-plugins/blendercodex/.mcp.json` exposes the `blendercodex` MCP server.
- `.agents/codex-plugins/blendercodex/skills/*/SKILL.md` are reusable Codex skills.

Install from the repository root:

```powershell
codex plugin marketplace add .
codex plugin add blendercodex@blendercodex
```

