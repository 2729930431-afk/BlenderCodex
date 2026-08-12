---
name: blendercodex
description: Generate new Blender .blend projects from scratch, or update existing/open Blender projects through a temporary live RPC bridge without installing a Blender add-on. Use when the user asks for BlenderCodex, image-to-Blender, text-to-Blender, direct .blend file generation, Blender Python modeling, Blender file inspection, live Blender scene control, temporary Blender RPC/bridge control, window/opening creation, or any hard-surface mesh generation, cleanup, retopology, topology rewrite, or edit that must preserve user changes.
---

# BlenderCodex

## Overview

BlenderCodex has two primary routes. Choose the route from the user's request before writing or running Blender code:

- **Create model / 起模型**: build a new Blender project from scratch. Locate Blender, run it in background mode, execute generated `bpy` code through a temporary Python file, and save a new `.blend` deliverable. Save a `.py` script only when the user asks for source, reproducibility, or debugging.
- **Edit model / 改模型**: modify an existing or currently open Blender project. Start Blender through the temporary live RPC bridge with the user-specified `.blend` file. If the user does not specify a file, infer the `.blend` file from the user's currently open Blender process and start a bridged Blender instance for that project. If the open project cannot be inferred, ask for the `.blend` path. Do not use keyboard/mouse UI injection as the normal edit path.

For existing `.blend` file regeneration or batch edits outside live control, compare the current scene state before changing or regenerating anything so user edits can be reviewed and preserved. Do not create backup `.blend` copies unless the user explicitly asks for a backup.

The temporary live RPC bridge launches Blender with a one-shot `--python` bridge script from the Codex plugin directory. It does not install a Blender add-on, does not copy files into Blender's add-on directory, and disappears when that Blender process exits or the bridge is shut down.

For text-only requests, first generate one reference image, show it to the user, and wait for confirmation before generating Blender code. If the user provides images, use them directly as the primary reference.

## Workflow

1. Route the task.
   - If the user asks to create, generate, build from a reference, or make a new Blender scene/project, use **Create model / 起模型**.
   - If the user asks to change, remove, add to, inspect, clean up, operate, or prove control of an existing/open Blender scene, use **Edit model / 改模型** with the temporary live RPC bridge.
   - If the request is ambiguous, infer from object references: named existing collections/objects, "my opened Blender", "current project", or "this model" usually mean edit model.

2. Classify create-model input.
   - If the user provides one or more images, use them as the reference and proceed.
   - If the user provides only text, generate one reference image and wait for confirmation or revision before generating Blender code.
   - If the user provides text plus images, treat the images as the primary form reference and the text as constraints.

3. Choose output paths for create-model work.
   - Default the deliverable to a `.blend` file in the user-specified directory, otherwise the current workspace output directory when available.
   - Do not leave a `.py` artifact unless the user explicitly asks to keep the script.
   - When keeping a script, use matching basenames such as `model.py` and `model.blend`.

4. Resolve Blender.
   - On first use, run `scripts/blender_locator.py find --json` to find and cache the highest local Blender version.
   - If the user specifies a version, pass `--version <version>` and choose the highest matching install.
   - If the user provides an explicit executable, run `scripts/blender_locator.py set --path <path> --json`.
   - The locator stores the path under `$CODEX_HOME/blendercodex/config.json`, falling back to `~/.codex/blendercodex/config.json`.

5. Compare existing `.blend` edits before changing anything unless the user says not to.
   - If the target `.blend` already exists and the user has not said to skip comparison, run `scripts/capture_blend_state.py capture-edits --blend <file.blend> --script <file.py>` before modifying or regenerating it.
   - The default comparison uses a temporary directory and leaves no `.blendercodex` sidecar files behind.
   - Use `--state-dir <state-dir>` only when the user explicitly wants persistent snapshots or reports.
   - Treat objects, materials, or collections added, removed, or changed in the current `.blend` as user edits until the user says otherwise.
   - If the user says no comparison is needed, pass `--skip-existing-capture` to `scripts/run_blender_model.py`.
   - Choose the safer update path after reading the report:
     - Direct `.blend` file edit: run targeted Blender Python in background mode against the existing file when user edits should remain in place.
     - Script merge: encode the reported user edits back into kept Blender Python only when the user requested a script artifact.

