# Book Page Edge Design Applicator

Streamlit app for creating forced/printed page-edge effects for books.

It supports two delivery modes:
- Full service: generate a print-ready edged interior PDF.
- Edge file only: generate edge asset files (`fore/top/bottom`) plus a metadata spec.

## What This Solves

When a closed book is viewed from the side/top/bottom, each page contributes one thin slice of an image. This tool automates:
- dimension calculation,
- per-page image slicing,
- compositing into page margins/bleed,
- final PDF generation or edge-asset export.

## Features

- Upload existing interior PDF or generate a blank interior by trim size + page count.
- Fore-edge only or all three edges (fore/top/bottom).
- Decoration input modes:
  - upload PNGs,
  - generate gradient,
  - generate solid color.
- Edge slicing with page-index interpolation and LANCZOS resizing.
- Optional bleed expansion and bleed-only edge placement.
- Fore-side placement: `right | left | both` + even-page mirroring.
- Output options:
  - print-ready edged `PDF`, or
  - downloadable `edge_files.zip` bundle.
- CI with lint/test and matrix release workflow for PyInstaller binaries.

## Process Flow

### 1) Full-Service (Print-Ready PDF)

```text
User Input
  ├─ Delivery: Full Service
  ├─ Interior: Upload PDF OR Generate Blank PDF
  ├─ Edge Config: Fore-only OR All three
  └─ Edge Art: Upload / Gradient / Solid

        ↓

PDF Analysis
  ├─ Page count
  ├─ Trim/media dimensions
  ├─ Bleed detection
  └─ Required edge image dimensions

        ↓

Per-Page Processing Loop
  ├─ Rasterize page @ DPI
  ├─ Slice edge image for page i
  ├─ Resize slice to strip target size
  ├─ Apply opacity
  ├─ Place on configured sides/edges
  └─ Encode page to JPEG and insert in output PDF

        ↓

Output
  └─ Download output_edges.pdf
```

### 2) Edge-File-Only

```text
User Input
  ├─ Delivery: Edge File Only
  ├─ Interior or blank-book specs (for sizing)
  └─ Edge Art: Upload / Gradient / Solid

        ↓

Dimension + Orientation Spec
  ├─ Fore: page 1 at top
  ├─ Top:  page 1 at left
  └─ Bottom: page 1 at left

        ↓

Bundle Build
  ├─ fore_edge.png
  ├─ top_edge.png (optional)
  ├─ bottom_edge.png (optional)
  └─ edge_spec.json

        ↓

Output
  └─ Download edge_files.zip
```

## Slicing Model

For a document with `N` pages and edge image height/width `H/W`:

- Fore-edge vertical slice for page `i`:
  - `y0 = round(i/N * H)`
  - `y1 = round((i+1)/N * H)`
- Top/bottom horizontal slice for page `i`:
  - `x0 = round(i/N * W)`
  - `x1 = round((i+1)/N * W)`

Bounds are clamped and forced non-empty to avoid cumulative off-by-one gaps.

## Project Layout

```text
.
├── .github/
│   └── workflows/
│       ├── python-ci.yml
│       └── release-matrix.yml
├── Makefile
├── pyproject.toml
├── streamlit_app.py
├── src/
│   └── book_page_edges/
│       ├── __init__.py
│       ├── app.py
│       └── core/
│           ├── __init__.py
│           ├── analysis.py
│           ├── config.py
│           ├── image_ops.py
│           ├── models.py
│           ├── pdf_factory.py
│           ├── processing.py
│           └── validation.py
└── tests/
    ├── test_core.py
    └── test_pdf_factory.py
```

## Technical Architecture

### Core modules

- `src/book_page_edges/core/config.py`
  - Defaults, printer presets, paper thickness presets.

- `src/book_page_edges/core/models.py`
  - Data models for page metrics and analysis.

- `src/book_page_edges/core/image_ops.py`
  - Unit conversions, slice bounds, slicing, side mirroring logic, image helpers.

- `src/book_page_edges/core/analysis.py`
  - PDF analysis and required edge-dimension calculations.

- `src/book_page_edges/core/validation.py`
  - PNG validation (size mismatch warnings, embedded DPI warnings).

