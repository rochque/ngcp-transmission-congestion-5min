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
    page_title="5-MIN GRID CONGESTION & RENEWABLE ABSORPTION REPORT",
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
    }

    .square-kpi-label { 
        color: #A0AAB8 !important; 
        font-size: 0.85rem !important; 
        font-weight: 800 !important; 
        text-transform: uppercase !important; 
        margin-bottom: 4px !important; 
    }

    .square-kpi-val { 
        color: #FFFFFF !important; 
        font-size: 1.75rem !important; 
        font-weight: 900 !important; 
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
    }

    .title-sub { 
        font-size: 1.0rem !important; 
        font-weight: 800 !important; 
        color: #00A3FF !important; 
    }

    .section-hdr-large { 
        font-size: 1.20rem !important; 
        font-weight: 900 !important; 
        color: #FFFFFF !important; 
        text-transform: uppercase !important; 
        margin-top: 8px !important; 
        margin-bottom: 6px !important; 
    }

    div[data-baseweb="select"] { 
        background-color: #161A22 !important; 
    }

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
SUMMARY_CSV = "D:/NGCP/Grid_Congestion_5min_Daily_Summary.csv"

@st.cache_data
def load_data(path):
    return pl.read_csv(path).to_pandas() if os.path.exists(path) else None

df = load_data(SUMMARY_CSV)

if df is None or df.empty:
    st.error(f"File missing or empty: `{SUMMARY_CSV}`. Please run `process_grid_congestion_5min.py` first.")
    st.stop()

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

# ---------------------------------------------------------
# 3. CONTROL SLICERS & NUMERICALLY SORTED DISTRICTS PIPELINE
# ---------------------------------------------------------
top_hdr_left, top_hdr_right = st.columns([0.85, 3.15], gap="small")

with top_hdr_left:
    st.markdown('<div class="title-main">5-MIN GRID CONGESTION & ABSORPTION</div>', unsafe_allow_html=True)
    st.markdown('<div class="title-sub">WESM RE CURTAILMENT & BESS TARGETING</div>', unsafe_allow_html=True)

mid_left_slicers, mid_right_chart = st.columns([0.85, 3.15], gap="small")
filtered_df = df.copy()

