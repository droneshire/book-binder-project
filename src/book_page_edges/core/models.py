from dataclasses import dataclass


@dataclass
class PageMetrics:
    index: int
    width_pts: float
    height_pts: float
    width_px: int
    height_px: int


@dataclass
class PdfAnalysis:
    page_count: int
    first_trim_w_pts: float
    first_trim_h_pts: float
    first_media_w_pts: float
    first_media_h_pts: float
    has_bleed_on_first_page: bool
    mixed_trim_sizes: bool
