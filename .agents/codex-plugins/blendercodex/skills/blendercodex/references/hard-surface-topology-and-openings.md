# Hard-Surface Topology and Opening Rules

Read this reference before every hard-surface mesh operation. It is mandatory for new models and edits, including architecture, manufactured props, machines, vehicles, furniture, Boolean cleanup, retopology, bevel preparation, UV repair after topology changes, and window/door opening work.

## Window and Wall-Opening Execution Policy

When the user requests windows or comparable wall openings:

1. Inspect first.
   - Read the live or saved mesh, wall thickness, floor bands, current opening rows, doors, roof/slab conflicts, corners, and facade rhythm.
   - Classify the target as interior-ready only when the intended opening zones have a real usable cavity behind them and paired exterior/interior wall faces. A closed solid, exterior-only sheet, single facade face, or disconnected panel is not interior-ready.
   - Use plausible clearances from corners, slabs, doors, roof edges, and adjoining masses.
   - Default to one shared rough width and height for a repeated window family. Use multiple sizes only when the user or design evidence requires them.
   - Keep door and window defaults distinct. Unless the user or binding design evidence says otherwise, use a standard single-leaf door rough opening of `1.0 m` wide by `2.1 m` high with a `0.0 m` sill, and a standard window rough opening of `1.2 m` wide by `1.5 m` high with a `0.9 m` sill. Never reuse one fallback width-and-height pair across both roles. Main or double doors and additional window families should follow the observed facade hierarchy rather than being forced to either standard size.

2. Create semantic markers.
   - Create empties in a stable collection such as `门窗标记`.
   - Align each empty to its wall plane and size it to the intended rough opening.
   - Use semantic names containing facade side, floor, and sequence. Store ASCII custom properties such as `blendercodex_role`, `blendercodex_target_object`, `blendercodex_floor_index`, `blendercodex_opening_width`, `blendercodex_opening_height`, and `blendercodex_status`.
   - For default-size markers, set local display width/height to the role-specific door or window values and write the same authoritative values to the opening custom properties. Blender Empty `dimensions` may report zero, so validate the visual box from its display size and scale as well as from `blendercodex_opening_width`, `blendercodex_opening_height`, and `blendercodex_opening_sill_height`.
   - Route marker creation and application through the `architectural-openings` executor.

3. Continue by default.
   - Continue from markers to validated opening application in the same task.
   - Stop after markers only when the user explicitly asks to inspect, move, approve, or revise them first.

4. Re-read immediately before mutation.
   - Query the live marker collection again immediately before cutting.
   - User-moved marker transforms are authoritative.
   - User-deleted markers mean those openings were rejected. Do not recreate them.
   - Do not restore earlier positions or counts from the proposal.

5. Prepare the shell, then cut and standardize.
   - If the target is not interior-ready, first hollow or open the existing volume into a coherent thickness-aware shell. Preserve the approved exterior silhouette, roof, slabs, transforms, materials, and unrelated user edits; do not invent rooms or partitions unless requested.
   - Validate that the cavity is usable, the inner wall surfaces are continuous, and the intended opening zones have sufficient wall thickness before cutting individual openings.
   - Only after that validation, cut the current live door/window markers through both exterior and interior wall faces.
   - Standardize the outside wall, inside wall, jambs, sill, and head together so the opening is coherent through the wall thickness.
   - Never stop after cutting the visible exterior face, and never leave the apparent opening blocked by solid geometry behind it.
   - Preserve live opening dimensions and validate repeated members of the same window family against one shared width and height.
   - Hide or archive the marker collection after validation when it remains useful for revisions.

## Hard-Surface Topology Contract

Apply these rules to every hard-surface mesh creation, edit, cleanup, or topology rewrite.

### Preserve intent

- Treat existing geometry and scene changes as user-owned unless the user places them in scope.
- Capture a compact baseline before localized work: object and mesh identity, transforms, dimensions, topology counts, material slots, UV state, and a coordinate/edge/face signature for protected regions.
- Modify only the requested surfaces. Do not regenerate deleted elements, reset moved elements, or rewrite a clean region merely for uniformity.

### Build feature-aligned edge flow

