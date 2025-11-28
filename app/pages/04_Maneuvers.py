#!/usr/bin/env python
"""
pages/04_Maneuvers.py

Maneuvers page: holds, S-turns, step climbs/descents.

This version:
- Reads ONLY maneuvers_rows.parquet.
- Converts UTC timestamps to local EST for daily/hourly stats.
- Builds the daily summary (hold_rows, s_turn_rows, step_rows,
  aircraft_with_maneuver) directly from that rows file.
- Limits the map to the BWI–NY corridor.
- Uses Plotly (no Matplotlib) so it blends with the Winds page.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ---------------------------------------------------------------------
# Paths – adjust if you move the data
# ---------------------------------------------------------------------

BASE = Path("/home/rghuglot/services/overflights")
LIB = BASE / "lib" / "overflight_data"

ROWS_PATH = LIB / "maneuver_summaries_v2" / "maneuvers_rows.parquet"

# BWI–NY corridor bounds (same idea as Flight Tracks page)
CORRIDOR_LAT_MIN = 39.0
CORRIDOR_LAT_MAX = 40.9
CORRIDOR_LON_MIN = -76.9
CORRIDOR_LON_MAX = -73.4


# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------


@st.cache_data(show_spinner="Loading maneuver rows…")
def load_rows() -> pd.DataFrame:
    """Load the per-row maneuvers file and attach EST-based time columns."""
    df = pd.read_parquet(ROWS_PATH)

    if "ts_utc" not in df.columns:
        raise ValueError("Expected ts_utc column in maneuvers_rows.parquet")

    # Ensure ts_utc is datetime
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], errors="coerce")

    # Handle timezone safely:
    # - If tz-naive: localize to UTC
    # - If already tz-aware: just convert to UTC (no tz_localize!)
    if df["ts_utc"].dt.tz is None:
        df["ts_utc"] = df["ts_utc"].dt.tz_localize("UTC")
    else:
        df["ts_utc"] = df["ts_utc"].dt.tz_convert("UTC")

    # Convert to corridor local time (EST/EDT via America/New_York)
    df["ts_est"] = df["ts_utc"].dt.tz_convert("America/New_York")

    # EST-based day and hour for plots
    df["day_est"] = df["ts_est"].dt.floor("D")
    df["hour_est"] = df["ts_est"].dt.hour

    return df


def build_daily_summary(df_rows: pd.DataFrame) -> pd.DataFrame:
    """
    Build a daily summary from the maneuver rows in **EST days**.

    Output columns (when possible):
      - day          (EST date)
      - hold_rows
      - s_turn_rows
      - step_rows
      - aircraft_with_maneuver
    """
    if "day_est" not in df_rows.columns:
        raise ValueError("Expected day_est column in maneuver rows dataframe")

    df = df_rows.copy()

    # Which flag columns are present?
    flag_cols = [c for c in ["is_hold", "s_turn_flag", "is_step"] if c in df.columns]
    if not flag_cols:
        raise ValueError(
            "No maneuver flag columns (is_hold, s_turn_flag, is_step) found "
            "in maneuvers_rows.parquet"
        )

    agg_kwargs = {}
    if "is_hold" in df.columns:
        agg_kwargs["hold_rows"] = ("is_hold", "sum")
    if "s_turn_flag" in df.columns:
        agg_kwargs["s_turn_rows"] = ("s_turn_flag", "sum")
    if "is_step" in df.columns:
        agg_kwargs["step_rows"] = ("is_step", "sum")

    daily = df.groupby("day_est").agg(**agg_kwargs).reset_index()

    # Aircraft with ≥1 maneuver per EST day
    if "icao24" in df.columns:
        df["any_maneuver"] = df[flag_cols].any(axis=1)
        ac_per_day = (
            df[df["any_maneuver"]]
            .groupby("day_est")["icao24"]
            .nunique()
            .rename("aircraft_with_maneuver")
        )
        daily = daily.merge(ac_per_day, on="day_est", how="left")
    else:
        daily["aircraft_with_maneuver"] = np.nan

    # Make sure counts are integers
    for col in daily.columns:
        if col != "day_est":
            daily[col] = daily[col].fillna(0).astype(int)

    # Rename day_est → day for plotting labels
    daily = daily.rename(columns={"day_est": "day"})

    return daily.sort_values("day")


# ---------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------


def make_daily_bar_figure(df: pd.DataFrame) -> go.Figure:
    """
    Stacked "report-style" daily maneuver bar figure using make_subplots.
    Days are EST corridor days.
    """
    metrics = [
        ("hold_rows", "Hold rows per day", "Hold rows per day"),
        ("s_turn_rows", "S-turn rows per day", "S-turn rows per day"),
        ("step_rows", "Step climb/desc rows per day", "Step climb/desc rows per day"),
        (
            "aircraft_with_maneuver",
            "Aircraft with ≥1 maneuver per day",
            "Aircraft with ≥1 maneuver per day",
        ),
    ]

    # Keep only metrics that actually exist
    metrics = [m for m in metrics if m[0] in df.columns]
    n_rows = len(metrics)
    if n_rows == 0:
        raise ValueError("No metric columns found in daily maneuver summary.")

    df = df.copy().sort_values("day")
    x_vals = df["day"]

    colors = ["#22c55e", "#3b82f6", "#f97316", "#ef4444"]

    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
    )

    for idx, (col, title, _y_label) in enumerate(metrics, start=1):
        avg_val = float(df[col].mean())

        fig.add_trace(
            go.Bar(
                x=x_vals,
                y=df[col],
                name=title,
                marker_color=colors[(idx - 1) % len(colors)],
                showlegend=False,
            ),
            row=idx,
            col=1,
        )

        fig.add_hline(
            y=avg_val,
            line_dash="dash",
            line_color="#9ca3af",
            annotation_text=f"avg ≈ {avg_val:,.0f}",
            annotation_font=dict(size=11, color="#9ca3af"),
            annotation_position="top right",
            row=idx,
            col=1,
        )

        fig.update_yaxes(title_text="Count", row=idx, col=1)

    fig.update_layout(
        height=800,
        margin=dict(l=70, r=40, t=40, b=60),
        template="plotly_dark",
        bargap=0.25,
    )

    fig.update_xaxes(
        row=n_rows,
        col=1,
        tickformat="%b %-d",
        title_text="Day (EST)",
    )

    return fig


def make_hourly_hist_figure(df_rows: pd.DataFrame) -> go.Figure:
    """
    Compact histogram: maneuver rows per local hour of day (EST).
    """
    if "hour_est" not in df_rows.columns:
        raise ValueError("hour_est column missing in maneuver rows dataframe")

    df = df_rows.copy()
    counts = df.groupby("hour_est").size().reset_index(name="rows")

    fig = px.bar(
        counts,
        x="hour_est",
        y="rows",
        labels=dict(hour_est="Hour of day (EST)", rows="Maneuver rows"),
        title="Maneuver rows by hour of day (local corridor time, EST)",
    )
    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=70, r=40, t=60, b=60),
    )
    return fig


def make_maneuver_map(df_rows: pd.DataFrame) -> go.Figure | None:
    """
    Map of maneuver locations, sampled for speed,
    restricted to the BWI–NY corridor.
    """
    if not {"lat", "lon"}.issubset(df_rows.columns):
        return None

    df = df_rows.copy()

    # Corridor bounding box: only BWI–NY corridor
    df = df[
        (df["lat"].between(CORRIDOR_LAT_MIN, CORRIDOR_LAT_MAX))
        & (df["lon"].between(CORRIDOR_LON_MIN, CORRIDOR_LON_MAX))
    ]

    if df.empty:
        return None

    def classify(row):
        if row.get("is_hold", False):
            return "Hold"
        if row.get("s_turn_flag", False):
            return "S-turn"
        if row.get("is_step", False):
            return "Step climb/desc"
        return "Other"

    df["maneuver_type"] = df.apply(classify, axis=1)

    # Sample for performance
    max_points = 15000
    if len(df) > max_points:
        df = df.sample(max_points, random_state=42)

    fig = px.scatter_mapbox(
        df,
        lat="lat",
        lon="lon",
        color="maneuver_type",
        hover_data=[c for c in ["icao24", "alt_ft"] if c in df.columns],
        zoom=6.3,
        center=dict(lat=40.0, lon=-75.2),
        height=500,
    )
    fig.update_layout(
        mapbox_style="carto-positron",
        margin=dict(l=0, r=0, t=30, b=0),
        legend_title_text="Maneuver type",
        template="plotly_dark",
    )
    return fig


# ---------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="Maneuvers", page_icon="🌀", layout="wide")

    st.title("Daily maneuver statistics (report-style)")

    st.markdown(
        """
