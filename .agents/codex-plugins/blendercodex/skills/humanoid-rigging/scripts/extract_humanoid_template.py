#!/usr/bin/env python3
"""Extract a reusable humanoid armature template from the active Blender file.

Run with Blender, for example:

    blender -b character.blend --python extract_humanoid_template.py -- \
      --armature "女主骨骼" --exclude-prefix "头发" --output template.json

The source armature is read only. Coordinates are stored in armature-local space.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import bpy


SEMANTIC_ROLES = {
    "root": "IK_Root",
    "pelvis": "Hips",
    "spine_lower": "Spine",
    "spine_upper": "UpperBody1",
    "chest": "Chest",
    "neck": "Neck",
    "head": "Head",
    "shoulder_r": "Right shoulder",
    "upper_arm_r": "Right arm",
    "elbow_r": "Right elbow",
    "wrist_r": "Right wrist",
    "shoulder_l": "Left shoulder",
    "upper_arm_l": "Left arm",
    "elbow_l": "Left elbow",
    "wrist_l": "Left wrist",
    "breast_r": "Breast1_R",
    "breast_l": "Breast1_L",
    "hip_r": "Right leg",
    "knee_r": "Right knee",
    "ankle_r": "Right ankle",
    "toe_r": "Right toe",
    "hip_l": "Left leg",
    "knee_l": "Left knee",
    "ankle_l": "Left ankle",
    "toe_l": "Left toe",
    "hand_ik_r": "IK_Hand_R",
    "hand_ik_l": "IK_Hand_L",
    "foot_ik_r": "IK_Foot_R",
    "foot_ik_l": "IK_Foot_L",
    "elbow_pole_r": "Pole_Elbow_R",
    "elbow_pole_l": "Pole_Elbow_L",
    "knee_pole_r": "Pole_Knee_R",
    "knee_pole_l": "Pole_Knee_L",
}

FINGER_ROLES = {
    f"{finger}_{segment}_{side.lower()}": f"{bone}{segment}_{side}"
    for side in ("L", "R")
    for finger, bone, segments in (
        ("thumb", "Thumb", (0, 1, 2)),
        ("index", "IndexFinger", (1, 2, 3)),
        ("middle", "MiddleFinger", (1, 2, 3)),
        ("ring", "RingFinger", (1, 2, 3)),
        ("little", "LittleFinger", (1, 2, 3)),
    )
    for segment in segments
}
SEMANTIC_ROLES.update(FINGER_ROLES)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--armature", required=True, help="Armature object name")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--template-id", default="female-humanoid-v1")
    parser.add_argument("--source-label", default="主角建模.blend::女主骨骼")
    parser.add_argument("--exclude-prefix", action="append", default=[])
    parser.add_argument("--exclude-bone", action="append", default=[])
    return parser.parse_args(argv)


def rounded(value: float) -> float:
    return round(float(value), 9)


def vector(value: Any) -> list[float]:
    return [rounded(component) for component in value]


def matrix(value: Any) -> list[list[float]]:
    return [[rounded(component) for component in row] for row in value]


def json_custom_properties(owner: Any) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for key in owner.keys():
        if key == "_RNA_UI":
            continue
        value = owner[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            properties[key] = value
        elif hasattr(value, "to_list"):
            properties[key] = value.to_list()
        elif isinstance(value, (list, tuple)):
            properties[key] = list(value)
    return properties


def serialize_constraint(constraint: Any, armature: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": constraint.name,
        "type": constraint.type,
        "influence": rounded(constraint.influence),
        "mute": bool(constraint.mute),
    }
    for key in (
        "subtarget",
        "pole_subtarget",
        "chain_count",
        "use_tail",
        "iterations",
        "use_stretch",
        "head_tail",
        "mix_mode",
        "target_space",
        "owner_space",
    ):
        if hasattr(constraint, key):
            value = getattr(constraint, key)
            result[key] = rounded(value) if isinstance(value, float) else value
    if hasattr(constraint, "target"):
        target = constraint.target
        result["target"] = "$SELF" if target == armature else (target.name if target else None)
    if hasattr(constraint, "pole_target"):
        target = constraint.pole_target
        result["pole_target"] = "$SELF" if target == armature else (target.name if target else None)
    if hasattr(constraint, "pole_angle"):
        result["pole_angle"] = rounded(constraint.pole_angle)
    return result


def is_excluded(name: str, prefixes: tuple[str, ...], exact_names: set[str]) -> bool:
    return name in exact_names or any(name.startswith(prefix) for prefix in prefixes)


def extract_template(args: argparse.Namespace) -> dict[str, Any]:
    armature = bpy.data.objects.get(args.armature)
    if armature is None or armature.type != "ARMATURE":
        armatures = [obj.name for obj in bpy.data.objects if obj.type == "ARMATURE"]
        raise RuntimeError(f"Armature {args.armature!r} not found. Available: {armatures}")

    prefixes = tuple(args.exclude_prefix)
    exact_names = set(args.exclude_bone)
    excluded = [
        bone.name
        for bone in armature.data.bones
        if is_excluded(bone.name, prefixes, exact_names)
    ]
    retained_names = {
        bone.name
        for bone in armature.data.bones
        if not is_excluded(bone.name, prefixes, exact_names)
    }

    bones: list[dict[str, Any]] = []
    for bone in armature.data.bones:
        if bone.name not in retained_names:
            continue
        parent = bone.parent.name if bone.parent else None
        if parent and parent not in retained_names:
            raise RuntimeError(f"Retained bone {bone.name!r} depends on excluded parent {parent!r}")
        bones.append(
            {
                "name": bone.name,
                "parent": parent,
                "head": vector(bone.head_local),
                "tail": vector(bone.tail_local),
                "matrix_local": matrix(bone.matrix_local),
                "length": rounded(bone.length),
                "use_connect": bool(bone.use_connect),
                "use_deform": bool(bone.use_deform),
                "use_inherit_rotation": bool(bone.use_inherit_rotation),
                "inherit_scale": bone.inherit_scale,
                "head_radius": rounded(bone.head_radius),
                "tail_radius": rounded(bone.tail_radius),
                "envelope_distance": rounded(bone.envelope_distance),
                "envelope_weight": rounded(bone.envelope_weight),
                "collections": [collection.name for collection in bone.collections],
                "custom_properties": json_custom_properties(bone),
            }
        )

    pose: list[dict[str, Any]] = []
    for pose_bone in armature.pose.bones:
        if pose_bone.name not in retained_names:
            continue
        constraints = [
            serialize_constraint(constraint, armature)
            for constraint in pose_bone.constraints
            if not (
                getattr(constraint, "subtarget", "") in excluded
                or getattr(constraint, "pole_subtarget", "") in excluded
            )
        ]
        custom_properties = json_custom_properties(pose_bone)
        if constraints or custom_properties or pose_bone.rotation_mode != "QUATERNION":
            pose.append(
                {
                    "bone": pose_bone.name,
                    "rotation_mode": pose_bone.rotation_mode,
                    "constraints": constraints,
                    "custom_properties": custom_properties,
                }
            )

    semantic_roles = {
        role: bone_name
        for role, bone_name in SEMANTIC_ROLES.items()
        if bone_name in retained_names
    }
    head_height = armature.data.bones[semantic_roles["head"]].tail_local.z
    lowest_point = min(
        min(bone.head_local.z, bone.tail_local.z)
        for bone in armature.data.bones
        if bone.name in retained_names and bone.use_deform
    )

    return {
        "schema_version": 1,
        "template_id": args.template_id,
        "description": "女主标准人形骨架；已排除全部头发骨链。",
        "source": {
            "artifact": args.source_label,
            "armature": armature.name,
            "blender_version": bpy.app.version_string,
        },
        "coordinate_system": {
            "space": "armature_local",
            "up_axis": "+Z",
            "right_axis": "-X",
            "forward_axis": "-Y",
            "unit_scale_meters": rounded(bpy.context.scene.unit_settings.scale_length or 1.0),
        },
        "reference_metrics": {
            "lowest_deform_z": rounded(lowest_point),
            "head_tail_z": rounded(head_height),
            "height": rounded(head_height - lowest_point),
        },
        "exclusion": {
            "prefixes": list(prefixes),
            "exact_names": sorted(exact_names),
            "excluded_bones": excluded,
        },
        "semantic_roles": semantic_roles,
        "bones": bones,
        "pose": pose,
        "counts": {
            "source_bones": len(armature.data.bones),
            "retained_bones": len(bones),
            "excluded_bones": len(excluded),
            "deform_bones": sum(1 for bone in bones if bone["use_deform"]),
            "control_bones": sum(1 for bone in bones if not bone["use_deform"]),
        },
    }


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = extract_template(args)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output), "counts": payload["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