- Place edges on real form changes: boundaries, openings, corners, creases, bevel limits, profile changes, and structural seams.
- For rectangular openings on planar walls, use horizontal sill and head bands plus vertical jamb and bay strips. Carry the same opening coordinates through exterior and interior wall faces.
- Keep opening topology facade-local. A jamb line stops at the sill/head band that needs it, and a sill/head line stops at the relevant wall boundary; do not project a building-wide Cartesian grid through unrelated facades, floors, slabs, ceilings, roofs, or blank wall regions.
- Treat a raw Boolean result as an intermediate only. Before delivery, rebuild the affected wall surfaces and reveals into the feature-aligned contract; the existence of a visually open hole is not acceptance evidence.
- On an orthogonal planar facade, reject any edge that diagonally bridges an opening corner, sill/head band, or jamb strip to a wall corner or unrelated vertex. Non-orthogonal edges are allowed only when they coincide with a genuine sloped, chamfered, curved, or mitered feature boundary such as a roof-contact line.
- Clean both wall sides and the reveals as one thickness-aware system. Reuse exact sill, head, and jamb coordinates on the exterior face, interior face, and connecting reveal faces so the opening has no offset or hidden transition.
- Prefer a minimal purposeful rectangular partition: first form continuous horizontal sill/head bands, then form vertical jamb/bay strips only inside the affected height interval. On blank planar regions, dissolve only subdivisions that neither complete a structural elevation loop nor improve regular quad flow.
- Preserve floor, slab, sill, head, and wall-base elevation rings when they wrap a corner or continue coherently through adjoining exterior, interior, gable, reveal, or thickness faces. Such rings are structural topology, not a forbidden global grid.
- Do not dissolve an edge solely because its two coplanar faces can form one rectangle. Keep a user-authored split when it closes a purposeful loop, avoids an oversized n-gon, or maintains editable quad bands; remove it only when it is isolated and featureless.
- When simplifying an existing mesh, merge only coplanar neighbors whose combined boundary remains a simple feature-aligned rectangle or rectilinear n-gon. Reject any merge that would need a bridge diagonal, self-touching loop, face hole, T-junction, or non-manifold edge.
- Prefer quads for regular strips and simple planar rectilinear n-gons for larger uninterrupted bands. N-gons must be planar, non-self-intersecting, and free of hidden duplicate edges.
- Remove Boolean-generated diagonals, triangle fans, skinny slivers, redundant coplanar edges, overlapping faces, and unnecessary poles when they do not describe the shape.
- Do not force orthogonal topology onto curved, sloped, triangular, chamfered, or intentionally irregular forms. Their edges must follow the real feature direction instead.
- Preserve purposeful hard edges, bevel support loops, panel seams, reveal edges, and intersections with neighboring geometry.

### Use a stable topology transaction

For a substantial rewrite:

1. Create an object-mode mesh copy or detached BMesh from the current mesh.
2. Apply the topology changes to the copy.
3. Validate the copy completely.
4. Assign the validated mesh to the object in one step.
5. Save and reopen the serialized file, then repeat the read-only validation.

Use direct Edit Mode operations only for small, local, low-risk edits. Do not combine a destructive `bmesh.update_edit_mesh(..., destructive=True)` rewrite with a manual `bpy.ops.ed.undo_push()` followed by an immediate save; use the copy-and-swap transaction instead.

### Maintain the UV contract

- Create or repair `UV_4m_world_standard` after topology changes.
- Make it the active and render UV layer.
- Keep one UV unit equal to four Blender/world units and allow coordinates outside 0-1.
- Verify sampled non-degenerate face-loop edges satisfy `(uv_edge_length * 4) / world_edge_length ~= 1` within a small numerical tolerance.

### Validate before completion

At minimum, verify:

- requested and protected geometry signatures;
- expected target faces or surface coverage;
- zero avoidable diagonal edges for orthogonal rectangular features;
- consistent outward/interior normals;
- zero wire edges, zero degenerate faces, zero accidental duplicate or overlapping geometry;
- classify boundary and non-manifold edges by source instead of requiring one blanket count: door thresholds that intentionally reach the wall base and other designed openings may remain boundaries, while wires, zero-length edges, accidental gaps, and disconnected fragments fail validation;
- completed openings remain unobstructed across multiple interior samples;
- targets that began without an interior cavity have a validated cavity and continuous inner wall surfaces before any door/window cut;
- every completed door/window opening connects the exterior to that cavity through the full wall thickness, with no remaining solid plug behind the visible opening;
- repeated opening families retain their agreed dimensions;
- `UV_4m_world_standard` is active/render and passes density sampling;
- the saved `.blend` can be reopened and returns the expected topology and metadata.

If validation fails, do not save over the approved main file. Keep the previous file intact, correct the copy, and validate again.
