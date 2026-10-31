import os
import glob
import polars as pl

# ---------------------------------------------------------
# UPDATED FOLDER PATHS FOR 5-MINUTE MARKET DATA
# ---------------------------------------------------------
RTDRS_FOLDER = r"D:\NGCP\5_MINUTE_MARKET_DATA\RTDRS"
OUTPUT_FILE = r"D:\NGCP\RTDRS_5min_Daily_Summary.csv"

print("🔍 Scanning for 5-Minute RTDRS CSV files...")
all_files = glob.glob(os.path.join(RTDRS_FOLDER, "**/*.csv"), recursive=True)
valid_files = [f for f in all_files if not os.path.basename(f).startswith("._")]

print(f"📁 Found {len(valid_files)} valid RTDRS CSV files. Processing...")

target_cols = [
    "TIME_INTERVAL", "REGION_NAME", "RESOURCE_NAME", "RESOURCE_TYPE",
    "COMMODITY_TYPE", "MKT_TYPE", "SCHED_MW", "PRICE"
]

dfs = []
for f in valid_files:
    try:
        df_sub = pl.read_csv(
            f, 
            infer_schema_length=0, 
            ignore_errors=True, 
            truncate_ragged_lines=True
        )
        available = [c for c in target_cols if c in df_sub.columns]
        if len(available) == len(target_cols):
            df_cast = df_sub.select(target_cols).with_columns([
                pl.col("SCHED_MW").cast(pl.Float64, strict=False),
                pl.col("PRICE").cast(pl.Float64, strict=False)
            ])
            dfs.append(df_cast)
    except Exception:
        continue

if dfs:
    full_df = pl.concat(dfs, how="diagonal")
    
    summary_df = full_df.lazy().with_columns([
        pl.col("TIME_INTERVAL").str.to_datetime("%m/%d/%Y %I:%M:%S %p", strict=False)
    ]).filter(
        pl.col("TIME_INTERVAL").is_not_null()
    ).with_columns([
        pl.when(pl.col("TIME_INTERVAL").dt.day() >= 26)
          .then(pl.col("TIME_INTERVAL").dt.offset_by("1mo").dt.strftime("%Y-%m"))
          .otherwise(pl.col("TIME_INTERVAL").dt.strftime("%Y-%m"))
          .alias("Billing_Date"),
        pl.col("TIME_INTERVAL").dt.date().alias("Date")
    ]).with_columns([
        pl.col("Billing_Date").str.slice(0, 4).alias("Year"),
        pl.col("TIME_INTERVAL").dt.strftime("%b").alias("Month_Name")
    ]).group_by([
        "Year", "Billing_Date", "Month_Name", "Date", "REGION_NAME", 
        "COMMODITY_TYPE", "RESOURCE_NAME", "RESOURCE_TYPE", "MKT_TYPE"
    ]).agg([
        pl.col("SCHED_MW").mean().alias("SCHED_MW"),
        pl.col("PRICE").mean().alias("RESERVE_PRICE")
    ]).with_columns([
        # SCHEDULED_VOLUME (MWh) = SCHED_MW / 12 (5-min intervals)
        (pl.col("SCHED_MW") / 12.0).alias("SCHEDULED_VOLUME"),
        
        # EST_RESERVE_PAYMENT (₱) = SCHEDULED_VOLUME * RESERVE_PRICE
        ((pl.col("SCHED_MW") / 12.0) * pl.col("RESERVE_PRICE")).alias("EST_RESERVE_PAYMENT")
    ]).collect()

    summary_df.write_csv(OUTPUT_FILE)
    print(f"✅ DONE! 5-Minute RTDRS summary saved to: {OUTPUT_FILE}")
else:
    print("❌ No matching RTDRS CSV files could be parsed.")