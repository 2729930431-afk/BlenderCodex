# FBX and Unity Hierarchy Safety

Read this reference whenever a Blender task changes object origins or parenting in a hierarchy that will be exported to FBX and imported by Unity. It applies to ordinary mesh/empty object hierarchies. Armatures, bones, constraints, and animation-driven transforms require their specialized workflow.

## Failure Mode

Blender evaluates an object's world transform as:

`parent.matrix_world @ matrix_parent_inverse @ matrix_basis`

A non-identity `matrix_parent_inverse` can keep an object visually fixed after a parent or origin change, but FBX and Unity do not preserve Blender's parent-inverse semantics as a separate concept. Exporters bake the compensation into local transforms. With nested children and unit conversion, this can produce alternating `100`/`0.01` scales, unexpected local positions, or a hierarchy that only looks correct while one roof is left unparented.

## Export-Safe Normalization

1. Capture evidence before mutation.
   - Record each protected object's parent, `matrix_world`, object scale, evaluated world bounds, modifiers, materials, and collections.
   - Identify the intended ownership hierarchy. Temporary unparenting is not part of the final model.

2. Restore intended parents while preserving world space.
   - Save the child's world matrix before changing `parent`.
   - Assign the intended parent, set `matrix_parent_inverse` to the identity matrix, and derive the real local matrix as `parent.matrix_world.inverted_safe() @ saved_world`.

3. Normalize the full ordinary object hierarchy top-down.
   - Save every object's world matrix before normalization.
   - Sort parented objects by hierarchy depth, shallowest first.
   - For each object, set `matrix_parent_inverse = Matrix.Identity(4)` and `matrix_basis = parent.matrix_world.inverted_safe() @ saved_world`.
   - Update the view layer after each parent level or object so descendants read the normalized parent matrix.

4. Validate in Blender.
   - Every ordinary parented export object has an identity `matrix_parent_inverse`.
   - Protected world matrices and evaluated world bounds remain unchanged within floating-point tolerance.
   - Intended parents, collections, modifier order, materials, and UVs remain unchanged.
   - Do not apply Array or Mirror modifiers merely to simplify export.

## Stable FBX Export

Use one explicit scale policy for plugin-controlled exports instead of mixing scene-unit compensation with per-node compensation:

- `global_scale=1.0`
- `apply_unit_scale=True`
- `apply_scale_options='FBX_SCALE_NONE'`
- `use_space_transform=True`
- `bake_space_transform=False`
- `axis_forward='-Z'`
- `axis_up='Y'`
- `bake_anim=False` unless animation is explicitly required

Include every object type required to preserve the intended hierarchy. Export to a temporary FBX first when overwriting a production asset.

## Round-Trip Acceptance

- Import the temporary FBX into a clean Blender process and verify the intended parent chain and representative local/world transforms at every depth.
- Reimport the production FBX in Unity and inspect the live scene or prefab hierarchy.
- Confirm that roof bases remain children of buildings and tiles/ridges remain children of roofs.
- Representative nested roof-owned objects should have unit local scale; no level should receive an extra `0.01` scale because its parent used a Blender parent-inverse compensation.
- Compare world-space placement and visible dimensions with the pre-export baseline. Unity may use a top-level unit-conversion transform; that is acceptable only when descendants remain internally consistent and the world-space result is unchanged.
- Save and reopen the `.blend`, then repeat the identity-parent-inverse and hierarchy checks. Do not save an unrelated dirty Unity scene merely to validate the imported asset.

## Do Not Apply Blindly

Do not normalize armatures, bones, constraint-driven objects, animation rigs, or intentionally nonstandard transforms with this object-only recipe. Route those through their specialized workflow and validate animation as well as static transforms.
