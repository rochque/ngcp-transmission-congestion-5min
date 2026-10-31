import os
import polars as pl
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & MATCHING SAMPLE COLOR SCHEME
# ---------------------------------------------------------
st.set_page_config(
    page_title="IEMOP RTDRS Executive Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
        max-width: 100% !important;
    }
    .main { background-color: #0B101D; }
    section[data-testid="stSidebar"] { background-color: #121829; }

    .kpi-card {
        background-color: #1A2235;
        border-radius: 8px;
        padding: 10px 14px;
        height: 85px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .card-blue { border-top: 3px solid #00A3FF; }
    .card-amber { border-top: 3px solid #FF9900; }
    .card-green { border-top: 3px solid #00C853; }
    .card-purple { border-top: 3px solid #9C27B0; }

    .kpi-title {
        color: #8E9AAB;
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        color: #FFFFFF;
        font-size: 1.25rem;
        font-weight: 700;
        line-height: 1.1;
    }
    .kpi-note {
        color: #5C687A;
        font-size: 0.62rem;
    }

    h1 { font-size: 1.5rem !important; font-weight: 800 !important; color: #FFFFFF !important; margin-bottom: 0rem !important; }
    h3 { font-size: 0.90rem !important; font-weight: 700 !important; color: #FFFFFF !important; margin-top: 0.1rem !important; margin-bottom: 0.2rem !important; }
    .stCaption { font-size: 0.80rem !important; color: #00A3FF !important; font-weight: 600 !important; margin-bottom: 0.4rem !important; }
    hr { margin-top: 0.4rem !important; margin-bottom: 0.4rem !important; border-color: #1E293B !important; }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. INSTANT SUMMARY DATA INGESTION & ROBUST MAPPINGS
# ---------------------------------------------------------
SUMMARY_CSV = r"D:\NGCP\RTDRS_5min_Daily_Summary.csv"

@st.cache_data
def load_and_process_summary(csv_path):
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

    commodity_map = {
        "Fr": "Fr (Regulating)",
        "Ru": "Ru (Contingency Up)",
        "Rd": "Rd (Contingency Down)",
        "Dr": "Dr (Dispatchable)"
    }
    if "COMMODITY_TYPE" in df_pd.columns:
        df_pd["COMMODITY_TYPE_FULL"] = df_pd["COMMODITY_TYPE"].map(lambda x: commodity_map.get(str(x), str(x)))
    else:
        df_pd["COMMODITY_TYPE_FULL"] = "Unspecified"

    df_pd["Year"] = df_pd["Year"].astype(str)

    # Column safeguards
    if "PRICE" not in df_pd.columns and "RESERVE_PRICE" in df_pd.columns:
        df_pd["PRICE"] = df_pd["RESERVE_PRICE"]
        
    if "SCHED_MWH" not in df_pd.columns:
        if "SCHEDULED_VOLUME" in df_pd.columns:
            df_pd["SCHED_MWH"] = df_pd["SCHEDULED_VOLUME"]
        else:
            df_pd["SCHED_MWH"] = df_pd["SCHED_MW"] / 12.0

    if "Reserve_Cost" not in df_pd.columns:
        if "EST_RESERVE_PAYMENT" in df_pd.columns:
            df_pd["Reserve_Cost"] = df_pd["EST_RESERVE_PAYMENT"]
        else:
            df_pd["Reserve_Cost"] = df_pd["SCHED_MWH"] * df_pd["PRICE"]

    return df_pd

st.title("REAL-TIME DISPATCH RESERVE SCHEDULES (RTDRS)")
st.caption("IEMOP Spot Market Monthly Performance & Capacity Analytics")

df = load_and_process_summary(SUMMARY_CSV)

if df is None:
    st.error(f"No summary CSV file found at: `{SUMMARY_CSV}`. Please run `python process_rtdrs_5min.py` first.")
    st.stop()

df["Date"] = pd.to_datetime(df["Date"])

# ---------------------------------------------------------
# 3. SIDEBAR CONTROLS
# ---------------------------------------------------------
st.sidebar.header("🕹️ Dynamic Controls")

available_years = sorted(df["Year"].dropna().unique().tolist(), reverse=True)
selected_year = st.sidebar.selectbox("Select Year", ["All"] + available_years)

filtered_df = df if selected_year == "All" else df[df["Year"] == selected_year]

available_billing = sorted(filtered_df["Billing_Date"].dropna().unique().tolist(), reverse=True)
selected_billing = st.sidebar.multiselect("Billing Period (Multi-Select)", available_billing)

if selected_billing:
    filtered_df = filtered_df[filtered_df["Billing_Date"].isin(selected_billing)]

regions = sorted(filtered_df["REGION_NAME_FULL"].dropna().unique().tolist())
selected_region = st.sidebar.selectbox("Region Name", ["All"] + regions)

if selected_region != "All":
    filtered_df = filtered_df[filtered_df["REGION_NAME_FULL"] == selected_region]

commodities = sorted(filtered_df["COMMODITY_TYPE_FULL"].dropna().unique().tolist())
selected_commodity = st.sidebar.multiselect("Commodity Type", commodities)

if selected_commodity:
    filtered_df = filtered_df[filtered_df["COMMODITY_TYPE_FULL"].isin(selected_commodity)]

all_resources = filtered_df["RESOURCE_NAME"].dropna().unique().tolist()
available_prefixes = sorted(list(set([str(res)[:2] for res in all_resources if str(res)[:2].isdigit()])))

selected_prefix = st.sidebar.selectbox("Resource Prefix (e.g., 01, 08)", ["All"] + available_prefixes)

if selected_prefix != "All":
    filtered_df = filtered_df[filtered_df["RESOURCE_NAME"].astype(str).str.startswith(selected_prefix)]

available_resources = sorted(filtered_df["RESOURCE_NAME"].dropna().unique().tolist())
selected_resources = st.sidebar.multiselect("Resource Name", available_resources)

if selected_resources:
    filtered_df = filtered_df[filtered_df["RESOURCE_NAME"].isin(selected_resources)]

if filtered_df.empty:
    st.warning("⚠️ No data available for the selected combination of filters. Please adjust your sidebar selections.")
    st.stop()

# ---------------------------------------------------------
# 4. COLOR-BORDERED KPI CARDS
# ---------------------------------------------------------
avg_sched_mw = filtered_df["SCHED_MW"].mean()
avg_price = filtered_df["PRICE"].mean()
total_cost_m = filtered_df["Reserve_Cost"].sum() / 1e6
total_volume_mwh = filtered_df["SCHED_MWH"].sum()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
        <div class="kpi-card card-blue">
            <div class="kpi-title">TOTAL AVG. SCHED MW</div>
            <div class="kpi-value">{avg_sched_mw:,.1f} <span style="font-size:0.85rem; color:#A0AAB8;">MW</span></div>
            <div class="kpi-note">Interval Average System Capacity</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
        <div class="kpi-card card-amber">
            <div class="kpi-title">AVG. RESERVE PRICE</div>
            <div class="kpi-value">₱{avg_price:,.2f}</div>
            <div class="kpi-note">/MWh Simple Average Clearing Price</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
        <div class="kpi-card card-green">
            <div class="kpi-title">EST. RESERVE PAYMENT</div>
            <div class="kpi-value">₱{total_cost_m:,.2f} <span style="font-size:0.85rem; color:#A0AAB8;">M</span></div>
            <div class="kpi-note">Total Scheduled Value (26th-25th)</div>
        </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
        <div class="kpi-card card-purple">
            <div class="kpi-title">SCHEDULED VOLUME</div>
            <div class="kpi-value">{total_volume_mwh:,.0f} <span style="font-size:0.85rem; color:#A0AAB8;">MWh</span></div>
            <div class="kpi-note">Converted (SCHED_MW / 12)</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------
# 5. CHARTS WITH MATCHED COLORS & FILTER TAGS
# ---------------------------------------------------------
row1_col1, row1_col2 = st.columns([3, 2])

with row1_col1:
    st.subheader("DAILY & WEEKLY AVERAGE SCHED_MW TREND")
    
    daily_df = filtered_df.groupby("Date")["SCHED_MW"].mean().reset_index()
    daily_df.rename(columns={"SCHED_MW": "Daily_Avg_MW"}, inplace=True)
    daily_df.sort_values("Date", inplace=True)
    daily_df["7Day_Trend"] = daily_df["Daily_Avg_MW"].rolling(7).mean()

    fig_combo = go.Figure()
    fig_combo.add_trace(go.Bar(x=daily_df["Date"], y=daily_df["Daily_Avg_MW"], name="Daily Avg MW", marker_color="#00A3FF"))
    fig_combo.add_trace(go.Scatter(x=daily_df["Date"], y=daily_df["7Day_Trend"], name="7-Day Trend", line=dict(color="#FF9900", width=2.5)))
    
    fig_combo.update_layout(
        template="plotly_dark", paper_bgcolor="#121829", plot_bgcolor="#121829",
        height=210, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_combo, use_container_width=True)

with row1_col2:
    st.subheader("RESERVE PRICE BY COMMODITY")
    
    commodity_df = filtered_df.groupby(["Billing_Date", "COMMODITY_TYPE_FULL"])["PRICE"].mean().reset_index()
    
    fig_stacked = px.bar(
        commodity_df, x="Billing_Date", y="PRICE", color="COMMODITY_TYPE_FULL",
        template="plotly_dark", height=210, labels={"PRICE": "Avg Price (₱)"},
        color_discrete_map={
            "Fr (Regulating)": "#00A3FF",
            "Ru (Contingency Up)": "#FF9900",
            "Rd (Contingency Down)": "#00C853",
            "Dr (Dispatchable)": "#9C27B0"
        }
    )
    fig_stacked.update_layout(
        paper_bgcolor="#121829", plot_bgcolor="#121829",
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title="")
    )
    st.plotly_chart(fig_stacked, use_container_width=True)

header_col1, header_col2 = st.columns([3, 2])
with header_col1:
    st.subheader("TOP 5 GENERATING RESOURCES BY AVERAGE MW")
with header_col2:
    region_tag = selected_region if selected_region != "All" else "All Regions"
    st.markdown(f"<div style='text-align: right; color: #00A3FF; font-weight: 700; font-size: 0.85rem; padding-top: 5px;'>Filtered by Region: {region_tag}</div>", unsafe_allow_html=True)

top5_df = (
    filtered_df.groupby("RESOURCE_NAME")["SCHED_MW"]
    .mean()
    .nlargest(5)
    .reset_index()
    .sort_values("SCHED_MW", ascending=True)
)

fig_bar = px.bar(
    top5_df, x="SCHED_MW", y="RESOURCE_NAME", orientation="h",
    text_auto=".1f", template="plotly_dark", color_discrete_sequence=["#00A3FF"]
)

fig_bar.update_layout(
    paper_bgcolor="#121829", plot_bgcolor="#121829",
    height=170, margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="", yaxis_title=""
)
st.plotly_chart(fig_bar, use_container_width=True)