6. Generate Blender code.
   - Follow `references/modeling-standards.md` for visual simplification and mesh decisions.
   - Follow `references/script-contract.md` for the generated code's command-line contract, save behavior, UV handling, and verification expectations.
   - Use concise Chinese names for collections and objects unless the user explicitly asks otherwise.
   - Prefer internal temporary execution: send the generated code to `scripts/run_blender_model.py --code-file - --output-blend <file.blend>`.
   - If the user asks to keep the Python, write the `.py` and run `scripts/run_blender_model.py <script.py> --output-blend <file.blend>`, or use `--script-output <file.py>` with `--code-file`.

7. Execute and verify.
   - Run `scripts/run_blender_model.py --code-file - --output-blend <file.blend>` to create the `.blend` without leaving a `.py` file.
   - Use `scripts/run_blender_model.py <script.py> --output-blend <file.blend>` only when there is an existing or explicitly requested script artifact.
   - When `<file.blend>` already exists, the runner automatically runs a temporary comparison before overwriting unless `--skip-existing-capture` is used.
   - Confirm that the `.blend` exists and that the Blender run completed without errors. Confirm `.py` only when it was explicitly requested.
   - If Blender cannot be found, ask the user for the Blender executable path and cache it with `blender_locator.py set`.

## Temporary Live RPC

Use this mode for edit-model work, live scene control, real-time Blender operation, or temporary RPC/bridge control.

1. Start or connect to a bridged Blender process.
   - Preferred: call `blendercodex_start_bridge` with `blendFile` when the user specifies a target `.blend`.
   - If the user does not specify a target `.blend`, call `blendercodex_start_bridge` without `blendFile`; the tool should infer the `.blend` path from the user's currently open Blender process and start the bridged Blender UI for that project.
   - If more than one open `.blend` project is detected or no open project can be inferred, ask the user which `.blend` file to use.
   - If Blender is already bridged, call `blendercodex_bridge_ping` and `blendercodex_scene_summary`.
   - If Blender cannot be found automatically, ask for `blenderPath` and pass it to `blendercodex_start_bridge`.
   - For visible Blender UI bridge launches, do not pass `keepAlive`; it is only for background automation. The MCP server ignores `keepAlive` unless `background` is true.
2. Edit the live scene through the bridge.
   - Use `blendercodex_scene_summary` to inspect current collections, objects, and file path.
   - Use `blendercodex_run_python` for targeted `bpy` changes. Set `RESULT` in the code to return structured data.
   - Use specialized bridge tools such as `blendercodex_prune_collection` when they match the request.
3. Save or stop.
   - Use `blendercodex_save` when the live scene changes should be written to disk.
   - Use `blendercodex_shutdown_bridge` when the user wants to stop RPC access while leaving Blender open.
   - Closing Blender also removes the temporary bridge.

Temporary live RPC rules:

- Do not require users or teammates to install a Blender add-on.
- Do not use or mention a persistent Blender-side listener as the normal workflow.
- Do not assume Codex can attach RPC to a Blender process that was already launched normally. To edit an already open project, start a new bridged Blender instance for that same `.blend` file unless the current process was already started with the bridge.
- The bridge listens only on localhost, uses a per-session token, and writes the active session under `$CODEX_HOME/blendercodex/`.
- `keepAlive` is background-only. Passing it to a visible UI launch can keep Blender's script thread in a bridge loop, leaving RPC reachable while Windows reports the Blender window as not responding.
- Do not create backup `.blend` copies during live RPC edits unless the user explicitly requested a backup. Use targeted edits and verification instead.
- For create-model work, prefer the background `.blend` workflow unless the user specifically asks for live scene control.

## Mandatory Window Opening Approval Gate

Apply this gate whenever the user asks to add, cut, create, arrange, move, or revise windows or comparable wall openings.

