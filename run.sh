#!/usr/bin/env bash
# Convenience wrapper: activates the venv and runs a command with it.
#   ./run.sh login_setup.py --all
#   ./run.sh orchestrator.py --headless
#   ./run.sh cli.py list
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "No venv found. Run ./setup.sh first." >&2
  exit 1
fi
source venv/bin/activate
exec python "$@"
