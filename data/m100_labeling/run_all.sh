#!/usr/bin/env bash
# Regenerate everything from the ORIGINAL csv (read-only). Run from the repository root.
set -euo pipefail
INPUT="${1:-data/m100_node1_digital_twin.csv}"
OUT="${2:-outputs/labeled_dataset}"
python ml_labeling/build_labeled_dataset.py --input "$INPUT" --output-dir "$OUT"
python ml_labeling/train_baselines.py --data-dir "$OUT"
