"""Blender runtime for live opening markers and rectilinear wall execution."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
import uuid

import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATION_DIR = SCRIPT_DIR.parents[1] / "model-validation" / "scripts"
for directory in (SCRIPT_DIR, VALIDATION_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
from geometry_core import UV_LAYER_NAME, planar_uv_4m  # noqa: E402
from opening_core import EnvelopeComponent, OpeningCut, build_rectilinear_shell, resolve_opening_defaults  # noqa: E402
from model_validation_runtime import mesh_health, object_signature, uv_density  # noqa: E402


MARKER_TAG = "blendercodex_opening_marker_v1"
DEFAULT_COLLECTION = "门窗标记"


def _timed(timings, name, callback):
    started = time.perf_counter()
    value = callback()
    timings[name] = round((time.perf_counter() - started) * 1000.0, 3)
    return value


def _collection(name, create=False):
    collection = bpy.data.collections.get(name)
    if collection is None and create:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    if collection is None:
        raise ValueError(f"Opening marker collection not found: {name}")
    return collection


def _marker_dimensions(marker):
    live_width = abs(float(marker.scale.x)) * float(marker.empty_display_size) * 2.0
    live_height = abs(float(marker.scale.z)) * float(marker.empty_display_size) * 2.0
    prop_width = marker.get("blendercodex_opening_width")
    prop_height = marker.get("blendercodex_opening_height")
    width = live_width if live_width > 1e-6 else float(prop_width or 0.0)
    height = live_height if live_height > 1e-6 else float(prop_height or 0.0)
    return width, height, {
        "width": prop_width is not None and abs(float(prop_width) - width) > 1e-4,
        "height": prop_height is not None and abs(float(prop_height) - height) > 1e-4,
    }


def inspect_markers(params):
    bpy.context.view_layer.update()
    collection = _collection(str(params.get("markerCollection") or DEFAULT_COLLECTION))
    rows = []
    for marker in sorted(collection.all_objects, key=lambda item: item.name):
        if not marker.get(MARKER_TAG):
            continue
        role = str(marker.get("blendercodex_role") or "").strip().lower()
        if role not in ("door", "window"):
            raise ValueError(f"Opening marker has missing or unsupported role: {marker.name} -> {role or '<missing>'}")
        width, height, conflicts = _marker_dimensions(marker)
        rows.append(
            {
                "name": marker.name,
                "id": str(marker.get("blendercodex_opening_id") or marker.name),
                "role": role,
                "target": str(marker.get("blendercodex_target_object") or ""),
                "width": width,
                "height": height,
                "sill": float(marker.get("blendercodex_opening_sill_height") or 0.0),
                "matrix_world": [[float(value) for value in row] for row in marker.matrix_world],
                "metadata_conflicts": conflicts,
            }
        )
    return rows


def create_markers(params):
    collection = _collection(str(params.get("markerCollection") or DEFAULT_COLLECTION), create=True)
    created = []
    specs = params.get("markers") or []
    prepared = []
    for index, spec in enumerate(specs):
        role = str(spec.get("role") or "").strip().lower()
        if role not in ("door", "window"):
            raise ValueError(f"Opening marker requires role door or window: index {index} -> {role or '<missing>'}")
        target_name = str(spec.get("target") or "").strip()
        if not target_name:
            raise ValueError(f"Opening marker requires an explicit target: index {index}")
        target = bpy.data.objects.get(target_name)
        if target is None or target.type != "MESH":
            raise ValueError(f"Opening marker target must be an existing mesh: index {index} -> {target_name}")
        axis = str(spec.get("axis") or "Y").upper()
        if axis not in ("X", "Y"):
            raise ValueError(f"Opening marker axis must be X or Y: index {index} -> {axis}")
        prepared.append((index, spec, role, target_name, axis, resolve_opening_defaults(role, spec)))
    for index, spec, role, target_name, axis, defaults in prepared:
        marker = bpy.data.objects.new(str(spec.get("name") or f"{role}_{index + 1:03d}"), None)
        collection.objects.link(marker)
        marker.empty_display_type = "CUBE"
        marker.empty_display_size = 0.5
        marker.location = tuple(float(value) for value in spec.get("location", (0, 0, defaults.sill + defaults.height * 0.5)))
        marker.rotation_euler = tuple(float(value) for value in spec.get("rotation", (0, 0, 0)))
        marker.scale = (defaults.width, float(spec.get("depth", 0.2)), defaults.height)
        marker[MARKER_TAG] = True
        marker["blendercodex_opening_id"] = str(spec.get("id") or uuid.uuid4())
        marker["blendercodex_role"] = role
        marker["blendercodex_target_object"] = target_name
        marker["blendercodex_wall_axis"] = axis
        marker["blendercodex_opening_width"] = defaults.width
        marker["blendercodex_opening_height"] = defaults.height
        marker["blendercodex_opening_sill_height"] = defaults.sill
        marker["blendercodex_status"] = "ready"
        created.append(marker.name)
    bpy.context.view_layer.update()
    return {"ok": True, "created": created, "markers": inspect_markers({"markerCollection": collection.name})}


def _component_rows(params, target, mesh):
    explicit = (params.get("componentsByObject") or {}).get(target.name)
    if explicit:
        return [EnvelopeComponent(str(row.get("id") or f"component-{index}"), tuple(float(value) for value in row["bounds"])) for index, row in enumerate(explicit)]
    # Automatic inference is intentionally narrow: accept only a single
    # axis-aligned box envelope. Compound or edited buildings must provide
    # explicit component bounds instead of silently collapsing to one AABB.
    if len(mesh.vertices) != 8 or len(mesh.edges) != 12 or len(mesh.polygons) != 6:
        raise ValueError(f"Target is not a provable single box; provide componentsByObject for {target.name}")
    if any(len(polygon.vertices) != 4 for polygon in mesh.polygons):
        raise ValueError(f"Target is not a closed quad box; provide componentsByObject for {target.name}")
    edge_face_counts = {tuple(sorted(edge.vertices)): 0 for edge in mesh.edges}
    for polygon in mesh.polygons:
        vertex_ids = list(polygon.vertices)
        for first, second in zip(vertex_ids, vertex_ids[1:] + vertex_ids[:1]):
            key = tuple(sorted((first, second)))
            if key not in edge_face_counts:
                raise ValueError(f"Target has a face edge missing from mesh edges; provide componentsByObject for {target.name}")
            edge_face_counts[key] += 1
    if any(face_count != 2 for face_count in edge_face_counts.values()):
        raise ValueError(f"Target is not a closed manifold box; provide componentsByObject for {target.name}")
    coordinates = {axis: sorted({round(float(getattr(vertex.co, axis)), 7) for vertex in mesh.vertices}) for axis in "xyz"}
    if any(len(values) != 2 for values in coordinates.values()):
        raise ValueError(f"Target is not a provable single box; provide componentsByObject for {target.name}")
    bounds = (
        coordinates["x"][0], coordinates["x"][1],
        coordinates["y"][0], coordinates["y"][1],
        coordinates["z"][0], coordinates["z"][1],
    )
    for polygon in mesh.polygons:
        vertices = [mesh.vertices[index].co for index in polygon.vertices]
        if not any(
            all(abs(float(getattr(vertex, axis)) - plane) <= 1e-6 for vertex in vertices)
            for axis, plane in (
                ("x", bounds[0]), ("x", bounds[1]),
                ("y", bounds[2]), ("y", bounds[3]),
                ("z", bounds[4]), ("z", bounds[5]),
            )
        ):
            raise ValueError(f"Target face is not aligned to its AABB; provide componentsByObject for {target.name}")
    return [EnvelopeComponent(target.name, bounds)]


def _cut_from_marker(marker, components, thickness):
    target = bpy.data.objects[str(marker["blendercodex_target_object"])]
    local = target.matrix_world.inverted() @ marker.matrix_world.translation
    declared_axis = "x" if str(marker.get("blendercodex_wall_axis") or "Y").lower() == "x" else "y"
    # Marker local Y is its wall-normal direction. Convert it into target-local
    # space so user rotations remain authoritative.
    marker_normal_world = marker.matrix_world.to_3x3() @ Vector((0, 1, 0))
    marker_normal_local = target.matrix_world.inverted().to_3x3() @ marker_normal_world
    axis = "x" if abs(marker_normal_local.x) > abs(marker_normal_local.y) else "y"
    if max(abs(marker_normal_local.x), abs(marker_normal_local.y)) < 0.98 * marker_normal_local.length:
        raise ValueError(f"Marker is not aligned to a supported vertical X/Y facade: {marker.name}")
    if axis != declared_axis:
        marker["blendercodex_wall_axis"] = axis.upper()
    width, height, _ = _marker_dimensions(marker)
    candidates = []
    for component in components:
        x0, x1, y0, y1, z0, z1 = component.bounds
        if not (z0 - 1e-4 <= local.z <= z1 + 1e-4):
            continue
        if axis == "x" and y0 - 1e-4 <= local.y <= y1 + 1e-4:
            candidates.extend(((abs(local.x - x0), component, -1), (abs(local.x - x1), component, 1)))
        if axis == "y" and x0 - 1e-4 <= local.x <= x1 + 1e-4:
            candidates.extend(((abs(local.y - y0), component, -1), (abs(local.y - y1), component, 1)))
    if not candidates:
        raise ValueError(f"Marker does not resolve to a component facade: {marker.name}")
    distance, component, side = min(candidates, key=lambda item: item[0])
    if distance > max(0.02, thickness * 0.25):
        raise ValueError(f"Marker is too far from target facade: {marker.name} ({distance:.4f} m)")
    return OpeningCut(
        str(marker.get("blendercodex_opening_id") or marker.name),
        component.component_id,
        axis,
        side,
        local.y if axis == "x" else local.x,
        local.z - height * 0.5,
        width,
        height,
    )


def _write_mesh(target, spec, candidate_name):
    mesh = bpy.data.meshes.new(candidate_name)
    mesh.from_pydata(spec.vertices, [], spec.faces)
    mesh.update(calc_edges=True)
    uv = mesh.uv_layers.new(name=UV_LAYER_NAME)
    mesh.uv_layers.active = uv
    uv.active_render = True
    matrix = [[float(value) for value in row] for row in target.matrix_world]
    projected = planar_uv_4m(spec.vertices, spec.faces, matrix)
    for polygon, values in zip(mesh.polygons, projected):
        for loop_id, value in zip(polygon.loop_indices, values):
            uv.data[loop_id].uv = value
    for material in target.data.materials:
        mesh.materials.append(material)
    return mesh


def apply_openings(params):
    timings = {}
    thickness = float(params.get("wallThickness", 0.2))
    marker_collection = str(params.get("markerCollection") or DEFAULT_COLLECTION)
    def read_live_markers():
        bpy.context.view_layer.update()
        return [item for item in _collection(marker_collection).all_objects if item.get(MARKER_TAG)]

    markers = _timed(timings, "inspect", read_live_markers)
    if not markers:
        raise ValueError("No live opening markers were found")
    targets = {}
    for marker in markers:
        role = str(marker.get("blendercodex_role") or "").strip().lower()
        if role not in ("door", "window"):
            raise ValueError(f"Opening marker has missing or unsupported role: {marker.name} -> {role or '<missing>'}")
        target_name = str(marker.get("blendercodex_target_object") or "")
        target = bpy.data.objects.get(target_name)
        if target is None or target.type != "MESH":
            raise ValueError(f"Marker target is not a mesh: {marker.name} -> {target_name}")
        if len(target.data.materials) > 1:
            raise ValueError(f"Multi-material targets are unsupported until per-face material mapping is explicit: {target_name}")
        targets[target_name] = target

    protected_names = [str(name) for name in params.get("protectedObjects") or []]
    missing_protected = [name for name in protected_names if bpy.data.objects.get(name) is None]
    if missing_protected:
        raise ValueError(f"Protected objects not found: {missing_protected}")
    protected_before = {name: object_signature(bpy.data.objects[name])["sha256"] for name in protected_names}
    candidates = {}
    old_meshes = {}
    marker_states = {
        marker.name: {
            key: (key in marker, marker.get(key))
            for key in ("blendercodex_status", "blendercodex_wall_axis")
        }
        for marker in markers
    }
    marker_collection_state = (
        _collection(marker_collection).hide_viewport,
        _collection(marker_collection).hide_render,
    )

    def build_all():
        for name, target in targets.items():
            components = _component_rows(params, target, target.data)
            cuts = [_cut_from_marker(marker, components, thickness) for marker in markers if str(marker["blendercodex_target_object"]) == name]
            spec = build_rectilinear_shell(components, cuts, thickness)
            candidates[name] = _write_mesh(target, spec, f"{name}.opening-candidate")

    try:
        _timed(timings, "build", build_all)
        reports = []
        for name, candidate in candidates.items():
            probe = targets[name].copy()
            probe.data = candidate
            reports.append({"name": name, "health": mesh_health(probe), "uv": uv_density(probe)})
            bpy.data.objects.remove(probe)
        if not all(
            row["health"]["wire_edges"] == 0
            and row["health"]["boundary_edges"] == 0
            and row["health"]["nonmanifold_edges"] == 0
            and row["health"]["degenerate_edges"] == 0
            and row["health"]["degenerate_faces"] == 0
            and row["uv"]["ok"]
            for row in reports
        ):
            raise ValueError(f"Opening candidate validation failed: {reports}")
        for name, candidate in candidates.items():
            target = targets[name]
            old_meshes[name] = target.data
            target.data = candidate
        for marker in markers:
            marker["blendercodex_status"] = "complete"
        protected_after = {name: object_signature(bpy.data.objects[name])["sha256"] for name in protected_names}
        if protected_before != protected_after:
            raise RuntimeError("Protected object signature changed during opening execution")
        if params.get("hideMarkers", True):
            _collection(marker_collection).hide_viewport = True
            _collection(marker_collection).hide_render = True
        if params.get("save", True):
            filepath = str(params.get("filepath") or bpy.data.filepath)
            if not filepath:
                raise ValueError("Saving requires an existing .blend filepath or explicit filepath")
            _timed(timings, "save", lambda: bpy.ops.wm.save_as_mainfile(filepath=filepath))
        for old_mesh in old_meshes.values():
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
        return {"ok": True, "markers": len(markers), "targets": sorted(targets), "reports": reports, "timings_ms": timings}
    except Exception:
        for name, old_mesh in old_meshes.items():
            targets[name].data = old_mesh
        for marker in markers:
            for key, (had_value, value) in marker_states[marker.name].items():
                if had_value:
                    marker[key] = value
                elif key in marker:
                    del marker[key]
        marker_collection_object = _collection(marker_collection)
        marker_collection_object.hide_viewport, marker_collection_object.hide_render = marker_collection_state
        for candidate in candidates.values():
            if candidate.users == 0:
                bpy.data.meshes.remove(candidate)
        raise


def dispatch(action, params):
    if action == "markers_create":
        return create_markers(params)
    if action == "markers_inspect":
        return {"ok": True, "markers": inspect_markers(params)}
    if action == "apply":
        return apply_openings(params)
    raise ValueError(f"Unknown architectural-openings action: {action}")


if "ACTION" in globals():
    RESULT = dispatch(ACTION, PARAMS)
