"""Pure-Python planning and module mesh generation for editable tiled roofs."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence


try:
    from geometry_core import MeshSpec
except ImportError:
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path
    import sys

    _path = Path(__file__).parents[2] / "model-validation" / "scripts" / "geometry_core.py"
    _spec = spec_from_file_location("geometry_core", _path)
    _module = module_from_spec(_spec)
    assert _spec and _spec.loader
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
    MeshSpec = _module.MeshSpec


@dataclass(frozen=True)
class TileProfile:
    pan_length: float = 0.50
    pan_width: float = 0.28
    pan_thickness: float = 0.032
    pan_curvature: float = 0.035
    cover_length: float = 0.51
    cover_width: float = 0.15
    cover_thickness: float = 0.030
    cover_curvature: float = 0.075
    ridge_length: float = 0.52
    ridge_width: float = 0.36
    ridge_thickness: float = 0.035
    ridge_curvature: float = 0.14
    row_pitch: float = 0.34
    column_pitch: float = 0.31
    ridge_pitch: float = 0.38


TRADITIONAL_GRAY_V1 = TileProfile()


def repeat_count(span: float, module_size: float, target_pitch: float) -> tuple[int, float]:
    if span <= 0 or module_size <= 0 or target_pitch <= 0:
        raise ValueError("Span, module size, and pitch must be positive")
    usable = max(0.0, span - module_size)
    count = max(1, math.ceil(usable / target_pitch) + 1)
    return count, usable / (count - 1) if count > 1 else 0.0


def _normalize(vector: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(float(value) ** 2 for value in vector))
    if length <= 1e-9:
        raise ValueError("Tile basis vectors must be non-zero")
    return tuple(float(value) / length for value in vector)


def _combine(origin, axis, a, cross, b, normal, c):
    return tuple(origin[i] + axis[i] * a + cross[i] * b + normal[i] * c for i in range(3))


def build_tile_module(
    length: float,
    width: float,
    thickness: float,
    curvature: float,
    convex: bool,
    segments: int,
    origin=(0.0, 0.0, 0.0),
    axis=(1.0, 0.0, 0.0),
    cross=(0.0, 1.0, 0.0),
    normal=(0.0, 0.0, 1.0),
) -> MeshSpec:
    """Create a closed editable pan-, cover-, or ridge-tile source mesh."""

    if min(length, width, thickness) <= 0 or segments < 2:
        raise ValueError("Tile dimensions must be positive and segments >= 2")
    axis, cross, normal = _normalize(axis), _normalize(cross), _normalize(normal)
    vertices = []
    for along in (-length * 0.5, length * 0.5):
        for bottom in (False, True):
            for index in range(segments + 1):
                q = index / segments * 2.0 - 1.0
                across = q * width * 0.5
                rise = curvature * (1.0 - q * q) if convex else curvature * q * q
                if bottom:
                    rise -= thickness
                vertices.append(_combine(origin, axis, along, cross, across, normal, rise))

    stride = segments + 1
    start_top, start_bottom = 0, stride
    end_top, end_bottom = stride * 2, stride * 3
    faces = []
    # Curved top and bottom surfaces run along the tile length.
    for index in range(segments):
        faces.append((start_top + index, start_top + index + 1, end_top + index + 1, end_top + index))
        faces.append((start_bottom + index, end_bottom + index, end_bottom + index + 1, start_bottom + index + 1))
    # End caps alternate top-forward and bottom-reverse so the polygon boundary
    # follows the actual closed cross-section instead of introducing diagonals.
    faces.append(tuple(range(start_top, start_top + stride)) + tuple(reversed(range(start_bottom, start_bottom + stride))))
    faces.append(tuple(reversed(range(end_top, end_top + stride))) + tuple(range(end_bottom, end_bottom + stride)))
    faces.append((start_top, start_bottom, end_bottom, end_top))
    faces.append((start_top + segments, end_top + segments, end_bottom + segments, start_bottom + segments))
    return MeshSpec(tuple(vertices), tuple(faces))


def plan_roof_field(slope_span: float, ridge_span: float, profile: TileProfile = TRADITIONAL_GRAY_V1) -> dict:
    pan_rows, row_step = repeat_count(slope_span, profile.pan_length, profile.row_pitch)
    pan_columns, column_step = repeat_count(ridge_span, profile.pan_width, profile.column_pitch)
    ridge_count, ridge_step = repeat_count(ridge_span, profile.ridge_length, profile.ridge_pitch)
    return {
        "pan_rows": pan_rows,
        "row_step": row_step,
        "pan_columns": pan_columns,
        "cover_columns": max(1, pan_columns - 1),
        "column_step": column_step,
        "ridge_count": ridge_count,
        "ridge_step": ridge_step,
    }
