import json
from pathlib import Path
import sys
import tempfile
import uuid

import bpy


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
OPENING = PLUGIN_ROOT / "skills" / "architectural-openings" / "scripts" / "opening_runtime.py"
ROOF = PLUGIN_ROOT / "skills" / "tiled-roof" / "scripts" / "tiled_roof_runtime.py"
VALIDATION = PLUGIN_ROOT / "skills" / "model-validation" / "scripts" / "model_validation_runtime.py"


def load_runtime(path):
    namespace = {"__file__": str(path)}
    exec(compile(path.read_bytes(), str(path), "exec"), namespace, namespace)
    return namespace["dispatch"]


bpy.ops.wm.read_factory_settings(use_empty=True)
opening = load_runtime(OPENING)
roof = load_runtime(ROOF)
validation = load_runtime(VALIDATION)

for invalid_marker in ({"target": "Wall"}, {"role": "vent", "target": "Wall"}, {"role": "window"}, {"role": "door", "target": "MissingWall"}):
    try:
        opening("markers_create", {"markerCollection": "InvalidOpenings", "markers": [invalid_marker]})
    except ValueError:
        pass
    else:
        raise AssertionError("marker creation accepted an invalid marker")
assert not bpy.data.collections["InvalidOpenings"].all_objects

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1.5), scale=(2, 2, 1.5))
wall = bpy.context.object
wall.name = "Wall"
wall["blendercodex_test_array"] = [1.0, 2.0, 3.0]
signature = validation("signature", {"objects": ["Wall"]})
assert signature["ok"] and signature["objects"][0]["payload"]["custom_properties"]["blendercodex_test_array"] == [1.0, 2.0, 3.0]
markers = opening("markers_create", {
    "markerCollection": "Openings",
    "markers": [
        {"name": "Door", "role": "door", "target": "Wall", "axis": "Y", "location": (-0.8, -2, 1.05), "rotation": (0, 0, 0)},
        {"name": "Window", "role": "window", "target": "Wall", "axis": "Y", "location": (0.8, -2, 1.65), "rotation": (0, 0, 0)},
    ],
})
assert [(round(row["width"], 3), round(row["height"], 3), row["sill"]) for row in markers["markers"]] == [(1.0, 2.1, 0.0), (1.2, 1.5, 0.9)]
# A six-quad closed mesh whose face is not on an AABB plane must not be
# silently flattened to a bounding box by automatic inference.
wall.data.vertices[0].co.x += 0.25
try:
    opening("apply", {"markerCollection": "Openings", "wallThickness": 0.2, "save": False})
except ValueError:
    pass
else:
    raise AssertionError("automatic inference accepted a non-AABB box")
wall.data.vertices[0].co.x -= 0.25
wall.data.update()
door_marker = bpy.data.objects["Door"]
for invalid_role in (None, "vent"):
    if invalid_role is None:
        del door_marker["blendercodex_role"]
    else:
        door_marker["blendercodex_role"] = invalid_role
    for action, parameters in (
        ("markers_inspect", {"markerCollection": "Openings"}),
        ("apply", {"markerCollection": "Openings", "save": False}),
    ):
        try:
            opening(action, parameters)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{action} accepted a missing or unknown role")
door_marker["blendercodex_role"] = "door"
applied = opening("apply", {"markerCollection": "Openings", "wallThickness": 0.2, "save": False})
assert applied["ok"] and applied["markers"] == 2
health = applied["reports"][0]["health"]
assert health["wire_edges"] == health["boundary_edges"] == health["nonmanifold_edges"] == health["degenerate_faces"] == 0
assert applied["reports"][0]["uv"]["ok"]

# Reject unsupported multi-material walls before any candidate swap.
extra_material = bpy.data.materials.new("ExtraWallMaterial")
second_material = bpy.data.materials.new("SecondWallMaterial")
wall.data.materials.append(extra_material)
wall.data.materials.append(second_material)
multi_material_mesh = wall.data
try:
    opening("apply", {
        "markerCollection": "Openings",
        "wallThickness": 0.2,
        "componentsByObject": {"Wall": [{"id": "wall", "bounds": [-2, 2, -2, 2, 0, 3]}]},
        "save": False,
    })
except ValueError as exc:
    assert "Multi-material" in str(exc)
else:
    raise AssertionError("multi-material wall was silently remapped")
assert wall.data is multi_material_mesh
wall.data.materials.clear()

# A failed save must roll back both mesh data and marker/collection state.
rollback_mesh = wall.data
opening_collection = bpy.data.collections["Openings"]
opening_collection.hide_viewport = False
opening_collection.hide_render = False
for marker in opening_collection.all_objects:
    marker["blendercodex_status"] = "ready"
