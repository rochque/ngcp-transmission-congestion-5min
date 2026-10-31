import os
import polars as pl

BASE_DIR = "D:/NGCP/5_MINUTE_MARKET_DATA"
OUTPUT_DEMAND_CSV = "D:/NGCP/Actual_Demand_5min_Daily_Summary.csv"

def process_actual_demand():
    print("=" * 60)
    print("RE-COMPILING ACTUAL DEMAND (REGION & PEAK FIX)")
    print("=" * 60)

    possible_paths = [
        os.path.join(BASE_DIR, "Actual Demand.csv"),
        os.path.join(BASE_DIR, "Actual_Demand.csv"),
        os.path.join(BASE_DIR, "Actual Demand"),
        os.path.join(BASE_DIR, "Actual_Demand")
    ]

    target_files = []
    for path in possible_paths:
        if os.path.isfile(path) and path.lower().endswith(".csv"):
            target_files = [path]
            print(f"📁 Detected Single Demand File: `{os.path.basename(path)}`")
            break
        elif os.path.isdir(path):
            target_files = [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(".csv") and "daily_summary" not in f.lower()]
            print(f"📁 Detected Demand Folder: `{os.path.basename(path)}` containing {len(target_files)} CSV files.")
            break

    if not target_files:
        print(f"⚠️ No CSV file or folder named 'Actual Demand' found in `{BASE_DIR}`.")
        return

    processed_dfs = []
    for idx, file_path in enumerate(target_files, start=1):
        try:
            df = pl.read_csv(file_path, infer_schema_length=10000)
            df = df.rename({col: col.strip().upper() for col in df.columns})

            if "TIME_INTERVAL" not in df.columns:
                continue

            df = df.with_columns(
                pl.col("TIME_INTERVAL")
                .str.to_datetime(format="%m/%d/%Y %H:%M", strict=False)
                .fill_null(pl.col("TIME_INTERVAL").str.to_datetime(format="%m/%d/%Y %I:%M:%S %p", strict=False))
                .fill_null(pl.col("TIME_INTERVAL").str.to_datetime(format="%m/%d/%Y %H:%M:%S", strict=False))
                .alias("Parsed_DateTime")
            ).filter(pl.col("Parsed_DateTime").is_not_null())

            df = df.with_columns([pl.col("Parsed_DateTime").dt.date().alias("Date")])

            agg_exprs = []
            # System Demand
            if "SYSTEM" in df.columns:
                agg_exprs.append(pl.col("SYSTEM").cast(pl.Float64, strict=False).mean().alias("SYSTEM_AVG"))
            if "PEAK_SYSTEM" in df.columns:
                agg_exprs.append(pl.col("PEAK_SYSTEM").cast(pl.Float64, strict=False).max().alias("SYSTEM_PEAK"))
            elif "SYSTEM" in df.columns:
                agg_exprs.append(pl.col("SYSTEM").cast(pl.Float64, strict=False).max().alias("SYSTEM_PEAK"))

            # Luzon Demand
            if "LUZON" in df.columns:
                agg_exprs.append(pl.col("LUZON").cast(pl.Float64, strict=False).mean().alias("LUZON_AVG"))
            if "PEAK_LUZON" in df.columns:
                agg_exprs.append(pl.col("PEAK_LUZON").cast(pl.Float64, strict=False).max().alias("LUZON_PEAK"))
            elif "LUZON" in df.columns:
                agg_exprs.append(pl.col("LUZON").cast(pl.Float64, strict=False).max().alias("LUZON_PEAK"))

            # Visayas Demand
            if "VISAYAS" in df.columns:
                agg_exprs.append(pl.col("VISAYAS").cast(pl.Float64, strict=False).mean().alias("VISAYAS_AVG"))
            if "PEAK_VISAYAS" in df.columns:
                agg_exprs.append(pl.col("PEAK_VISAYAS").cast(pl.Float64, strict=False).max().alias("VISAYAS_PEAK"))
            elif "VISAYAS" in df.columns:
                agg_exprs.append(pl.col("VISAYAS").cast(pl.Float64, strict=False).max().alias("VISAYAS_PEAK"))

            # Mindanao Demand
            if "MINDANAO" in df.columns:
                agg_exprs.append(pl.col("MINDANAO").cast(pl.Float64, strict=False).mean().alias("MINDANAO_AVG"))
            if "PEAK_MINDANAO" in df.columns:
                agg_exprs.append(pl.col("PEAK_MINDANAO").cast(pl.Float64, strict=False).max().alias("MINDANAO_PEAK"))
            elif "MINDANAO" in df.columns:
                agg_exprs.append(pl.col("MINDANAO").cast(pl.Float64, strict=False).max().alias("MINDANAO_PEAK"))

            daily_summary = df.group_by("Date").agg(agg_exprs)
            processed_dfs.append(daily_summary)
        except Exception as e:
            print(f"   ❌ Error processing {os.path.basename(file_path)}: {e}")

    if processed_dfs:
        final_df = pl.concat(processed_dfs, how="diagonal").sort(["Date"])
        final_df.write_csv(OUTPUT_DEMAND_CSV)
        print(f"\n✅ Summary saved to: {OUTPUT_DEMAND_CSV} ({len(final_df):,} records)")

if __name__ == "__main__":
    process_actual_demand()