- `src/book_page_edges/core/processing.py`
  - Main compositing pipeline and output PDF construction.

- `src/book_page_edges/core/pdf_factory.py`
  - Blank interior PDF generation from trim + page count.

- `src/book_page_edges/app.py`
  - Streamlit UI workflow and delivery branching.

### Rendering pipeline (full-service)

```text
fitz page -> pixmap @ DPI -> PIL RGBA canvas
      + per-edge slice crop/resize/opacity
      + placement (left/right/top/bottom)
      -> RGB JPEG bytes
      -> new PDF page (same or expanded dimensions)
```

## Installation and Usage

## Prerequisites

- Python 3.10+
- `make`

## Quickstart

```bash
make run_app
```

This will:
1. create `.venv`,
2. upgrade `pip`,
3. install package (`pip install -e .`),
4. run Streamlit app.

## Makefile Commands

- `make init`: create venv and upgrade pip.
- `make install`: install project in editable mode.
- `make run_app`: launch Streamlit app.
- `make format`: run `black`.
- `make lint`: run `mypy` + `pylint`.
- `make test`: run unit tests with `pytest`.
- `make build_standalone`: build one-file app with PyInstaller.
- `make clean`: remove venv/cache/build artifacts.

## Full-Service Usage (step-by-step)

1. Select `Full Service - Print-Ready Book PDF`.
2. Choose interior source:
   - upload manuscript PDF, or
   - generate blank interior from trim + page count.
3. Review analysis panel and required edge dimensions.
4. Select edge layout (`Fore-edge Only` or `All Three Edges`).
5. Choose decoration source (`Upload Images`, `Gradient`, or `Solid Color`).
6. Configure side/mirroring/opacity/quality/bleed.
7. Click `Generate Styled Edge PDF`.
8. Download `output_edges.pdf`.

## Edge-File-Only Usage (step-by-step)

1. Select `Edge File Only`.
2. Provide interior source (or blank specs) for sizing context.
3. Select edge layout and decoration source.
4. Click `Generate Edge File Bundle`.
5. Download `edge_files.zip`.

Bundle contents:
- `fore_edge.png`
- `top_edge.png` (if requested)
- `bottom_edge.png` (if requested)
- `edge_spec.json`

## Input/Output Specs

### Edge image orientation

- Fore-edge: page 1 at top, last page at bottom.
- Top edge: page 1 at left, last page at right.
- Bottom edge: page 1 at left, last page at right.

### Expected dimensions

Given first page raster size `(page_w_px, page_h_px)`, page count `N`, strip width `S`:
- Fore: `S x (page_h_px * N)`
- Top: `(page_w_px * N) x S`
- Bottom: `(page_w_px * N) x S`

## CI/CD

### Python CI

Workflow: `.github/workflows/python-ci.yml`

Runs on push and PR:
- `make lint`
- `make test`

### Release Matrix (PyInstaller)

Workflow: `.github/workflows/release-matrix.yml`

Triggered after successful `Python CI` on `main`:
- Builds binaries on:
  - `ubuntu-latest`
  - `macos-latest`
  - `windows-latest`
- Publishes a GitHub Release with assets and direct download links.

## Testing

Current tests cover:
- unit conversions and slice boundaries,
- vertical/horizontal slicing behavior,
- side mirroring logic,
- expected dimension calculations,
- blank PDF generation dimensions and page count.

Run:

```bash
make test
```

## Limitations

- Output PDF is rasterized; text is no longer selectable/searchable.
- Large books and high DPI can increase processing time and output size.
- Color output can vary by printer and paper.
- Edge effect quality depends on trim accuracy and print process.

## Troubleshooting

- If images fail validation:
  - check PNG dimensions against Required Edge Image Dimensions.
- If output covers content area:
  - enable bleed mode and/or reduce edge width.
- If local `pytest` fails due to missing modules:
  - use `make test` so dependencies are installed in `.venv`.

## License

See `LICENSE`.

## Deploy (Streamlit Community Cloud)

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create a new app and select:
   - Repository: `droneshire/book-binder-project`
   - Branch: `main`
   - Main file path: `streamlit_app.py`
3. Deploy.

If prompted for dependencies, this repo already provides `requirements.txt`.
