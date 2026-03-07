import fitz

from book_page_edges.core.pdf_factory import add_bleed_to_manuscript, create_blank_pdf


def test_create_blank_pdf_dimensions_and_page_count() -> None:
    pdf_bytes = create_blank_pdf(
        page_count=12, trim_width_in=5.0, trim_height_in=8.0)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        assert len(doc) == 12
        first = doc[0].rect
        assert round(first.width, 3) == 360.0
        assert round(first.height, 3) == 576.0


def test_add_bleed_to_manuscript() -> None:
    # 6 x 9 in trim -> with 0.125 in bleed: 6.125 x 9.25 in (per KDP)
    pdf_bytes = create_blank_pdf(
        page_count=2, trim_width_in=6.0, trim_height_in=9.0
    )
    out_bytes = add_bleed_to_manuscript(pdf_bytes, bleed_in=0.125)
    with fitz.open(stream=out_bytes, filetype="pdf") as doc:
        assert len(doc) == 2
        first = doc[0]
        w_pts = first.rect.width
        h_pts = first.rect.height
        # 6.125 * 72 = 441, 9.25 * 72 = 666
        assert round(w_pts, 2) == 441.0
        assert round(h_pts, 2) == 666.0
