#!/usr/bin/env python
"""
Generate small SYNTHETIC sample data for the Overflights Dashboard.

This is fake data shaped like the real corridor dataset (same columns,
same rough ranges) so you can run and click through the dashboard without
the real ADS-B / NOAA extract from the VM. It is NOT real flight data —
don't use it for anything analytical.

Usage:
    python scripts/generate_sample_data.py [--out-dir DATA_DIR] [--seed 42]

By default writes into ../data (i.e. <repo_root>/data), matching the
default OVERFLIGHTS_DATA_DIR expected by app/config.py. Run this, then:

    cd app
    streamlit run app_overflights_dashboard.py

Files written:
    <out>/fuel_wind_rows_nov01_07_enriched_all.parquet   (row-level flight+wind+fuel/CO2)
    <out>/maneuver_summaries_v2/maneuvers_rows.parquet    (row-level maneuver flags)

It then invokes the repo's own ETL scripts
(app/etl/build_daily_fuel_co2_features.py and
app/etl/forecast_fuelandco2_next_week.py) so the daily-features and
forecast parquet files are produced by the real pipeline code, not
hand-faked — this also doubles as a smoke test of that pipeline.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

# Corridor bounding box (same as used by the app's map pages).
LAT_MIN, LAT_MAX = 39.0, 40.9
LON_MIN, LON_MAX = -76.9, -73.4
ALT_MIN, ALT_MAX = 20_000, 43_000

DAYS = pd.date_range("2025-11-01", "2025-11-07", freq="D")

# Rough "corners" of the corridor for each cardinal direction of travel,
# so headings/positions are internally consistent (not just random noise).
DIRECTIONS = {
    "N": {"start": (39.05, -75.15), "end": (40.85, -75.15), "heading": 0},
    "S": {"start": (40.85, -75.15), "end": (39.05, -75.15), "heading": 180},
    "E": {"start": (39.95, -76.8), "end": (39.95, -73.5), "heading": 90},
    "W": {"start": (39.95, -73.5), "end": (39.95, -76.8), "heading": 270},
}


def _rand_icao24(rng: np.random.Generator, n: int) -> list[str]:
    return ["".join(rng.choice(list("0123456789abcdef"), size=6)) for _ in range(n)]


def build_fuel_wind_rows(rng: np.random.Generator, aircraft_per_day: int = 45) -> pd.DataFrame:
    rows = []
    dir_names = list(DIRECTIONS.keys())

    for day in DAYS:
        icao24s = _rand_icao24(rng, aircraft_per_day)
        for icao24 in icao24s:
            direction = dir_names[rng.integers(0, len(dir_names))]
            leg = DIRECTIONS[direction]
            n_pts = int(rng.integers(20, 60))

            lat0, lon0 = leg["start"]
            lat1, lon1 = leg["end"]
            base_heading = leg["heading"]

            # Random start time during the day (UTC), spaced ~30-90s apart.
            start_offset_s = int(rng.integers(0, 22 * 3600))
            step_s = rng.integers(30, 90, size=n_pts)
            ts = day + pd.to_timedelta(start_offset_s, unit="s") + pd.to_timedelta(
                np.cumsum(step_s), unit="s"
            )

            frac = np.linspace(0, 1, n_pts)
            lat = lat0 + (lat1 - lat0) * frac + rng.normal(0, 0.01, n_pts)
            lon = lon0 + (lon1 - lon0) * frac + rng.normal(0, 0.01, n_pts)
            lat = np.clip(lat, LAT_MIN, LAT_MAX)
            lon = np.clip(lon, LON_MIN, LON_MAX)

            heading = (base_heading + rng.normal(0, 4, n_pts)) % 360

            # Altitude: mostly cruise with occasional step climb/descent.
            cruise_alt = rng.integers(ALT_MIN + 2000, ALT_MAX - 2000)
            alt_ft = cruise_alt + np.cumsum(rng.choice([0, 0, 0, 500, -500], size=n_pts))
            alt_ft = np.clip(alt_ft, ALT_MIN, ALT_MAX)

            spd_kts = rng.normal(460, 25, n_pts).clip(350, 560)

            wind_speed_mps = rng.normal(15, 6, n_pts).clip(0, None)
            wind_dir_deg = rng.uniform(0, 360, n_pts)
            wind_u = -wind_speed_mps * np.sin(np.deg2rad(wind_dir_deg))
            wind_v = -wind_speed_mps * np.cos(np.deg2rad(wind_dir_deg))

            # Fuel burn per row (kg), CO2 via a fixed combustion factor (~3.16 kg CO2/kg fuel).
            fuel_kg_row = rng.gamma(shape=2.0, scale=1.2, size=n_pts)
            co2_kg_row = fuel_kg_row * 3.16

            sturn_flag = (rng.random(n_pts) < 0.03).astype(int)

            rows.append(
                pd.DataFrame(
                    {
                        "day": day.date(),
                        "icao24": icao24,
                        "ts_utc": ts,
                        "lat": lat,
                        "lon": lon,
                        "alt_ft": alt_ft.astype(float),
                        "heading": heading,
                        "spd_kts": spd_kts,
                        "fuel_kg_row": fuel_kg_row,
                        "co2_kg_row": co2_kg_row,
                        "wind_u": wind_u,
                        "wind_v": wind_v,
                        "wind_speed": wind_speed_mps,
                        "wind_dir": wind_dir_deg,
                        "sturn_flag": sturn_flag,
                    }
                )
            )

    return pd.concat(rows, ignore_index=True)


def build_maneuvers_rows(fuel_wind_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Derive a smaller maneuver-flags table from a sample of the main rows."""
    sample = fuel_wind_df.sample(frac=0.35, random_state=rng.integers(0, 2**31 - 1)).copy()

    n = len(sample)
    is_hold = rng.random(n) < 0.02
    s_turn_flag = rng.random(n) < 0.03
    is_step = rng.random(n) < 0.05

    out = pd.DataFrame(
        {
            "ts_utc": sample["ts_utc"].to_numpy(),
            "icao24": sample["icao24"].to_numpy(),
            "lat": sample["lat"].to_numpy(),
            "lon": sample["lon"].to_numpy(),
            "alt_ft": sample["alt_ft"].to_numpy(),
            "is_hold": is_hold,
            "s_turn_flag": s_turn_flag,
            "is_step": is_step,
        }
    )
    return out.sort_values(["icao24", "ts_utc"]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "data",
        help="Directory to write sample parquet files into (default: <repo_root>/data)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--aircraft-per-day",
        type=int,
        default=45,
        help="Number of synthetic aircraft tracks per day (default: 45)",
    )
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "maneuver_summaries_v2").mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Generating synthetic row-level flight/wind/fuel data into {out_dir} ...")
    fuel_wind_df = build_fuel_wind_rows(rng, aircraft_per_day=args.aircraft_per_day)
    fuel_wind_path = out_dir / "fuel_wind_rows_nov01_07_enriched_all.parquet"
    fuel_wind_df.to_parquet(fuel_wind_path, index=False)
    print(f"[INFO] Wrote {len(fuel_wind_df):,} rows to {fuel_wind_path}")

    print("[INFO] Generating synthetic maneuver rows ...")
    maneuvers_df = build_maneuvers_rows(fuel_wind_df, rng)
    maneuvers_path = out_dir / "maneuver_summaries_v2" / "maneuvers_rows.parquet"
    maneuvers_df.to_parquet(maneuvers_path, index=False)
    print(f"[INFO] Wrote {len(maneuvers_df):,} rows to {maneuvers_path}")

    # Now run the repo's own ETL pipeline against this synthetic data so the
    # daily-features and forecast parquet files come from the real code path.
    env = {"OVERFLIGHTS_DATA_DIR": str(out_dir)}
    import os

    full_env = dict(os.environ)
    full_env.update(env)

    etl_dir = REPO_ROOT / "app" / "etl"
    for script in ["build_daily_fuel_co2_features.py", "forecast_fuelandco2_next_week.py"]:
        print(f"[INFO] Running {script} ...")
        result = subprocess.run(
            [sys.executable, str(etl_dir / script)],
            env=full_env,
            cwd=str(etl_dir),
        )
        if result.returncode != 0:
            print(f"[ERROR] {script} failed with exit code {result.returncode}", file=sys.stderr)
            return result.returncode

    print("[INFO] Done. Sample data is ready.")
    print(f"[INFO] Set OVERFLIGHTS_DATA_DIR={out_dir} if it's not the default ./data next to app/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
