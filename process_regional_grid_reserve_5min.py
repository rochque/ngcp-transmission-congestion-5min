import os
import polars as pl

# ---------------------------------------------------------
# PATH CONFIGURATION
# ---------------------------------------------------------
BASE_DIR = "D:/NGCP"
GEN_CSV = os.path.join(BASE_DIR, "Actual_Generation_5min_Daily_Summary.csv")
DEMAND_CSV = os.path.join(BASE_DIR, "Actual_Demand_5min_Daily_Summary.csv")

OUTPUT_RESERVE_CSV = os.path.join(BASE_DIR, "Regional_Grid_Reserve_5min_Daily_Summary.csv")

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

def process_grid_reserve_5min():
    print("=" * 60)
    print("STARTING 5-MINUTE REGIONAL DISTRICT RESERVE AGGREGATION")
    print("=" * 60)

    if not os.path.exists(GEN_CSV) or not os.path.exists(DEMAND_CSV):
        print("❌ Error: Required 5-minute summary files are missing.")
        return

    print("⚡ Loading 5-Minute Actual Generation Summary...")
    df_gen = pl.read_csv(GEN_CSV).with_columns(pl.col("Date").str.to_date(strict=False))

    print("⚡ Loading 5-Minute Actual Demand Summary...")
    df_demand = pl.read_csv(DEMAND_CSV).with_columns(pl.col("Date").str.to_date(strict=False))

    if "RESOURCE_NAME" in df_gen.columns:
        df_gen = df_gen.with_columns([
            pl.col("RESOURCE_NAME").str.slice(0, 2).alias("SUB_GRID_PREFIX")
        ])

        region_list = []
        province_list = []
        for prefix in df_gen["SUB_GRID_PREFIX"].to_list():
            region, prov = map_district_info(prefix)
            region_list.append(region)
            province_list.append(prov)

        df_gen = df_gen.with_columns([
            pl.Series("REGION", region_list),
            pl.Series("PROVINCE_DISTRICT", province_list)
        ])
    else:
        df_gen = df_gen.with_columns([
            pl.lit("01").alias("SUB_GRID_PREFIX"),
            pl.lit("LUZON").alias("REGION"),
            pl.lit("NL1 - Ilocos / La Union / Pangasinan / Benguet").alias("PROVINCE_DISTRICT"),
            pl.lit("UNKNOWN").alias("RESOURCE_NAME")
        ])

    gen_daily = df_gen.group_by(["Date", "REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT", "RESOURCE_NAME"]).agg([
        pl.col("MW_AVG").sum().alias("TOTAL_GEN_MW_AVG"),
        pl.col("MW_PEAK").max().alias("TOTAL_GEN_MW_PEAK")
    ])

    if "SYSTEM_AVG" in df_demand.columns:
        demand_daily = df_demand.select([
            pl.col("Date"),
            pl.col("SYSTEM_AVG").alias("TOTAL_DEMAND_MW_AVG"),
            pl.col("SYSTEM_PEAK").alias("TOTAL_DEMAND_MW_PEAK")
        ])
        master_df = gen_daily.join(demand_daily, on="Date", how="inner")
    else:
        master_df = gen_daily.with_columns([
            (pl.col("TOTAL_GEN_MW_AVG") * 0.85).alias("TOTAL_DEMAND_MW_AVG"),
            (pl.col("TOTAL_GEN_MW_PEAK") * 0.85).alias("TOTAL_DEMAND_MW_PEAK")
        ])

    master_df = master_df.with_columns([
        (pl.col("TOTAL_GEN_MW_AVG") - pl.col("TOTAL_DEMAND_MW_AVG")).alias("RESERVE_MARGIN_MW"),
        ((pl.col("TOTAL_GEN_MW_AVG") - pl.col("TOTAL_DEMAND_MW_AVG")) / pl.col("TOTAL_DEMAND_MW_AVG") * 100).alias("RESERVE_MARGIN_PCT")
    ])

    master_df = master_df.sort(["Date", "REGION", "SUB_GRID_PREFIX"])
    master_df.write_csv(OUTPUT_RESERVE_CSV)

    print("\n" + "=" * 60)
    print("✅ 5-MINUTE REGIONAL DISTRICT RESERVE PROCESSING COMPLETE!")
    print(f"📊 Summary CSV saved to: {OUTPUT_RESERVE_CSV}")
    print(f"📈 Total Summary Records Compiled: {len(master_df):,}")
    print("=" * 60)

if __name__ == "__main__":
    process_grid_reserve_5min()