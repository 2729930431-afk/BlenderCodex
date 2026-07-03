#!/usr/bin/env python3
"""Run BlenderCodex code with the cached Blender executable."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from blender_locator import find_blender


def default_blend_path(script_path: Path) -> Path:
    return script_path.with_suffix(".blend")


@dataclass
class PreparedScript:
    path: Path
    source: str
    temporary: bool
    cleanup: tempfile.TemporaryDirectory[str] | None = None


def read_code_file(raw_path: str) -> str:
    if raw_path == "-":
        return sys.stdin.read()
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Blender Python code file not found: {path}")
    return path.read_text(encoding="utf-8")


def prepare_script(args: argparse.Namespace) -> PreparedScript:
    if args.script and args.code_file:
        raise ValueError("Pass either a script path or --code-file, not both.")
    if not args.script and not args.code_file:
        raise ValueError("Pass a script path, or pass --code-file for internal temporary execution.")

    if args.script:
        script_path = Path(args.script).expanduser().resolve()
        if not script_path.is_file():
            raise FileNotFoundError(f"Generated Blender Python file not found: {script_path}")
        return PreparedScript(path=script_path, source="script", temporary=False)

    code = read_code_file(args.code_file)
    if args.script_output:
        script_path = Path(args.script_output).expanduser().resolve()
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(code, encoding="utf-8")
        return PreparedScript(path=script_path, source="script_output", temporary=False)

    temp_dir = tempfile.TemporaryDirectory(prefix="blendercodex-internal-")
    script_path = Path(temp_dir.name) / "blendercodex_internal.py"
    script_path.write_text(code, encoding="utf-8")
    return PreparedScript(path=script_path, source="internal_temp", temporary=True, cleanup=temp_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute BlenderCodex code in Blender.")
    parser.add_argument("script", nargs="?", help="Generated Blender Python file to keep as an artifact")
    parser.add_argument(
        "--code-file",
        help="Read Blender Python from a file, or '-' for stdin, and run it through a temporary script.",
    )
    parser.add_argument(
        "--script-output",
        help="Persist --code-file contents to this .py file before running. Omit for internal temporary execution.",
    )
    parser.add_argument("--output-blend", help="Output .blend path")
    parser.add_argument("--version", help="Requested Blender version prefix, e.g. 4.2")
    parser.add_argument("--blender-path", help="Explicit Blender executable or install directory")
    parser.add_argument("--refresh", action="store_true", help="Ignore cached Blender path")
    parser.add_argument(
        "--skip-existing-capture",
        action="store_true",
        help="Skip comparison against an existing output .blend before overwriting it.",
    )
    parser.add_argument(
        "--state-dir",
        help="Persist existing .blend comparison snapshots and reports here. Omit for temporary comparison.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print command without running")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    return parser


def capture_existing_blend(
    args: argparse.Namespace,
    script_path: Path,
    output_blend: Path,
    blender: dict[str, object],
) -> dict[str, object]:
    capture_command = [
        sys.executable,
        str(Path(__file__).with_name("capture_blend_state.py")),
        "--blender-path",
        str(blender["path"]),
        "capture-edits",
        "--blend",
        str(output_blend),
        "--script",
        str(script_path),
    ]
    if args.state_dir:
        capture_command.extend(["--state-dir", str(Path(args.state_dir).expanduser().resolve())])

    capture_env = os.environ.copy()
    capture_env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        capture_command,
        env=capture_env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": capture_command,
        "returncode": result.returncode,
        "persistent_state_dir": str(Path(args.state_dir).expanduser().resolve()) if args.state_dir else None,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def main() -> int:
    args = build_parser().parse_args()

    try:
        prepared = prepare_script(args)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        if args.output_blend:
            output_blend = Path(args.output_blend).expanduser().resolve()
        elif prepared.source == "script":
            output_blend = default_blend_path(prepared.path)
        else:
            print("--output-blend is required when using --code-file without a script path.", file=sys.stderr)
            return 1

        script_path = prepared.path
        blender = find_blender(args.version, args.refresh, args.blender_path)
        command = [
            blender["path"],
            "--factory-startup",
            "-b",
            "--python",
            str(script_path),
            "--",
            "--output-blend",
            str(output_blend),
        ]
        payload: dict[str, object] = {
            "command": command,
            "script": str(script_path),
            "script_source": prepared.source,
            "temporary_script": prepared.temporary,
            "output_blend": str(output_blend),
            "blender": blender,
        }

        if args.dry_run:
            if output_blend.is_file() and not args.skip_existing_capture:
                existing_capture_command = [
                    sys.executable,
                    str(Path(__file__).with_name("capture_blend_state.py")),
                    "--blender-path",
                    blender["path"],
                    "capture-edits",
                    "--blend",
                    str(output_blend),
                    "--script",
                    str(script_path),
                ]
                if args.state_dir:
                    existing_capture_command.extend(
                        ["--state-dir", str(Path(args.state_dir).expanduser().resolve())]
                    )
                payload["existing_capture_command"] = existing_capture_command
            print(json.dumps(payload, indent=2) if args.json else " ".join(command))
            return 0

        output_blend.parent.mkdir(parents=True, exist_ok=True)
        if output_blend.is_file() and not args.skip_existing_capture:
            capture_payload = capture_existing_blend(args, script_path, output_blend, blender)
            payload["existing_capture"] = capture_payload
            if capture_payload["returncode"] != 0:
                if args.json:
                    print(json.dumps(payload, indent=2))
                print(
                    f"Existing .blend capture failed; refusing to overwrite: {output_blend}",
                    file=sys.stderr,
                )
                return int(capture_payload["returncode"])

        env = os.environ.copy()
        env["BLENDERCODEX_OUTPUT_BLEND"] = str(output_blend)
        result = subprocess.run(command, env=env, check=False)
        payload["returncode"] = result.returncode
        payload["exists"] = output_blend.is_file()
        if args.json:
            print(json.dumps(payload, indent=2))
        if result.returncode != 0:
            return result.returncode
        if not output_blend.is_file():
            print(f"Blender finished but output was not created: {output_blend}", file=sys.stderr)
            return 2
        return 0
    finally:
        if prepared.cleanup is not None:
            prepared.cleanup.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