1. Inspect the real building mesh, wall thickness, floor bands, existing doors/windows, facade rhythm, corners, and structural conflicts before proposing locations. Classify it as interior-ready only when the intended opening zones have a usable cavity plus paired exterior/interior wall faces; a closed solid, exterior-only sheet, single facade face, or disconnected panel is not interior-ready.
2. Create or update semantic empty-object markers only. Put them in a pending-confirmation collection such as `窗位标记_待确认`; align each marker to its target wall and set its dimensions to the intended rough opening size. Give markers stable facade/floor names and opening metadata when practical.
   - Unless the user or binding design evidence specifies another size, use a `1.0 m` rough width and `2.0 m` rough height for every door and window. Store the same authoritative values in `blendercodex_opening_width` and `blendercodex_opening_height`; do not silently substitute a type-specific window size.
3. Show or summarize the marker plan and wait for explicit user confirmation. Do not cut, boolean, delete, rebuild, or otherwise change the target wall mesh before confirmation.
4. After confirmation, re-read the live marker collection. Treat marker transforms as authoritative: preserve user-moved markers, honor deleted markers as removed openings, and never recreate or reset them unless asked.
5. If the target is not interior-ready, first preserve the approved exterior while rebuilding it as a coherent thickness-aware hollow shell. Validate the usable cavity and continuous inner wall surfaces before cutting anything.
6. Cut only the confirmed markers through the full wall thickness, then standardize the exterior face, interior face, and reveal topology together under the hard-surface contract. Keep members of the same window family equal in rough width and height unless the user explicitly defines multiple sizes.
7. Treat raw Boolean output as an intermediate at most. Before delivery, rebuild the affected facade into facade-local sill/head bands and jamb/bay strips; do not leave Boolean diagonals, triangle fans, slivers, or opening coordinates propagated into adjacent blank walls, corners, floors, or roof caps.
8. Keep the marker collection hidden or otherwise non-obstructive after validation, but preserve it when future revision context is useful.

## Mandatory Hard-Surface Topology Contract

- For every hard-surface mesh creation or edit, read `references/hard-surface-topology-and-openings.md` before changing geometry. This applies to buildings, architectural shells, props, machines, vehicles, furniture, and any mesh whose form depends on deliberate planar, sharp, beveled, or manufactured surfaces.
- Preserve approved shapes, object transforms, opening positions, meaningful seams, sharp edges, material assignments, and unrelated user edits. Capture a baseline signature for protected geometry before a localized topology rewrite.
- Align edge flow to real features. Rectangular wall openings use continuous sill/head bands and vertical jamb/bay strips on both exterior and interior surfaces; do not leave Boolean diagonals or an unstandardized inner wall after cleaning the outer wall.
- Localize those bands to the wall and height interval that owns the feature. Never solve a multi-opening building with a global Cartesian grid that propagates every jamb, sill, or head coordinate across unrelated facades, floors, slabs, ceilings, or blank wall areas.
- Interpret minimal topology as the fewest purposeful feature loops, not the fewest faces. Preserve structural elevation rings and user-authored quad loops that wrap adjoining exterior, interior, gable, reveal, or slab faces, even when a coplanar rectangle merge is technically possible.
- Prefer quads and simple planar rectilinear n-gons. Do not introduce convenience diagonals, triangle fans, overlapping faces, duplicate coincident edges, wire edges, degenerate faces, or avoidable poles. Curved, sloped, triangular, and beveled features may use non-orthogonal edges where the shape genuinely requires them.
- For substantial topology rewrites, work on an object-mode mesh copy or detached BMesh, validate it, then atomically assign it to the object. Avoid destructive in-place Edit Mode BMesh rewrites combined with a manual undo push and immediate save.
- Rebuild and verify `UV_4m_world_standard` after topology changes. Make it active/render and retain one UV unit per four world units.
- Validate target face counts or coverage, normals, opening clearance, protected-geometry signatures, wire/degenerate geometry, and boundary/non-manifold counts. Save and reopen the serialized `.blend` after a substantial rewrite before reporting completion.

## Modeling Defaults

