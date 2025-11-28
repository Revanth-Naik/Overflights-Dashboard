#!/usr/bin/env python
"""
forecast_fuelandco2_next_week.py

Use the daily aggregated features (fuel_co2_daily_features.parquet)
to produce a simple 7-day forecast for total fuel_kg and co2_kg.

This script is intentionally lightweight:
- It only reads the small daily features parquet (7 rows).
- It uses simple linear regression via numpy.polyfit (no heavy ML).
- It writes both the history and the forecast into one parquet file
  so the dashboard can plot them together easily.
"""

from __future__ import annotations

import sys
from datetime import timedelta

from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Paths (adjust only if you change your directory layout)
# ---------------------------------------------------------------------
FEATURES_PATH = Path(
    "/home/rghuglot/services/overflights/lib/overflight_data/fuel_co2_daily_features.parquet"
)
FORECAST_OUT = Path(
    "/home/rghuglot/services/overflights/lib/overflight_data/fuel_co2_daily_forecast.parquet"
)


def fit_linear_trend(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """
    Fit a simple linear trend y = a * x + b using numpy.polyfit.
    Returns (a, b).
    """
    # Guard: if all y identical or length < 2, just return flat line
    if len(y) < 2 or np.allclose(y, y[0]):
        return 0.0, float(y.mean())

    a, b = np.polyfit(x, y, 1)
    return float(a), float(b)


def build_forecast(df_daily: pd.DataFrame, horizon_days: int = 7) -> pd.DataFrame:
    """
    Given a small daily dataframe with columns:
        day, fuel_kg, co2_kg, s_turn_rows, mean_spd_kts, mean_alt_ft
    create a 7-day forecast for fuel_kg and co2_kg.

    Returns a dataframe with both history and forecast and a column:
        is_forecast: False for history, True for forecast rows
    """
    # Ensure day is datetime
    df = df_daily.copy()
    df["day"] = pd.to_datetime(df["day"])

    # Use index 0..n-1 as the time variable
    df = df.sort_values("day").reset_index(drop=True)
    x_hist = np.arange(len(df), dtype=float)

    # Fit linear trends for fuel and co2
    a_fuel, b_fuel = fit_linear_trend(x_hist, df["fuel_kg"].values)
    a_co2, b_co2 = fit_linear_trend(x_hist, df["co2_kg"].values)

    # Build future x positions
    last_x = x_hist[-1]
    x_future = np.arange(last_x + 1, last_x + 1 + horizon_days, dtype=float)

    # Predict
    fuel_pred = a_fuel * x_future + b_fuel
    co2_pred = a_co2 * x_future + b_co2

    # Clip to non-negative just in case
    fuel_pred = np.clip(fuel_pred, 0, None)
    co2_pred = np.clip(co2_pred, 0, None)

    # Build future dates: 1..horizon_days after last day in history
    last_day = df["day"].max()
    future_days = [last_day + timedelta(days=i) for i in range(1, horizon_days + 1)]

    df_future = pd.DataFrame(
        {
            "day": future_days,
            "fuel_kg": fuel_pred,
            "co2_kg": co2_pred,
        }
    )

    # Carry over some simple context columns by using the last known values
    for col in ["s_turn_rows", "mean_spd_kts", "mean_alt_ft"]:
        if col in df.columns:
            df_future[col] = df[col].iloc[-1]

    # Mark history vs forecast
    df["is_forecast"] = False
    df_future["is_forecast"] = True

    # Combine
    df_all = pd.concat([df, df_future], ignore_index=True)
    return df_all


def main() -> int:
    print(f"[INFO] Reading daily features from: {FEATURES_PATH}")
    if not FEATURES_PATH.exists():
        print(f"[ERROR] Features file not found: {FEATURES_PATH}", file=sys.stderr)
        return 1

    df_daily = pd.read_parquet(FEATURES_PATH)
    if df_daily.empty:
        print("[ERROR] Daily features file is empty.", file=sys.stderr)
        return 1

    print("[INFO] Daily features (history):")
    print(df_daily)

    print("[INFO] Building 7-day forecast …")
    df_all = build_forecast(df_daily, horizon_days=7)

    print("[INFO] Combined history + forecast:")
    print(df_all)

    print(f"[INFO] Writing forecast parquet to: {FORECAST_OUT}")
    FORECAST_OUT.parent.mkdir(parents=True, exist_ok=True)
    df_all.to_parquet(FORECAST_OUT, index=False)

    print("[INFO] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
