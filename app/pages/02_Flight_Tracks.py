"""
02_Flight_Tracks.py

Flight tracks page for the overflights dashboard.
Shows one corridor day at a time, with filters for
enter / exit altitude bands, directions, and sampling.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import duckdb
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import FUEL_WIND_PATH as DATA_PATH

ALT_MIN = 20_000
ALT_MAX = 43_000

MAX_POINTS_HARD_CAP = 200_000  # safety so map never explodes


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


@st.cache_data(show_spinner="Loading available days…")
def get_available_days() -> list[pd.Timestamp]:
    """Return sorted unique days from the parquet."""
    con = duckdb.connect()
    sql = f"""
        SELECT DISTINCT day
        FROM read_parquet('{DATA_PATH}')
        ORDER BY day
    """
    df = con.execute(sql).df()
    con.close()
    return list(pd.to_datetime(df["day"]).dt.date)


@st.cache_data(show_spinner="Loading flight track dataset…")
def load_tracks(selected_day: str) -> pd.DataFrame:
    """
    Load one day of tracks from DuckDB, and attach per-aircraft
    enter / exit altitudes using window functions.

    Returns a DataFrame with columns:
      day, icao24, ts_utc, lat, lon, alt_ft, heading,
      enter_alt_ft, exit_alt_ft, enter_heading, exit_heading
    """
    con = duckdb.connect()
    sql = f"""
        WITH base AS (
            SELECT
                day,
                icao24,
                ts_utc,
                lat,
                lon,
                alt_ft,
                heading
            FROM read_parquet('{DATA_PATH}')
            WHERE
                day = DATE '{selected_day}'
                AND alt_ft BETWEEN {ALT_MIN} AND {ALT_MAX}
        ),
        extents AS (
            SELECT
                *,
                MIN(alt_ft) OVER (PARTITION BY icao24) AS enter_alt_ft,
                MAX(alt_ft) OVER (PARTITION BY icao24) AS exit_alt_ft,
                FIRST_VALUE(heading) OVER (
                    PARTITION BY icao24
                    ORDER BY ts_utc
                ) AS enter_heading,
                LAST_VALUE(heading) OVER (
                    PARTITION BY icao24
                    ORDER BY ts_utc
                    ROWS BETWEEN UNBOUNDED PRECEDING
                         AND UNBOUNDED FOLLOWING
                ) AS exit_heading
            FROM base
        )
        SELECT *
        FROM extents
        ORDER BY icao24, ts_utc
    """
    df = con.execute(sql).df()
    con.close()
    return df


def _heading_to_cardinal_scalar(hdg: float) -> str:
    """
    Convert a single heading (degrees) to N/E/S/W,
    using 45° sectors centered on 0, 90, 180, 270.
    """
    if pd.isna(hdg):
        return "X"

    hdg = float(hdg) % 360.0

    if (hdg >= 315.0) or (hdg < 45.0):
        return "N"
    if 45.0 <= hdg < 135.0:
        return "E"
    if 135.0 <= hdg < 225.0:
        return "S"
    if 225.0 <= hdg < 315.0:
        return "W"
    return "X"


def classify_direction_from_enter_exit(enter_hdg: float, exit_hdg: float) -> str:
    """
    Apply Dr. Sherry's rule:

    - S-to-N: enters and exits with heading >315 or <45  (N)
    - N-to-S: enters and exits with heading 135–225     (S)
    - E-to-W: enters and exits with heading 45–135      (E)
    - W-to-E: enters and exits with heading 225–315     (W)

    We compute the cardinal for each, and only keep it if
    enter and exit are in the same sector. Otherwise return "X".
    """
    enter_label = _heading_to_cardinal_scalar(enter_hdg)
    exit_label = _heading_to_cardinal_scalar(exit_hdg)

    if enter_label == exit_label and enter_label in {"N", "E", "S", "W"}:
        return enter_label
    return "X"


def fast_sample(df: pd.DataFrame, max_aircraft: int, max_points: int) -> pd.DataFrame:
    """
    Down-sample by:
      1) Randomly choosing up to `max_aircraft` unique icao24,
      2) Then sub-sampling rows to at most `max_points`.
    """
    if df.empty:
        return df

    # Step 1: limit number of aircraft
    ac = df["icao24"].unique()
    if len(ac) > max_aircraft:
        chosen = np.random.choice(ac, size=max_aircraft, replace=False)
        df = df[df["icao24"].isin(chosen)]

    # Step 2: limit total points
    if len(df) > max_points:
        idx = np.linspace(0, len(df) - 1, max_points).astype(int)
        df = df.iloc[idx]

    return df


def make_flight_map(df: pd.DataFrame):
    """
    Build the Plotly map figure using line_map (MapLibre-based; replaces the
    deprecated/removed line_mapbox in Plotly >= 6) and the cardinal_direction
    colors. Also overlays the corridor NAVAIDs.
    """
    if df.empty:
        return None

    color_map = {
        "N": "#1f77b4",  # blue
        "E": "#ff7f0e",  # orange
        "S": "#d62728",  # red
        "W": "#2ca02c",  # green
    }

    fig = px.line_map(
        df,
        lat="lat",
        lon="lon",
        color="cardinal_direction",
        color_discrete_map=color_map,
        hover_data={
            "icao24": True,
            "cardinal_direction": True,
            "alt_ft": True,
            "ts_utc": True,
            "lat": False,
            "lon": False,
        },
        zoom=6.3,
        height=650,
    )

    fig.update_layout(
        map_style="carto-positron",
        margin=dict(l=0, r=0, t=0, b=0),
        legend_title_text="Direction",
    )

    # ----------------- NAVAIDs overlay -----------------
    navaids = [
        # Kennedy
        {"id": "JFK", "lat": 40.6328839, "lon": -73.7713917},
        # Robbinsville
        {"id": "RBV", "lat": 40.2024022, "lon": -74.4950261},
        # Coyle
        {"id": "CYN", "lat": 39.8173381, "lon": -74.4316258},
        # Sea Isle
        {"id": "SIE", "lat": 39.0955089, "lon": -74.8003439},
        # Lancaster
        {"id": "LRP", "lat": 40.1199756, "lon": -76.2912953},
        # Armel
        {"id": "AML", "lat": 38.9345925, "lon": -77.4667017},
    ]

    fig.add_scattermap(
        lat=[n["lat"] for n in navaids],
        lon=[n["lon"] for n in navaids],
        mode="markers+text",
        marker=dict(size=9, color="black"),
        text=[n["id"] for n in navaids],
        textposition="top center",
        name="NAVAIDs",
        legendgroup="NAVAIDs",
        showlegend=True,
    )

    return fig


# ---------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------


def main() -> None:
    st.title("Flight tracks")

    st.markdown(
        """
