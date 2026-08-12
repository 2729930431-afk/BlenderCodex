# Verified Evidence: Distinct Door and Window Opening Sizes

```yaml
artifact: D:/Clone/scnvenger_assets/村庄资产/云浮村/方国伟家.blend
user_edit: The user rejected a shared 1.0 x 2.0 m size for door and window markers and required the plugin to keep door and window dimensions distinct.
observed_problem: One shared fallback pair erased the semantic and vertical distinction between floor-level doors and elevated windows.
inferred_reason: Opening role is binding evidence. Doors begin at the floor and are sized for passage, while windows normally have a sill and a different aspect ratio; door and window roles must not share one fallback width-and-height pair.
implemented_by: skills/architectural-openings/scripts/opening_core.py ROLE_DEFAULTS and skills/architectural-openings/scripts/opening_runtime.py marker creation/application
future_rule: Without stronger evidence, use a single-leaf door rough opening of 1.0 m wide by 2.1 m high with a 0.0 m sill, and a window rough opening of 1.2 m wide by 1.5 m high with a 0.9 m sill.
validation: Run the architectural executor unit and Blender integration tests; verify marker transforms and metadata use the same role-specific values and the two fallback width/height pairs differ.
limits: Explicit user dimensions and binding design evidence override these fallbacks. Additional door or window families may use different sizes when facade hierarchy supports them.
```

## Scene Evidence

- Standard single-leaf door markers use `1.0 x 2.1 m` at floor level.
- The main double-door marker uses `1.8 x 2.4 m`, derived from the main-entry hierarchy.
- Standard outbuilding window markers use `1.2 x 1.5 m` with a `0.9 m` sill.
- Main-house window markers use `1.5 x 1.5 m`; ear-room window markers use `1.0 x 1.2 m`, preserving distinct facade families.
- The accepted tiled-roof system was outside the correction scope and remained unchanged.
