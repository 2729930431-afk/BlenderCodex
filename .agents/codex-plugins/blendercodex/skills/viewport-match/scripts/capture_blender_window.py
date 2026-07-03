#!/usr/bin/env python3
"""Capture a Blender window without forcing it to the foreground.

Windows-only. Uses PrintWindow via ctypes and Pillow to save a PNG.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
dwmapi = ctypes.windll.dwmapi

BOOL = ctypes.c_int
HWND = ctypes.c_void_p
LPARAM = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
PW_RENDERFULLCONTENT = 0x00000002
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DIB_RGB_COLORS = 0
SRCCOPY = 0x00CC0020
SW_SHOWNOACTIVATE = 4


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [("rgbBlue", ctypes.c_byte), ("rgbGreen", ctypes.c_byte), ("rgbRed", ctypes.c_byte), ("rgbReserved", ctypes.c_byte)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


@dataclass
class WindowInfo:
    hwnd: int
    pid: int
    title: str
    rect: tuple[int, int, int, int]
    minimized: bool

    @property
    def area(self) -> int:
        left, top, right, bottom = self.rect
        return max(0, right - left) * max(0, bottom - top)


def set_dpi_awareness() -> None:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def default_session_file(session_name: str) -> Path:
    base = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return base / "blendercodex" / f"bridge_session_{session_name}.json"


def pid_from_session(path: Path) -> int | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    raw = data.get("pid")
    return int(raw) if raw else None


def get_window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(HWND(hwnd))
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(HWND(hwnd), buf, length + 1)
    return buf.value


def window_pid(hwnd: int) -> int:
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(HWND(hwnd), ctypes.byref(pid))
    return int(pid.value)


def is_minimized(hwnd: int) -> bool:
    return bool(user32.IsIconic(HWND(hwnd)))


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = RECT()
    if dwmapi.DwmGetWindowAttribute(HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
        user32.GetWindowRect(HWND(hwnd), ctypes.byref(rect))
    return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))


def enumerate_windows(
    pid: int | None = None,
    title_contains: str | None = None,
    min_area: int = 8000,
    include_minimized: bool = False,
) -> list[WindowInfo]:
    wins: list[WindowInfo] = []
    title_need = title_contains.lower() if title_contains else None

    @ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
    def callback(hwnd: int, _lparam: int) -> int:
        if not user32.IsWindowVisible(HWND(hwnd)):
            return 1
        current_pid = window_pid(hwnd)
        if pid is not None and current_pid != pid:
            return 1
        minimized = is_minimized(hwnd)
        if minimized and not include_minimized:
            return 1
        title = get_window_text(hwnd)
        if title_need and title_need not in title.lower():
            return 1
        rect = window_rect(hwnd)
        info = WindowInfo(int(hwnd), current_pid, title, rect, minimized)
        if info.area >= min_area:
            wins.append(info)
        return 1

    user32.EnumWindows(callback, 0)
    wins.sort(key=lambda w: w.area, reverse=True)
    return wins


def capture_hwnd(hwnd: int) -> Image.Image:
    if is_minimized(hwnd):
        raise RuntimeError("Window is minimized; restore it or use --show-no-activate before capture")
    left, top, right, bottom = window_rect(hwnd)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid window rect: {(left, top, right, bottom)}")

    window_dc = user32.GetWindowDC(HWND(hwnd))
    mem_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    old_obj = gdi32.SelectObject(mem_dc, bitmap)

    try:
        ok = user32.PrintWindow(HWND(hwnd), mem_dc, PW_RENDERFULLCONTENT)
        if not ok:
            ok = user32.PrintWindow(HWND(hwnd), mem_dc, 0)
        if not ok:
            # Last resort captures screen pixels at that rectangle. This still
            # avoids activation but may include occluding windows.
            src_dc = user32.GetDC(None)
            gdi32.BitBlt(mem_dc, 0, 0, width, height, src_dc, left, top, SRCCOPY)
            user32.ReleaseDC(None, src_dc)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = ctypes.create_string_buffer(width * height * 4)
        lines = gdi32.GetDIBits(mem_dc, bitmap, 0, height, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
        if lines == 0:
            raise RuntimeError("GetDIBits returned no image data")
        return Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", 0, 1).convert("RGB")
    finally:
        gdi32.SelectObject(mem_dc, old_obj)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(HWND(hwnd), window_dc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-name", default="default")
    parser.add_argument("--session-file")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd", type=lambda x: int(x, 0))
    parser.add_argument("--title-contains")
    parser.add_argument("--output")
    parser.add_argument("--list", action="store_true", help="List matching windows as JSON and exit")
    parser.add_argument("--min-area", type=int, default=8000)
    parser.add_argument("--include-minimized", action="store_true", help="Include minimized windows when listing or selecting")
    parser.add_argument("--show-no-activate", action="store_true", help="Show/restore the selected window without activating it before capture")
    return parser.parse_args()


def main() -> int:
    if os.name != "nt":
        raise SystemExit("capture_blender_window.py currently supports Windows only")
    set_dpi_awareness()
    args = parse_args()

    pid = args.pid
    session_file = Path(args.session_file) if args.session_file else default_session_file(args.session_name)
    if pid is None and session_file.exists():
        pid = pid_from_session(session_file)

    if args.hwnd is not None:
        targets = [WindowInfo(args.hwnd, window_pid(args.hwnd), get_window_text(args.hwnd), window_rect(args.hwnd), is_minimized(args.hwnd))]
    else:
        targets = enumerate_windows(pid=pid, title_contains=args.title_contains, min_area=args.min_area, include_minimized=args.include_minimized)

    if args.list:
        print(json.dumps([w.__dict__ for w in targets], ensure_ascii=False, indent=2))
        return 0
    if not targets:
        raise SystemExit("No matching Blender window found")
    if not args.output:
        raise SystemExit("--output is required unless --list is used")

    target = targets[0]
    if target.minimized and args.show_no_activate:
        user32.ShowWindow(HWND(target.hwnd), SW_SHOWNOACTIVATE)
        time.sleep(0.25)
        target = WindowInfo(target.hwnd, target.pid, target.title, window_rect(target.hwnd), is_minimized(target.hwnd))
    image = capture_hwnd(target.hwnd)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(
        json.dumps(
            {
                "output": str(output),
                "hwnd": target.hwnd,
                "pid": target.pid,
                "title": target.title,
                "rect": target.rect,
                "width": image.width,
                "height": image.height,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
