#!/usr/bin/env python3
"""Acceptance checks for BlenderCodex's Blender locator helpers."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import blender_locator as locator  # noqa: E402


def main() -> int:
    assert locator.parse_version_tuple("Blender 4.3.2") == (4, 3, 2)
    assert locator.parse_version_tuple("Blender 3.6") == (3, 6, 0)
    assert locator.requested_version_tuple("4.2") == (4, 2)
    assert locator.version_matches("4.2.1", "4.2")
    assert not locator.version_matches("4.3.0", "4.2")
    print("test_blender_locator passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
