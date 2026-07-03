---
name: viewport-match
description: Capture a live Blender window without forcing it to the foreground, compare that viewport screenshot against a user-provided reference image, then use the BlenderCodex RPC bridge to iteratively adjust viewport angle, framing, and when requested minimal model geometry so the Blender window view resembles the reference. Use when the user asks to match a Blender view/camera/model to an image, compare Blender viewport differences, auto-align a model to a reference, or run screenshot-based visual correction through BlenderCodex.
---

# Viewport Match

## Overview

Use this skill for screenshot-in-the-loop Blender alignment. It requires a visible Blender process launched through the temporary BlenderCodex RPC bridge; the window may stay behind other windows, but it should not be minimized.

Read `references/algorithm.md` before doing the actual optimization loop.

## Workflow

1. Confirm a bridged Blender session exists.
   - Prefer `blendercodex_bridge_ping` and `blendercodex_scene_summary`.
   - If no bridge exists, start one with `blendercodex_start_bridge` and `blendFile`. Do not pass `keepAlive` for a visible UI launch.
2. Capture the Blender window without foreground activation.
   - Run `scripts/capture_blender_window.py --session-file <bridge_session.json> --output <png>`.
   - Use `--pid`, `--title-contains`, or `--hwnd` only when the session file is unavailable or ambiguous.
   - If Blender is minimized, restore it or use `--show-no-activate`; minimized windows often return tiny offscreen placeholder captures.
   - Do not use mouse or keyboard focus changes to capture the window.
3. Compare the capture with the user image.
   - Run `scripts/analyze_viewport_match.py --reference <user_image> --capture <png> --output-json <report.json> --debug-dir <dir>`.
   - If the captured screenshot includes too much UI, rerun with `--capture-crop x,y,w,h` after inspecting the debug images.
4. Adjust the live viewport through RPC first.
   - Use `blendercodex_run_python` to set 3D view yaw/pitch/roll, `view_location`, `view_distance`, lens/zoom, or clipping.
   - Run a coarse-to-fine search: capture, score, change one or two variables, capture again, keep improvements.
   - Prefer view changes over geometry changes while the remaining error is explainable by camera/view framing.
5. Modify model geometry only when view optimization stalls and the user asked for model correction.
   - Attribute residual differences to named objects or collections: body proportions, roof tower placement, window row spacing, canopy depth, rail height, or side-wall depth.
   - Make the smallest targeted RPC edit; avoid broad regeneration.
   - Save with `blendercodex_save` only after the requested live edits are complete.
6. Report the result.
   - Include the best score, screenshot path, reference path, changed view variables, and any model objects changed.
   - Mention capture limitations if PrintWindow returned a black/empty image or if the Blender window was minimized.

## Resource Guide

- `scripts/capture_blender_window.py`: Win32/Pillow screenshot capture by session, PID, title, or HWND. It intentionally avoids `SetForegroundWindow`.
- `scripts/analyze_viewport_match.py`: Pillow/NumPy visual comparison report with masks, bounding boxes, edge histograms, and adjustment hints.
- `references/algorithm.md`: Scoring formula, optimization loop, and RPC snippets for viewport/model edits.
