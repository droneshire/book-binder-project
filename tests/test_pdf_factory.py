import fitz

from book_page_edges.core.pdf_factory import create_blank_pdf


def test_create_blank_pdf_dimensions_and_page_count() -> None:
    pdf_bytes = create_blank_pdf(page_count=12, trim_width_in=5.0, trim_height_in=8.0)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        assert len(doc) == 12
        first = doc[0].rect
        assert round(first.width, 3) == 360.0
        assert round(first.height, 3) == 576.0
