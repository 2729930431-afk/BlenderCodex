#!/usr/bin/env python3
"""Find, select, and cache the local Blender executable for BlenderCodex."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
CONFIG_ENV = "BLENDERCODEX_CONFIG_DIR"


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override).expanduser().resolve() / "config.json"
    codex_home = os.environ.get("CODEX_HOME")
    base = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return base / "blendercodex" / "config.json"


def parse_version_tuple(text: str | None) -> tuple[int, int, int] | None:
    if not text:
        return None
    matches = VERSION_RE.findall(text)
    if not matches:
        return None
    major, minor, patch = matches[-1]
    return (int(major), int(minor), int(patch or 0))


def version_tuple_to_str(version: tuple[int, int, int] | None) -> str:
    if version is None:
        return ""
    return ".".join(str(part) for part in version)


def requested_version_tuple(raw: str | None) -> tuple[int, ...] | None:
    if not raw:
        return None
    match = VERSION_RE.search(raw)
    if not match:
        raise ValueError(f"Invalid Blender version request: {raw}")
    values = [int(match.group(1)), int(match.group(2))]
    if match.group(3) is not None:
        values.append(int(match.group(3)))
    return tuple(values)


def version_matches(candidate: str | None, requested: str | None) -> bool:
    requested_tuple = requested_version_tuple(requested)
    if requested_tuple is None:
        return True
    candidate_tuple = parse_version_tuple(candidate)
    if candidate_tuple is None:
        return False
    return candidate_tuple[: len(requested_tuple)] == requested_tuple


def resolve_executable(raw_path: str | Path) -> Path | None:
    path = Path(raw_path).expanduser()
    if path.is_dir():
        executable = path / ("blender.exe" if os.name == "nt" else "blender")
        if executable.is_file():
            return executable.resolve()
    if path.is_file():
        return path.resolve()
    return None


def run_blender_version(path: Path) -> str:
    try:
        result = subprocess.run(
            [str(path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return version_tuple_to_str(parse_version_tuple(str(path)))
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return version_tuple_to_str(parse_version_tuple(output)) or version_tuple_to_str(
        parse_version_tuple(str(path))
    )


def path_candidates() -> dict[Path, str]:
    candidates: dict[Path, str] = {}

    for env_name in ("BLENDER_PATH", "BLENDER_EXECUTABLE"):
        raw = os.environ.get(env_name)
        if raw:
            resolved = resolve_executable(raw)
            if resolved:
                candidates[resolved] = env_name

    for command_name in ("blender", "blender.exe"):
        raw = shutil.which(command_name)
        if raw:
            resolved = resolve_executable(raw)
            if resolved:
                candidates[resolved] = "PATH"

    if os.name == "nt":
        roots = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
            os.environ.get("ProgramData"),
        ]
        for raw_root in [root for root in roots if root]:
            root = Path(raw_root)
            foundation = root / "Blender Foundation"
            for match in foundation.glob("Blender*"):
                resolved = resolve_executable(match)
                if resolved:
                    candidates[resolved] = "common-windows"
            for direct in (
                root / "Blender Foundation" / "Blender" / "blender.exe",
                root / "Microsoft" / "WindowsApps" / "blender.exe",
                root / "chocolatey" / "bin" / "blender.exe",
            ):
                resolved = resolve_executable(direct)
                if resolved:
                    candidates[resolved] = "common-windows"
        scoop = Path.home() / "scoop" / "apps" / "blender" / "current" / "blender.exe"
        resolved = resolve_executable(scoop)
        if resolved:
            candidates[resolved] = "scoop"
        candidates.update(registry_windows_candidates())
    else:
        for raw in (
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/usr/bin/blender",
            "/usr/local/bin/blender",
            "/opt/homebrew/bin/blender",
        ):
            resolved = resolve_executable(raw)
            if resolved:
                candidates[resolved] = "common-unix"

    return candidates


def clean_registry_path(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip()
    if value.startswith('"'):
        parts = value.split('"')
        value = parts[1] if len(parts) > 1 else value.strip('"')
    else:
        lower = value.lower()
        exe_index = lower.find(".exe")
        if exe_index >= 0:
            value = value[: exe_index + 4]
        elif "," in value:
            value = value.split(",", 1)[0]
    return value.strip().strip('"') or None


def registry_windows_candidates() -> dict[Path, str]:
    if os.name != "nt":
        return {}
    try:
        import winreg
    except ImportError:
        return {}

    keys = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    candidates: dict[Path, str] = {}
    for root, key_path in keys:
        try:
            with winreg.OpenKey(root, key_path) as key:
                subkey_count = winreg.QueryInfoKey(key)[0]
                for index in range(subkey_count):
                    try:
                        subkey_name = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            values = {}
                            for value_name in ("DisplayName", "InstallLocation", "DisplayIcon"):
                                try:
                                    values[value_name] = winreg.QueryValueEx(subkey, value_name)[0]
                                except OSError:
                                    values[value_name] = ""
                    except OSError:
                        continue
                    haystack = " ".join(str(value) for value in values.values()).lower()
                    if "blender" not in haystack:
                        continue
                    for value_name in ("InstallLocation", "DisplayIcon"):
                        cleaned = clean_registry_path(str(values.get(value_name) or ""))
                        if not cleaned:
                            continue
                        resolved = resolve_executable(cleaned)
                        if resolved:
                            candidates[resolved] = "registry"
        except OSError:
            continue
    return candidates


def load_cache() -> dict[str, Any] | None:
    path = config_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def save_cache(payload: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def cache_is_valid(payload: dict[str, Any], requested_version: str | None) -> bool:
    raw_path = payload.get("path")
    if not isinstance(raw_path, str):
        return False
    resolved = resolve_executable(raw_path)
    if resolved is None:
        return False
    return version_matches(payload.get("version"), requested_version)


def make_payload(path: Path, source: str) -> dict[str, Any]:
    version = run_blender_version(path)
    return {
        "path": str(path),
        "version": version,
        "source": source,
        "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_path": str(config_path()),
    }


def find_blender(
    requested_version: str | None = None,
    refresh: bool = False,
    explicit_path: str | None = None,
) -> dict[str, Any]:
    if explicit_path:
        resolved = resolve_executable(explicit_path)
        if resolved is None:
            raise FileNotFoundError(f"Blender executable not found: {explicit_path}")
        payload = make_payload(resolved, "explicit")
        if not version_matches(payload.get("version"), requested_version):
            raise ValueError(
                f"Blender at {resolved} is version {payload.get('version') or 'unknown'}, "
                f"not requested version {requested_version}."
            )
        save_cache(payload)
        return payload

    cached = load_cache()
    if cached and not refresh and cache_is_valid(cached, requested_version):
        cached = dict(cached)
        cached["source"] = "cache"
        cached["config_path"] = str(config_path())
        return cached

    candidates = []
    for path, source in path_candidates().items():
        payload = make_payload(path, source)
        if version_matches(payload.get("version"), requested_version):
            candidates.append(payload)

    if not candidates:
        hint = "Specify Blender with: blender_locator.py set --path <blender executable>"
        if requested_version:
            hint += f" --version {requested_version}"
        raise FileNotFoundError(f"No matching Blender install found. {hint}")

    candidates.sort(
        key=lambda item: parse_version_tuple(item.get("version")) or (0, 0, 0),
        reverse=True,
    )
    selected = candidates[0]
    save_cache(selected)
    return selected


def print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload["path"])


def run_self_test() -> None:
    assert parse_version_tuple("Blender 4.2.1") == (4, 2, 1)
    assert parse_version_tuple(r"C:\Program Files\Blender Foundation\Blender 3.6") == (
        3,
        6,
        0,
    )
    assert requested_version_tuple("4.1") == (4, 1)
    assert requested_version_tuple("4.1.2") == (4, 1, 2)
    assert version_matches("4.1.2", "4.1")
    assert not version_matches("4.2.0", "4.1")
    print("blender_locator self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Find and cache Blender for BlenderCodex.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    find_parser = subparsers.add_parser("find", help="Find and cache Blender")
    find_parser.add_argument("--version", help="Requested Blender version prefix, e.g. 4.2")
    find_parser.add_argument("--path", help="Explicit Blender executable or install directory")
    find_parser.add_argument("--refresh", action="store_true", help="Ignore cached path")
    find_parser.add_argument("--json", action="store_true", help="Print JSON")

    set_parser = subparsers.add_parser("set", help="Cache an explicit Blender path")
    set_parser.add_argument("--path", required=True, help="Blender executable or install directory")
    set_parser.add_argument("--version", help="Requested Blender version prefix")
    set_parser.add_argument("--json", action="store_true", help="Print JSON")

    show_parser = subparsers.add_parser("show", help="Show the cached Blender path")
    show_parser.add_argument("--json", action="store_true", help="Print JSON")

    subparsers.add_parser("clear", help="Clear the cached Blender path")
    subparsers.add_parser("self-test", help="Run deterministic parser tests")

    args = parser.parse_args()
    try:
        if args.command == "find":
            payload = find_blender(args.version, args.refresh, args.path)
            print_payload(payload, args.json)
        elif args.command == "set":
            payload = find_blender(args.version, True, args.path)
            print_payload(payload, args.json)
        elif args.command == "show":
            payload = load_cache()
            if not payload:
                raise FileNotFoundError(f"No Blender cache exists at {config_path()}")
            payload["config_path"] = str(config_path())
            print_payload(payload, args.json)
        elif args.command == "clear":
            path = config_path()
            if path.exists():
                path.unlink()
            print(f"Cleared {path}")
        elif args.command == "self-test":
            run_self_test()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
