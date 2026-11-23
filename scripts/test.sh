#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else "нужен Python 3.11+")'
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
