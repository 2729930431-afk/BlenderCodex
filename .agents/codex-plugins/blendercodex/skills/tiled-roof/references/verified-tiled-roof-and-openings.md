# Verified Evidence: 瓦片屋顶 and L-Roof Boolean Trimming

```yaml
artifact: D:/Clone/scnvenger_assets/村庄资产/云浮村/唐家.blend
user_edit: Completed the 唐老三家 L-shaped tiled roof and designated its editable construction and per-slope trimming behavior as the future default.
observed_problem: The previous repair copied one Boolean target across slope domains, producing an incorrect L-roof intersection even though modifier types looked consistent.
inferred_reason: L-roof tile trimming is directional. Each slope must subtract the intersecting wing volume occupying its rejected side, so neighboring slopes may require different cutter solids.
implemented_by: skills/tiled-roof/scripts/tiled_roof_runtime.py l_boolean domain action and its focused MCP build/validate routes
future_rule: Use independent slope tile domains and a final per-slope Boolean Difference whose cutter is selected from the actual intersecting volume rather than copied globally.
validation: Run tiled-roof unit, MCP, and Blender fixture checks; inspect each L-domain cutter target, modifier order, source topology, and evaluated boundary before accepting the result.
limits: A stated roof construction overrides the default. Simple uninterrupted slopes do not need Boolean cutters, and automatic general L-roof cutter inference is not supported.
```

## Scene Evidence

- `唐老三家.东翼北坡.板瓦源` and `唐老三家.东翼北坡.筒瓦源` use `唐老三家屋顶_布尔原型1`.
- `唐老三家.西翼西坡.板瓦源` and `唐老三家.西翼西坡.筒瓦源` use `唐老三家屋顶_布尔原型2`.
- Other slope domains use the coherent visible base where that volume yields the intended retained tiles.
- The corrected modifier order is `沿檐口阵列`, `沿坡向叠瓦阵列`, then `布尔` with `DIFFERENCE` and `MANIFOLD`.
- The cutter prototypes are separate closed six-face solids spanning beyond the relevant tile intersections.