door_axis_before_failure = door_marker.get("blendercodex_wall_axis")
wall_bound_box = [tuple(corner) for corner in wall.bound_box]
rollback_bounds = [
    min(corner[0] for corner in wall_bound_box), max(corner[0] for corner in wall_bound_box),
    min(corner[1] for corner in wall_bound_box), max(corner[1] for corner in wall_bound_box),
    min(corner[2] for corner in wall_bound_box), max(corner[2] for corner in wall_bound_box),
]
missing_parent = Path(tempfile.gettempdir()) / f"missing-blendercodex-parent-{uuid.uuid4().hex}"
try:
    opening("apply", {
        "markerCollection": "Openings",
        "wallThickness": 0.2,
        "componentsByObject": {"Wall": [{"id": "wall", "bounds": rollback_bounds}]},
        "save": True,
        "filepath": str(missing_parent / "opening.blend"),
    })
except RuntimeError:
    pass
else:
    raise AssertionError("opening executor unexpectedly saved to a missing parent")
assert wall.data is rollback_mesh
assert not opening_collection.hide_viewport and not opening_collection.hide_render
assert all(marker.get("blendercodex_status") == "ready" for marker in opening_collection.all_objects)
assert door_marker.get("blendercodex_wall_axis") == door_axis_before_failure

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
owner = bpy.context.object
owner.name = "Owner"
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
roof_base = bpy.context.object
roof_base.name = "RoofBase"
roof_result = roof("build", {
    "domains": [{
        "roofObject": "RoofBase",
        "ownerObject": "Owner",
        "kind": "independent_slope",
        "eave": [0, 0, 0],
        "ridge": [0, 4, 2],
        "ridgeDirection": [1, 0, 0],
        "ridgeSpan": 6,
    }],
    "save": False,
})
assert roof_result["ok"], roof_result
for row in roof_result["validation"]["reports"]:
    assert row["health"]["wire_edges"] == row["health"]["boundary_edges"] == row["health"]["nonmanifold_edges"] == 0
    assert row["uv"]["ok"] and row["order_ok"] and row["contract_ok"]

# Replacement is transactional: a failed save restores the previous roof system.
bpy.ops.mesh.primitive_cube_add(size=0.25)
old_roof_tiles = bpy.context.object
old_roof_tiles.name = "OldRoofTiles"
old_roof_tiles["blendercodex_roof_system"] = "blendercodex_tiled_roof_v1"
old_roof_tiles["blendercodex_roof_owner"] = "Owner"
old_roof_tiles.parent = roof_base
old_mesh = old_roof_tiles.data
previous_roof_objects = {
    obj.name: obj
    for obj in bpy.data.objects
    if obj.get("blendercodex_roof_system") == "blendercodex_tiled_roof_v1"
    and (
        (obj.parent is not None and obj.parent.name == "RoofBase")
        or obj.get("blendercodex_roof_owner") == "Owner"
    )
}
bpy.ops.mesh.primitive_cube_add(size=0.2)
other_owner = bpy.context.object
other_owner.name = "OtherOwner"
other_roof_tiles = other_owner
other_roof_tiles["blendercodex_roof_system"] = "blendercodex_tiled_roof_v1"
other_roof_tiles["blendercodex_roof_owner"] = "OtherOwner"
# Existing shared-name materials are reused but never overwritten.
shared_material = bpy.data.materials["青灰陶瓦"]
shared_color = tuple(shared_material.diffuse_color)
unrelated = bpy.data.objects.new("UnrelatedMaterialUser", bpy.data.meshes.new("UnrelatedMaterialMesh"))
bpy.context.scene.collection.objects.link(unrelated)
unrelated.data.materials.append(shared_material)
try:
    roof("build", {
        "domains": [{
            "roofObject": "RoofBase",
            "ownerObject": "Owner",
            "kind": "independent_slope",
            "eave": [0, 0, 0],
            "ridge": [0, 4, 2],
            "ridgeDirection": [1, 0, 0],
            "ridgeSpan": 6,
        }],
        "replaceExisting": True,
        "save": True,
        "filepath": str(missing_parent / "roof.blend"),
    })
except RuntimeError:
    pass
else:
    raise AssertionError("roof executor unexpectedly saved to a missing parent")
assert bpy.data.objects.get("OldRoofTiles") is old_roof_tiles
assert old_roof_tiles.data is old_mesh and old_roof_tiles.users_collection
assert bpy.data.objects.get("OtherOwner") is other_roof_tiles and other_roof_tiles.users_collection
assert tuple(shared_material.diffuse_color) == shared_color
assert all(bpy.data.objects.get(name) is obj and obj.users_collection for name, obj in previous_roof_objects.items())
assert all(bpy.data.objects.get(name) is obj for name, obj in previous_roof_objects.items())

print(json.dumps({"ok": True, "opening": applied, "roof": roof_result}, ensure_ascii=False))
