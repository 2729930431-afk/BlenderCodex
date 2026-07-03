#!/usr/bin/env python3
"""Acceptance checks for BlenderCodex snapshot comparison helpers."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import capture_blend_state as capture  # noqa: E402


def main() -> int:
    baseline = {
        "objects": [
            {
                "name": "Wall",
                "type": "MESH",
                "location": [0, 0, 0],
                "rotation_degrees": [0, 0, 0],
                "scale": [1, 1, 1],
                "dimensions": [2, 1, 3],
                "collections": ["Shell"],
                "materials": ["Plaster"],
                "modifiers": [],
                "mesh": {"signature": "aaa", "vertex_count": 8, "edge_count": 12, "polygon_count": 6, "uv_layers": ["UVMap"]},
            },
            {
                "name": "OldTrim",
                "type": "MESH",
                "location": [1, 0, 1],
                "rotation_degrees": [0, 0, 0],
                "scale": [1, 1, 1],
                "dimensions": [1, 1, 1],
                "collections": ["Trim"],
                "materials": ["Stone"],
                "modifiers": [],
                "mesh": {"signature": "bbb", "vertex_count": 8, "edge_count": 12, "polygon_count": 6, "uv_layers": ["UVMap"]},
            },
        ],
        "materials": [{"name": "Plaster", "diffuse_color": [1, 1, 1, 1], "use_nodes": True}],
        "collections": [{"name": "Shell", "children": [], "objects": ["Wall"]}],
    }
    current = {
        "objects": [
            {
                "name": "Wall",
                "type": "MESH",
                "location": [0.25, 0, 0],
                "rotation_degrees": [0, 0, 0],
                "scale": [1, 1, 1],
                "dimensions": [2, 1, 3],
                "collections": ["Shell"],
                "materials": ["Plaster"],
                "modifiers": [],
                "mesh": {"signature": "aaa", "vertex_count": 8, "edge_count": 12, "polygon_count": 6, "uv_layers": ["UVMap"]},
            },
            {
                "name": "UserBalcony",
                "type": "MESH",
                "location": [0, -1, 2],
                "rotation_degrees": [0, 0, 0],
                "scale": [1, 1, 1],
                "dimensions": [1, 0.5, 0.2],
                "collections": ["Balcony"],
                "materials": ["Iron"],
                "modifiers": [],
                "mesh": {"signature": "ccc", "vertex_count": 8, "edge_count": 12, "polygon_count": 6, "uv_layers": ["UVMap"]},
            },
        ],
        "materials": [{"name": "Plaster", "diffuse_color": [0.9, 0.9, 0.9, 1], "use_nodes": True}],
        "collections": [{"name": "Shell", "children": [], "objects": ["Wall"]}],
    }

    diff = capture.compare_snapshots(current, baseline)
    assert diff["objects"]["added"] == ["UserBalcony"]
    assert diff["objects"]["removed"] == ["OldTrim"]
    assert diff["objects"]["changed"][0]["name"] == "Wall"
    assert diff["objects"]["changed"][0]["changes"][0]["field"] == "location"
    assert diff["summary"]["materials_changed"] == 1
    assert capture.default_state_dir(Path("house.blend")) == Path("house.blendercodex")
    print("test_capture_blend_state passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
