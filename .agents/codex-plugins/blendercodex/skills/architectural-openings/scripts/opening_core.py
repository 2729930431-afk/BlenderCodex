"""Deterministic planning and mesh generation for rectilinear openings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


try:
    from geometry_core import MeshSpec, mesh_health
except ImportError:  # package-style import for tests
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path
    import sys

    _path = Path(__file__).parents[2] / "model-validation" / "scripts" / "geometry_core.py"
    _spec = spec_from_file_location("geometry_core", _path)
    _module = module_from_spec(_spec)
    assert _spec and _spec.loader
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
    MeshSpec, mesh_health = _module.MeshSpec, _module.mesh_health


@dataclass(frozen=True)
class OpeningDefaults:
    width: float
    height: float
    sill: float


ROLE_DEFAULTS = {
    "door": OpeningDefaults(1.0, 2.1, 0.0),
    "window": OpeningDefaults(1.2, 1.5, 0.9),
}


@dataclass(frozen=True)
class EnvelopeComponent:
    component_id: str
    bounds: tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class OpeningCut:
    opening_id: str
    component_id: str
    axis: str
    side: int
    center_u: float
    bottom: float
    width: float
    height: float


def resolve_opening_defaults(role: str, explicit: Mapping[str, float] | None = None) -> OpeningDefaults:
    normalized = str(role).strip().lower()
    if normalized not in ROLE_DEFAULTS:
        raise ValueError(f"Unsupported opening role: {role}")
    base = ROLE_DEFAULTS[normalized]
    explicit = explicit or {}
    result = OpeningDefaults(
        float(explicit.get("width", base.width)),
        float(explicit.get("height", base.height)),
        float(explicit.get("sill", base.sill)),
    )
    if result.width <= 0 or result.height <= 0 or result.sill < 0:
        raise ValueError("Opening width/height must be positive and sill must be non-negative")
    return result


def _cluster(values: Iterable[float], epsilon: float) -> list[float]:
    result = []
    for value in sorted(float(item) for item in values):
        if not result or abs(value - result[-1]) > epsilon:
            result.append(value)
        else:
            result[-1] = (result[-1] + value) * 0.5
    return result


def _contains_wall(component: EnvelopeComponent, point, thickness: float, epsilon: float) -> bool:
    x0, x1, y0, y1, z0, z1 = component.bounds
    x, y, z = point
    if not (x0 + epsilon < x < x1 - epsilon and y0 + epsilon < y < y1 - epsilon and z0 + epsilon < z < z1 - epsilon):
        return False
    in_cavity = x0 + thickness + epsilon < x < x1 - thickness - epsilon and y0 + thickness + epsilon < y < y1 - thickness - epsilon
    return not in_cavity


def _inside_opening(cut: OpeningCut, component: EnvelopeComponent, point, thickness: float, epsilon: float) -> bool:
    x0, x1, y0, y1, _, _ = component.bounds
    x, y, z = point
    if not (cut.bottom + epsilon < z < cut.bottom + cut.height - epsilon):
        return False
    u = y if cut.axis == "x" else x
    if not (cut.center_u - cut.width * 0.5 + epsilon < u < cut.center_u + cut.width * 0.5 - epsilon):
        return False
    if cut.axis == "x":
        outer = x0 if cut.side < 0 else x1
        inner = x0 + thickness if cut.side < 0 else x1 - thickness
        return min(outer, inner) - epsilon < x < max(outer, inner) + epsilon
    outer = y0 if cut.side < 0 else y1
    inner = y0 + thickness if cut.side < 0 else y1 - thickness
    return min(outer, inner) - epsilon < y < max(outer, inner) + epsilon


def build_rectilinear_shell(
    components: Iterable[EnvelopeComponent],
    openings: Iterable[OpeningCut],
    thickness: float = 0.2,
    epsilon: float = 1e-7,
) -> MeshSpec:
    """Build a closed cell-complex shell for an axis-aligned box union."""

    components = tuple(components)
    openings = tuple(openings)
    if not components:
        raise ValueError("At least one envelope component is required")
    if thickness <= epsilon:
        raise ValueError("Wall thickness must exceed epsilon")
    by_id = {item.component_id: item for item in components}
    if len(by_id) != len(components):
        raise ValueError("Envelope component ids must be unique")

    seen_opening_ids = set()
    facade_intervals = {}

    xs, ys, zs = set(), set(), set()
    for component in components:
        x0, x1, y0, y1, z0, z1 = component.bounds
        if min(x1 - x0, y1 - y0) <= thickness * 2 + epsilon or z1 - z0 <= epsilon:
            raise ValueError(f"Component is too small for wall thickness: {component.component_id}")
        xs.update((x0, x0 + thickness, x1 - thickness, x1))
        ys.update((y0, y0 + thickness, y1 - thickness, y1))
        zs.update((z0, z1))
    for cut in openings:
        if cut.opening_id in seen_opening_ids:
            raise ValueError(f"Opening ids must be unique: {cut.opening_id}")
        seen_opening_ids.add(cut.opening_id)
        if cut.component_id not in by_id:
            raise ValueError(f"Opening references unknown component: {cut.component_id}")
        if cut.axis not in ("x", "y") or cut.side not in (-1, 1):
            raise ValueError(f"Opening has invalid facade axis/side: {cut.opening_id}")
        if cut.width <= epsilon or cut.height <= epsilon:
            raise ValueError(f"Opening has invalid size: {cut.opening_id}")
        component = by_id[cut.component_id]
        x0, x1, y0, y1, z0, z1 = component.bounds
        bottom, top = cut.bottom, cut.bottom + cut.height
        u0, u1 = cut.center_u - cut.width * 0.5, cut.center_u + cut.width * 0.5
        facade_min, facade_max = (y0, y1) if cut.axis == "x" else (x0, x1)
        if bottom < z0 - epsilon or top > z1 + epsilon or u0 < facade_min + thickness - epsilon or u1 > facade_max - thickness + epsilon:
            raise ValueError(f"Opening exceeds its facade or wall height: {cut.opening_id}")
        facade_key = (cut.component_id, cut.axis, cut.side)
        for other_u0, other_u1, other_z0, other_z1, other_id in facade_intervals.get(facade_key, []):
            if min(u1, other_u1) - max(u0, other_u0) > epsilon and min(top, other_z1) - max(bottom, other_z0) > epsilon:
                raise ValueError(f"Openings overlap on one facade: {other_id} and {cut.opening_id}")
        facade_intervals.setdefault(facade_key, []).append((u0, u1, bottom, top, cut.opening_id))
        zs.update((cut.bottom, cut.bottom + cut.height))
        if cut.axis == "x":
            xs.update((x0, x0 + thickness) if cut.side < 0 else (x1 - thickness, x1))
            ys.update((cut.center_u - cut.width * 0.5, cut.center_u + cut.width * 0.5))
        else:
            ys.update((y0, y0 + thickness) if cut.side < 0 else (y1 - thickness, y1))
            xs.update((cut.center_u - cut.width * 0.5, cut.center_u + cut.width * 0.5))

    xs, ys, zs = _cluster(xs, epsilon), _cluster(ys, epsilon), _cluster(zs, epsilon)
    solid = set()
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            for k in range(len(zs) - 1):
                if min(xs[i + 1] - xs[i], ys[j + 1] - ys[j], zs[k + 1] - zs[k]) <= epsilon:
                    continue
                point = ((xs[i] + xs[i + 1]) * 0.5, (ys[j] + ys[j + 1]) * 0.5, (zs[k] + zs[k + 1]) * 0.5)
                owners = [component for component in components if _contains_wall(component, point, thickness, epsilon)]
                if owners and not any(_inside_opening(cut, by_id[cut.component_id], point, thickness, epsilon) for cut in openings):
                    solid.add((i, j, k))

    vertex_ids, vertices, faces = {}, [], []

    def vertex(i, j, k):
        key = (i, j, k)
        if key not in vertex_ids:
            vertex_ids[key] = len(vertices)
            vertices.append((xs[i], ys[j], zs[k]))
        return vertex_ids[key]

    for i, j, k in sorted(solid):
        if (i - 1, j, k) not in solid:
            faces.append((vertex(i, j, k), vertex(i, j, k + 1), vertex(i, j + 1, k + 1), vertex(i, j + 1, k)))
        if (i + 1, j, k) not in solid:
            faces.append((vertex(i + 1, j, k), vertex(i + 1, j + 1, k), vertex(i + 1, j + 1, k + 1), vertex(i + 1, j, k + 1)))
        if (i, j - 1, k) not in solid:
            faces.append((vertex(i, j, k), vertex(i + 1, j, k), vertex(i + 1, j, k + 1), vertex(i, j, k + 1)))
        if (i, j + 1, k) not in solid:
            faces.append((vertex(i, j + 1, k), vertex(i, j + 1, k + 1), vertex(i + 1, j + 1, k + 1), vertex(i + 1, j + 1, k)))
        if (i, j, k - 1) not in solid:
            faces.append((vertex(i, j, k), vertex(i, j + 1, k), vertex(i + 1, j + 1, k), vertex(i + 1, j, k)))
        if (i, j, k + 1) not in solid:
            faces.append((vertex(i, j, k + 1), vertex(i + 1, j, k + 1), vertex(i + 1, j + 1, k + 1), vertex(i, j + 1, k + 1)))

    spec = MeshSpec(tuple(vertices), tuple(faces))
    health = mesh_health(spec, epsilon)
    if not health.manifold or abs(health.signed_volume) <= epsilon:
        raise ValueError(f"Generated shell failed topology validation: {health}")
    return spec
