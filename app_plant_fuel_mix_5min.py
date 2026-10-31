import os
import polars as pl
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & DARK CANVAS STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="PLANT-LEVEL PERFORMANCE & FUEL MIX BENCHMARK",
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
SUMMARY_CSV = "D:/NGCP/Plant_Fuel_Mix_5min_Daily_Summary.csv"

@st.cache_data
def load_data(path):
    return pl.read_csv(path).to_pandas() if os.path.exists(path) else None

df = load_data(SUMMARY_CSV)

if df is None or df.empty:
    st.error(f"File missing or empty: `{SUMMARY_CSV}`. Please run `process_plant_fuel_mix_5min.py` first.")
    st.stop()

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

# ---------------------------------------------------------
# 3. CONTROL SLICERS & NUMERICALLY SORTED DISTRICTS PIPELINE
# ---------------------------------------------------------
top_hdr_left, top_hdr_right = st.columns([0.85, 3.15], gap="small")

with top_hdr_left:
    st.markdown('<div class="title-main">PLANT & FUEL MIX BENCHMARK</div>', unsafe_allow_html=True)
    st.markdown('<div class="title-sub">RESOURCE PERFORMANCE & RENEWABLES</div>', unsafe_allow_html=True)

mid_left_slicers, mid_right_chart = st.columns([0.85, 3.15], gap="small")
filtered_df = df.copy()

