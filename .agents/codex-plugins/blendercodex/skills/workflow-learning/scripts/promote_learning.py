"""Validate that a learned Blender workflow has executable promotion evidence."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys


REQUIRED_EXECUTABLE_FIELDS = (
    "observed_problem",
    "owner_skill",
    "runtime_action",
    "parameter_schema",
    "fixture",
    "acceptance_checks",
    "mcp_tool",
    "tests",
)


def _runtime_actions(runtime_path: Path) -> set[str]:
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    actions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            comparison = node.test
            if len(comparison.ops) == 1 and isinstance(comparison.ops[0], ast.In):
                if isinstance(comparison.left, ast.Name) and comparison.left.id == "action" and isinstance(comparison.comparators[0], (ast.Tuple, ast.List, ast.Set)):
                    actions.update(
                        element.value
                        for element in comparison.comparators[0].elts
                        if isinstance(element, ast.Constant) and isinstance(element.value, str)
                    )
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        left, right = node.left, node.comparators[0]
        if isinstance(left, ast.Name) and left.id == "action" and isinstance(right, ast.Constant) and isinstance(right.value, str):
            actions.add(right.value)
        if isinstance(right, ast.Name) and right.id == "action" and isinstance(left, ast.Constant) and isinstance(left.value, str):
            actions.add(left.value)
    return actions


def validate_packet(packet: dict, plugin_root: Path) -> list[str]:
    errors = []
    kind = str(packet.get("kind") or "executable")
    required = ("observed_problem", "future_rule") if kind == "policy" else REQUIRED_EXECUTABLE_FIELDS
    for field in required:
        if not packet.get(field):
            errors.append(f"missing {field}")
    if kind != "policy" and packet.get("owner_skill"):
        skill_root = plugin_root / "skills" / str(packet["owner_skill"])
        if not (skill_root / "SKILL.md").exists():
            errors.append(f"owner skill not found: {packet['owner_skill']}")
        runtime = packet.get("runtime_file")
        if not runtime:
            errors.append("missing runtime_file")
        elif not (skill_root / str(runtime)).exists():
            errors.append(f"runtime file not found: {runtime}")
        else:
            try:
                actions = _runtime_actions(skill_root / str(runtime))
            except (OSError, SyntaxError) as exc:
                errors.append(f"runtime cannot be parsed: {exc}")
                actions = set()
            if str(packet.get("runtime_action") or "") not in actions:
                errors.append(f"runtime action not found in runtime: {packet.get('runtime_action')}")
        fixture = packet.get("fixture")
        if fixture and not (plugin_root / str(fixture)).exists():
            errors.append(f"fixture not found: {fixture}")
        mcp_tool = packet.get("mcp_tool")
        mcp_server = plugin_root / "scripts" / "blendercodex_mcp_server.js"
        mcp_text = mcp_server.read_text(encoding="utf-8") if mcp_server.exists() else ""
        if mcp_tool and f'name: "{mcp_tool}"' not in mcp_text:
            errors.append(f"MCP tool not found: {mcp_tool}")
        test_paths = [plugin_root / str(test) for test in packet.get("tests") or []]
        for test_path in test_paths:
            if not test_path.exists():
                errors.append(f"test not found: {test_path.relative_to(plugin_root)}")
        if test_paths and all(path.exists() for path in test_paths):
            combined_tests = "\n".join(path.read_text(encoding="utf-8") for path in test_paths)
            for token, label in ((str(packet.get("runtime_action") or ""), "runtime action"), (str(mcp_tool or ""), "MCP tool")):
                if token and token not in combined_tests:
                    errors.append(f"tests do not reference {label}: {token}")
            for check in packet.get("acceptance_checks") or []:
                if str(check) not in combined_tests:
                    errors.append(f"tests do not reference acceptance check: {check}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("packet")
    parser.add_argument("--plugin-root", required=True)
    args = parser.parse_args(argv)
    packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    errors = validate_packet(packet, Path(args.plugin_root))
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
