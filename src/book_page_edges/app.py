"""Streamlit UI for generating print-ready and edge-only book edge outputs."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from dataclasses import dataclass
from typing import Any

import fitz
import streamlit as st
from PIL import Image

from book_page_edges.core.analysis import analyze_pdf, expected_edge_dimensions
from book_page_edges.core.config import (
    DEFAULT_DPI,
    DEFAULT_EDGE_WIDTH_PTS,
    DEFAULT_FORE_OPACITY,
    DEFAULT_JPEG_QUALITY,
    PAPER_TYPES_INCH_PER_PAGE,
    PRINTER_PRESETS,
)
from book_page_edges.core.image_ops import inches_to_pts
from book_page_edges.core.models import PageMetrics, PdfAnalysis
from book_page_edges.core.pdf_factory import create_blank_pdf
from book_page_edges.core.processing import (
    EdgeImageSet,
    PlacementOptions,
    RenderOptions,
    generate_output_pdf,
)
from book_page_edges.core.validation import validate_uploaded_image


@dataclass(frozen=True)
class OutputSettings:
    """Rendering and quality settings."""

    dpi: int
    edge_width_pts: float
    fore_opacity: float
    jpeg_quality: int


@dataclass(frozen=True)
class BleedSettings:
    """Bleed placement and sizing settings."""

    add_bleed: bool
    bleed_in: float
    apply_edges_in_bleed_only: bool


@dataclass(frozen=True)
class SidebarSettings:
    """Configuration values collected from the sidebar controls."""

    preset: str
    paper_type: str
    output: OutputSettings
    bleed: BleedSettings


@dataclass(frozen=True)
class InteriorData:
    """Resolved interior context after input selection."""

    pdf_bytes: bytes
    analysis: PdfAnalysis
    metrics: list[PageMetrics]
    dims: dict[str, int]
    bleed_pts: float


@dataclass(frozen=True)
class EdgeInputs:
    """Edge image payload and selection configuration from the main form."""

    edge_config: str
    side: str
    mirror_even: bool
    images: EdgeImageSet
    warnings: list[str]
    ready: bool


@dataclass(frozen=True)
class EdgeBundleMeta:
    """Metadata attached to edge-only bundles."""

    dims: dict[str, int]
    dpi: int
    edge_width_pts: float
    page_count: int
    edge_config: str


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Convert `#RRGGBB` to an RGB tuple."""

    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _interpolate_rgb(
    color_a: tuple[int, int, int],
    color_b: tuple[int, int, int],
    weight: float,
) -> tuple[int, int, int]:
    """Linear interpolation between two RGB colors."""

    return (
        round(color_a[0] + (color_b[0] - color_a[0]) * weight),
        round(color_a[1] + (color_b[1] - color_a[1]) * weight),
        round(color_a[2] + (color_b[2] - color_a[2]) * weight),
    )


def _build_gradient_image(
    width: int,
    height: int,
    color_start: str,
    color_end: str,
    vertical: bool,
) -> Image.Image:
    """Build a simple two-color gradient image."""

    color_a = _hex_to_rgb(color_start)
    color_b = _hex_to_rgb(color_end)
    img = Image.new("RGBA", (width, height))
    px = img.load()
    if px is None:
        raise RuntimeError("Failed to acquire pixel buffer")

    if vertical:
        denom = max(1, height - 1)
        for y in range(height):
            color = _interpolate_rgb(color_a, color_b, y / denom)
            for x in range(width):
                px[x, y] = (*color, 255)
    else:
        denom = max(1, width - 1)
        for x in range(width):
            color = _interpolate_rgb(color_a, color_b, x / denom)
            for y in range(height):
                px[x, y] = (*color, 255)

    return img


def _build_solid_image(width: int, height: int, color: str) -> Image.Image:
    """Build a single-color RGBA image."""

    r, g, b = _hex_to_rgb(color)
    return Image.new("RGBA", (width, height), (r, g, b, 255))