- Do not add cameras or lights unless the user explicitly requests them.
- Ignore all reference-image dimension labels unless the user says those dimensions are binding.
- Ignore wall stains, patches, surface damage, grime, tiny material details, and ornamental micro-detail by default.
- Preserve the basic structure: massing, roofs, domes, arches, doors, windows, balconies, simple railings, stairs, major trim, and large decorative forms.
- For house generation, default to a house-specific prompt contract: ignore doorplates, readable signs, animal-head trophies, antlers, and other small wall ornaments unless the user explicitly asks for them; keep the front facade orientation clear from the reference and place entrances, shopfronts, balconies, and major facade details on that intended face.
- For every repeated brick or roof-tile element, use unapplied Blender Array modifiers with editable source modules, counts, spacing, and overlap. Do not hand-duplicate, join, or bake repeated bricks or tiles into a one-off mesh. Do not flatten tile roofs into a single painted plane when the reference clearly depends on repeated tiles.
- Unless the user requests another roof construction, treat every request to make or revise a building roof as a **瓦片屋顶 (tiled roof)**. Read `references/tiled-roof-system.md` and build the editable structural base, pan-tile and cover-tile sources, ridge/edge tiles, and modifiers described there. This default defines construction, not roof silhouette: preserve the requested gabled, hipped, L-shaped, single-slope, or other form.
- Keep each generated roof system in the owning roof's hierarchy: link tile arrays, ridge tiles, trims, and other roof-related child objects to the same collection or collections as the roof, and parent them directly to the owning roof object. Do not create a dedicated one-roof collection solely to hold generated roof parts. Preserve user-authored roof parenting and collection placement during later edits.
- For a symmetric two-slope gabled roof, read `references/roof-origin-mirroring.md`. Default to one authoritative slope's editable pan-tile and cover-tile Array sources, then a final unapplied Mirror modifier that uses the owning building root as its mirror object. Place that building origin at the roof-plan symmetry center on ground Z while preserving the building mesh and every descendant's world-space transform. Keep ridge tiles independent. Do not collapse genuinely asymmetric, hipped, dormered, penetrated, damaged, or slope-specific roofs into this pattern.
- For gabled house roofs, always close both short-side triangular gable faces under the roof slopes unless the reference clearly shows an open pavilion or exposed truss. The gable panels should align to the wall top, eaves, ridge, and roof thickness, use the wall/trim material as appropriate, and be UV-processed like other structural wall geometry.
- For two-storey houses, keep first-floor and second-floor structure integrated through one coherent main shell or connected structural mesh system. The whole wall body should read as continuous architecture with wall thickness, reserved/cut openings, and floor markers, not as separated stacked wall blocks.
- For house balconies, default to a protruding balcony when the reference shows an exterior balcony. Build the balcony slab, side returns, supports, and full exposed-edge railing as structural geometry attached to the main shell rather than as a flat facade decoration.
- For any building model or edit, calculate or infer floor count and floor bands before placing facade elements. Split building structure by floor when practical, keep stable floor markers with `blendercodex_floor_*` custom properties, and use those markers as the reference for windows, doors, stairs, and later internal-structure work. If markers are absent in an existing model, infer floors from exterior window and door rows before adding new facade or internal elements.
- For house and building main bodies, do not fake the primary structure by stacking separate cube blocks. Build the main body as an integrated shell or connected structural mesh, optionally split by floor or wing for editing, with coherent wall thickness, openings, and floor markers so future internal decoration and structural expansion have clean anchors.
- Use continuous custom meshes for curved domes, carved bands, relief profiles, arched trim, and other forms that would look artificial if made by stacking primitive blocks.
- Basic primitives are acceptable for simple slabs, flat walls, cylinders, posts, panes, and repeating railing rods.
- Assign basic color materials so the user can later replace materials directly.
- UV unwrap every mesh with stable proportions and no obvious stretching.

## FBX and Unity Hierarchy Safety

- For any FBX/Unity task that reparents objects or moves origins inside an export hierarchy, read `references/fbx-unity-hierarchy.md` before saving or exporting.
- Do not leave ordinary export objects dependent on non-identity `matrix_parent_inverse` compensation. Preserve each world matrix, normalize parented objects top-down to an identity parent inverse plus a real local `matrix_basis`, and verify world matrices and evaluated bounds afterward.
- Restore intentional ownership before export. A roof stays under its building, and its tile arrays, ridge tiles, and trims stay under that roof; a temporarily unparented object is not an acceptable workaround for transform problems.
- Round-trip the exported FBX and inspect it in the target Unity project. Validate hierarchy, representative local transforms at every nesting depth, and world-space appearance instead of accepting export success alone.

