import io

import fitz
from PIL import Image

from book_page_edges.core.image_ops import (
    apply_opacity,
    effective_side,
    pil_from_pixmap,
    pts_to_px,
    slice_horizontal,
    slice_vertical,
)


def generate_output_pdf(
    pdf_bytes: bytes,
    fore_img: Image.Image | None,
    top_img: Image.Image | None,
    bottom_img: Image.Image | None,
    dpi: int,
    edge_width_pts: float,
    side: str,
    mirror_even: bool,
    fore_opacity: float,
    jpeg_quality: int,
    add_bleed: bool,
    bleed_pts: float,
    apply_edges_in_bleed_only: bool,
    progress_callback,
) -> bytes:
    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    out = fitz.open()

    total_pages = len(src)
    strip_px = pts_to_px(edge_width_pts, dpi)
    bleed_px = pts_to_px(bleed_pts, dpi) if add_bleed else 0
    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)

    if add_bleed and apply_edges_in_bleed_only:
        strip_px = min(strip_px, bleed_px)

    metadata = src.metadata
    if metadata:
        out.set_metadata(metadata)

    for i, page in enumerate(src):
        rect = page.rect
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        base_canvas = pil_from_pixmap(pix).convert("RGBA")

        if add_bleed:
            canvas = Image.new(
                "RGBA",
                (base_canvas.width + 2 * bleed_px, base_canvas.height + 2 * bleed_px),
                (255, 255, 255, 255),
            )
            canvas.paste(base_canvas, (bleed_px, bleed_px))
            content_x0 = bleed_px
            content_y0 = bleed_px
            content_x1 = bleed_px + base_canvas.width
            content_y1 = bleed_px + base_canvas.height
        else:
            canvas = base_canvas
            content_x0 = 0
            content_y0 = 0
            content_x1 = base_canvas.width
            content_y1 = base_canvas.height

        if fore_img is not None:
            sl = slice_vertical(fore_img, i, total_pages).resize(
                (strip_px, canvas.height), Image.Resampling.LANCZOS
            )
            sl = apply_opacity(sl, fore_opacity)
            side_now = effective_side(side, mirror_even, i)

            right_x = canvas.width - strip_px
            left_x = 0
            if add_bleed and apply_edges_in_bleed_only:
                right_x = content_x1
                left_x = content_x0 - strip_px

            if side_now in {"right", "both"}:
                canvas.paste(sl, (right_x, 0), sl)
            if side_now in {"left", "both"}:
                left_sl = sl.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                canvas.paste(left_sl, (left_x, 0), left_sl)

        if top_img is not None:
            sl_top = slice_horizontal(top_img, i, total_pages).resize(
                (canvas.width, strip_px), Image.Resampling.LANCZOS
            )
            sl_top = apply_opacity(sl_top, fore_opacity)
            top_y = 0
            if add_bleed and apply_edges_in_bleed_only:
                top_y = content_y0 - strip_px
            canvas.paste(sl_top, (0, top_y), sl_top)

        if bottom_img is not None:
            sl_bottom = slice_horizontal(bottom_img, i, total_pages).resize(
                (canvas.width, strip_px), Image.Resampling.LANCZOS
            )
            sl_bottom = apply_opacity(sl_bottom, fore_opacity)
            bottom_y = canvas.height - strip_px
            if add_bleed and apply_edges_in_bleed_only:
                bottom_y = content_y1
            canvas.paste(sl_bottom, (0, bottom_y), sl_bottom)

        rgb = canvas.convert("RGB")
        jpg = io.BytesIO()
        rgb.save(jpg, format="JPEG", quality=jpeg_quality, optimize=True)

        page_w_pts = rect.width + (2 * bleed_pts if add_bleed else 0)
        page_h_pts = rect.height + (2 * bleed_pts if add_bleed else 0)
        out_page = out.new_page(width=page_w_pts, height=page_h_pts)
        out_page.insert_image(out_page.rect, stream=jpg.getvalue())

        progress_callback(i + 1, total_pages)

    output_bytes = out.tobytes(garbage=4, deflate=True)
    src.close()
    out.close()
    return output_bytes
