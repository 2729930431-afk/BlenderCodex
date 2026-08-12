"""Pure-Python geometry helpers shared by BlenderCodex runtimes.

This module deliberately has no bpy dependency so its deterministic planning,
canonical signatures, topology checks, and UV math can be unit tested quickly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence


UV_LAYER_NAME = "UV_4m_world_standard"


@dataclass(frozen=True)
class MeshSpec:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class MeshHealth:
    vertices: int
    edges: int
    faces: int
    wire_edges: int
    boundary_edges: int
    nonmanifold_edges: int
    degenerate_edges: int
    degenerate_faces: int
    duplicate_faces: int
    signed_volume: float

    @property
    def manifold(self) -> bool:
        return not any(
            (
                self.wire_edges,
                self.boundary_edges,
                self.nonmanifold_edges,
                self.degenerate_edges,
                self.degenerate_faces,
                self.duplicate_faces,
            )
        )


def _round_float(value: float, digits: int) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Canonical signatures reject NaN and infinity")
    rounded = round(value, digits)
    return 0.0 if rounded == 0 else rounded


def canonicalize(value: Any, float_digits: int = 7) -> Any:
    """Return a JSON-safe, stable representation for signatures."""

    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {
            str(key): canonicalize(item, float_digits)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize(item, float_digits) for item in value]
    if isinstance(value, set):
        rows = [canonicalize(item, float_digits) for item in value]
        return sorted(rows, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return _round_float(value, float_digits)
    if isinstance(value, str) or value is None:
        return value
    return str(value)


def canonical_json(value: Any, float_digits: int = 7) -> str:
    return json.dumps(
        canonicalize(value, float_digits),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def fingerprint(value: Any, float_digits: int = 7) -> str:
    return hashlib.sha256(canonical_json(value, float_digits).encode("utf-8")).hexdigest()


def _sub(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length(vector: Sequence[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def mesh_health(spec: MeshSpec, epsilon: float = 1e-9) -> MeshHealth:
    edge_faces: dict[tuple[int, int], int] = {}
    duplicate_faces = 0
    face_keys: set[tuple[int, ...]] = set()
    degenerate_faces = 0
    signed_volume = 0.0
    vertex_count = len(spec.vertices)

    for face in spec.faces:
        if any(not isinstance(vertex_id, int) or isinstance(vertex_id, bool) or vertex_id < 0 or vertex_id >= vertex_count for vertex_id in face):
            raise ValueError(f"Face contains an invalid vertex index: {face}")
        key = tuple(sorted(face))
        if key in face_keys:
            duplicate_faces += 1
        face_keys.add(key)
        if len(face) < 3:
            degenerate_faces += 1
            continue
        origin = spec.vertices[face[0]]
        area2 = 0.0
        for index in range(1, len(face) - 1):
            a = spec.vertices[face[index]]
            b = spec.vertices[face[index + 1]]
            cross = _cross(_sub(a, origin), _sub(b, origin))
            area2 += _length(cross)
            signed_volume += _dot(origin, cross) / 6.0
        if area2 <= epsilon:
            degenerate_faces += 1
        for index, start in enumerate(face):
            end = face[(index + 1) % len(face)]
            edge = tuple(sorted((start, end)))
            edge_faces[edge] = edge_faces.get(edge, 0) + 1

    degenerate_edges = sum(
        _length(_sub(spec.vertices[a], spec.vertices[b])) <= epsilon
        for a, b in edge_faces
    )
    wire_edges = sum(count == 0 for count in edge_faces.values())
    boundary_edges = sum(count == 1 for count in edge_faces.values())
    nonmanifold_edges = sum(count != 2 for count in edge_faces.values())
    return MeshHealth(
        vertices=len(spec.vertices),
        edges=len(edge_faces),
        faces=len(spec.faces),
        wire_edges=wire_edges,
        boundary_edges=boundary_edges,
        nonmanifold_edges=nonmanifold_edges,
        degenerate_edges=degenerate_edges,
        degenerate_faces=degenerate_faces,
        duplicate_faces=duplicate_faces,
        signed_volume=signed_volume,
    )


def transform_point(matrix: Sequence[Sequence[float]], point: Sequence[float]) -> tuple[float, float, float]:
    x, y, z = point
    w = matrix[3][0] * x + matrix[3][1] * y + matrix[3][2] * z + matrix[3][3]
    if abs(w) <= 1e-12:
        raise ValueError("Point transform produced a zero homogeneous coordinate")
    return (
        (matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3]) / w,
        (matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3]) / w,
        (matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3]) / w,
    )


def planar_uv_4m(
    vertices: Sequence[Sequence[float]],
    faces: Iterable[Sequence[int]],
    world_matrix: Sequence[Sequence[float]],
    epsilon: float = 1e-9,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Project each planar face in world space at one UV unit per four metres."""

    world = [transform_point(world_matrix, point) for point in vertices]
    result = []
    for face in faces:
        ids = tuple(face)
        if len(ids) < 3:
            raise ValueError("UV projection requires faces with at least three vertices")
        origin = world[ids[0]]
        normal_raw = None
        for index in range(1, len(ids) - 1):
            candidate = _cross(_sub(world[ids[index]], origin), _sub(world[ids[index + 1]], origin))
            if _length(candidate) > epsilon:
                normal_raw = candidate
                break
        if normal_raw is None:
            raise ValueError("UV projection encountered a zero-area face")
        normal_length = _length(normal_raw)
        normal = tuple(component / normal_length for component in normal_raw)
        # Anchor the face basis to the first non-degenerate boundary edge. This
        # makes every polygon boundary edge align with U or V for the
        # rectilinear/segmented surfaces produced by the executors.
        u_raw = None
        for a, b in zip(ids, ids[1:] + ids[:1]):
            candidate = _sub(world[b], world[a])
            if _length(candidate) > epsilon:
                u_raw = candidate
                break
        if u_raw is None:
            raise ValueError("UV projection encountered a degenerate face")
        length = _length(u_raw)
        u_axis = tuple(component / length for component in u_raw)
        v_raw = _cross(normal, u_axis)
        v_length = _length(v_raw)
        v_axis = tuple(component / v_length for component in v_raw)
        loops = []
        for vertex_id in ids:
            delta = _sub(world[vertex_id], origin)
            loops.append((_dot(delta, u_axis) / 4.0, _dot(delta, v_axis) / 4.0))
        result.append(tuple(loops))
    return tuple(result)
