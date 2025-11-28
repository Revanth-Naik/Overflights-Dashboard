#!/usr/bin/env python
"""
05_Wind_tables_and_roses.py

Weekly wind tables and roses page for the Airspace Overflights dashboard.

This page reads the joined RAP / flight parquet
    fuel_wind_rows_nov01_07_enriched_all.parquet
with DuckDB and *aggregates inside DuckDB* so we never load the full
1.4 GB dataset into memory.

It shows:
1. Wind magnitude heatmap – mean wind speed (kt) at 00 / 06 / 12 / 18 UTC.
2. Wind direction heatmap – circular mean wind direction (deg) at the same times.
3. Daily wind-rose row – one small rose per day, showing how direction is distributed.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

DATA_PATH = Path(
    "/home/rghuglot/services/overflights/lib/overflight_data/"
    "fuel_wind_rows_nov01_07_enriched_all.parquet"
)

SUMMARY_HOURS: List[int] = [0, 6, 12, 18]


# ---------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------


def hour_labels() -> List[str]:
    """Pretty labels for the Y axis in UTC."""
    return [f"{h:02d}:00" for h in SUMMARY_HOURS]


def day_labels(days: List[object]) -> List[str]:
    """Pretty labels for the X axis (e.g., 'Nov 1')."""
    labels: List[str] = []
    for d in days:
        d_ts = pd.to_datetime(d)
        labels.append(d_ts.strftime("%b %-d"))
    return labels


# ---------------------------------------------------------------------
# Data loading with DuckDB (fast + memory-safe)
# ---------------------------------------------------------------------


@st.cache_data(show_spinner="Loading 4-times-per-day wind grids from DuckDB…")
def load_speed_and_dir_grids() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return (speed_grid, dir_grid) with index = hour_utc (0,6,12,18),
    columns = day, values = mean speed / mean direction.

    All aggregation happens in DuckDB; pandas only sees the tiny summary table.
    """
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"{DATA_PATH} not found")

    con = duckdb.connect()

    # One query to compute both mean speed and circular mean direction.
    sql = f"""
        WITH base AS (
            SELECT
                ts_utc,
                date_trunc('day', ts_utc)::DATE AS day,
                wind_speed,
                wind_dir
            FROM read_parquet('{DATA_PATH.as_posix()}')
        ),
        four_hour AS (
            SELECT
                /* bucket into 0 / 6 / 12 / 18 UTC */
                (extract('hour' FROM ts_utc)::INT / 6) * 6 AS hour_utc,
                day,
                wind_speed,
                wind_dir
            FROM base
        )
        SELECT
            hour_utc,
            day,
            avg(wind_speed) AS mean_speed,
            /* circular mean in DuckDB (deg, 0–360) */
            (
                atan2(
                    avg(sin(wind_dir * pi() / 180.0)),
                    avg(cos(wind_dir * pi() / 180.0))
                ) * 180.0 / pi()
            ) AS mean_dir_deg_raw
        FROM four_hour
        WHERE hour_utc IN (0, 6, 12, 18)
        GROUP BY 1, 2
        ORDER BY day, hour_utc;
    """

    df = con.execute(sql).df()
    con.close()

    # Normalize direction into 0–360
    df["mean_dir_deg"] = (df["mean_dir_deg_raw"] + 360.0) % 360.0

    # Pivot to grids
    speed_grid = (
        df.pivot(index="hour_utc", columns="day", values="mean_speed")
        .reindex(index=SUMMARY_HOURS)
        .sort_index(axis=1)
    )

    dir_grid = (
        df.pivot(index="hour_utc", columns="day", values="mean_dir_deg")
        .reindex(index=SUMMARY_HOURS)
        .sort_index(axis=1)
    )

    # Drop days that are all-NaN in BOTH grids
    valid_cols = [
        c
        for c in speed_grid.columns
        if not (speed_grid[c].isna().all() and dir_grid[c].isna().all())
    ]
    speed_grid = speed_grid[valid_cols]
    dir_grid = dir_grid[valid_cols]

    return speed_grid, dir_grid


@st.cache_data(show_spinner="Loading daily wind-rose counts from DuckDB…")
def load_wind_rose_counts() -> pd.DataFrame:
    """
    Return a small table with columns:
        day, dir_bin (0,30,...,330), count

    Again, everything is aggregated in DuckDB.
    """
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"{DATA_PATH} not found")

    con = duckdb.connect()

    sql = f"""
        WITH base AS (
            SELECT
                date_trunc('day', ts_utc)::DATE AS day,
                /* wrap into 0–360 just in case */
                mod(wind_dir, 360.0) AS wind_dir
            FROM read_parquet('{DATA_PATH.as_posix()}')
        )
        SELECT
            day,
            floor(wind_dir / 30.0) * 30.0 AS dir_bin,
            count(*) AS n
        FROM base
        GROUP BY 1, 2
        ORDER BY 1, 2;
    """

    df = con.execute(sql).df()
    con.close()
    return df


# ---------------------------------------------------------------------
# Plotly figure builders
# ---------------------------------------------------------------------