## Generated Code Requirements

- Clear the default scene at the start.
- Parse `--output-blend` after Blender's `--` argument separator; fall back to `BLENDERCODEX_OUTPUT_BLEND`; otherwise save beside the kept `.py` file with a `.blend` suffix.
- Stamp generated files with scene custom properties such as `blendercodex_source_script` and `blendercodex_generated_at_utc` when practical.
- Put all generated objects in named collections and assign each object to exactly the relevant collection.
- Create materials once, reuse them, and name them in Chinese.
- For custom mesh objects, create real vertices/faces rather than overlay-only curves when the form is structural.
- Run UV unwrap logic for mesh objects before saving.
- Save the file with `bpy.ops.wm.save_as_mainfile(filepath=...)`.

## Humanoid Rigging

- When the user asks to recognize a humanoid mesh, extract or import a standard skeleton, fit anatomical joints, create an armature, bind weights, skin a character, or prepare IK controls, use the `humanoid-rigging` skill with this skill.
- Prefer the gated `blendercodex_humanoid_analyze`, `blendercodex_humanoid_fit_standard`, `blendercodex_humanoid_validate`, and `blendercodex_humanoid_bind_preview` tools for this workflow.
- Keep target inspection read-only until `humanoid-rigging` has created semantic joint markers and the user has explicitly confirmed them. Require a separate approval before parenting meshes or writing weights.
- Use the authoritative copied Armature asset from `humanoid-rigging/assets/female-humanoid-v1.blend`; use its JSON only as metadata, and do not infer or restore excluded hair bones.

## Learning From User Edits

- When the user says to learn, remember, analyze their modifications, or make the plugin smarter, use the `model-learning` skill with this skill. Inspect the live or saved scene, preserve user edits, explain the observed correction, decide whether it is durable, then update the closest owning `SKILL.md` rule or focused reference file.
- Do not promote every one-off model change into a global default. Promote only corrections that are verified by the user, repeated, or clearly repair a class of modeling failures.
- Do not rely on adjacent `.memory.md` files for future default behavior. Durable lessons must live in the loaded skill body or a referenced rule document so the next BlenderCodex task receives the rule directly.
- Record learnings as concise evidence-based notes: what was wrong, what the user changed, why that change improves the model, what future generation or edit should do, and what validation proves the new rule was applied.

## Resources

- `scripts/blender_locator.py`: find, select, and cache the Blender executable.
- `scripts/capture_blend_state.py`: snapshot existing `.blend` files and compare them with a regenerated baseline in a temporary directory by default.
- `scripts/run_blender_model.py`: execute generated Blender code in background mode, either from a kept `.py` script or from `--code-file -` through a temporary internal script, and pass the output `.blend` path.
- Plugin-level `scripts/blendercodex_bridge.py`: temporary in-process Blender RPC bridge run by Blender with `--python`; it is not an installed add-on.
- Plugin-level `scripts/blendercodex_mcp_server.js`: Codex-side MCP adapter for starting and using the temporary bridge.
- `references/modeling-standards.md`: load when deciding what to model or ignore from a reference.
- `references/script-contract.md`: load before writing generated Blender bpy code.
- `references/hard-surface-topology-and-openings.md`: mandatory rules for window approval gates and every hard-surface mesh operation.
- `references/roof-origin-mirroring.md`: mandatory workflow when creating or converting symmetric two-slope tiled roofs to a single editable slope plus building-origin Mirror system.
- `references/tiled-roof-system.md`: mandatory default construction for 瓦片屋顶 systems, including the verified per-slope Boolean workflow for L-shaped roof intersections.
- `references/fbx-unity-hierarchy.md`: mandatory transform-normalization and round-trip checks for parent/origin edits in FBX/Unity export hierarchies.