def _validate_top_bottom_image(
    uploaded_file: Any,
    label: str,
    dims: dict[str, int],
) -> tuple[list[str], Image.Image]:
    """Validate top/bottom uploads and auto-rotate vertical-form uploads."""

    expected_w = dims["top_w"]
    expected_h = dims["top_h"]
    warnings, img = validate_uploaded_image(
        uploaded_file,
        label,
        expected_w,
        expected_h,
    )

    if img.size == (expected_h, expected_w):
        img = img.transpose(Image.Transpose.ROTATE_90)
        warnings.append(
            f"{label}: detected vertical upload format "
            f"({expected_h}x{expected_w}), auto-rotated for processing."
        )

    return warnings, img


def _png_bytes(img: Image.Image) -> bytes:
    """Encode a PIL image to PNG bytes."""

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _build_edge_bundle_zip(
    fore_img: Image.Image,
    top_img: Image.Image | None,
    bottom_img: Image.Image | None,
    meta: EdgeBundleMeta,
) -> bytes:
    """Build a zip file for edge-only delivery."""

    spec = {
        "page_count": meta.page_count,
        "dpi": meta.dpi,
        "edge_width_pts": meta.edge_width_pts,
        "edge_config": meta.edge_config,
        "dimensions_px": {
            "fore": {
                "width": meta.dims["fore_w"],
                "height": meta.dims["fore_h"],
            },
            "top": {
                "width": meta.dims["top_w"],
                "height": meta.dims["top_h"],
            },
            "bottom": {
                "width": meta.dims["top_w"],
                "height": meta.dims["top_h"],
            },
        },
        "orientation": {
            "fore": "page 1 at top",
            "top": "page 1 at left",
            "bottom": "page 1 at left",
        },
    }

    out = io.BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fore_edge.png", _png_bytes(fore_img))
        if top_img is not None:
            archive.writestr("top_edge.png", _png_bytes(top_img))
        if bottom_img is not None:
            archive.writestr("bottom_edge.png", _png_bytes(bottom_img))
        archive.writestr("edge_spec.json", json.dumps(spec, indent=2))

    return out.getvalue()


def _render_pdf_preview_images(
    pdf_bytes: bytes,
    start_page: int,
    page_window: int,
) -> tuple[list[Image.Image], int, int]:
    """Render a small image preview window for generated output pages."""

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        total = len(doc)
        if total == 0:
            raise ValueError("Generated PDF has no pages")

        start = max(0, min(start_page, total - 1))
        previews: list[Image.Image] = []
        for idx in range(start, min(total, start + page_window)):
            page = doc[idx]
            pix = page.get_pixmap(matrix=fitz.Matrix(0.16, 0.16), alpha=False)
            previews.append(
                Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            )

    return previews, total, start


def _thumbnail(img: Image.Image, max_w: int = 220, max_h: int = 320) -> Image.Image:
    """Create a bounded-size thumbnail copy."""

    out = img.copy()
    out.thumbnail((max_w, max_h))
    return out