with mid_left_slicers:
    if "REGION" in filtered_df.columns:
        selected_region = st.selectbox("Region Slicer", ["All Regions"] + sorted(filtered_df["REGION"].dropna().unique().tolist()))
        if selected_region != "All Regions":
            filtered_df = filtered_df[filtered_df["REGION"] == selected_region]

    if "FUEL_TYPE" in filtered_df.columns:
        selected_fuels = st.multiselect("Resource / Fuel Tech", sorted(filtered_df["FUEL_TYPE"].dropna().unique().tolist()))
        if selected_fuels:
            filtered_df = filtered_df[filtered_df["FUEL_TYPE"].isin(selected_fuels)]

    # NUMERICALLY SORT DISTRICTS BY PREFIX (01 to 14)
    if "PROVINCE_DISTRICT" in filtered_df.columns:
        raw_districts = filtered_df["PROVINCE_DISTRICT"].dropna().unique().tolist()
        
        def extract_sort_key(dist_str):
            if "SUB_GRID_PREFIX" in filtered_df.columns:
                match = filtered_df[filtered_df["PROVINCE_DISTRICT"] == dist_str]["SUB_GRID_PREFIX"].values
                if len(match) > 0 and str(match[0]).isdigit():
                    return int(match[0])
            digits = "".join([c for c in dist_str if c.isdigit()])
            return int(digits) if digits else 99

        sorted_districts = sorted(raw_districts, key=extract_sort_key)
        selected_district = st.selectbox("District & Covered Provinces", ["All Districts"] + sorted_districts)
        
        if selected_district != "All Districts":
            filtered_df = filtered_df[filtered_df["PROVINCE_DISTRICT"] == selected_district]

    available_years = sorted(filtered_df["Date"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
    selected_year = st.selectbox("Year Slicer", available_years, index=0)
    filtered_df = filtered_df[filtered_df["Date"].dt.year == selected_year]

    min_date, max_date = filtered_df["Date"].min().date(), filtered_df["Date"].max().date()
    selected_dates = st.date_input("Calendar Slicer", value=[min_date, max_date], min_value=min_date, max_value=max_date)
    if isinstance(selected_dates, (list, tuple)) and len(selected_dates) == 2:
        filtered_df = filtered_df[(filtered_df["Date"] >= pd.to_datetime(selected_dates[0])) & (filtered_df["Date"] <= pd.to_datetime(selected_dates[1]))]

# ---------------------------------------------------------
# 4. TOP EXECUTIVE KPI CARDS
# ---------------------------------------------------------
with top_hdr_right:
    tot_curtailed_mw = filtered_df["CURTAILED_MW_AVG"].sum()
    avg_curtailed_mw = filtered_df["CURTAILED_MW_AVG"].mean()
    peak_curtailment_mw = filtered_df["CURTAILED_MW_PEAK"].max() if "CURTAILED_MW_PEAK" in filtered_df else 0.0
    
    avg_demand_mw = filtered_df["SYSTEM_AVG"].mean() if "SYSTEM_AVG" in filtered_df and filtered_df["SYSTEM_AVG"].mean() > 0 else 1.0
    
    # 5-MINUTE INTERVAL ACCURATE RATIO
    curtailment_ratio_pct = (avg_curtailed_mw / avg_demand_mw * 100) if avg_demand_mw > 0 else 0.0
    bess_target_mw = peak_curtailment_mw

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">TOTAL CURTAILED GENERATION</div><div class="square-kpi-val" style="color:#E53935;">{tot_curtailed_mw:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">PEAK CURTAILMENT SPIKE</div><div class="square-kpi-val" style="color:#F97316;">{peak_curtailment_mw:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">CURTAILMENT / DEMAND RATIO</div><div class="square-kpi-val" style="color:#00A3FF;">{curtailment_ratio_pct:.2f}%</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">BESS STORAGE TARGET CAPACITY</div><div class="square-kpi-val" style="color:#10B981;">{bess_target_mw:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 5. MIDDLE ROW: 5-MINUTE INTERVAL CURTAILMENT PROFILE
# ---------------------------------------------------------
with mid_right_chart:
    min_sel_date = filtered_df["Date"].min()
    max_sel_date = filtered_df["Date"].max()
    date_label = f"({min_sel_date.strftime('%b %d, %Y').upper()} - {max_sel_date.strftime('%b %d, %Y').upper()})"

    # TITLE UPDATED TO 5-MINUTE MARKET GRANULARITY
    st.markdown(f'<div class="section-hdr-large">5-MINUTE MARKET CURTAILMENT PROFILE VS SYSTEM DEMAND SHIFT (BESS OPPORTUNITY) {date_label}</div>', unsafe_allow_html=True)

    if "Hour" in filtered_df.columns:
        hourly = filtered_df.groupby("Hour")[["CURTAILED_MW_AVG", "SYSTEM_AVG"]].mean().reset_index()
        hourly["Hour"] = pd.to_numeric(hourly["Hour"], errors="coerce").fillna(0).astype(int)
        hourly = hourly.sort_values("Hour")
        hourly["Hour_Label"] = hourly["Hour"].apply(lambda h: f"{h:02d}:00")

        fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
        fig_combo.add_trace(go.Bar(x=hourly["Hour_Label"], y=hourly["CURTAILED_MW_AVG"], name="5-Min Curtailed MW (Midday Spike)", marker_color="#E53935"), secondary_y=False)
        fig_combo.add_trace(go.Scatter(x=hourly["Hour_Label"], y=hourly["SYSTEM_AVG"], name="System Grid Demand (MW)", line=dict(color="#00A3FF", width=3)), secondary_y=True)

        fig_combo.update_layout(
            template="plotly_dark", 
            paper_bgcolor="#161A22", 
            plot_bgcolor="#161A22", 
            height=380, 
            margin=dict(l=10, r=10, t=15, b=10),
            legend=dict(font=dict(size=11, color="#FFFFFF"))
        )
        st.plotly_chart(fig_combo, use_container_width=True)

# ---------------------------------------------------------
# 6. BOTTOM ROW: DISTRICT CONGESTION RANKINGS & FUEL TYPE SHARE
# ---------------------------------------------------------
bot_left, bot_right = st.columns([3, 2], gap="small")

with bot_left:
    st.markdown('<div class="section-hdr-large">DISTRICT TRANSMISSION BOTTLENECK RANKINGS (01 TO 14)</div>', unsafe_allow_html=True)
    
    dist_rank = filtered_df.groupby(["REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT"])[["CURTAILED_MW_AVG", "CURTAILED_MW_PEAK", "SYSTEM_AVG"]].agg({
        "CURTAILED_MW_AVG": "sum",
        "CURTAILED_MW_PEAK": "max",
        "SYSTEM_AVG": "mean"
    }).reset_index().rename(
        columns={
            "REGION": "Region", 
            "SUB_GRID_PREFIX": "Dist #", 
            "PROVINCE_DISTRICT": "District & Covered Provinces", 
            "CURTAILED_MW_AVG": "Total Curtailed MW", 
            "CURTAILED_MW_PEAK": "Peak Spike MW", 
            "SYSTEM_AVG": "Local Demand MW"
        }
    ).sort_values("Total Curtailed MW", ascending=False)

    dist_rank["Absorption Gap Ratio (%)"] = ((dist_rank["Total Curtailed MW"] / dist_rank["Local Demand MW"].replace(0, 1)) * 100).map(lambda x: f"{x:.2f}%")
    dist_rank["Total Curtailed MW"] = dist_rank["Total Curtailed MW"].map(lambda x: f"{x:,.1f} MW")
    dist_rank["Peak Spike MW"] = dist_rank["Peak Spike MW"].map(lambda x: f"{x:,.1f} MW")
    dist_rank["Local Demand MW"] = dist_rank["Local Demand MW"].map(lambda x: f"{x:,.1f} MW")

    st.dataframe(dist_rank, use_container_width=True, hide_index=True, height=420)

with bot_right:
    st.markdown('<div class="section-hdr-large">CURTAILED ENERGY BY RESOURCE TYPE (%)</div>', unsafe_allow_html=True)
    pie_df = filtered_df.groupby("FUEL_TYPE")["CURTAILED_MW_AVG"].sum().reset_index().sort_values("CURTAILED_MW_AVG", ascending=False)
    
    colors = {"Solar": "#F59E0B", "Wind": "#10B981", "Hydro": "#3B82F6", "Geothermal": "#F97316", "Variable RE / Other": "#8B5CF6"}

    fig_pie = go.Figure(go.Pie(
        labels=pie_df["FUEL_TYPE"], 
        values=pie_df["CURTAILED_MW_AVG"], 
        hole=0.45,
        textinfo="percent", 
        textposition="inside", 
        textfont=dict(size=13, color="#FFFFFF", family="Arial Black"),
        marker=dict(colors=[colors.get(f, "#00A3FF") for f in pie_df["FUEL_TYPE"]])
    ))

    fig_pie.update_layout(
        template="plotly_dark", 
        paper_bgcolor="#161A22", 
        plot_bgcolor="#161A22", 
        height=320, 
        margin=dict(l=10, r=10, t=10, b=35), 
        legend=dict(font=dict(size=11, color="#FFFFFF"))
    )
    st.plotly_chart(fig_pie, use_container_width=True)