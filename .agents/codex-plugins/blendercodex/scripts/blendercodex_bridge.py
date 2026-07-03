"""Temporary BlenderCodex RPC bridge.

Run this file inside Blender with:

    blender.exe optional-file.blend --python blendercodex_bridge.py

The bridge is not installed as an add-on. It exists only for the lifetime of the
current Blender process, listens on localhost, and requires a per-session token
written to a session JSON file.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import queue
import secrets
import socket
import socketserver
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import bpy


DEFAULT_HOST = "127.0.0.1"
DEFAULT_SESSION_NAME = "default"


def parse_blender_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Start a temporary BlenderCodex RPC bridge.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token")
    parser.add_argument("--session-file")
    parser.add_argument("--session-name", default=DEFAULT_SESSION_NAME)
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="Keep Blender alive and process RPC work on this script thread. Useful for background smoke tests.",
    )
    return parser.parse_args(argv)


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".codex"


def safe_session_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name.strip())
    return cleaned or DEFAULT_SESSION_NAME


def default_session_file(name: str) -> Path:
    return codex_home() / "blendercodex" / f"bridge_session_{safe_session_name(name)}.json"


def json_response(request_id: Any, result: Any = None, error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"id": request_id}
    if error is None:
        payload["ok"] = True
        payload["result"] = result
    else:
        payload["ok"] = False
        payload["error"] = error
    return payload


def object_payload(obj: bpy.types.Object) -> dict[str, Any]:
    return {
        "name": obj.name,
        "type": obj.type,
        "location": [round(float(value), 6) for value in obj.location],
        "rotation_euler": [round(float(value), 6) for value in obj.rotation_euler],
        "scale": [round(float(value), 6) for value in obj.scale],
        "dimensions": [round(float(value), 6) for value in obj.dimensions],
        "collections": sorted(collection.name for collection in obj.users_collection),
    }


def collection_payload(collection: bpy.types.Collection) -> dict[str, Any]:
    return {
        "name": collection.name,
        "objects": sorted(obj.name for obj in collection.objects),
        "children": sorted(child.name for child in collection.children),
    }


def scene_summary() -> dict[str, Any]:
    bpy.context.view_layer.update()
    return {
        "file": bpy.data.filepath,
        "scene": bpy.context.scene.name,
        "blender_version": bpy.app.version_string,
        "object_count": len(bpy.context.scene.objects),
        "collection_count": len(bpy.data.collections),
        "material_count": len(bpy.data.materials),
        "collections": [collection_payload(collection) for collection in sorted(bpy.data.collections, key=lambda item: item.name)],
        "objects": [object_payload(obj) for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name)],
        "materials": sorted(material.name for material in bpy.data.materials),
    }


def execute_python(code: str) -> dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    namespace: dict[str, Any] = {
        "__name__": "__blendercodex_bridge_exec__",
        "bpy": bpy,
        "RESULT": None,
    }
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exec(code, namespace)
    result = namespace.get("RESULT")
    try:
        json.dumps(result)
        json_result = result
    except TypeError:
        json_result = repr(result)
    return {
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "result": json_result,
    }


def save_file(filepath: str | None = None) -> dict[str, Any]:
    if filepath:
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(filepath).expanduser()))
    else:
        bpy.ops.wm.save_as_mainfile()
    return {
        "file": bpy.data.filepath,
        "saved": True,
    }


def open_file(filepath: str) -> dict[str, Any]:
    bpy.ops.wm.open_mainfile(filepath=str(Path(filepath).expanduser()))
    return scene_summary()


def run_method(method: str, params: dict[str, Any]) -> Any:
    if method == "ping":
        return {
            "pong": True,
            "file": bpy.data.filepath,
            "scene": bpy.context.scene.name,
            "blender_version": bpy.app.version_string,
            "object_count": len(bpy.context.scene.objects),
        }
    if method == "scene_summary":
        return scene_summary()
    if method == "run_python":
        code = params.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("run_python requires a non-empty code string.")
        return execute_python(code)
    if method == "save":
        filepath = params.get("filepath")
        if filepath is not None and not isinstance(filepath, str):
            raise ValueError("save filepath must be a string when provided.")
        return save_file(filepath)
    if method == "open_file":
        filepath = params.get("filepath")
        if not isinstance(filepath, str) or not filepath:
            raise ValueError("open_file requires filepath.")
        return open_file(filepath)
    if method == "shutdown":
        BridgeState.current.stop_requested = True
        return {"shutdown": True}
    raise ValueError(f"Unknown method: {method}")


@dataclass
class WorkItem:
    request_id: Any
    method: str
    params: dict[str, Any]
    event: threading.Event = field(default_factory=threading.Event)
    response: dict[str, Any] | None = None


class BridgeState:
    current: "BridgeState"

    def __init__(self, token: str):
        self.token = token
        self.work_queue: queue.Queue[WorkItem] = queue.Queue()
        self.stop_requested = False
        self.server: socketserver.ThreadingTCPServer | None = None


class BridgeTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class BridgeRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        state = BridgeState.current
        for raw_line in self.rfile:
            try:
                request = json.loads(raw_line.decode("utf-8"))
                request_id = request.get("id")
                if request.get("token") != state.token:
                    self.write_response(json_response(request_id, error="Unauthorized bridge token."))
                    continue
                method = request.get("method")
                params = request.get("params") or {}
                if not isinstance(method, str):
                    self.write_response(json_response(request_id, error="Request method must be a string."))
                    continue
                if not isinstance(params, dict):
                    self.write_response(json_response(request_id, error="Request params must be an object."))
                    continue

                item = WorkItem(request_id=request_id, method=method, params=params)
                state.work_queue.put(item)
                if not item.event.wait(timeout=float(request.get("timeoutSeconds") or 30.0)):
                    self.write_response(json_response(request_id, error=f"Bridge request timed out: {method}"))
                    continue
                self.write_response(item.response or json_response(request_id, error="Missing bridge response."))
            except Exception as exc:  # noqa: BLE001 - bridge must report errors to the caller.
                self.write_response(json_response(None, error=f"{exc}\n{traceback.format_exc()}"))

    def write_response(self, response: dict[str, Any]) -> None:
        self.wfile.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
        self.wfile.flush()


def process_one_item(item: WorkItem) -> None:
    try:
        result = run_method(item.method, item.params)
        item.response = json_response(item.request_id, result=result)
    except Exception as exc:  # noqa: BLE001 - preserve Blender-side traceback.
        item.response = json_response(item.request_id, error=f"{exc}\n{traceback.format_exc()}")
    finally:
        item.event.set()


def process_queue_once() -> None:
    state = BridgeState.current
    while True:
        try:
            item = state.work_queue.get_nowait()
        except queue.Empty:
            break
        process_one_item(item)


def timer_tick() -> float | None:
    process_queue_once()
    state = BridgeState.current
    if state.stop_requested:
        cleanup_session()
        if state.server is not None:
            def stop_server() -> None:
                state.server.shutdown()
                state.server.server_close()

            threading.Thread(target=stop_server, daemon=True).start()
        return None
    return 0.05


def cleanup_session() -> None:
    raw = os.environ.get("BLENDERCODEX_BRIDGE_SESSION_FILE")
    if not raw:
        return
    path = Path(raw)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def write_session_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def main() -> None:
    args = parse_blender_args()
    session_file = Path(args.session_file).expanduser() if args.session_file else default_session_file(args.session_name)
    token = args.token or secrets.token_urlsafe(32)

    BridgeState.current = BridgeState(token)
    server = BridgeTCPServer((args.host, args.port), BridgeRequestHandler)
    BridgeState.current.server = server
    host, port = server.server_address

    os.environ["BLENDERCODEX_BRIDGE_SESSION_FILE"] = str(session_file)
    session_payload = {
        "schema_version": 1,
        "host": host,
        "port": port,
        "token": token,
        "pid": os.getpid(),
        "session_name": args.session_name,
        "file": bpy.data.filepath,
        "scene": bpy.context.scene.name,
        "blender_version": bpy.app.version_string,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bridge_script": str(Path(__file__).resolve()),
    }
    write_session_file(session_file, session_payload)

    server_thread = threading.Thread(target=server.serve_forever, name="BlenderCodexBridgeServer", daemon=True)
    server_thread.start()
    print(f"BlenderCodex bridge listening on {host}:{port}")
    print(f"BlenderCodex bridge session: {session_file}")

    if args.keep_alive:
        try:
            while not BridgeState.current.stop_requested:
                process_queue_once()
                time.sleep(0.02)
        finally:
            cleanup_session()
            server.shutdown()
            server.server_close()
        return

    bpy.app.timers.register(timer_tick, first_interval=0.05, persistent=True)


if __name__ == "__main__":
    main()
