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
    page_title="ACTUAL GENERATION OUTPUT - DISTRICT PERFORMANCE",
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
SUMMARY_CSV = "D:/NGCP/Actual_Generation_5min_Daily_Summary.csv"

@st.cache_data
def load_data(path):
    return pl.read_csv(path).to_pandas() if os.path.exists(path) else None

df = load_data(SUMMARY_CSV)

if df is None or df.empty:
    st.error(f"File missing or empty: `{SUMMARY_CSV}`. Please run `process_actual_generation_5min.py` first.")
    st.stop()

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

# ---------------------------------------------------------
# 3. CONTROL SLICERS & FILTERING PIPELINE
# ---------------------------------------------------------
top_hdr_left, top_hdr_right = st.columns([0.85, 3.15], gap="small")

with top_hdr_left:
    st.markdown('<div class="title-main">ACTUAL GENERATION OUTPUT</div>', unsafe_allow_html=True)
    st.markdown('<div class="title-sub">DISTRICT & PROVINCE PERFORMANCE</div>', unsafe_allow_html=True)

mid_left_slicers, mid_right_chart = st.columns([0.85, 3.15], gap="small")
filtered_df = df.copy()

with mid_left_slicers:
    if "REGION" in filtered_df.columns:
        selected_region = st.selectbox("Region Slicer", ["All Regions"] + sorted(filtered_df["REGION"].dropna().unique().tolist()))
        if selected_region != "All Regions":
            filtered_df = filtered_df[filtered_df["REGION"] == selected_region]

    if "PROVINCE_DISTRICT" in filtered_df.columns:
        selected_district = st.selectbox("District & Covered Provinces", ["All Districts"] + sorted(filtered_df["PROVINCE_DISTRICT"].dropna().unique().tolist()))
        if selected_district != "All Districts":
            filtered_df = filtered_df[filtered_df["PROVINCE_DISTRICT"] == selected_district]

    if "RESOURCE_NAME" in filtered_df.columns:
        selected_resources = st.multiselect("Resource / Plant Search", sorted(filtered_df["RESOURCE_NAME"].dropna().unique().tolist()))
        if selected_resources:
            filtered_df = filtered_df[filtered_df["RESOURCE_NAME"].isin(selected_resources)]

    years = sorted(filtered_df["Date"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
    selected_year = st.selectbox("Year Slicer", years, index=0)
    filtered_df = filtered_df[filtered_df["Date"].dt.year == selected_year]

    min_date, max_date = filtered_df["Date"].min().date(), filtered_df["Date"].max().date()
    selected_dates = st.date_input("Calendar Slicer", value=[min_date, max_date], min_value=min_date, max_value=max_date)
    if isinstance(selected_dates, (list, tuple)) and len(selected_dates) == 2:
        filtered_df = filtered_df[(filtered_df["Date"] >= pd.to_datetime(selected_dates[0])) & (filtered_df["Date"] <= pd.to_datetime(selected_dates[1]))]

# ---------------------------------------------------------
# 4. TOP EXECUTIVE KPI CARDS
# ---------------------------------------------------------
with top_hdr_right:
    tot_mwh = (filtered_df["MW_AVG"].sum() * 24)
    avg_mw = filtered_df["MW_AVG"].mean()
    peak_mw = filtered_df["MW_PEAK"].max()
    active_units = filtered_df["RESOURCE_NAME"].nunique() if "RESOURCE_NAME" in filtered_df.columns else 1

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">TOTAL DELIVERED MWh</div><div class="square-kpi-val">{tot_mwh:,.1f} <span class="square-kpi-unit">MWh</span></div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">PEAK GENERATION OUTPUT</div><div class="square-kpi-val">{peak_mw:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">AVG GENERATION (MW)</div><div class="square-kpi-val">{avg_mw:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">ACTIVE UNITS</div><div class="square-kpi-val">{active_units:,} <span class="square-kpi-unit">Units</span></div></div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 5. MIDDLE ROW: DYNAMIC DATE SPAN HEADER & TREND
# ---------------------------------------------------------
with mid_right_chart:
    min_sel_date = filtered_df["Date"].min()
    max_sel_date = filtered_df["Date"].max()

    is_start_of_month = (min_sel_date.day == 1)
    is_end_of_month = (max_sel_date == (min_sel_date + pd.offsets.MonthEnd(1)))

    if min_sel_date.month == max_sel_date.month and min_sel_date.year == max_sel_date.year and is_start_of_month and is_end_of_month:
        date_label = min_sel_date.strftime('%B %Y').upper()
    else:
        date_label = f"({min_sel_date.strftime('%b %d, %Y').upper()} - {max_sel_date.strftime('%b %d, %Y').upper()})"

    st.markdown(f'<div class="section-hdr-large">DAILY GENERATION TREND BY DISTRICT {date_label}</div>', unsafe_allow_html=True)

    daily_chart = filtered_df.groupby("Date")["MW_AVG"].sum().reset_index().sort_values("Date")
    daily_chart["Weekly_Avg"] = daily_chart["MW_AVG"].rolling(7, min_periods=1).mean()
    daily_chart["Day_Label"] = daily_chart["Date"].dt.strftime('%b %d')

    fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
    fig_combo.add_trace(go.Bar(x=daily_chart["Day_Label"], y=daily_chart["MW_AVG"], name="Daily Generation (MW)", marker_color="#00A3FF"), secondary_y=False)
    fig_combo.add_trace(go.Scatter(x=daily_chart["Day_Label"], y=daily_chart["Weekly_Avg"], name="Weekly Trend (MW)", line=dict(color="#F97316", width=2.5)), secondary_y=True)
    fig_combo.update_layout(template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22", height=380, margin=dict(l=10, r=10, t=15, b=10))
    st.plotly_chart(fig_combo, use_container_width=True)

# ---------------------------------------------------------
# 6. BOTTOM ROW: DISTRICT MATRIX & DONUT CHART
# ---------------------------------------------------------
bot_left, bot_right = st.columns([3, 2], gap="small")

with bot_left:
    st.markdown('<div class="section-hdr-large">DISTRICT PERFORMANCE MATRIX (MW)</div>', unsafe_allow_html=True)
    dist_matrix = filtered_df.groupby(["REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT"])["MW_AVG"].agg(["mean", "max", "count"]).reset_index().rename(
        columns={"REGION": "Region", "SUB_GRID_PREFIX": "Dist #", "PROVINCE_DISTRICT": "District & Covered Provinces", "mean": "Avg MW", "max": "Peak MW", "count": "Records"}
    ).sort_values(["Region", "Dist #"])
    dist_matrix["Avg MW"] = dist_matrix["Avg MW"].map(lambda x: f"{x:,.1f} MW")
    dist_matrix["Peak MW"] = dist_matrix["Peak MW"].map(lambda x: f"{x:,.1f} MW")
    st.dataframe(dist_matrix, use_container_width=True, hide_index=True)

with bot_right:
    st.markdown('<div class="section-hdr-large">DISTRICT CONTRIBUTION SHARE (%)</div>', unsafe_allow_html=True)
    pie_df = filtered_df.groupby("SUB_GRID_PREFIX")["MW_AVG"].sum().reset_index().sort_values("SUB_GRID_PREFIX")
    fig_pie = go.Figure(go.Pie(
        labels=pie_df["SUB_GRID_PREFIX"].apply(lambda x: f"District {x}"), values=pie_df["MW_AVG"], hole=0.45, sort=False,
        textinfo="percent", textposition="inside", textfont=dict(size=14, color="#FFFFFF", family="Arial Black")
    ))
    fig_pie.update_layout(template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22", height=320, margin=dict(l=10, r=10, t=10, b=35), legend=dict(font=dict(size=14, color="#FFFFFF")))
    st.plotly_chart(fig_pie, use_container_width=True)