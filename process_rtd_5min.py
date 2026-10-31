import os
import glob
import polars as pl

# Old Path:
# RTD_FOLDER = r"D:\NGCP\RTD"

# New Path:
RTD_FOLDER = r"D:\NGCP\5_MINUTE_MARKET_DATA\RTD"
OUTPUT_FILE = r"D:\NGCP\RTD_5min_Daily_Summary.csv"

print("🔍 Scanning for RTD CSV files...")
all_files = glob.glob(os.path.join(RTD_FOLDER, "**/*.csv"), recursive=True)
valid_files = [f for f in all_files if not os.path.basename(f).startswith("._")]

print(f"📁 Found {len(valid_files)} valid CSV files. Starting memory-safe batch processing...")

target_cols = [
    "TIME_INTERVAL", "REGION_NAME", "RESOURCE_NAME", "MKT_TYPE",
    "SCHED_MW", "LMP", "LMP_SMP", "LMP_LOSS", "LMP_CONGESTION", "LOSS_FACTOR"
]

num_cols = ["SCHED_MW", "LMP", "LMP_SMP", "LMP_LOSS", "LMP_CONGESTION", "LOSS_FACTOR"]

processed_dfs = []

# Process in small file chunks to ensure RAM stays low
batch_size = 50
for i in range(0, len(valid_files), batch_size):
    batch = valid_files[i:i + batch_size]
    if i % 500 == 0 or i == 0:
        print(f"⚡ Processing batch {i // batch_size + 1} / {(len(valid_files) - 1) // batch_size + 1}...")
    
    sub_frames = []
    for f in batch:
        try:
            # Force schema override or cast immediately per file to avoid Int64 vs Float64 conflicts
            df_sub = pl.read_csv(
                f, 
                infer_schema_length=0,  # Reads all columns as Utf8 (String) initially to prevent type errors
                ignore_errors=True,
                truncate_ragged_lines=True
            )
            available = [c for c in target_cols if c in df_sub.columns]
            if len(available) == len(target_cols):
                # Cast numeric columns to Float64 explicitly per file before combining
                cast_expressions = [pl.col(c).cast(pl.Float64, strict=False) for c in num_cols]
                sub_frames.append(df_sub.select(target_cols).with_columns(cast_expressions))
        except Exception:
            continue
            
    if sub_frames:
        batch_df = pl.concat(sub_frames, how="diagonal")
        
        # Immediate daily aggregation per batch
        daily_batch = batch_df.lazy().with_columns([
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
            "Year", "Billing_Date", "Month_Name", "Date", "REGION_NAME", "RESOURCE_NAME", "MKT_TYPE"
        ]).agg([
            pl.col("SCHED_MW").mean().alias("SCHED_MW"),
            pl.col("LMP").mean().alias("LMP"),
            pl.col("LMP_SMP").mean().alias("LMP_SMP"),
            pl.col("LMP_LOSS").mean().alias("LMP_LOSS"),
            pl.col("LMP_CONGESTION").mean().alias("LMP_CONGESTION"),
            pl.col("LOSS_FACTOR").mean().alias("LOSS_FACTOR")
        ]).collect()
        
        processed_dfs.append(daily_batch)

print("🧩 Finalizing combined multi-year daily summary...")
final_df = pl.concat(processed_dfs, how="diagonal").group_by([
    "Year", "Billing_Date", "Month_Name", "Date", "REGION_NAME", "RESOURCE_NAME", "MKT_TYPE"
]).agg([
    pl.col("SCHED_MW").mean().alias("SCHED_MW"),
    pl.col("LMP").mean().alias("LMP"),
    pl.col("LMP_SMP").mean().alias("LMP_SMP"),
    pl.col("LMP_LOSS").mean().alias("LMP_LOSS"),
    pl.col("LMP_CONGESTION").mean().alias("LMP_CONGESTION"),
    pl.col("LOSS_FACTOR").mean().alias("LOSS_FACTOR")
])

final_df.write_csv(OUTPUT_FILE)
print(f"✅ DONE! Compact summary saved to: {OUTPUT_FILE}")