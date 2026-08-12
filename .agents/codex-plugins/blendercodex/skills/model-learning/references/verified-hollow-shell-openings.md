# Verified Learning Packet: Hollow Shells and Delivery-Ready Opening Topology

```yaml
artifact: D:/Clone/scnvenger_assets/村庄资产/云浮村/唐家.blend; live BlenderCodex RPC inspection of 唐老二主屋, 唐老二厢房, and 唐老二耳房 after the user's manual correction; prior viewport screenshot showing an opening-to-corner diagonal
user_edit: Hollowed the building interiors and simplified the generated door/window topology so openings pass through a real wall shell without the diagonal and over-propagated facade cuts shown in the failed result.
observed_problem: The previous workflow treated a visible wall hole as completion. It cut before proving a usable interior cavity, then left Boolean-style diagonals and redundant opening coordinates extending into unrelated wall and corner regions.
inferred_reason: The correction makes the building usable from both sides and keeps topology aligned to actual features. An opening is architectural only when exterior face, reveal, interior face, and cavity are coherent; a facade diagonal or global coordinate grid adds no form and makes later edits fragile.
future_rule: Classify the target as interior-ready before cutting. If needed, first create a coherent thickness-aware hollow shell. After confirmation, cut through the full wall thickness and rebuild the affected facade locally with sill/head bands and jamb/bay strips. Raw Boolean output is only an intermediate, never delivery topology. Classify intentional door-threshold boundaries separately from defective wires or gaps.
scope: scoped_skill_rule for buildings, wall shells, and rectangular door/window openings
storage_target: skills/blendercodex/SKILL.md and skills/blendercodex/references/hard-surface-topology-and-openings.md
validation: Inspect the live corrected meshes for paired shell faces, unobstructed full-depth openings, local feature bands, modifiers, face types, wire/degenerate geometry, UV_4m_world_standard, and the absence of facade bridge diagonals; run test_hard_surface_workflow.js and test_model_learning_skill.js.
limits: Do not ban non-orthogonal edges that describe a real sloped roof-contact, chamfer, curve, or miter. Do not interpret intentional open thresholds as accidental gaps. This packet does not approve unrelated mesh defects found during inspection.
```

## Scene Evidence

- The live scene was clean (`bpy.data.is_dirty == false`) when inspected, and a separate Blender 5.0 background reopen reproduced the topology counts, so the measurements reflect the serialized user-corrected file.
- `唐老二主屋` now has `127 / 234 / 90` vertices/edges/faces, `70` quads, no triangles, no modifiers, no wire or degenerate edges, and active/render `UV_4m_world_standard`.
- `唐老二厢房` now has `104 / 190 / 69` vertices/edges/faces, `57` quads, no triangles, no modifiers, no wire or degenerate edges, and active/render `UV_4m_world_standard`.
- Compared with the prior generated states reported in this task (`135 / 276 / 113` and `116 / 234 / 93`), the correction removes redundant topology instead of merely hiding it.
- Remaining non-axis edges on the main house and side wing are 0.2 m top-corner miters, not diagonals spanning a planar facade from an opening to a wall corner.
- `唐老二耳房` is useful evidence for preserving genuine single-slope roof directions. A clean Blender 5.0 background reopen confirmed two zero-length loose edges; that isolated defect is excluded from the promoted pattern and still fails the general hard-surface contract.
