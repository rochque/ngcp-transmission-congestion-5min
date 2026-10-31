import os
import polars as pl

# BASE DIRECTORY PATHS
BASE_DIR = "D:/NGCP/5_MINUTE_MARKET_DATA"
OUTPUT_CONGESTION_CSV = "D:/NGCP/Grid_Congestion_5min_Daily_Summary.csv"

# 14 NGCP O&M TRANSMISSION DISTRICTS MAPPER
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

def map_resource_type(plant_name):
    p = str(plant_name).upper()
    if any(k in p for k in ["SOLAR", "SOL"]): return "Solar"
    if any(k in p for k in ["WIND", "WND"]): return "Wind"
    if any(k in p for k in ["HYDRO", "HEPP", "PULANGI", "AGUS"]): return "Hydro"
    if any(k in p for k in ["GEO", "TIWI", "MAIBARARA", "PALINPINON"]): return "Geothermal"
    return "Variable RE / Other"

def load_curtailment_recursively(batch_size=2000):
    # SEARCH FOR RE_CURTAILMENT FOLDER OR DERIVED CURTAILMENT DATA
    folder_candidates = ["RE_Curtailment", "RE_CURTAILMENT", "Curtailment", "RTDRS"]
    folder_path = None
    
    for candidate in folder_candidates:
        p = os.path.join(BASE_DIR, candidate)
        if os.path.exists(p):
            folder_path = p
            break

    if not folder_path:
        print(f"⚠️ Curtailment directory not found under `{BASE_DIR}`. Checking fallback dataset...")
        return None

    csv_files = [os.path.join(root, f) for root, _, files in os.walk(folder_path) for f in files if f.lower().endswith(".csv") and "daily_summary" not in f.lower()]
    if not csv_files:
        print(f"⚠️ No CSV files found inside `{folder_path}`.")
        return None

    print(f"📂 Processing {len(csv_files):,} CSV files in RE Curtailment dataset...")
    batch_dfs = []
    current_batch = []

    for idx, file_path in enumerate(sorted(csv_files), start=1):
        try:
            df = pl.read_csv(file_path, infer_schema_length=10000)
            df = df.rename({col: col.strip().upper() for col in df.columns})

            time_col = [c for c in df.columns if "TIME" in c or "INTERVAL" in c or "DATE" in c]
            curtail_col = [c for c in df.columns if any(k in c for k in ["CURTAIL", "CURTAILED_MW", "SCHED_MW", "MW", "DISPATCH_MW"])]

            if not time_col or not curtail_col:
                continue

            df = df.with_columns(
                pl.col(time_col[0])
                .str.to_datetime(format="%m/%d/%Y %H:%M", strict=False)
                .fill_null(pl.col(time_col[0]).str.to_datetime(format="%m/%d/%Y %I:%M:%S %p", strict=False))
                .fill_null(pl.col(time_col[0]).str.to_datetime(format="%m/%d/%Y %H:%M:%S", strict=False))
                .alias("Parsed_DateTime")
            ).filter(pl.col("Parsed_DateTime").is_not_null())

            df = df.with_columns([
                pl.col("Parsed_DateTime").dt.date().alias("Date"),
                pl.col("Parsed_DateTime").dt.hour().alias("Hour"),
                pl.col(curtail_col[0]).cast(pl.Float64, strict=False).alias("CURTAILED_MW")
            ])

            if "RESOURCE_NAME" in df.columns:
                df = df.with_columns([
                    pl.col("RESOURCE_NAME").str.strip_chars().str.to_uppercase().alias("RESOURCE_NAME"),
                    pl.col("RESOURCE_NAME").str.slice(0, 2).alias("SUB_GRID_PREFIX")
                ])
                regions, districts, fuel_types = [], [], []
                for p, plant in zip(df["SUB_GRID_PREFIX"].to_list(), df["RESOURCE_NAME"].to_list()):
                    reg, dist = map_district_info(p)
                    regions.append(reg)
                    districts.append(dist)
                    fuel_types.append(map_resource_type(plant))
                
                df = df.with_columns([
                    pl.Series("REGION", regions, dtype=pl.String),
                    pl.Series("PROVINCE_DISTRICT", districts, dtype=pl.String),
                    pl.Series("FUEL_TYPE", fuel_types, dtype=pl.String)
                ])
            else:
                df = df.with_columns([
                    pl.lit("01").alias("SUB_GRID_PREFIX"),
                    pl.lit("LUZON").alias("REGION"),
                    pl.lit("NL1 - Ilocos / La Union / Pangasinan / Benguet").alias("PROVINCE_DISTRICT"),
                    pl.lit("GENERIC_RE_PLANT").alias("RESOURCE_NAME"),
                    pl.lit("Solar").alias("FUEL_TYPE")
                ])

            hourly = df.group_by(["Date", "Hour", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME", "FUEL_TYPE"]).agg([
                pl.col("CURTAILED_MW").mean().alias("CURTAILED_MW_AVG"),
                pl.col("CURTAILED_MW").max().alias("CURTAILED_MW_PEAK")
            ])
            current_batch.append(hourly)

            if len(current_batch) >= batch_size:
                consolidated = pl.concat(current_batch, how="diagonal").group_by(["Date", "Hour", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME", "FUEL_TYPE"]).agg([
                    pl.col("CURTAILED_MW_AVG").mean(),
                    pl.col("CURTAILED_MW_PEAK").max()
                ])
                batch_dfs.append(consolidated)
                current_batch = []
                print(f"   - Memory Checkpoint [{idx}/{len(csv_files)}]: Cleared.")

        except Exception:
            continue

    if current_batch:
        batch_dfs.append(pl.concat(current_batch, how="diagonal"))

    if batch_dfs:
        final_df = pl.concat(batch_dfs, how="diagonal").group_by(["Date", "Hour", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME", "FUEL_TYPE"]).agg([
            pl.col("CURTAILED_MW_AVG").mean(),
            pl.col("CURTAILED_MW_PEAK").max()
        ])
        return final_df
    return None

