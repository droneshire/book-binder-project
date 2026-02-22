import io
import json
import zipfile

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
from book_page_edges.core.models import PdfAnalysis
from book_page_edges.core.pdf_factory import create_blank_pdf
from book_page_edges.core.processing import generate_output_pdf
from book_page_edges.core.validation import validate_uploaded_image


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _interpolate_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def _build_gradient_image(width: int, height: int, c1: str, c2: str, vertical: bool) -> Image.Image:
    a = _hex_to_rgb(c1)
    b = _hex_to_rgb(c2)
    img = Image.new("RGBA", (width, height))
    px = img.load()

    if vertical:
        denom = max(1, height - 1)
        for y in range(height):
            color = _interpolate_rgb(a, b, y / denom)
            for x in range(width):
                px[x, y] = (*color, 255)
    else:
        denom = max(1, width - 1)
        for x in range(width):
            color = _interpolate_rgb(a, b, x / denom)
            for y in range(height):
                px[x, y] = (*color, 255)

    return img


def _build_solid_image(width: int, height: int, color: str) -> Image.Image:
    r, g, b = _hex_to_rgb(color)
    return Image.new("RGBA", (width, height), (r, g, b, 255))


def _validate_top_bottom_image(
    uploaded_file,
    label: str,
    dims: dict[str, int],
) -> tuple[list[str], Image.Image]:
    expected_w = dims["top_w"]
    expected_h = dims["top_h"]
    warnings, img = validate_uploaded_image(uploaded_file, label, expected_w, expected_h)

    # Accept StyledBookEdges-like vertical images and rotate them automatically.
    if img.size == (expected_h, expected_w):
        img = img.transpose(Image.Transpose.ROTATE_90)
        warnings.append(
            f"{label}: detected vertical upload format ({expected_h}x{expected_w}), auto-rotated for processing."
        )

    return warnings, img


