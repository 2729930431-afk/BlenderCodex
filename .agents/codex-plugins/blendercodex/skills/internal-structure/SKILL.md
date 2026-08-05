---
name: internal-structure
description: Use when adding or generating internal building structure in BlenderCodex projects, including floor slabs, floor bands, stair flights, landings, stairwell voids, structural cores, door-aligned openings, or reusable floor markers. Trigger for requests about internal structure, interiors as structure only, floors, storeys, levels, stairs, staircases, floor-aware building modeling, or inferring floors from exterior windows and doors. The workflow reads scene geometry first, respects exterior window and door placement, infers floors from existing markers or opening rows, leaves floor markers for future modeling, and avoids decorative interior content.
---

# Internal Structure

## Overview

Use this skill with BlenderCodex when a building needs internal structural logic: floor slabs, stair circulation, stairwell openings, simple cores, and durable floor markers. The output is structure only; do not add furniture, room dressing, wall finishes, props, lighting, or decorative interiors unless the user explicitly asks.

## Coordination

- Also use the `blendercodex` skill for Blender file execution, RPC bridge startup, live scene inspection, saving rules, and existing model preservation.
- Before creating or changing a window, door, wall opening, shell, slab, stair, landing, core, or other hard-surface topology, read sibling reference `../blendercodex/references/hard-surface-topology-and-openings.md` and apply its confirmation, topology, transaction, and validation rules.
- For an existing or currently open `.blend`, use the temporary live RPC bridge and inspect the real scene before generating or changing internal structure.
- For a new building model, include floor markers during initial generation so later windows, doors, facade bands, and internal structure share the same floor reference.
- If the existing house body was made from stacked cube primitives, do not continue that pattern. Add internal structure as integrated floor slabs, stairwell voids, and connected structural modules; for future buildings, prefer an interior-ready shell or connected main-body mesh.
- Read `references/floor-inference-and-stairs.md` before writing final Blender Python when floor markers are absent, exterior openings conflict, the building has multiple masses, or the stair layout is nontrivial.

## Workflow

1. Read model structure data.
   - Capture scene file path, units, collections, visible object names, object types, materials, world bounding boxes, dimensions, and custom properties.
   - Classify envelope, roof/base, facade panels, windows, doors, large openings, existing stair hints, and existing floor markers.
   - Prefer geometry and custom properties over object names, but use names and collection taxonomy as supporting evidence.

2. Derive floor data.
   - If floor markers already exist, load them and validate that exterior windows and doors sit within the expected floor bands.
   - If markers are absent, infer floors from exterior window and door rows, facade bands, slab-like features, floor names in objects, and the building envelope height.
   - Keep floor slabs below sill bands and above door/window heads so floors do not cut across exterior openings.
   - Treat door locations as access openings that internal walls or structural cores must not block.

3. Plan before creating geometry.
   - Build a compact floor plan data object with floor index, z-range, slab z, clear height, associated openings, stairwell location, and door access route.
   - Choose stair placement from structure evidence: existing vertical small-window stacks, service doors, side/back facades, core-like masses, or an unobtrusive bay that avoids exterior openings.
   - Ask the user only if the scene evidence supports incompatible floor counts or no safe stair route.

4. Create internal structure.
   - Put generated objects in semantic collections such as `Internal Structure`, `Floor Markers`, per-floor structure collections, and `Stair Structure`, or localized equivalents that match the project.
   - Create slabs, simple structural walls/cores, stairwell cutouts, stair flights, and landings. Keep wall and slab placement aligned to the derived floor bands and exterior openings.
   - Build stairs from repeatable components, array modifiers, or generated repeated modules. Store enough custom properties or modifiers so the stair can be adjusted later.
   - Avoid placing opaque structure across windows, exterior doors, loading doors, storefront openings, or existing clear access paths.

5. Leave durable markers.
   - Add a floor marker collection if missing.
   - Store floor index, z-range, slab elevation, clear height, source, and related openings on marker objects and/or scene custom properties with stable ASCII keys.
   - Tag generated slabs, cores, stairs, landings, and stairwell cutouts with their floor index or floor span.

6. Verify.
   - Return a structured summary from Blender Python: inferred floor count, floor z-ranges, marker count, stair start/end floors, created object counts, and any unresolved assumptions.
   - Check that every floor has a marker, every created slab is assigned to a floor, stairs connect adjacent levels, and door openings remain unblocked.
   - Save only when the user requested persistent changes or when following the normal create-model save path.

## Marker Contract

Use stable custom property keys so later skills and edits can reuse the floor data:

- `blendercodex_floor_schema`: string, recommended value `1`
- `blendercodex_floor_index`: integer starting at 1
- `blendercodex_floor_z_min`, `blendercodex_floor_z_max`, `blendercodex_floor_slab_z`: floats in scene units
- `blendercodex_floor_source`: `marker`, `window_rows`, `facade_bands`, `name_inference`, or `manual`
- `blendercodex_opening_refs`: short list or string of related window/door object names
- `blendercodex_structure_role`: `floor_marker`, `slab`, `core_wall`, `stair_flight`, `landing`, or `stairwell_void`

## Resources

- `references/floor-inference-and-stairs.md`: detailed floor inference, marker, stair, and verification rules for building internal structures.
