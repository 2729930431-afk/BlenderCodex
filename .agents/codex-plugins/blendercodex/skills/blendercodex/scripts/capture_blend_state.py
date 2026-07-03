#!/usr/bin/env python3
"""Capture and compare BlenderCodex .blend scene state.

This host-side helper runs Blender in background mode, writes JSON scene
snapshots into either an explicit state directory or a temporary directory, and
can compare an existing user-edited .blend file with a fresh regeneration from
the matching Blender Python script.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from blender_locator import find_blender, make_payload, resolve_executable, version_matches


SNAPSHOT_RUNTIME = r'''
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy


def rounded(value, digits=6):
    return round(float(value), digits)


def rounded_list(values, digits=6):
    if values is None:
        return None
    return [rounded(value, digits) for value in values]


def jsonable_property(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        if hasattr(value, "to_list"):
            return value.to_list()
        return str(value)


def mesh_signature(mesh):
    payload = {
        "vertices": [
            [rounded(vertex.co.x, 5), rounded(vertex.co.y, 5), rounded(vertex.co.z, 5)]
            for vertex in mesh.vertices
        ],
        "edges": [list(edge.vertices) for edge in mesh.edges],
        "polygons": [list(poly.vertices) for poly in mesh.polygons],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def material_payload(material):
    payload = {
        "name": material.name,
        "diffuse_color": rounded_list(material.diffuse_color),
        "use_nodes": bool(material.use_nodes),
    }
    if material.use_nodes and material.node_tree:
        node = material.node_tree.nodes.get("Principled BSDF")
        if node:
            bsdf = {}
            for key in ("Base Color", "Metallic", "Roughness", "Alpha"):
                socket = node.inputs.get(key)
                if socket is None:
                    continue
                value = socket.default_value
                if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
                    bsdf[key] = rounded_list(value)
                else:
                    bsdf[key] = rounded(value)
            payload["principled_bsdf"] = bsdf
    return payload


def modifier_payload(modifier):
    payload = {
        "name": modifier.name,
        "type": modifier.type,
        "show_viewport": bool(modifier.show_viewport),
        "show_render": bool(modifier.show_render),
    }
    for key in (
        "width",
        "segments",
        "count",
        "use_relative_offset",
        "use_constant_offset",
        "constant_offset_displace",
        "affect",
    ):
        if not hasattr(modifier, key):
            continue
        value = getattr(modifier, key)
        if isinstance(value, bool):
            payload[key] = value
        elif isinstance(value, (int, float)):
            payload[key] = rounded(value)
        elif isinstance(value, str):
            payload[key] = value
        elif hasattr(value, "__iter__"):
            payload[key] = rounded_list(value)
    return payload


def object_payload(obj):
    payload = {
        "name": obj.name,
        "type": obj.type,
        "location": rounded_list(obj.location),
        "rotation_degrees": rounded_list([math.degrees(value) for value in obj.rotation_euler]),
        "scale": rounded_list(obj.scale),
        "dimensions": rounded_list(obj.dimensions),
        "collections": sorted(collection.name for collection in obj.users_collection),
        "materials": [
            material.name
            for material in getattr(getattr(obj, "data", None), "materials", [])
            if material
        ],
        "modifiers": [modifier_payload(modifier) for modifier in obj.modifiers],
    }

    custom_properties = {
        key: jsonable_property(obj[key])
        for key in obj.keys()
        if not str(key).startswith("_")
    }
    if custom_properties:
        payload["custom_properties"] = custom_properties

    data = getattr(obj, "data", None)
    if obj.type == "MESH" and data:
        payload["mesh"] = {
            "name": data.name,
            "vertex_count": len(data.vertices),
            "edge_count": len(data.edges),
            "polygon_count": len(data.polygons),
            "uv_layers": [layer.name for layer in data.uv_layers],
            "signature": mesh_signature(data),
        }
    elif data is not None and hasattr(data, "name"):
        payload["data_name"] = data.name

    return payload


def collection_payload(collection):
    return {
        "name": collection.name,
        "children": sorted(child.name for child in collection.children),
        "objects": sorted(obj.name for obj in collection.objects),
    }


def scene_payload():
    bpy.context.view_layer.update()
    return {
        "schema_version": 1,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "blender_version": bpy.app.version_string,
        "file": bpy.data.filepath,
        "scene": bpy.context.scene.name,
        "object_count": len(bpy.context.scene.objects),
        "collection_count": len(bpy.data.collections),
        "material_count": len(bpy.data.materials),
        "collections": sorted(
            [collection_payload(collection) for collection in bpy.data.collections],
            key=lambda item: item["name"],
        ),
        "objects": sorted(
            [object_payload(obj) for obj in bpy.context.scene.objects],
            key=lambda item: item["name"],
        ),
        "materials": sorted(
            [material_payload(material) for material in bpy.data.materials],
            key=lambda item: item["name"],
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-output", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    output = Path(args.snapshot_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scene_payload(), ensure_ascii=False, indent=2), encoding="utf-8")


main()
'''


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_state_dir(blend_path: Path) -> Path:
    return blend_path.parent / f"{blend_path.stem}.blendercodex"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if len(text) > limit else text


def resolve_blender(args: argparse.Namespace) -> dict[str, Any]:
    explicit_path = getattr(args, "blender_path", None)
    requested_version = getattr(args, "version", None)
    if explicit_path:
        resolved = resolve_executable(explicit_path)
        if resolved is None:
            raise FileNotFoundError(f"Blender executable not found: {explicit_path}")
        payload = make_payload(resolved, "explicit")
        if not version_matches(payload.get("version"), requested_version):
            raise ValueError(
                f"Blender at {resolved} is version {payload.get('version') or 'unknown'}, "
                f"not requested version {requested_version}."
            )
        return payload
    return find_blender(
        requested_version,
        getattr(args, "refresh", False),
        None,
    )


def capture_snapshot(blend_path: Path, output_json: Path, blender: dict[str, Any]) -> dict[str, Any]:
    blend_path = blend_path.expanduser().resolve()
    output_json = output_json.expanduser().resolve()
    if not blend_path.is_file():
        raise FileNotFoundError(f"Blend file not found: {blend_path}")

    with tempfile.TemporaryDirectory(prefix="blendercodex-snapshot-") as temp_dir:
        runtime_script = Path(temp_dir) / "snapshot_runtime.py"
        runtime_script.write_text(SNAPSHOT_RUNTIME, encoding="utf-8")
        command = [
            blender["path"],
            "--factory-startup",
            "-b",
            str(blend_path),
            "--python",
            str(runtime_script),
            "--",
            "--snapshot-output",
            str(output_json),
        ]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    payload = {
        "command": command,
        "returncode": result.returncode,
        "snapshot": str(output_json),
        "stdout_tail": tail(result.stdout),
        "stderr_tail": tail(result.stderr),
    }
    if result.returncode != 0:
        raise RuntimeError(json.dumps(payload, ensure_ascii=False, indent=2))
    if not output_json.is_file():
        raise RuntimeError(f"Blender finished but snapshot was not created: {output_json}")
    return payload


def run_generated_script(
    script_path: Path,
    output_blend: Path,
    blender: dict[str, Any],
) -> dict[str, Any]:
    script_path = script_path.expanduser().resolve()
    output_blend = output_blend.expanduser().resolve()
    command = [
        blender["path"],
        "--factory-startup",
        "-b",
        "--python",
        str(script_path),
        "--",
        "--output-blend",
        str(output_blend),
    ]
    env = os.environ.copy()
    env["BLENDERCODEX_OUTPUT_BLEND"] = str(output_blend)
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        command,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "output_blend": str(output_blend),
        "exists": output_blend.is_file(),
        "stdout_tail": tail(result.stdout),
        "stderr_tail": tail(result.stderr),
    }


def index_by_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in items}


def nested_get(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def compare_named_items(
    current_items: list[dict[str, Any]],
    baseline_items: list[dict[str, Any]],
    fields: list[tuple[str, ...]],
) -> dict[str, Any]:
    current = index_by_name(current_items)
    baseline = index_by_name(baseline_items)
    added = sorted(set(current) - set(baseline))
    removed = sorted(set(baseline) - set(current))
    changed = []
    for name in sorted(set(current) & set(baseline)):
        changed_fields = []
        for field in fields:
            current_value = nested_get(current[name], field)
            baseline_value = nested_get(baseline[name], field)
            if current_value != baseline_value:
                changed_fields.append(
                    {
                        "field": ".".join(field),
                        "baseline": baseline_value,
                        "current": current_value,
                    }
                )
        if changed_fields:
            changed.append({"name": name, "changes": changed_fields})
    return {"added": added, "removed": removed, "changed": changed}


def compare_snapshots(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    object_fields = [
        ("type",),
        ("location",),
        ("rotation_degrees",),
        ("scale",),
        ("dimensions",),
        ("collections",),
        ("materials",),
        ("modifiers",),
        ("mesh", "signature"),
        ("mesh", "vertex_count"),
        ("mesh", "edge_count"),
        ("mesh", "polygon_count"),
        ("mesh", "uv_layers"),
        ("custom_properties",),
    ]
    material_fields = [
        ("diffuse_color",),
        ("use_nodes",),
        ("principled_bsdf",),
    ]
    collection_fields = [
        ("children",),
        ("objects",),
    ]
    objects = compare_named_items(current.get("objects", []), baseline.get("objects", []), object_fields)
    materials = compare_named_items(
        current.get("materials", []),
        baseline.get("materials", []),
        material_fields,
    )
    collections = compare_named_items(
        current.get("collections", []),
        baseline.get("collections", []),
        collection_fields,
    )
    return {
        "objects": objects,
        "materials": materials,
        "collections": collections,
        "summary": {
            "objects_added": len(objects["added"]),
            "objects_removed": len(objects["removed"]),
            "objects_changed": len(objects["changed"]),
            "materials_added": len(materials["added"]),
            "materials_removed": len(materials["removed"]),
            "materials_changed": len(materials["changed"]),
            "collections_added": len(collections["added"]),
            "collections_removed": len(collections["removed"]),
            "collections_changed": len(collections["changed"]),
        },
    }


def command_snapshot(args: argparse.Namespace) -> int:
    blender = resolve_blender(args)
    capture = capture_snapshot(Path(args.blend), Path(args.output), blender)
    payload = {"blender": blender, "capture": capture}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_compare(args: argparse.Namespace) -> int:
    current = read_json(Path(args.current))
    baseline = read_json(Path(args.baseline))
    diff = compare_snapshots(current, baseline)
    if args.output:
        write_json(Path(args.output), diff)
    print(json.dumps(diff, ensure_ascii=False, indent=2))
    return 0


def command_capture_edits(args: argparse.Namespace) -> int:
    blender = resolve_blender(args)
    blend_path = Path(args.blend).expanduser().resolve()
    if args.state_dir:
        state_dir = Path(args.state_dir).expanduser().resolve()
        return capture_edits_to_state_dir(args, blender, blend_path, state_dir, persist=True)

    with tempfile.TemporaryDirectory(prefix="blendercodex-edits-") as temp_dir:
        return capture_edits_to_state_dir(args, blender, blend_path, Path(temp_dir), persist=False)


def capture_edits_to_state_dir(
    args: argparse.Namespace,
    blender: dict[str, Any],
    blend_path: Path,
    state_dir: Path,
    persist: bool,
) -> int:
    stamp = args.stamp or utc_stamp()
    current_snapshot = state_dir / f"current_snapshot.{stamp}.json"
    baseline_snapshot = state_dir / f"script_baseline_snapshot.{stamp}.json"
    baseline_blend = state_dir / f"script_baseline.{stamp}.blend"
    report_path = state_dir / f"user_edits.{stamp}.json"
    latest_path = state_dir / "latest_user_edits.json"

    report: dict[str, Any] = {
        "schema_version": 1,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "blend": str(blend_path),
        "state_dir": str(state_dir),
        "persistent_state": persist,
        "current_snapshot": str(current_snapshot),
        "source_script": str(Path(args.script).expanduser().resolve()) if args.script else None,
        "blender": blender,
    }

    try:
        report["current_capture"] = capture_snapshot(blend_path, current_snapshot, blender)
    except Exception as exc:  # noqa: BLE001 - preserve the failure details for the agent.
        report["current_capture_error"] = str(exc)
        if persist:
            write_json(report_path, report)
            write_json(latest_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    if args.script:
        regeneration = run_generated_script(Path(args.script), baseline_blend, blender)
        report["script_regeneration"] = regeneration
        report["baseline_blend"] = str(baseline_blend)
        report["baseline_snapshot"] = str(baseline_snapshot)
        if regeneration["returncode"] == 0 and regeneration["exists"]:
            try:
                report["baseline_capture"] = capture_snapshot(baseline_blend, baseline_snapshot, blender)
                report["diff"] = compare_snapshots(read_json(current_snapshot), read_json(baseline_snapshot))
            except Exception as exc:  # noqa: BLE001
                report["baseline_capture_error"] = str(exc)
        else:
            report["diff_status"] = "script_regeneration_failed"
    else:
        report["diff_status"] = "no_source_script"

    if persist:
        write_json(report_path, report)
        write_json(latest_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture or compare BlenderCodex scene state.")
    parser.add_argument("--version", help="Requested Blender version prefix, e.g. 4.2")
    parser.add_argument("--blender-path", help="Explicit Blender executable or install directory")
    parser.add_argument("--refresh", action="store_true", help="Ignore cached Blender path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot", help="Write a JSON snapshot for an existing .blend.")
    snapshot.add_argument("--blend", required=True)
    snapshot.add_argument("--output", required=True)

    compare = subparsers.add_parser("compare", help="Compare two snapshot JSON files.")
    compare.add_argument("--current", required=True)
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--output")

    edits = subparsers.add_parser(
        "capture-edits",
        help="Snapshot an existing .blend and compare it with a regeneration from a script.",
    )
    edits.add_argument("--blend", required=True)
    edits.add_argument("--script")
    edits.add_argument("--state-dir", help="Persist snapshots and reports here. Omit for temporary comparison.")
    edits.add_argument("--stamp")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "snapshot":
        return command_snapshot(args)
    if args.command == "compare":
        return command_compare(args)
    if args.command == "capture-edits":
        return command_capture_edits(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
