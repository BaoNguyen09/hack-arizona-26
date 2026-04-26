from __future__ import annotations

import argparse

from forecast_future_usage import forecast_from_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forecast future hourly state electricity usage.")
    parser.add_argument("--start", required=True, help="Forecast start timestamp, e.g. 2026-04-27T14:00:00Z.")
    parser.add_argument("--end", help="Exclusive forecast end timestamp.")
    parser.add_argument("--hours", type=int, help="Number of hourly periods to forecast.")
    parser.add_argument("--states", help="Optional comma-separated state codes, e.g. CA,TX,NY.")
    parser.add_argument("--model", default="electricity_usage_model.pkl", help="Pickled trained model path.")
    parser.add_argument("--history", default="state_energy_timeseries.csv", help="Historical state data CSV.")
    parser.add_argument("--output", default="state_usage_forecast.csv", help="Forecast CSV output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    states = [state.strip() for state in args.states.split(",")] if args.states else None
    forecast = forecast_from_files(
        start=args.start,
        end=args.end,
        hours=args.hours,
        states=states,
        model_path=args.model,
        history_path=args.history,
    )
    forecast.to_csv(args.output, index=False)
    print(f"Wrote {len(forecast):,} forecast rows to {args.output}")


if __name__ == "__main__":
    main()
