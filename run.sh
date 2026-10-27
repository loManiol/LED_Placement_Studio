#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  LED Placement Studio"
echo "============================================"
echo

if [ -f "venv/bin/python" ]; then
    echo "Using existing virtual environment..."
    # shellcheck disable=SC1091
    source venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    # shellcheck disable=SC1091
    source venv/bin/activate
    echo "Installing dependencies (first run only)..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi

echo
echo "Starting LED Placement Studio..."
echo
python main.py
