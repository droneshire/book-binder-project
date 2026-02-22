VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip
STREAMLIT := $(VENV)/bin/streamlit
PYINSTALLER := $(VENV)/bin/pyinstaller
BLACK := $(VENV)/bin/black
AUTOPEP8 := $(VENV)/bin/autopep8
MYPY := $(VENV)/bin/mypy
PYLINT := $(VENV)/bin/pylint
PYTEST := $(VENV)/bin/pytest

.PHONY: clean init install run_app build_standalone format lint test

clean:
	rm -rf $(VENV) build dist .pytest_cache .mypy_cache
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +

init:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: init
	$(PIP) install -e .

run_app: install
	$(STREAMLIT) run streamlit_app.py

build_standalone: install
	$(PIP) install pyinstaller
	$(PYINSTALLER) --clean --noconfirm --onefile \
		--name book-page-edges \
		--collect-all streamlit \
		--collect-all fitz \
		--collect-all PIL \
		streamlit_app.py

format: install
	$(PIP) install autopep8 black
	$(AUTOPEP8) --in-place --recursive src streamlit_app.py tests
	$(BLACK) src streamlit_app.py

lint: install
	$(PIP) install mypy pylint
	$(MYPY) --ignore-missing-imports src streamlit_app.py
	$(PYLINT) src/book_page_edges streamlit_app.py

test: install
	$(PIP) install pytest
	$(PYTEST) -q
