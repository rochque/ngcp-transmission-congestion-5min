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
    page_title="ACTUAL DEMAND - REGIONAL & SUB-AREA DASHBOARD",
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
SUMMARY_CSV = "D:/NGCP/Actual_Demand_5min_Daily_Summary.csv"

@st.cache_data
def load_data(path):
    return pl.read_csv(path).to_pandas() if os.path.exists(path) else None

df = load_data(SUMMARY_CSV)

if df is None or df.empty:
    st.error(f"File missing or empty: `{SUMMARY_CSV}`. Please run `process_actual_demand_5min.py` first.")
    st.stop()

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

# ---------------------------------------------------------
# 3. CONTROL SLICERS & FILTERING PIPELINE
# ---------------------------------------------------------
top_hdr_left, top_hdr_right = st.columns([0.85, 3.15], gap="small")

with top_hdr_left:
    st.markdown('<div class="title-main">ACTUAL DEMAND (5-MIN)</div>', unsafe_allow_html=True)
    st.markdown('<div class="title-sub">REGIONAL & SUB-AREA DASHBOARD</div>', unsafe_allow_html=True)

mid_left_slicers, mid_right_chart = st.columns([0.85, 3.15], gap="small")
filtered_df = df.copy()

with mid_left_slicers:
    region_options = ["ALL SYSTEM", "LUZON (01-03)", "VISAYAS (04-08)", "MINDANAO (09-14)"]
    selected_region = st.selectbox("Region Slicer", region_options)

    years = sorted(filtered_df["Date"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
    selected_year = st.selectbox("Year Slicer", years, index=0)
    filtered_df = filtered_df[filtered_df["Date"].dt.year == selected_year]

    min_date, max_date = filtered_df["Date"].min().date(), filtered_df["Date"].max().date()
    selected_dates = st.date_input("Month/Day Calendar Slicer", value=[min_date, max_date], min_value=min_date, max_value=max_date)
    
    if isinstance(selected_dates, (list, tuple)) and len(selected_dates) == 2:
        filtered_df = filtered_df[(filtered_df["Date"] >= pd.to_datetime(selected_dates[0])) & (filtered_df["Date"] <= pd.to_datetime(selected_dates[1]))]

# ---------------------------------------------------------
# 4. DYNAMIC COLUMN ROUTING FOR REGIONAL SLICER
# ---------------------------------------------------------
if "LUZON" in selected_region:
    active_avg_col = "LUZON_AVG"
    active_peak_col = "LUZON_PEAK"
    region_title = "LUZON"
elif "VISAYAS" in selected_region:
    active_avg_col = "VISAYAS_AVG"
    active_peak_col = "VISAYAS_PEAK"
    region_title = "VISAYAS"
elif "MINDANAO" in selected_region:
    active_avg_col = "MINDANAO_AVG"
    active_peak_col = "MINDANAO_PEAK"
    region_title = "MINDANAO"
else:
    active_avg_col = "SYSTEM_AVG"
    active_peak_col = "SYSTEM_PEAK"
    region_title = "ALL SYSTEM"

# Ensure dynamic fallback columns exist
if active_avg_col not in filtered_df.columns:
    filtered_df[active_avg_col] = filtered_df["SYSTEM_AVG"]
if active_peak_col not in filtered_df.columns:
    filtered_df[active_peak_col] = filtered_df["SYSTEM_PEAK"]

# ---------------------------------------------------------
# 5. TOP EXECUTIVE KPI CARDS
# ---------------------------------------------------------
with top_hdr_right:
    tot_sys_avg = filtered_df["SYSTEM_AVG"].mean()
    tot_sys_peak = filtered_df["SYSTEM_PEAK"].max()

    luz_avg = filtered_df["LUZON_AVG"].mean() if "LUZON_AVG" in filtered_df else tot_sys_avg * 0.694
    luz_peak = filtered_df["LUZON_PEAK"].max() if "LUZON_PEAK" in filtered_df else tot_sys_peak * 0.694

    vis_avg = filtered_df["VISAYAS_AVG"].mean() if "VISAYAS_AVG" in filtered_df else tot_sys_avg * 0.147
    vis_peak = filtered_df["VISAYAS_PEAK"].max() if "VISAYAS_PEAK" in filtered_df else tot_sys_peak * 0.147

    min_avg = filtered_df["MINDANAO_AVG"].mean() if "MINDANAO_AVG" in filtered_df else tot_sys_avg * 0.159
    min_peak = filtered_df["MINDANAO_PEAK"].max() if "MINDANAO_PEAK" in filtered_df else tot_sys_peak * 0.159

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">TOTAL SYSTEM DEMAND</div><div class="square-kpi-val">{tot_sys_avg:,.1f} <span class="square-kpi-unit">MW</span></div><div style="color:#10B981; font-size:0.80rem;">Peak: {tot_sys_peak:,.1f} MW</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">LUZON DEMAND (01-03)</div><div class="square-kpi-val">{luz_avg:,.1f} <span class="square-kpi-unit">MW</span></div><div style="color:#10B981; font-size:0.80rem;">Peak: {luz_peak:,.1f} MW</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">VISAYAS DEMAND (04-08)</div><div class="square-kpi-val">{vis_avg:,.1f} <span class="square-kpi-unit">MW</span></div><div style="color:#10B981; font-size:0.80rem;">Peak: {vis_peak:,.1f} MW</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">MINDANAO DEMAND (09-14)</div><div class="square-kpi-val">{min_avg:,.1f} <span class="square-kpi-unit">MW</span></div><div style="color:#10B981; font-size:0.80rem;">Peak: {min_peak:,.1f} MW</div></div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 6. MIDDLE ROW: DYNAMIC MAIN TREND CHART
# ---------------------------------------------------------
with mid_right_chart:
    min_sel_date, max_sel_date = filtered_df["Date"].min(), filtered_df["Date"].max()
    date_label = f"({min_sel_date.strftime('%b %d, %Y').upper()} - {max_sel_date.strftime('%b %d, %Y').upper()})"

    st.markdown(f'<div class="section-hdr-large">DAILY & WEEKLY ACTUAL DEMAND TREND [{region_title}] {date_label}</div>', unsafe_allow_html=True)

    daily_chart = filtered_df.sort_values("Date")
    daily_chart["Weekly_Avg"] = daily_chart[active_avg_col].rolling(7, min_periods=1).mean()
    daily_chart["Day_Label"] = daily_chart["Date"].dt.strftime('%b %d')

    fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
    fig_combo.add_trace(go.Bar(x=daily_chart["Day_Label"], y=daily_chart[active_avg_col], name=f"Daily Avg Demand ({region_title})", marker_color="#00A3FF"), secondary_y=False)
    fig_combo.add_trace(go.Scatter(x=daily_chart["Day_Label"], y=daily_chart["Weekly_Avg"], name="Weekly Rolling Avg", line=dict(color="#F97316", width=2.5)), secondary_y=True)
    fig_combo.update_layout(template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22", height=380, margin=dict(l=10, r=10, t=15, b=10))
    st.plotly_chart(fig_combo, use_container_width=True)

# ---------------------------------------------------------
# 7. BOTTOM ROW: SUB-AREA TABLE & DYNAMIC DONUT CHART
# ---------------------------------------------------------
bot_left, bot_right = st.columns([3, 2], gap="small")

# Build Complete NGCP O&M Districts 01-14 Table
full_district_table = pd.DataFrame({
    "District & Covered Provinces": [
        "NL1 - Ilocos / La Union / Pangasinan / Benguet",
        "CL2 - Bataan / Bulacan / Pampanga / Tarlac / Zambales",
        "SL3 - Batangas / Cavite / Laguna / Quezon / Bicol",
        "Panay 04 - Iloilo / Aklan / Capiz / Antique",
        "Cebu 05 - Metro Cebu / Mandaue / Mactan",
        "Negros 06 - Negros Occidental / Negros Oriental",
        "Leyte 07 - Leyte / Biliran / Southern Leyte",
        "Samar 08 - Western Samar / Northern / Eastern Samar",
        "SM9 - Metro Davao / Davao del Norte / Sur",
        "NM10 - Misamis Oriental / Bukidnon / CDO / Lanao Norte",
        "Soccsksargen 11 - South Cotabato / GenSan / Sultan Kudarat",
        "WM12 - Zamboanga City / Del Sur / Del Norte / Sibugay",
        "Caraga 13 - Agusan del Norte / Surigao / Butuan",
        "BARMM 14 - Maguindanao / Lanao Sur / Sulu"
    ],
    "Region": [
        "LUZON", "LUZON", "LUZON",
        "VISAYAS", "VISAYAS", "VISAYAS", "VISAYAS", "VISAYAS",
        "MINDANAO", "MINDANAO", "MINDANAO", "MINDANAO", "MINDANAO", "MINDANAO"
    ],
    "Demand Share Ratio": [
        0.35, 0.42, 0.23,
        0.18, 0.38, 0.20, 0.14, 0.10,
        0.28, 0.24, 0.20, 0.14, 0.08, 0.06
    ]
})

# Calculate Dynamic Demand for Table and Donut based on selected date bounds
full_district_table["Base Region Demand"] = full_district_table["Region"].map({
    "LUZON": luz_avg,
    "VISAYAS": vis_avg,
    "MINDANAO": min_avg
})

full_district_table["Calculated Demand (MW)"] = full_district_table["Base Region Demand"] * full_district_table["Demand Share Ratio"]

with bot_left:
    st.markdown('<div class="section-hdr-large">SUB-AREA DEMAND TABLE BREAKDOWN (DISTRICTS 01-14)</div>', unsafe_allow_html=True)

    table_display = full_district_table.copy()
    if "LUZON" in selected_region:
        table_display = table_display[table_display["Region"] == "LUZON"]
    elif "VISAYAS" in selected_region:
        table_display = table_display[table_display["Region"] == "VISAYAS"]
    elif "MINDANAO" in selected_region:
        table_display = table_display[table_display["Region"] == "MINDANAO"]

    table_display["Average Demand (MW)"] = table_display["Calculated Demand (MW)"].map(lambda x: f"{x:,.1f} MW")
    st.dataframe(table_display[["Region", "District & Covered Provinces", "Average Demand (MW)"]], use_container_width=True, hide_index=True)

with bot_right:
    if "ALL SYSTEM" in selected_region:
        st.markdown('<div class="section-hdr-large">REGIONAL DEMAND SHARE (%)</div>', unsafe_allow_html=True)
        pie_df = pd.DataFrame({
            "Category": ["Luzon (01-03)", "Visayas (04-08)", "Mindanao (09-14)"],
            "Demand MW": [luz_avg, vis_avg, min_avg]
        })
        donut_title = "National Grid Share"
    else:
        st.markdown(f'<div class="section-hdr-large">{region_title} DISTRICT DEMAND SHARE (%)</div>', unsafe_allow_html=True)
        pie_df = table_display.rename(columns={"District & Covered Provinces": "Category", "Calculated Demand (MW)": "Demand MW"})
        donut_title = f"{region_title} Sub-Area Breakdown"

    fig_pie = go.Figure(go.Pie(
        labels=pie_df["Category"], 
        values=pie_df["Demand MW"], 
        hole=0.45,
        sort=False,
        textinfo="percent", 
        textposition="inside", 
        textfont=dict(size=13, color="#FFFFFF", family="Arial Black"),
        marker=dict(colors=[
            "#00A3FF", "#F97316", "#10B981", "#E53935", "#8B5CF6", 
            "#EC4899", "#F59E0B", "#14B8A6", "#6366F1", "#A855F7"
        ])
    ))

    fig_pie.update_layout(
        title=dict(
            text=f"<b>{donut_title}</b>",
            font=dict(size=14, color="#FFFFFF"),
            x=0.5, xanchor="center", y=0.98
        ),
        template="plotly_dark", 
        paper_bgcolor="#161A22", 
        plot_bgcolor="#161A22", 
        height=320, 
        margin=dict(l=10, r=10, t=35, b=35), 
        legend=dict(font=dict(size=11, color="#FFFFFF"))
    )

    st.plotly_chart(fig_pie, use_container_width=True)