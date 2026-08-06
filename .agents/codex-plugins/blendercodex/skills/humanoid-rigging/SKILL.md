---
name: humanoid-rigging
description: Extract, validate, recognize, fit, import, or bind Blender humanoid armatures from character meshes using the BlenderCodex standard skeleton. Use with BlenderCodex for 人形识别、人形骨骼、骨骼绑定、自动绑骨、骨架导入、关键关节识别、T-pose/A-pose fitting, armature templates, skinning, IK controls, or retargetable character-rig preparation.
---

# Humanoid Rigging

## Overview

Use BlenderCodex live RPC to turn character geometry into a confirmed semantic landmark plan, fit the recorded standard humanoid skeleton, and bind only after a separate approval gate. Preserve the target mesh and any existing rigs or weights.

## Coordination

- Use `blendercodex` for RPC startup, live inspection, targeted `bpy` execution, saving, and source-model preservation.
- Use `model-learning` when a user-corrected skeleton or landmark placement should become a durable template rule.
- Read `references/humanoid-landmarks-and-fitting.md` before recognizing a target mesh, creating landmarks, fitting bones, or binding weights.
- Use `assets/female-humanoid-v1.blend` as the authoritative standard body skeleton.
- Read `references/female-humanoid-v1.json` only for semantic roles, measurements, inspection, and validation metadata. Never reconstruct the exact rest rig from the JSON matrices.
- Use `references/female-body-prior-v1.json` as the heroine-derived proportion, landmark, and weighted-region prior. It excludes hair and accessory meshes and is not a replacement for the authoritative Armature asset.

## Route the task

- **Record a standard:** run `scripts/build_humanoid_rig_asset.py` to copy the real Object and Armature datablocks, then remove explicitly scoped accessory bones only from the copy. Export JSON metadata separately with `scripts/extract_humanoid_template.py`.
- **Preview or import the standard:** append `assets/female-humanoid-v1.blend`, or copy the approved source object with `source.copy()` plus `source.data.copy()` when it is already in the scene. Remap self-targeting pose constraints to the copy, then remove excluded bones on the copied datablock.
- **Recognize a target:** inspect evaluated mesh geometry and existing rig evidence read-only, classify humanoid confidence and pose, then create semantic empty markers only.
- **Fit a skeleton:** re-read confirmed markers and construct a new armature from the standard hierarchy while fitting each anatomical chain independently.
- **Bind a mesh:** require a second explicit approval after the fitted armature validates; then create or transfer weights without overwriting existing rig data.

## Live RPC tools

Use the specialized tools instead of rewriting the fitting algorithm in an ad hoc `bpy` snippet:

1. Call `blendercodex_humanoid_analyze` with explicit target mesh names or a target collection. It inspects evaluated geometry, records a target signature, and creates only `HR_<role>` empties in `人形绑定标记_待确认`.
2. Show the markers and wait for explicit user approval. Preserve moved markers and missing/deleted markers.
3. Call `blendercodex_humanoid_fit_standard` with `confirmed=true`. It refuses unconfirmed requests, rechecks the target signature, appends the authoritative `.blend` Armature, fits the copied bones, and returns validation without binding or saving.
4. Call `blendercodex_humanoid_validate` whenever markers or the preview need rechecking.
5. Show the fitted rig and wait for a separate binding approval. Then call `blendercodex_humanoid_bind_preview` with `confirmed=true`; default to `existing_groups` when compatible weights exist, otherwise use `automatic`. Both paths work on duplicated mesh datablocks and do not save.

The next Codex task loads newly installed MCP tools; a task that predates the plugin update continues to expose its older tool list.

## Standard template

Treat `assets/female-humanoid-v1.blend` as the current authoritative standard. It is a direct Blender datablock copy of `女主骨骼` from `新角色资产/主角建模.blend`, with only the scoped hair bones removed from the copy. It preserves exact Blender rest matrices, bone roll, pose channels, bone collections, and self-targeting constraints without format conversion.

Treat `references/female-humanoid-v1.json` as metadata, not as a lossless construction format. Use it for semantic roles, measurements, reports, and validation. Do not create EditBones by assigning exported `Bone.matrix_local` values to `EditBone.matrix`; those APIs do not provide a lossless round trip for this rig and visibly corrupt the rest pose.

The source contained 94 bones. The template excludes the 18 bones whose names begin with `头发`, retaining 76 bones: 54 deform bones and 22 controller/end bones. Do not silently restore excluded hair chains.

## Recognition and landmark approval gate

