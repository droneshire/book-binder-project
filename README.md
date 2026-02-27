# Book Page Edge Design Applicator

Streamlit app for generating forced/printed page-edge effects for books.

It supports two download types:
- Full Service: creates a print-ready edged interior PDF.
- Edge File Only: creates edge asset files (`fore/top/bottom`) + `edge_spec.json` in a zip.

## Final Capabilities

- Upload interior PDF or generate a blank interior (trim size + page count).
- Fore-edge only or all three edges (fore/top/bottom).
- Edge art source:
  - upload PNGs,
  - generate gradient,
  - generate solid color.
- Slice algorithm maps one image segment per page, with safe clamped bounds.
- Side controls: `right`, `left`, `both`, plus even-page mirroring.
- Optional bleed expansion and bleed-only placement.
- Output preview shown before download (full-service mode).
- Edge-file bundle export with machine-readable metadata.

## Process Flow

### Full Service (Print-Ready PDF)

```text
Download Type: Full Service
    |
Interior Source (Upload PDF or Generate Blank)
    |
PDF Analysis + Required Edge Dimensions
    |
Edge Configuration (Fore-only or All Three)
    |
Decoration Source (Upload / Gradient / Solid)
    |
Per-page render loop:
  rasterize page -> slice edge art -> resize -> apply opacity -> place strips
    |
Generate output_edges.pdf
    |
Show preview (page 1) + download button
```

### Edge File Only

```text
Download Type: Edge File Only
    |
Interior Source (for sizing context)
    |
Dimension calculation + orientation rules
    |
Prepare edge images (upload/generated)
    |
Build edge_files.zip containing:
  fore_edge.png
  top_edge.png (optional)
  bottom_edge.png (optional)
  edge_spec.json
    |
Download bundle
```

## Core Algorithm

For page `i` in a document of `N` pages:

- Fore-edge (side) slice (vertical):
  - `y0 = round(i / N * H)`
  - `y1 = round((i + 1) / N * H)`
- Top/Bottom slices (horizontal):
  - `x0 = round(i / N * W)`
  - `x1 = round((i + 1) / N * W)`

Where `H` and `W` are source edge image dimensions. Bounds are clamped and enforced non-empty.

Duplex-aware placement rules:

- Fore-edge artwork is always placed on the **outer** edge, respecting binding:
  - LTR binding: outer edge is right on odd pages, left on even pages.
  - RTL binding: outer edge is left on odd pages, right on even pages.
- Top and bottom edges are applied consistently to the top and bottom margins plus bleed.

Placement order (to avoid corner artifacts):

1. Top
2. Bottom
3. Side (fore-edge)

High-level functional requirements (from the original PRD):

- **F1**: Accept independent edge artwork per edge (fore/top/bottom).
- **F2**: Apply slices into the correct margin zones.
- **F3**: Extend slices into the configured bleed region.
- **F4**: Maintain a safe text zone inside printer-safe margins.
- **F5**: Be duplex-aware so outer edges are decorated correctly.
- **F6**: Allow enabling/disabling each edge independently.

## Project Structure

```text
.
├── .github/workflows/
│   ├── python-ci.yml
│   └── release-matrix.yml
├── .streamlit/config.toml
├── Makefile
├── pyproject.toml
├── requirements.txt
├── streamlit_app.py
├── src/book_page_edges/
│   ├── app.py
│   └── core/
│       ├── analysis.py
│       ├── config.py
│       ├── image_ops.py
│       ├── models.py
│       ├── pdf_factory.py
│       ├── processing.py
│       └── validation.py
└── tests/
    ├── test_core.py
    └── test_pdf_factory.py
```

## Technical Implementation

- `src/book_page_edges/app.py`
  - Streamlit UI and branching for both download types.
  - Builds gradient/solid edge images.
  - Shows post-generation preview in full-service mode.

- `src/book_page_edges/core/processing.py`
  - Per-page rendering/compositing pipeline.
  - JPEG-embedded PDF output with optional bleed expansion.

- `src/book_page_edges/core/analysis.py`
  - PDF analysis and required edge-dimension calculation.

- `src/book_page_edges/core/validation.py`
  - Uploaded image validation and warnings.

- `src/book_page_edges/core/pdf_factory.py`
  - Blank PDF creation from trim dimensions and page count.

- `streamlit_app.py`
  - App entrypoint.
  - Adds `src/` to `sys.path` so Streamlit Cloud can import package modules.

## How To Run Locally

Prerequisites:
- Python 3.10+
- `make`

Quickstart:

```bash
make run_app
```

This creates `.venv`, installs dependencies, and launches Streamlit.

## Make Targets

- `make init` - create venv + upgrade pip
- `make install` - install package (`pip install -e .`)
- `make run_app` - run Streamlit app
- `make format` - run `autopep8` then `black`
- `make lint` - run `mypy` + `pylint`
- `make test` - run `pytest`
- `make build_standalone` - build one-file executable with PyInstaller
- `make clean` - remove venv/build/cache artifacts

## Usage Guide

### Full Service

1. Select `Download Type` -> `Full Service - Print-Ready Book PDF`.
2. Choose interior source:
   - upload interior PDF, or
   - generate blank interior from trim width/height + page count.
3. Review Book Specifications and Required Edge Image Dimensions.
4. Select edge layout (`Fore-edge Only` or `All Three Edges`).
5. Choose decoration source (`Upload Images`, `Gradient`, `Solid Color`).
6. Adjust side, mirror-even, DPI, opacity, JPEG quality, and bleed options.
7. Click `Generate Styled Edge PDF`.
8. Review preview shown below action.
9. Download `interior_multi_edge.pdf`.

### Edge File Only

1. Select `Download Type` -> `Edge File Only`.
2. Provide interior source (for sizing context).
3. Configure layout and decoration source.
4. Click `Generate Edge File Bundle`.
5. Download `edge_files.zip`.

Bundle contents:
- `fore_edge.png`
- `top_edge.png` (if selected)
- `bottom_edge.png` (if selected)
- `edge_spec.json`

## CI/CD and Releases

### Python CI

Workflow: `.github/workflows/python-ci.yml`

Runs on push/PR:
- `make lint`
- `make test`

### Matrix Release Build

Workflow: `.github/workflows/release-matrix.yml`

After successful CI on `main`, builds PyInstaller binaries for:
- Ubuntu
- macOS
- Windows

Then publishes a GitHub Release with binary assets and direct download links.

## Deploy To Streamlit Community Cloud

1. Push repository to GitHub.
2. In Streamlit Community Cloud:
   - Repository: `droneshire/book-binder-project`
   - Branch: `main`
   - Main file: `streamlit_app.py`
3. Deploy.

Notes:
- `requirements.txt` is included.
- `streamlit_app.py` bootstraps `src/` on `sys.path`, fixing `ModuleNotFoundError: book_page_edges` in remote deploys.

### Data Handling on Streamlit

- Uploaded PDFs and edge images are held **only in memory** for the active session.
- After a full-service PDF or edge bundle is successfully generated, the app clears upload-related Streamlit state so previously uploaded files are no longer retained by the UI logic.

## Testing

Run:

```bash
make test
```

Tests currently cover:
- pixel/point conversion,
- slice boundary behavior,
- side mirroring logic,
- expected dimension calculations,
- blank PDF generation dimensions + page count.

## Known Limitations

- Full-service output is rasterized (text is not selectable/searchable).
- Very large books and/or high DPI increase runtime and output size.
- Final printed appearance depends on printer trim tolerance and paper.

## License

See `LICENSE`.
