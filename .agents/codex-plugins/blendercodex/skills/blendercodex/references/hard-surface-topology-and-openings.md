# Hard-Surface Topology and Opening Rules

Read this reference before every hard-surface mesh operation. It is mandatory for new models and edits, including architecture, manufactured props, machines, vehicles, furniture, Boolean cleanup, retopology, bevel preparation, UV repair after topology changes, and window/door opening work.

## Window and Wall-Opening Approval Gate

When the user requests windows or comparable wall openings:

1. Inspect first.
   - Read the live or saved mesh, wall thickness, floor bands, current opening rows, doors, roof/slab conflicts, corners, and facade rhythm.
   - Use plausible clearances from corners, slabs, doors, roof edges, and adjoining masses.
   - Default to one shared rough width and height for a repeated window family. Use multiple sizes only when the user or design evidence requires them.

2. Mark only.
   - Create empties in a pending collection such as `窗位标记_待确认`.
   - Align each empty to its wall plane and size it to the intended rough opening.
   - Use semantic names containing facade side, floor, and sequence. When practical, store ASCII custom properties such as `blendercodex_role=window_marker`, `blendercodex_target_object`, `blendercodex_floor_index`, `blendercodex_opening_width`, `blendercodex_opening_height`, and `blendercodex_status=pending_confirmation`.
   - Do not modify the wall mesh during this phase.

3. Wait for explicit confirmation.
   - Present the markers for inspection and stop before cutting geometry.
   - A screenshot, viewport view, or concise facade/floor/size summary may be used, but it does not replace confirmation.

4. Re-read after confirmation.
   - Query the live marker collection again immediately before cutting.
   - User-moved marker transforms are authoritative.
   - User-deleted markers mean those openings were rejected. Do not recreate them.
   - Do not restore earlier positions or counts from the proposal.

5. Cut and standardize as one operation.
   - Cut only confirmed markers.
   - Standardize the outside wall, inside wall, jambs, sill, and head together so the opening is coherent through the wall thickness.
   - Preserve confirmed opening dimensions and validate repeated members of the same window family against one shared width and height.
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
- boundary and non-manifold counts do not worsen, except for intentional openings, and any repairs are reported;
- confirmed openings remain unobstructed across multiple interior samples;
- repeated opening families retain their agreed dimensions;
- `UV_4m_world_standard` is active/render and passes density sampling;
- the saved `.blend` can be reopened and returns the expected topology and metadata.

If validation fails, do not save over the approved main file. Keep the previous file intact, correct the copy, and validate again.
