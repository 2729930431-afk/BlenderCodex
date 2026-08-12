# 瓦片屋顶 (Tiled Roof) System

Read this reference whenever a user asks to make, repair, or revise a building roof. Unless the user specifies another construction, “屋顶” means the editable **瓦片屋顶** system below. The requested roof silhouette still controls whether the result is gabled, hipped, L-shaped, single-slope, or another form.

## Default Structure

- Build a coherent structural roof base with the intended roof planes, gables, eaves, ridges, hips, valleys, and thickness.
- Use separate editable pan-tile (`板瓦源`) and cover-tile (`筒瓦源`) source meshes. Repeat them with unapplied Array modifiers instead of hand duplication or a baked combined mesh.
- On a regular slope, put the along-eave Array first and the up-slope overlapping Array second. Keep ridge and edge tiles as independent editable sources/arrays.
- Parent tile, ridge, trim, and helper objects to the owning roof and keep them in the roof's existing collection placement. Use `UV_4m_world_standard` on every mesh.
- For a symmetric two-slope roof, also follow `roof-origin-mirroring.md`; its final Mirror comes after the tile Arrays.

## Verified L-Shaped Boolean Workflow

The authoritative evidence is the user-corrected `唐家.blend` L-shaped roof. Its essential lesson is that an L intersection is not solved by assigning one visible roof base as the Boolean target for every slope.

1. Build the coherent visible L-shaped structural roof base first.
2. Split tile generation into independent slope domains for each wing and orientation. Each domain owns a pan-tile source and a cover-tile source; do not force the whole L roof through one mirrored or shared tile array.
3. For each source, keep the modifier order `Array along eave -> Array up slope -> Boolean Difference`. The Boolean is last and remains unapplied.
4. At every concave/intersecting wing, construct a dedicated closed, manifold cutter solid from the roof volume that must remove the overlapping tiles. Extend the cutter fully through the tile thickness and beyond the intersection so it cannot leave coplanar slivers.
5. Choose the Boolean target independently per slope. Neighboring slopes may require different wing-specific cutter solids, while a slope whose correct trim coincides with the coherent visible base may use that base. Never copy one cutter target to every slope merely for consistency.
6. Use `DIFFERENCE` with the `MANIFOLD` solver when the cutter and tile modules satisfy the manifold requirement. Keep cutter objects editable but hidden from viewport and render after validation.
7. Keep ridge tiles independent from the slope-cutting Boolean unless the design specifically requires a trimmed ridge. End ridge arrays at the real L junction; do not let them cross or overshoot the valley/hip intersection.

## Acceptance Checks

- Every visible roof slope has editable pan-tile and cover-tile sources; Arrays are unapplied.
- Every L-intersection tile source has the exact modifier order `ARRAY, ARRAY, BOOLEAN` and a deliberately selected Boolean target.
- Cutter solids are closed/manifold, extend through the complete tile envelope, remain editable, and are hidden from final display/render.
- Evaluated tiles stop cleanly at their owning slope boundaries: no floating remnants, crossed tile strips, overlap through another wing, coplanar slivers, or missing strips beside the valley.
- Structural base, tile sources, ridge/edge sources, and cutters keep correct ownership and world transforms.
- `UV_4m_world_standard` is active/render where applicable. Save and reopen the `.blend`, then re-check modifier targets and evaluated bounds.

## Limits

- Do not use this default when the user requests metal sheet, concrete slab, thatch, membrane, glass, or another non-tile roof.
- Do not assume Boolean is needed on a simple uninterrupted slope.
- Do not derive cutter choice from object names alone. Inspect the actual intersecting volumes and the intended retained side of each slope.
