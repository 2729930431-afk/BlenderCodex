#!/usr/bin/env python3
"""Refine Blender screenshots into design references with GPT Image 2."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import textwrap
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image


API_BASE = "https://api.openai.com/v1"
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MODE_HINTS = {
    "refine": "Enhance the current screenshot into a polished production design reference while preserving the existing layout.",
    "material": "Focus on material treatment, color palette, wear, grime, decals, and surface finish while preserving geometry.",
    "variant": "Create one coherent alternate design that keeps the asset role and rough silhouette.",
    "callout-sheet": "Create a clean design callout sheet with concise labels only where they clarify modeling changes.",
    "orthographic": "Create a cleaner blueprint-like design reference with front/side/three-quarter readability.",
    "texture": "Focus on texture and material replacement ideas that can be applied to the current model.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", required=True, help="Screenshot/reference image. May be repeated up to 16 times.")
    parser.add_argument("--user-request", help="User design requirement. Required unless --prompt-file is used.")
    parser.add_argument("--prompt-file")
    parser.add_argument("--scene-summary-json", help="Optional blendercodex_scene_summary JSON file.")
    parser.add_argument("--design-mode", choices=sorted(MODE_HINTS), default="refine")
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--quality", choices=["low", "medium", "high", "auto"], default="high")
    parser.add_argument("--size", default="from-image", help="auto, from-image, or WIDTHxHEIGHT.")
    parser.add_argument("--max-edge", type=int, default=1536, help="Max output edge when --size from-image is used.")
    parser.add_argument("--background", choices=["auto", "opaque", "transparent"], default="auto")
    parser.add_argument("--input-fidelity", choices=["high", "low", "omit"], default="omit")
    parser.add_argument("--output-format", choices=["png", "jpeg", "webp"], default="png")
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-metadata")
    parser.add_argument("--save-prompt")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


def read_scene_summary(path: str | None) -> str:
    if not path:
        return "No scene summary provided."
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    keep = {
        "file": data.get("file"),
        "scene": data.get("scene"),
        "object_count": data.get("object_count"),
        "collection_count": data.get("collection_count"),
        "material_count": data.get("material_count"),
        "collections": [c.get("name") for c in data.get("collections", [])[:12]],
    }
    return json.dumps(keep, ensure_ascii=False)


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    else:
        if not args.user_request:
            raise SystemExit("--user-request or --prompt-file is required")
        scene_summary = read_scene_summary(args.scene_summary_json)
        prompt = f"""
Use the attached Blender viewport screenshot as the exact current state of a game asset.
Refine it into a production-ready visual design reference.

Mode:
{args.design_mode}: {MODE_HINTS[args.design_mode]}

User request:
{args.user_request}

Scene notes:
{scene_summary}

Preserve:
- current asset identity, broad silhouette, camera/view composition, and major proportions
- existing large modules unless the user explicitly asks to change them
- model readability for later Blender editing

Improve:
- design specificity and medium-level detail
- material/color decisions
- readable construction of repeated or modular parts
- game-asset clarity from the current viewport

