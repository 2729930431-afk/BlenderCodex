#!/usr/bin/env python3
"""Validate a copied humanoid rig asset against its source armature."""

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
    parser.add_argument("--asset", required=True)
    parser.add_argument("--source-armature", required=True)
    parser.add_argument("--asset-object", default="标准骨骼_女主_v1")
    parser.add_argument("--exclude-prefix", action="append", default=[])
    parser.add_argument("--expect-retained", type=int, required=True)
    parser.add_argument("--expect-excluded", type=int, required=True)
    return parser.parse_args(argv)


def rounded_matrix(value: Any) -> tuple[float, ...]:
    return tuple(round(float(component), 9) for row in value for component in row)


def bone_signature(bone: Any) -> dict[str, Any]:
    return {
        "matrix": rounded_matrix(bone.matrix_local),
        "head": tuple(round(float(value), 9) for value in bone.head_local),
        "tail": tuple(round(float(value), 9) for value in bone.tail_local),
        "parent": bone.parent.name if bone.parent else None,
        "use_connect": bool(bone.use_connect),
        "use_deform": bool(bone.use_deform),
        "inherit_scale": bone.inherit_scale,
        "collections": tuple(sorted(collection.name for collection in bone.collections)),
    }


def main() -> int:
    args = parse_args()
    source = bpy.data.objects.get(args.source_armature)
    if source is None or source.type != "ARMATURE":
        raise RuntimeError(f"Source armature not found: {args.source_armature}")

    asset = Path(args.asset).expanduser().resolve()
    before = set(bpy.data.collections.keys())
    with bpy.data.libraries.load(str(asset), link=False) as (data_from, data_to):
        data_to.collections = list(data_from.collections)
    loaded_collections = [
        collection for collection in data_to.collections if collection and collection.name not in before
    ]
    candidates = [
        obj
        for collection in loaded_collections
        for obj in collection.all_objects
        if obj.type == "ARMATURE" and obj.name == args.asset_object
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one asset armature {args.asset_object!r}, found {len(candidates)}")
    copied = candidates[0]

    prefixes = tuple(args.exclude_prefix)
    expected_names = [
        bone.name
        for bone in source.data.bones
        if not any(bone.name.startswith(prefix) for prefix in prefixes)
    ]
    excluded_names = [
        bone.name
        for bone in source.data.bones
        if any(bone.name.startswith(prefix) for prefix in prefixes)
    ]
    actual_names = list(copied.data.bones.keys())
    mismatches = [
        name
        for name in expected_names
        if name not in copied.data.bones
        or bone_signature(source.data.bones[name]) != bone_signature(copied.data.bones[name])
    ]
    foreign = sorted(set(actual_names) - set(expected_names))
    self_target_errors = []
    for pose_bone in copied.pose.bones:
        for constraint in pose_bone.constraints:
            if hasattr(constraint, "target") and constraint.target not in (None, copied):
                self_target_errors.append(f"{pose_bone.name}:{constraint.name}:target")
            if hasattr(constraint, "pole_target") and constraint.pole_target not in (None, copied):
                self_target_errors.append(f"{pose_bone.name}:{constraint.name}:pole_target")

    result = {
        "ok": not mismatches and not foreign and not self_target_errors,
        "asset": str(asset),
        "source_bones": len(source.data.bones),
        "retained_bones": len(actual_names),
        "excluded_bones": len(excluded_names),
        "rest_mismatches": mismatches,
        "foreign_bones": foreign,
        "self_target_errors": self_target_errors,
        "constraint_count": sum(len(pb.constraints) for pb in copied.pose.bones),
    }
    if len(actual_names) != args.expect_retained:
        result["ok"] = False
        result["retained_count_error"] = [args.expect_retained, len(actual_names)]
    if len(excluded_names) != args.expect_excluded:
        result["ok"] = False
        result["excluded_count_error"] = [args.expect_excluded, len(excluded_names)]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
