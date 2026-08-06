#!/usr/bin/env python3
"""Validate a BlenderCodex humanoid armature template JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ROLES = {
    "root",
    "pelvis",
    "spine_lower",
    "chest",
    "neck",
    "head",
    "shoulder_l",
    "elbow_l",
    "wrist_l",
    "shoulder_r",
    "elbow_r",
    "wrist_r",
    "hip_l",
    "knee_l",
    "ankle_l",
    "toe_l",
    "hip_r",
    "knee_r",
    "ankle_r",
    "toe_r",
}


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    bones = payload.get("bones")
    if not isinstance(bones, list) or not bones:
        return errors + ["bones must be a non-empty list"]

    names = [bone.get("name") for bone in bones]
    if any(not isinstance(name, str) or not name for name in names):
        errors.append("every bone must have a non-empty string name")
    if len(names) != len(set(names)):
        errors.append("bone names must be unique")
    name_set = set(names)

    for bone in bones:
        name = bone.get("name", "<unnamed>")
        parent = bone.get("parent")
        if parent is not None and parent not in name_set:
            errors.append(f"bone {name!r} has missing parent {parent!r}")
        for key in ("head", "tail"):
            value = bone.get(key)
            if not isinstance(value, list) or len(value) != 3:
                errors.append(f"bone {name!r} {key} must contain 3 numbers")
        matrix = bone.get("matrix_local")
        if (
            not isinstance(matrix, list)
            or len(matrix) != 4
            or any(not isinstance(row, list) or len(row) != 4 for row in matrix)
        ):
            errors.append(f"bone {name!r} matrix_local must be 4x4")

    for name in names:
        visited: set[str] = set()
        current = name
        while current is not None:
            if current in visited:
                errors.append(f"parent cycle detected at {name!r}")
                break
            visited.add(current)
            row = next((bone for bone in bones if bone.get("name") == current), None)
            current = row.get("parent") if row else None

    roles = payload.get("semantic_roles", {})
    missing_roles = sorted(REQUIRED_ROLES - set(roles))
    if missing_roles:
        errors.append(f"missing semantic roles: {missing_roles}")
    for role, bone_name in roles.items():
        if bone_name not in name_set:
            errors.append(f"semantic role {role!r} references missing bone {bone_name!r}")

    excluded = set(payload.get("exclusion", {}).get("excluded_bones", []))
    retained_exclusions = sorted(excluded & name_set)
    if retained_exclusions:
        errors.append(f"excluded bones were retained: {retained_exclusions}")

    counts = payload.get("counts", {})
    expected_counts = {
        "retained_bones": len(bones),
        "deform_bones": sum(bool(bone.get("use_deform")) for bone in bones),
        "control_bones": sum(not bool(bone.get("use_deform")) for bone in bones),
        "excluded_bones": len(excluded),
    }
    for key, expected in expected_counts.items():
        if counts.get(key) != expected:
            errors.append(f"counts.{key} must be {expected}, got {counts.get(key)!r}")

    for pose_row in payload.get("pose", []):
        bone_name = pose_row.get("bone")
        if bone_name not in name_set:
            errors.append(f"pose record references missing bone {bone_name!r}")
        for constraint in pose_row.get("constraints", []):
            for key in ("subtarget", "pole_subtarget"):
                target = constraint.get(key)
                if target and target not in name_set:
                    errors.append(
                        f"constraint on {bone_name!r} references missing {key} {target!r}"
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template")
    args = parser.parse_args()
    path = Path(args.template).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(payload)
    print(
        json.dumps(
            {
                "ok": not errors,
                "template": str(path),
                "errors": errors,
                "counts": payload.get("counts"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
