import os
import polars as pl

BASE_DIR = "D:/NGCP/5_MINUTE_MARKET_DATA"
OUTPUT_CONGESTION_CSV = "D:/NGCP/Transmission_Congestion_5min_Daily_Summary.csv"
OUTPUT_RESOURCE_CURTAILMENT_CSV = "D:/NGCP/Subgrid_Resource_Curtailment_Summary.csv"
DEMAND_SUMMARY_CSV = "D:/NGCP/Actual_Demand_5min_Daily_Summary.csv"
CURTAILMENT_SUMMARY_CSV = "D:/NGCP/Grid_Congestion_5min_Daily_Summary.csv"

def process_transmission_and_resources():
    print("=" * 60)
    print("STARTING 5-MINUTE RESOURCE-LEVEL CONGESTION PIPELINE")
    print("=" * 60)

    # ---------------------------------------------------------
    # 1. PROCESS DAILY TRANSMISSION CONGESTION LOGS
    # ---------------------------------------------------------
    folder_candidates = ["Congestion", "CONGESTION", "Transmission_Congestion", "RE_Curtailment"]
    folder_path = None
    for candidate in folder_candidates:
        p = os.path.join(BASE_DIR, candidate)
        if os.path.exists(p):
            folder_path = p
            break
    if not folder_path:
        folder_path = BASE_DIR

    csv_files = [os.path.join(root, f) for root, _, files in os.walk(folder_path) for f in files if f.lower().endswith(".csv") and "daily_summary" not in f.lower()]
    
    processed_dfs = []
    req_cols = ["LUZON_BASE_CASE", "LUZON_CONTINGENCY", "VISAYAS_BASE_CASE", "VISAYAS_CONTINGENCY", "MINDANAO_BASE_CASE", "MINDANAO_CONTINGENCY"]

    for file_path in sorted(csv_files):
        try:
            df = pl.read_csv(file_path, infer_schema_length=10000)
            df = df.rename({col: col.strip().upper() for col in df.columns})

            time_col = [c for c in df.columns if "TIME" in c or "INTERVAL" in c or "DATE" in c]
            if not time_col or not any(c in df.columns for c in req_cols):
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
                pl.col("Parsed_DateTime").dt.hour().alias("Hour")
            ])

            select_exprs = [pl.col("Date"), pl.col("Hour")]
            for col in req_cols:
                if col in df.columns:
                    select_exprs.append(pl.col(col).cast(pl.Float64, strict=False).fill_null(0.0))
                else:
                    select_exprs.append(pl.lit(0.0).alias(col))

            df_clean = df.select(select_exprs)

            hourly = df_clean.group_by(["Date", "Hour"]).agg([
                pl.col("LUZON_BASE_CASE").sum().alias("LUZON_BASE_CASE"),
                pl.col("LUZON_CONTINGENCY").sum().alias("LUZON_CONTINGENCY"),
                pl.col("VISAYAS_BASE_CASE").sum().alias("VISAYAS_BASE_CASE"),
                pl.col("VISAYAS_CONTINGENCY").sum().alias("VISAYAS_CONTINGENCY"),
                pl.col("MINDANAO_BASE_CASE").sum().alias("MINDANAO_BASE_CASE"),
                pl.col("MINDANAO_CONTINGENCY").sum().alias("MINDANAO_CONTINGENCY")
            ])
            processed_dfs.append(hourly)
        except Exception:
            continue

    if processed_dfs:
        final_df = pl.concat(processed_dfs, how="diagonal").group_by(["Date", "Hour"]).agg([
            pl.col("LUZON_BASE_CASE").sum(),
            pl.col("LUZON_CONTINGENCY").sum(),
            pl.col("VISAYAS_BASE_CASE").sum(),
            pl.col("VISAYAS_CONTINGENCY").sum(),
            pl.col("MINDANAO_BASE_CASE").sum(),
            pl.col("MINDANAO_CONTINGENCY").sum()
        ])

        final_df = final_df.with_columns([
            (pl.col("LUZON_BASE_CASE") + pl.col("LUZON_CONTINGENCY")).alias("LUZON_TOTAL_CONGESTION"),
            (pl.col("VISAYAS_BASE_CASE") + pl.col("VISAYAS_CONTINGENCY")).alias("VISAYAS_TOTAL_CONGESTION"),
            (pl.col("MINDANAO_BASE_CASE") + pl.col("MINDANAO_CONTINGENCY")).alias("MINDANAO_TOTAL_CONGESTION"),
            (pl.col("LUZON_BASE_CASE") + pl.col("VISAYAS_BASE_CASE") + pl.col("MINDANAO_BASE_CASE")).alias("TOTAL_BASE_CASE"),
            (pl.col("LUZON_CONTINGENCY") + pl.col("VISAYAS_CONTINGENCY") + pl.col("MINDANAO_CONTINGENCY")).alias("TOTAL_CONTINGENCY")
        ])

        final_df = final_df.with_columns(
            (pl.col("TOTAL_BASE_CASE") + pl.col("TOTAL_CONTINGENCY")).alias("SYSTEM_TOTAL_CONGESTION")
        )

        if os.path.exists(DEMAND_SUMMARY_CSV):
            demand_df = pl.read_csv(DEMAND_SUMMARY_CSV).with_columns(pl.col("Date").str.to_date(strict=False))
            final_df = final_df.join(demand_df.select(["Date", "SYSTEM_AVG"]), on="Date", how="left").fill_null(0.0)
        else:
            final_df = final_df.with_columns(pl.lit(0.0).alias("SYSTEM_AVG"))

        if os.path.exists(CURTAILMENT_SUMMARY_CSV):
            curtail_df = pl.read_csv(CURTAILMENT_SUMMARY_CSV).with_columns(pl.col("Date").str.to_date(strict=False))
            curtail_reg = curtail_df.group_by(["Date", "REGION"]).agg(
                pl.col("CURTAILED_MW_AVG").sum().alias("CURTAILED_MW")
            )
            curtail_pivoted = curtail_reg.pivot(on="REGION", index="Date", values="CURTAILED_MW").fill_null(0.0)
            
            for r_col in ["LUZON", "VISAYAS", "MINDANAO"]:
                if r_col not in curtail_pivoted.columns:
                    curtail_pivoted = curtail_pivoted.with_columns(pl.lit(0.0).alias(r_col))
            
            curtail_pivoted = curtail_pivoted.rename({
                "LUZON": "LUZON_CURTAILED_MW",
                "VISAYAS": "VISAYAS_CURTAILED_MW",
                "MINDANAO": "MINDANAO_CURTAILED_MW"
            }).with_columns(
                (pl.col("LUZON_CURTAILED_MW") + pl.col("VISAYAS_CURTAILED_MW") + pl.col("MINDANAO_CURTAILED_MW")).alias("TOTAL_CURTAILED_MW")
            )

            final_df = final_df.join(curtail_pivoted, on="Date", how="left").fill_null(0.0)
        else:
            final_df = final_df.with_columns([
                pl.lit(0.0).alias("LUZON_CURTAILED_MW"),
                pl.lit(0.0).alias("VISAYAS_CURTAILED_MW"),
                pl.lit(0.0).alias("MINDANAO_CURTAILED_MW"),
                pl.lit(0.0).alias("TOTAL_CURTAILED_MW")
            ])

        final_df.sort(["Date", "Hour"]).write_csv(OUTPUT_CONGESTION_CSV)
        print(f"✅ Daily Summary saved: {OUTPUT_CONGESTION_CSV}")

    # ---------------------------------------------------------
    # 2. GENERATE SUBGRID RESOURCE CURTAILMENT SUMMARY (NEW TASK)
    # ---------------------------------------------------------
    curtailment_files = [os.path.join(root, f) for root, _, files in os.walk(BASE_DIR) for f in files if f.lower().endswith(".csv") and "curtail" in f.lower() and "daily_summary" not in f.lower()]
    
    if curtailment_files:
        print(f"📂 Scanning {len(curtailment_files):,} RE Curtailment files to build `{OUTPUT_RESOURCE_CURTAILMENT_CSV}`...")
        resource_dfs = []

        for f_path in curtailment_files:
            try:
                res_df = pl.read_csv(f_path, infer_schema_length=10000)
                res_df = res_df.rename({col: col.strip().upper() for col in res_df.columns})

                curtail_col = [c for c in res_df.columns if "CURTAIL" in c]

                if "RESOURCE_NAME" in res_df.columns and "FUEL_TYPE" in res_df.columns and curtail_col:
                    res_df = res_df.with_columns([
                        pl.col("RESOURCE_NAME").str.slice(0, 2).alias("DISTRICT_CODE"),
                        pl.col(curtail_col[0]).cast(pl.Float64, strict=False).fill_null(0.0).alias("CURTAILED_MW")
                    ])
                    resource_dfs.append(res_df.select(["DISTRICT_CODE", "RESOURCE_NAME", "FUEL_TYPE", "CURTAILED_MW"]))
            except Exception:
                continue

        if resource_dfs:
            final_resource_df = pl.concat(resource_dfs, how="diagonal").group_by(["DISTRICT_CODE", "RESOURCE_NAME", "FUEL_TYPE"]).agg([
                pl.col("CURTAILED_MW").sum().alias("TOTAL_RESOURCE_CURTAILED_MW"),
                pl.len().alias("CURTAILMENT_EVENTS_COUNT")
            ]).sort("TOTAL_RESOURCE_CURTAILED_MW", descending=True)

            final_resource_df.write_csv(OUTPUT_RESOURCE_CURTAILMENT_CSV)
            print(f"✅ Subgrid Resource Summary generated: {OUTPUT_RESOURCE_CURTAILMENT_CSV}")

if __name__ == "__main__":
    process_transmission_and_resources()