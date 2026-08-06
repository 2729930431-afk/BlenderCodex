# Humanoid Landmarks and Fitting

## Purpose

Use mesh evidence to decide whether a target is a humanoid, propose semantic joint markers, and fit the stored BlenderCodex humanoid template only after the user confirms those markers.

## Evidence and confidence

Treat humanoid recognition as a confidence-scored classification, not a bounding-box test. Inspect evaluated world-space geometry, connected components, symmetry, silhouette cross-sections, topology density, object names, and any existing vertex groups or armature modifiers.

Use `female-body-prior-v1.json` for the heroine's normalized landmark proportions and per-bone weighted-region statistics. The prior was extracted from the bound face, neck, hands, inner/outer clothing, trousers, shoes, ears, collar, and eyelashes; hair, scarf, whip, and small accessory proxies were excluded. Treat this as a geometric prior only. Copy the actual rig from `female-humanoid-v1.blend`.

Require evidence for one head above a torso, bilateral shoulder-to-hand chains, and bilateral hip-to-foot chains. Classify the pose as `t_pose`, `a_pose`, `neutral`, `posed`, or `unknown`. Do not automatically fit a standard rest skeleton to `posed` or `unknown` geometry.

Use these confidence levels:

- `high`: all major bilateral chains and joint bends are geometrically distinct.
- `medium`: the body is humanoid but one or more joints depend on symmetry or proportion inference.
- `low`: limbs overlap the torso, components are missing, the mesh is strongly posed, or clothing obscures the silhouette.

Stop before armature creation when overall confidence is below `0.75` or any required primary landmark is below `0.6`.

Recognition order:

1. Resolve only explicit or selected target mesh objects and compute an unchanged-target signature from base geometry, transforms, vertex counts, and polygon counts.
2. If a compatible existing armature is explicitly allowed, use its rest-bone endpoints as high-confidence calibration evidence.
3. Otherwise map the heroine body prior into the evaluated target bounds, refine the center chain from horizontal mesh sections, follow each arm silhouette independently, and refine each leg from side-specific cross-sections.
4. Classify the pose. Permit automatic fitting only for `t_pose`, `a_pose`, or verified reference-rest evidence; reject `posed` and `unknown` geometry.
5. Keep world `+Z` up, heroine right on `-X`, heroine left on `+X`, and forward on `-Y` for v1. Reject incompatible orientation instead of guessing.

## Marker contract

Create empties in `人形绑定标记_待确认`. Name them `HR_<role>`, store `humanoid_role`, `confidence`, `evidence`, and `source_object` as custom properties, and use world-space positions.

Required primary roles:

```text
pelvis
spine_lower spine_upper chest neck head_base head_top
shoulder_l elbow_l wrist_l hand_l
shoulder_r elbow_r wrist_r hand_r
hip_l knee_l ankle_l heel_l toe_l
hip_r knee_r ankle_r heel_r toe_r
```

Finger roles are optional and use `<finger>_<segment>_<side>`, for example `index_1_l`. Add them only when individual fingers and joints are separable from the evaluated mesh. Never invent finger markers from a closed fist or mitten-like geometry.

Show the marker plan and wait for explicit confirmation. Immediately before fitting, re-read the live collection. Treat user-moved markers as authoritative and user-deleted markers as rejected; never recreate or reset them unless asked.

Front-view agreement is not sufficient. Inspect the sagittal depth of the pelvis, every spine point, neck/head base, both hips, knees, and ankles. Estimate depth from the midpoint of robust front/back section bounds, blended with the anatomical prior; do not use a raw vertex median because dense outer-garment panels bias it toward a surface. Keep the pelvis-to-head chain continuous in `Y`, and require each hip/leg joint to remain in the central region of its corresponding body section.

## Fitting rules

Append or copy the Armature datablock from `assets/female-humanoid-v1.blend` and preserve its names, hierarchy, rest roll, deform flags, controller roles, bone collections, pose channels, and IK/copy-rotation constraints. Use `female-humanoid-v1.json` only for semantic mappings and validation metadata; never reconstruct the base rest rig from exported matrices.

Fit in armature-local space after deriving a target basis from the confirmed markers:

1. Set the origin and root from the pelvis and ground plane; preserve `+Z` as up unless the target basis proves otherwise.
2. Fit the pelvis-to-head chain piecewise through confirmed spine, chest, neck, head-base, and head-top markers. Do not use one uniform vertical scale for the full torso.
3. Fit each arm independently through shoulder, elbow, wrist, and hand markers. Preserve the template bone roll relative to the fitted chain plane.
4. Fit each leg independently through hip, knee, ankle, heel, and toe markers. Derive pole directions from the limb plane and reject nearly collinear ambiguous chains.
5. Fit finger chains only from confirmed finger markers. When fingers are unavailable, keep them unbound and report that manual fitting is required.
6. Place IK hand/foot controls at their fitted endpoints and pole controls along the confirmed limb-plane normal. Recompute rather than uniformly scaling stored controller offsets.
7. Keep optional breast bones only when the target needs them; otherwise retain them as non-deforming or omit them through an explicit option.

The authoritative asset may contain useful source pose channels, but a fitted binding preview must start neutral. Clear copied `PoseBone.matrix_basis` values after the rest fit, snap each hand IK control head to the confirmed wrist and tail to the confirmed hand, and recompute elbow/knee pole angles against the confirmed joints. For nearly straight T/A-pose limbs, treat small silhouette bends as noise and place poles along the stable world `-Y` fallback instead of above or beside the character.

The runtime starts from the exact appended Armature data, disables X-mirror only during edit-bone fitting, warps each torso/arm/leg region through its own confirmed anchors, snaps the 25 primary endpoints exactly, and restores the copied Armature setting afterward. Preserve roll by transforming the standard local-Z roll direction. Recompute elbow and knee poles from the fitted limb plane, using `-Y` only as the stable fallback for nearly straight limbs.

Do not include the 18 excluded hair bones. Hair, cloth, tails, accessories, and facial rigs are separate extension layers and must not be inferred as part of the standard body skeleton.

## Binding gate

Create the fitted armature on a new object and validate it before parenting or writing weights. Report the proposed deform bones, omitted optional bones, marker confidence, and known ambiguities. Bind only after explicit user approval.

Prefer existing verified weights when present. Otherwise start with empty vertex groups or automatic weights on a duplicate/detached data path, validate deformation using symmetric test poses, then atomically apply the approved result. Never overwrite an existing armature or weights without explicit permission.

`blendercodex_humanoid_bind_preview` intentionally creates duplicate mesh objects and duplicate mesh datablocks. `existing_groups` retargets compatible copied vertex groups to the fitted rig; `automatic` clears groups only on the duplicates before Blender automatic weighting. Neither mode modifies originals or saves the scene.

## Validation

Verify:

- all required semantic roles resolve to retained bones;
- parent hierarchy is acyclic and every parent exists;
- left/right chains remain on their confirmed sides;
- bone heads and tails remain inside or immediately adjacent to the intended body region;
- elbows and knees bend toward their pole markers;
- finger order and handedness are preserved;
- all constraints reference retained bones;
- all copied pose bases are neutral before preview evaluation;
- evaluated Pose Position endpoints remain within the same tolerance as Rest Position endpoints;
- the sagittal pelvis-to-head chain has no depth discontinuity and core/leg markers remain within robust front/back section bounds;
- the target mesh is unchanged before binding approval;
- a save/reopen check preserves the fitted armature after binding is approved.
