from typing import Iterable

import fitz

from book_page_edges.core.image_ops import pts_to_px
from book_page_edges.core.models import PageMetrics, PdfAnalysis


def collect_page_metrics(doc: fitz.Document, dpi: int) -> list[PageMetrics]:
    metrics: list[PageMetrics] = []
    scale = dpi / 72.0
    for idx, page in enumerate(doc):
        rect = page.rect
        metrics.append(
            PageMetrics(
                index=idx,
                width_pts=rect.width,
                height_pts=rect.height,
                width_px=max(1, round(rect.width * scale)),
                height_px=max(1, round(rect.height * scale)),
            )
        )
    return metrics


def analyze_pdf(doc: fitz.Document, dpi: int) -> tuple[PdfAnalysis, list[PageMetrics]]:
    metrics = collect_page_metrics(doc, dpi)
    if not metrics:
        raise ValueError("PDF has no pages")

    first_page = doc[0]
    trim = first_page.trimbox
    media = first_page.mediabox

    mixed_trim = False
    first_trim_size = (round(trim.width, 4), round(trim.height, 4))
    for p in doc:
        t = p.trimbox
        if (round(t.width, 4), round(t.height, 4)) != first_trim_size:
            mixed_trim = True
            break

    analysis = PdfAnalysis(
        page_count=len(doc),
        first_trim_w_pts=trim.width,
        first_trim_h_pts=trim.height,
        first_media_w_pts=media.width,
        first_media_h_pts=media.height,
        has_bleed_on_first_page=(media.width > trim.width or media.height > trim.height),
        mixed_trim_sizes=mixed_trim,
    )
    return analysis, metrics


def expected_edge_dimensions(
    metrics: Iterable[PageMetrics],
    page_count: int,
    edge_width_pts: float,
    dpi: int,
) -> dict[str, int]:
    metrics = list(metrics)
    first = metrics[0]
    strip_px = pts_to_px(edge_width_pts, dpi)

    fore_w = strip_px
    fore_h = first.height_px * page_count
    top_w = first.width_px * page_count
    top_h = strip_px

    return {
        "strip_px": strip_px,
        "fore_w": fore_w,
        "fore_h": fore_h,
        "top_w": top_w,
        "top_h": top_h,
    }
