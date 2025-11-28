#!/usr/bin/env python
"""
Build daily fuel / CO2 / speed / altitude features for the corridor week.

Input:
    /home/rghuglot/services/overflights/lib/overflight_data/
        fuel_wind_rows_nov01_07_enriched_all.parquet

Output:
    /home/rghuglot/services/overflights/lib/overflight_data/
        fuel_co2_daily_features.parquet
"""

from pathlib import Path
import duckdb

INPUT_PATH = (
    "/home/rghuglot/services/overflights/lib/overflight_data/"
    "fuel_wind_rows_nov01_07_enriched_all.parquet"
)

OUTPUT_PATH = (
    "/home/rghuglot/services/overflights/lib/overflight_data/"
    "fuel_co2_daily_features.parquet"
)


def main() -> None:
    print(f"[INFO] Building daily features from: {INPUT_PATH}")

    con = duckdb.connect()

    # NOTE:
    # DuckDB told us the row-level columns are:
    #   fuel_kg_row, co2_kg_row, sturn_flag, alt_ft, spd_kts, ...
    # so we aggregate those and rename them to nice daily features.
    sql = f"""
    SELECT
        day,
        SUM(fuel_kg_row)                         AS fuel_kg,
        SUM(co2_kg_row)                          AS co2_kg,
        SUM(CASE WHEN sturn_flag > 0 THEN 1
                 ELSE 0 END)                    AS s_turn_rows,
        AVG(spd_kts)                             AS mean_spd_kts,
        AVG(alt_ft)                              AS mean_alt_ft
    FROM read_parquet('{INPUT_PATH}')
    GROUP BY day
    ORDER BY day
    """

    df = con.execute(sql).df()

    print("[INFO] Daily features (preview):")
    print(df)

    out_path = Path(OUTPUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Save as parquet using DuckDB (works fine even for small df)
    con.register("daily_features", df)
    con.execute(
        f"COPY daily_features TO '{OUTPUT_PATH}' (FORMAT 'parquet')"
    )

    print(f"[INFO] Wrote daily features to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
