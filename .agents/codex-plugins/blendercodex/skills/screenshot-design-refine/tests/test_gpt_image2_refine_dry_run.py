from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gpt_image2_refine.py"


def test_dry_run_builds_request_without_api_key(tmp_path: Path) -> None:
    image = tmp_path / "shot.png"
    Image.new("RGB", (320, 200), (80, 80, 80)).save(image)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--image",
            str(image),
            "--user-request",
            "make the building more readable as a modular town asset",
            "--output",
            str(tmp_path / "out.png"),
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert data["request"]["model"] == "gpt-image-2"
    assert data["request"]["size"] == "1024x640"
    assert data["request"]["input_fidelity"] is None
    assert "modular town asset" in data["request"]["prompt"]


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as raw:
        test_dry_run_builds_request_without_api_key(Path(raw))
    print("ok")