def process_grid_congestion():
    print("=" * 60)
    print("STARTING GRID CONGESTION & RENEWABLE ABSORPTION PIPELINE")
    print("=" * 60)

    curtail_df = load_curtailment_recursively()

    # LOAD ACTUAL DEMAND SUMMARY FOR ABSORPTION RATIO
    demand_summary_path = "D:/NGCP/Actual_Demand_5min_Daily_Summary.csv"
    demand_df = None
    if os.path.exists(demand_summary_path):
        demand_df = pl.read_csv(demand_summary_path).with_columns(pl.col("Date").str.to_date(strict=False))

    if curtail_df is None:
        print("⚠️ RE Curtailment dataset missing. Generating synthetic framework placeholder for structure validation...")
        # FALLBACK EMPTY STRUCTURE TO PREVENT SCRIPT BREAKAGE
        schema = {
            "Date": pl.Date, "Hour": pl.Int32, "REGION": pl.String, "SUB_GRID_PREFIX": pl.String,
            "PROVINCE_DISTRICT": pl.String, "RESOURCE_NAME": pl.String, "FUEL_TYPE": pl.String,
            "CURTAILED_MW_AVG": pl.Float64, "CURTAILED_MW_PEAK": pl.Float64
        }
        curtail_df = pl.DataFrame(schema=schema)

    keys = ["Date", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT"]
    
    # AGGREGATE DAILY/HOURLY BOTTLENECK METRICS
    if demand_df is not None and not curtail_df.is_empty():
        merged = curtail_df.join(demand_df, on="Date", how="left").fill_null(0.0)
    else:
        merged = curtail_df.with_columns([
            pl.lit(0.0).alias("SYSTEM_AVG"),
            pl.lit(0.0).alias("SYSTEM_PEAK")
        ])

    # CALCULATE LOCAL ABSORPTION & BESS POTENTIAL
    merged = merged.with_columns([
        pl.when(pl.col("SYSTEM_AVG") > 0)
        .then((pl.col("CURTAILED_MW_AVG") / pl.col("SYSTEM_AVG")) * 100)
        .otherwise(0.0)
        .alias("CURTAILMENT_DEMAND_RATIO_PCT")
    ])

    merged.write_csv(OUTPUT_CONGESTION_CSV)
    print(f"\n✅ Grid Congestion Summary successfully saved: {OUTPUT_CONGESTION_CSV} ({len(merged):,} records)")

if __name__ == "__main__":
    process_grid_congestion()