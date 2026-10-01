#!/usr/bin/env bash
# Lab 01 - run the whole pipeline, in order. Stops at the first step that fails.

# -e: stop at the first command that fails
# -u: stop if a variable is used that was never set
# -o pipefail: a failure inside a pipe (a | b) counts as a failure too
set -euo pipefail

# go to the folder this script is in, so it works from anywhere
cd "$(dirname "$0")"

python extract.py       # 1. source -> raw files
python load.py          # 2. raw files -> database tables, with quality checks
python transform.py     # 3. raw tables -> result tables
python serve.py         # 4. result table -> screen and CSV file