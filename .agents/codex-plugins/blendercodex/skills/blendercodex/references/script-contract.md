# BlenderCodex Code Contract

Load this before writing generated Blender bpy code, whether it will be saved as a `.py` file or run through BlenderCodex's temporary internal runner.

## Required Behavior

- The generated code must run inside Blender through either the temporary internal path or a kept script:

```powershell
python scripts/run_blender_model.py --code-file - --output-blend output.blend
python scripts/run_blender_model.py script.py --output-blend output.blend
```

- Internally both paths execute Blender as:

```text
blender --factory-startup -b --python script.py -- --output-blend output.blend
```

- Parse arguments after Blender's `--` separator:

```python
def parse_output_path(default_path):
    import argparse
    import os
    import sys

    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-blend")
    args = parser.parse_args(argv)
    return args.output_blend or os.environ.get("BLENDERCODEX_OUTPUT_BLEND") or default_path
```

- Clear the startup scene:

```python
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
```

- Do not create cameras or lights unless requested.
- If practical, stamp the scene before saving so future captures can identify the code source:

```python
import datetime

bpy.context.scene["blendercodex_source_script"] = str(SCRIPT_PATH)
bpy.context.scene["blendercodex_generated_at_utc"] = datetime.datetime.utcnow().isoformat() + "Z"
```

- Save with `bpy.ops.wm.save_as_mainfile(filepath=str(output_path))`.

## Recommended Helpers

- `get_or_create_collection(name, parent=None)` to keep all objects categorized.
- `make_material(name, color)` to create reusable base-color materials.
- `link_to_collection(obj, collection)` to avoid objects lingering only in the scene root.
- `create_mesh_object(name, vertices, faces, material, collection)` for continuous custom meshes.
- `unwrap_mesh(obj)` to select the object, enter edit mode, run UV unwrap or smart project, and return to object mode.

## UV Guidance

- For box-like architectural pieces, create sensible planar/cubic UVs or run smart projection with a moderate angle limit.
- For curved forms, keep topology regular and unwrap after normals are recalculated.
- Apply object transforms before unwrap when scale would distort UVs:

```python
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
```

## Verification Checklist

- The generated `.blend` exists in the requested directory.
- The generated `.py` exists only if the user explicitly requested a kept script.
- Existing output `.blend` files were compared temporarily with `scripts/capture_blend_state.py capture-edits` or by the default guard in `scripts/run_blender_model.py`, unless the user explicitly asked to skip comparison.
- Blender execution exits successfully.
- The scene contains named Chinese collections and objects.
- Mesh objects have material slots and UV layers.
