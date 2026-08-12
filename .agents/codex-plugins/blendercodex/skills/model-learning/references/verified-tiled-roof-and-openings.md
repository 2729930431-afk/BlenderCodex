# Verified Learning: 瓦片屋顶, L-Roof Boolean Trimming, and Opening Defaults

```yaml
artifact: D:/Clone/scnvenger_assets/村庄资产/云浮村/唐家.blend
user_edit: Completed the 唐老三家 L-shaped tiled roof and explicitly designated it as the future default; also required all unspecified doors and windows to use a 1.0 x 2.0 m rough opening.
observed_problem: The previous repair copied one Boolean target across slope domains. This produced an incorrect L-roof intersection even though the Array/Boolean modifier types looked consistent.
inferred_reason: The corrected scene proves that L-roof tile trimming is directional. Each slope must subtract the particular intersecting wing volume that occupies its rejected side; different slopes therefore use different dedicated cutter solids, and only suitable slopes use the visible structural base directly.
future_rule: Treat unspecified roofs as editable 瓦片屋顶 systems. For L shapes, use independent slope tile domains and a final per-slope Boolean Difference whose cutter is selected from the actual intersecting volume, not copied globally. Treat every unspecified door and window rough opening as 1.0 m wide by 2.0 m high.
scope: global_default
storage_target: skills/blendercodex/SKILL.md, skills/blendercodex/references/tiled-roof-system.md, and skills/blendercodex/references/hard-surface-topology-and-openings.md
validation: Inspect the authoritative live scene for separate wing-specific Boolean cutter targets; test the skill text, default dimensions, reference routing, cachebuster, and plugin manifest.
limits: A stated roof construction or opening size overrides the defaults. Simple uninterrupted slopes do not need Boolean cutters, and cutter selection must follow geometry rather than names.
```

## Scene Evidence

- `唐老三家.东翼北坡.板瓦源` and `唐老三家.东翼北坡.筒瓦源` use `唐老三家屋顶_布尔原型1`.
- `唐老三家.西翼西坡.板瓦源` and `唐老三家.西翼西坡.筒瓦源` use `唐老三家屋顶_布尔原型2`.
- Other slope domains use the coherent visible base where that volume yields the intended retained tiles.
- The corrected modifier order is `沿檐口阵列`, `沿坡向叠瓦阵列`, then `布尔` with `DIFFERENCE` and `MANIFOLD`.
- The cutter prototypes are separate closed six-face solids spanning beyond the relevant tile intersections.
