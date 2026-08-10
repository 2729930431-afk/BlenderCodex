# Verified Learning Packet: FBX Parent-Inverse Normalization

- `artifact`: User-edited `花山养殖场.blend`, its roof hierarchy, the exported `花山养殖场.fbx`, and the Unity scene instance.
- `user_edit`: The user moved building origins to roof symmetry centers, used one editable tile slope plus Mirror, and requested that the guesthouse roof be restored under the guesthouse without reintroducing Unity transform errors.
- `observed_problem`: Parented roof systems relied on non-identity Blender parent-inverse matrices. In the previous FBX, nested tile nodes imported with local scale `0.01`, while the temporarily unparented guesthouse roof imported consistently.
- `inferred_reason`: Blender's parent-inverse compensation is evaluated separately from the local basis, while FBX/Unity bake hierarchy transforms and unit conversion into node-local TRS. A compensated parent plus grandchildren therefore exposed an extra scale conversion. This reason is inferred from the transform formula and verified before/after round trips.
- `future_rule`: After any origin or parent edit in an ordinary FBX/Unity object hierarchy, preserve world matrices and normalize parented objects top-down to identity `matrix_parent_inverse` plus real local transforms. Restore intended ownership and use one explicit FBX scale policy.
- `scope`: `scoped_skill_rule` for FBX/Unity export and origin/parent-edit workflows.
- `storage_target`: `blendercodex/SKILL.md`, `blendercodex/references/fbx-unity-hierarchy.md`, and the roof-origin mirroring reference.
- `validation`: Compare protected Blender world matrices/bounds, save and reopen the `.blend`, round-trip a temporary FBX, reimport in Unity, inspect all roof parent chains, and verify representative nested roof nodes have local scale `1,1,1`.
- `limits`: Do not apply the ordinary-object normalization recipe blindly to armatures, bones, constraints, or animation-driven transforms.
