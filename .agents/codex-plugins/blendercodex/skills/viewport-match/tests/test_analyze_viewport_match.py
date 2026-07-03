from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_viewport_match.py"


def test_analyze_reports_score_for_shifted_rectangles(tmp_path: Path) -> None:
    ref = tmp_path / "ref.png"
    cap = tmp_path / "cap.png"
    for path, box in ((ref, (70, 45, 210, 180)), (cap, (86, 55, 226, 190))):
        image = Image.new("RGB", (280, 220), (24, 24, 24))
        draw = ImageDraw.Draw(image)
        draw.rectangle(box, fill=(190, 188, 170))
        draw.rectangle((box[0] + 18, box[1] + 18, box[2] - 18, box[1] + 54), fill=(30, 40, 42))
        image.save(path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--reference", str(ref), "--capture", str(cap)],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    assert data["score"] >= 0
    assert "pan_image_delta" in data["suggestions"]


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as raw:
        test_analyze_reports_score_for_shifted_rectangles(Path(raw))
    print("ok")