with mid_left_slicers:
    if "REGION" in filtered_df.columns:
        selected_region = st.selectbox("Region Slicer", ["All Regions"] + sorted(filtered_df["REGION"].dropna().unique().tolist()))
        if selected_region != "All Regions":
            filtered_df = filtered_df[filtered_df["REGION"] == selected_region]

    if "FUEL_TYPE" in filtered_df.columns:
        selected_fuels = st.multiselect("Fuel / Resource Type", sorted(filtered_df["FUEL_TYPE"].dropna().unique().tolist()))
        if selected_fuels:
            filtered_df = filtered_df[filtered_df["FUEL_TYPE"].isin(selected_fuels)]

    # NUMERICALLY SORT DISTRICTS BY PREFIX CODE (01 to 14)
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
# 4. TOP EXECUTIVE KPI CARDS (CORRECTED)
# ---------------------------------------------------------
with top_hdr_right:
    tot_actual_mw = filtered_df["ACTUAL_MW_AVG"].sum()
    tot_rtd_mw = filtered_df["RTD_MW_AVG"].sum() if "RTD_MW_AVG" in filtered_df else tot_actual_mw
    
    vre_mask = filtered_df["FUEL_TYPE"].isin(["Solar", "Wind", "Hydro", "Geothermal"]) if "FUEL_TYPE" in filtered_df else pd.Series(False, index=filtered_df.index)
    vre_mw = filtered_df[vre_mask]["ACTUAL_MW_AVG"].sum() if not filtered_df.empty else 0.0
    
    # FIX: Use total actual generation (or total system demand sum) as the denominator 
    # so both numerator and denominator represent the same total scale over the selected period.
    total_grid_denominator = tot_actual_mw if tot_actual_mw > 0 else 1.0
    re_penetration_pct = (vre_mw / total_grid_denominator) * 100

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">TOTAL ACTUAL GENERATION</div><div class="square-kpi-val">{tot_actual_mw:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">MARKET SCHEDULED (RTD)</div><div class="square-kpi-val">{tot_rtd_mw:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">RENEWABLE OUTPUT (VRE)</div><div class="square-kpi-val" style="color:#10B981;">{vre_mw:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">GRID RE PENETRATION</div><div class="square-kpi-val" style="color:#10B981;">{re_penetration_pct:.1f}%</div></div>', unsafe_allow_html=True)



# ---------------------------------------------------------
# 5. MIDDLE ROW: DAILY GENERATION TREND BY FUEL MIX
# ---------------------------------------------------------
with mid_right_chart:
    min_sel_date = filtered_df["Date"].min()
    max_sel_date = filtered_df["Date"].max()
    date_label = f"({min_sel_date.strftime('%b %d, %Y').upper()} - {max_sel_date.strftime('%b %d, %Y').upper()})"

    st.markdown(f'<div class="section-hdr-large">DAILY GENERATION TREND BY FUEL TYPE {date_label}</div>', unsafe_allow_html=True)

    fuel_trend = filtered_df.groupby(["Date", "FUEL_TYPE"])["ACTUAL_MW_AVG"].sum().reset_index()
    pivoted_fuel = fuel_trend.pivot(index="Date", columns="FUEL_TYPE", values="ACTUAL_MW_AVG").fillna(0.0)
    pivoted_fuel["Day_Label"] = pivoted_fuel.index.strftime('%b %d')

    fig_stack = go.Figure()
    colors = {"Coal": "#1F2937", "Natural Gas": "#00A3FF", "Geothermal": "#F97316", "Hydro": "#3B82F6", "Solar": "#F59E0B", "Wind": "#10B981", "Diesel / Oil": "#E53935", "Thermal / Others": "#8B5CF6"}

    for col in pivoted_fuel.columns:
        if col != "Day_Label":
            fig_stack.add_trace(go.Bar(
                x=pivoted_fuel["Day_Label"], 
                y=pivoted_fuel[col], 
                name=col, 
                marker_color=colors.get(col, "#A0AAB8")
            ))

    fig_stack.update_layout(
        template="plotly_dark", 
        paper_bgcolor="#161A22", 
        plot_bgcolor="#161A22", 
        height=380, 
        barmode="stack",
        margin=dict(l=10, r=10, t=15, b=10),
        legend=dict(font=dict(size=11, color="#FFFFFF"))
    )
    st.plotly_chart(fig_stack, use_container_width=True)

# ---------------------------------------------------------
# 6. BOTTOM ROW: ALL GENERATING PLANTS & FUEL MIX DONUT
# ---------------------------------------------------------
bot_left, bot_right = st.columns([3, 2], gap="small")

with bot_left:
    st.markdown('<div class="section-hdr-large">PLANT PERFORMANCE & UTILIZATION RANKING (ALL UNITS)</div>', unsafe_allow_html=True)
    
    # UNTRUNCATED GROUPING SHOWS ALL UNITS (INCLUDING DISTRICT 12)
    plant_rank = filtered_df.groupby(["RESOURCE_NAME", "FUEL_TYPE", "PROVINCE_DISTRICT"])[["ACTUAL_MW_AVG", "ACTUAL_MW_PEAK", "RTD_MW_AVG"]].mean().reset_index().rename(
        columns={
            "RESOURCE_NAME": "Plant Unit", 
            "FUEL_TYPE": "Fuel / Tech", 
            "PROVINCE_DISTRICT": "District & Location", 
            "ACTUAL_MW_AVG": "Avg MW", 
            "ACTUAL_MW_PEAK": "Peak MW", 
            "RTD_MW_AVG": "RTD Sched"
        }
    ).sort_values("Avg MW", ascending=False)

    plant_rank["Utilization (%)"] = ((plant_rank["Avg MW"] / plant_rank["Peak MW"].replace(0, 1)) * 100).map(lambda x: f"{min(x, 100.0):.1f}%")
    plant_rank["Avg MW"] = plant_rank["Avg MW"].map(lambda x: f"{x:,.1f} MW")
    plant_rank["Peak MW"] = plant_rank["Peak MW"].map(lambda x: f"{x:,.1f} MW")
    plant_rank["RTD Sched"] = plant_rank["RTD Sched"].map(lambda x: f"{x:,.1f} MW")

    st.dataframe(plant_rank, use_container_width=True, hide_index=True, height=420)

with bot_right:
    st.markdown('<div class="section-hdr-large">FUEL & RESOURCE MIX SHARE (%)</div>', unsafe_allow_html=True)
    pie_df = filtered_df.groupby("FUEL_TYPE")["ACTUAL_MW_AVG"].sum().reset_index().sort_values("ACTUAL_MW_AVG", ascending=False)
    
    fig_pie = go.Figure(go.Pie(
        labels=pie_df["FUEL_TYPE"], 
        values=pie_df["ACTUAL_MW_AVG"], 
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