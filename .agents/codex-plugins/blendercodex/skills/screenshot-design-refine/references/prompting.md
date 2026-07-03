# GPT Image 2 Screenshot Design Prompting

Use this reference when composing a prompt for the built-in image generation/editing path. The bundled API script is fallback-only.

## Core Prompt Structure

Include these parts in order:

1. Role: production concept artist for editable game assets.
2. Input constraint: the attached Blender screenshot is the current model state, not a random inspiration image.
3. Preserve list: silhouette, camera/view, scale, major object count, and recognizable modules unless the user asks to change them.
4. Change list: user-specific refinements, material direction, detail density, damage/weathering, faction/era/style cues, or readability requirements.
5. Output requirement: one clean reference image suitable for modeling; avoid UI, watermarks, unreadable text, and unrelated props.
6. Modeling usefulness: emphasize clear forms, readable construction, modular parts, and visible design decisions.
7. Building structure constraint, when applicable: keep doors, windows, balconies, and facade rows aligned to existing or inferred floor bands unless the user explicitly asks to redesign the structure.

## Modes

- `refine`: Enhance the current screenshot into a polished design reference while keeping the model's layout.
- `material`: Focus on material, color, grime, wear, decals, and surface finish while preserving geometry.
- `variant`: Produce a coherent alternate design that keeps the asset role and rough silhouette.
- `callout-sheet`: Add concise visual callouts for changes; use only when labels are useful.
- `orthographic`: Generate a cleaner blueprint-like front/side/three-quarter concept from the screenshot.
- `texture`: Focus on texture/material treatment for later material replacement.

## Default Prompt Skeleton

```text
Use the attached Blender viewport screenshot as the exact current state of a game asset.
Refine it into a production-ready visual design reference.

User request:
{user_request}

Scene notes:
{scene_summary}

Preserve:
- current asset identity, broad silhouette, camera/view composition, and major proportions
- existing large modules unless explicitly changed
- existing or inferred floor bands and opening rows for buildings
- model readability for later Blender editing

Improve:
- design specificity and medium-level detail
- material/color decisions
- readable construction of repeated or modular parts
- game-asset clarity from the current viewport

Avoid:
- changing the asset into a different object category
- adding unrelated characters, vehicles, logos, or UI
- tiny noisy details that cannot be modeled
- windows, doors, or balconies floating between structural floor rows
- heavy text unless callout mode is requested
```

## After Generation

Inspect the generated image before editing Blender. Translate changes into explicit model tasks:

- silhouette or massing changes,
- material assignments,
- modular detail additions,
- array count/spacing changes,
- surface detail to encode as geometry vs material,
- reference-only paint/grime that should remain material work.

## API/CLI Fallback Note

Only use `scripts/gpt_image2_refine.py` when the user explicitly asks for the API/CLI/model-control path. The default route is direct built-in image generation and does not require `OPENAI_API_KEY`.
