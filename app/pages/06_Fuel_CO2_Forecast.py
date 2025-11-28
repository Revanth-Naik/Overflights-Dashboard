#!/usr/bin/env python
"""
Page 06 – Fuel and CO₂ forecast

Reads the daily history + 7-day forecast from
`fuel_co2_daily_forecast.parquet` and shows:

- High-level summary of last observed vs first forecast day
- Bar chart for fuel (history vs forecast)
- Bar chart for CO₂ (history vs forecast)
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pandas as pd
import plotly.express as px
import streamlit as st


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

# Absolute path is fine for the server you’re on.
FORECAST_PATH = Path(
    "/home/rghuglot/services/overflights/lib/overflight_data/"
    "fuel_co2_daily_forecast.parquet"
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def load_forecast(path: Path) -> pd.DataFrame:
    """Load daily history + forecast from parquet and tidy it."""
    df = pd.read_parquet(path)

    # Ensure dtypes
    df["day"] = pd.to_datetime(df["day"])
    if "is_forecast" not in df.columns:
        df["is_forecast"] = False

    df = df.sort_values("day").reset_index(drop=True)
    return df


def pct_change(old: float, new: float) -> float:
    """Percent change new vs old (returns NaN if not defined)."""
    if old == 0 or pd.isna(old) or pd.isna(new):
        return float("nan")
    return (new - old) / old * 100.0


def make_metric_chart(
    df: pd.DataFrame,
    metric_col: str,
    title: str,
    yaxis_title: str,
) -> "px.Figure":
    """
    Generic bar chart for a single metric (fuel_kg or co2_kg).

    Bars are colored by Observed vs Forecast and a vertical dashed line
    marks the first forecast day.
    """
    # Copy so we don’t mutate the original
    df_plot = df.copy()

    # Human-friendly legend labels instead of True/False
    df_plot["forecast_type"] = df_plot["is_forecast"].map(
        {False: "Observed", True: "Forecast"}
    )

    fig = px.bar(
        df_plot,
        x="day",
        y=metric_col,
        color="forecast_type",
        color_discrete_map={
            "Observed": "#1f77b4",  # blue
            "Forecast": "#ff7f0e",  # orange
        },
        labels={"day": "Day", metric_col: yaxis_title},
        title=title,
    )

    # Vertical line at the first forecast day
    if df_plot["is_forecast"].any():
        first_fc = df_plot.loc[df_plot["is_forecast"], "day"].min()
    else:
        first_fc = None

    if first_fc is not None and pd.notna(first_fc):
        fig.add_vline(
            x=first_fc,
            line_dash="dash",
            line_color="white",
            opacity=0.6,
        )

    fig.update_layout(
        legend_title="",
        bargap=0.15,
        xaxis_title="Day",
        yaxis_title=yaxis_title,
    )

    return fig


# ----------------------------------------------------------------------
# Page layout
# ----------------------------------------------------------------------


def main() -> None:
    st.title("Fuel and CO₂ forecast")

    if not FORECAST_PATH.exists():
        st.error(f"Forecast file not found: `{FORECAST_PATH}`")
        return

    df = load_forecast(FORECAST_PATH)

    if df.empty:
        st.warning("Forecast file is empty.")
        return

    hist = df[~df["is_forecast"]].copy()
    fcst = df[df["is_forecast"]].copy()

    if hist.empty or fcst.empty:
        st.warning(
            "Need at least one observed day and one forecast day "
            "to show this page."
        )
        return

    last_obs = hist.iloc[-1]
    first_fc = fcst.iloc[0]

    fuel_pct = pct_change(last_obs["fuel_kg"], first_fc["fuel_kg"])
    co2_pct = pct_change(last_obs["co2_kg"], first_fc["co2_kg"])

    total_fuel_fc = fcst["fuel_kg"].sum()
    total_co2_fc = fcst["co2_kg"].sum()

    # ---------- Summary bullets ------------------------------------------------
    st.markdown(
        f"""
- **Last observed day:** `{last_obs['day'].date()}`  
- **First forecast day:** `{first_fc['day'].date()}`  
- **Fuel change (first forecast vs last observed):** {fuel_pct:+.2f} %  
- **CO₂ change (first forecast vs last observed):** {co2_pct:+.2f} %  
- **Total forecast fuel (next {len(fcst)} days):** {total_fuel_fc:,.0f} kg  
- **Total forecast CO₂ (next {len(fcst)} days):** {total_co2_fc:,.0f} kg  
"""
    )

    st.markdown("---")

    # ---------- Fuel chart -----------------------------------------------------
    st.subheader("Fuel forecast")

    fig_fuel = make_metric_chart(
        df,
        metric_col="fuel_kg",
        title="Daily fuel – history vs 7-day forecast",
        yaxis_title="Fuel (kg)",
    )
    st.plotly_chart(fig_fuel, width="stretch")

    # ---------- CO2 chart ------------------------------------------------------
    st.subheader("CO₂ forecast")

    fig_co2 = make_metric_chart(
        df,
        metric_col="co2_kg",
        title="Daily CO₂ – history vs 7-day forecast",
        yaxis_title="CO₂ (kg)",
    )
    st.plotly_chart(fig_co2, width="stretch")


# Streamlit entry point
if __name__ == "__main__":
    main()
