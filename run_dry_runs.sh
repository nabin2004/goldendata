#!/usr/bin/env bash
# Script to dry run the first 10 Manim scenes from data/canonical/validated.jsonl
# Usage: ./run_dry_runs.sh [LIMIT]

set -e

LIMIT=${1:-10}
echo "=========================================================="
echo " Running Manim dry_run on first $LIMIT examples"
echo "=========================================================="

if command -v uv &> /dev/null; then
    PYTHONPATH=src uv run python scripts/dry_run_samples.py --limit "$LIMIT"
else
    PYTHONPATH=src python3 scripts/dry_run_samples.py --limit "$LIMIT"
fi
