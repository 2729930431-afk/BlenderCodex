# Learning Packet: Pose Rebase and Sagittal Fit

- `artifact`: `D:/Clone/scnvenger_assets/新角色资产/城镇男性组.blend`, character `001白德昌（中年男性）`, plus the user's frontal and side-view screenshots from 2026-08-06.
- `user_edit`: The user reviewed semantic markers and the fitted rig, rejected inherited arm/IK offsets, then reviewed the side view and corrected the spine, pelvis, hip, knee, and ankle depth plan before requesting a new fit.
- `observed_problem`: Rest endpoints reported zero marker error while Pose Position showed arms pulled toward the waist and pole controls floating above the character. After pose rebasing, the frontal view passed but the side view exposed a zig-zag spine and displaced thigh chain caused by topology-weighted clothing sections.
- `inferred_reason`: The copied authoritative rig retained non-identity source pose channels, and validation inspected only rest endpoints. Geometry recognition also used raw vertex medians, so dense outer garments biased sagittal depth away from anatomical centers.
- `future_rule`: A fitted preview must neutralize copied pose bases, explicitly fit IK control endpoints, recompute pole positions/angles, and validate evaluated Pose Position. Landmark recognition and validation must use robust front/back section bounds and reject sagittal center-chain discontinuities or core/leg joints near an outer shell.
- `scope`: `scoped_skill_rule`.
- `storage_target`: `humanoid-rigging/SKILL.md`, `references/humanoid-landmarks-and-fitting.md`, and `scripts/humanoid_rig_runtime.py`.
- `validation`: Blender integration must prove neutral pose bases, bounded Rest and Pose marker errors, preserved target signatures, and duplicate-safe binding previews; static tests must require the promoted rules and runtime checks.
- `limits`: Do not force a perfectly straight spine or world-axis pole direction on deliberately posed characters. Low-confidence, strongly posed, incomplete, or heavily occluded targets still require manual marker review.
