# ✈️ Overflights Dashboard  
### DAEN 690 – Airspace Overflight Analysis  
*George Mason University · Fall 2025*

This repository contains the full Streamlit dashboard, ETL pipeline, data engineering workflows, and fuel/CO₂ forecasting model developed for the DAEN 690 Overflights Project.  
The project analyzes traffic in the **Baltimore–New York high-altitude corridor (FL200–FL430)** using ADS-B and NOAA weather data.

---

## 🔍 **Project Overview**

The goal of this project is to:

- Monitor high-altitude traffic in the NY–BWI corridor  
- Detect atmospheric impacts (wind direction, headwind, tailwind, crosswind)  
- Identify and quantify aircraft maneuvers (holds, S-turns, step climbs)  
- Estimate and forecast fuel burn and CO₂ emissions  
- Visualize all insights through an interactive Streamlit dashboard  

The dashboard is designed to help aviation analysts understand corridor congestion, efficiency, and environmental impact.

---

## 🏗️ **System Architecture**

```
+-------------------------------+
|  ADS-B Flight Data (Rows)     |
+-------------------------------+
                |
                v
+-------------------------------+
|  NOAA RAP/GRIB2 Weather Data  |
+-------------------------------+
                |
                v
+----------------------------------------------+
|              ETL PIPELINE (Python)           |
|  - Merge flight + weather                    |
|  - Compute winds (head/tail/crosswind)       |
|  - Detect maneuvers                          |
|  - Compute fuel + CO₂ (row-level)            |
|  - Aggregate daily features                  |
+----------------------------------------------+
                |
                v
+-------------------------------+
|  Feature Store (Parquet)     |
+-------------------------------+
                |
                v
+----------------------------------------------+
|        ML: Random Forest Regression          |
|  - Predict next 7 days fuel & CO₂            |
+----------------------------------------------+
                |
                v
+----------------------------------------------+
|        Streamlit Overflights Dashboard       |
+----------------------------------------------+
```

Image file: `docs/system_architecture.png`

---

## 📂 **Repository Structure**

```
Overflights-Dashboard/
│
├── app/
│   ├── app_overflights_dashboard.py
│   ├── pages/
│   │   ├── 01_Summary.py
│   │   ├── 02_Flight_Tracks.py
│   │   ├── 03_Winds.py
│   │   ├── 04_Maneuvers.py
│   │   ├── 05_Wind_tables_and_roses.py
│   │   └── 06_Fuel_CO2_Forecast.py
│   ├── etl/
│   ├── models/
│   ├── output/
│   └── services/
│
├── docs/
│   ├── api_notes.md
│   ├── presentation_outline.md
│   └── system_architecture.png
│
├── reports/
│   ├── midterm_presentation/
│   └── final_presentation/
│
├── .gitignore
├── LICENSE
└── README.md
```

---

## 📊 **Dashboard Pages**

### **1️⃣ Summary Page**
- High-level statistics for the corridor  
- Daily averages  
- Traffic trends

### **2️⃣ Flight Tracks**
- Visualizes daily tracks inside the NY–BWI corridor  
- Direction classification based on heading:  
  - **N (315°–45°)**  
  - **S (135°–225°)**  
  - **E (45°–135°)**  
  - **W (225°–315°)**  
- Filters for:
  - Entry altitude band  
  - Exit altitude band  
  - Cardinal direction  
  - Sampling controls  
- Includes NAVAIDs:
  JFK, RBV, CYN, SIE, LRP, AML

---

### **3️⃣ Winds Page**
- Shows headwind, tailwind, crosswind components
- Daily bar charts + heatmaps + wind roses
- Single week of corridor weather for quick pattern detection

---

### **4️⃣ Maneuvers**
- Detect and count:
  - Holding patterns  
  - S-turns  
  - Step climbs and descents  
- Daily stacked summaries  
- Hour-of-day histogram  
- Map of maneuver hotspots (clustered inside corridor)

---

### **5️⃣ Wind Tables & Roses**
- Raw wind tables  
- Full wind roses for the week in EST  
- Side-by-side comparison of per-day patterns  

---

### **6️⃣ Fuel & CO₂ Forecast**
- Uses a **Random Forest Regressor**  
- Trains on 7 days of enriched row-level data  
- Features:
  - Total fuel  
  - CO₂  
  - Maneuvers  
  - Wind speed  
  - Mean altitude  
- Produces:
  - Next 7-day forecast  
  - Trend-line comparison  
  - Summary table  
  - % change from previous day  

---

## ⚙️ **How to Run the Dashboard**

### 1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Get some data in place (pick one)

**Option A — try it now with synthetic sample data** (no real data needed):

```bash
python scripts/generate_sample_data.py
```

This writes small fake parquet files (same schema as the real dataset) into
`data/` at the repo root, and runs the real ETL scripts against them to
produce the daily-features and forecast files too. Good for a quick
click-through of every page; the numbers are not real.

**Option B — point at the real data**, wherever it lives (the VM path, a
mounted drive, another folder), without editing any code:

```bash
export OVERFLIGHTS_DATA_DIR=/home/rghuglot/services/overflights/lib/overflight_data
```

(or copy/symlink the real parquet files into `data/` at the repo root,
matching the layout below — that's the default when the env var isn't set).

### 3. Run the Streamlit app:

```bash
cd app
streamlit run app_overflights_dashboard.py
```

---

## 📦 **Data Handling**

Raw data is NOT stored in GitHub (see `.gitignore`). All data paths are
centralized in `app/config.py`, which resolves to `data/` at the repo root
by default, or to `$OVERFLIGHTS_DATA_DIR` if that environment variable is
set — no hardcoded machine-specific paths in the page/ETL code anymore.

Expected layout, wherever `DATA_DIR` points:

```
data/
├── fuel_wind_rows_nov01_07_enriched_all.parquet
├── fuel_co2_daily_features.parquet
├── fuel_co2_daily_forecast.parquet
└── maneuver_summaries_v2/
    └── maneuvers_rows.parquet
```

---

## 📘 **Methodology Summary**

A detailed explanation of each calculation is provided in:  
👉 `docs/api_notes.md`

Includes formulas for:

- Wind components (head/tail/crosswind)  
- Maneuver detection  
- Fuel & CO₂ estimation  
- Random Forest forecasting  

---

## 👥 Contributors

**Revanth Naik Ghugloth**  
**Sreyas Kolli**  
**Sravani Lakshmi Malapati**  
**Dr. Lance Sherry (Advisor)**  

---

## 📝 License

MIT License
