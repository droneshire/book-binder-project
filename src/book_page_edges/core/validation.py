import io

from PIL import Image


def validate_uploaded_image(
    uploaded_file,
    label: str,
    expected_width: int,
    expected_height: int,
) -> tuple[list[str], Image.Image]:
    warnings: list[str] = []
    raw = Image.open(io.BytesIO(uploaded_file.getvalue()))
    actual_w, actual_h = raw.size

    if (actual_w, actual_h) != (expected_width, expected_height):
        pct_w = ((actual_w / expected_width) - 1.0) * 100.0 if expected_width else 0.0
        pct_h = ((actual_h / expected_height) - 1.0) * 100.0 if expected_height else 0.0
        warnings.append(
            f"{label}: size is {actual_w}x{actual_h}, expected {expected_width}x{expected_height} "
            f"({pct_w:+.1f}% width, {pct_h:+.1f}% height)."
        )

    dpi_info = raw.info.get("dpi")
    if isinstance(dpi_info, tuple) and len(dpi_info) >= 1:
        try:
            img_dpi = float(dpi_info[0])
            if img_dpi < 300:
                warnings.append(
                    f"{label}: embedded DPI is {img_dpi:.0f}; 300+ is recommended."
                )
        except (TypeError, ValueError):
            pass

    return warnings, raw.convert("RGBA")
