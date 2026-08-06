#!/usr/bin/env python3
"""Copy a source armature datablock into a standalone Blender rig asset.

Run with Blender, for example:

    blender -b character.blend --python build_humanoid_rig_asset.py -- \
      --armature "女主骨骼" --exclude-prefix "头发" --output standard.blend

The source armature is never edited. The output asset is created by copying the
actual Object and Armature datablocks, then removing only explicitly excluded
bones from the copied datablock.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import bpy


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--armature", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--object-name", default="标准骨骼_女主_v1")
    parser.add_argument("--collection-name", default="标准骨骼资产")
    parser.add_argument("--template-id", default="female-humanoid-v1")
    parser.add_argument("--exclude-prefix", action="append", default=[])
    parser.add_argument("--exclude-bone", action="append", default=[])
    parser.add_argument("--expect-retained", type=int)
    parser.add_argument("--expect-excluded", type=int)
    return parser.parse_args(argv)


def rounded_matrix(value: Any) -> tuple[float, ...]:
    return tuple(round(float(component), 9) for row in value for component in row)


def rest_signature(armature: Any, excluded: set[str]) -> dict[str, dict[str, Any]]:
    return {
        bone.name: {
            "matrix": rounded_matrix(bone.matrix_local),
            "head": tuple(round(float(value), 9) for value in bone.head_local),
            "tail": tuple(round(float(value), 9) for value in bone.tail_local),
            "parent": bone.parent.name if bone.parent else None,
            "use_connect": bool(bone.use_connect),
            "use_deform": bool(bone.use_deform),
            "inherit_scale": bone.inherit_scale,
            "collections": tuple(sorted(collection.name for collection in bone.collections)),
        }
        for bone in armature.data.bones
        if bone.name not in excluded
    }


def main() -> int:
    args = parse_args()
    source = bpy.data.objects.get(args.armature)
    if source is None or source.type != "ARMATURE":
        available = [obj.name for obj in bpy.data.objects if obj.type == "ARMATURE"]
        raise RuntimeError(f"Armature {args.armature!r} not found. Available: {available}")

    prefixes = tuple(args.exclude_prefix)
    exact_names = set(args.exclude_bone)
    excluded = {
        bone.name
        for bone in source.data.bones
        if bone.name in exact_names or any(bone.name.startswith(prefix) for prefix in prefixes)
    }
    expected_rest = rest_signature(source, excluded)

    collection = bpy.data.collections.new(args.collection_name)
    bpy.context.scene.collection.children.link(collection)
    copied = source.copy()
    copied.data = source.data.copy()
    copied.name = args.object_name
    copied.data.name = f"{args.object_name}_Armature"
    collection.objects.link(copied)

    for pose_bone in copied.pose.bones:
        for constraint in pose_bone.constraints:
            if hasattr(constraint, "target") and constraint.target == source:
                constraint.target = copied
            if hasattr(constraint, "pole_target") and constraint.pole_target == source:
                constraint.pole_target = copied

    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    copied.select_set(True)
    bpy.context.view_layer.objects.active = copied
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in list(copied.data.edit_bones):
        if bone.name in excluded:
            copied.data.edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()

    copied["blendercodex_template_id"] = args.template_id
    copied["blendercodex_copy_method"] = "source_armature_datablock_copy_then_remove_excluded"
    copied["blendercodex_excluded_prefixes"] = json.dumps(list(prefixes), ensure_ascii=False)
    copied["blendercodex_excluded_bones"] = json.dumps(sorted(excluded), ensure_ascii=False)

    actual_rest = rest_signature(copied, set())
    mismatches = sorted(
        name for name, expected in expected_rest.items() if actual_rest.get(name) != expected
    )
    retained = len(copied.data.bones)
    if mismatches:
        raise RuntimeError(f"Copied rest data differs from source: {mismatches}")
    if args.expect_retained is not None and retained != args.expect_retained:
        raise RuntimeError(f"Expected {args.expect_retained} retained bones, found {retained}")
    if args.expect_excluded is not None and len(excluded) != args.expect_excluded:
        raise RuntimeError(f"Expected {args.expect_excluded} excluded bones, found {len(excluded)}")

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(
        str(output),
        {collection},
        path_remap="RELATIVE",
        fake_user=True,
        compress=True,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output),
                "object": copied.name,
                "source_bones": len(source.data.bones),
                "retained_bones": retained,
                "excluded_bones": len(excluded),
                "rest_mismatches": len(mismatches),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
