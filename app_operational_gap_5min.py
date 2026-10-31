import os
import polars as pl
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="MARKET DISPATCH VS OPERATIONAL GAP REPORT",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown('''
    <style>
    .block-container { 
        padding-top: 2.0rem !important; 
        padding-bottom: 0.5rem !important; 
        padding-left: 1.0rem !important; 
        padding-right: 1.0rem !important; 
        max-width: 100% !important; 
    }
    body, .main { background-color: #0A0E17 !important; }
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
        font-size: 0.82rem !important; 
        font-weight: 800 !important; 
        text-transform: uppercase !important; 
        margin-bottom: 4px !important; 
    }
    .square-kpi-val { 
        color: #FFFFFF !important; 
        font-size: 1.70rem !important; 
        font-weight: 900 !important; 
    }
    .square-kpi-unit { 
        font-size: 0.85rem !important; 
        color: #A0AAB8 !important; 
        font-weight: 600 !important; 
    }
    .title-main { font-size: 1.80rem !important; font-weight: 900 !important; color: #FFFFFF !important; }
    .title-sub { font-size: 1.0rem !important; font-weight: 800 !important; color: #00A3FF !important; }
    .section-hdr-large { 
        font-size: 1.10rem !important; 
        font-weight: 900 !important; 
        color: #FFFFFF !important; 
        text-transform: uppercase !important; 
        margin-top: 8px !important; 
        margin-bottom: 6px !important; 
    }
    div[data-baseweb="select"] { background-color: #161A22 !important; }
    div[data-testid="stDataFrame"] div[role="columnheader"] span { 
        font-size: 0.95rem !important; 
        font-weight: 800 !important; 
        color: #00A3FF !important; 
    }
    div[data-testid="stDataFrame"] div[role="gridcell"] { 
        font-size: 0.90rem !important; 
        font-weight: 700 !important; 
        color: #FFFFFF !important; 
    }
    </style>
''', unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. DATA INGESTION
# ---------------------------------------------------------
SUMMARY_CSV = "D:/NGCP/Operational_Gap_5min_Daily_Summary.csv"

@st.cache_data
def load_data(path):
    return pl.read_csv(path).to_pandas() if os.path.exists(path) else None

df = load_data(SUMMARY_CSV)

if df is None or df.empty:
    st.error(f"File missing or empty: `{SUMMARY_CSV}`. Please run `process_operational_gap.py` first.")
    st.stop()

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

# ---------------------------------------------------------
# 3. CONTROL SLICERS
# ---------------------------------------------------------
top_hdr_left, top_hdr_right = st.columns([0.85, 3.15], gap="small")

with top_hdr_left:
    st.markdown('<div class="title-main">OPERATIONAL GAP REPORT</div>', unsafe_allow_html=True)
    st.markdown('<div class="title-sub">RTD VS RTDRS VS ACTUAL GENERATION</div>', unsafe_allow_html=True)

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

    # Date filtering
    global_min_date = df["Date"].min().date()
    global_max_date = df["Date"].max().date()
    
    selected_dates = st.date_input("Calendar Range Slicer", value=[global_min_date, global_max_date], min_value=global_min_date, max_value=global_max_date)
    
    if isinstance(selected_dates, (list, tuple)) and len(selected_dates) == 2:
        filtered_df = filtered_df[(filtered_df["Date"] >= pd.to_datetime(selected_dates[0])) & (filtered_df["Date"] <= pd.to_datetime(selected_dates[1]))]

# ---------------------------------------------------------
# 4. TOP EXECUTIVE KPI CARDS (Average System Generation MW)
# ---------------------------------------------------------
# Calculate system totals per date first, then take average MW across selected period
daily_totals = filtered_df.groupby("Date")[["RTD_MW_AVG", "RTDRS_MW_AVG", "ACTUAL_MW_AVG", "UDD_COMPLIANCE_GAP_MW"]].sum()

rtd_system_avg = daily_totals["RTD_MW_AVG"].mean() if not daily_totals.empty else 0.0
rtdrs_system_avg = daily_totals["RTDRS_MW_AVG"].mean() if not daily_totals.empty else 0.0
actual_system_avg = daily_totals["ACTUAL_MW_AVG"].mean() if not daily_totals.empty else 0.0
udd_system_avg = daily_totals["UDD_COMPLIANCE_GAP_MW"].mean() if not daily_totals.empty else 0.0

with top_hdr_right:
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">MARKET DISPATCH (RTD)</div><div class="square-kpi-val">{rtd_system_avg:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">RE-DISPATCH (RTDRS)</div><div class="square-kpi-val">{rtdrs_system_avg:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">ACTUAL PHYSICAL OUTPUT</div><div class="square-kpi-val">{actual_system_avg:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">UNINSTRUCTED DEVIATION (UDD)</div><div class="square-kpi-val" style="color:{"#10B981" if udd_system_avg >= 0 else "#E53935"};">{udd_system_avg:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 5. MIDDLE ROW: TREND CHART
# ---------------------------------------------------------
with mid_right_chart:
    if not filtered_df.empty:
        min_sel_date = filtered_df["Date"].min()
        max_sel_date = filtered_df["Date"].max()
        date_label = f"({min_sel_date.strftime('%b %d, %Y').upper()} - {max_sel_date.strftime('%b %d, %Y').upper()})"

        st.markdown(f'<div class="section-hdr-large">DAILY DISPATCH SCHEDULE VS PHYSICAL OUTPUT TREND {date_label}</div>', unsafe_allow_html=True)

        daily = filtered_df.groupby("Date")[["RTD_MW_AVG", "RTDRS_MW_AVG", "ACTUAL_MW_AVG", "UDD_COMPLIANCE_GAP_MW"]].sum().reset_index().sort_values("Date")
        daily["Day_Label"] = daily["Date"].dt.strftime('%b %d, %Y')

        fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
        fig_combo.add_trace(go.Bar(x=daily["Day_Label"], y=daily["RTD_MW_AVG"], name="Market Dispatch (RTD)", marker_color="#00A3FF"), secondary_y=False)
        fig_combo.add_trace(go.Bar(x=daily["Day_Label"], y=daily["RTDRS_MW_AVG"], name="Re-Dispatch (RTDRS)", marker_color="#8B5CF6"), secondary_y=False)
        fig_combo.add_trace(go.Scatter(x=daily["Day_Label"], y=daily["ACTUAL_MW_AVG"], name="Actual Output", line=dict(color="#10B981", width=3)), secondary_y=False)
        fig_combo.add_trace(go.Scatter(x=daily["Day_Label"], y=daily["UDD_COMPLIANCE_GAP_MW"], name="UDD Gap (MW)", line=dict(color="#F97316", width=2, dash="dot")), secondary_y=True)

        fig_combo.update_layout(
            template="plotly_dark", 
            paper_bgcolor="#161A22", 
            plot_bgcolor="#161A22", 
            height=380, 
            margin=dict(l=10, r=10, t=15, b=10), 
            barmode="group"
        )
        st.plotly_chart(fig_combo, use_container_width=True)

# ---------------------------------------------------------
# 6. BOTTOM ROW: DISTRICT GAP MATRIX & COMPLIANCE SHARE
# ---------------------------------------------------------
bot_left, bot_right = st.columns([3, 2], gap="small")

with bot_left:
    st.markdown('<div class="section-hdr-large">DISTRICT DISPATCH & COMPLIANCE BREAKDOWN (AVERAGE MW)</div>', unsafe_allow_html=True)
    dist_matrix = filtered_df.groupby(["REGION", "SUB_GRID_PREFIX", "PROVINCE_DISTRICT"])[["RTD_MW_AVG", "RTDRS_MW_AVG", "ACTUAL_MW_AVG", "UDD_COMPLIANCE_GAP_MW"]].mean().reset_index().rename(
        columns={"REGION": "Region", "SUB_GRID_PREFIX": "Dist #", "PROVINCE_DISTRICT": "District & Covered Provinces", "RTD_MW_AVG": "RTD Schedule", "RTDRS_MW_AVG": "RTDRS Schedule", "ACTUAL_MW_AVG": "Actual Output", "UDD_COMPLIANCE_GAP_MW": "UDD Gap (MW)"}
    ).sort_values(["Region", "Dist #"])

    dist_matrix["RTD Schedule"] = dist_matrix["RTD Schedule"].map(lambda x: f"{x:,.1f} MW")
    dist_matrix["RTDRS Schedule"] = dist_matrix["RTDRS Schedule"].map(lambda x: f"{x:,.1f} MW")
    dist_matrix["Actual Output"] = dist_matrix["Actual Output"].map(lambda x: f"{x:,.1f} MW")
    dist_matrix["UDD Gap (MW)"] = dist_matrix["UDD Gap (MW)"].map(lambda x: f"{x:,.1f} MW")

    st.dataframe(dist_matrix, use_container_width=True, hide_index=True)

with bot_right:
    st.markdown('<div class="section-hdr-large">RE-DISPATCH OVERRIDE BY DISTRICT (%)</div>', unsafe_allow_html=True)
    if not filtered_df.empty:
        pie_df = filtered_df.groupby("SUB_GRID_PREFIX")["REDISPATCH_IMPACT_MW"].apply(lambda x: x.abs().sum()).reset_index().sort_values("SUB_GRID_PREFIX")
        fig_pie = go.Figure(go.Pie(
            labels=pie_df["SUB_GRID_PREFIX"].apply(lambda x: f"District {x}"), values=pie_df["REDISPATCH_IMPACT_MW"], hole=0.45, sort=False,
            textinfo="percent", textposition="inside", textfont=dict(size=14, color="#FFFFFF", family="Arial Black")
        ))
        fig_pie.update_layout(template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22", height=320, margin=dict(l=10, r=10, t=10, b=35), legend=dict(font=dict(size=11, color="#FFFFFF")))
        st.plotly_chart(fig_pie, use_container_width=True)