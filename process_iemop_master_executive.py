import os
import polars as pl

# ---------------------------------------------------------
# PATH CONFIGURATION
# ---------------------------------------------------------
BASE_DIR = "D:/NGCP"
RTD_CSV = os.path.join(BASE_DIR, "RTD_5min_Daily_Summary.csv")
RTDRS_CSV = os.path.join(BASE_DIR, "RTDRS_5min_Daily_Summary.csv")
DEMAND_CSV = os.path.join(BASE_DIR, "Actual_Demand_5min_Daily_Summary.csv")
GEN_CSV = os.path.join(BASE_DIR, "Actual_Generation_5min_Daily_Summary.csv")

OUTPUT_MASTER_CSV = os.path.join(BASE_DIR, "IEMOP_Master_Executive_Summary.csv")

# District and Province Mapping Engine
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

def process_master_executive():
    print("=" * 60)
    print("STARTING IEMOP DISTRICT & PROVINCE MASTER AGGREGATION")
    print("=" * 60)

    if not os.path.exists(GEN_CSV) or not os.path.exists(DEMAND_CSV):
        print("❌ Error: Both Actual Demand and Actual Generation summaries are required.")
        return

    print("⚡ Loading Actual Generation Output Summary...")
    df_gen = pl.read_csv(GEN_CSV).with_columns(pl.col("Date").str.to_date(strict=False))

    print("⚡ Loading Actual Demand Summary...")
    df_demand = pl.read_csv(DEMAND_CSV).with_columns(pl.col("Date").str.to_date(strict=False))

    if "RESOURCE_NAME" in df_gen.columns:
        df_gen = df_gen.with_columns([
            pl.col("RESOURCE_NAME").str.slice(0, 2).alias("SUB_GRID_PREFIX")
        ])
        
        # Apply district and province mapping
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

    if os.path.exists(RTD_CSV):
        print("⚡ Merging RTD Market Schedules...")
        df_rtd = pl.read_csv(RTD_CSV).with_columns(pl.col("Date").str.to_date(strict=False))
        rtd_cols = [c for c in df_rtd.columns if c.endswith("_AVG")]
        if rtd_cols:
            df_gen = df_gen.join(
                df_rtd.select(["Date", "RESOURCE_NAME", rtd_cols[0]]),
                on=["Date", "RESOURCE_NAME"],
                how="left"
            ).rename({rtd_cols[0]: "RTD_MW_AVG"})

    if "RTD_MW_AVG" not in df_gen.columns:
        df_gen = df_gen.with_columns(pl.col("MW_AVG").alias("RTD_MW_AVG"))

    df_gen = df_gen.with_columns([
        (pl.col("MW_AVG") - pl.col("RTD_MW_AVG")).alias("UDD_MW"),
        (pl.col("MW_AVG") * 24).alias("DELIVERED_MWH")
    ])

    df_gen = df_gen.sort(["Date", "REGION", "SUB_GRID_PREFIX", "RESOURCE_NAME"])
    df_gen.write_csv(OUTPUT_MASTER_CSV)

    print("\n" + "=" * 60)
    print("✅ IEMOP DISTRICT & PROVINCE MASTER PROCESSING COMPLETE!")
    print(f"📊 Summary CSV saved to: {OUTPUT_MASTER_CSV}")
    print(f"📈 Total Detailed Records Compiled: {len(df_gen):,}")
    print("=" * 60)

if __name__ == "__main__":
    process_master_executive()