#!/usr/bin/env python
"""
01_Summary.py

Dashboard overview + weekly flight / fuel / CO2 summary.
"""

import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import FUEL_WIND_PATH as DATA_PATH

KGS_TO_TONS = 1.0 / 1000.0


@st.cache_data(show_spinner="Loading weekly summary data…")
def load_week() -> pd.DataFrame:
    con = duckdb.connect()
    sql = f"""
        SELECT
            day,
            icao24,
            fuel_kg_row,
            co2_kg_row
        FROM read_parquet('{DATA_PATH}')
        WHERE fuel_kg_row IS NOT NULL
          AND co2_kg_row   IS NOT NULL
    """
    return con.execute(sql).df()


def build_daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    # total fuel & CO2 per day, flights per day (unique aircraft)
    daily = (
        df.groupby("day")
        .agg(
            total_fuel_kg=("fuel_kg_row", "sum"),
            total_co2_kg=("co2_kg_row", "sum"),
            flights=("icao24", "nunique"),
        )
        .reset_index()
        .sort_values("day")
    )
    return daily


def build_aircraft_day(df: pd.DataFrame) -> pd.DataFrame:
    # aggregate per (day, aircraft) -> "aircraft-day" = proxy for a flight
    ad = (
        df.groupby(["day", "icao24"])
        .agg(
            fuel_kg=("fuel_kg_row", "sum"),
            co2_kg=("co2_kg_row", "sum"),
        )
        .reset_index()
    )
    return ad


def build_top20(df: pd.DataFrame) -> pd.DataFrame:
    # total fuel / CO2 per aircraft across the week
    top = (
        df.groupby("icao24")
        .agg(
            total_fuel_kg=("fuel_kg_row", "sum"),
            total_co2_kg=("co2_kg_row", "sum"),
            aircraft_days=("day", "nunique"),
        )
        .reset_index()
        .sort_values("total_fuel_kg", ascending=False)
        .head(20)
    )
    return top


def main() -> None:
    st.title("Flight Summary – Week of Nov 1–7, 2025")


    st.caption(f"Data source: `{DATA_PATH}`")

    df = load_week()
    daily = build_daily_summary(df)
    ad = build_aircraft_day(df)
    top20 = build_top20(df)

    # -------- Flights per day --------
    st.subheader("Number of flights per day (aircraft count as a flight proxy)")

    fig_flights = px.bar(
        daily,
        x="day",
        y="flights",
        labels={"day": "Day", "flights": "Number of unique aircraft (proxy for flights)"},
        title="Flights per day",
    )
    st.plotly_chart(fig_flights, width="stretch")

    # -------- Daily fuel and CO2 --------
    st.subheader("Daily fuel and CO₂")

    col1, col2 = st.columns(2)

    with col1:
        fig_fuel = px.bar(
            daily,
            x="day",
            y="total_fuel_kg",
            labels={"day": "Day", "total_fuel_kg": "Fuel (kg)"},
            title="Total fuel per day",
        )
        st.plotly_chart(fig_fuel, width="stretch")

    with col2:
        fig_co2 = px.bar(
            daily,
            x="day",
            y="total_co2_kg",
            labels={"day": "Day", "total_co2_kg": "CO₂ (kg)"},
            title="Total CO₂ per day",
        )
        st.plotly_chart(fig_co2, width="stretch")

    # -------- Distributions per aircraft-day --------
    st.subheader("Fuel and CO₂ per aircraft-day (flight proxy)")

    col3, col4 = st.columns(2)

    with col3:
        fig_hist_fuel = px.histogram(
            ad,
            x="fuel_kg",
            nbins=60,
            labels={"fuel_kg": "Fuel per aircraft-day (kg)", "count": "Number of aircraft-days"},
            title="Fuel distribution",
        )
        st.plotly_chart(fig_hist_fuel, width="stretch")

    with col4:
        fig_hist_co2 = px.histogram(
            ad,
            x="co2_kg",
            nbins=60,
            labels={"co2_kg": "CO₂ per aircraft-day (kg)", "count": "Number of aircraft-days"},
            title="CO₂ distribution",
        )
        st.plotly_chart(fig_hist_co2, width="stretch")

    st.markdown(
        """
Each bar shows **how many aircraft-days** fall into a given fuel or CO₂ band.
The long tail to the right reflects a small number of long or heavy flights.
        """
    )

    # -------- Top 20 aircraft table --------
    st.subheader("Top 20 aircraft by total fuel (icao24)")

    st.caption(
        "When airline mapping is available, this table can be switched from **icao24** "
        "to **airline name**. For now it shows the aircraft IDs with the highest fuel usage."
    )

    st.dataframe(
        top20.rename(
            columns={
                "icao24": "Aircraft (icao24)",
                "total_fuel_kg": "Total fuel (kg)",
                "total_co2_kg": "Total CO₂ (kg)",
                "aircraft_days": "Number of aircraft-days",
            }
        ),
        width="stretch",
    )


if __name__ == "__main__":
    main()
