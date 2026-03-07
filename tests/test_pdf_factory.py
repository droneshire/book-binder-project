import fitz

from book_page_edges.core.pdf_factory import (
    add_bleed_to_manuscript,
    create_blank_pdf,
    normalize_trim_sizes,
)


def test_create_blank_pdf_dimensions_and_page_count() -> None:
    pdf_bytes = create_blank_pdf(
        page_count=12, trim_width_in=5.0, trim_height_in=8.0)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        assert len(doc) == 12
        first = doc[0].rect
        assert round(first.width, 3) == 360.0
        assert round(first.height, 3) == 576.0


def test_normalize_trim_sizes_standardizes_pages() -> None:
    """Pages with different trim sizes are scaled to match the first page."""
    page1 = create_blank_pdf(page_count=1, trim_width_in=6.0, trim_height_in=9.0)
    page2 = create_blank_pdf(page_count=1, trim_width_in=5.0, trim_height_in=8.0)

    # Build a mixed-size PDF by concatenating the two docs.
    doc1 = fitz.open(stream=page1, filetype="pdf")
    doc2 = fitz.open(stream=page2, filetype="pdf")
    doc1.insert_pdf(doc2)
    mixed_bytes = doc1.tobytes(garbage=4, deflate=True)
    doc1.close()
    doc2.close()

    out_bytes = normalize_trim_sizes(mixed_bytes)
    with fitz.open(stream=out_bytes, filetype="pdf") as doc:
        assert len(doc) == 2
        w0, h0 = round(doc[0].rect.width, 2), round(doc[0].rect.height, 2)
        w1, h1 = round(doc[1].rect.width, 2), round(doc[1].rect.height, 2)
        # Both pages should now match the first page's 6×9 in trim dimensions.
        assert w0 == 432.0  # 6.0 * 72
        assert h0 == 648.0  # 9.0 * 72
        assert w1 == w0
        assert h1 == h0


def test_normalize_trim_sizes_uniform_pdf_unchanged_dimensions() -> None:
    """A PDF where all pages already share the same trim size passes through unchanged."""
    pdf_bytes = create_blank_pdf(page_count=3, trim_width_in=6.0, trim_height_in=9.0)
    out_bytes = normalize_trim_sizes(pdf_bytes)
    with fitz.open(stream=out_bytes, filetype="pdf") as doc:
        assert len(doc) == 3
        for page in doc:
            assert round(page.rect.width, 2) == 432.0
            assert round(page.rect.height, 2) == 648.0


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
