#!/usr/bin/env python
"""
Main landing page for the Airspace Overflights dashboard.

This page is intentionally lightweight:
- It does NOT load big parquet files
- It only explains what each page does
"""

import streamlit as st

# ------------------------------------------------------
# Basic page setup
# ------------------------------------------------------
st.set_page_config(
    page_title="Airspace Overflights – Corridor Dashboard",
    page_icon="🛫",
    layout="wide",
)

# Optional: hide the “data source / host-config” menu item in the toolbar
HIDE_DATA_SOURCE_CSS = """
<style>
/* Hide the data source / host-config menu in the Streamlit toolbar */
[data-testid="stToolbar"] > div:nth-child(2) {
    display: none;
}
</style>
"""
st.markdown(HIDE_DATA_SOURCE_CSS, unsafe_allow_html=True)

# ------------------------------------------------------
# Main title and short description
# ------------------------------------------------------
st.title("Airspace Overflights – Corridor Dashboard")

st.markdown(
    """
This dashboard summarizes **traffic, fuel burn, CO₂ emissions, winds, and
maneuvers** for flights crossing the **Washington–New York high-altitude
corridor (FL200–FL430)** during one week in **November 2025**.

All heavy plots live in the pages on the left.  
This front page is just a **guide** to help you understand what you are seeing.
"""
)

st.markdown("---")

# ------------------------------------------------------
# Section: How the data is built
# ------------------------------------------------------
st.subheader("Data in this dashboard (high-level idea)")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
- **Flight data (tracks)**  
  - ADS-B–style position reports inside the corridor  
  - Points are filtered to **FL200–FL430** and to the Baltimore–New York box  
  - Each point has: `icao24`, time, latitude/longitude, altitude, speed, etc.

- **Weather data (winds & temp)**  
  - Joined to each track point from gridded weather (e.g. RAP / ERA5-style)  
  - We derive **headwind / tailwind**, **crosswind**, and **wind direction**.
"""
    )

with col2:
    st.markdown(
        """
- **Fuel and CO₂**  
  - Fuel burn is estimated for each track point (`fuel_kg_row`).  
  - CO₂ is computed using a simple factor (`co2_kg_row`).  
  - These rows are then aggregated to **daily totals** and other summaries.

- **Maneuver flags**  
  - Each point can be marked as:  
    - **Hold** (`is_hold`)  
    - **S-turn** (`sturn_flag`)  
    - **Step climb / descent** (`is_step`)  
  - These are rolled up into **daily counts** and **hourly patterns**.
"""
    )

st.markdown("---")

# ------------------------------------------------------
# Section: What each page shows
# ------------------------------------------------------
st.subheader("Pages in the dashboard")

st.markdown(
    """
### 1. Summary 🧾  
A quick, big-picture view of the week.

- Flights (aircraft-days) per day  
- Total **fuel (kg)** and **CO₂ (kg)** per day  
- Distributions of fuel and CO₂ per aircraft-day  
- Top aircraft IDs (icao24) by fuel burn  

Use this page when you just want the **overall impact** of the week.
"""
)

st.markdown(
    """
### 2. Flight Tracks 🗺️  
A map of **flight routes inside the corridor**, one day at a time.

- Filter by **day**  
- Filter by **direction** (North / South / East / West)  
- Set a **max number of aircraft / points** to keep the map fast  
- Show the main **navigation aids (NAVAIDs)** in the corridor  
- Colour lines by direction so you can see the main flows

This page answers: *“Who is flying where, and in which direction?”*
"""
)

st.markdown(
    """
### 3. Winds 🌬️  
Winds inside the corridor, focused on the **selected day**.

- Histograms of **headwind / tailwind** (positive = headwind, negative = tailwind)  
- Histograms of **crosswind** (left vs right crosswind)  
- A small wind table by **UTC time blocks** (00, 06, 12, 18 UTC)  

This page answers: *“What kind of winds did aircraft see that day?”*
"""
)

st.markdown(
    """
### 4. Maneuvers 🔁  
Where and when aircraft perform **non-standard movements**.

- Daily totals of:  
  - **Holding patterns**  
  - **S-turns**  
  - **Step climbs / descents**  
- Hour-of-day patterns for each maneuver type  
- A map that shows **where** these maneuvers occur inside the corridor  

This page answers:  
- *“Which days had the most maneuvers?”*  
- *“Are there specific places in the corridor where maneuvers cluster?”*
"""
)

st.markdown(
    """
### 5. Wind Tables & Roses 🌈  
A weekly-level view of winds, using **tables, heatmaps, and wind roses**.

- **6-hour wind tables** for the whole week (00–06, 06–12, 12–18, 18–24 UTC)  
- **Heatmaps** that show how wind speed changes over **6h / 12h / 24h** windows  
- Weekly **wind-rose style plots** that summarize direction and strength  

This page is designed to look like the **heatmaps and roses** you shared,
but fully integrated into the Streamlit layout instead of pasted images.
"""
)

st.markdown(
    """
### 6. Fuel & CO₂ Forecast 🔮  
A simple **production-style model** that takes the daily history and predicts
the **next 7 days** of fuel and CO₂ for the corridor.

- Uses the daily features we built:  
  - Total fuel and CO₂ per day  
  - S-turn counts  
  - Average speed and altitude  
- Trains a **Random Forest** model on the 7 historical days  
- Produces a **7-day forecast**  

On the chart you will see two types of points/lines:

- **Observed** (history) – real values from Nov 1–7  
- **Forecast** (future) – model predictions for Nov 8–14

The legend and colour coding clearly show which is which.
"""
)

st.markdown("---")

# ------------------------------------------------------
# Section: How to read the numbers
# ------------------------------------------------------
st.subheader("How to read the numbers")

st.markdown(
    """
- **Fuel and CO₂** are in **kilograms**.  
- One **aircraft-day** is one `icao24` on one day inside the corridor.  
  We use this as a simple proxy for “flights” in the dataset.  
- Maps are **sampled** (using a max-points slider) so the dashboard stays
  responsive even though the raw data has tens of millions of points.
"""
)

st.info(
    "Tip: if a page feels slow, try reducing the day range or lowering the "
    "`max aircraft` / `max points` sliders on that page."
)
