"""Streamlit entrypoint for local and cloud deployment."""

# pylint: disable=duplicate-code

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if __name__ == "__main__":
    from book_page_edges.app import main

    main()
