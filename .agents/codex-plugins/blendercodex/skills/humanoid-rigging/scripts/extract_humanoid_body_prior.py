#!/usr/bin/env python3
"""Extract a reusable body-proportion and weighted-region prior in Blender."""

import argparse
import json
import math
import os
import sys
from collections import defaultdict

import bpy
from mathutils import Vector


DEFAULT_PROXY_MESHES = [
    "下睫毛",
    "外衣",
    "手",
    "耳朵",
    "脖子",
    "脸",
    "裤子",
    "里衣",
    "鞋",
    "领子",
]

LANDMARK_ENDPOINTS = {
    "pelvis": ("Hips", "head"),
    "spine_lower": ("Spine", "head"),
    "spine_upper": ("UpperBody1", "head"),
    "chest": ("Chest", "head"),
    "neck": ("Neck", "head"),
    "head_base": ("Head", "head"),
    "head_top": ("Head", "tail"),
    "shoulder_r": ("Right arm", "head"),
    "elbow_r": ("Right elbow", "head"),
    "wrist_r": ("Right wrist", "head"),
    "hand_r": ("IK_Hand_R", "tail"),
    "shoulder_l": ("Left arm", "head"),
    "elbow_l": ("Left elbow", "head"),
    "wrist_l": ("Left wrist", "head"),
    "hand_l": ("IK_Hand_L", "tail"),
    "hip_r": ("Right leg", "head"),
    "knee_r": ("Right knee", "head"),
    "ankle_r": ("Right ankle", "head"),
    "heel_r": ("Right ankle", "tail"),
    "toe_r": ("Right toe", "tail"),
    "hip_l": ("Left leg", "head"),
    "knee_l": ("Left knee", "head"),
    "ankle_l": ("Left ankle", "head"),
    "heel_l": ("Left ankle", "tail"),
    "toe_l": ("Left toe", "tail"),
}


def blender_args():
    argv = sys.argv
    return argv[argv.index("--") + 1 :] if "--" in argv else []


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--armature", required=True)
    parser.add_argument("--mesh", action="append", default=[])
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(blender_args())


def vec(value):
    return [round(float(component), 9) for component in value]


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return float(ordered[index])


def point_segment_distance(point, head, tail):
    axis = tail - head
    length_squared = axis.length_squared
    if length_squared <= 1e-16:
        return (point - head).length
    factor = max(0.0, min(1.0, (point - head).dot(axis) / length_squared))
    return (point - (head + axis * factor)).length


def main():
    args = parse_args()
    armature = bpy.data.objects.get(args.armature)
    if armature is None or armature.type != "ARMATURE":
        raise ValueError(f"Armature not found: {args.armature}")

    with open(args.template, "r", encoding="utf-8") as handle:
        template = json.load(handle)
    retained = {bone["name"] for bone in template["bones"]}
    deform = {bone["name"] for bone in template["bones"] if bone["use_deform"]}

    requested = args.mesh or DEFAULT_PROXY_MESHES
    meshes = []
    missing = []
    for name in requested:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            missing.append(name)
        else:
            meshes.append(obj)
    if not meshes:
        raise ValueError("No body proxy meshes were resolved")

    armature_inverse = armature.matrix_world.inverted_safe()
    bounds_min = Vector((math.inf, math.inf, math.inf))
    bounds_max = Vector((-math.inf, -math.inf, -math.inf))
    samples = defaultdict(list)
    total_vertices = 0

    for obj in meshes:
        to_armature = armature_inverse @ obj.matrix_world
        group_names = {group.index: group.name for group in obj.vertex_groups}
        for vertex in obj.data.vertices:
            point = to_armature @ vertex.co
            total_vertices += 1
            for axis in range(3):
                bounds_min[axis] = min(bounds_min[axis], point[axis])
                bounds_max[axis] = max(bounds_max[axis], point[axis])
            for assignment in vertex.groups:
                name = group_names.get(assignment.group)
                if name in deform and assignment.weight > 1e-6:
                    samples[name].append((point.copy(), float(assignment.weight), obj.name))

    bounds_size = bounds_max - bounds_min
    height = max(float(bounds_size.z), 1e-9)
    bones = armature.data.bones
    regions = {}
    for bone_name in sorted(deform):
        rows = samples.get(bone_name, [])
        if not rows:
            continue
        weight_sum = sum(weight for _, weight, _ in rows)
        centroid = sum((point * weight for point, weight, _ in rows), Vector()) / max(weight_sum, 1e-9)
        minimum = Vector((math.inf, math.inf, math.inf))
        maximum = Vector((-math.inf, -math.inf, -math.inf))
        radii = []
        bone = bones.get(bone_name)
        for point, weight, _ in rows:
            if weight >= 0.05:
                for axis in range(3):
                    minimum[axis] = min(minimum[axis], point[axis])
                    maximum[axis] = max(maximum[axis], point[axis])
            if bone is not None:
                radii.append(point_segment_distance(point, bone.head_local, bone.tail_local))
        if math.isinf(minimum.x):
            minimum = centroid.copy()
            maximum = centroid.copy()
        regions[bone_name] = {
            "sample_count": len(rows),
            "weight_sum": round(weight_sum, 6),
            "centroid": vec(centroid),
            "bounds_min": vec(minimum),
            "bounds_max": vec(maximum),
            "radius_p50": round(percentile(radii, 0.50), 9),
            "radius_p90": round(percentile(radii, 0.90), 9),
            "source_meshes": sorted({source for _, _, source in rows}),
        }

    landmarks = {}
    for role, (bone_name, endpoint) in LANDMARK_ENDPOINTS.items():
        bone = bones.get(bone_name)
        if bone is None or bone_name not in retained:
            raise ValueError(f"Landmark {role} cannot resolve retained bone {bone_name}")
        point = bone.head_local if endpoint == "head" else bone.tail_local
        landmarks[role] = {
            "bone": bone_name,
            "endpoint": endpoint,
            "position": vec(point),
            "normalized_bbox": vec((point - bounds_min) / height),
        }

    payload = {
        "schema_version": 1,
        "prior_id": "female-body-prior-v1",
        "description": "Body proxy, landmark, and weighted-region prior extracted from the heroine source rig; hair and accessory meshes are excluded.",
        "source": {
            "artifact": bpy.data.filepath,
            "armature": armature.name,
            "blender_version": bpy.app.version_string,
        },
        "coordinate_system": template["coordinate_system"],
        "body_proxy": {
            "objects": [obj.name for obj in meshes],
            "missing_requested_objects": missing,
            "vertex_count": total_vertices,
            "bounds_min": vec(bounds_min),
            "bounds_max": vec(bounds_max),
            "dimensions": vec(bounds_size),
            "height": round(height, 9),
        },
        "landmarks": landmarks,
        "weighted_regions": regions,
        "counts": {
            "landmarks": len(landmarks),
            "weighted_regions": len(regions),
            "proxy_meshes": len(meshes),
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"ok": True, "output": args.output, "counts": payload["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
