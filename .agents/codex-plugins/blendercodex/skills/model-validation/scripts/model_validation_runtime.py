"""Blender runtime for stable signatures, topology checks, and UV validation."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from geometry_core import UV_LAYER_NAME, canonical_json  # noqa: E402


def _id_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(key): _id_value(item) for key, item in value.items()}
    if hasattr(value, "to_list"):
        return [_id_value(item) for item in value.to_list()]
    if isinstance(value, (list, tuple)) or (hasattr(value, "__iter__") and not isinstance(value, (str, bytes))):
        try:
            return [_id_value(item) for item in value]
        except TypeError:
            pass
    return str(value)


def _matrix_rows(matrix):
    return [[float(value) for value in row] for row in matrix]


def _modifier_payload(modifier):
    payload = {"name": modifier.name, "type": modifier.type, "show_viewport": modifier.show_viewport}
    for field in (
        "count",
        "use_relative_offset",
        "use_constant_offset",
        "constant_offset_displace",
        "operation",
        "solver",
        "use_axis",
    ):
        if hasattr(modifier, field):
            value = getattr(modifier, field)
            payload[field] = list(value) if hasattr(value, "__iter__") and not isinstance(value, str) else value
    for field in ("object", "mirror_object"):
        target = getattr(modifier, field, None)
        payload[field] = target.name if target else None
    return payload


def object_signature(obj):
    payload = {
        "name": obj.name,
        "type": obj.type,
        "matrix_world": _matrix_rows(obj.matrix_world),
        "parent": obj.parent.name if obj.parent else None,
        "collections": sorted(collection.name for collection in obj.users_collection),
        "custom_properties": {key: _id_value(obj[key]) for key in sorted(obj.keys()) if key != "_RNA_UI"},
        "modifiers": [_modifier_payload(modifier) for modifier in obj.modifiers],
    }
    if obj.type == "MESH":
        mesh = obj.data
        payload["mesh"] = {
            "vertices": [[float(value) for value in vertex.co] for vertex in mesh.vertices],
            "edges": [[int(value) for value in edge.vertices] for edge in mesh.edges],
            "faces": [[int(value) for value in polygon.vertices] for polygon in mesh.polygons],
            "materials": [material.name if material else None for material in mesh.materials],
            "uv_layers": [layer.name for layer in mesh.uv_layers],
        }
    encoded = canonical_json(payload).encode("utf-8")
    return {"name": obj.name, "sha256": hashlib.sha256(encoded).hexdigest(), "payload": payload}


def mesh_health(obj):
    if obj.type != "MESH":
        raise ValueError(f"Object is not a mesh: {obj.name}")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        return {
            "vertices": len(bm.verts),
            "edges": len(bm.edges),
            "faces": len(bm.faces),
            "wire_edges": sum(len(edge.link_faces) == 0 for edge in bm.edges),
            "boundary_edges": sum(len(edge.link_faces) == 1 for edge in bm.edges),
            "nonmanifold_edges": sum(len(edge.link_faces) != 2 for edge in bm.edges),
            "degenerate_edges": sum(edge.calc_length() <= 1e-8 for edge in bm.edges),
            "degenerate_faces": sum(face.calc_area() <= 1e-10 for face in bm.faces),
        }
    finally:
        bm.free()


def uv_density(obj):
    mesh = obj.data
    uv = mesh.uv_layers.get(UV_LAYER_NAME)
    if not uv:
        return {"ok": False, "reason": "missing_uv_layer"}
    ratios = []
    for polygon in mesh.polygons:
        loops = list(polygon.loop_indices)
        for index, loop_id in enumerate(loops):
            next_loop = loops[(index + 1) % len(loops)]
            a = mesh.vertices[mesh.loops[loop_id].vertex_index].co
            b = mesh.vertices[mesh.loops[next_loop].vertex_index].co
            world_length = ((obj.matrix_world @ b) - (obj.matrix_world @ a)).length
            if world_length <= 1e-8:
                continue
            uv_length = (uv.data[next_loop].uv - uv.data[loop_id].uv).length
            ratios.append(uv_length * 4.0 / world_length)
    max_error = max((abs(value - 1.0) for value in ratios), default=math.inf)
    return {
        "ok": bool(ratios) and max_error <= 0.02 and mesh.uv_layers.active == uv and uv.active_render and uv.name == UV_LAYER_NAME,
        "samples": len(ratios),
        "max_error": max_error,
        "active": mesh.uv_layers.active == uv,
        "active_render": uv.active_render,
    }


def _objects(params):
    names = params.get("objects") or []
    if names:
        result = []
        for name in names:
            obj = bpy.data.objects.get(str(name))
            if obj is None:
                raise ValueError(f"Object not found: {name}")
            result.append(obj)
        return result
    return sorted((obj for obj in bpy.context.selected_objects if obj.type == "MESH"), key=lambda item: item.name)


def dispatch(action, params):
    objects = _objects(params)
    if action == "signature":
        rows = [object_signature(obj) for obj in objects]
        digest = hashlib.sha256(canonical_json(rows).encode("utf-8")).hexdigest()
        return {"ok": True, "objects": rows, "sha256": digest}
    if action == "validate":
        reports = []
        for obj in objects:
            health = mesh_health(obj)
            uv = uv_density(obj)
            topology_ok = not any(health[key] for key in ("wire_edges", "degenerate_edges", "degenerate_faces"))
            if params.get("requireManifold", True):
                topology_ok = topology_ok and health["nonmanifold_edges"] == 0
            reports.append({"name": obj.name, "health": health, "uv": uv, "ok": topology_ok and uv["ok"]})
        return {"ok": bool(reports) and all(row["ok"] for row in reports), "reports": reports}
    raise ValueError(f"Unknown model-validation action: {action}")


if "ACTION" in globals():
    RESULT = dispatch(ACTION, PARAMS)
