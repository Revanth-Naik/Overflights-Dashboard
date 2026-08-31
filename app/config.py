#!/usr/bin/env python
"""
Central data-path configuration for the Overflights Dashboard.

Every page and ETL script used to hardcode an absolute path to a specific
VM (`/home/rghuglot/services/overflights/lib/overflight_data/...`), which
meant the app only ran on that one machine. This module fixes that.

By default, data files are expected in a `data/` folder at the repo root
(next to `app/`, `docs/`, etc.):

    Overflights-Dashboard/
    ├── app/
    ├── data/                                          <- put parquet files here
    │   ├── fuel_wind_rows_nov01_07_enriched_all.parquet
    │   ├── fuel_co2_daily_features.parquet
    │   ├── fuel_co2_daily_forecast.parquet
    │   └── maneuver_summaries_v2/
    │       └── maneuvers_rows.parquet
    ├── docs/
    └── ...

To point at data living somewhere else (e.g. the original VM path, an
external drive, or a different data folder) without editing any code, set
the OVERFLIGHTS_DATA_DIR environment variable before running Streamlit:

    export OVERFLIGHTS_DATA_DIR=/home/rghuglot/services/overflights/lib/overflight_data
    streamlit run app_overflights_dashboard.py
"""

import os
from pathlib import Path

# Repo root = one level up from this file's directory (app/).
_REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(
    os.environ.get("OVERFLIGHTS_DATA_DIR", _REPO_ROOT / "data")
).expanduser().resolve()

# Row-level joined flight + wind + fuel/CO2 dataset (the big one).
FUEL_WIND_PATH = DATA_DIR / "fuel_wind_rows_nov01_07_enriched_all.parquet"

# Daily aggregated features built by app/etl/build_daily_fuel_co2_features.py
DAILY_FEATURES_PATH = DATA_DIR / "fuel_co2_daily_features.parquet"

# History + 7-day forecast built by app/etl/forecast_fuelandco2_next_week.py
FORECAST_PATH = DATA_DIR / "fuel_co2_daily_forecast.parquet"

# Row-level maneuver flags (holds / S-turns / step climbs).
MANEUVERS_ROWS_PATH = DATA_DIR / "maneuver_summaries_v2" / "maneuvers_rows.parquet"
