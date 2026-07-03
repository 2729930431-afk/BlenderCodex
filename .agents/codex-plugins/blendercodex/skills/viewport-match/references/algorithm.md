# Viewport Matching Algorithm

Use this reference after `SKILL.md` triggers and before starting a screenshot-based alignment loop.

## Inputs

- `reference_image`: user image to match.
- `bridge_session.json`: session file from `blendercodex_start_bridge`; use its `pid` for window capture.
- `blendercodex` RPC access to run Blender Python in the visible bridged process.

The Blender window must be visible but does not need focus. Minimized windows often produce stale or black `PrintWindow` captures.

## Scoring

Run `scripts/analyze_viewport_match.py` to compute:

- Object mask from distance to border background color.
- Largest connected component bbox, center, area fraction, and aspect.
- Edge orientation histogram from grayscale gradients.
- Normalized grayscale crop difference.

The combined score is lower-is-better:

```text
score =
  0.28 * normalized_center_delta +
  0.22 * abs(log(area_ratio)) +
  0.18 * abs(log(aspect_ratio)) +
  0.22 * (1 - edge_histogram_cosine) +
  0.10 * normalized_crop_mse
```

Use the report's `suggestions` as hints, not as hard truth. Backgrounds, UI panels, transparency, and model material brightness can confuse masks.

## Optimization Loop

1. Capture current window.
2. Analyze against the reference.
3. Apply view-only candidates:
   - pan X/Y to match mask center,
   - zoom/view distance to match mask area,
   - yaw to match left/right side visibility and diagonal edge balance,
   - pitch to match roof/floor visibility,
   - roll only when the reference is visibly tilted.
4. Re-capture and keep only lower-score candidates.
5. Repeat with smaller step sizes until score improvement is small.
6. If the best view still has persistent structural residuals, apply minimal model edits.

Suggested coarse search:

```text
yaw:   -50, -35, -20, -10, 0, 10, 20, 35, 50 degrees
pitch:  50, 58, 66, 74 degrees
zoom:   0.72, 0.85, 1.0, 1.18, 1.38 relative factor
pan:    report center delta converted to view plane offsets
```

## RPC View Snippet

Use this with `blendercodex_run_python`. Adjust values per candidate.

```python
import bpy
import math
import mathutils

def set_view(yaw_deg=0, pitch_deg=63, roll_deg=0, distance=12, location=(0, 0, 4)):
    # Blender view_rotation describes the view orientation; this is good enough
    # for iterative screenshot search because each candidate is scored visually.
    rot = mathutils.Euler(
        (math.radians(pitch_deg), 0.0, math.radians(yaw_deg)),
        "XYZ",
    ).to_quaternion()
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                rv3d = space.region_3d
                rv3d.view_perspective = "PERSP"
                rv3d.view_rotation = rot
                rv3d.view_distance = distance
                rv3d.view_location = mathutils.Vector(location)
                space.overlay.show_floor = False
                space.overlay.show_axis_x = False
                space.overlay.show_axis_y = False
                space.shading.type = "MATERIAL"

set_view(yaw_deg=-25, pitch_deg=64, distance=13, location=(0, 0, 4.2))
RESULT = {"ok": True}
```

## Geometry Edit Rules

Only edit geometry after view-only matching stalls.

- Preserve user edits. Work through named objects/collections and avoid full regeneration.
- Change transforms/modifiers first: scale body depth, move tower, adjust array count/offset, change canopy depth, or move window rows.
- Prefer reversible edits through modifiers or object transforms. Apply destructive mesh edits only when necessary.
- Capture and rescore after each edit batch.
- Save only after the requested correction is done.

Residual-to-edit mapping:

- Reference object is consistently wider after all yaw/zoom candidates: scale main body X or reduce side-depth visibility.
- Roof tower remains off-center: move tower collection/object in X/Y.
- Window rhythm mismatch: adjust Array modifier `constant_offset_displace` or `count`.
- Canopy projects too far/too little: edit canopy Y depth or slope vertices.
- Side face too deep/too shallow at matching yaw: scale body depth Y.