def make_speed_heatmap(speed_grid: pd.DataFrame) -> go.Figure:
    """Plotly heatmap for mean wind speed."""
    if speed_grid.empty:
        return go.Figure()

    y = hour_labels()
    x = day_labels(list(speed_grid.columns))

    fig = go.Figure(
        data=go.Heatmap(
            z=speed_grid.to_numpy(),
            x=x,
            y=y,
            colorscale="OrRd",
            colorbar=dict(title="kt"),
            hovertemplate=(
                "Day: %{x}<br>"
                "UTC hour: %{y}<br>"
                "Wind speed: %{z:.1f} kt<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title="Wind Magnitude (knots) – 00 / 06 / 12 / 18 UTC",
        template="plotly_dark",
        xaxis_title="Day",
        yaxis_title="UTC hour",
        margin=dict(l=60, r=40, t=60, b=60),
        height=400,
    )
    return fig


def make_dir_heatmap(dir_grid: pd.DataFrame) -> go.Figure:
    """Plotly heatmap for circular mean wind direction."""
    if dir_grid.empty:
        return go.Figure()

    y = hour_labels()
    x = day_labels(list(dir_grid.columns))

    fig = go.Figure(
        data=go.Heatmap(
            z=dir_grid.to_numpy(),
            x=x,
            y=y,
            colorscale="Greens",
            colorbar=dict(title="deg"),
            zmin=0,
            zmax=360,
            hovertemplate=(
                "Day: %{x}<br>"
                "UTC hour: %{y}<br>"
                "Dir: %{z:.0f}°<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title="Wind Direction (degrees) – 00 / 06 / 12 / 18 UTC",
        template="plotly_dark",
        xaxis_title="Day",
        yaxis_title="UTC hour",
        margin=dict(l=60, r=40, t=60, b=60),
        height=400,
    )
    return fig


def make_wind_rose_grid_from_counts(df_counts: pd.DataFrame) -> go.Figure:
    """
    Build a row of daily wind-rose plots from the aggregated counts table
    (columns: day, dir_bin, n).
    """
    if df_counts.empty:
        return go.Figure()

    groups = list(df_counts.groupby("day"))
    n_days = len(groups)
    if n_days == 0:
        return go.Figure()

    # Fixed 30° bins
    all_bins = np.arange(0, 360, 30)

    fig = make_subplots(
        rows=1,
        cols=n_days,
        specs=[[{"type": "polar"}] * n_days],
        horizontal_spacing=0.03,
        subplot_titles=[pd.to_datetime(d).strftime("%b %-d") for d, _ in groups],
    )

    for idx, (d, sub) in enumerate(groups, start=1):
        # ensure we have all bins in order
        counts = (
            sub.set_index("dir_bin")["n"]
            .reindex(all_bins, fill_value=0)
            .to_numpy()
        )

        theta = all_bins  # degrees

        fig.add_trace(
            go.Barpolar(
                r=counts,
                theta=theta,
                marker=dict(color="#7fcdbb", line=dict(width=0)),
                opacity=0.9,
                showlegend=False,
                name=pd.to_datetime(d).strftime("%Y-%m-%d"),
            ),
            row=1,
            col=idx,
        )

        fig.update_polars(
            radialaxis=dict(showticklabels=False, ticks="", showgrid=False),
            angularaxis=dict(
                direction="clockwise",
                rotation=90,  # 0° at top (north)
                showgrid=False,
            ),
            bgcolor="rgba(0,0,0,0)",
            row=1,
            col=idx,
        )

    fig.update_layout(
        template="plotly_dark",
        title="Daily wind-rose row (30° direction bins, counts)",
        margin=dict(l=20, r=20, t=60, b=20),
        height=320,
    )
    return fig


# ---------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------


def main() -> None:
    st.title("Weekly wind tables and roses")

    st.markdown(
        """
This page shows **one week of winds in the corridor** using the same Plotly
styling as the **Winds** page:

1. **Wind magnitude heatmap** – mean wind speed (kt) at 00/06/12/18 UTC.  
2. **Wind direction heatmap** – circular mean direction (°) at the same times.  
3. **Daily wind-rose row** – one rose per day, showing how wind direction is distributed.

All stats are computed from the joined RAP / flight dataset:
"""
    )
    st.code(DATA_PATH.name, language="bash")

    # ---- Load aggregated data (fast) ----
    try:
        speed_grid, dir_grid = load_speed_and_dir_grids()
        df_rose_counts = load_wind_rose_counts()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load wind data: {exc!s}")
        return

    # ---- Heatmaps stacked vertically ----
    fig_speed = make_speed_heatmap(speed_grid)
    if not fig_speed.data:
        st.info("No data available for the wind-speed heatmap.")
    else:
        st.plotly_chart(fig_speed, width="stretch")

    fig_dir = make_dir_heatmap(dir_grid)
    if not fig_dir.data:
        st.info("No data available for the wind-direction heatmap.")
    else:
        st.plotly_chart(fig_dir, width="stretch")

    # ---- Daily wind-rose row ----
    st.markdown("### Daily wind-rose row")
    st.caption(
        "Each polar plot shows the distribution of wind direction for that day "
        "in 30° bins (counts of corridor points)."
    )

    fig_rose = make_wind_rose_grid_from_counts(df_rose_counts)
    if not fig_rose.data:
        st.info("No wind-rose data available for this week.")
    else:
        st.plotly_chart(fig_rose, width="stretch")


if __name__ == "__main__":
    main()
