# pages/03_Winds.py
#
# Faster Winds page:
#  - Only loads one day at a time
#  - Uses DuckDB to SAMPLE at most max_rows rows
#  - Computes headwind/tailwind & crosswind in Python
#  - Builds a single-day wind rose from that sample

import numpy as np
import pandas as pd
import duckdb
import plotly.express as px
import streamlit as st

# ---- CONFIG ----

DATA_PATH = (
    "/home/rghuglot/services/overflights/lib/overflight_data/"
    "fuel_wind_rows_nov01_07_enriched_all.parquet"
)

MPS_TO_KT = 1.943844  # m/s → knots


# ---- DATA HELPERS ----

@st.cache_data(show_spinner="Loading wind sample…")
def load_wind_sample(day_str: str, alt_min: float, alt_max: float, max_rows: int = 80000):
    """
    Return a sampled subset of winds for one day and altitude band.

    Columns used: ts_utc, alt_ft, wind_u, wind_v, wind_speed, wind_dir, heading.
    Sampling keeps the page fast even when the full day has millions of rows.
    """
    con = duckdb.connect()

    # DuckDB SAMPLE in ROWS keeps us from pulling the whole day
    sql = f"""
        SELECT
            day,
            ts_utc,
            alt_ft,
            wind_u,
            wind_v,
            wind_speed,
            wind_dir,
            heading
        FROM read_parquet('{DATA_PATH}')
        WHERE day = DATE '{day_str}'
          AND alt_ft BETWEEN {alt_min} AND {alt_max}
        USING SAMPLE {max_rows} ROWS
    """

    df = con.execute(sql).df()
    if df.empty:
        return df

    # Convert to knots
    df["wind_u_kt"] = df["wind_u"] * MPS_TO_KT
    df["wind_v_kt"] = df["wind_v"] * MPS_TO_KT
    df["wind_speed_kt"] = df["wind_speed"] * MPS_TO_KT

    # Track angle in radians
    track_rad = np.deg2rad(df["heading"].to_numpy())

    # Wind components relative to track
    # along_kt > 0 : headwind, < 0 : tailwind
    along = -(
        df["wind_u_kt"].to_numpy() * np.cos(track_rad)
        + df["wind_v_kt"].to_numpy() * np.sin(track_rad)
    )

    # crosswind (positive right, negative left, we plot magnitude)
    cross = -(
        -df["wind_u_kt"].to_numpy() * np.sin(track_rad)
        + df["wind_v_kt"].to_numpy() * np.cos(track_rad)
    )

    df["along_kt"] = along
    df["cross_kt"] = cross
    df["cross_abs_kt"] = np.abs(cross)

    # Head / tail categories
    df["along_type"] = np.where(df["along_kt"] >= 0, "headwind", "tailwind")

    return df


def build_daily_rose(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a simple daily wind rose from the sample:
      - 30° direction bins
      - mean speed per bin (knots)
    """
    if df.empty:
        return df

    rose = df[["wind_dir", "wind_speed_kt"]].dropna().copy()
    if rose.empty:
        return rose

    # 12 bins: 0–30, 30–60, …, 330–360
    bins = np.arange(0, 361, 30)
    centers = (bins[:-1] + bins[1:]) / 2  # e.g. 15, 45, …

    rose["dir_bin"] = pd.cut(
        rose["wind_dir"] % 360,
        bins=bins,
        include_lowest=True,
        right=False,
        labels=centers,
    )

    rose = (
        rose.groupby("dir_bin", observed=True)
        .agg(mean_speed_kt=("wind_speed_kt", "mean"))
        .reset_index()
    )

    rose["dir_bin_center"] = rose["dir_bin"].astype(float)

    return rose


# ---- PLOTS ----

def plot_along_hist(df: pd.DataFrame):
    fig = px.histogram(
        df,
        x="along_kt",
        color="along_type",
        barmode="overlay",
        nbins=80,
        labels={
            "along_kt": "Along-track wind (kt)",
            "count": "Count",
            "along_type": "Type",
        },
    )
    fig.update_layout(legend_title_text="Wind type")
    return fig


def plot_cross_hist(df: pd.DataFrame):
    fig = px.histogram(
        df,
        x="cross_abs_kt",
        nbins=80,
        labels={
            "cross_abs_kt": "Crosswind magnitude (kt)",
            "count": "Count",
        },
    )
    return fig


def plot_daily_rose(rose_df: pd.DataFrame, day_label: str):
    if rose_df.empty:
        return None

    fig = px.bar_polar(
        rose_df,
        r="mean_speed_kt",
        theta="dir_bin_center",
        labels={
            "mean_speed_kt": "Mean wind speed (kt)",
            "dir_bin_center": "Direction (°)",
        },
    )
    fig.update_layout(
        title=f"Wind rose for {day_label}",
        polar_angularaxis_direction="clockwise",
        polar_angularaxis_rotation=90,  # 0° at the top (North)
    )
    return fig


# ---- STREAMLIT PAGE ----

def main():
    st.markdown("## 03 – Winds")

    st.write(
        "This page shows **headwind / tailwind** and **crosswind** distributions "
        "for a selected day and altitude band, plus a simple daily **wind rose**."
    )

    # --- Sidebar / filters ---

    con = duckdb.connect()
    days = con.execute(
        f"SELECT DISTINCT day FROM read_parquet('{DATA_PATH}') ORDER BY day"
    ).df()["day"].astype(str).tolist()

    if not days:
        st.error("No days found in the wind dataset.")
        return

    day_str = st.sidebar.selectbox("Flight day", days, index=0)

    alt_min, alt_max = st.sidebar.slider(
        "Altitude band (ft)",
        min_value=20000,
        max_value=43000,
        value=(20000, 43000),
        step=1000,
    )

    max_rows = st.sidebar.slider(
        "Max rows to sample (performance)",
        min_value=20000,
        max_value=150000,
        value=80000,
        step=10000,
        help="Higher values give smoother histograms but can be slower.",
    )

    st.caption(
        f"Data source: `{DATA_PATH}` – day {day_str}, altitude {alt_min:,}–{alt_max:,} ft, "
        f"sampled up to {max_rows:,} rows."
    )

    # --- Load sample ---

    df = load_wind_sample(day_str, alt_min, alt_max, max_rows=max_rows)
    if df.empty:
        st.warning("No wind data for this filter combination.")
        return

    n_rows = len(df)
    st.write(
        f"Using a sample of **{n_rows:,} points** for the histograms and wind rose."
    )

    # --- Histograms ---

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Headwind vs tailwind (along-track, kt)")
        fig_along = plot_along_hist(df)
        st.plotly_chart(fig_along, width="stretch")

    with col2:
        st.markdown("### Crosswind magnitude (kt)")
        fig_cross = plot_cross_hist(df)
        st.plotly_chart(fig_cross, width="stretch")

    st.divider()

    # --- Daily wind rose ---

    st.markdown("### Daily wind rose (sample-based)")

    rose_df = build_daily_rose(df)
    fig_rose = plot_daily_rose(rose_df, day_str)

    if fig_rose is None:
        st.info("Not enough data to build a wind rose for this day.")
    else:
        st.plotly_chart(fig_rose, width="stretch")


if __name__ == "__main__":
    main()
