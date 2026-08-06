"""Blender integration smoke test for the gated humanoid rig runtime."""

import argparse
import json
import sys

import bpy


def blender_args():
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


parser = argparse.ArgumentParser()
parser.add_argument("--runtime", required=True)
args = parser.parse_args(blender_args())

namespace = {"__file__": args.runtime}
with open(args.runtime, "rb") as handle:
    exec(compile(handle.read(), args.runtime, "exec"), namespace, namespace)
dispatch = namespace["dispatch"]

targets = ["下睫毛", "外衣", "手", "耳朵", "脖子", "脸", "裤子", "里衣", "鞋", "领子"]
before = {
    name: {
        "mesh": bpy.data.objects[name].data.name,
        "groups": [group.name for group in bpy.data.objects[name].vertex_groups],
        "modifiers": [(modifier.name, modifier.type, getattr(getattr(modifier, "object", None), "name", None)) for modifier in bpy.data.objects[name].modifiers],
        "matrix": [float(value) for row in bpy.data.objects[name].matrix_world for value in row],
    }
    for name in targets
}

analyzed = dispatch("analyze", {
    "targetObjects": targets,
    "armatureHint": "女主骨骼",
    "markerCollection": "__HR_TEST_MARKERS__",
    "replaceMarkers": True,
    "createMarkers": True,
})
assert analyzed["ok"] and analyzed["fit_allowed"]
assert analyzed["metrics"]["method"] == "existing_armature_rest"
assert len(analyzed["created_markers"]) == 25

geometry_only = dispatch("analyze", {
    "targetObjects": targets,
    "useExistingRigEvidence": False,
    "createMarkers": False,
})
assert geometry_only["ok"]
assert geometry_only["metrics"]["method"] == "geometry+heroine_body_prior"
assert geometry_only["landmark_count"] == 25
assert geometry_only["metrics"]["pose"] in {"t_pose", "a_pose"}, geometry_only["metrics"]
assert geometry_only["fit_allowed"] is True

try:
    dispatch("fit_standard", {"markerCollection": "__HR_TEST_MARKERS__", "confirmed": False})
except ValueError as error:
    assert "approval" in str(error).lower()
else:
    raise AssertionError("fit_standard accepted an unconfirmed request")

fitted = dispatch("fit_standard", {
    "markerCollection": "__HR_TEST_MARKERS__",
    "confirmed": True,
    "previewName": "__HR_TEST_RIG__",
    "replacePreview": True,
})
assert fitted["ok"], fitted
assert fitted["bone_count"] == 76
assert fitted["hair_bone_count"] == 0
assert fitted["validation"]["max_marker_error"] < 0.002, fitted["validation"]
assert fitted["validation"]["pose_basis_neutral"], fitted["validation"]
assert fitted["validation"]["max_pose_marker_error"] < 0.02, fitted["validation"]

rig = bpy.data.objects["__HR_TEST_RIG__"]
for side, bone_name in (("r", "IK_Hand_R"), ("l", "IK_Hand_L")):
    wrist = bpy.data.objects[f"HR_wrist_{side}"].matrix_world.translation
    hand = bpy.data.objects[f"HR_hand_{side}"].matrix_world.translation
    bone = rig.data.bones[bone_name]
    assert (rig.matrix_world @ bone.head_local - wrist).length < 1e-5
    assert (rig.matrix_world @ bone.tail_local - hand).length < 1e-5
for pose_bone in rig.pose.bones:
    delta = sum(
        abs(pose_bone.matrix_basis[row][column] - (1.0 if row == column else 0.0))
        for row in range(4)
        for column in range(4)
    )
    assert delta < 1e-6, (pose_bone.name, delta)

validated = dispatch("validate", {
    "markerCollection": "__HR_TEST_MARKERS__",
    "rigObject": "__HR_TEST_RIG__",
})
assert validated["ok"], validated
assert validated["pose_basis_neutral"]
assert validated["max_pose_marker_error"] < 0.02
assert not [row for row in validated["violations"] if row["type"].startswith("sagittal_")]

try:
    dispatch("bind_preview", {"rigObject": "__HR_TEST_RIG__", "confirmed": False})
except ValueError as error:
    assert "approval" in str(error).lower()
else:
    raise AssertionError("bind_preview accepted an unconfirmed request")

bound = dispatch("bind_preview", {
    "rigObject": "__HR_TEST_RIG__",
    "markerCollection": "__HR_TEST_MARKERS__",
    "confirmed": True,
    "method": "existing_groups",
    "previewCollection": "__HR_TEST_BIND__",
    "replacePreview": True,
})
assert bound["originals_modified"] is False
assert len(bound["preview_objects"]) == len(targets)

after = {
    name: {
        "mesh": bpy.data.objects[name].data.name,
        "groups": [group.name for group in bpy.data.objects[name].vertex_groups],
        "modifiers": [(modifier.name, modifier.type, getattr(getattr(modifier, "object", None), "name", None)) for modifier in bpy.data.objects[name].modifiers],
        "matrix": [float(value) for row in bpy.data.objects[name].matrix_world for value in row],
    }
    for name in targets
}
assert before == after, "Original target objects changed during preview workflow"

print(json.dumps({
    "ok": True,
    "analysis_method": analyzed["metrics"]["method"],
    "geometry_method": geometry_only["metrics"]["method"],
    "geometry_pose": geometry_only["metrics"]["pose"],
    "geometry_confidence": geometry_only["metrics"]["overall_confidence"],
    "marker_count": len(analyzed["created_markers"]),
    "bone_count": fitted["bone_count"],
    "max_marker_error": validated["max_marker_error"],
    "max_pose_marker_error": validated["max_pose_marker_error"],
    "max_sagittal_marker_error": validated["max_sagittal_marker_error"],
    "pose_basis_neutral": validated["pose_basis_neutral"],
    "binding_preview_count": len(bound["preview_objects"]),
    "originals_unchanged": before == after,
}, ensure_ascii=False))
