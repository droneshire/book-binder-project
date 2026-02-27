"""Typed data models used by analysis and UI layers."""
# pylint: disable=duplicate-code

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PageMetrics:
    """Per-page dimensions represented in points and raster pixels."""

    index: int
    width_pts: float
    height_pts: float
    width_px: int
    height_px: int


@dataclass
class PdfAnalysis:
    """Summary of PDF geometry properties used by the app."""

    page_count: int
    first_trim_w_pts: float
    first_trim_h_pts: float
    first_media_w_pts: float
    first_media_h_pts: float
    has_bleed_on_first_page: bool
    mixed_trim_sizes: bool


@dataclass
class EdgeConfig:
    """Per-edge configuration matching the PRD schema."""

    enabled: bool
    zone_in: float


@dataclass
class MultiEdgeConfig:  # pylint: disable=too-many-instance-attributes
    """High-level configuration model for multi-edge placement."""

    fore: EdgeConfig
    top: EdgeConfig
    bottom: EdgeConfig
    bleed_in: float
    safe_margin_in: float
    trim_width_in: float
    trim_height_in: float
    binding: str
