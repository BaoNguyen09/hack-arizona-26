from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import pandas as pd

from electricity_cost_model import predict_usage_by_state, train_electricity_usage_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the all-state electricity usage model from a CSV.")
    parser.add_argument("--input", default="state_energy_timeseries.csv", help="Model-ready CSV from the fetch helper.")
    parser.add_argument("--model-output", default="electricity_usage_model.pkl", help="Where to save the fitted model.")
    parser.add_argument("--metrics-output", default="electricity_usage_metrics.json", help="Where to save test metrics.")
    parser.add_argument("--predictions-output", help="Optional CSV of in-sample predictions.")
    parser.add_argument("--target", default="total_kw_usage", help="Target column. Current generated CSV uses total_kw_usage.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Latest fraction of timestamps to hold out.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    frame = pd.read_csv(input_path)
    fitted_model, metrics = train_electricity_usage_model(
        frame,
        target=args.target,
        test_size=args.test_size,
    )

    with open(args.model_output, "wb") as handle:
        pickle.dump(fitted_model, handle)

    with open(args.metrics_output, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"Saved model to {args.model_output}")
    print(f"Saved metrics to {args.metrics_output}")

    if args.predictions_output:
        predictions = predict_usage_by_state(fitted_model, frame)
        predictions.to_csv(args.predictions_output, index=False)
        print(f"Saved predictions to {args.predictions_output}")


if __name__ == "__main__":
    main()
