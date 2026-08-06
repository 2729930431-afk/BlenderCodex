"""Runtime actions for BlenderCodex humanoid analysis, fitting, and binding previews.

This file is executed inside Blender by the temporary RPC bridge.  Call
``dispatch(action, params)``; no scene is saved by this module.
"""

import hashlib
import json
import math
import os
from collections import Counter

import bpy
from mathutils import Matrix, Vector


SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ASSET = os.path.join(SKILL_ROOT, "assets", "female-humanoid-v1.blend")
DEFAULT_TEMPLATE = os.path.join(SKILL_ROOT, "references", "female-humanoid-v1.json")
DEFAULT_PRIOR = os.path.join(SKILL_ROOT, "references", "female-body-prior-v1.json")
DEFAULT_MARKER_COLLECTION = "人形绑定标记_待确认"
DEFAULT_FIT_COLLECTION = "人形绑定骨骼_待确认"
DEFAULT_BIND_COLLECTION = "人形绑定预览"

REQUIRED_ROLES = [
    "pelvis",
    "spine_lower", "spine_upper", "chest", "neck", "head_base", "head_top",
    "shoulder_l", "elbow_l", "wrist_l", "hand_l",
    "shoulder_r", "elbow_r", "wrist_r", "hand_r",
    "hip_l", "knee_l", "ankle_l", "heel_l", "toe_l",
    "hip_r", "knee_r", "ankle_r", "heel_r", "toe_r",
]

DIRECT_ENDPOINTS = {
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

REGION_ROLES = {
    "torso": ["pelvis", "spine_lower", "spine_upper", "chest", "neck", "head_base", "head_top"],
    "arm_r": ["chest", "shoulder_r", "elbow_r", "wrist_r", "hand_r"],
    "arm_l": ["chest", "shoulder_l", "elbow_l", "wrist_l", "hand_l"],
    "leg_r": ["pelvis", "hip_r", "knee_r", "ankle_r", "heel_r", "toe_r"],
    "leg_l": ["pelvis", "hip_l", "knee_l", "ankle_l", "heel_l", "toe_l"],
}


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _vec(value):
    return Vector((float(value[0]), float(value[1]), float(value[2])))


def _plain_vec(value, digits=6):
    return [round(float(component), digits) for component in value]


def _percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def _median(values):
    return _percentile(values, 0.5)


def _robust_midpoint(values, lower=0.1, upper=0.9):
    if not values:
        return 0.0
    return 0.5 * (_percentile(values, lower) + _percentile(values, upper))


def _collection_objects(collection):
    result = set(collection.objects)
    for child in collection.children:
        result.update(_collection_objects(child))
    return result


def _resolve_targets(params):
    objects = []
    names = params.get("targetObjects") or []
    if names:
        missing = []
        for name in names:
            obj = bpy.data.objects.get(str(name))
            if obj is None or obj.type != "MESH":
                missing.append(str(name))
            else:
                objects.append(obj)
        if missing:
            raise ValueError("Target mesh objects not found: " + ", ".join(missing))
    elif params.get("targetCollection"):
        collection = bpy.data.collections.get(str(params["targetCollection"]))
        if collection is None:
            raise ValueError(f"Target collection not found: {params['targetCollection']}")
        objects = [obj for obj in _collection_objects(collection) if obj.type == "MESH"]
    else:
        objects = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]

    if not objects and params.get("armatureHint"):
        armature = bpy.data.objects.get(str(params["armatureHint"]))
        if armature is not None and armature.type == "ARMATURE":
            for obj in bpy.data.objects:
                if obj.type != "MESH":
                    continue
                uses_armature = obj.parent == armature or any(
                    modifier.type == "ARMATURE" and modifier.object == armature for modifier in obj.modifiers
                )
                if uses_armature:
                    objects.append(obj)

    excluded = {str(name) for name in params.get("excludeObjects") or []}
    objects = sorted({obj for obj in objects if obj.name not in excluded}, key=lambda item: item.name)
    if not objects:
        raise ValueError("No target meshes were provided or selected")
    return objects