This page shows the **corridor flight tracks** for one day at a time.
Use the controls in the left toolbar to choose the day, **enter / exit
altitude bands**, directions, and sampling density.
"""
    )

    # ---------------- Sidebar / controls ----------------
    with st.sidebar:
        st.header("Flight Tracks Controls")

        # Day picker
        days = get_available_days()
        if not days:
            st.error("No days found in flight track dataset.")
            return

        default_day = days[0]
        selected_day = st.selectbox(
            "Select day",
            options=days,
            index=0,
            format_func=lambda d: d.strftime("%Y-%m-%d"),
        )
        selected_day_str = selected_day.strftime("%Y-%m-%d")

        st.markdown("### Enter altitude band (ft)")
        enter_min = st.slider(
            "Enter altitude – min",
            ALT_MIN,
            ALT_MAX - 1_000,
            ALT_MIN,
            step=1_000,
        )
        enter_max = st.slider(
            "Enter altitude – max",
            enter_min + 1_000,
            ALT_MAX,
            ALT_MAX - 1_000,
            step=1_000,
        )

        st.markdown("### Exit altitude band (ft)")
        exit_min = st.slider(
            "Exit altitude – min",
            ALT_MIN,
            ALT_MAX - 1_000,
            ALT_MIN,
            step=1_000,
        )
        exit_max = st.slider(
            "Exit altitude – max",
            exit_min + 1_000,
            ALT_MAX,
            ALT_MAX,
            step=1_000,
        )

        st.markdown("### Directions to show (N/E/S/W)")
        dir_options = ["N", "E", "S", "W"]
        selected_dirs = st.multiselect(
            "Directions",
            options=dir_options,
            default=dir_options,
        )

        max_aircraft = st.slider(
            "Max aircraft (sampling)",
            min_value=50,
            max_value=2_000,
            value=400,
            step=50,
            help="Lower = faster; limits number of aircraft drawn on the map.",
        )

        st.caption("Lower max aircraft is faster and safer under Cloudflare.")

    # ---------------- Load & filter data ----------------
    df_all = load_tracks(selected_day_str)

    if df_all.empty:
        st.warning(f"No track data available for {selected_day_str}.")
        return

    # Attach simple day label for display
    df_all["day_str"] = selected_day_str

    # Filter by enter / exit bands (per aircraft, repeated per row)
    df = df_all[
        (df_all["enter_alt_ft"] >= enter_min)
        & (df_all["enter_alt_ft"] <= enter_max)
        & (df_all["exit_alt_ft"] >= exit_min)
        & (df_all["exit_alt_ft"] <= exit_max)
    ].copy()

    if df.empty:
        st.warning(
            "No aircraft match the selected enter / exit altitude bands "
            f"for {selected_day_str}."
        )
        return

    # ---------------- Direction classification ----------------
    # Compute one direction label per aircraft based on ENTER and EXIT headings
    per_ac = df.groupby("icao24").agg(
        enter_hdg=("enter_heading", "first"),
        exit_hdg=("exit_heading", "first"),
    )
    per_ac["cardinal_direction"] = [
        classify_direction_from_enter_exit(e, x)
        for e, x in zip(per_ac["enter_hdg"], per_ac["exit_hdg"])
    ]
    dir_map = per_ac["cardinal_direction"].to_dict()
    df["cardinal_direction"] = df["icao24"].map(dir_map)

    if selected_dirs:
        df = df[df["cardinal_direction"].isin(selected_dirs)].copy()
    else:
        st.warning("No directions selected — please pick at least one of N/E/S/W.")
        return

    if df.empty:
        st.warning(
            "No tracks remain after applying direction filters. "
            "Flights whose entry/exit headings are inconsistent are dropped. "
            "Try widening altitude bands or enabling more directions."
        )
        return

    # Basic counts before sampling
    total_aircraft = df["icao24"].nunique()
    total_points = len(df)

    # Down-sample for speed & Cloudflare safety
    df = fast_sample(df, max_aircraft=max_aircraft, max_points=MAX_POINTS_HARD_CAP)

    sampled_aircraft = df["icao24"].nunique()
    sampled_points = len(df)

    # ---------------- Summary text ----------------
    st.markdown(
        f"""
Filtered and sampled to **{sampled_aircraft} aircraft** with
**{sampled_points:,} points** for **{selected_day_str}**.

Entry band: **{enter_min:,}–{enter_max:,} ft**, Exit band:
**{exit_min:,}–{exit_max:,} ft**.  
(Hard cap: {MAX_POINTS_HARD_CAP:,} points for the map.)
"""
    )

    # ---------------- Map ----------------
    fig = make_flight_map(df)
    if fig is None:
        st.warning("Nothing to plot after filtering.")
        return

    st.plotly_chart(fig, width="stretch")


if __name__ == "__main__":
    main()
