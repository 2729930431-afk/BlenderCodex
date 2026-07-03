# Floor Inference And Stairs

Read this reference when implementing internal building structure, especially when the scene has no existing floor markers.

## Data To Extract First

Use Blender Python through the live bridge or background runner to collect:

- Scene units, file path, collection hierarchy, and existing custom properties.
- World bounding boxes for visible mesh and curve objects.
- Envelope candidates: large walls, facade panels, roof caps, bases, parapets, floor bands, and structural masses.
- Opening candidates: windows, doors, storefront panes, loading doors, shutters, dark cavities, and frame modules.
- Stair hints: existing stairwell window stacks, service doors, elevator/core-like masses, shafts, ladders, or vertical circulation labels.
- Existing floor markers: objects, empties, collections, or scene custom properties with floor/storey/level names or `blendercodex_floor_*` keys.

Return the raw analysis as structured data before committing geometry. The analysis should be strong enough to explain why each floor exists.

## Opening Classification

Use a mix of geometry, names, collections, and materials:

- Window tokens include `window`, `glass`, `pane`, `frame`, and local language equivalents in the project.
- Door tokens include `door`, `entrance`, `gate`, `shutter`, `loading`, and local language equivalents in the project.
- Merge fragments that share a base prefix, collection, facade side, and close bounding boxes. Broken panes, mullions, sill bars, and dark cavities should describe one opening, not many floors.
- Estimate facade side from the object center relative to the building bounding box and from the thinnest bounding-box axis.
- Ignore vegetation, pipes, railings, wires, signs, antennas, loose debris, and tiny decorative fragments when deriving floors.

## Floor Derivation

Prefer existing markers. When they are absent:

1. Group opening candidates by building mass or facade when the building has multiple volumes.
2. Cluster opening center heights. Use names, facade bands, and repeated rows to stabilize the clusters.
3. Treat exterior doors near the base as ground-floor evidence. Large storefront or shutter openings usually belong to floor 1.
4. For each row, estimate sill, center, and head heights. Floor slabs should sit below sills and above the previous row's heads, not through openings.
5. Infer floor bands from the base z, roof/parapet z, and ordered opening rows. If the top floor has no windows, create a final band only when roof height and massing clearly support it.
6. Validate row spacing. Adjacent clear heights should be plausible and similar unless there is a mezzanine, tower, or stairwell.
7. Record confidence and source per floor. Use `name_inference` only as supporting evidence unless object names clearly encode floor numbers.

For staggered stairwell windows, do not treat every staggered small window as a separate floor. Tie them to the nearest main floor bands unless the facade clearly shows split levels.

## Planning Geometry

Before creating geometry, prepare a floor plan object with:

- `floor_index`
- `z_min`, `z_max`, `slab_z`, `clear_height`
- `opening_refs`
- `stairwell_xy`
- `stair_direction`
- `door_access_refs`
- `confidence`
- `notes`

If evidence conflicts, return the plan and ask the user before adding geometry. Otherwise create the structure directly.

## Structural Output

Create only the internal structural shell:

- Floor slabs and roof/attic access slab when appropriate.
- Simple core walls or shear walls where they do not block exterior openings.
- Stairwell voids through slabs.
- Stair flights, landings, and simple side stringers or guard edges when needed for readability.
- Door-aligned wall gaps or access clearances.
- Integrated or connected structural meshes where a continuous body will be expanded later; avoid solving house bodies by stacking disconnected cube primitives.

Do not add interior furniture, appliances, wall finishes, ceiling panels, lights, decorations, room labels, carpets, or small props.

## Stair Rules

- Prefer a stair location suggested by the model: vertical small-window stacks, service doors, side/back facade bays, tower masses, or existing core-like blocks.
- Keep the stairwell footprint away from important exterior windows and doors.
- Connect every adjacent floor pair unless the user asks for partial structure.
- Use repeated components: an Array modifier on a tread/riser module, linked duplicate modules, or a generated repeated mesh. Preserve a component/modifier relationship when practical.
- Use plausible values in scene units: consistent riser count per floor span, uniform tread depth, landings at floor elevations, and a clear stairwell opening through the slabs.
- If floor heights vary, compute a separate stair run per span rather than forcing one repeated count across all floors.

## Marker And Collection Rules

Use existing collection taxonomy when editing a project. If no taxonomy exists, create:

- `Internal Structure`
- `Floor Markers`
- `Stair Structure`
- One per-floor structure collection, such as `Floor 01 Structure`

Every generated structural object should carry:

- `blendercodex_structure_role`
- `blendercodex_floor_index` for single-floor objects
- `blendercodex_floor_span` for stairs, cores, or voids spanning floors

Every marker should carry the marker contract from `SKILL.md`.

## Verification

After generating or editing, use Blender Python to verify:

- Floor marker count equals inferred floor count.
- Each floor has at least one slab or intentional structural element.
- No generated slab or wall intersects the bounding box of an exterior door or window opening.
- Stair flights and landings reach the expected floor elevations.
- Stairwell voids line up through affected slabs.
- Generated objects live in semantic collections and have floor custom properties.

Return unresolved assumptions in the final result instead of hiding them.
