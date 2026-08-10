#!/usr/bin/env bash
# Sets up the venv if needed, then rebuilds templates.json and the site from
# apps/ and stacks/. Does not touch Docker Hub - run `gallery fetch-metadata`
# separately (or let the scheduled refresh-dockerhub workflow do it) to
# refresh cache/dockerhub.json.
# Any extra arguments are passed through to `gallery build` (e.g. --repo-url).
set -euo pipefail
cd "$(dirname "$0")"

VENV_DIR=".venv"
PYTHON_BIN="python3"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN="python"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
  echo "==> Creating virtual environment..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> Installing dependencies..."
pip install -q -e .

echo "==> Building templates.json and the website..."
python -m gallery build "$@"

echo "==> Validating templates.json..."
python -m gallery validate

echo "Done. templates.json and docs/ are up to date."
