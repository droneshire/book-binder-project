import io

import fitz
from PIL import Image


def pts_to_px(pts: float, dpi: int) -> int:
    return max(1, round((pts * dpi) / 72.0))


def inches_to_pts(inches: float) -> float:
    return inches * 72.0


def safe_slice_bounds(start: float, end: float, limit: int) -> tuple[int, int]:
    s = max(0, min(limit, round(start)))
    e = max(0, min(limit, round(end)))
    if e <= s:
        e = min(limit, s + 1)
    return s, e


def slice_vertical(img: Image.Image, page_idx: int, total_pages: int) -> Image.Image:
    h = img.height
    y0, y1 = safe_slice_bounds((page_idx / total_pages) * h, ((page_idx + 1) / total_pages) * h, h)
    return img.crop((0, y0, img.width, y1))


def slice_horizontal(img: Image.Image, page_idx: int, total_pages: int) -> Image.Image:
    w = img.width
    x0, x1 = safe_slice_bounds((page_idx / total_pages) * w, ((page_idx + 1) / total_pages) * w, w)
    return img.crop((x0, 0, x1, img.height))


def apply_opacity(img: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return img
    rgba = img.copy()
    alpha = rgba.getchannel("A")
    alpha = alpha.point(lambda a: int(a * opacity))
    rgba.putalpha(alpha)
    return rgba


def pil_from_pixmap(pix: fitz.Pixmap) -> Image.Image:
    mode = "RGBA" if pix.alpha else "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def to_rgba(uploaded_file) -> Image.Image:
    return Image.open(io.BytesIO(uploaded_file.getvalue())).convert("RGBA")


def effective_side(base_side: str, mirror_even: bool, page_idx_zero_based: int) -> str:
    if base_side == "both":
        return "both"
    if not mirror_even:
        return base_side
    is_even_page_number = ((page_idx_zero_based + 1) % 2) == 0
    if not is_even_page_number:
        return base_side
    return "left" if base_side == "right" else "right"
