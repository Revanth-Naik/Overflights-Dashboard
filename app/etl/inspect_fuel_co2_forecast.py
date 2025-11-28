#!/usr/bin/env python
"""
Quick inspection of daily fuel & CO2 forecast.

- Reads the combined history + forecast parquet
- Prints a clean table
- Shows simple summary stats
"""

from __future__ import annotations

import duckdb
import pandas as pd
from pathlib import Path

FORECAST_PATH = Path(
    "/home/rghuglot/services/overflights/lib/overflight_data/fuel_co2_daily_forecast.parquet"
)


def load_forecast() -> pd.DataFrame:
    if not FORECAST_PATH.exists():
        raise SystemExit(f"[ERROR] Forecast file not found: {FORECAST_PATH}")

    con = duckdb.connect()
    df = con.execute(
        f"""
        SELECT
            day,
            fuel_kg,
            co2_kg,
            s_turn_rows,
            mean_spd_kts,
            mean_alt_ft,
            is_forecast
        FROM read_parquet('{FORECAST_PATH}')
        ORDER BY day
        """
    ).df()
    return df


def main() -> None:
    print(f"[INFO] Reading forecast from: {FORECAST_PATH}")
    df = load_forecast()

    # Split history vs forecast
    hist = df[~df["is_forecast"]].copy()
    fut = df[df["is_forecast"]].copy()

    pd.set_option("display.float_format", lambda x: f"{x:,.0f}")

    print("\n=== HISTORY (observed days) ===")
    print(hist)

    print("\n=== FORECAST (next days) ===")
    print(fut)

    # Simple summary numbers
    if not hist.empty and not fut.empty:
        last_hist = hist.iloc[-1]
        first_forecast = fut.iloc[0]

        print("\n=== SIMPLE SUMMARY ===")
        print(f"Last observed day: {last_hist['day']}")
        print(f"  fuel_kg: {last_hist['fuel_kg']:,.0f}")
        print(f"  co2_kg : {last_hist['co2_kg']:,.0f}")

        print(f"\nFirst forecast day: {first_forecast['day']}")
        print(f"  fuel_kg: {first_forecast['fuel_kg']:,.0f}")
        print(f"  co2_kg : {first_forecast['co2_kg']:,.0f}")

        fuel_change = (
            (first_forecast["fuel_kg"] - last_hist["fuel_kg"])
            / last_hist["fuel_kg"]
            * 100.0
        )
        co2_change = (
            (first_forecast["co2_kg"] - last_hist["co2_kg"])
            / last_hist["co2_kg"]
            * 100.0
        )

        print(f"\nChange fuel vs last day: {fuel_change:,.2f}%")
        print(f"Change CO₂ vs last day : {co2_change:,.2f}%")

        print("\nTotal forecast fuel (next week): "
              f"{fut['fuel_kg'].sum():,.0f} kg")
        print("Total forecast CO₂ (next week): "
              f"{fut['co2_kg'].sum():,.0f} kg")

    print("\n[INFO] Done.")


if __name__ == "__main__":
    main()