def _to_data_uri(img: Image.Image) -> str:
    """Encode an image into an inline PNG data URI."""

    out = io.BytesIO()
    img.save(out, format="PNG")
    b64 = base64.b64encode(out.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _render_info(
    analysis: PdfAnalysis,
    dims: dict[str, int],
    settings: SidebarSettings,
    bleed_pts: float,
) -> None:
    """Render the analysis and sizing section."""

    st.subheader("📘 Book Specifications")
    st.write(f"Page Count: **{analysis.page_count}**")
    st.write(
        "Trim / Media (first page): "
        f"**{analysis.first_trim_w_pts:.2f}x{analysis.first_trim_h_pts:.2f} pts** / "
        f"**{analysis.first_media_w_pts:.2f}x{analysis.first_media_h_pts:.2f} pts**"
    )
    detected = "Yes" if analysis.has_bleed_on_first_page else "No"
    st.write(f"Bleed detected on source PDF: **{detected}**")

    if analysis.mixed_trim_sizes:
        st.warning("Mixed trim sizes detected across pages.")

    st.subheader("📏 Required Edge Image Dimensions")
    st.write(f"DPI: **{settings.output.dpi}**")
    st.write(
        f"Edge width: **{settings.output.edge_width_pts:.2f} pts** ({dims['strip_px']} px)"
    )
    st.code(
        "\n".join(
            [
                f"Fore-edge Image:  {dims['fore_w']} x {dims['fore_h']} px (vertical)",
                f"Top Edge Image:   {dims['top_w']} x {dims['top_h']} px",
                f"Bottom Edge Image:{dims['top_w']} x {dims['top_h']} px",
            ]
        )
    )

    paper_inches = PAPER_TYPES_INCH_PER_PAGE[settings.paper_type]
    est_thickness_in = paper_inches * analysis.page_count
    est_thickness_mm = est_thickness_in * 25.4
    st.caption(
        "Estimated closed block thickness: "
        f"{est_thickness_in:.2f} in ({est_thickness_mm:.1f} mm) "
        f"using {paper_inches:.3f} in/page"
    )

    bleed_px = round((bleed_pts * settings.output.dpi) / 72.0)
    st.caption(f"Configured output bleed: {bleed_pts / 72.0:.3f} in ({bleed_px} px)")


def _render_sidebar() -> SidebarSettings:
    """Render sidebar controls and return normalized settings."""

    with st.sidebar:
        st.header("⚙️ Output Settings")
        preset = st.selectbox(
            "Printer Preset",
            options=list(PRINTER_PRESETS.keys()),
            index=1,
        )
        preset_vals = PRINTER_PRESETS[preset]

        dpi = int(
            st.number_input(
                "DPI",
                min_value=72,
                max_value=1200,
                value=DEFAULT_DPI,
                step=1,
            )
        )
        edge_width_pts = float(
            st.number_input(
                "Edge Width (pts)",
                min_value=1.0,
                max_value=200.0,
                value=DEFAULT_EDGE_WIDTH_PTS,
                step=1.0,
            )
        )
        fore_opacity = float(
            st.slider(
                "Edge Opacity",
                min_value=0.0,
                max_value=1.0,
                value=DEFAULT_FORE_OPACITY,
                step=0.01,
            )
        )
        jpeg_quality = int(
            st.slider(
                "JPEG Quality",
                min_value=1,
                max_value=95,
                value=DEFAULT_JPEG_QUALITY,
                step=1,
            )
        )

        st.header("🩸 Bleed")
        add_bleed = st.checkbox("Add Bleed To Output", value=False)
        bleed_in = float(
            st.number_input(
                "Bleed (inches)",
                min_value=0.0,
                max_value=0.5,
                value=float(preset_vals["bleed_in"]),
                step=0.005,
                format="%.3f",
            )
        )
        apply_edges_in_bleed_only = st.checkbox(
            "Apply Edges In Bleed Area Only",
            value=True,
        )

        st.header("📄 Paper")
        paper_type = st.selectbox(
            "Paper Type",
            options=list(PAPER_TYPES_INCH_PER_PAGE.keys()),
            index=0,
        )
        st.caption(
            f"Preset safe area ({preset}): " f"{preset_vals['safe_area_in']:.3f} in"
        )

    return SidebarSettings(
        preset=preset,
        paper_type=paper_type,
        output=OutputSettings(
            dpi=dpi,
            edge_width_pts=edge_width_pts,
            fore_opacity=fore_opacity,
            jpeg_quality=jpeg_quality,
        ),
        bleed=BleedSettings(
            add_bleed=add_bleed,
            bleed_in=bleed_in,
            apply_edges_in_bleed_only=apply_edges_in_bleed_only,
        ),
    )


def _render_interior_source() -> bytes | None:
    """Render interior source controls and return resolved PDF bytes."""

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.subheader("📚 Interior Source")
    interior_source = st.radio(
        "Choose interior input",
        options=["Upload Interior PDF", "Generate Blank Interior PDF"],
        horizontal=True,
    )

    if interior_source == "Upload Interior PDF":
        pdf_upload = st.file_uploader(
            "📎 Your manuscript PDF with bleed",
            type=["pdf"],
            key="pdf_upload",
        )
        if pdf_upload is None:
            st.info("Upload a print-ready interior PDF to continue.")
            return None
        return pdf_upload.getvalue()

    c1, c2, c3 = st.columns(3)
    with c1:
        trim_width_in = float(
            st.number_input(
                "Trim Width (in)",
                min_value=1.0,
                max_value=12.0,
                value=5.0,
                step=0.01,
            )
        )
    with c2:
        trim_height_in = float(
            st.number_input(
                "Trim Height (in)",
                min_value=1.0,
                max_value=14.0,
                value=8.0,
                step=0.01,
            )
        )
    with c3:
        blank_page_count = int(
            st.number_input(
                "Page Count",
                min_value=1,
                max_value=2000,
                value=300,
                step=1,
            )
        )

    try:
        pdf_bytes = create_blank_pdf(
            page_count=blank_page_count,
            trim_width_in=trim_width_in,
            trim_height_in=trim_height_in,
        )
    except (ValueError, RuntimeError) as exc:
        st.error(f"Failed to generate blank interior PDF: {exc}")
        return None

    st.caption(
        "🧱 Using generated blank interior PDF. "
        "Output will be edge-sliced artwork on blank pages."
    )
    return pdf_bytes


def _prepare_interior_data(
    settings: SidebarSettings, pdf_bytes: bytes
) -> InteriorData | None:
    """Analyze PDF and compute edge dimension recommendations."""

    bleed_pts = inches_to_pts(settings.bleed.bleed_in)
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.divider()

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            analysis, metrics = analyze_pdf(doc, settings.output.dpi)
    except (RuntimeError, ValueError) as exc:
        st.error(f"Failed to open PDF: {exc}")
        return None

    dims = expected_edge_dimensions(
        metrics=metrics,
        page_count=analysis.page_count,
        edge_width_pts=settings.output.edge_width_pts,
        dpi=settings.output.dpi,
    )

    _render_info(
        analysis=analysis,
        dims=dims,
        settings=settings,
        bleed_pts=bleed_pts,
    )

    return InteriorData(
        pdf_bytes=pdf_bytes,
        analysis=analysis,
        metrics=metrics,
        dims=dims,
        bleed_pts=bleed_pts,
    )


def _edge_inputs_from_upload(
    dims: dict[str, int],
    include_top_bottom: bool,
) -> tuple[Image.Image | None, Image.Image | None, Image.Image | None, list[str], bool]:
    """Collect edge images from upload widgets."""

    warnings: list[str] = []
    fore_img = None
    top_img = None
    bottom_img = None

    col1, col2 = st.columns(2)
    with col1:
        fore_upload = st.file_uploader(
            "🖼️ Fore-edge Image",
            type=["png"],
            key="fore_upload",
        )
    with col2:
        top_upload = None
        bottom_upload = None
        if include_top_bottom:
            top_upload = st.file_uploader(
                "🖼️ Top Edge Image",
                type=["png"],
                key="top_upload",
            )
            bottom_upload = st.file_uploader(
                "🖼️ Bottom Edge Image",
                type=["png"],
                key="bottom_upload",
            )

    ready = fore_upload is not None
    if fore_upload is not None:
        cur_warnings, fore_img = validate_uploaded_image(
            fore_upload,
            "Fore edge",
            dims["fore_w"],
            dims["fore_h"],
        )
        warnings.extend(cur_warnings)

    if include_top_bottom:
        if top_upload is None or bottom_upload is None:
            ready = False
        else:
            top_warnings, top_img = _validate_top_bottom_image(
                top_upload,
                "Top edge",
                dims,
            )
            warnings.extend(top_warnings)
            bottom_warnings, bottom_img = _validate_top_bottom_image(
                bottom_upload,
                "Bottom edge",
                dims,
            )
            warnings.extend(bottom_warnings)

    return fore_img, top_img, bottom_img, warnings, ready


def _edge_inputs_from_generated(
    dims: dict[str, int],
    include_top_bottom: bool,
    input_mode: str,
) -> tuple[Image.Image | None, Image.Image | None, Image.Image | None, list[str], bool]:
    """Build edge images from generated color/gradient inputs."""

    warnings: list[str] = []

    if input_mode == "Gradient":
        color_a = st.color_picker("🌈 Gradient Start Color", "#1d4ed8", key="grad_c1")
        color_b = st.color_picker("🌈 Gradient End Color", "#0f766e", key="grad_c2")
        fore_img = _build_gradient_image(
            dims["fore_w"],
            dims["fore_h"],
            color_a,
            color_b,
            vertical=True,
        )
        if include_top_bottom:
            top_img = _build_gradient_image(
                dims["top_w"],
                dims["top_h"],
                color_a,
                color_b,
                vertical=False,
            )
            bottom_img = _build_gradient_image(
                dims["top_w"],
                dims["top_h"],
                color_a,
                color_b,
                vertical=False,
            )
        else:
            top_img = None
            bottom_img = None

        return fore_img, top_img, bottom_img, warnings, True

    color = st.color_picker("🎯 Edge Color", "#0f172a", key="solid_c")
    fore_img = _build_solid_image(dims["fore_w"], dims["fore_h"], color)
    if include_top_bottom:
        top_img = _build_solid_image(dims["top_w"], dims["top_h"], color)
        bottom_img = _build_solid_image(dims["top_w"], dims["top_h"], color)
    else:
        top_img = None
        bottom_img = None

    return fore_img, top_img, bottom_img, warnings, True


def _render_edge_configuration(dims: dict[str, int]) -> EdgeInputs:
    """Render edge config controls and resolve edge images."""

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.subheader("🧩 Edge Configuration")
    edge_config = st.radio(
        "Select edge layout",
        options=["Fore-edge Only", "All Three Edges"],
        horizontal=True,
    )

    side = st.selectbox("↔️ Fore-edge Side", options=["right", "left", "both"], index=0)
    mirror_even = st.checkbox("🪞 Mirror Even Pages", value=False)

    input_mode = st.radio(
        "Decoration source",
        options=["Upload Images", "Gradient", "Solid Color"],
        horizontal=True,
    )
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.subheader("🎨 Edge Input")

    include_top_bottom = edge_config == "All Three Edges"
    if input_mode == "Upload Images":
        fore_img, top_img, bottom_img, warnings, ready = _edge_inputs_from_upload(
            dims,
            include_top_bottom,
        )
    else:
        fore_img, top_img, bottom_img, warnings, ready = _edge_inputs_from_generated(
            dims,
            include_top_bottom,
            input_mode,
        )

    return EdgeInputs(
        edge_config=edge_config,
        side=side,
        mirror_even=mirror_even,
        images=EdgeImageSet(fore=fore_img, top=top_img, bottom=bottom_img),
        warnings=warnings,
        ready=ready,
    )


def _validate_preconditions(
    settings: SidebarSettings,
    interior: InteriorData,
    edge_inputs: EdgeInputs,
) -> bool:
    """Validate runtime preconditions before generation."""

    for warning in edge_inputs.warnings:
        st.warning(warning)

    if settings.bleed.add_bleed and settings.bleed.bleed_in <= 0:
        st.error("Bleed must be greater than 0 when 'Add Bleed To Output' is enabled.")
        return False

    if settings.bleed.add_bleed and settings.bleed.apply_edges_in_bleed_only:
        if settings.output.edge_width_pts > interior.bleed_pts:
            st.warning(
                "Edge width is larger than bleed and will be clamped to bleed width."
            )

    if not edge_inputs.ready:
        st.warning("Complete required edge inputs to generate output.")
        return False

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    return True


def _render_edge_file_only_button(
    interior: InteriorData,
    edge_inputs: EdgeInputs,
    settings: SidebarSettings,
) -> None:
    """Render and execute edge-file-only generation flow."""

    if not st.button("Generate Edge File Bundle", type="primary"):
        return

    if edge_inputs.images.fore is None:
        st.error("Fore-edge image is required.")
        return

    try:
        bundle = _build_edge_bundle_zip(
            fore_img=edge_inputs.images.fore,
            top_img=edge_inputs.images.top,
            bottom_img=edge_inputs.images.bottom,
            meta=EdgeBundleMeta(
                dims=interior.dims,
                dpi=settings.output.dpi,
                edge_width_pts=settings.output.edge_width_pts,
                page_count=interior.analysis.page_count,
                edge_config=edge_inputs.edge_config,
            ),
        )
    except (RuntimeError, ValueError, OSError) as exc:
        st.error(f"Failed to build edge bundle: {exc}")
        return

    size_mb = len(bundle) / (1024 * 1024)
    st.success(f"✅ Edge bundle generated. File size: {size_mb:.2f} MB")
    st.download_button(
        label="⬇️ Download edge_files.zip",
        data=bundle,
        file_name="edge_files.zip",
        mime="application/zip",
        type="primary",
    )


def _render_preview_html(preview_imgs: list[Image.Image], start_page: int) -> str:
    """Build HTML preview cards for two pages."""

    left_page_num = start_page + 1
    right_page_num = start_page + 2
    left_uri = _to_data_uri(_thumbnail(preview_imgs[0], max_w=160, max_h=220))

    if len(preview_imgs) > 1:
        right_uri = _to_data_uri(_thumbnail(preview_imgs[1], max_w=160, max_h=220))
        right_block = (
            "<div style='text-align:center;'>"
            f"<img src='{right_uri}' "
            "style='width:160px; height:220px; object-fit:contain; "
            "border:1px solid #ddd; border-radius:8px; background:#fff;' />"
            f"<div style='font-size:0.85rem; margin-top:6px;'>Page {right_page_num}</div>"
            "</div>"
        )
    else:
        right_block = (
            "<div style='display:flex; align-items:center; font-size:0.85rem; color:#666;'>"
            "Only one page available."
            "</div>"
        )

    return (
        "<div style='display:flex; justify-content:center; gap:16px; margin:8px 0 14px 0;'>"
        "<div style='text-align:center;'>"
        f"<img src='{left_uri}' "
        "style='width:160px; height:220px; object-fit:contain; "
        "border:1px solid #ddd; border-radius:8px; background:#fff;' />"
        f"<div style='font-size:0.85rem; margin-top:6px;'>Page {left_page_num}</div>"
        "</div>"
        f"{right_block}"
        "</div>"
    )


def _render_preview_navigation(
    total_pages: int, start_page: int, page_count: int
) -> None:
    """Render page preview navigation controls."""

    nav_cols = st.columns([1, 2, 1])
    with nav_cols[0]:
        prev_clicked = st.button("⬅️", disabled=start_page == 0, key="preview_prev")
    with nav_cols[1]:
        end_page = min(total_pages, start_page + page_count)
        st.markdown(
            (
                "<div style='text-align:center; padding-top:8px;'>"
                f"Pages {start_page + 1}-{end_page} of {total_pages}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    with nav_cols[2]:
        next_clicked = st.button(
            "➡️",
            disabled=(start_page + page_count) >= total_pages,
            key="preview_next",
        )

    if prev_clicked:
        st.session_state["preview_start_page"] = max(0, start_page - 1)
        st.rerun()
    if next_clicked:
        st.session_state["preview_start_page"] = min(total_pages - 1, start_page + 1)
        st.rerun()


def _render_full_service_output(
    output_pdf: bytes,
) -> None:
    """Render post-generation success, preview, and download controls."""

    size_mb = len(output_pdf) / (1024 * 1024)
    st.success(f"✅ Output generated successfully. File size: {size_mb:.2f} MB")

    try:
        preview_start = int(st.session_state.get("preview_start_page", 0))
        preview_imgs, total_pages, clamped_start = _render_pdf_preview_images(
            output_pdf,
            start_page=preview_start,
            page_window=2,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        st.warning(f"Preview unavailable: {exc}")
    else:
        st.session_state["preview_start_page"] = clamped_start
        st.subheader("👀 Preview")
        _render_preview_navigation(total_pages, clamped_start, len(preview_imgs))
        st.markdown(
            _render_preview_html(preview_imgs, clamped_start),
            unsafe_allow_html=True,
        )

    st.download_button(
        label="⬇️ Download output_edges.pdf",
        data=output_pdf,
        file_name="output_edges.pdf",
        mime="application/pdf",
        type="primary",
    )


def _run_full_service(
    interior: InteriorData,
    edge_inputs: EdgeInputs,
    settings: SidebarSettings,
) -> None:
    """Handle generation and display of full-service PDF output."""

    if "generated_output_pdf" not in st.session_state:
        st.session_state["generated_output_pdf"] = None
    if "preview_start_page" not in st.session_state:
        st.session_state["preview_start_page"] = 0

    if st.button("🚀 Generate Styled Edge PDF", type="primary"):
        progress = st.progress(0.0)
        status = st.empty()

        def progress_callback(done: int, total: int) -> None:
            pct = done / total
            progress.progress(pct)
            status.write(f"Processing page {done}/{total} ({pct * 100:.1f}%)")

        options = RenderOptions(
            dpi=settings.output.dpi,
            edge_width_pts=settings.output.edge_width_pts,
            fore_opacity=settings.output.fore_opacity,
            jpeg_quality=settings.output.jpeg_quality,
            placement=PlacementOptions(
                side=edge_inputs.side,
                mirror_even=edge_inputs.mirror_even,
                add_bleed=settings.bleed.add_bleed,
                bleed_pts=interior.bleed_pts,
                apply_edges_in_bleed_only=settings.bleed.apply_edges_in_bleed_only,
            ),
        )

        try:
            output_pdf = generate_output_pdf(
                pdf_bytes=interior.pdf_bytes,
                edge_images=edge_inputs.images,
                options=options,
                progress_callback=progress_callback,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(f"Processing failed: {exc}")
            return
        finally:
            progress.empty()
            status.empty()

        st.session_state["generated_output_pdf"] = output_pdf
        st.session_state["preview_start_page"] = 0

    stored_output_pdf = st.session_state.get("generated_output_pdf")
    if stored_output_pdf is not None:
        _render_full_service_output(stored_output_pdf)


def main() -> None:
    """Run the Streamlit UI application."""

    st.set_page_config(page_title="Book Page Edge Applicator", layout="wide")
    st.title("✨ Create Your Styled Edges PDF")
    st.subheader("📦 Download Type")
    delivery = st.radio(
        "Download type",
        options=["Full Service - Print-Ready Book PDF", "Edge File Only"],
        horizontal=True,
    )
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.divider()

    settings = _render_sidebar()
    pdf_bytes = _render_interior_source()
    if pdf_bytes is None:
        return

    interior = _prepare_interior_data(settings, pdf_bytes)
    if interior is None:
        return

    edge_inputs = _render_edge_configuration(interior.dims)
    if not _validate_preconditions(settings, interior, edge_inputs):
        return

    if delivery == "Edge File Only":
        _render_edge_file_only_button(interior, edge_inputs, settings)
        return

    _run_full_service(interior, edge_inputs, settings)