def _png_bytes(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _build_edge_bundle_zip(
    fore_img: Image.Image,
    top_img: Image.Image | None,
    bottom_img: Image.Image | None,
    dims: dict[str, int],
    dpi: int,
    edge_width_pts: float,
    page_count: int,
    edge_config: str,
) -> bytes:
    meta = {
        "page_count": page_count,
        "dpi": dpi,
        "edge_width_pts": edge_width_pts,
        "edge_config": edge_config,
        "dimensions_px": {
            "fore": {"width": dims["fore_w"], "height": dims["fore_h"]},
            "top": {"width": dims["top_w"], "height": dims["top_h"]},
            "bottom": {"width": dims["top_w"], "height": dims["top_h"]},
        },
        "orientation": {
            "fore": "page 1 at top",
            "top": "page 1 at left",
            "bottom": "page 1 at left",
        },
    }

    out = io.BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("fore_edge.png", _png_bytes(fore_img))
        if top_img is not None:
            zf.writestr("top_edge.png", _png_bytes(top_img))
        if bottom_img is not None:
            zf.writestr("bottom_edge.png", _png_bytes(bottom_img))
        zf.writestr("edge_spec.json", json.dumps(meta, indent=2))
    return out.getvalue()


def _render_pdf_preview_image(pdf_bytes: bytes) -> Image.Image:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if len(doc) == 0:
            raise ValueError("Generated PDF has no pages")
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(0.35, 0.35), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def render_info(
    analysis: PdfAnalysis,
    dims: dict[str, int],
    dpi: int,
    edge_width_pts: float,
    paper_inches_per_page: float,
    bleed_pts: float,
) -> None:
    st.subheader("📘 Book Specifications")
    st.write(f"Page Count: **{analysis.page_count}**")
    st.write(
        "Trim / Media (first page): "
        f"**{analysis.first_trim_w_pts:.2f}x{analysis.first_trim_h_pts:.2f} pts** / "
        f"**{analysis.first_media_w_pts:.2f}x{analysis.first_media_h_pts:.2f} pts**"
    )
    st.write(f"Bleed detected on source PDF: **{'Yes' if analysis.has_bleed_on_first_page else 'No'}**")
    if analysis.mixed_trim_sizes:
        st.warning("Mixed trim sizes detected across pages.")

    st.subheader("📏 Required Edge Image Dimensions")
    st.write(f"DPI: **{dpi}**")
    st.write(f"Edge width: **{edge_width_pts:.2f} pts** ({dims['strip_px']} px)")
    st.code(
        "\n".join(
            [
                f"Fore-edge Image:  {dims['fore_w']} x {dims['fore_h']} px (vertical)",
                f"Top Edge Image:   {dims['top_w']} x {dims['top_h']} px",
                f"Bottom Edge Image:{dims['top_w']} x {dims['top_h']} px",
            ]
        )
    )

    est_thickness_in = paper_inches_per_page * analysis.page_count
    est_thickness_mm = est_thickness_in * 25.4
    st.caption(
        "Estimated closed block thickness: "
        f"{est_thickness_in:.2f} in ({est_thickness_mm:.1f} mm) using {paper_inches_per_page:.3f} in/page"
    )
    bleed_px = round((bleed_pts * dpi) / 72.0)
    st.caption(f"Configured output bleed: {bleed_pts / 72.0:.3f} in ({bleed_px} px)")


def _edge_images_from_inputs(
    mode: str,
    edge_config: str,
    dims: dict[str, int],
) -> tuple[Image.Image | None, Image.Image | None, Image.Image | None, list[str], bool]:
    warnings: list[str] = []
    valid = True
    fore_img = None
    top_img = None
    bottom_img = None

    include_top_bottom = edge_config == "All Three Edges"

    st.subheader("🎨 Edge Input")

    if mode == "Upload Images":
        col1, col2 = st.columns(2)
        with col1:
            fore_upload = st.file_uploader("🖼️ Fore-edge Image", type=["png"], key="fore_upload")
        with col2:
            if include_top_bottom:
                top_upload = st.file_uploader("🖼️ Top Edge Image", type=["png"], key="top_upload")
                bottom_upload = st.file_uploader("🖼️ Bottom Edge Image", type=["png"], key="bottom_upload")
            else:
                top_upload = None
                bottom_upload = None

        if fore_upload is None:
            valid = False
        else:
            w, fore_img = validate_uploaded_image(fore_upload, "Fore edge", dims["fore_w"], dims["fore_h"])
            warnings.extend(w)

        if include_top_bottom:
            if top_upload is None or bottom_upload is None:
                valid = False
            else:
                w, top_img = _validate_top_bottom_image(top_upload, "Top edge", dims)
                warnings.extend(w)
                w, bottom_img = _validate_top_bottom_image(bottom_upload, "Bottom edge", dims)
                warnings.extend(w)

    elif mode == "Gradient":
        c1 = st.color_picker("🌈 Gradient Start Color", "#1d4ed8", key="grad_c1")
        c2 = st.color_picker("🌈 Gradient End Color", "#0f766e", key="grad_c2")

        fore_img = _build_gradient_image(dims["fore_w"], dims["fore_h"], c1, c2, vertical=True)
        if include_top_bottom:
            top_img = _build_gradient_image(dims["top_w"], dims["top_h"], c1, c2, vertical=False)
            bottom_img = _build_gradient_image(dims["top_w"], dims["top_h"], c1, c2, vertical=False)

    else:  # Solid Color
        color = st.color_picker("🎯 Edge Color", "#0f172a", key="solid_c")

        fore_img = _build_solid_image(dims["fore_w"], dims["fore_h"], color)
        if include_top_bottom:
            top_img = _build_solid_image(dims["top_w"], dims["top_h"], color)
            bottom_img = _build_solid_image(dims["top_w"], dims["top_h"], color)

    return fore_img, top_img, bottom_img, warnings, valid


def main() -> None:
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

    with st.sidebar:
        st.header("⚙️ Output Settings")
        preset = st.selectbox("Printer Preset", options=list(PRINTER_PRESETS.keys()), index=1)
        preset_vals = PRINTER_PRESETS[preset]

        dpi = st.number_input("DPI", min_value=72, max_value=1200, value=DEFAULT_DPI, step=1)
        edge_width_pts = st.number_input(
            "Edge Width (pts)", min_value=1.0, max_value=200.0, value=DEFAULT_EDGE_WIDTH_PTS, step=1.0
        )
        fore_opacity = st.slider("Edge Opacity", min_value=0.0, max_value=1.0, value=DEFAULT_FORE_OPACITY, step=0.01)
        jpeg_quality = st.slider("JPEG Quality", min_value=1, max_value=95, value=DEFAULT_JPEG_QUALITY, step=1)

        st.header("🩸 Bleed")
        add_bleed = st.checkbox("Add Bleed To Output", value=False)
        bleed_in = st.number_input(
            "Bleed (inches)",
            min_value=0.0,
            max_value=0.5,
            value=float(preset_vals["bleed_in"]),
            step=0.005,
            format="%.3f",
        )
        apply_edges_in_bleed_only = st.checkbox("Apply Edges In Bleed Area Only", value=True)

        st.header("📄 Paper")
        paper_type = st.selectbox("Paper Type", options=list(PAPER_TYPES_INCH_PER_PAGE.keys()), index=0)
        st.caption(f"Preset safe area ({preset}): {preset_vals['safe_area_in']:.3f} in")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.subheader("📚 Interior Source")
    interior_source = st.radio(
        "Choose interior input",
        options=["Upload Interior PDF", "Generate Blank Interior PDF"],
        horizontal=True,
    )

    if interior_source == "Upload Interior PDF":
        pdf_upload = st.file_uploader("📎 Your manuscript PDF with bleed", type=["pdf"], key="pdf_upload")
        if pdf_upload is None:
            st.info("Upload a print-ready interior PDF to continue.")
            return
        pdf_bytes = pdf_upload.getvalue()
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            trim_width_in = st.number_input("Trim Width (in)", min_value=1.0, max_value=12.0, value=5.0, step=0.01)
        with c2:
            trim_height_in = st.number_input("Trim Height (in)", min_value=1.0, max_value=14.0, value=8.0, step=0.01)
        with c3:
            blank_page_count = st.number_input("Page Count", min_value=1, max_value=2000, value=300, step=1)

        try:
            pdf_bytes = create_blank_pdf(
                page_count=int(blank_page_count),
                trim_width_in=float(trim_width_in),
                trim_height_in=float(trim_height_in),
            )
        except Exception as exc:
            st.error(f"Failed to generate blank interior PDF: {exc}")
            return
        st.caption("🧱 Using generated blank interior PDF. Output will be edge-sliced artwork on blank pages.")

    bleed_pts = inches_to_pts(float(bleed_in))
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.divider()

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            analysis, metrics = analyze_pdf(doc, int(dpi))
    except Exception as exc:
        st.error(f"Failed to open PDF: {exc}")
        return

    dims = expected_edge_dimensions(
        metrics=metrics,
        page_count=analysis.page_count,
        edge_width_pts=float(edge_width_pts),
        dpi=int(dpi),
    )

    render_info(
        analysis=analysis,
        dims=dims,
        dpi=int(dpi),
        edge_width_pts=float(edge_width_pts),
        paper_inches_per_page=PAPER_TYPES_INCH_PER_PAGE[paper_type],
        bleed_pts=bleed_pts,
    )

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

    try:
        fore_img, top_img, bottom_img, image_warnings, ready = _edge_images_from_inputs(input_mode, edge_config, dims)
    except Exception as exc:
        st.error(f"Failed while preparing edge inputs: {exc}")
        return

    for msg in image_warnings:
        st.warning(msg)

    if add_bleed and bleed_in <= 0:
        st.error("Bleed must be greater than 0 when 'Add Bleed To Output' is enabled.")
        return

    if add_bleed and apply_edges_in_bleed_only and edge_width_pts > bleed_pts:
        st.warning("Edge width is larger than bleed and will be clamped to bleed width.")

    if not ready:
        st.warning("Complete required edge inputs to generate output.")
        return
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    if delivery == "Edge File Only":
        if st.button("Generate Edge File Bundle", type="primary"):
            if fore_img is None:
                st.error("Fore-edge image is required.")
                return

            try:
                bundle = _build_edge_bundle_zip(
                    fore_img=fore_img,
                    top_img=top_img,
                    bottom_img=bottom_img,
                    dims=dims,
                    dpi=int(dpi),
                    edge_width_pts=float(edge_width_pts),
                    page_count=analysis.page_count,
                    edge_config=edge_config,
                )
            except Exception as exc:
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
        return

    if st.button("🚀 Generate Styled Edge PDF", type="primary"):
        progress = st.progress(0.0)
        status = st.empty()

        def progress_callback(done: int, total: int) -> None:
            pct = done / total
            progress.progress(pct)
            status.write(f"Processing page {done}/{total} ({pct * 100:.1f}%)")

        try:
            output_pdf = generate_output_pdf(
                pdf_bytes=pdf_bytes,
                fore_img=fore_img,
                top_img=top_img,
                bottom_img=bottom_img,
                dpi=int(dpi),
                edge_width_pts=float(edge_width_pts),
                side=side,
                mirror_even=bool(mirror_even),
                fore_opacity=float(fore_opacity),
                jpeg_quality=int(jpeg_quality),
                add_bleed=bool(add_bleed),
                bleed_pts=float(bleed_pts),
                apply_edges_in_bleed_only=bool(apply_edges_in_bleed_only),
                progress_callback=progress_callback,
            )
        except Exception as exc:
            st.error(f"Processing failed: {exc}")
            return
        finally:
            progress.empty()
            status.empty()

        size_mb = len(output_pdf) / (1024 * 1024)
        st.success(f"✅ Output generated successfully. File size: {size_mb:.2f} MB")
        try:
            preview_img = _render_pdf_preview_image(output_pdf)
            st.subheader("👀 Preview")
            st.image(preview_img, caption="Generated output preview (page 1)", use_container_width=True)
        except Exception as exc:
            st.warning(f"Preview unavailable: {exc}")
        st.download_button(
            label="⬇️ Download output_edges.pdf",
            data=output_pdf,
            file_name="output_edges.pdf",
            mime="application/pdf",
            type="primary",
        )
