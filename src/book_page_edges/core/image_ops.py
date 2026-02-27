"""Image and geometry utility functions for page-edge processing."""

from __future__ import annotations

import io
from typing import Any

import fitz
from PIL import Image


def pts_to_px(pts: float, dpi: int) -> int:
    """Convert points to pixels at the provided DPI."""

    return max(1, round((pts * dpi) / 72.0))


def inches_to_pts(inches: float) -> float:
    """Convert inches to points."""

    return inches * 72.0


def safe_slice_bounds(start: float, end: float, limit: int) -> tuple[int, int]:
    """Clamp and normalize slice bounds to a non-empty interval."""

    slice_start = max(0, min(limit, round(start)))
    slice_end = max(0, min(limit, round(end)))
    if slice_end <= slice_start:
        slice_end = min(limit, slice_start + 1)
    return slice_start, slice_end


def slice_vertical(img: Image.Image, page_idx: int, total_pages: int) -> Image.Image:
    """Slice a vertical edge image for the given page index."""

    height = img.height
    y0, y1 = safe_slice_bounds(
        (page_idx / total_pages) * height,
        ((page_idx + 1) / total_pages) * height,
        height,
    )
    return img.crop((0, y0, img.width, y1))


def slice_horizontal(img: Image.Image, page_idx: int, total_pages: int) -> Image.Image:
    """Slice a horizontal edge image for the given page index."""

    width = img.width
    x0, x1 = safe_slice_bounds(
        (page_idx / total_pages) * width,
        ((page_idx + 1) / total_pages) * width,
        width,
    )
    return img.crop((x0, 0, x1, img.height))


def apply_opacity(img: Image.Image, opacity: float) -> Image.Image:
    """Apply opacity to an RGBA image by scaling alpha channel values."""

    if opacity >= 0.999:
        return img
    rgba = img.copy()
    alpha = rgba.getchannel("A")
    alpha = alpha.point(lambda a: int(a * opacity))
    rgba.putalpha(alpha)
    return rgba


def pil_from_pixmap(pix: fitz.Pixmap) -> Image.Image:
    """Convert a PyMuPDF pixmap to a PIL image."""

    mode = "RGBA" if pix.alpha else "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def to_rgba(uploaded_file: Any) -> Image.Image:
    """Read an uploaded image-like object into RGBA mode."""

    return Image.open(io.BytesIO(uploaded_file.getvalue())).convert("RGBA")


def effective_side(
    base_side: str, mirror_even: bool, binding: str, page_idx_zero_based: int
) -> str:
    """Return effective fore-edge side, honoring duplex and binding direction."""

    if base_side == "both":
        return "both"

    # If mirroring is disabled, respect the explicit side selection.
    if not mirror_even:
        return base_side

    # Duplex-aware mapping: ensure artwork lands on the outer edge given binding.
    is_even_page_number = ((page_idx_zero_based + 1) % 2) == 0
    if binding.lower() == "rtl":
        # Binding on the right; outer edge is left on odd pages, right on even.
        return "left" if not is_even_page_number else "right"

    # Default / LTR: binding on the left; outer edge is right on odd, left on even.
    return "right" if not is_even_page_number else "left"
