"""Static configuration values and presets for the app."""

from __future__ import annotations

DEFAULT_DPI = 300
DEFAULT_EDGE_WIDTH_PTS = 36.0
DEFAULT_FORE_OPACITY = 1.0
DEFAULT_JPEG_QUALITY = 92

PRINTER_PRESETS: dict[str, dict[str, float]] = {
    "custom": {"bleed_in": 0.125, "safe_area_in": 0.375},
    "kdp": {"bleed_in": 0.125, "safe_area_in": 0.375},
    "ingramspark": {"bleed_in": 0.125, "safe_area_in": 0.5},
    "lulu": {"bleed_in": 0.125, "safe_area_in": 0.25},
}

PAPER_TYPES_INCH_PER_PAGE: dict[str, float] = {
    "standard": 0.004,
    "thick": 0.006,
    "thin": 0.003,
    "cardstock": 0.010,
}