def _mesh_signature(objects):
    digest = hashlib.sha256()
    rows = []
    for obj in sorted(objects, key=lambda item: item.name):
        world = obj.matrix_world
        sums = Vector()
        for vertex in obj.data.vertices:
            sums += world @ vertex.co
        row = {
            "name": obj.name,
            "vertices": len(obj.data.vertices),
            "polygons": len(obj.data.polygons),
            "matrix_world": [round(float(value), 7) for row_value in world for value in row_value],
            "world_coordinate_sum": _plain_vec(sums, 7),
        }
        rows.append(row)
        digest.update(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return {"sha256": digest.hexdigest(), "objects": rows}


def _evaluated_points(objects, max_points=60000):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    total = sum(len(obj.data.vertices) for obj in objects)
    stride = max(1, int(math.ceil(total / max(1, max_points))))
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            world = evaluated.matrix_world
            points.extend(world @ vertex.co for index, vertex in enumerate(mesh.vertices) if index % stride == 0)
        finally:
            evaluated.to_mesh_clear()
    if len(points) < 32:
        raise ValueError("Target geometry has too few evaluated vertices for humanoid analysis")
    return points


def _bounds(points):
    minimum = Vector((math.inf, math.inf, math.inf))
    maximum = Vector((-math.inf, -math.inf, -math.inf))
    for point in points:
        for axis in range(3):
            minimum[axis] = min(minimum[axis], point[axis])
            maximum[axis] = max(maximum[axis], point[axis])
    return minimum, maximum


def _existing_armature(objects, hint, prior):
    candidates = []
    if hint:
        candidate = bpy.data.objects.get(str(hint))
        if candidate is not None and candidate.type == "ARMATURE":
            candidates.append(candidate)
    for obj in objects:
        if obj.parent is not None and obj.parent.type == "ARMATURE":
            candidates.append(obj.parent)
        candidates.extend(
            modifier.object for modifier in obj.modifiers
            if modifier.type == "ARMATURE" and modifier.object is not None
        )
    if not candidates:
        return None
    counts = Counter(candidate.name for candidate in candidates)
    for name, _ in counts.most_common():
        candidate = bpy.data.objects.get(name)
        if candidate is None:
            continue
        required_bones = {row["bone"] for row in prior["landmarks"].values()}
        if required_bones.issubset({bone.name for bone in candidate.data.bones}):
            return candidate
    return None


def _landmarks_from_armature(armature, prior, include_fingers):
    result = {}
    for role, row in prior["landmarks"].items():
        bone = armature.data.bones[row["bone"]]
        local = bone.head_local if row["endpoint"] == "head" else bone.tail_local
        result[role] = {
            "position": armature.matrix_world @ local,
            "confidence": 1.0,
            "evidence": "existing_armature_rest",
        }
    if include_fingers:
        template = _load_json(DEFAULT_TEMPLATE)
        for role, bone_name in template["semantic_roles"].items():
            if not any(token in role for token in ("thumb_", "index_", "middle_", "ring_", "little_")):
                continue
            bone = armature.data.bones.get(bone_name)
            if bone is not None:
                result[role] = {
                    "position": armature.matrix_world @ bone.head_local,
                    "confidence": 0.98,
                    "evidence": "existing_armature_rest",
                }
    return result


def _slice_center(points, z_value, thickness, center_x, side=None, x_limit=None):
    rows = []
    for point in points:
        if abs(point.z - z_value) > thickness:
            continue
        signed = point.x - center_x
        if side == "r" and signed >= 0:
            continue
        if side == "l" and signed <= 0:
            continue
        if x_limit is not None and abs(signed) > x_limit:
            continue
        rows.append(point)
    if len(rows) < 3:
        return None, 0
    # Vertex medians are biased toward whichever clothing panel has the densest
    # topology.  Use the midpoint of the robust front/back bounds for sagittal
    # depth, while retaining medians for the lateral and height axes.
    return Vector((
        _median([p.x for p in rows]),
        _robust_midpoint([p.y for p in rows]),
        _median([p.z for p in rows]),
    )), len(rows)


def _slice_sagittal_stats(points, z_value, thickness, center_x, side=None, x_limit=None):
    rows = []
    for point in points:
        if abs(point.z - z_value) > thickness:
            continue
        signed = point.x - center_x
        if side == "r" and signed >= 0:
            continue
        if side == "l" and signed <= 0:
            continue
        if x_limit is not None and abs(signed) > x_limit:
            continue
        rows.append(point)
    if len(rows) < 3:
        return None
    values = [point.y for point in rows]
    lower = _percentile(values, 0.1)
    upper = _percentile(values, 0.9)
    return {
        "lower": lower,
        "upper": upper,
        "center": 0.5 * (lower + upper),
        "count": len(rows),
    }


def _geometry_landmarks(points, prior):
    minimum, maximum = _bounds(points)
    dimensions = maximum - minimum
    height = max(dimensions.z, 1e-9)
    source_bounds = prior["body_proxy"]
    source_min = _vec(source_bounds["bounds_min"])
    source_max = _vec(source_bounds["bounds_max"])
    source_center = (source_min + source_max) * 0.5
    target_center = (minimum + maximum) * 0.5
    scale = height / max(float(source_bounds["height"]), 1e-9)

    def initial(source_point):
        offset = source_point - source_center
        return Vector((
            target_center.x + offset.x * scale,
            target_center.y + offset.y * scale,
            minimum.z + (source_point.z - source_min.z) * scale,
        ))

    landmarks = {}
    source_positions = {role: _vec(row["position"]) for role, row in prior["landmarks"].items()}
    for role, source_point in source_positions.items():
        landmarks[role] = {
            "position": initial(source_point),
            "confidence": 0.76,
            "evidence": "heroine_body_prior",
        }

    central_limit = max(height * 0.11, min(dimensions.x * 0.22, height * 0.18))
    for role in ("pelvis", "spine_lower", "spine_upper", "chest", "neck", "head_base"):
        seed = landmarks[role]["position"]
        center, count = _slice_center(points, seed.z, height * 0.018, target_center.x, x_limit=central_limit)
        if center is not None:
            landmarks[role]["position"].x = center.x
            # Blend the anatomy prior with the robust section midpoint.  The
            # prior prevents loose coats from dragging the spine onto a shell;
            # the section keeps differently proportioned bodies centered.
            landmarks[role]["position"].y = seed.y * 0.35 + center.y * 0.65
            landmarks[role]["position"].z = center.z
            landmarks[role]["confidence"] = min(0.9, 0.78 + min(count, 80) / 1000.0)
            landmarks[role]["evidence"] = "heroine_prior+robust_sagittal_section"

    # Follow the arm silhouette laterally. This lets A-pose arms slope instead of
    # inheriting the heroine's nearly horizontal arm heights.
    for side, sign in (("r", -1.0), ("l", 1.0)):
        shoulder_role = f"shoulder_{side}"
        hand_role = f"hand_{side}"
        shoulder_distance = abs(landmarks[shoulder_role]["position"].x - target_center.x)
        signed_distances = [sign * (point.x - target_center.x) for point in points]
        outer = _percentile([value for value in signed_distances if value > 0], 0.995)
        if outer <= shoulder_distance * 1.1:
            continue
        source_shoulder = abs(source_positions[shoulder_role].x - source_center.x)
        source_hand = abs(source_positions[hand_role].x - source_center.x)
        outer_width = max(height * 0.018, (outer - shoulder_distance) * 0.045)
        outer_candidates = [
            point for point in points
            if abs(sign * (point.x - target_center.x) - outer) <= outer_width
        ]
        outer_height = (
            _median([point.z for point in outer_candidates])
            if len(outer_candidates) >= 3
            else landmarks[hand_role]["position"].z
        )
        shoulder_height = landmarks[shoulder_role]["position"].z
        for role in (shoulder_role, f"elbow_{side}", f"wrist_{side}", hand_role):
            source_distance = abs(source_positions[role].x - source_center.x)
            fraction = (source_distance - source_shoulder) / max(source_hand - source_shoulder, 1e-9)
            fraction = max(0.0, min(1.0, fraction))
            target_distance = shoulder_distance + fraction * (outer - shoulder_distance)
            width = max(height * 0.018, (outer - shoulder_distance) * 0.045)
            expected_height = shoulder_height + fraction * (outer_height - shoulder_height)
            height_window = height * (0.065 + 0.035 * fraction)
            candidates = [
                point for point in points
                if abs(sign * (point.x - target_center.x) - target_distance) <= width
                and abs(point.z - expected_height) <= height_window
            ]
            if len(candidates) >= 3:
                landmarks[role]["position"] = Vector((
                    _median([point.x for point in candidates]),
                    _robust_midpoint([point.y for point in candidates]),
                    _median([point.z for point in candidates]),
                ))
                landmarks[role]["confidence"] = min(0.88, 0.72 + min(len(candidates), 80) / 800.0)
                landmarks[role]["evidence"] = "heroine_prior+arm_silhouette"

    # Refine bilateral leg centers from horizontal slices at the prior heights.
    for side in ("r", "l"):
        for role in (f"hip_{side}", f"knee_{side}", f"ankle_{side}"):
            seed = landmarks[role]["position"]
            center, count = _slice_center(points, seed.z, height * 0.02, target_center.x, side=side)
            if center is not None:
                center.y = seed.y * 0.35 + center.y * 0.65
                landmarks[role]["position"] = center
                landmarks[role]["confidence"] = min(0.9, 0.76 + min(count, 80) / 800.0)
                landmarks[role]["evidence"] = "heroine_prior+leg_cross_section"

    left_extent = max(0.0, maximum.x - target_center.x)
    right_extent = max(0.0, target_center.x - minimum.x)
    symmetry = 1.0 - abs(left_extent - right_extent) / max(left_extent, right_extent, 1e-9)
    aspect = height / max(dimensions.x, 1e-9)
    humanoid_shape = 1.0 if 0.65 <= aspect <= 4.5 else max(0.0, 1.0 - abs(aspect - 1.8) / 4.0)
    overall = max(0.0, min(0.92, 0.69 + 0.16 * symmetry + 0.07 * humanoid_shape))
    outer_z = []
    for point in points:
        if abs(point.x - target_center.x) >= max(left_extent, right_extent) * 0.75:
            outer_z.append(point.z)
    hand_z = _median(outer_z) if outer_z else landmarks["hand_l"]["position"].z
    shoulder_z = 0.5 * (landmarks["shoulder_l"]["position"].z + landmarks["shoulder_r"]["position"].z)
    delta = (shoulder_z - hand_z) / height
    pose = "t_pose" if abs(delta) < 0.08 else ("a_pose" if 0.08 <= delta < 0.32 else "posed")
    return landmarks, {
        "overall_confidence": round(overall, 4),
        "symmetry_score": round(symmetry, 4),
        "pose": pose,
        "bounds_min": _plain_vec(minimum),
        "bounds_max": _plain_vec(maximum),
        "dimensions": _plain_vec(dimensions),
        "height": round(height, 6),
        "method": "geometry+heroine_body_prior",
    }


def _ensure_collection(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def _create_markers(collection, landmarks, source_names, analysis_id, display_size):
    created = []
    for role, row in landmarks.items():
        marker = bpy.data.objects.new(f"HR_{role}", None)
        marker.empty_display_type = "SPHERE"
        marker.empty_display_size = display_size
        marker.show_in_front = True
        marker.location = row["position"]
        confidence = float(row["confidence"])
        marker.color = (1.0 - confidence, confidence, 0.15, 1.0)
        marker["humanoid_role"] = role
        marker["confidence"] = confidence
        marker["evidence"] = row["evidence"]
        marker["source_objects"] = json.dumps(source_names, ensure_ascii=False)
        marker["analysis_id"] = analysis_id
        collection.objects.link(marker)
        created.append(marker.name)
    return created


def analyze(params):
    objects = _resolve_targets(params)
    prior_path = os.path.abspath(str(params.get("priorPath") or DEFAULT_PRIOR))
    prior = _load_json(prior_path)
    signature = _mesh_signature(objects)
    points = _evaluated_points(objects, int(params.get("maxPoints") or 60000))
    minimum, maximum = _bounds(points)
    height = max((maximum - minimum).z, 1e-9)
    armature = _existing_armature(objects, params.get("armatureHint"), prior) if params.get("useExistingRigEvidence", True) else None
    if armature is not None:
        landmarks = _landmarks_from_armature(armature, prior, bool(params.get("includeFingers")))
        metrics = {
            "overall_confidence": 1.0,
            "symmetry_score": 1.0,
            "pose": "reference_rest",
            "bounds_min": _plain_vec(minimum),
            "bounds_max": _plain_vec(maximum),
            "dimensions": _plain_vec(maximum - minimum),
            "height": round(height, 6),
            "method": "existing_armature_rest",
            "armature": armature.name,
        }
    else:
        landmarks, metrics = _geometry_landmarks(points, prior)

    required_confidence = min(float(landmarks[role]["confidence"]) for role in REQUIRED_ROLES)
    fit_allowed = metrics["overall_confidence"] >= 0.75 and required_confidence >= 0.6 and metrics["pose"] not in {"posed", "unknown"}
    analysis_id = hashlib.sha256(
        (signature["sha256"] + json.dumps(sorted(landmarks), ensure_ascii=False)).encode("utf-8")
    ).hexdigest()[:16]
    collection_name = str(params.get("markerCollection") or DEFAULT_MARKER_COLLECTION)
    created = []
    if params.get("createMarkers", True):
        collection = _ensure_collection(collection_name)
        existing = [obj for obj in collection.objects if obj.get("humanoid_role")]
        if existing and not params.get("replaceMarkers", False):
            raise ValueError(
                f"Marker collection {collection_name} already contains semantic markers; preserve user edits or pass replaceMarkers=true explicitly"
            )
        if params.get("replaceMarkers", False):
            for obj in list(collection.objects):
                if obj.get("humanoid_role"):
                    bpy.data.objects.remove(obj, do_unlink=True)
        created = _create_markers(collection, landmarks, [obj.name for obj in objects], analysis_id, height * 0.012)
        collection["humanoid_analysis_id"] = analysis_id
        collection["humanoid_target_objects"] = json.dumps([obj.name for obj in objects], ensure_ascii=False)
        collection["humanoid_target_signature"] = json.dumps(signature, ensure_ascii=False, sort_keys=True)
        collection["humanoid_overall_confidence"] = float(metrics["overall_confidence"])
        collection["humanoid_pose"] = metrics["pose"]
        collection["humanoid_fit_allowed"] = bool(fit_allowed)
        collection["humanoid_prior_id"] = prior["prior_id"]
        bpy.context.view_layer.update()

    return {
        "ok": True,
        "analysis_id": analysis_id,
        "target_objects": [obj.name for obj in objects],
        "target_signature": signature["sha256"],
        "marker_collection": collection_name if params.get("createMarkers", True) else None,
        "created_markers": created,
        "required_roles": REQUIRED_ROLES,
        "landmark_count": len(landmarks),
        "required_min_confidence": round(required_confidence, 4),
        "fit_allowed": fit_allowed,
        "metrics": metrics,
        "landmarks": {
            role: {
                "position": _plain_vec(row["position"]),
                "confidence": round(float(row["confidence"]), 4),
                "evidence": row["evidence"],
            }
            for role, row in landmarks.items()
        },
        "next_gate": "Confirm or move/delete markers, then call humanoid_fit_standard with confirmed=true.",
        "saved": False,
    }


def _read_markers(collection_name):
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        raise ValueError(f"Marker collection not found: {collection_name}")
    markers = {}
    duplicates = []
    for obj in collection.objects:
        role = obj.get("humanoid_role")
        if not role:
            continue
        role = str(role)
        if role in markers:
            duplicates.append(role)
        markers[role] = obj
    if duplicates:
        raise ValueError("Duplicate semantic marker roles: " + ", ".join(sorted(set(duplicates))))
    missing = [role for role in REQUIRED_ROLES if role not in markers]
    if missing:
        raise ValueError("Required markers are missing or were rejected: " + ", ".join(missing))
    return collection, markers


def _verify_signature(collection):
    raw_names = collection.get("humanoid_target_objects")
    raw_signature = collection.get("humanoid_target_signature")
    if not raw_names or not raw_signature:
        raise ValueError("Marker collection does not contain an analysis target signature")
    names = json.loads(str(raw_names))
    objects = []
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise ValueError(f"Analyzed target mesh is missing: {name}")
        objects.append(obj)
    expected = json.loads(str(raw_signature))
    actual = _mesh_signature(objects)
    if actual["sha256"] != expected["sha256"]:
        raise ValueError("Target mesh or transform changed after landmark analysis; analyze again before fitting")
    return objects, actual


def _bone_region(name):
    lowered = name.lower()
    right = "right" in lowered or lowered.endswith("_r")
    left = "left" in lowered or lowered.endswith("_l")
    leg = any(token in lowered for token in ("leg", "knee", "ankle", "toe", "foot"))
    arm = any(token in lowered for token in ("shoulder", "arm", "elbow", "wrist", "hand", "finger", "thumb"))
    if right and leg:
        return "leg_r"
    if left and leg:
        return "leg_l"
    if right and arm:
        return "arm_r"
    if left and arm:
        return "arm_l"
    return "torso"


def _append_standard(asset_path, object_name):
    if not os.path.isfile(asset_path):
        raise ValueError(f"Authoritative humanoid asset not found: {asset_path}")
    with bpy.data.libraries.load(asset_path, link=False) as (data_from, data_to):
        candidates = [name for name in data_from.objects if name == "标准骨骼_女主_v1"]
        if not candidates:
            raise ValueError("Authoritative asset does not contain 标准骨骼_女主_v1")
        data_to.objects = candidates
    rig = data_to.objects[0]
    if rig is None or rig.type != "ARMATURE":
        raise ValueError("Appended standard object is not an armature")
    collection = _ensure_collection(DEFAULT_FIT_COLLECTION)
    collection.objects.link(rig)
    rig.name = object_name
    rig.data.name = f"{object_name}_Armature"
    rig.matrix_world = Matrix.Identity(4)
    return rig


def _fit_transform(source_landmarks, target_landmarks):
    source_pelvis = source_landmarks["pelvis"]
    target_pelvis = target_landmarks["pelvis"]
    source_height = max(abs(source_landmarks["head_top"].z - source_pelvis.z), 1e-9)
    target_height = max(abs(target_landmarks["head_top"].z - target_pelvis.z), 1e-9)
    scale_z = target_height / source_height
    source_shoulders = (source_landmarks["shoulder_l"] - source_landmarks["shoulder_r"]).length
    target_shoulders = (target_landmarks["shoulder_l"] - target_landmarks["shoulder_r"]).length
    scale_x = target_shoulders / max(source_shoulders, 1e-9)
    scale_x = max(scale_z * 0.55, min(scale_z * 1.8, scale_x))
    scale_y = scale_z

    def transform(point):
        offset = point - source_pelvis
        return target_pelvis + Vector((offset.x * scale_x, offset.y * scale_y, offset.z * scale_z))

    return transform, Vector((scale_x, scale_y, scale_z))


def _warp_point(point, region, transform, source_landmarks, target_landmarks):
    base = transform(point)
    roles = REGION_ROLES[region]
    weighted_delta = Vector()
    weight_sum = 0.0
    for role in roles:
        source = source_landmarks[role]
        distance = (point - source).length
        if distance <= 1e-7:
            return target_landmarks[role].copy()
        weight = 1.0 / max(distance * distance, 1e-8)
        weighted_delta += (target_landmarks[role] - transform(source)) * weight
        weight_sum += weight
    return base + weighted_delta / max(weight_sum, 1e-9)


def _pole_position(start, joint, end, fallback, distance_scale):
    axis = end - start
    if axis.length_squared <= 1e-12:
        return joint + fallback.normalized() * distance_scale
    projected = start + axis * ((joint - start).dot(axis) / axis.length_squared)
    bend = joint - projected
    # Nearly straight T/A-pose limbs can have a few millimeters of noisy bend
    # from clothing samples.  Treat that as ambiguous and use the stable -Y
    # fallback instead of placing pole controls above or beside the character.
    bend_ratio = bend.length / max(axis.length, 1e-9)
    direction = bend.normalized() if bend_ratio >= 0.08 else fallback.normalized()
    return joint + direction * distance_scale


def _reset_pose_basis(rig):
    changed = []
    for pose_bone in rig.pose.bones:
        delta = sum(
            abs(pose_bone.matrix_basis[row][column] - (1.0 if row == column else 0.0))
            for row in range(4)
            for column in range(4)
        )
        if delta > 1e-8:
            changed.append(pose_bone.name)
        pose_bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return changed


def _optimize_pole_angle(rig, pose_bone_name, target_joint):
    pose_bone = rig.pose.bones.get(pose_bone_name)
    if pose_bone is None:
        return None
    constraint = next((row for row in pose_bone.constraints if row.type == "IK"), None)
    if constraint is None or constraint.pole_target is None:
        return None

    best_error = math.inf
    best_angle = float(constraint.pole_angle)

    def sample(start, end, steps):
        nonlocal best_error, best_angle
        for index in range(steps + 1):
            angle = start + (end - start) * index / max(steps, 1)
            constraint.pole_angle = angle
            bpy.context.view_layer.update()
            actual = rig.matrix_world @ pose_bone.head
            error = (actual - target_joint).length
            if error < best_error:
                best_error = error
                best_angle = angle

    sample(-math.pi, math.pi, 180)
    refinement = math.radians(4.0)
    sample(best_angle - refinement, best_angle + refinement, 160)
    constraint.pole_angle = best_angle
    bpy.context.view_layer.update()
    return {
        "bone": pose_bone_name,
        "pole_angle": round(best_angle, 7),
        "joint_error": round((rig.matrix_world @ pose_bone.head - target_joint).length, 7),
    }


def fit_standard(params):
    if params.get("confirmed") is not True:
        raise ValueError("Marker approval is required: call with confirmed=true only after the user confirms the live markers")
    collection_name = str(params.get("markerCollection") or DEFAULT_MARKER_COLLECTION)
    marker_collection, marker_objects = _read_markers(collection_name)
    target_objects, signature = _verify_signature(marker_collection)
    if not bool(marker_collection.get("humanoid_fit_allowed", False)) and not params.get("allowLowConfidence", False):
        raise ValueError("Landmark analysis did not meet the automatic fitting threshold; revise markers or pass allowLowConfidence=true explicitly")

    object_name = str(params.get("previewName") or "标准骨骼_人形拟合_待确认")
    existing = bpy.data.objects.get(object_name)
    if existing is not None:
        if not params.get("replacePreview", False) or not existing.get("humanoid_fit_preview"):
            raise ValueError(f"Fit preview object already exists: {object_name}")
        bpy.data.objects.remove(existing, do_unlink=True)

    prior = _load_json(os.path.abspath(str(params.get("priorPath") or DEFAULT_PRIOR)))
    source_landmarks = {role: _vec(row["position"]) for role, row in prior["landmarks"].items()}
    target_landmarks = {role: obj.matrix_world.translation.copy() for role, obj in marker_objects.items() if role in source_landmarks}
    rig = _append_standard(os.path.abspath(str(params.get("assetPath") or DEFAULT_ASSET)), object_name)
    transform, scales = _fit_transform(source_landmarks, target_landmarks)

    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    mirror_x = bool(rig.data.use_mirror_x)
    rig.data.use_mirror_x = False
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = rig.data.edit_bones
    originals = {}
    for bone in edit_bones:
        originals[bone.name] = {
            "head": bone.head.copy(),
            "tail": bone.tail.copy(),
            "roll_axis": bone.matrix.to_3x3() @ Vector((0.0, 0.0, 1.0)),
        }

    for bone in edit_bones:
        original = originals[bone.name]
        region = _bone_region(bone.name)
        bone.head = _warp_point(original["head"], region, transform, source_landmarks, target_landmarks)
        bone.tail = _warp_point(original["tail"], region, transform, source_landmarks, target_landmarks)

    # Snap the anatomical endpoints exactly to the confirmed markers.
    for role, (bone_name, endpoint) in DIRECT_ENDPOINTS.items():
        bone = edit_bones.get(bone_name)
        if bone is not None:
            setattr(bone, endpoint, target_landmarks[role])

    # Preserve wrist length within the confirmed wrist-to-hand span.
    for side, wrist_name in (("r", "Right wrist"), ("l", "Left wrist")):
        wrist = target_landmarks[f"wrist_{side}"]
        hand = target_landmarks[f"hand_{side}"]
        source_span = (source_landmarks[f"hand_{side}"] - source_landmarks[f"wrist_{side}"]).length
        source_wrist_length = (originals[wrist_name]["tail"] - originals[wrist_name]["head"]).length
        factor = max(0.12, min(0.65, source_wrist_length / max(source_span, 1e-9)))
        edit_bones[wrist_name].head = wrist
        edit_bones[wrist_name].tail = wrist.lerp(hand, factor)

    # The IK hand target is evaluated from its head, while the primary hand
    # marker maps to its tail.  Fit both endpoints explicitly; warping only the
    # tail leaves the inherited target head offset and pulls the arm chain away
    # from otherwise correct shoulder/elbow/wrist markers.
    for side, ik_name in (("r", "IK_Hand_R"), ("l", "IK_Hand_L")):
        control = edit_bones.get(ik_name)
        if control is not None:
            control.head = target_landmarks[f"wrist_{side}"]
            control.tail = target_landmarks[f"hand_{side}"]

    # Recompute pole controls from fitted limb planes, with the heroine's -Y
    # bend direction as the stable fallback for nearly straight A/T poses.
    limb_height = max((target_landmarks["head_top"] - target_landmarks["toe_l"]).length, 1e-6)
    pole_distance = limb_height * 0.22
    fallback = Vector((0.0, -1.0, 0.0))
    for side, pole_name in (("r", "Pole_Elbow_R"), ("l", "Pole_Elbow_L")):
        pole = edit_bones.get(pole_name)
        if pole is not None:
            head = _pole_position(
                target_landmarks[f"shoulder_{side}"], target_landmarks[f"elbow_{side}"],
                target_landmarks[f"wrist_{side}"], fallback, pole_distance,
            )
            pole.head = head
            pole.tail = head + Vector((0.0, 0.0, limb_height * 0.065))
    for side, pole_name in (("r", "Pole_Knee_R"), ("l", "Pole_Knee_L")):
        pole = edit_bones.get(pole_name)
        if pole is not None:
            head = _pole_position(
                target_landmarks[f"hip_{side}"], target_landmarks[f"knee_{side}"],
                target_landmarks[f"ankle_{side}"], fallback, pole_distance,
            )
            pole.head = head
            pole.tail = head + Vector((0.0, 0.0, limb_height * 0.065))

    # Align roll with the copied standard local-Z directions after scaling.
    for bone in edit_bones:
        axis = originals[bone.name]["roll_axis"]
        transformed_axis = Vector((axis.x * scales.x, axis.y * scales.y, axis.z * scales.z))
        if transformed_axis.length > 1e-8 and bone.length > 1e-8:
            bone.align_roll(transformed_axis.normalized())
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.data.use_mirror_x = mirror_x

    for pose_bone in rig.pose.bones:
        for constraint in pose_bone.constraints:
            if hasattr(constraint, "target") and constraint.target is not None and constraint.target.type == "ARMATURE":
                constraint.target = rig

    # The authoritative asset intentionally preserves its source pose channels,
    # but a newly fitted binding preview must start neutral.  Rebase the copied
    # pose onto the fitted rest skeleton, then solve pole angles against the
    # confirmed elbow and knee markers.
    reset_pose_bones = _reset_pose_basis(rig)
    pole_solutions = []
    for pose_bone_name, role in (
        ("Right elbow", "elbow_r"),
        ("Left elbow", "elbow_l"),
        ("Right knee", "knee_r"),
        ("Left knee", "knee_l"),
    ):
        solution = _optimize_pole_angle(rig, pose_bone_name, target_landmarks[role])
        if solution is not None:
            pole_solutions.append(solution)

    rig.show_in_front = True
    rig.display_type = "WIRE"
    rig["humanoid_fit_preview"] = True
    rig["humanoid_analysis_id"] = str(marker_collection.get("humanoid_analysis_id", ""))
    rig["humanoid_marker_collection"] = collection_name
    rig["humanoid_target_objects"] = json.dumps([obj.name for obj in target_objects], ensure_ascii=False)
    rig["humanoid_target_signature"] = json.dumps(signature, ensure_ascii=False, sort_keys=True)
    rig["humanoid_binding_approved"] = False
    rig["humanoid_pose_rebased"] = True
    rig["humanoid_pose_rebased_bones"] = json.dumps(reset_pose_bones, ensure_ascii=False)
    rig["humanoid_pole_solutions"] = json.dumps(pole_solutions, ensure_ascii=False)
    bpy.context.view_layer.update()

    validation = validate({"rigObject": rig.name, "markerCollection": collection_name})
    return {
        "ok": validation["ok"],
        "rig_object": rig.name,
        "armature_data": rig.data.name,
        "bone_count": len(rig.data.bones),
        "hair_bone_count": len([bone for bone in rig.data.bones if bone.name.startswith("头发")]),
        "target_objects": [obj.name for obj in target_objects],
        "validation": validation,
        "next_gate": "Inspect the fitted rig, then call humanoid_bind_preview with confirmed=true.",
        "saved": False,
    }


def validate(params):
    rig_name = str(params.get("rigObject") or "标准骨骼_人形拟合_待确认")
    rig = bpy.data.objects.get(rig_name)
    if rig is None or rig.type != "ARMATURE":
        raise ValueError(f"Fitted armature not found: {rig_name}")
    collection_name = str(params.get("markerCollection") or rig.get("humanoid_marker_collection") or DEFAULT_MARKER_COLLECTION)
    marker_collection, marker_objects = _read_markers(collection_name)
    template = _load_json(DEFAULT_TEMPLATE)
    expected_bones = {bone["name"] for bone in template["bones"]}
    actual_bones = {bone.name for bone in rig.data.bones}
    violations = []
    if actual_bones != expected_bones:
        violations.append({
            "type": "bone_set_mismatch",
            "missing": sorted(expected_bones - actual_bones),
            "extra": sorted(actual_bones - expected_bones),
        })
    hair = sorted(name for name in actual_bones if name.startswith("头发"))
    if hair:
        violations.append({"type": "excluded_hair_bones_present", "bones": hair})

    constraint_errors = []
    for pose_bone in rig.pose.bones:
        for constraint in pose_bone.constraints:
            for field in ("subtarget", "pole_subtarget"):
                target_name = getattr(constraint, field, "")
                if target_name and target_name not in actual_bones:
                    constraint_errors.append(f"{pose_bone.name}:{constraint.name}:{field}:{target_name}")
            if hasattr(constraint, "target") and constraint.target is not None and constraint.target != rig:
                constraint_errors.append(f"{pose_bone.name}:{constraint.name}:external_target:{constraint.target.name}")
    if constraint_errors:
        violations.append({"type": "constraint_errors", "items": constraint_errors})

    marker_errors = {}
    reference_height = max(
        (marker_objects["head_top"].matrix_world.translation - marker_objects["toe_l"].matrix_world.translation).length,
        1e-6,
    )
    tolerance = reference_height * 0.012
    for role, (bone_name, endpoint) in DIRECT_ENDPOINTS.items():
        bone = rig.data.bones.get(bone_name)
        if bone is None:
            continue
        local = bone.head_local if endpoint == "head" else bone.tail_local
        actual = rig.matrix_world @ local
        expected = marker_objects[role].matrix_world.translation
        error = (actual - expected).length
        marker_errors[role] = round(error, 7)
        if error > tolerance:
            violations.append({"type": "marker_fit_error", "role": role, "error": error, "tolerance": tolerance})

    # Rest endpoints can be perfect while inherited pose transforms and live IK
    # constraints visibly pull the evaluated rig away from the character.  A
    # binding preview must therefore validate the evaluated Pose Position too.
    bpy.context.view_layer.update()
    pose_marker_errors = {}
    for role, (bone_name, endpoint) in DIRECT_ENDPOINTS.items():
        pose_bone = rig.pose.bones.get(bone_name)
        if pose_bone is None:
            continue
        local = pose_bone.head if endpoint == "head" else pose_bone.tail
        actual = rig.matrix_world @ local
        expected = marker_objects[role].matrix_world.translation
        error = (actual - expected).length
        pose_marker_errors[role] = round(error, 7)
        if error > tolerance:
            violations.append({
                "type": "pose_marker_fit_error",
                "role": role,
                "error": error,
                "tolerance": tolerance,
            })

    pose_basis_errors = []
    for pose_bone in rig.pose.bones:
        delta = sum(
            abs(pose_bone.matrix_basis[row][column] - (1.0 if row == column else 0.0))
            for row in range(4)
            for column in range(4)
        )
        if delta > 1e-6:
            pose_basis_errors.append({"bone": pose_bone.name, "delta": round(delta, 7)})
    if pose_basis_errors:
        violations.append({"type": "pose_basis_not_neutral", "bones": pose_basis_errors})

    # Reject a side-view zig-zag center chain even when every individual rest
    # endpoint was snapped exactly to a bad marker.
    center_roles = ["pelvis", "spine_lower", "spine_upper", "chest", "neck", "head_base"]
    sagittal_steps = {}
    sagittal_step_tolerance = reference_height * 0.05
    for first, second in zip(center_roles, center_roles[1:]):
        step = abs(
            marker_objects[second].matrix_world.translation.y
            - marker_objects[first].matrix_world.translation.y
        )
        key = f"{first}->{second}"
        sagittal_steps[key] = round(step, 7)
        if step > sagittal_step_tolerance:
            violations.append({
                "type": "sagittal_chain_discontinuity",
                "segment": key,
                "error": step,
                "tolerance": sagittal_step_tolerance,
            })

    signature_ok = True
    target_objects = []
    try:
        target_objects, _ = _verify_signature(marker_collection)
    except Exception as error:
        signature_ok = False
        violations.append({"type": "target_signature", "message": str(error)})

    sagittal_marker_errors = {}
    if signature_ok:
        points = _evaluated_points(target_objects, 60000)
        minimum, maximum = _bounds(points)
        dimensions = maximum - minimum
        center_x = 0.5 * (minimum.x + maximum.x)
        central_limit = max(reference_height * 0.11, min(dimensions.x * 0.22, reference_height * 0.18))
        # Neck/head-base and ankle landmarks can legitimately sit away from a
        # clothing-section midpoint, so use section-depth rejection only for
        # the torso core and upper leg.  The full chain still participates in
        # continuity and evaluated-pose checks above.
        for role in ("pelvis", "spine_lower", "spine_upper", "chest"):
            position = marker_objects[role].matrix_world.translation
            stats = _slice_sagittal_stats(
                points, position.z, reference_height * 0.018, center_x, x_limit=central_limit,
            )
            if stats is None:
                continue
            error = abs(position.y - stats["center"])
            allowed = max(reference_height * 0.012, (stats["upper"] - stats["lower"]) * 0.35)
            sagittal_marker_errors[role] = round(error, 7)
            if error > allowed:
                violations.append({
                    "type": "sagittal_marker_depth",
                    "role": role,
                    "error": error,
                    "tolerance": allowed,
                })
        for side in ("r", "l"):
            for role in (f"hip_{side}", f"knee_{side}"):
                position = marker_objects[role].matrix_world.translation
                stats = _slice_sagittal_stats(
                    points, position.z, reference_height * 0.02, center_x, side=side,
                )
                if stats is None:
                    continue
                error = abs(position.y - stats["center"])
                allowed = max(reference_height * 0.012, (stats["upper"] - stats["lower"]) * 0.35)
                sagittal_marker_errors[role] = round(error, 7)
                if error > allowed:
                    violations.append({
                        "type": "sagittal_marker_depth",
                        "role": role,
                        "error": error,
                        "tolerance": allowed,
                    })

    return {
        "ok": not violations,
        "rig_object": rig.name,
        "marker_collection": collection_name,
        "bone_count": len(actual_bones),
        "hair_bone_count": len(hair),
        "constraint_error_count": len(constraint_errors),
        "target_signature_ok": signature_ok,
        "max_marker_error": max(marker_errors.values()) if marker_errors else None,
        "marker_errors": marker_errors,
        "pose_basis_neutral": not pose_basis_errors,
        "pose_basis_errors": pose_basis_errors,
        "max_pose_marker_error": max(pose_marker_errors.values()) if pose_marker_errors else None,
        "pose_marker_errors": pose_marker_errors,
        "sagittal_step_tolerance": round(sagittal_step_tolerance, 7),
        "sagittal_steps": sagittal_steps,
        "max_sagittal_marker_error": max(sagittal_marker_errors.values()) if sagittal_marker_errors else None,
        "sagittal_marker_errors": sagittal_marker_errors,
        "violations": violations,
        "saved": False,
    }


def bind_preview(params):
    if params.get("confirmed") is not True:
        raise ValueError("Binding approval is required: call with confirmed=true only after the user confirms the fitted rig")
    rig_name = str(params.get("rigObject") or "标准骨骼_人形拟合_待确认")
    rig = bpy.data.objects.get(rig_name)
    if rig is None or rig.type != "ARMATURE" or not rig.get("humanoid_fit_preview"):
        raise ValueError(f"Validated fitted rig preview not found: {rig_name}")
    validation = validate({"rigObject": rig.name, "markerCollection": params.get("markerCollection")})
    if not validation["ok"]:
        raise ValueError("Fitted rig validation failed; binding preview was not created")

    target_names = json.loads(str(rig.get("humanoid_target_objects", "[]")))
    targets = []
    for name in target_names:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise ValueError(f"Target mesh is missing: {name}")
        targets.append(obj)
    expected_signature = json.loads(str(rig.get("humanoid_target_signature", "{}")))
    if _mesh_signature(targets).get("sha256") != expected_signature.get("sha256"):
        raise ValueError("Target mesh or transform changed after fitting; binding preview was not created")

    collection_name = str(params.get("previewCollection") or DEFAULT_BIND_COLLECTION)
    existing_collection = bpy.data.collections.get(collection_name)
    if existing_collection is not None and existing_collection.objects and not params.get("replacePreview", False):
        raise ValueError(f"Binding preview collection already contains objects: {collection_name}")
    collection = _ensure_collection(collection_name)
    if params.get("replacePreview", False):
        for obj in list(collection.objects):
            if obj.get("humanoid_binding_preview"):
                bpy.data.objects.remove(obj, do_unlink=True)

    method = str(params.get("method") or "existing_groups")
    copies = []
    for source in targets:
        duplicate = source.copy()
        duplicate.data = source.data.copy()
        duplicate.name = f"{source.name}_绑定预览"
        duplicate.matrix_world = source.matrix_world.copy()
        duplicate.parent = None
        for modifier in list(duplicate.modifiers):
            if modifier.type == "ARMATURE":
                duplicate.modifiers.remove(modifier)
        duplicate["humanoid_binding_preview"] = True
        duplicate["humanoid_source_object"] = source.name
        collection.objects.link(duplicate)
        copies.append(duplicate)

    deform_names = {bone.name for bone in rig.data.bones if bone.use_deform}
    warnings = []
    if method == "existing_groups":
        for duplicate in copies:
            matched = sorted(group.name for group in duplicate.vertex_groups if group.name in deform_names)
            if not matched:
                warnings.append(f"{duplicate.name}: no compatible deform groups")
                continue
            modifier = duplicate.modifiers.new(name="标准骨骼绑定", type="ARMATURE")
            modifier.object = rig
            duplicate["humanoid_matched_groups"] = len(matched)
    elif method in {"automatic", "auto"}:
        for duplicate in copies:
            duplicate.vertex_groups.clear()
            duplicate.select_set(True)
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        try:
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        except Exception as error:
            raise RuntimeError(f"Blender automatic weights failed on duplicate meshes: {error}")
    else:
        raise ValueError("Unsupported binding method; use existing_groups or automatic")

    rig["humanoid_binding_approved"] = True
    bpy.context.view_layer.update()
    return {
        "ok": not warnings,
        "rig_object": rig.name,
        "method": method,
        "preview_collection": collection_name,
        "source_objects": target_names,
        "preview_objects": [obj.name for obj in copies],
        "warnings": warnings,
        "originals_modified": False,
        "saved": False,
    }


def dispatch(action, params=None):
    params = dict(params or {})
    if action == "analyze":
        return analyze(params)
    if action == "fit_standard":
        return fit_standard(params)
    if action == "validate":
        return validate(params)
    if action == "bind_preview":
        return bind_preview(params)
    raise ValueError(f"Unknown humanoid rig action: {action}")


if "ACTION" in globals():
    RESULT = dispatch(ACTION, globals().get("PARAMS", {}))
