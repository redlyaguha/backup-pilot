#!/bin/sh
set -eu
printf "commit: "
git rev-parse HEAD
id
cat /etc/os-release
python3 --version
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -S -B -m unittest discover -s tests -v
