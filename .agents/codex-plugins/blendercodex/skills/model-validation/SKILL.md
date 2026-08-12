---
name: model-validation
description: Validate Blender hard-surface mesh topology, world-density UVs, stable protected-object signatures, modifier contracts, and serialized model integrity. Use with BlenderCodex for 模型验证、拓扑检查、非流形、退化面、UV_4m_world_standard、保护签名, regression checks, or final verification after architectural edits.
---

# Model Validation

Use the shared validator before committing or reporting a substantial Blender mesh edit.

## Workflow

1. Call `blendercodex_model_signature` before mutation for protected objects.
2. Run the owning executor on detached candidates and commit only after its validation succeeds.
3. Call `blendercodex_validate_model` for explicit changed mesh objects.
4. Compare protected signatures after mutation. When serialized verification is required, save, explicitly reopen through BlenderCodex, then call the signature/validation tools again; the current validator does not reopen files itself.
5. Finish the task after checks pass; do not add a completion confirmation gate unless the user requested one.

## Acceptance checks

- zero wire edges and degenerate edges/faces;
- zero unexpected boundary/non-manifold edges;
- active/render `UV_4m_world_standard` with `(uv_length*4)/world_length` within 2%;
- stable canonical SHA-256 fingerprints without pointer or `repr` values;
- unchanged protected transforms, raw geometry, materials, collections, parenting, custom properties, and key modifier references.

The pure helpers in `scripts/geometry_core.py` are used by unit tests and runtimes. The Blender adapter in `scripts/model_validation_runtime.py` is authoritative for mesh wire-edge and modifier inspection.