This page shows **holds**, **S-turns**, and **step climbs/descents**
in the corridor for the week, using Plotly charts so they match the
**Winds** page style.

- **Daily bars** use **EST days** (local corridor time).  
- **Hour-of-day histogram** uses **local hours (EST)** where possible.  

**Top figure:** stacked daily bars (one row per metric).  
**Middle figure:** a compact histogram of maneuver rows by hour of day (EST).  
**Bottom:** a sampled map of where maneuvers occur inside the BWI–NY corridor.
        """
    )

    # Load maneuver rows once
    try:
        df_rows = load_rows()
    except Exception as exc:
        st.error(f"Could not load maneuver rows data: {exc}")
        return

    # Build daily summary from rows
    try:
        df_daily = build_daily_summary(df_rows)
    except Exception as exc:
        st.error(f"Could not build daily maneuver summary from rows: {exc}")
        return

    # ---- Daily stacked bars -----------------------------------------
    try:
        fig_daily = make_daily_bar_figure(df_daily)
        st.plotly_chart(fig_daily, width="stretch")
    except Exception as exc:
        st.error(f"Error building daily maneuver figure: {exc}")

    st.divider()

    # ---- Hourly histogram -------------------------------------------
    st.subheader("Maneuver rows by hour of day (local, EST)")
    try:
        fig_hour = make_hourly_hist_figure(df_rows)
        st.plotly_chart(fig_hour, width="stretch")
    except Exception as exc:
        st.error(f"Error building hourly histogram: {exc}")

    st.divider()

    # ---- Map ---------------------------------------------------------
    st.subheader("Where do maneuvers occur in the BWI–NY corridor?")
    fig_map = make_maneuver_map(df_rows)
    if fig_map is None:
        st.info(
            "Maneuver rows either lack lat/lon or none fall inside "
            "the BWI–NY corridor, so the map cannot be drawn."
        )
    else:
        st.plotly_chart(fig_map, width="stretch")


if __name__ == "__main__":
    main()
