import os
import polars as pl
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & DARK CANVAS STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="5-MINUTE MARKET DATA: REGIONAL DISTRICT RESERVE ANALYSIS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown('''
    <style>
    .block-container {
        padding-top: 3.2rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 1.0rem !important;
        padding-right: 1.0rem !important;
        max-width: 100% !important;
    }
    
    body, .main { 
        background-color: #0A0E17 !important; 
    }

    .square-kpi-card {
        background-color: #161A22 !important;
        border: 1px solid #282F3D !important;
        border-radius: 8px !important;
        padding: 12px 8px !important;
        height: 105px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        box-sizing: border-box !important;
    }

    .square-kpi-label {
        color: #A0AAB8 !important;
        font-size: 0.85rem !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        margin-bottom: 4px !important;
        line-height: 1.2 !important;
        display: block !important;
    }

    .square-kpi-val {
        color: #FFFFFF !important;
        font-size: 1.75rem !important;
        font-weight: 900 !important;
        line-height: 1.1 !important;
        display: block !important;
    }

    .square-kpi-unit {
        font-size: 0.90rem !important;
        color: #A0AAB8 !important;
        font-weight: 600 !important;
    }

    .title-main {
        font-size: 1.80rem !important;
        font-weight: 900 !important;
        color: #FFFFFF !important;
        line-height: 1.15 !important;
        letter-spacing: 0.5px !important;
        margin-bottom: 2px !important;
    }
    
    .title-sub {
        font-size: 1.0rem !important;
        font-weight: 800 !important;
        color: #00A3FF !important;
        letter-spacing: 0.6px !important;
        margin-bottom: 0px !important;
    }

    .section-hdr-large {
        font-size: 1.20rem !important;
        font-weight: 900 !important;
        color: #FFFFFF !important;
        text-transform: uppercase !important;
        margin-top: 8px !important;
        margin-bottom: 6px !important;
        letter-spacing: 0.5px !important;
    }

    div[data-baseweb="select"] {
        background-color: #161A22 !important;
    }

    /* ENLARGED TABLE CELL FONT SIZE */
    div[data-testid="stDataFrame"] div[role="columnheader"] span {
        font-size: 1.05rem !important;
        font-weight: 800 !important;
        color: #00A3FF !important;
    }

    div[data-testid="stDataFrame"] div[role="gridcell"] {
        font-size: 1.0rem !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
    }
    </style>
''', unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. DATA INGESTION
# ---------------------------------------------------------
RESERVE_CSV = "D:/NGCP/Regional_Grid_Reserve_5min_Daily_Summary.csv"

@st.cache_data
def load_reserve_summary(csv_path):
    if not os.path.exists(csv_path):
        return None
    df_pl = pl.read_csv(csv_path)
    df_pd = df_pl.to_pandas()
    return df_pd

df = load_reserve_summary(RESERVE_CSV)

if df is None or df.empty:
    st.error(f"Reserve Summary CSV not found or empty: `{RESERVE_CSV}`. Please run `process_regional_grid_reserve_5min.py` first.")
    st.stop()

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

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

if "PROVINCE_DISTRICT" not in df.columns:
    df["REGION"] = df["SUB_GRID_PREFIX"].apply(lambda p: DISTRICT_PROVINCE_MAP.get(str(p)[:2], ("OTHER", f"District {p}"))[0])
    df["PROVINCE_DISTRICT"] = df["SUB_GRID_PREFIX"].apply(lambda p: DISTRICT_PROVINCE_MAP.get(str(p)[:2], ("OTHER", f"District {p}"))[1])

# ---------------------------------------------------------
# 3. CONTROL SLICERS & FILTERING PIPELINE
# ---------------------------------------------------------
top_hdr_left, top_hdr_right = st.columns([0.85, 3.15], gap="small")

with top_hdr_left:
    st.markdown('<div class="title-main">REGIONAL GRID RESERVE</div>', unsafe_allow_html=True)
    st.markdown('<div class="title-sub">5-MINUTE MARKET DATA DISTRICT ANALYSIS</div>', unsafe_allow_html=True)

mid_left_slicers, mid_right_chart = st.columns([0.85, 3.15], gap="small")

filtered_df = df.copy()

with mid_left_slicers:
    # 1. Region Slicer
    available_regions = ["All Regions", "LUZON", "VISAYAS", "MINDANAO"]
    selected_region = st.selectbox("Region Slicer", available_regions)

    if selected_region != "All Regions":
        filtered_df = filtered_df[filtered_df["REGION"] == selected_region]

    # 2. District & Province Slicer
    available_districts = sorted([d for d in filtered_df["PROVINCE_DISTRICT"].dropna().unique().tolist() if str(d).strip() != ""])
    selected_district = st.selectbox("District & Province Slicer", ["All Districts & Provinces"] + available_districts)

    if selected_district != "All Districts & Provinces":
        filtered_df = filtered_df[filtered_df["PROVINCE_DISTRICT"] == selected_district]

    # 3. Resource / Plant Search
    resource_col = "RESOURCE_NAME" if "RESOURCE_NAME" in filtered_df.columns else None
    if resource_col:
        available_resources = sorted([r for r in filtered_df[resource_col].dropna().unique().tolist() if str(r).strip() != ""])
        selected_resources = st.multiselect("Resource / Plant Search", available_resources)
        if selected_resources:
            filtered_df = filtered_df[filtered_df[resource_col].isin(selected_resources)]

    # 4. Dynamic Year Slicer
    available_years = sorted(filtered_df["Date"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
    if not available_years:
        st.error("No valid year data found.")
        st.stop()

    selected_year = st.selectbox("Year Slicer", available_years, index=0)
    filtered_df = filtered_df[filtered_df["Date"].dt.year == selected_year]

    if filtered_df.empty:
        st.warning("⚠️ No data available for selected criteria.")
        st.stop()

    # 5. Calendar Slicer
    max_date = filtered_df["Date"].max().date()
    min_date = filtered_df["Date"].min().date()

    selected_dates = st.date_input(
        "Month/Day Calendar Slicer", 
        value=[min_date, max_date],
        min_value=min_date,
        max_value=max_date
    )

    if isinstance(selected_dates, (list, tuple)):
        if len(selected_dates) == 2:
            s_date, e_date = selected_dates
            filtered_df = filtered_df[(filtered_df["Date"] >= pd.to_datetime(s_date)) & (filtered_df["Date"] <= pd.to_datetime(e_date))]
        elif len(selected_dates) == 1:
            s_date = selected_dates[0]
            filtered_df = filtered_df[filtered_df["Date"] == pd.to_datetime(s_date)]

    if filtered_df.empty:
        st.warning("⚠️ No data available for selected date range.")
        st.stop()

# ---------------------------------------------------------
# 4. TOP EXECUTIVE KPI CARDS
# ---------------------------------------------------------
with top_hdr_right:
    gen_val = filtered_df["TOTAL_GEN_MW_AVG"].sum()
    demand_val = filtered_df["TOTAL_DEMAND_MW_AVG"].sum()
    reserve_margin = filtered_df["RESERVE_MARGIN_MW"].mean()
    reserve_pct = filtered_df["RESERVE_MARGIN_PCT"].mean()

    c1, c2, c3, c4 = st.columns(4, gap="small")

    with c1:
        st.markdown(f'''
            <div class="square-kpi-card">
                <div class="square-kpi-label">TOTAL GENERATION OUTPUT</div>
                <div class="square-kpi-val">{gen_val * 24:,.1f} <span class="square-kpi-unit">MWh</span></div>
            </div>
        ''', unsafe_allow_html=True)

    with c2:
        st.markdown(f'''
            <div class="square-kpi-card">
                <div class="square-kpi-label">TOTAL SYSTEM DEMAND</div>
                <div class="square-kpi-val">{demand_val * 24:,.1f} <span class="square-kpi-unit">MWh</span></div>
            </div>
        ''', unsafe_allow_html=True)

    with c3:
        st.markdown(f'''
            <div class="square-kpi-card">
                <div class="square-kpi-label">REAL-TIME RESERVE MARGIN</div>
                <div class="square-kpi-val">{reserve_margin:+,.1f} <span class="square-kpi-unit">MW</span></div>
            </div>
        ''', unsafe_allow_html=True)

    with c4:
        st.markdown(f'''
            <div class="square-kpi-card">
                <div class="square-kpi-label">RESERVE BUFFER RATIO</div>
                <div class="square-kpi-val">{reserve_pct:+.2f}%</div>
            </div>
        ''', unsafe_allow_html=True)

# ---------------------------------------------------------
# 5. MIDDLE ROW: SUPPLY VS DEMAND BALANCE TREND
# ---------------------------------------------------------
with mid_right_chart:
    min_sel_date = filtered_df["Date"].min()
    max_sel_date = filtered_df["Date"].max()
    
    if min_sel_date.month == max_sel_date.month and min_sel_date.year == max_sel_date.year:
        date_label = min_sel_date.strftime('%B %Y').upper()
    else:
        date_label = f"{min_sel_date.strftime('%b %d, %Y').upper()} - {max_sel_date.strftime('%b %d, %Y').upper()}"

    st.markdown(f'<div class="section-hdr-large">DAILY SUPPLY VS DEMAND BALANCE TREND ({date_label})</div>', unsafe_allow_html=True)

    daily_chart = filtered_df.groupby("Date").agg({
        "TOTAL_GEN_MW_AVG": "sum",
        "TOTAL_DEMAND_MW_AVG": "mean",
        "RESERVE_MARGIN_MW": "mean"
    }).reset_index().sort_values("Date")

    daily_chart["Day_Label"] = daily_chart["Date"].dt.strftime('%b %d')

    fig_combo = make_subplots(specs=[[{"secondary_y": True}]])

    fig_combo.add_trace(
        go.Bar(
            x=daily_chart["Day_Label"], 
            y=daily_chart["TOTAL_DEMAND_MW_AVG"], 
            name="Actual Demand (MW)", 
            marker_color="#00A3FF"
        ),
        secondary_y=False
    )

    fig_combo.add_trace(
        go.Scatter(
            x=daily_chart["Day_Label"], 
            y=daily_chart["TOTAL_GEN_MW_AVG"], 
            name="Available Generation (MW)", 
            line=dict(color="#F97316", width=2.5)
        ),
        secondary_y=False
    )

    fig_combo.add_trace(
        go.Scatter(
            x=daily_chart["Day_Label"], 
            y=daily_chart["RESERVE_MARGIN_MW"], 
            name="Reserve Margin Buffer (MW)", 
            line=dict(color="#10B981", width=2.0, dash="dot")
        ),
        secondary_y=True
    )

    fig_combo.update_layout(
        template="plotly_dark",
        paper_bgcolor="#161A22",
        plot_bgcolor="#161A22",
        height=380,
        margin=dict(l=10, r=10, t=15, b=10),
        barmode="group",
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="center", x=0.5, font=dict(size=12)),
        xaxis=dict(title="Date", gridcolor="#282F3D")
    )

    fig_combo.update_yaxes(title_text="Power Supply / Demand (MW)", secondary_y=False, gridcolor="#282F3D")
    fig_combo.update_yaxes(title_text="Reserve Headroom (MW)", secondary_y=True, showgrid=False)

    st.plotly_chart(fig_combo, use_container_width=True)

# ---------------------------------------------------------
# 6. BOTTOM ROW: DISTRICT MATRIX & DONUT CHART
# ---------------------------------------------------------
bot_left, bot_right = st.columns([3, 2], gap="small")

with bot_left:
    st.markdown('<div class="section-hdr-large">DISTRICT SUPPLY & RESERVE BALANCE MATRIX (MW)</div>', unsafe_allow_html=True)

    reserve_matrix = (
        filtered_df.groupby(["REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT"]).agg({
            "TOTAL_GEN_MW_AVG": "mean",
            "TOTAL_DEMAND_MW_AVG": "mean",
            "RESERVE_MARGIN_MW": "mean"
        })
        .reset_index()
        .rename(columns={
            "REGION": "Region",
            "SUB_GRID_PREFIX": "Dist #",
            "PROVINCE_DISTRICT": "District & Covered Provinces",
            "TOTAL_GEN_MW_AVG": "Avg Gen (MW)",
            "TOTAL_DEMAND_MW_AVG": "Avg Demand (MW)",
            "RESERVE_MARGIN_MW": "Reserve Margin (MW)"
        })
        .sort_values(["Region", "Dist #"])
    )

    reserve_matrix["Avg Gen (MW)"] = reserve_matrix["Avg Gen (MW)"].map(lambda x: f"{x:,.1f} MW")
    reserve_matrix["Avg Demand (MW)"] = reserve_matrix["Avg Demand (MW)"].map(lambda x: f"{x:,.1f} MW")
    reserve_matrix["Reserve Margin (MW)"] = reserve_matrix["Reserve Margin (MW)"].map(lambda x: f"{x:+,.1f} MW")

    st.dataframe(reserve_matrix, use_container_width=True, hide_index=True)

with bot_right:
    st.markdown('<div class="section-hdr-large">DISTRICT GENERATION CONTRIBUTION SHARE (%)</div>', unsafe_allow_html=True)

    pie_df = (
        filtered_df.groupby("SUB_GRID_PREFIX")["TOTAL_GEN_MW_AVG"]
        .sum()
        .reset_index()
        .sort_values("SUB_GRID_PREFIX", ascending=True)
    )

    fig_pie = go.Figure(go.Pie(
        labels=pie_df["SUB_GRID_PREFIX"].apply(lambda x: f"District {x}"),
        values=pie_df["TOTAL_GEN_MW_AVG"],
        hole=0.45,
        sort=False,
        textinfo="percent",
        textposition="inside",
        insidetextorientation="horizontal",
        textfont=dict(size=14, color="#FFFFFF", family="Arial Black"),
        marker=dict(colors=[
            "#00A3FF", "#F97316", "#10B981", "#E53935", "#8B5CF6", 
            "#EC4899", "#F59E0B", "#14B8A6", "#6366F1", "#A855F7"
        ])
    ))

    fig_pie.update_layout(
        title=dict(
            text="<b>District Generation Share</b>",
            font=dict(size=16, color="#FFFFFF"),
            x=0.5, xanchor="center", y=0.98
        ),
        template="plotly_dark",
        paper_bgcolor="#161A22", 
        plot_bgcolor="#161A22",
        height=320, 
        margin=dict(l=10, r=10, t=35, b=35),
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=-0.42, 
            xanchor="center", 
            x=0.5,
            font=dict(size=14, color="#FFFFFF")
        )
    )

    st.plotly_chart(fig_pie, use_container_width=True)