1. Inspect all target mesh objects, evaluated transforms, connected components, symmetry, silhouette, topology, existing vertex groups, and modifiers without changing the scene.
2. Reject or defer targets that are not clearly humanoid, are strongly posed, are incomplete, or have ambiguous limb separation.
3. Create semantic empties in `人形绑定标记_待确认` only. Include confidence and evidence custom properties.
4. Validate markers from both the frontal and sagittal views. Use robust front/back section bounds rather than topology-weighted vertex medians; loose coats, boots, and dense facial panels must not pull the spine, pelvis, hips, knees, or ankles onto an outer shell. Reject a zig-zag spine or thigh chain whose joint centers leave the intended body section.
5. Summarize required, optional, missing, and low-confidence landmarks. Wait for explicit user confirmation.
6. Immediately before fitting, re-read the live marker collection. Preserve user-moved markers and treat deleted markers as rejected. Never recreate or reset them unless asked.

Do not create an armature, parent meshes, add armature modifiers, create vertex groups, or write weights before marker confirmation.

## Fitting and binding approval gate

1. Build the candidate by appending/copying the authoritative `.blend` Armature datablock onto a new object; never rewrite an existing rig in place and never reconstruct the base rig from JSON.
2. Preserve standard bone names, hierarchy, handedness, deform flags, IK controls, pole controls, and supported constraints.
3. Fit torso, left/right arms, left/right legs, hands, and fingers as independent anatomical chains. Do not solve the body with one bounding-box scale.
4. Validate hierarchy, joint placement, roll, bend planes, left/right symmetry, constraint targets, and mesh clearance.
5. Rebase inherited source pose channels to identity on the fitted preview, fit each hand IK control from wrist to hand, place nearly straight limb poles along the stable `-Y` fallback, and solve pole angles against the confirmed elbow/knee markers.
6. Validate both Rest Position and evaluated Pose Position. A zero rest-marker error is not sufficient when live IK constraints pull the visible rig away from the markers.
7. Present the fitted armature result and wait for explicit binding approval.
8. After approval, bind through a detached or duplicate-safe data path, test representative symmetric poses, then save and reopen before reporting completion.

If finger landmarks cannot be established, leave finger bones unbound and report the manual work required. Treat facial bones, hair, cloth, tails, and accessories as separate rig layers.

## Extract a standard

Build the lossless `.blend` asset inside Blender:

```powershell
blender -b <source.blend> --python scripts/build_humanoid_rig_asset.py -- `
  --armature "女主骨骼" `
  --exclude-prefix "头发" `
  --expect-retained 76 `
  --expect-excluded 18 `
  --output assets/female-humanoid-v1.blend
```

Export JSON metadata separately:

```powershell
blender -b <source.blend> --python scripts/extract_humanoid_template.py -- `
  --armature "女主骨骼" `
  --exclude-prefix "头发" `
  --output references/female-humanoid-v1.json
```

Then validate outside Blender:

```powershell
python scripts/validate_humanoid_template.py references/female-humanoid-v1.json
```

Extract the heroine body prior from explicitly scoped bound body proxies:

```powershell
blender -b <source.blend> --python scripts/extract_humanoid_body_prior.py -- `
  --armature "女主骨骼" `
  --template references/female-humanoid-v1.json `
  --output references/female-body-prior-v1.json
```

Validate the `.blend` asset against the source inside Blender:

```powershell
blender -b <source.blend> --python scripts/validate_humanoid_rig_asset.py -- `
  --source-armature "女主骨骼" `
  --asset assets/female-humanoid-v1.blend `
  --exclude-prefix "头发" `
  --expect-retained 76 `
  --expect-excluded 18
```

Regenerate the standard only from an explicitly approved source armature. Template regeneration is a reusable plugin change, so update tests and the plugin cachebuster after validation.

## Validation minimums

- Confirm the standard validator returns `ok: true`.
- Confirm the authoritative `.blend` asset has zero rest-data mismatches against the source after exclusions.
- Confirm the template retains 76 bones and no retained name begins with `头发`.
- Confirm required semantic roles resolve and all constraint subtargets exist.
- Confirm the heroine body prior resolves 25 required primary landmarks, uses only approved body-proxy meshes, and records weighted regions without hair/accessory objects.
- Confirm the target mesh remains byte-for-byte or signature-equivalent before binding approval.
- Confirm the fitted armature is a new object and the original rig/weights remain recoverable.
- Confirm copied pose bases are neutral, the evaluated Pose Position remains within marker tolerance, the sagittal center chain is continuous, and pelvis/hip/leg markers remain within robust body-section depth.
- After approved binding, exercise shoulders, elbows, wrists, hips, knees, ankles, and available fingers; save and reopen the `.blend`.
