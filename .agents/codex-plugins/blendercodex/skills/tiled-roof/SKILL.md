---
name: tiled-roof
description: Build, update, inspect, and validate editable Blender pan-tile, cover-tile, ridge-tile, and edge-tile roof systems. Use with BlenderCodex for 瓦片屋顶、板瓦、筒瓦、脊瓦、檐口、双坡屋顶、单坡屋顶、L 型瓦屋顶, Array/Mirror roof workflows, or repeated tiled-roof work that should use a tested executor.
---

# Tiled Roof

Use the tiled-roof MCP executor instead of copying scripts from task history.

## Workflow

1. Inspect roof bases and identify explicit slope domains, owner roots, eave/ridge vectors, ridge spans, symmetry, and any L-roof cutters.
2. Call `blendercodex_tiled_roof_build` with analyzed `domains`. Use:
   - `gable_mirror` only for genuinely symmetric two-slope roofs with a valid owner-root mirror plane;
   - `independent_slope` for asymmetric or slope-specific roofs;
   - `l_boolean` only with an explicit closed cutter for each domain.
3. Keep pan, cover, and ridge meshes closed and editable. Keep modifier order as Array along eave, Array up slope, then optional Mirror or Boolean.
4. Keep tile sources in the roof's existing collections and parent them directly to the roof base. Do not apply repetition modifiers.
5. Let the executor validate topology, `UV_4m_world_standard`, modifier order, ownership, and save by default.
6. Finish after successful validation. Pause only when the user explicitly requests a preview or review step.

## Tools

- `blendercodex_tiled_roof_inspect`: inspect an existing generated system.
- `blendercodex_tiled_roof_build`: create a tested editable system in one call.
- `blendercodex_tiled_roof_validate`: validate source meshes and modifier contracts.
- `blendercodex_model_signature`: protect unrelated geometry.

## Limits

- Domain analysis remains an inspection step; do not fabricate dimensions from object names.
- Automatic general L-roof cutter inference is not supported. Supply a closed manifold mesh cutter per domain. Cutter penetration and evaluated Boolean fragments still require scene-specific inspection.
- Do not use `gable_mirror` when transforms, penetrations, dormers, damage, or slope geometry differ.

Read [references/roof-contract.md](references/roof-contract.md) for the domain schema and tile profile.

Read [references/verified-tiled-roof-and-openings.md](references/verified-tiled-roof-and-openings.md) only when auditing or extending the L-roof learning and its regression evidence.
