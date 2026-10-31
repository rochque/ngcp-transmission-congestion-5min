import os
import polars as pl
 
BASE_DIR = "D:/NGCP/5_MINUTE_MARKET_DATA"
OUTPUT_FUEL_MIX_CSV = "D:/NGCP/Plant_Fuel_Mix_5min_Daily_Summary.csv"
 
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
    if any(k in p for k in ["GEO", "MAIBARARA", "TIWI", "PALINPINON"]): return "Geothermal"
    if any(k in p for k in ["COAL", "TPP", "POWER_PLANT", "CALACA", "SUAL"]): return "Coal"
    if any(k in p for k in ["GAS", "CCGT", "SAN_LORENZO", "SAN_GABRIEL"]): return "Natural Gas"
    if any(k in p for k in ["DIESEL", "DPP", "BUNAWAN"]): return "Diesel / Oil"
    if any(k in p for k in ["BATTERY", "BESS"]): return "Battery Storage"
    return "Thermal / Others"
 
def load_dataset_recursively_safe(folder_name, mw_col_name, batch_size=2000):
    folder_path = os.path.join(BASE_DIR, folder_name)
    if not os.path.exists(folder_path):
        return None
 
    csv_files = [os.path.join(root, f) for root, _, files in os.walk(folder_path) for f in files if f.lower().endswith(".csv") and "daily_summary" not in f.lower()]
    if not csv_files:
        return None
 
    print(f"📂 Processing {len(csv_files):,} CSV files in `{folder_name}` (Memory-Safe)...")
    batch_dfs = []
    current_batch = []
 
    for idx, file_path in enumerate(sorted(csv_files), start=1):
        try:
            df = pl.read_csv(file_path, infer_schema_length=10000)
            df = df.rename({col: col.strip().upper() for col in df.columns})
 
            time_col = [c for c in df.columns if "TIME" in c or "INTERVAL" in c or "DATE" in c]
            target_mw = [c for c in df.columns if c in ["SCHED_MW", "MW", "SCHEDULED_MW", "DISPATCH_MW", "MW_OUTPUT", mw_col_name]]
 
            if not time_col or not target_mw:
                continue
 
            df = df.with_columns(
                pl.col(time_col[0])
                .str.to_datetime(format="%m/%d/%Y %H:%M", strict=False)
                .fill_null(pl.col(time_col[0]).str.to_datetime(format="%m/%d/%Y %I:%M:%S %p", strict=False))
                .fill_null(pl.col(time_col[0]).str.to_datetime(format="%m/%d/%Y %H:%M:%S", strict=False))
                .alias("Parsed_DateTime")
            ).filter(pl.col("Parsed_DateTime").is_not_null())
 
            # Cast and apply safety guard (clip RTD values to >= 0.0)
            mw_expr = pl.col(target_mw[0]).cast(pl.Float64, strict=False)
            if mw_col_name == "RTD_MW":
                mw_expr = mw_expr.clip(lower_bound=0.0)

            df = df.with_columns([
                pl.col("Parsed_DateTime").dt.date().alias("Date"),
                mw_expr.alias(mw_col_name)
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
                    pl.lit("GENERIC_PLANT").alias("RESOURCE_NAME"),
                    pl.lit("Thermal / Others").alias("FUEL_TYPE")
                ])
 
            daily = df.group_by(["Date", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME", "FUEL_TYPE"]).agg([
                pl.col(mw_col_name).mean().alias(f"{mw_col_name}_AVG"),
                pl.col(mw_col_name).max().alias(f"{mw_col_name}_PEAK")
            ])
            current_batch.append(daily)
 
            if len(current_batch) >= batch_size:
                consolidated = pl.concat(current_batch, how="diagonal").group_by(["Date", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME", "FUEL_TYPE"]).agg([
                    pl.col(f"{mw_col_name}_AVG").mean(),
                    pl.col(f"{mw_col_name}_PEAK").max()
                ])
                batch_dfs.append(consolidated)
                current_batch = []
                print(f"   Checkpoint [{idx}/{len(csv_files)}]: Memory cleared.")
 
        except Exception:
            continue
 
    if current_batch:
        batch_dfs.append(pl.concat(current_batch, how="diagonal"))
 
    if batch_dfs:
        final_df = pl.concat(batch_dfs, how="diagonal").group_by(["Date", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME", "FUEL_TYPE"]).agg([
            pl.col(f"{mw_col_name}_AVG").mean(),
            pl.col(f"{mw_col_name}_PEAK").max()
        ])
        return final_df
    return None
 
def process_plant_fuel_mix():
    print("=" * 60)
    print("STARTING PLANT-LEVEL PERFORMANCE & FUEL MIX PIPELINE")
    print("=" * 60)
 
    rtd_df = load_dataset_recursively_safe("RTD", "RTD_MW")
    gen_df = load_dataset_recursively_safe("Actual_Generation_Output", "ACTUAL_MW")
 
    active_dfs = []
    if rtd_df is not None: active_dfs.append(rtd_df)
    if gen_df is not None: active_dfs.append(gen_df)
 
    if not active_dfs:
        print("❌ Could not process datasets.")
        return
 
    keys = ["Date", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME", "FUEL_TYPE"]
 
    # DIAGONAL CONCATENATION PREVENTS JOIN DUPLICATES
    merged = pl.concat(active_dfs, how="diagonal").group_by(keys).agg([
        pl.col("RTD_MW_AVG").sum().fill_null(0.0) if "RTD_MW_AVG" in pl.concat(active_dfs, how="diagonal").columns else pl.lit(0.0),
        pl.col("RTD_MW_PEAK").max().fill_null(0.0) if "RTD_MW_PEAK" in pl.concat(active_dfs, how="diagonal").columns else pl.lit(0.0),
        pl.col("ACTUAL_MW_AVG").sum().fill_null(0.0) if "ACTUAL_MW_AVG" in pl.concat(active_dfs, how="diagonal").columns else pl.lit(0.0),
        pl.col("ACTUAL_MW_PEAK").max().fill_null(0.0) if "ACTUAL_MW_PEAK" in pl.concat(active_dfs, how="diagonal").columns else pl.lit(0.0)
    ])
 
    # ATTACH ACTUAL DEMAND SUMMARY IF AVAILABLE
    demand_summary_path = "D:/NGCP/Actual_Demand_5min_Daily_Summary.csv"
    if os.path.exists(demand_summary_path):
        demand_df = pl.read_csv(demand_summary_path).with_columns(pl.col("Date").str.to_date(strict=False))
        merged = merged.join(demand_df, on="Date", how="left").fill_null(0.0)
    else:
        merged = merged.with_columns([pl.lit(0.0).alias("SYSTEM_AVG"), pl.lit(0.0).alias("SYSTEM_PEAK")])
 
    merged.write_csv(OUTPUT_FUEL_MIX_CSV)
    print(f"\n✅ Plant Fuel Mix Benchmark successfully saved: {OUTPUT_FUEL_MIX_CSV} ({len(merged):,} records)")
 
if __name__ == "__main__":
    process_plant_fuel_mix()