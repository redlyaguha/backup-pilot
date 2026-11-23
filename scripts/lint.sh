#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else "нужен Python 3.11+")'
python3 "$ROOT/scripts/lint.py"
