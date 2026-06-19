"""End-to-end entry point: train models, save artifacts, print validation."""

from __future__ import annotations

import json

from evaluate import run_validation
from train_models import run_training


def main() -> None:
    metrics = run_training()
    print("\n=== Training metrics ===")
    print(json.dumps(metrics, indent=2))
    print("\n=== Inference validation ===")
    run_validation()


if __name__ == "__main__":
    main()
