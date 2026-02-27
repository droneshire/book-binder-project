from PIL import Image

from book_page_edges.core.analysis import expected_edge_dimensions
from book_page_edges.core.image_ops import (
    effective_side,
    pts_to_px,
    safe_slice_bounds,
    slice_horizontal,
    slice_vertical,
)
from book_page_edges.core.models import PageMetrics


def test_pts_to_px_conversion() -> None:
    assert pts_to_px(36.0, 300) == 150


def test_safe_slice_bounds_no_overlap_for_simple_case() -> None:
    assert safe_slice_bounds(0.0, 100.0, 1000) == (0, 100)
    assert safe_slice_bounds(900.0, 1000.0, 1000) == (900, 1000)


def test_slice_vertical_covers_expected_region() -> None:
    img = Image.new("RGBA", (10, 1000), (255, 0, 0, 255))
    sl0 = slice_vertical(img, 0, 10)
    sl9 = slice_vertical(img, 9, 10)
    assert sl0.size == (10, 100)
    assert sl9.size == (10, 100)


def test_slice_horizontal_covers_expected_region() -> None:
    img = Image.new("RGBA", (1000, 10), (255, 0, 0, 255))
    sl0 = slice_horizontal(img, 0, 10)
    sl9 = slice_horizontal(img, 9, 10)
    assert sl0.size == (100, 10)
    assert sl9.size == (100, 10)


def test_effective_side_with_even_mirroring_ltr() -> None:
    assert effective_side(
        "right",
        mirror_even=True,
        binding="ltr",
        page_idx_zero_based=0,
    ) == "right"
    assert effective_side(
        "right",
        mirror_even=True,
        binding="ltr",
        page_idx_zero_based=1,
    ) == "left"
    assert effective_side(
        "left",
        mirror_even=True,
        binding="ltr",
        page_idx_zero_based=1,
    ) == "left"


def test_effective_side_with_even_mirroring_rtl() -> None:
    assert effective_side(
        "right",
        mirror_even=True,
        binding="rtl",
        page_idx_zero_based=0,
    ) == "left"
    assert effective_side(
        "right",
        mirror_even=True,
        binding="rtl",
        page_idx_zero_based=1,
    ) == "right"


def test_expected_dimensions() -> None:
    metrics = [
        PageMetrics(index=0, width_pts=360.0, height_pts=576.0,
                    width_px=1500, height_px=2400),
    ]
    dims = expected_edge_dimensions(
        metrics=metrics, page_count=300, edge_width_pts=36.0, dpi=300)
    assert dims["strip_px"] == 150
    assert dims["fore_w"] == 150
    assert dims["fore_h"] == 2400 * 300
    assert dims["top_w"] == 1500 * 300
    assert dims["top_h"] == 150
