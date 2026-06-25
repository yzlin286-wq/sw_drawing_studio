from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def validate_application_ui_screenshot(path: Path | str) -> dict[str, Any]:
    image_path = Path(path)
    result: dict[str, Any] = {
        "path": str(image_path),
        "pass": False,
        "exists": image_path.exists() and image_path.is_file(),
        "width": 0,
        "height": 0,
        "reasons": [],
    }
    if not result["exists"]:
        result["reasons"].append("screenshot_file_missing")
        return result
    if image_path.stat().st_size <= 0:
        result["reasons"].append("screenshot_file_empty")
        return result

    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as exc:
        result["reasons"].append(f"screenshot_decode_failed:{exc}")
        return result

    width, height = image.size
    result["width"] = int(width)
    result["height"] = int(height)
    gray = _gray_array(image)
    aspect = width / max(1, height)
    min_size_pass = width >= 1200 and height >= 700
    aspect_pass = 1.25 <= aspect <= 2.4
    top_chrome_pass = _nonwhite_ratio(gray[: max(24, int(height * 0.08)), :]) >= 0.08
    left_nav_pass = _nonwhite_ratio(gray[:, : max(80, int(width * 0.08))]) >= 0.04
    bottom_log_pass = _nonwhite_ratio(gray[int(height * 0.78) :, :]) >= 0.015
    side_by_side_pass = _side_by_side_review_region_pass(gray)

    checks = {
        "min_size_pass": min_size_pass,
        "aspect_pass": aspect_pass,
        "top_chrome_pass": top_chrome_pass,
        "left_nav_pass": left_nav_pass,
        "bottom_log_pass": bottom_log_pass,
        "side_by_side_review_region_pass": side_by_side_pass,
    }
    result["checks"] = checks
    for key, passed in checks.items():
        if not passed:
            result["reasons"].append(key)
    result["pass"] = all(checks.values())
    return result


def validate_application_ui_screenshots(paths: list[Path | str]) -> dict[str, Any]:
    checks = [validate_application_ui_screenshot(path) for path in paths]
    passing = [item["path"] for item in checks if item.get("pass")]
    return {
        "pass": bool(passing),
        "passing_paths": passing,
        "checks": checks,
    }


def _gray_array(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image).astype(np.float32)
    return (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]).astype(np.uint8)


def _nonwhite_ratio(region: np.ndarray) -> float:
    if region.size <= 0:
        return 0.0
    return float((region < 248).sum()) / float(region.size)


def _bright_ratio(region: np.ndarray) -> float:
    if region.size <= 0:
        return 0.0
    return float((region > 238).sum()) / float(region.size)


def _side_by_side_review_region_pass(gray: np.ndarray) -> bool:
    height, width = gray.shape
    y1 = int(height * 0.18)
    y2 = int(height * 0.72)
    left = gray[y1:y2, int(width * 0.28) : int(width * 0.50)]
    right = gray[y1:y2, int(width * 0.53) : int(width * 0.75)]
    divider = gray[y1:y2, int(width * 0.50) : int(width * 0.53)]
    return (
        _bright_ratio(left) >= 0.68
        and _bright_ratio(right) >= 0.68
        and _nonwhite_ratio(left) >= 0.002
        and _nonwhite_ratio(right) >= 0.002
        and _nonwhite_ratio(divider) >= 0.01
    )
