# Opening executor contract

Each marker uses `blendercodex_opening_marker_v1=true`, a stable `blendercodex_opening_id`, `blendercodex_role`, `blendercodex_target_object`, `blendercodex_wall_axis`, and role-specific width, height, and sill properties. Live transform dimensions override stale size properties and conflicts appear in inspection results.

`componentsByObject` maps an object name to rows shaped as:

```json
{"id":"main","bounds":[-4,4,-6,6,0,4]}
```

Bounds are object-local `xmin,xmax,ymin,ymax,zmin,zmax`. Components must be rectilinear boxes large enough for twice the chosen wall thickness. Openings must resolve to an exterior X or Y facade. The executor builds a closed solid cell complex, subtracts marker volumes, creates `UV_4m_world_standard`, validates the detached candidate, then replaces the mesh data.

Automatic single-component inference is limited to a closed manifold 8-vertex, 12-edge, 6-quad axis-aligned box whose faces cover the local AABB planes. Supply explicit components or stop for non-box geometry. Explicit components are trusted caller input and must come from current scene inspection.

The first executor version rejects multi-material target meshes rather than losing per-face material assignments. It also rejects duplicate ids, facade-overlapping openings, and openings outside the valid wall span.
