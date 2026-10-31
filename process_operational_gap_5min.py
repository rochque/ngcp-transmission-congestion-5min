import os
import polars as pl

BASE_DIR = "D:/NGCP/5_MINUTE_MARKET_DATA"
OUTPUT_GAP_CSV = "D:/NGCP/Operational_Gap_5min_Daily_Summary.csv"

# Conversion map converted to a Polars DataFrame for fast, native joins
MAP_DATA = [
    {"SUB_GRID_PREFIX": "01", "REGION": "LUZON", "PROVINCE_DISTRICT": "NL1 - Ilocos / La Union / Pangasinan / Benguet"},
    {"SUB_GRID_PREFIX": "02", "REGION": "LUZON", "PROVINCE_DISTRICT": "CL2 - Bataan / Bulacan / Pampanga / Tarlac / Zambales"},
    {"SUB_GRID_PREFIX": "03", "REGION": "LUZON", "PROVINCE_DISTRICT": "SL3 - Batangas / Cavite / Laguna / Quezon / Bicol"},
    {"SUB_GRID_PREFIX": "04", "REGION": "VISAYAS", "PROVINCE_DISTRICT": "Panay 04 - Iloilo / Aklan / Capiz / Antique"},
    {"SUB_GRID_PREFIX": "05", "REGION": "VISAYAS", "PROVINCE_DISTRICT": "Cebu 05 - Metro Cebu / Mandaue / Mactan"},
    {"SUB_GRID_PREFIX": "06", "REGION": "VISAYAS", "PROVINCE_DISTRICT": "Negros 06 - Negros Occidental / Negros Oriental"},
    {"SUB_GRID_PREFIX": "07", "REGION": "VISAYAS", "PROVINCE_DISTRICT": "Leyte 07 - Leyte / Biliran / Southern Leyte"},
    {"SUB_GRID_PREFIX": "08", "REGION": "VISAYAS", "PROVINCE_DISTRICT": "Samar 08 - Western Samar / Northern / Eastern Samar"},
    {"SUB_GRID_PREFIX": "09", "REGION": "MINDANAO", "PROVINCE_DISTRICT": "SM9 - Metro Davao / Davao del Norte / Sur"},
    {"SUB_GRID_PREFIX": "10", "REGION": "MINDANAO", "PROVINCE_DISTRICT": "NM10 - Misamis Oriental / Bukidnon / CDO / Lanao Norte"},
    {"SUB_GRID_PREFIX": "11", "REGION": "MINDANAO", "PROVINCE_DISTRICT": "Soccsksargen 11 - South Cotabato / GenSan / Sultan Kudarat"},
    {"SUB_GRID_PREFIX": "12", "REGION": "MINDANAO", "PROVINCE_DISTRICT": "WM12 - Zamboanga City / Del Sur / Del Norte / Sibugay"},
    {"SUB_GRID_PREFIX": "13", "REGION": "MINDANAO", "PROVINCE_DISTRICT": "Caraga 13 - Agusan del Norte / Surigao / Butuan"},
    {"SUB_GRID_PREFIX": "14", "REGION": "MINDANAO", "PROVINCE_DISTRICT": "BARMM 14 - Maguindanao / Lanao Sur / Sulu"}
]
map_df = pl.DataFrame(MAP_DATA)

