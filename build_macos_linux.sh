#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "Building LED Placement Studio..."
python3 -m pip install --upgrade pip pyinstaller
pyinstaller --noconfirm --clean \
  --name "LED_Placement_Studio" \
  --windowed \
  --onefile \
  --add-data "styles:styles" \
  --add-data "assets:assets" \
  main.py
echo "Done. Binary is in dist/"
