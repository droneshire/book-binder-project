# Book Page Edge Design Applicator

Streamlit app for generating forced/printed page-edge effects for books. It produces a print-ready edged interior PDF from your uploaded manuscript and edge artwork.

## Final Capabilities

- Upload interior PDF; add bleed to manuscript is on by default (KDP: 0.125 in; 6.125 × 9.25 in page size for 6×9 trim).
- Fore-edge only or all three edges (fore/top/bottom).
- Edge art source:
  - upload PNGs,
  - generate gradient,
  - generate solid color.
- Slice algorithm maps one image segment per page, with safe clamped bounds.
- Side controls: `right`, `left`, `both`, plus even-page mirroring.
- Optional bleed expansion and bleed-only placement.
- Output preview shown before download.

## Process Flow

```text
Interior Source (Upload PDF; add bleed on by default)
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
Generate print-ready PDF
    |
Show preview + download button
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
  - Streamlit UI for the print-ready PDF flow.
  - Builds gradient/solid edge images.
  - Shows post-generation preview.

- `src/book_page_edges/core/processing.py`
  - Per-page rendering/compositing pipeline.
  - JPEG-embedded PDF output with optional bleed expansion.

- `src/book_page_edges/core/analysis.py`
  - PDF analysis and required edge-dimension calculation.

- `src/book_page_edges/core/validation.py`
  - Uploaded image validation and warnings.

- `src/book_page_edges/core/pdf_factory.py`
  - Add bleed to manuscript (KDP-style expansion); blank PDF helper for tests.

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

1. Upload an interior PDF (add bleed to manuscript is on by default; KDP 6.125 × 9.25 in for 6×9 trim).
2. Review Book Specifications and Required Edge Image Dimensions.
3. Select edge layout (`Fore-edge Only` or `All Three Edges`).
4. Choose decoration source (`Upload Images`, `Gradient`, `Solid Color`).
5. Adjust side, mirror-even, DPI, edge width, opacity, and JPEG quality as needed.
6. Click `Generate Styled Edge PDF`.
7. Review preview and download `interior_multi_edge.pdf`.

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
- After a PDF is successfully generated, the app clears upload-related Streamlit state so previously uploaded files are no longer retained by the UI logic.

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

- Output is rasterized (text is not selectable/searchable).
- Very large books and/or high DPI increase runtime and output size.
- Final printed appearance depends on printer trim tolerance and paper.

## License

See `LICENSE`.
