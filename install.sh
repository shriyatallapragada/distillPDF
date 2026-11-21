#!/usr/bin/env bash
# One-command setup for the DistillPDF pipeline and extension package.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then
    echo "Creating .venv with uv..."
    uv venv --python 3.12 .venv
  else
    echo "Creating .venv with python3..."
    python3 -m venv .venv
  fi
fi

echo "Installing Python dependencies..."
if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python -e ".[dev]"
else
  .venv/bin/pip install -e ".[dev]"
fi

echo "Registering the local PDF helper with Chrome..."
.venv/bin/python scripts/install_native_host.py

echo "Building the extension package..."
python3 scripts/package_extension.py

echo
echo "Done. Next steps:"
echo "  1. Chrome -> chrome://extensions -> Developer mode -> Load unpacked"
echo "  2. Select this project's extension/ folder"
echo "  3. Open a NotebookLM chat, pick answers, click Build PDF + HTML"
echo "  4. Find study-notes.pdf and study-notes.html in ~/Downloads"
echo "     (or in this project's out/ folder if macOS blocks Downloads)"
echo
echo "Windows users: run install.bat. On a phone, open"
echo "dist/DistillPDF-mobile-capture.zip's capture.html and paste the answers there."