Avoid:
- changing the asset into a different object category
- adding unrelated characters, vehicles, logos, UI, or watermarks
- tiny noisy details that cannot be modeled
- heavy text unless callout mode is requested
"""
    prompt = textwrap.dedent(prompt).strip()
    if len(prompt) > 32000:
        raise SystemExit(f"Prompt is too long for GPT image models: {len(prompt)} characters")
    return prompt


def validate_images(paths: list[str]) -> list[Path]:
    if len(paths) > 16:
        raise SystemExit("GPT image edit supports up to 16 input images")
    out: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            raise SystemExit(f"Image does not exist: {path}")
        if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            raise SystemExit(f"Unsupported image suffix for GPT image edit: {path.suffix}")
        if path.stat().st_size >= 50 * 1024 * 1024:
            raise SystemExit(f"Image must be under 50MB: {path}")
        out.append(path)
    return out


def size_from_image(path: Path, max_edge: int) -> str:
    image = Image.open(path)
    w, h = image.size
    min_pixels = 655_360
    max_pixels = 8_294_400
    scale_for_min = (min_pixels / max(1, w * h)) ** 0.5
    scale_for_max = (max_pixels / max(1, w * h)) ** 0.5
    scale_for_edge = max_edge / max(w, h)
    scale = min(max(scale_for_min, 1.0), scale_for_max, scale_for_edge)
    w = max(16, int(round((w * scale) / 16) * 16))
    h = max(16, int(round((h * scale) / 16) * 16))
    ratio = w / h
    if ratio > 3:
        w = int(round((h * 3) / 16) * 16)
    elif ratio < 1 / 3:
        h = int(round((w * 3) / 16) * 16)
    return f"{w}x{h}"


def resolve_size(raw: str, images: list[Path], max_edge: int) -> str:
    if raw == "from-image":
        return size_from_image(images[0], max_edge)
    return raw


def build_multipart(fields: list[tuple[str, str]], files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    boundary = f"----codex-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    def add(line: str | bytes) -> None:
        chunks.append(line if isinstance(line, bytes) else line.encode("utf-8"))

    for name, value in fields:
        add(f"--{boundary}\r\n")
        add(f'Content-Disposition: form-data; name="{name}"\r\n\r\n')
        add(str(value))
        add("\r\n")
    for field, path in files:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        add(f"--{boundary}\r\n")
        add(f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n')
        add(f"Content-Type: {mime}\r\n\r\n")
        chunks.append(path.read_bytes())
        add("\r\n")
    add(f"--{boundary}--\r\n")
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def request_images(args: argparse.Namespace, images: list[Path], prompt: str, size: str) -> dict:
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is not set")
    base = os.environ.get("OPENAI_BASE_URL", API_BASE).rstrip("/")
    url = f"{base}/images/edits"
    fields = [
        ("model", args.model),
        ("prompt", prompt),
        ("quality", args.quality),
        ("size", size),
        ("n", str(args.n)),
        ("background", args.background),
        ("output_format", args.output_format),
    ]
    if args.input_fidelity != "omit":
        fields.append(("input_fidelity", args.input_fidelity))
    body, content_type = build_multipart(fields, [("image[]", path) for path in images])
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI Images API error {exc.code}: {detail}") from exc


def output_paths(base: Path, count: int, ext: str) -> list[Path]:
    if count == 1:
        return [base.with_suffix(f".{ext}")]
    return [base.with_name(f"{base.stem}_{i + 1:02d}").with_suffix(f".{ext}") for i in range(count)]


def save_response_images(response: dict, output: Path, output_format: str) -> list[str]:
    data = response.get("data") or []
    paths = output_paths(output, len(data), output_format)
    output.parent.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for item, path in zip(data, paths):
        b64 = item.get("b64_json")
        if b64:
            path.write_bytes(base64.b64decode(b64))
            saved.append(str(path))
            continue
        url = item.get("url")
        if url:
            with urllib.request.urlopen(url, timeout=120) as resp:
                path.write_bytes(resp.read())
            saved.append(str(path))
    return saved


def main() -> int:
    args = parse_args()
    images = validate_images(args.image)
    if args.model.startswith("gpt-image-2") and args.background == "transparent":
        raise SystemExit("gpt-image-2 does not support transparent backgrounds; use auto or opaque")
    prompt = load_prompt(args)
    size = resolve_size(args.size, images, args.max_edge)
    request_preview = {
        "endpoint": "/v1/images/edits",
        "model": args.model,
        "images": [str(p) for p in images],
        "size": size,
        "quality": args.quality,
        "background": args.background,
        "input_fidelity": None if args.input_fidelity == "omit" else args.input_fidelity,
        "output_format": args.output_format,
        "n": args.n,
        "prompt": prompt,
    }
    if args.save_prompt:
        Path(args.save_prompt).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save_prompt).write_text(prompt + "\n", encoding="utf-8")
    if args.dry_run:
        print(json.dumps({"dry_run": True, "request": request_preview}, ensure_ascii=False, indent=2))
        return 0

    response = request_images(args, images, prompt, size)
    saved = save_response_images(response, Path(args.output), args.output_format)
    metadata = {"request": {k: v for k, v in request_preview.items() if k != "prompt"}, "prompt": prompt, "saved": saved, "response": response}
    if args.output_metadata:
        Path(args.output_metadata).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_metadata).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"saved": saved, "metadata": args.output_metadata}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
