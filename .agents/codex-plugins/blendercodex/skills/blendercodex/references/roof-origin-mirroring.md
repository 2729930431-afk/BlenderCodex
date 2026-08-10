# Roof Origin and Tile Mirroring

Read this reference when creating or converting a symmetric two-slope tiled roof. It records a user-verified workflow from `花山养殖场.blend`: the parking area, residence, and guesthouse were authored manually with a building-centered mirror system; the same pattern was then accepted after application to the gate, poultry area, and livestock area.

## Durable Rule

For a truly symmetric two-slope gabled roof, keep one authoritative slope's pan-tile and cover-tile sources editable. Build repetition with unapplied Array modifiers and place one unapplied Mirror modifier after the Arrays. Use the owning building root as the Mirror object so moving, rotating, or duplicating the building carries the symmetry plane with it.

Place the building root object's origin at the roof-plan symmetry center in X/Y and at the building ground level in Z. Moving the origin must not move the building mesh, roof base, tiles, ridge, or any other descendant in world space. Keep the roof base directly parented to the building and keep tile arrays and ridge tiles directly parented to the roof in the roof's existing collections.

## Conversion Workflow

1. Inspect before editing.
   - Identify the building root, roof base, ridge direction, symmetry axis, pan-tile arrays, cover-tile arrays, and ridge-tile arrays.
   - Compare the two evaluated slopes. Confirm that roof pitch, eaves, row counts, materials, penetrations, and silhouette are intended to be symmetric.
   - Treat the user-edited side as authoritative. Otherwise keep the cleaner source side; do not hard-code west, east, north, or south as the source.

2. Capture protected state.
   - Record world-space vertex signatures, object transforms, parent relationships, material slots, UV layers, modifier order, and evaluated bounds for the building, roof, tiles, and unrelated descendants.
   - Do not create a backup `.blend` unless the user requests one.

3. Relocate the building origin without moving geometry.
   - Derive the mirror plane from the roof base's world-space plan bounds or another verified roof-center reference.
   - Put the building origin at that X/Y center and the building ground Z.
   - Transform the building mesh by the inverse origin delta and update direct-child parent inverses so all protected world matrices remain unchanged.
   - Do not reset a roof or tile child's world transform merely to make local values look cleaner.

4. Consolidate the slopes.
   - Keep the authoritative pan-tile and cover-tile objects with their unapplied Array modifiers.
   - Add one Mirror modifier after all Array modifiers. Enable only the required mirror axis and set `mirror_object` to the owning building root.
   - Keep ridge tiles independent; a centered ridge does not need the slope Mirror.
   - Remove the redundant opposite-slope objects only after confirming that the mirrored evaluated result covers the intended opposite slope.

5. Preserve hierarchy and editability.
   - Keep the roof base as a direct child of the building.
   - Keep pan tiles, cover tiles, ridge tiles, trims, and other roof-owned parts as direct children of the roof in the same collection or collections as that roof.
   - Do not apply Arrays or Mirror, join the evaluated tiles, or create a dedicated one-roof collection.

## Validation

- Building and descendant world-space geometry remains unchanged within floating-point tolerance, except for the intentionally replaced opposite-slope evaluated tiles.
- The building origin matches the verified roof-plan symmetry center and ground Z.
- The modifier order is `Array ... -> Mirror`; Arrays and Mirror remain unapplied.
- The Mirror uses the owning building root, enables exactly the required axis, and produces symmetric evaluated bounds about that root.
- Each converted roof keeps one pan-tile source, one cover-tile source, and independent ridge tiles as direct children.
- Materials and `UV_4m_world_standard` remain active/render with unchanged world density.
- Raw source meshes have zero wire edges and zero degenerate faces; boundary and non-manifold counts do not worsen.
- Save and reopen the `.blend`, then repeat the hierarchy, origin, modifier, symmetry, UV, and mesh-health checks.

## Do Not Apply

Keep separate slope systems when the roof is asymmetric or contains hip geometry, dormers, chimneys, openings, slope-specific trim, deliberate damage, different materials, unequal pitches, or other features that must not mirror. If another system requires the building origin to stay elsewhere, preserve that requirement and use a user-approved dedicated mirror reference instead of silently moving the building origin.
