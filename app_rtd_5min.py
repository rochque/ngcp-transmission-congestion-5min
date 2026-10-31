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
    page_title="REAL-TIME DISPATCH (RTD) MONTHLY PERFORMANCE DASHBOARD",
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
        height: 100px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        box-sizing: border-box !important;
    }

    .square-kpi-label {
        color: #A0AAB8 !important;
        font-size: 0.82rem !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.6px !important;
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
        font-size: 1.55rem !important;
        font-weight: 900 !important;
        color: #FFFFFF !important;
        line-height: 1.15 !important;
        letter-spacing: 0.5px !important;
        margin-bottom: 2px !important;
    }
    
    .title-sub {
        font-size: 0.92rem !important;
        font-weight: 800 !important;
        color: #00A3FF !important;
        letter-spacing: 0.6px !important;
        margin-bottom: 0px !important;
    }

    .section-hdr-large {
        font-size: 1.05rem !important;
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
    </style>
''', unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. DATA INGESTION
# ---------------------------------------------------------

#FROM
#SUMMARY_CSV = r"D:\NGCP\RTD_5min_Daily_Summary.csv"

#CHANGE TO:
SUMMARY_CSV = "RTD_5min_Daily_Summary.csv"


@st.cache_data
def load_summary_data(csv_path):
    if not os.path.exists(csv_path):
        return None
        
    df_pl = pl.read_csv(csv_path)
    df_pd = df_pl.to_pandas()

    region_map = {
        "CLUZ": "CLUZ (Luzon)",
        "CMIN": "CMIN (Mindanao)",
        "CVIS": "CVIS (Visayas)"
    }
    df_pd["REGION_NAME_FULL"] = df_pd["REGION_NAME"].map(lambda x: region_map.get(str(x), str(x)))
    return df_pd

df = load_summary_data(SUMMARY_CSV)

if df is None:
    st.error(f"Summary file not found: `{SUMMARY_CSV}`. Please run `process_rtd_5min.py` first.")
    st.stop()

df["Date"] = pd.to_datetime(df["Date"])

# ---------------------------------------------------------
# 3. CONTROL SLICERS & STRICT FILTERING PIPELINE
# ---------------------------------------------------------
top_hdr_left, top_hdr_right = st.columns([0.85, 3.15], gap="small")

with top_hdr_left:
    st.markdown('<div class="title-main">REAL-TIME DISPATCH (RTD)</div>', unsafe_allow_html=True)
    st.markdown('<div class="title-sub">MONTHLY PERFORMANCE DASHBOARD</div>', unsafe_allow_html=True)

mid_left_slicers, mid_right_chart = st.columns([0.85, 3.15], gap="small")

filtered_df = df.copy()

with mid_left_slicers:
    # 1. Region Name Slicer
    regions = sorted(filtered_df["REGION_NAME_FULL"].dropna().unique().tolist())
    selected_region = st.selectbox("Region Name Slicer", ["All"] + regions)

    if selected_region != "All":
        filtered_df = filtered_df[filtered_df["REGION_NAME_FULL"] == selected_region]

    # 2. Resource Prefix Filter
    all_resources = filtered_df["RESOURCE_NAME"].dropna().unique().tolist()
    available_prefixes = sorted(list(set([str(res)[:2] for res in all_resources if str(res)[:2].isdigit()])))
    selected_prefix = st.selectbox("Resource Prefix (01-14)", ["All"] + available_prefixes)

    if selected_prefix != "All":
        filtered_df = filtered_df[filtered_df["RESOURCE_NAME"].astype(str).str.startswith(selected_prefix)]

    # 3. Resource Name Search
    available_resources = sorted(filtered_df["RESOURCE_NAME"].dropna().unique().tolist())
    selected_resources = st.multiselect("Resource Name Search", available_resources)

    if selected_resources:
        filtered_df = filtered_df[filtered_df["RESOURCE_NAME"].isin(selected_resources)]

    # 4. Year Slicer
    available_years = sorted(filtered_df["Date"].dt.year.unique().tolist(), reverse=True)
    selected_year = st.selectbox("Year Slicer", available_years, index=0)

    filtered_df = filtered_df[filtered_df["Date"].dt.year == selected_year]

    # 5. Calendar Slicer - DEFAULT TO LATEST MONTH OF SELECTED YEAR
    max_date_in_year = filtered_df["Date"].max()
    default_start_month = max_date_in_year.replace(day=1)

    selected_dates = st.date_input(
        "Month/Day Calendar Slicer", 
        value=[default_start_month.date(), max_date_in_year.date()]
    )

    # STRICT DATE RANGE FILTERING (Ensures 1-week selections like Dec 01-07 work)
    if isinstance(selected_dates, (list, tuple)):
        if len(selected_dates) == 2:
            s_date, e_date = selected_dates
            filtered_df = filtered_df[(filtered_df["Date"] >= pd.to_datetime(s_date)) & (filtered_df["Date"] <= pd.to_datetime(e_date))]
        elif len(selected_dates) == 1:
            s_date = selected_dates[0]
            filtered_df = filtered_df[filtered_df["Date"] == pd.to_datetime(s_date)]

    if filtered_df.empty:
        st.warning("⚠️ No data available for selected filters.")
        st.stop()

# ---------------------------------------------------------
# 4. TOP KPI CARDS (STRICTLY FILTERED)
# ---------------------------------------------------------
with top_hdr_right:
    avg_sched_mw = filtered_df["SCHED_MW"].mean()
    avg_lmp = filtered_df["LMP"].mean()
    avg_congestion = filtered_df["LMP_CONGESTION"].mean()
    avg_loss_factor = filtered_df["LOSS_FACTOR"].mean()

    c1, c2, c3, c4 = st.columns(4, gap="small")

    with c1:
        st.markdown(f'''
            <div class="square-kpi-card">
                <div class="square-kpi-label">TOTAL AVG. SCHED_MW</div>
                <div class="square-kpi-val">{avg_sched_mw:,.1f} <span class="square-kpi-unit">MW</span></div>
            </div>
        ''', unsafe_allow_html=True)

    with c2:
        st.markdown(f'''
            <div class="square-kpi-card">
                <div class="square-kpi-label">AVG. SYSTEM LMP</div>
                <div class="square-kpi-val">₱{avg_lmp:,.2f} <span class="square-kpi-unit">/ MWh</span></div>
            </div>
        ''', unsafe_allow_html=True)

    with c3:
        st.markdown(f'''
            <div class="square-kpi-card">
                <div class="square-kpi-label">AVG. CONGESTION COST</div>
                <div class="square-kpi-val">₱{avg_congestion:,.2f}</div>
            </div>
        ''', unsafe_allow_html=True)

    with c4:
        st.markdown(f'''
            <div class="square-kpi-card">
                <div class="square-kpi-label">AVG. LOSS FACTOR</div>
                <div class="square-kpi-val">{avg_loss_factor:,.3f}</div>
            </div>
        ''', unsafe_allow_html=True)

# ---------------------------------------------------------
# 5. MIDDLE ROW: COMBO BAR CHART
# ---------------------------------------------------------
with mid_right_chart:
    st.markdown('<div class="section-hdr-large">DAILY & WEEKLY AVG. SCHED_MW TREND</div>', unsafe_allow_html=True)

    daily_mw = filtered_df.groupby("Date")["SCHED_MW"].mean().reset_index().sort_values("Date")
    daily_mw["Weekly_Avg_MW"] = daily_mw["SCHED_MW"].rolling(7, min_periods=1).mean()
    daily_mw["Day_Label"] = daily_mw["Date"].dt.strftime('%b %d')

    fig_combo = make_subplots(specs=[[{"secondary_y": True}]])

    # Trace 1: Weekly aveg_MW Bars (Light Blue)
    fig_combo.add_trace(
        go.Bar(
            x=daily_mw["Day_Label"], 
            y=daily_mw["Weekly_Avg_MW"], 
            name="Weekly aveg_MW", 
            marker_color="#38BDF8"
        ),
        secondary_y=False
    )

    # Trace 2: Daily aveg_MW Bars (Orange)
    fig_combo.add_trace(
        go.Bar(
            x=daily_mw["Day_Label"], 
            y=daily_mw["SCHED_MW"], 
            name="Daily aveg_MW", 
            marker_color="#F97316"
        ),
        secondary_y=True
    )

    # Trace 3: Smooth Trend Line
    fig_combo.add_trace(
        go.Scatter(
            x=daily_mw["Day_Label"], 
            y=daily_mw["Weekly_Avg_MW"], 
            name="Weekly Trend", 
            line=dict(color="#7DD3FC", width=2.0),
            showlegend=False
        ),
        secondary_y=False
    )

    fig_combo.update_layout(
        template="plotly_dark",
        paper_bgcolor="#161A22",
        plot_bgcolor="#161A22",
        height=380,
        margin=dict(l=10, r=10, t=15, b=10),
        barmode="group",
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="center", x=0.5),
        xaxis=dict(
            title="Date",
            gridcolor="#282F3D"
        )
    )

    fig_combo.update_yaxes(title_text="Average MW", secondary_y=False, gridcolor="#282F3D")
    fig_combo.update_yaxes(title_text="Average MW", secondary_y=True, showgrid=False)

    st.plotly_chart(fig_combo, use_container_width=True)

# ---------------------------------------------------------
# 6. BOTTOM ROW: DECOMPOSITION (LEFT) & TOP 5 RESOURCES (RIGHT)
# ---------------------------------------------------------
bot_left, bot_right = st.columns([3, 2], gap="small")

with bot_left:
    st.markdown('<div class="section-hdr-large">LMP PRICE COMPONENTS DECOMPOSITION</div>', unsafe_allow_html=True)

    lmp_df = filtered_df.groupby("Date")[["LMP_SMP", "LMP_LOSS", "LMP_CONGESTION"]].mean().reset_index().sort_values("Date")
    lmp_df["Day_Label"] = lmp_df["Date"].dt.strftime('%b %d')

    fig_stacked = go.Figure()
    fig_stacked.add_trace(go.Bar(x=lmp_df["Day_Label"], y=lmp_df["LMP_SMP"], name="LMP_SMP", marker_color="#38BDF8"))
    fig_stacked.add_trace(go.Bar(x=lmp_df["Day_Label"], y=lmp_df["LMP_LOSS"], name="LMP_LOSS", marker_color="#F97316"))
    fig_stacked.add_trace(go.Bar(x=lmp_df["Day_Label"], y=lmp_df["LMP_CONGESTION"], name="LMP_CONGESTION", marker_color="#E53935"))

    fig_stacked.update_layout(
        barmode="stack",
        template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22",
        height=220, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        xaxis=dict(title="Date", gridcolor="#282F3D")
    )
    st.plotly_chart(fig_stacked, use_container_width=True)

with bot_right:
    h_a, h_b = st.columns([2.2, 1.0])
    with h_a:
        st.markdown('<div class="section-hdr-large">TOP 5 GENERATING RESOURCES BY REGION</div>', unsafe_allow_html=True)
    with h_b:
        reg_tag = selected_region if selected_region != "All" else "All Regions"
        st.markdown(f"<div style='text-align: right; color: #00A3FF; font-weight: 800; font-size: 0.82rem; padding-top: 12px;'>Region: {reg_tag}</div>", unsafe_allow_html=True)

    top5_df = (
        filtered_df.groupby("RESOURCE_NAME")["SCHED_MW"]
        .mean()
        .nlargest(5)
        .reset_index()
        .sort_values("SCHED_MW", ascending=True)
    )

    fig_bar = go.Figure(go.Bar(
        x=top5_df["SCHED_MW"],
        y=top5_df["RESOURCE_NAME"],
        orientation="h",
        text=top5_df["SCHED_MW"].apply(lambda x: f"{x:.1f}"),
        textposition="inside",
        marker_color="#38BDF8"
    ))

    fig_bar.update_layout(
        template="plotly_dark",
        paper_bgcolor="#161A22", plot_bgcolor="#161A22",
        height=220, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Average MW", yaxis_title=""
    )
    st.plotly_chart(fig_bar, use_container_width=True)