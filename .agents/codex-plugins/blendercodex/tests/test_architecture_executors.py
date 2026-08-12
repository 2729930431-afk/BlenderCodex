import importlib.util
import json
from pathlib import Path
import sys
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_SCRIPTS = PLUGIN_ROOT / "skills" / "model-validation" / "scripts"
OPENING_SCRIPTS = PLUGIN_ROOT / "skills" / "architectural-openings" / "scripts"
ROOF_SCRIPTS = PLUGIN_ROOT / "skills" / "tiled-roof" / "scripts"
for directory in (VALIDATION_SCRIPTS, OPENING_SCRIPTS, ROOF_SCRIPTS):
    sys.path.insert(0, str(directory))

from geometry_core import MeshSpec, canonicalize, fingerprint, mesh_health
from opening_core import EnvelopeComponent, OpeningCut, build_rectilinear_shell, resolve_opening_defaults
from tiled_roof_core import TRADITIONAL_GRAY_V1, build_tile_module, plan_roof_field

PROMOTER_PATH = PLUGIN_ROOT / "skills" / "workflow-learning" / "scripts" / "promote_learning.py"
promoter_spec = importlib.util.spec_from_file_location("promote_learning", PROMOTER_PATH)
promoter = importlib.util.module_from_spec(promoter_spec)
assert promoter_spec and promoter_spec.loader
promoter_spec.loader.exec_module(promoter)


class ArchitectureExecutorsTest(unittest.TestCase):
    def test_distinct_opening_defaults(self):
        door = resolve_opening_defaults("door")
        window = resolve_opening_defaults("window")
        self.assertEqual((door.width, door.height, door.sill), (1.0, 2.1, 0.0))
        self.assertEqual((window.width, window.height, window.sill), (1.2, 1.5, 0.9))
        self.assertNotEqual((door.width, door.height), (window.width, window.height))

    def test_window_and_door_shells_are_manifold(self):
        component = EnvelopeComponent("wall", (-2, 2, -2, 2, 0, 3))
        for cut in (
            OpeningCut("door", "wall", "y", -1, 0, 0, 1.0, 2.1),
            OpeningCut("window", "wall", "y", -1, 0, 0.9, 1.2, 1.5),
        ):
            health = mesh_health(build_rectilinear_shell([component], [cut], 0.2))
            self.assertTrue(health.manifold, health)
            self.assertNotEqual(health.signed_volume, 0)
        with self.assertRaisesRegex(ValueError, "overlap"):
            build_rectilinear_shell(
                [component],
                [
                    OpeningCut("first", "wall", "y", -1, 0, 0.5, 1.2, 1.5),
                    OpeningCut("second", "wall", "y", -1, 0.2, 0.7, 1.2, 1.5),
                ],
                0.2,
            )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            build_rectilinear_shell(
                [component],
                [OpeningCut("outside", "wall", "y", -1, 1.8, 0.9, 1.2, 1.5)],
                0.2,
            )

    def test_compound_shell_clusters_coincident_planes(self):
        components = (
            EnvelopeComponent("main", (-3, 3, -3, 3, 0, 4)),
            EnvelopeComponent("ear", (-3, 0, 3, 5, 0, 3)),
        )
        cuts = (OpeningCut("window", "ear", "x", -1, 4, 0.8, 1.0, 1.2),)
        health = mesh_health(build_rectilinear_shell(components, cuts, 0.2))
        self.assertTrue(health.manifold, health)
        self.assertEqual(health.degenerate_faces, 0)

    def test_tile_sources_are_closed(self):
        profile = TRADITIONAL_GRAY_V1
        rows = (
            (profile.pan_length, profile.pan_width, profile.pan_thickness, profile.pan_curvature, False, 6),
            (profile.cover_length, profile.cover_width, profile.cover_thickness, profile.cover_curvature, True, 8),
            (profile.ridge_length, profile.ridge_width, profile.ridge_thickness, profile.ridge_curvature, True, 10),
        )
        for args in rows:
            health = mesh_health(build_tile_module(*args))
            self.assertTrue(health.manifold, health)

    def test_roof_repeat_plan_and_stable_signatures(self):
        plan = plan_roof_field(4.5, 6.0)
        self.assertGreater(plan["pan_rows"], 1)
        self.assertGreater(plan["pan_columns"], 1)
        self.assertEqual(fingerprint({"a": 0, "b": 1.0}), fingerprint({"b": 1, "a": -0.0}))
        with self.assertRaises(ValueError):
            canonicalize(float("nan"))
        with self.assertRaisesRegex(ValueError, "invalid vertex index"):
            mesh_health(MeshSpec(((0.0, 0.0, 0.0),), ((0, 1, 0),)))

    def test_learning_promotion_requires_real_executor_wiring(self):
        packet = {
            "kind": "executable",
            "observed_problem": "Repeated opening scripts were regenerated.",
            "owner_skill": "architectural-openings",
            "runtime_file": "scripts/opening_runtime.py",
            "runtime_action": "apply",
            "parameter_schema": {"markerCollection": "string"},
            "fixture": "tests/test_architecture_runtime_blender.py",
            "acceptance_checks": ["manifold", "uv"],
            "mcp_tool": "blendercodex_openings_apply",
            "tests": ["tests/test_architecture_executors.py", "tests/test_architecture_runtime_mcp.js"],
        }
        self.assertEqual(promoter.validate_packet(packet, PLUGIN_ROOT), [])
        bad = dict(packet, mcp_tool="blendercodex_missing_tool", fixture="tests/missing.py")
        errors = promoter.validate_packet(bad, PLUGIN_ROOT)
        self.assertTrue(any("fixture not found" in error for error in errors))
        self.assertTrue(any("MCP tool not found" in error for error in errors))
        empty_shell = PLUGIN_ROOT / "skills" / "architectural-openings" / "scripts" / "empty_runtime.py"
        try:
            empty_shell.write_text('"""No dispatch here; apply appears only in prose."""\n', encoding="utf-8")
            shell_packet = dict(packet, runtime_file="scripts/empty_runtime.py")
            self.assertTrue(any("runtime action not found" in error for error in promoter.validate_packet(shell_packet, PLUGIN_ROOT)))
        finally:
            empty_shell.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
