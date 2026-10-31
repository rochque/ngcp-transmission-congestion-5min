import os
import polars as pl

BASE_DIR = "D:/NGCP/5_MINUTE_MARKET_DATA/Actual_Generation_Output"
OUTPUT_SUMMARY_CSV = "D:/NGCP/Actual_Generation_5min_Daily_Summary.csv"

DISTRICT_PROVINCE_MAP = {
    "01": ("LUZON", "NL1 - Ilocos / La Union / Pangasinan / Benguet"),
    "02": ("LUZON", "CL2 - Bataan / Bulacan / Pampanga / Tarlac / Zambales"),
    "03": ("LUZON", "SL3 - Batangas / Cavite / Laguna / Quezon / Bicol"),
    "04": ("VISAYAS", "Panay 04 - Iloilo / Aklan / Capiz / Antique"),
    "05": ("VISAYAS", "Cebu 05 - Metro Cebu / Mandaue / Mactan"),
    "06": ("VISAYAS", "Negros 06 - Negros Occidental / Negros Oriental"),
    "07": ("VISAYAS", "Leyte 07 - Leyte / Biliran / Southern Leyte"),
    "08": ("VISAYAS", "Samar 08 - Western Samar / Northern / Eastern Samar"),
    "09": ("MINDANAO", "SM9 - Metro Davao / Davao del Norte / Sur"),
    "10": ("MINDANAO", "NM10 - Misamis Oriental / Bukidnon / CDO / Lanao Norte"),
    "11": ("MINDANAO", "Soccsksargen 11 - South Cotabato / GenSan / Sultan Kudarat"),
    "12": ("MINDANAO", "WM12 - Zamboanga City / Del Sur / Del Norte / Sibugay"),
    "13": ("MINDANAO", "Caraga 13 - Agusan del Norte / Surigao / Butuan"),
    "14": ("MINDANAO", "BARMM 14 - Maguindanao / Lanao Sur / Sulu")
}

def map_district_info(prefix):
    if not prefix or len(prefix) < 2:
        return ("UNKNOWN", "Unknown District / Provinces")
    p = prefix[:2]
    return DISTRICT_PROVINCE_MAP.get(p, ("OTHER", f"District {p} - Other Provinces"))

def process_actual_generation():
    print("=" * 60)
    print("RE-COMPILING ACTUAL GENERATION (FIXING MM/DD/YYYY DATE PARSING)")
    print("=" * 60)

    csv_files = [os.path.join(BASE_DIR, f) for f in os.listdir(BASE_DIR) if f.lower().endswith(".csv") and "daily_summary" not in f.lower()] if os.path.exists(BASE_DIR) else []
    if not csv_files:
        print(f"⚠️ No CSV files found under `{BASE_DIR}`.")
        return

    processed_dfs = []
    for idx, file_path in enumerate(sorted(csv_files), start=1):
        if idx % 100 == 0 or idx == len(csv_files):
            print(f"   - Processing file [{idx}/{len(csv_files)}]: {os.path.basename(file_path)}")
        try:
            df = pl.read_csv(file_path, infer_schema_length=10000)
            df = df.rename({col: col.strip().upper() for col in df.columns})
            
            time_col = [c for c in df.columns if "TIME" in c or "INTERVAL" in c or "DATE" in c]
            mw_col = [c for c in df.columns if c == "MW" or "GENERATION" in c]

            if not time_col or not mw_col:
                continue

            # STRICT MM/DD/YYYY PARSER
            df = df.with_columns(
                pl.col(time_col[0])
                .str.to_datetime(format="%m/%d/%Y %H:%M", strict=False)
                .fill_null(pl.col(time_col[0]).str.to_datetime(format="%m/%d/%Y %I:%M:%S %p", strict=False))
                .fill_null(pl.col(time_col[0]).str.to_datetime(format="%m/%d/%Y %H:%M:%S", strict=False))
                .alias("Parsed_DateTime")
            ).filter(pl.col("Parsed_DateTime").is_not_null())

            df = df.with_columns([
                pl.col("Parsed_DateTime").dt.date().alias("Date"),
                pl.col(mw_col[0]).cast(pl.Float64, strict=False).alias("MW")
            ])

            if "RESOURCE_NAME" in df.columns:
                df = df.with_columns(pl.col("RESOURCE_NAME").str.slice(0, 2).alias("SUB_GRID_PREFIX"))
                regions, districts = [], []
                for p in df["SUB_GRID_PREFIX"].to_list():
                    reg, dist = map_district_info(p)
                    regions.append(reg)
                    districts.append(dist)
                df = df.with_columns([
                    pl.Series("REGION", regions, dtype=pl.String),
                    pl.Series("PROVINCE_DISTRICT", districts, dtype=pl.String)
                ])

            group_keys = ["Date"]
            for k in ["REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME"]:
                if k in df.columns:
                    group_keys.append(k)

            daily_summary = df.group_by(group_keys).agg([
                pl.col("MW").mean().alias("MW_AVG"),
                pl.col("MW").max().alias("MW_PEAK")
            ])

            daily_summary = daily_summary.with_columns([
                pl.col("Date").cast(pl.Date),
                pl.col("REGION").cast(pl.String),
                pl.col("SUB_GRID_PREFIX").cast(pl.String),
                pl.col("PROVINCE_DISTRICT").cast(pl.String),
                pl.col("RESOURCE_NAME").cast(pl.String),
                pl.col("MW_AVG").cast(pl.Float64),
                pl.col("MW_PEAK").cast(pl.Float64)
            ])

            processed_dfs.append(daily_summary)
        except Exception as e:
            print(f"   ❌ Error in {os.path.basename(file_path)}: {e}")

    if processed_dfs:
        final_df = pl.concat(processed_dfs, how="diagonal").sort(["Date"])
        final_df.write_csv(OUTPUT_SUMMARY_CSV)
        print(f"\n✅ Fixed Summary saved to: {OUTPUT_SUMMARY_CSV} ({len(final_df):,} records)")

if __name__ == "__main__":
    process_actual_generation()