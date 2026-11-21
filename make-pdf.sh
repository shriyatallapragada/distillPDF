#!/usr/bin/env bash
# Linux: double-click this file (or drag chat.json onto it).
cd "$(dirname "$0")" || exit 1
python3 scripts/make_pdf.py "$@"
