"""Validation helpers for user-provided edge images."""

from __future__ import annotations

import io
from typing import Any

from PIL import Image

# When "ideal" is this large, don't show raw pixel count (e.g. fore_h = page_h × pages)
_LARGE_DIMENSION = 50_000


def validate_uploaded_image(
    uploaded_file: Any,
    label: str,
    expected_width: int,
    expected_height: int,
) -> tuple[list[str], Image.Image]:
    """Validate image dimensions and embedded DPI metadata."""

    warnings: list[str] = []
    raw = Image.open(io.BytesIO(uploaded_file.getvalue()))
    actual_w, actual_h = raw.size

    if (actual_w, actual_h) != (expected_width, expected_height):
        if expected_height > _LARGE_DIMENSION or expected_width > _LARGE_DIMENSION:
            # "Ideal" is strip × (page_dim × page_count)—huge; don't imply user needs that
            if expected_height > _LARGE_DIMENSION:
                warnings.append(
                    f"{label}: size is {actual_w}×{actual_h}. Recommended width ≈ {expected_width} px (strip). "
                    "Height is flexible—sliced one segment per page; your image will be scaled. Advisory only."
                )
            else:
                warnings.append(
                    f"{label}: size is {actual_w}×{actual_h}. Recommended height ≈ {expected_height} px (strip). "
                    "Width is flexible—sliced one segment per page; your image will be scaled. Advisory only."
                )
        else:
            pct_w = (
                ((actual_w / expected_width) - 1.0) * 100.0 if expected_width else 0.0
            )
            pct_h = (
                ((actual_h / expected_height) - 1.0) * 100.0 if expected_height else 0.0
            )
            warnings.append(
                f"{label}: size is {actual_w}×{actual_h}. For a 1:1, non-repeating mapping "
                f"the ideal size would be ~{expected_width}×{expected_height} "
                f"({pct_w:+.1f}% width, {pct_h:+.1f}% height). "
                "Your image will still be auto-scaled and sliced; this is an advisory note only."
            )

    dpi_info = raw.info.get("dpi")
    if isinstance(dpi_info, tuple) and dpi_info:
        try:
            image_dpi = float(dpi_info[0])
        except (TypeError, ValueError):
            image_dpi = 0.0
        if image_dpi and image_dpi < 300:
            warnings.append(
                f"{label}: embedded DPI is {image_dpi:.0f}; 300+ is recommended."
            )

    return warnings, raw.convert("RGBA")
