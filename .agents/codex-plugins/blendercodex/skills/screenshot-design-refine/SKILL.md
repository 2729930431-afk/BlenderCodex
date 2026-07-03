---
name: screenshot-design-refine
description: Capture or reuse Blender viewport screenshots, combine screenshot data with the user's design requirements, directly invoke Codex's built-in image generation/editing capability by default to create refined visual design references without requiring an API key, and translate the refined output into BlenderCodex modeling changes. Use when the user asks to refine a Blender model design from a screenshot, generate concept variants from the current Blender view, directly call image generation/GPT-image2-style generation with viewport data, produce design reference images for a model, or turn a Blender screenshot into a more detailed game-asset concept. Use the bundled GPT Image 2 API script only when the user explicitly asks for API/CLI fallback.
---

# Screenshot Design Refine

## Overview

Use this skill to turn the current Blender viewport into a refined design reference, then use that design to guide BlenderCodex edits only after the user confirms the generated image.

Default to Codex's built-in image generation/editing path. It does not require `OPENAI_API_KEY`. Treat `scripts/gpt_image2_refine.py` as an explicit API/CLI fallback only.

Hard rule for Blender edits: generate and show the design reference first, then stop and wait for explicit user confirmation before translating it into Blender geometry or materials. Do not apply model edits in the same pass unless the user has already approved that specific generated reference image.

Read `references/prompting.md` before building the image prompt.

## Workflow

1. Confirm the design target.
   - Extract the user requirement: style, asset type, what to preserve, what to change, output count, and whether the result is concept art, material pass, callout sheet, or a model-edit guide.
   - If the user wants to keep current proportions or camera view, state that constraint in the prompt.
2. Capture or select screenshot data.
   - If a live Blender bridge is available, use sibling skill script `../viewport-match/scripts/capture_blender_window.py` to capture the visible Blender window without foreground activation.
   - Do not use captures from minimized Blender windows; they may be tiny offscreen placeholders. Use `--show-no-activate` if a window must be shown without foreground activation.
   - If the user already provided a screenshot, use it directly.
   - Optionally call `blendercodex_scene_summary` and include a short scene summary in the prompt.
3. Generate the design reference with the built-in image generation path.
   - If the screenshot is a local file, inspect it with `view_image` first so it is visible in conversation context.
   - Use the built-in image generation/editing capability directly; do not ask for `OPENAI_API_KEY`.
   - Use `refine` by default; use `material`, `variant`, `callout-sheet`, `orthographic`, or `texture` when the user asks.
   - Keep the screenshot as the current model state, not loose inspiration. Preserve the model's identity unless the user asks for a redesign.
   - Show the generated image to the user and ask for confirmation or revisions before any BlenderCodex editing.
4. Use API/CLI fallback only when explicitly requested.
   - Use `scripts/gpt_image2_refine.py --image <screenshot> --user-request "<request>" --output <png>` only if the user asks for API, CLI, exact `gpt-image-2` model controls, dry-run request JSON, or a reproducible command.
   - The fallback script requires `OPENAI_API_KEY` for live API calls. Do not print secrets.
   - For fallback `gpt-image-2`, do not set `background=transparent`; use `auto` or `opaque`.
   - For fallback `gpt-image-2`, omit `input_fidelity`; the model handles input images at high fidelity automatically.
5. After user approval, use the result.
   - Save the refined image(s) to the requested output location or a working directory.
   - If the user approved applying the design, compare the refined image with the current model and implement targeted BlenderCodex edits through RPC or background generation.
   - Prefer preserving model identity: current massing, silhouette, camera composition, and major proportions unless the prompt says otherwise.
   - For buildings, reconcile generated facade details with the model's existing or inferred floor markers before editing geometry. Floor bands, slab positions, and exterior opening rows are stronger evidence than visually plausible generated window positions.
6. Report.
   - Return output image paths, prompt summary, model name, quality/size settings, and any Blender changes made.
   - If the API call was skipped, return the dry-run prompt and exact command to run.

## Resource Guide

- `scripts/gpt_image2_refine.py`: optional API/CLI fallback wrapper for GPT Image 2 image edits with screenshot input, prompt construction, dry-run mode, and base64 output saving. Do not use it for the default built-in path.
- `references/prompting.md`: Prompt template, mode-specific instructions, and screenshot-to-design checklist.
