#!/usr/bin/env bash
# One-time setup for Linux / macOS. Usage: ./setup.sh
set -e
cd "$(dirname "$0")"

PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.10+ first." >&2
  exit 1
fi

echo "[1/3] Creating virtualenv..."
if [ ! -d venv ]; then "$PY" -m venv venv; fi
source venv/bin/activate

echo "[2/3] Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[3/3] Installing Chromium for Playwright..."
python -m playwright install chromium

echo
echo "Setup complete. Next steps:"
echo "  python login_setup.py --all   # once, to log into each service"
echo "  python cli.py add gemini \"my prompt\""
echo "  python cli.py run"
