"""Utilities to construct synthetic/blank interior PDFs and add bleed."""

from __future__ import annotations

import fitz

from book_page_edges.core.config import KDP_BLEED_IN
from book_page_edges.core.image_ops import inches_to_pts


def add_bleed_to_manuscript(pdf_bytes: bytes, bleed_in: float = KDP_BLEED_IN) -> bytes:
    """Expand each page by the given bleed so content can extend to the trim edge.

    Per KDP specs: page width with bleed = trim width + 0.125 in,
    page height with bleed = trim height + 0.25 in (0.125 in top and bottom).
    """
    bleed_pts = inches_to_pts(bleed_in)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out = fitz.open()
    for page in doc:
        trim = page.trimbox
        new_width_pts = trim.width + bleed_pts
        new_height_pts = trim.height + 2 * bleed_pts
        out_page = out.new_page(width=new_width_pts, height=new_height_pts)
        # Draw original page at (0,0) so trim area is filled; right and bottom get bleed
        src_rect = fitz.Rect(0, 0, trim.width, trim.height)
        out_page.show_pdf_page(src_rect, doc, page.number)
    data = out.tobytes(garbage=4, deflate=True)
    doc.close()
    out.close()
    return data


def create_blank_pdf(
    page_count: int,
    trim_width_in: float,
    trim_height_in: float,
) -> bytes:
    """Create a blank PDF with the given page count and trim dimensions."""

    if page_count < 1:
        raise ValueError("page_count must be >= 1")
    if trim_width_in <= 0 or trim_height_in <= 0:
        raise ValueError("trim dimensions must be > 0")

    width_pts = inches_to_pts(trim_width_in)
    height_pts = inches_to_pts(trim_height_in)

    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page(width=width_pts, height=height_pts)

    data = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return data
