"""Static configuration values and presets for the app."""

from __future__ import annotations

PTS_PER_INCH = 72.0
DEFAULT_DPI = 300
DEFAULT_FORE_OPACITY = 1.0
DEFAULT_JPEG_QUALITY = 92

# KDP 6" x 9" trim and bleed (per KDP Set Trim Size, Bleed, and Margins)
KDP_BLEED_IN = 0.125
# Default edge width = preset bleed so it stays within trim-safe zone (no clamp/warning)
DEFAULT_EDGE_WIDTH_PTS = KDP_BLEED_IN * PTS_PER_INCH
KDP_TRIM_WIDTH_IN = 6.0
KDP_TRIM_HEIGHT_IN = 9.0
KDP_PAGE_WITH_BLEED_WIDTH_IN = KDP_TRIM_WIDTH_IN + KDP_BLEED_IN
KDP_PAGE_WITH_BLEED_HEIGHT_IN = KDP_TRIM_HEIGHT_IN + 2 * KDP_BLEED_IN

# Printer presets: safe area (inches); bleed uses KDP_BLEED_IN
CUSTOM_SAFE_AREA_IN = 0.375
KDP_SAFE_AREA_IN = 0.375
INGRAMSPARK_SAFE_AREA_IN = 0.5
LULU_SAFE_AREA_IN = 0.25

PRINTER_PRESETS: dict[str, dict[str, float]] = {
    "custom": {"bleed_in": KDP_BLEED_IN, "safe_area_in": CUSTOM_SAFE_AREA_IN},
    "kdp": {"bleed_in": KDP_BLEED_IN, "safe_area_in": KDP_SAFE_AREA_IN},
    "ingramspark": {"bleed_in": KDP_BLEED_IN, "safe_area_in": INGRAMSPARK_SAFE_AREA_IN},
    "lulu": {"bleed_in": KDP_BLEED_IN, "safe_area_in": LULU_SAFE_AREA_IN},
}

PAPER_TYPES_INCH_PER_PAGE: dict[str, float] = {
    "standard": 0.004,
    "thick": 0.006,
    "thin": 0.003,
    "cardstock": 0.010,
}
