#!/usr/bin/env python3
"""Compare a reference image and Blender viewport capture."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def parse_crop(raw: str | None) -> tuple[int, int, int, int] | None:
    if not raw:
        return None
    parts = [int(p.strip()) for p in raw.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("Crop must be x,y,w,h")
    return (parts[0], parts[1], parts[2], parts[3])


def load_rgb(path: Path, crop: tuple[int, int, int, int] | None, max_side: int = 768) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if crop:
        x, y, w, h = crop
        image = image.crop((x, y, x + w, y + h))
    scale = max_side / max(image.size)
    if scale < 1.0:
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    return image


def border_pixels(arr: np.ndarray, width: int = 12) -> np.ndarray:
    h, w, _ = arr.shape
    width = max(1, min(width, h // 4, w // 4))
    return np.concatenate([arr[:width].reshape(-1, 3), arr[-width:].reshape(-1, 3), arr[:, :width].reshape(-1, 3), arr[:, -width:].reshape(-1, 3)], axis=0)


def dilate(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="constant")
    out = np.zeros_like(mask)
    for dy in range(3):
        for dx in range(3):
            out |= padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    return out


def erode(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="constant", constant_values=True)
    out = np.ones_like(mask)
    for dy in range(3):
        for dx in range(3):
            out &= padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    return out


def largest_component(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best: list[tuple[int, int]] = []
    coords = np.argwhere(mask)
    for start_y, start_x in coords:
        if seen[start_y, start_x]:
            continue
        stack = [(int(start_y), int(start_x))]
        seen[start_y, start_x] = True
        comp: list[tuple[int, int]] = []
        while stack:
            y, x = stack.pop()
            comp.append((y, x))
            for ny in (y - 1, y, y + 1):
                for nx in (x - 1, x, x + 1):
                    if ny < 0 or ny >= h or nx < 0 or nx >= w or seen[ny, nx] or not mask[ny, nx]:
                        continue
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(comp) > len(best):
            best = comp
    out = np.zeros_like(mask, dtype=bool)
    if best:
        ys, xs = zip(*best)
        out[np.array(ys), np.array(xs)] = True
    return out


def make_mask(image: Image.Image) -> np.ndarray:
    arr = np.asarray(image).astype(np.float32) / 255.0
    bg = np.median(border_pixels(arr), axis=0)
    dist = np.linalg.norm(arr - bg, axis=2)
    lum = arr.mean(axis=2)
    bg_lum = float(np.mean(bg))
    sat = (arr.max(axis=2) - arr.min(axis=2)) / np.maximum(arr.max(axis=2), 1e-4)
    threshold = max(0.10, min(0.28, float(np.percentile(dist, 78))))
    mask = (dist > threshold) | (np.abs(lum - bg_lum) > 0.16) | ((sat > 0.18) & (dist > 0.06))
    mask = erode(dilate(dilate(mask)))
    largest = largest_component(mask)
    return largest if largest.any() else mask


def bbox(mask: np.ndarray) -> list[int]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return [0, 0, mask.shape[1] - 1, mask.shape[0] - 1]
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def edge_histogram(image: Image.Image, mask: np.ndarray, bins: int = 18) -> list[float]:
    gray = np.asarray(image.convert("L")).astype(np.float32) / 255.0
    gy, gx = np.gradient(gray)
    mag = np.sqrt(gx * gx + gy * gy)
    orient = np.mod(np.arctan2(gy, gx), math.pi)
    threshold = np.percentile(mag, 82)
    weights = mag * (mag >= threshold) * mask
    hist, _edges = np.histogram(orient, bins=bins, range=(0, math.pi), weights=weights)
    total = float(hist.sum())
    if total <= 1e-8:
        return [0.0] * bins
    return (hist / total).astype(float).tolist()


def normalized_crop(image: Image.Image, box: list[int], size: int = 192) -> np.ndarray:
    x0, y0, x1, y1 = box
    crop = image.crop((x0, y0, x1 + 1, y1 + 1)).convert("L").resize((size, size), Image.Resampling.BILINEAR)
    arr = np.asarray(crop).astype(np.float32) / 255.0
    return (arr - arr.mean()) / (arr.std() + 1e-5)


def features(image: Image.Image) -> dict:
    mask = make_mask(image)
    box = bbox(mask)
    x0, y0, x1, y1 = box
    w = max(1, x1 - x0 + 1)
    h = max(1, y1 - y0 + 1)
    return {
        "size": [image.width, image.height],
        "bbox": box,
        "center": [((x0 + x1) / 2) / image.width, ((y0 + y1) / 2) / image.height],
        "area_fraction": float(mask.mean()),
        "aspect": float(w / h),
        "edge_histogram": edge_histogram(image, mask),
        "mask": mask,
    }


def cosine(a: list[float], b: list[float]) -> float:
    aa = np.asarray(a, dtype=np.float32)
    bb = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(aa) * np.linalg.norm(bb))
    return float(np.dot(aa, bb) / denom) if denom > 1e-8 else 0.0


def compare(reference: Image.Image, capture: Image.Image) -> dict:
    rf = features(reference)
    cf = features(capture)
    center_delta = [cf["center"][0] - rf["center"][0], cf["center"][1] - rf["center"][1]]
    center_score = math.sqrt(center_delta[0] ** 2 + center_delta[1] ** 2)
    area_ratio = max(cf["area_fraction"], 1e-6) / max(rf["area_fraction"], 1e-6)
    aspect_ratio = max(cf["aspect"], 1e-6) / max(rf["aspect"], 1e-6)
    edge_cos = cosine(rf["edge_histogram"], cf["edge_histogram"])
    rcrop = normalized_crop(reference, rf["bbox"])
    ccrop = normalized_crop(capture, cf["bbox"])
    crop_mse = float(np.mean((rcrop - ccrop) ** 2) / 4.0)
    score = 0.28 * center_score + 0.22 * abs(math.log(area_ratio)) + 0.18 * abs(math.log(aspect_ratio)) + 0.22 * (1 - edge_cos) + 0.10 * crop_mse
    zoom_factor = math.sqrt(max(rf["area_fraction"], 1e-6) / max(cf["area_fraction"], 1e-6))
    suggestions = {
        "pan_image_delta": [-center_delta[0], -center_delta[1]],
        "zoom_factor_hint": zoom_factor,
        "too_small": area_ratio < 0.92,
        "too_large": area_ratio > 1.08,
        "capture_too_wide": aspect_ratio > 1.08,
        "capture_too_narrow": aspect_ratio < 0.92,
        "edge_similarity": edge_cos,
    }
    return {
        "score": score,
        "components": {
            "center_score": center_score,
            "area_ratio": area_ratio,
            "aspect_ratio": aspect_ratio,
            "edge_cosine": edge_cos,
            "crop_mse": crop_mse,
        },
        "reference": {k: v for k, v in rf.items() if k != "mask"},
        "capture": {k: v for k, v in cf.items() if k != "mask"},
        "suggestions": suggestions,
        "_masks": {"reference": rf["mask"], "capture": cf["mask"]},
    }


def save_debug(debug_dir: Path, reference: Image.Image, capture: Image.Image, report: dict) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray((report["_masks"]["reference"] * 255).astype(np.uint8)).save(debug_dir / "reference_mask.png")
    Image.fromarray((report["_masks"]["capture"] * 255).astype(np.uint8)).save(debug_dir / "capture_mask.png")
    for name, image, feat in (("reference_box.png", reference, report["reference"]), ("capture_box.png", capture, report["capture"])):
        boxed = image.copy()
        draw = ImageDraw.Draw(boxed)
        draw.rectangle(feat["bbox"], outline=(255, 0, 0), width=3)
        boxed.save(debug_dir / name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--output-json")
    parser.add_argument("--debug-dir")
    parser.add_argument("--reference-crop", type=parse_crop)
    parser.add_argument("--capture-crop", type=parse_crop)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reference = load_rgb(Path(args.reference), args.reference_crop)
    capture = load_rgb(Path(args.capture), args.capture_crop)
    report = compare(reference, capture)
    masks = report.pop("_masks")
    if args.debug_dir:
        report["_masks"] = masks
        save_debug(Path(args.debug_dir), reference, capture, report)
        report.pop("_masks")
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
