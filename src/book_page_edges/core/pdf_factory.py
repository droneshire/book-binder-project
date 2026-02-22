import fitz

from book_page_edges.core.image_ops import inches_to_pts


def create_blank_pdf(
    page_count: int, trim_width_in: float, trim_height_in: float
) -> bytes:
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
