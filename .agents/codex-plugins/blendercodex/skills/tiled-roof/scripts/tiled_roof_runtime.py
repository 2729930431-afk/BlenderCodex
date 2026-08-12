"""Blender runtime for editable pan-, cover-, ridge-, and edge-tile systems."""

from __future__ import annotations

import math
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATION_DIR = SCRIPT_DIR.parents[1] / "model-validation" / "scripts"
for directory in (SCRIPT_DIR, VALIDATION_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
from geometry_core import UV_LAYER_NAME, planar_uv_4m  # noqa: E402
from model_validation_runtime import mesh_health, uv_density  # noqa: E402
from tiled_roof_core import TRADITIONAL_GRAY_V1, build_tile_module, plan_roof_field  # noqa: E402


SYSTEM_TAG = "blendercodex_tiled_roof_v1"


def _vector(value):
    return Vector(tuple(float(item) for item in value))


def _material(name, color):
    existing = bpy.data.materials.get(name)
    if existing is not None:
        return existing
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    node = material.node_tree.nodes.get("Principled BSDF") if material.node_tree else None
    if node:
        node.inputs["Base Color"].default_value = color
        node.inputs["Roughness"].default_value = 0.86
    return material


def _mesh_from_spec(name, spec):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(spec.vertices, [], spec.faces)
    mesh.update(calc_edges=True)
    uv = mesh.uv_layers.new(name=UV_LAYER_NAME)
    mesh.uv_layers.active = uv
    uv.active_render = True
    identity = ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    projected = planar_uv_4m(spec.vertices, spec.faces, identity)
    for polygon, values in zip(mesh.polygons, projected):
        for loop_id, value in zip(polygon.loop_indices, values):
            uv.data[loop_id].uv = value
    return mesh


def _array(obj, name, count, offset):
    modifier = obj.modifiers.new(name, "ARRAY")
    modifier.count = int(count)
    modifier.use_relative_offset = False
    modifier.use_constant_offset = True
    modifier.constant_offset_displace = tuple(float(value) for value in offset)
    return modifier


def _source_object(name, mesh, roof, material, role, owner):
    obj = bpy.data.objects.new(name, mesh)
    collections = list(roof.users_collection) or [bpy.context.scene.collection]
    for collection in collections:
        collection.objects.link(obj)
    obj.parent = roof
    # Module vertices are authored in world coordinates. Preserve them while
    # parenting under an arbitrarily transformed roof base.
    obj.matrix_parent_inverse = roof.matrix_world.inverted()
    obj["blendercodex_roof_system"] = SYSTEM_TAG
    obj["blendercodex_roof_role"] = role
    obj["blendercodex_roof_owner"] = owner.name
    mesh.materials.append(material)
    return obj


def _build_domain(row, params, created):
    roof = bpy.data.objects.get(str(row["roofObject"]))
    owner = bpy.data.objects.get(str(row["ownerObject"]))
    if roof is None or owner is None:
        raise ValueError(f"Roof or owner object not found: {row}")
    kind = str(row.get("kind") or "gable_mirror")
    if kind not in ("gable_mirror", "independent_slope", "l_boolean"):
        raise ValueError(f"Unsupported tiled-roof algorithm: {kind}")
    eave = _vector(row["eave"])
    ridge = _vector(row["ridge"])
    ridge_dir = _vector(row["ridgeDirection"]).normalized()
    up_slope = (ridge - eave).normalized()
    normal = up_slope.cross(ridge_dir)
    if normal.z < 0:
        normal.negate()
    normal.normalize()
    slope_span = (ridge - eave).length
    ridge_span = float(row["ridgeSpan"])
    plan = plan_roof_field(slope_span, ridge_span)
    profile = TRADITIONAL_GRAY_V1
    start = -ridge_span * 0.5 + profile.pan_width * 0.5
    pan_center = eave + up_slope * (profile.pan_length * 0.5) + ridge_dir * start + normal * 0.028
    pan_spec = build_tile_module(profile.pan_length, profile.pan_width, profile.pan_thickness, profile.pan_curvature, False, 6, pan_center, up_slope, ridge_dir, normal)
    pan_mesh = _mesh_from_spec(f"{roof.name}.pan-source", pan_spec)
    pan = _source_object(f"{roof.name}.板瓦源", pan_mesh, roof, _material("青灰陶瓦", (0.075, 0.095, 0.105, 1.0)), "pan_tile", owner)
    created.append(pan)
    _array(pan, "沿檐口阵列", plan["pan_columns"], ridge_dir * plan["column_step"])
    _array(pan, "沿坡向叠瓦阵列", plan["pan_rows"], up_slope * plan["row_step"])

    cover_center = eave + up_slope * (profile.cover_length * 0.5) + ridge_dir * (start + plan["column_step"] * 0.5) + normal * 0.058
    cover_spec = build_tile_module(profile.cover_length, profile.cover_width, profile.cover_thickness, profile.cover_curvature, True, 8, cover_center, up_slope, ridge_dir, normal)
    cover_mesh = _mesh_from_spec(f"{roof.name}.cover-source", cover_spec)
    cover = _source_object(f"{roof.name}.筒瓦源", cover_mesh, roof, _material("深灰屋脊", (0.045, 0.055, 0.06, 1.0)), "cover_tile", owner)
    created.append(cover)
    _array(cover, "沿檐口阵列", plan["cover_columns"], ridge_dir * plan["column_step"])
    _array(cover, "沿坡向叠瓦阵列", plan["pan_rows"], up_slope * plan["row_step"])

    if kind == "gable_mirror":
        mirror_axis = int(row.get("mirrorAxis", 0))
        for obj in (pan, cover):
            modifier = obj.modifiers.new("双坡镜像", "MIRROR")
            modifier.use_axis = tuple(index == mirror_axis for index in range(3))
            modifier.mirror_object = owner

    if kind == "l_boolean":
        cutter = bpy.data.objects.get(str(row.get("cutterObject") or ""))
        if cutter is None or cutter.type != "MESH":
            raise ValueError("L-roof domains require an explicit mesh cutterObject")
        cutter_health = mesh_health(cutter)
        if any(cutter_health[key] for key in ("wire_edges", "boundary_edges", "nonmanifold_edges", "degenerate_edges", "degenerate_faces")):
            raise ValueError(f"L-roof cutter must be closed and manifold: {cutter.name} -> {cutter_health}")
        for obj in (pan, cover):
            modifier = obj.modifiers.new("坡域裁切", "BOOLEAN")
            modifier.operation = "DIFFERENCE"
            modifier.solver = "MANIFOLD"
            modifier.object = cutter

    ridge_center = ridge + ridge_dir * (-ridge_span * 0.5 + profile.ridge_length * 0.5) + Vector((0, 0, 0.055))
    cross = Vector((1, 0, 0)) if abs(ridge_dir.y) > 0.5 else Vector((0, 1, 0))
    ridge_spec = build_tile_module(profile.ridge_length, profile.ridge_width, profile.ridge_thickness, profile.ridge_curvature, True, 10, ridge_center, ridge_dir, cross, Vector((0, 0, 1)))
    ridge_mesh = _mesh_from_spec(f"{roof.name}.ridge-source", ridge_spec)
    ridge_obj = _source_object(f"{roof.name}.脊瓦源", ridge_mesh, roof, _material("深灰屋脊", (0.045, 0.055, 0.06, 1.0)), "ridge_tile", owner)
    created.append(ridge_obj)
    _array(ridge_obj, "沿屋脊阵列", plan["ridge_count"], ridge_dir * plan["ridge_step"])
    return {"roof": roof.name, "owner": owner.name, "kind": kind, "plan": plan, "objects": [pan.name, cover.name, ridge_obj.name]}


def inspect(params):
    objects = sorted((obj for obj in bpy.data.objects if obj.get("blendercodex_roof_system") == SYSTEM_TAG), key=lambda item: item.name)
    return {
        "ok": True,
        "objects": [
            {
                "name": obj.name,
                "role": obj.get("blendercodex_roof_role"),
                "owner": obj.get("blendercodex_roof_owner"),
                "modifiers": [modifier.type for modifier in obj.modifiers],
            }
            for obj in objects
        ],
    }


def validate(params):
    names = params.get("objects") or [obj.name for obj in bpy.data.objects if obj.get("blendercodex_roof_system") == SYSTEM_TAG]
    reports = []
    for name in names:
        obj = bpy.data.objects.get(str(name))
        if obj is None or obj.type != "MESH":
            raise ValueError(f"Tiled-roof source object not found: {name}")
        types = [modifier.type for modifier in obj.modifiers]
        role = obj.get("blendercodex_roof_role")
        expected = ["ARRAY"] if role == "ridge_tile" else ["ARRAY", "ARRAY"]
        order_ok = types[: len(expected)] == expected
        contract_ok = True
        if "MIRROR" in types:
            contract_ok = types[-1] == "MIRROR" and obj.modifiers[-1].mirror_object is not None
        if "BOOLEAN" in types:
            boolean = obj.modifiers[-1]
            contract_ok = types[-1] == "BOOLEAN" and boolean.operation == "DIFFERENCE" and boolean.solver == "MANIFOLD" and boolean.object is not None
        reports.append({"name": obj.name, "health": mesh_health(obj), "uv": uv_density(obj), "modifiers": types, "order_ok": order_ok, "contract_ok": contract_ok})
    return {"ok": bool(reports) and all(
        row["health"]["wire_edges"] == 0
        and row["health"]["boundary_edges"] == 0
        and row["health"]["nonmanifold_edges"] == 0
        and row["health"]["degenerate_edges"] == 0
        and row["health"]["degenerate_faces"] == 0
        and row["uv"]["ok"]
        and row["order_ok"]
        and row["contract_ok"]
        for row in reports
    ), "reports": reports}


def build(params):
    started = time.perf_counter()
    domains = params.get("domains") or []
    if not domains:
        raise ValueError("Tiled-roof build requires explicit analyzed domains")
    for row in domains:
        roof = bpy.data.objects.get(str(row.get("roofObject") or ""))
        owner = bpy.data.objects.get(str(row.get("ownerObject") or ""))
        if roof is None or roof.type != "MESH":
            raise ValueError(f"roofObject must name an existing mesh: {row.get('roofObject')}")
        if owner is None:
            raise ValueError(f"ownerObject not found: {row.get('ownerObject')}")
        ridge_direction = _vector(row.get("ridgeDirection") or (0, 0, 0))
        eave, ridge = _vector(row.get("eave") or (0, 0, 0)), _vector(row.get("ridge") or (0, 0, 0))
        if ridge_direction.length <= 1e-8 or (ridge - eave).length <= 1e-8:
            raise ValueError("Roof domain ridgeDirection and eave-to-ridge slope must be non-zero")
        if ridge_direction.normalized().cross((ridge - eave).normalized()).length <= 1e-6:
            raise ValueError("Roof domain ridgeDirection must not be parallel to its slope")
        if float(row.get("ridgeSpan") or 0.0) <= 0:
            raise ValueError("Roof domain ridgeSpan must be positive")
    domain_roofs = {str(row["roofObject"]) for row in domains}
    domain_owners = {str(row["ownerObject"]) for row in domains}
    existing = [
        obj
        for obj in bpy.data.objects
        if obj.get("blendercodex_roof_system") == SYSTEM_TAG
        and (
            (obj.parent is not None and obj.parent.name in domain_roofs)
            or str(obj.get("blendercodex_roof_owner") or "") in domain_owners
        )
    ]
    if existing and not params.get("replaceExisting", False):
        raise ValueError("A BlenderCodex tiled-roof system already exists; set replaceExisting=true to replace it")
    save_requested = params.get("save", True)
    filepath = str(params.get("filepath") or bpy.data.filepath)
    if save_requested and not filepath:
        raise ValueError("Saving requires an existing .blend filepath or explicit filepath")
    created = []
    detached_existing = []
    try:
        reports = [_build_domain(row, params, created) for row in domains]
        validation = validate({"objects": [obj.name for obj in created]})
        if not validation["ok"]:
            raise ValueError(f"Tiled-roof validation failed: {validation}")
        if params.get("replaceExisting", False):
            for obj in existing:
                collections = tuple(obj.users_collection)
                for collection in collections:
                    collection.objects.unlink(obj)
                detached_existing.append((obj, collections))
        if save_requested:
            bpy.ops.wm.save_as_mainfile(filepath=filepath)
        for obj, _collections in detached_existing:
            mesh = obj.data if obj.type == "MESH" else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        return {"ok": True, "domains": reports, "validation": validation, "timings_ms": {"total": round((time.perf_counter() - started) * 1000.0, 3)}}
    except Exception:
        for obj, collections in detached_existing:
            if obj.name in bpy.data.objects:
                for collection in collections:
                    if obj.name not in collection.objects:
                        collection.objects.link(obj)
        for obj in created:
            if obj.name in bpy.data.objects:
                mesh = obj.data if obj.type == "MESH" else None
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh is not None and mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
        raise


def dispatch(action, params):
    if action == "inspect":
        return inspect(params)
    if action == "build":
        return build(params)
    if action == "validate":
        return validate(params)
    raise ValueError(f"Unknown tiled-roof action: {action}")


if "ACTION" in globals():
    RESULT = dispatch(ACTION, PARAMS)
