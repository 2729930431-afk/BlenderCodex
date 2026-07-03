# BlenderCodex Modeling Standards

Load this reference when translating an image or confirmed generated reference into Blender Python.

## Visual Simplification

- Model the object's stable base structure first: body massing, roofs, domes, arches, door and window openings, balconies, railings, stairs, and major trim.
- Ignore surface noise by default: wall stains, cracks, dirt, patches, tiny stones, chips, paint damage, labels, watermarks, and material aging.
- Ignore reference-image dimension marks unless the user explicitly says to honor them.
- Keep decorative detail at the readable silhouette and medium-detail level. Do not spend geometry on tiny texture-like marks.
- For house references, ignore doorplates, readable shop signs, painted text, animal-head trophies, antlers, and small wall ornaments by default unless the user asks for those details. Preserve the building mass, openings, roof form, balcony, railing, stairs, and major trim instead.
- For houses, establish the intended front facade from the reference before placing details. Entrances, storefronts, protruding balconies, and major facade trim should face the same direction, and the generated scene should record or name that front direction when practical.
- If the prompt asks for "like the image", preserve proportions and style cues, but simplify construction enough that the result is editable.

## Naming and Collections

- Use concise Chinese names for collections, objects, and materials unless the user requests another language.
- Prefer collection categories such as `主体结构`, `屋顶圆顶`, `门窗`, `阳台栏杆`, `装饰构件`, `楼梯地面`, and `辅助网格`.
- Put related objects in one collection. Avoid one large flat collection with every object at the root.
- Name repeated objects with readable suffixes, for example `栏杆立柱_01`, `栏杆立柱_02`.

## Geometry Rules

- Use custom mesh vertices and faces for forms whose shape matters: domes, arches, carved bands, curved pediments, relief panels, scalloped edges, and organic decorative profiles.
- Do not fake forms such as domes or carved reliefs by visibly stacking unrelated cubes, cylinders, and spheres.
- For two-storey houses, model the first and second storeys as one integrated structural shell or connected shell system, with continuous walls, coherent floor markers, and reserved/cut openings. Avoid treating each floor as a separate visible cube block.
- For tiled house roofs, use explicit repeated tile rows through modules, loops, or Array modifiers by default. Keep the roof plane, ridge, eaves, and tile spacing editable and avoid a single unarticulated slab when tiles are a visible design cue.
- For gabled house roofs, create the two short-side triangular gable wall faces as structural closure panels before adding roof trim and tile arrays. They should fill the side void from wall top to ridge, align with eaves and roof thickness, use wall or side-trim material, carry UVs, and avoid leaving a hollow roof triangle visible from side views.
- For house balconies, use a protruding exterior balcony by default when the reference includes one. The balcony slab, side returns, supports, and railing should connect logically to the main shell and cover all exposed edges.
- Basic primitives are acceptable for genuinely simple forms: flat walls, floors, rectangular beams, columns, window panes, railing rods, and simple posts.
- For repeated architectural parts, generate them with loops or reusable functions so the Python remains editable.
- Add bevels or bevel modifiers to soften hard architectural edges when appropriate, but keep modifier names and objects readable.

## Materials and UVs

- Assign simple base-color materials only. The user's later workflow should be material replacement, not rebuilding geometry.
- Do not create detailed procedural grime, cracks, stains, or photo-like material nodes unless the user asks.
- UV unwrap every mesh. Use proportional UVs and avoid obvious stretching.
- For curved custom meshes, ensure face layout is clean enough for Blender's unwrap or smart projection to produce usable islands.

## Deliverable Scope

- Do not add cameras, lights, render settings, animation, or world/background styling unless requested.
- The `.py` and `.blend` deliverables should use the same output directory by default.
- The `.blend` should open as an editable modeling file, not as a render-only scene.