def load_dataset_recursively_safe(folder_name, mw_col_name, batch_size=2000):
    folder_path = os.path.join(BASE_DIR, folder_name)
    if not os.path.exists(folder_path):
        return None

    csv_files = [
        os.path.join(root, f) 
        for root, _, files in os.walk(folder_path) 
        for f in files if f.lower().endswith(".csv") and "daily_summary" not in f.lower()
    ]
    if not csv_files:
        return None

    print(f"📂 Processing {len(csv_files):,} CSV files in `{folder_name}`...")

    collected_dfs = []

    for idx, file_path in enumerate(sorted(csv_files), start=1):
        try:
            df = pl.read_csv(file_path, infer_schema_length=10000)
            df = df.rename({col: col.strip().upper() for col in df.columns})

            time_col = [c for c in df.columns if any(k in c for k in ["TIME", "INTERVAL", "DATE"])]
            target_mw = [c for c in df.columns if c in ["SCHED_MW", "MW", "SCHEDULED_MW", "DISPATCH_MW", "MW_OUTPUT", mw_col_name]]

            if not time_col or not target_mw:
                continue

            # Parse datetime
            df = df.with_columns(
                pl.col(time_col[0])
                .str.to_datetime(format="%m/%d/%Y %H:%M", strict=False)
                .fill_null(pl.col(time_col[0]).str.to_datetime(format="%m/%d/%Y %I:%M:%S %p", strict=False))
                .fill_null(pl.col(time_col[0]).str.to_datetime(format="%m/%d/%Y %H:%M:%S", strict=False))
                .alias("Parsed_DateTime")
            ).filter(pl.col("Parsed_DateTime").is_not_null())

            df = df.with_columns([
                pl.col("Parsed_DateTime").dt.date().alias("Date"),
                pl.col(target_mw[0]).cast(pl.Float64, strict=False).alias(mw_col_name)
            ])

            if "RESOURCE_NAME" in df.columns:
                df = df.with_columns([
                    pl.col("RESOURCE_NAME").str.strip_chars().str.to_uppercase().alias("RESOURCE_NAME"),
                    pl.col("RESOURCE_NAME").str.slice(0, 2).alias("SUB_GRID_PREFIX")
                ])
                df = df.join(map_df, on="SUB_GRID_PREFIX", how="left").with_columns([
                    pl.col("REGION").fill_null("OTHER"),
                    pl.col("PROVINCE_DISTRICT").fill_null("Other Provinces")
                ])
            else:
                df = df.with_columns([
                    pl.lit("01").alias("SUB_GRID_PREFIX"),
                    pl.lit("LUZON").alias("REGION"),
                    pl.lit("NL1 - Ilocos / La Union / Pangasinan / Benguet").alias("PROVINCE_DISTRICT"),
                    pl.lit("GENERIC_PLANT").alias("RESOURCE_NAME")
                ])

            # Calculate actual average MW per resource per date directly
            daily = df.group_by(["Date", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME"]).agg([
                pl.col(mw_col_name).mean().alias(f"{mw_col_name}_AVG")
            ])
            collected_dfs.append(daily)

        except Exception:
            continue

    if collected_dfs:
        # Single final aggregation ensures clean arithmetic mean without batch distortions
        final_df = (
            pl.concat(collected_dfs, how="diagonal")
            .group_by(["Date", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME"])
            .agg(pl.col(f"{mw_col_name}_AVG").mean())
        )
        return final_df

    return None

def process_operational_gap():
    print("=" * 60)
    print("STARTING DIAGONAL AGGREGATION OPERATIONAL GAP PIPELINE")
    print("=" * 60)

    rtd_df = load_dataset_recursively_safe("RTD", "RTD_MW")
    rtdrs_df = load_dataset_recursively_safe("RTDRS", "RTDRS_MW")
    gen_df = load_dataset_recursively_safe("Actual_Generation_Output", "ACTUAL_MW")

    active_dfs = [df for df in [rtd_df, rtdrs_df, gen_df] if df is not None]

    if not active_dfs:
        print("❌ Could not load datasets.")
        return

    keys = ["Date", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME"]

    # Combine datasets
    merged = pl.concat(active_dfs, how="diagonal").group_by(keys).agg([
        pl.col("RTD_MW_AVG").first().fill_null(0.0) if "RTD_MW_AVG" in pl.concat(active_dfs, how="diagonal").columns else pl.lit(0.0),
        pl.col("RTDRS_MW_AVG").first().fill_null(0.0) if "RTDRS_MW_AVG" in pl.concat(active_dfs, how="diagonal").columns else pl.lit(0.0),
        pl.col("ACTUAL_MW_AVG").first().fill_null(0.0) if "ACTUAL_MW_AVG" in pl.concat(active_dfs, how="diagonal").columns else pl.lit(0.0),
    ])

    # Compute Operational Gap Metrics
    merged = merged.with_columns([
        (pl.col("RTDRS_MW_AVG") - pl.col("RTD_MW_AVG")).alias("REDISPATCH_IMPACT_MW"),
        (pl.col("ACTUAL_MW_AVG") - pl.col("RTDRS_MW_AVG")).alias("UDD_COMPLIANCE_GAP_MW"),
        (pl.col("ACTUAL_MW_AVG") - pl.col("RTD_MW_AVG")).alias("TOTAL_OPERATIONAL_GAP_MW")
    ]).sort(["Date"])

    merged.write_csv(OUTPUT_GAP_CSV)
    print(f"\n✅ Operational Gap Summary successfully saved: {OUTPUT_GAP_CSV} ({len(merged):,} records)")

if __name__ == "__main__":
    process_operational_gap()