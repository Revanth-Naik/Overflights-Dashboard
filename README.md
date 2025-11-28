# Airspace Overflights Dashboard – BWI–NY Corridor

**Course:** DAEN 690 – Capstone Project  
**Team:** Overflights  
**Sponsor:** CATSR (Center for Air Transportation Systems Research), GMU  
**Faculty Advisor:** Dr. Lance Sherry  

This repository is the central, version-controlled workspace for our DAEN 690 capstone project.  
It contains the code, documentation, and deliverables for the **Airspace Overflights Dashboard**,  
which analyzes high-altitude overflights between **Baltimore (BWI)** and **New York (NY)**.

---

## 1. Problem statement (short version)

High-altitude traffic in the **BWI–NY corridor (FL200–FL430)** is busy and complex.  
Today, traffic managers mostly see:

- raw ADS-B tracks,
- basic weather products, and
- no short-term demand or fuel/CO₂ summaries.

This makes it hard to:

- see north/south flows by altitude,
- understand wind-driven **maneuvers** (holds, S-turns, step climbs),
- estimate daily fuel burn and CO₂ emissions, and
- get **short-term forecasts** of demand and impact.

Our project builds an **operational analytics system** that:

1. Ingests ADS-B tracks (OpenSky / TRINO) and NOAA RAP winds.
2. Detects true overflights in a defined 3D corridor.
3. Estimates per-segment fuel and CO₂.
4. Detects maneuvers (holds, S-turns, step climbs/descents).
5. Aggregates everything into daily / hourly metrics and simple forecasts.
6. Presents results in a **Streamlit dashboard**, published through a **Cloudflare tunnel**.

---

## 2. Data sources

We do **not** store raw data in this GitHub repo.  
All large datasets live on the DAEN 690 VM under:

```text
/home/rghuglot/services/overflights/lib/overflight_data/# Overflights-Dashboard
A full end-to-end analytics system for the BWI–NY high-altitude corridor. Includes ADS-B ingestion, RAP wind processing, per-row wind joins, maneuver detection (holds, S-turns, step climbs), fuel &amp; CO₂ estimation, a Random Forest forecast model, and a multi-page Streamlit dashboard served through Cloudflare Tunnel.
