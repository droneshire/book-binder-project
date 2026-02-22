"""PDF compositing pipeline for applying edge artwork."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Callable

import fitz
from PIL import Image

from book_page_edges.core.image_ops import (
    apply_opacity,
    effective_side,
    pil_from_pixmap,
    pts_to_px,
    slice_horizontal,
    slice_vertical,
)


@dataclass(frozen=True)
class PlacementOptions:
    """Placement configuration for composited edge strips."""

    side: str
    mirror_even: bool
    add_bleed: bool
    bleed_pts: float
    apply_edges_in_bleed_only: bool


@dataclass(frozen=True)
class RenderOptions:
    """Rasterization and encoding settings for output generation."""

    dpi: int
    edge_width_pts: float
    fore_opacity: float
    jpeg_quality: int
    placement: PlacementOptions


@dataclass(frozen=True)
class EdgeImageSet:
    """Container for optional edge images."""

    fore: Image.Image | None
    top: Image.Image | None
    bottom: Image.Image | None


@dataclass(frozen=True)
class CanvasGeometry:
    """Coordinates describing live content bounds inside a canvas."""

    content_x0: int
    content_y0: int
    content_x1: int
    content_y1: int


@dataclass(frozen=True)
class ComposeState:
    """Shared state used to compose each output page."""

    options: RenderOptions
    total_pages: int
    strip_px: int


@dataclass(frozen=True)
class PageComposeRequest:
    """Page-specific inputs for rendering one output page."""

    page: fitz.Page
    page_idx: int
    edge_images: EdgeImageSet
    matrix: fitz.Matrix
    bleed_px: int


@dataclass(frozen=True)
class RenderContext:
    """Page-local canvas context for edge placement operations."""

    page_idx: int
    canvas: Image.Image
    geometry: CanvasGeometry


@dataclass(frozen=True)
class GenerationContext:
    """Document-level context used while iterating rendered pages."""

    src: fitz.Document
    out: fitz.Document
    matrix: fitz.Matrix
    bleed_px: int
    progress_callback: Callable[[int, int], None]


ProgressCallback = Callable[[int, int], None]


def _effective_strip_px(options: RenderOptions) -> int:
    strip_px = pts_to_px(options.edge_width_pts, options.dpi)
    if options.placement.add_bleed and options.placement.apply_edges_in_bleed_only:
        bleed_px = pts_to_px(options.placement.bleed_pts, options.dpi)
        return min(strip_px, bleed_px)
    return strip_px


def _make_canvas(
    base_canvas: Image.Image,
    add_bleed: bool,
    bleed_px: int,
) -> tuple[Image.Image, CanvasGeometry]:
    if not add_bleed:
        geometry = CanvasGeometry(0, 0, base_canvas.width, base_canvas.height)
        return base_canvas, geometry

    canvas = Image.new(
        "RGBA",
        (base_canvas.width + 2 * bleed_px, base_canvas.height + 2 * bleed_px),
        (255, 255, 255, 255),
    )
    canvas.paste(base_canvas, (bleed_px, bleed_px))
    geometry = CanvasGeometry(
        content_x0=bleed_px,
        content_y0=bleed_px,
        content_x1=bleed_px + base_canvas.width,
        content_y1=bleed_px + base_canvas.height,
    )
    return canvas, geometry


def _paste_fore(
    canvas: Image.Image,
    geometry: CanvasGeometry,
    page_idx: int,
    fore_img: Image.Image,
    state: ComposeState,
) -> None:
    slice_img = slice_vertical(fore_img, page_idx, state.total_pages).resize(
        (state.strip_px, canvas.height),
        Image.Resampling.LANCZOS,
    )
    slice_img = apply_opacity(slice_img, state.options.fore_opacity)

    side_now = effective_side(
        state.options.placement.side,
        state.options.placement.mirror_even,
        page_idx,
    )

    right_x = canvas.width - state.strip_px
    left_x = 0
    if (
        state.options.placement.add_bleed
        and state.options.placement.apply_edges_in_bleed_only
    ):
        right_x = geometry.content_x1
        left_x = geometry.content_x0 - state.strip_px

    if side_now in {"right", "both"}:
        canvas.paste(slice_img, (right_x, 0), slice_img)
    if side_now in {"left", "both"}:
        left_slice = slice_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        canvas.paste(left_slice, (left_x, 0), left_slice)


def _paste_horizontal(
    context: RenderContext,
    edge_img: Image.Image,
    state: ComposeState,
    is_top: bool,
) -> None:
    slice_img = slice_horizontal(edge_img, context.page_idx, state.total_pages).resize(
        (context.canvas.width, state.strip_px),
        Image.Resampling.LANCZOS,
    )
    slice_img = apply_opacity(slice_img, state.options.fore_opacity)

    if is_top:
        y_pos = 0
        if (
            state.options.placement.add_bleed
            and state.options.placement.apply_edges_in_bleed_only
        ):
            y_pos = context.geometry.content_y0 - state.strip_px
    else:
        y_pos = context.canvas.height - state.strip_px
        if (
            state.options.placement.add_bleed
            and state.options.placement.apply_edges_in_bleed_only
        ):
            y_pos = context.geometry.content_y1

    context.canvas.paste(slice_img, (0, y_pos), slice_img)


def _encode_canvas_to_jpeg(canvas: Image.Image, jpeg_quality: int) -> bytes:
    rgb = canvas.convert("RGB")
    jpg = io.BytesIO()
    rgb.save(jpg, format="JPEG", quality=jpeg_quality, optimize=True)
    return jpg.getvalue()


def _page_dimensions(page: fitz.Page, options: RenderOptions) -> tuple[float, float]:
    rect = page.rect
    if not options.placement.add_bleed:
        return rect.width, rect.height

    bleed = 2 * options.placement.bleed_pts
    return rect.width + bleed, rect.height + bleed


def _compose_page(
    request: PageComposeRequest,
    state: ComposeState,
) -> tuple[bytes, float, float]:
    pix = request.page.get_pixmap(matrix=request.matrix, alpha=False)
    base_canvas = pil_from_pixmap(pix).convert("RGBA")
    canvas, geometry = _make_canvas(
        base_canvas,
        state.options.placement.add_bleed,
        request.bleed_px,
    )

    if request.edge_images.fore is not None:
        _paste_fore(canvas, geometry, request.page_idx, request.edge_images.fore, state)
    context = RenderContext(page_idx=request.page_idx, canvas=canvas, geometry=geometry)
    if request.edge_images.top is not None:
        _paste_horizontal(
            context,
            request.edge_images.top,
            state,
            is_top=True,
        )
    if request.edge_images.bottom is not None:
        _paste_horizontal(
            context,
            request.edge_images.bottom,
            state,
            is_top=False,
        )

    jpg_bytes = _encode_canvas_to_jpeg(canvas, state.options.jpeg_quality)
    width_pts, height_pts = _page_dimensions(request.page, state.options)
    return jpg_bytes, width_pts, height_pts


def _render_all_pages(
    edge_images: EdgeImageSet,
    state: ComposeState,
    context: GenerationContext,
) -> None:
    for page_idx, page in enumerate(context.src):
        request = PageComposeRequest(
            page=page,
            page_idx=page_idx,
            edge_images=edge_images,
            matrix=context.matrix,
            bleed_px=context.bleed_px,
        )
        jpg_bytes, width_pts, height_pts = _compose_page(request, state)
        out_page = context.out.new_page(width=width_pts, height=height_pts)
        out_page.insert_image(out_page.rect, stream=jpg_bytes)
        context.progress_callback(page_idx + 1, state.total_pages)


def generate_output_pdf(
    pdf_bytes: bytes,
    edge_images: EdgeImageSet,
    options: RenderOptions,
    progress_callback: ProgressCallback,
) -> bytes:
    """Generate an edged output PDF from input PDF bytes and edge images."""

    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    out = fitz.open()

    total_pages = len(src)
    state = ComposeState(
        options=options,
        total_pages=total_pages,
        strip_px=_effective_strip_px(options),
    )
    bleed_px = (
        pts_to_px(options.placement.bleed_pts, options.dpi)
        if options.placement.add_bleed
        else 0
    )
    matrix = fitz.Matrix(options.dpi / 72.0, options.dpi / 72.0)

    metadata = getattr(src, "metadata", None)
    if metadata:
        out.set_metadata(metadata)

    generation_context = GenerationContext(
        src=src,
        out=out,
        matrix=matrix,
        bleed_px=bleed_px,
        progress_callback=progress_callback,
    )
    _render_all_pages(edge_images, state, generation_context)

    output_bytes = out.tobytes(garbage=4, deflate=True)
    src.close()
    out.close()
    return output_bytes
