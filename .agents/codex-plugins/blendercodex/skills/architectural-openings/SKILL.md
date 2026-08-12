---
name: architectural-openings
description: Create, inspect, apply, and validate Blender architectural door, window, and rectangular wall openings from semantic live markers. Use with BlenderCodex for 门窗、窗位、门洞、墙洞、opening markers, rough openings, rectilinear wall shells, or repeated facade opening work that should run through a tested executor instead of ad hoc bpy code.
---

# Architectural Openings

Use the specialized MCP tools instead of rewriting opening geometry code.

## Workflow

1. Inspect the real target meshes and classify each supported envelope as an axis-aligned box or explicit box union in object-local space.
2. Create semantic markers with `blendercodex_opening_markers_create` when markers do not already exist. Use stable ids, explicit target objects, and wall axes.
3. Use distinct defaults when stronger evidence is absent:
   - door: `1.0 m × 2.1 m`, sill `0.0 m`;
   - window: `1.2 m × 1.5 m`, sill `0.9 m`.
4. Continue directly to `blendercodex_openings_apply` after marker creation. Pause only when the user explicitly asks to inspect, move, approve, or revise markers first.
5. Immediately before applying, let the runtime re-read the live marker collection. Existing marker transforms are authoritative and deleted markers stay deleted.
6. Pass `componentsByObject` for compound box-union buildings. Do not approximate curved, sloped, non-rectilinear, or unclassified walls; report them as unsupported.
7. Protect roofs and unrelated geometry with `protectedObjects`. Let the executor build detached candidates, validate them, atomically swap meshes, hide markers, and save by default.
8. Finish the task after successful validation. Do not ask the user to confirm completion unless they explicitly requested a review stop.

## Tools

- `blendercodex_opening_markers_create`: create role-aware semantic markers.
- `blendercodex_opening_markers_inspect`: inspect the authoritative live marker snapshot.
- `blendercodex_openings_apply`: build and commit supported rectilinear openings.
- `blendercodex_validate_model`: run topology and `UV_4m_world_standard` checks.
- `blendercodex_model_signature`: capture stable protected-object fingerprints.

## Guarantees and limits

- Never share one fallback size between doors and windows.
- Preserve materials, transforms, roof geometry, and unrelated user changes. Reject multi-material walls until a tested per-face material transfer exists.
- Require explicit `componentsByObject` when a compound envelope cannot be derived safely.
- Fail before mesh replacement when the target is unsupported or validation fails.
- Treat this executor as rough-opening construction; frames, leaves, glazing, and trim are separate tasks.
- The current executor validates closed topology, UV density, dimensions/overlap bounds, role families, and protected signatures. It does not yet provide ray-grid clearance, normal-direction, or save/reopen validation; use live inspection or a separate reopened task when those checks are required.

Read [references/opening-contract.md](references/opening-contract.md) when supplying marker/component schemas or diagnosing a rejected target.

Read [references/verified-distinct-opening-sizes.md](references/verified-distinct-opening-sizes.md) only when auditing or extending the role-specific size learning and its regression evidence.
