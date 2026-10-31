import os
import polars as pl
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & DARK CANVAS STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="TRANSMISSION CONGESTION & RESOURCE CROSS-ANALYTICS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
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
        font-size: 0.82rem !important; 
        font-weight: 800 !important; 
        text-transform: uppercase !important; 
        margin-bottom: 4px !important; 
    }

    .square-kpi-val { 
        color: #FFFFFF !important; 
        font-size: 1.65rem !important; 
        font-weight: 900 !important; 
    }

    .square-kpi-unit { 
        font-size: 0.85rem !important; 
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
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. DATA INGESTION
# ---------------------------------------------------------
SUMMARY_CSV = "D:/NGCP/Transmission_Congestion_5min_Daily_Summary.csv"
RESOURCE_CSV = "D:/NGCP/Subgrid_Resource_Curtailment_Summary.csv"

@st.cache_data
def load_data(path):
    return pl.read_csv(path).to_pandas() if os.path.exists(path) else None

df = load_data(SUMMARY_CSV)
resource_df = load_data(RESOURCE_CSV)

if df is None or df.empty:
    st.error(f"File missing or empty: `{SUMMARY_CSV}`. Please run `process_transmission_congestion_5min.py` first.")
    st.stop()

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

# ---------------------------------------------------------
# 3. CONTROL SLICERS & GRID FOCUS PIPELINE
# ---------------------------------------------------------
top_hdr_left, top_hdr_right = st.columns([0.85, 3.15], gap="small")

with top_hdr_left:
    st.markdown('<div class="title-main">TRANSMISSION CONGESTION</div>', unsafe_allow_html=True)
    st.markdown('<div class="title-sub">RESOURCE-LEVEL CROSS-ANALYTICS</div>', unsafe_allow_html=True)

mid_left_slicers, mid_right_chart = st.columns([0.85, 3.15], gap="small")
filtered_df = df.copy()

with mid_left_slicers:
    available_years = sorted(filtered_df["Date"].dt.year.dropna().astype(int).unique().tolist(), reverse=True)
    selected_year = st.selectbox("Year Slicer", available_years, index=0)
    filtered_df = filtered_df[filtered_df["Date"].dt.year == selected_year]

    selected_grid = st.selectbox("Grid Focus Slicer", ["All Grids (System-Wide)", "Luzon Grid", "Visayas Grid", "Mindanao Grid"])

    view_mode = st.radio("Chart Mode", ["Chronological Trend", "Normalized Hourly Profile", "Matrix Heatmap", "Demand/Curtailment Overlay"])

    min_date, max_date = filtered_df["Date"].min().date(), filtered_df["Date"].max().date()
    selected_dates = st.date_input("Calendar Slicer", value=[min_date, max_date], min_value=min_date, max_value=max_date, key="calendar_slicer_v12")
    
    if isinstance(selected_dates, (list, tuple)) and len(selected_dates) == 2:
        filtered_df = filtered_df[(filtered_df["Date"] >= pd.to_datetime(selected_dates[0])) & (filtered_df["Date"] <= pd.to_datetime(selected_dates[1]))]

# ---------------------------------------------------------
# 4. TOP EXECUTIVE KPI CARDS
# ---------------------------------------------------------
with top_hdr_right:
    if selected_grid == "Luzon Grid":
        tot_base_case = filtered_df["LUZON_BASE_CASE"].sum()
        tot_contingency = filtered_df["LUZON_CONTINGENCY"].sum()
        tot_system_events = filtered_df["LUZON_TOTAL_CONGESTION"].sum()
        tot_curtailed_mw = filtered_df["LUZON_CURTAILED_MW"].sum() if "LUZON_CURTAILED_MW" in filtered_df else 0.0
    elif selected_grid == "Visayas Grid":
        tot_base_case = filtered_df["VISAYAS_BASE_CASE"].sum()
        tot_contingency = filtered_df["VISAYAS_CONTINGENCY"].sum()
        tot_system_events = filtered_df["VISAYAS_TOTAL_CONGESTION"].sum()
        tot_curtailed_mw = filtered_df["VISAYAS_CURTAILED_MW"].sum() if "VISAYAS_CURTAILED_MW" in filtered_df else 0.0
    elif selected_grid == "Mindanao Grid":
        tot_base_case = filtered_df["MINDANAO_BASE_CASE"].sum()
        tot_contingency = filtered_df["MINDANAO_CONTINGENCY"].sum()
        tot_system_events = filtered_df["MINDANAO_TOTAL_CONGESTION"].sum()
        tot_curtailed_mw = filtered_df["MINDANAO_CURTAILED_MW"].sum() if "MINDANAO_CURTAILED_MW" in filtered_df else 0.0
    else:
        tot_base_case = filtered_df["TOTAL_BASE_CASE"].sum()
        tot_contingency = filtered_df["TOTAL_CONTINGENCY"].sum()
        tot_system_events = filtered_df["SYSTEM_TOTAL_CONGESTION"].sum()
        tot_curtailed_mw = filtered_df["TOTAL_CURTAILED_MW"].sum() if "TOTAL_CURTAILED_MW" in filtered_df else 0.0

    avg_demand_gw = (filtered_df["SYSTEM_AVG"].mean() / 1000.0) if "SYSTEM_AVG" in filtered_df and filtered_df["SYSTEM_AVG"].mean() > 0 else 1.0
    events_per_gw = tot_system_events / avg_demand_gw if avg_demand_gw > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">TOTAL CONGESTION EVENTS</div><div class="square-kpi-val" style="color:#E53935;">{tot_system_events:,.0f}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">CONGESTION / GW DEMAND</div><div class="square-kpi-val" style="color:#F97316;">{events_per_gw:,.1f} <span class="square-kpi-unit">Ev/GW</span></div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">CORRELATED RE CURTAILMENT</div><div class="square-kpi-val" style="color:#8B5CF6;">{tot_curtailed_mw:,.1f} <span class="square-kpi-unit">MW</span></div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="square-kpi-card"><div class="square-kpi-label">N-1 CONTINGENCY EVENTS</div><div class="square-kpi-val" style="color:#00A3FF;">{tot_contingency:,.0f}</div></div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 5. MIDDLE ROW: MULTI-VIEW CHART ENGINE
# ---------------------------------------------------------
with mid_right_chart:
    num_days = max((filtered_df["Date"].max() - filtered_df["Date"].min()).days + 1, 1)

    if view_mode == "Chronological Trend":
        st.markdown(f'<div class="section-hdr-large">DAILY TRANSMISSION CONGESTION TIMELINE ({num_days} DAYS)</div>', unsafe_allow_html=True)
        daily = filtered_df.groupby("Date")[["LUZON_TOTAL_CONGESTION", "VISAYAS_TOTAL_CONGESTION", "MINDANAO_TOTAL_CONGESTION"]].sum().reset_index()
        daily["Day_Label"] = daily["Date"].dt.strftime('%b %d')

        fig = go.Figure()
        if selected_grid in ["All Grids (System-Wide)", "Luzon Grid"]:
            fig.add_trace(go.Bar(x=daily["Day_Label"], y=daily["LUZON_TOTAL_CONGESTION"], name="Luzon", marker_color="#00A3FF"))
        if selected_grid in ["All Grids (System-Wide)", "Visayas Grid"]:
            fig.add_trace(go.Bar(x=daily["Day_Label"], y=daily["VISAYAS_TOTAL_CONGESTION"], name="Visayas", marker_color="#F97316"))
        if selected_grid in ["All Grids (System-Wide)", "Mindanao Grid"]:
            fig.add_trace(go.Bar(x=daily["Day_Label"], y=daily["MINDANAO_TOTAL_CONGESTION"], name="Mindanao", marker_color="#10B981"))
        fig.update_layout(template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22", height=380, barmode="stack", margin=dict(l=10, r=10, t=15, b=10))
        st.plotly_chart(fig, use_container_width=True)

    elif view_mode == "Normalized Hourly Profile":
        st.markdown(f'<div class="section-hdr-large">AVERAGE DAILY CONGESTION PROFILE PER HOUR (NORMALIZED ACROSS {num_days} DAYS)</div>', unsafe_allow_html=True)
        filtered_df["Hour"] = pd.to_numeric(filtered_df["Hour"], errors="coerce").fillna(0).astype(int)
        hourly_avg = filtered_df.groupby("Hour")[["LUZON_TOTAL_CONGESTION", "VISAYAS_TOTAL_CONGESTION", "MINDANAO_TOTAL_CONGESTION"]].sum().reset_index()
        
        for col in ["LUZON_TOTAL_CONGESTION", "VISAYAS_TOTAL_CONGESTION", "MINDANAO_TOTAL_CONGESTION"]:
            hourly_avg[col] = hourly_avg[col] / num_days

        hourly_avg["Hour_Label"] = hourly_avg["Hour"].apply(lambda h: f"{h:02d}:00")

        fig = go.Figure()
        if selected_grid in ["All Grids (System-Wide)", "Luzon Grid"]:
            fig.add_trace(go.Bar(x=hourly_avg["Hour_Label"], y=hourly_avg["LUZON_TOTAL_CONGESTION"], name="Luzon Avg/Day", marker_color="#00A3FF"))
        if selected_grid in ["All Grids (System-Wide)", "Visayas Grid"]:
            fig.add_trace(go.Bar(x=hourly_avg["Hour_Label"], y=hourly_avg["VISAYAS_TOTAL_CONGESTION"], name="Visayas Avg/Day", marker_color="#F97316"))
        if selected_grid in ["All Grids (System-Wide)", "Mindanao Grid"]:
            fig.add_trace(go.Bar(x=hourly_avg["Hour_Label"], y=hourly_avg["MINDANAO_TOTAL_CONGESTION"], name="Mindanao Avg/Day", marker_color="#10B981"))
        fig.update_layout(template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22", height=380, barmode="stack", margin=dict(l=10, r=10, t=15, b=10))
        st.plotly_chart(fig, use_container_width=True)

    elif view_mode == "Demand/Curtailment Overlay":
        st.markdown(f'<div class="section-hdr-large">CONGESTION EVENTS VS DEMAND & CURTAILMENT OVERLAY</div>', unsafe_allow_html=True)
        filtered_df["Hour"] = pd.to_numeric(filtered_df["Hour"], errors="coerce").fillna(0).astype(int)
        
        col_target = "SYSTEM_TOTAL_CONGESTION"
        curtail_target = "TOTAL_CURTAILED_MW"
        if selected_grid == "Luzon Grid": 
            col_target = "LUZON_TOTAL_CONGESTION"
            curtail_target = "LUZON_CURTAILED_MW"
        elif selected_grid == "Visayas Grid": 
            col_target = "VISAYAS_TOTAL_CONGESTION"
            curtail_target = "VISAYAS_CURTAILED_MW"
        elif selected_grid == "Mindanao Grid": 
            col_target = "MINDANAO_TOTAL_CONGESTION"
            curtail_target = "MINDANAO_CURTAILED_MW"

        overlay = filtered_df.groupby("Hour")[[col_target, "SYSTEM_AVG", curtail_target]].mean().reset_index().sort_values("Hour")
        overlay["Hour_Label"] = overlay["Hour"].apply(lambda h: f"{h:02d}:00")

        fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
        fig_dual.add_trace(go.Bar(x=overlay["Hour_Label"], y=overlay[col_target], name=f"{selected_grid} Congestion", marker_color="#E53935"), secondary_y=False)
        fig_dual.add_trace(go.Scatter(x=overlay["Hour_Label"], y=overlay["SYSTEM_AVG"], name="System Grid Demand (MW)", line=dict(color="#00A3FF", width=3)), secondary_y=True)
        fig_dual.add_trace(go.Scatter(x=overlay["Hour_Label"], y=overlay[curtail_target], name=f"{selected_grid} Curtailed RE (MW)", line=dict(color="#F59E0B", width=3, dash="dot")), secondary_y=True)

        fig_dual.update_layout(template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22", height=380, margin=dict(l=10, r=10, t=15, b=10))
        st.plotly_chart(fig_dual, use_container_width=True)

    else:
        st.markdown('<div class="section-hdr-large">2D MATRIX CONGESTION HEATMAP (DATES VS HOURS)</div>', unsafe_allow_html=True)
        filtered_df["Hour"] = pd.to_numeric(filtered_df["Hour"], errors="coerce").fillna(0).astype(int)
        
        col_target = "SYSTEM_TOTAL_CONGESTION"
        if selected_grid == "Luzon Grid": col_target = "LUZON_TOTAL_CONGESTION"
        elif selected_grid == "Visayas Grid": col_target = "VISAYAS_TOTAL_CONGESTION"
        elif selected_grid == "Mindanao Grid": col_target = "MINDANAO_TOTAL_CONGESTION"

        heatmap_df = filtered_df.pivot_table(index=filtered_df["Date"].dt.strftime('%Y-%m-%d'), columns="Hour", values=col_target, aggfunc="sum").fillna(0)
        
        fig = px.imshow(heatmap_df, labels=dict(x="Hour of Day", y="Date", color="Events"), x=[f"{h:02d}:00" for h in heatmap_df.columns], color_continuous_scale="Plasma")
        fig.update_layout(template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22", height=380, margin=dict(l=10, r=10, t=15, b=10))
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# 6. BOTTOM ROW: REGIONAL SECURITY MATRIX & RESOURCE DRILL-DOWN TABLE
# ---------------------------------------------------------
bot_left, bot_right = st.columns([3, 2], gap="small")

with bot_left:
    st.markdown('<div class="section-hdr-large">REGIONAL CONGESTION & SECURITY MATRIX</div>', unsafe_allow_html=True)
    matrix = pd.DataFrame([
        {"Island Grid": "LUZON", "Base Case (N-0)": filtered_df["LUZON_BASE_CASE"].sum(), "Contingency (N-1)": filtered_df["LUZON_CONTINGENCY"].sum(), "Total Events": filtered_df["LUZON_TOTAL_CONGESTION"].sum()},
        {"Island Grid": "VISAYAS", "Base Case (N-0)": filtered_df["VISAYAS_BASE_CASE"].sum(), "Contingency (N-1)": filtered_df["VISAYAS_CONTINGENCY"].sum(), "Total Events": filtered_df["VISAYAS_TOTAL_CONGESTION"].sum()},
        {"Island Grid": "MINDANAO", "Base Case (N-0)": filtered_df["MINDANAO_BASE_CASE"].sum(), "Contingency (N-1)": filtered_df["MINDANAO_CONTINGENCY"].sum(), "Total Events": filtered_df["MINDANAO_TOTAL_CONGESTION"].sum()},
    ])
    matrix["Contingency Share (%)"] = ((matrix["Contingency (N-1)"] / matrix["Total Events"].replace(0, 1)) * 100).map(lambda x: f"{x:.1f}%")
    st.dataframe(matrix, use_container_width=True, hide_index=True, height=180)

    # SUB-GRID DISTRICTS & COVERED PLANT LOCATIONS
    st.markdown('<div class="section-hdr-large">SUB-GRID DISTRICTS & COVERED PLANT LOCATIONS (CLICK ROW TO DRILL DOWN)</div>', unsafe_allow_html=True)
    
    luz_ev = filtered_df["LUZON_TOTAL_CONGESTION"].sum()
    vis_ev = filtered_df["VISAYAS_TOTAL_CONGESTION"].sum()
    min_ev = filtered_df["MINDANAO_TOTAL_CONGESTION"].sum()

    luz_curt = filtered_df["LUZON_CURTAILED_MW"].sum() if "LUZON_CURTAILED_MW" in filtered_df else 0.0
    vis_curt = filtered_df["VISAYAS_CURTAILED_MW"].sum() if "VISAYAS_CURTAILED_MW" in filtered_df else 0.0
    min_curt = filtered_df["MINDANAO_CURTAILED_MW"].sum() if "MINDANAO_CURTAILED_MW" in filtered_df else 0.0

    district_map_data = [
        {"Dist #": "01", "Grid": "LUZON", "Sub-Grid & Covered Plant Locations": "NL1 - Ilocos / La Union / Pangasinan / Benguet", "Reg_Events": luz_ev, "Reg_Curt": luz_curt},
        {"Dist #": "02", "Grid": "LUZON", "Sub-Grid & Covered Plant Locations": "CL2 - Bataan / Bulacan / Pampanga / Tarlac / Zambales", "Reg_Events": luz_ev, "Reg_Curt": luz_curt},
        {"Dist #": "03", "Grid": "LUZON", "Sub-Grid & Covered Plant Locations": "SL3 - Batangas / Cavite / Laguna / Quezon / Bicol", "Reg_Events": luz_ev, "Reg_Curt": luz_curt},
        {"Dist #": "04", "Grid": "VISAYAS", "Sub-Grid & Covered Plant Locations": "Panay 04 - Iloilo / Aklan / Capiz / Antique", "Reg_Events": vis_ev, "Reg_Curt": vis_curt},
        {"Dist #": "05", "Grid": "VISAYAS", "Sub-Grid & Covered Plant Locations": "Cebu 05 - Metro Cebu / Mandaue / Mactan", "Reg_Events": vis_ev, "Reg_Curt": vis_curt},
        {"Dist #": "06", "Grid": "VISAYAS", "Sub-Grid & Covered Plant Locations": "Negros 06 - Negros Occidental / Negros Oriental", "Reg_Events": vis_ev, "Reg_Curt": vis_curt},
        {"Dist #": "07", "Grid": "VISAYAS", "Sub-Grid & Covered Plant Locations": "Leyte 07 - Leyte / Biliran / Southern Leyte", "Reg_Events": vis_ev, "Reg_Curt": vis_curt},
        {"Dist #": "08", "Grid": "VISAYAS", "Sub-Grid & Covered Plant Locations": "Samar 08 - Western Samar / Northern / Eastern Samar", "Reg_Events": vis_ev, "Reg_Curt": vis_curt},
        {"Dist #": "09", "Grid": "MINDANAO", "Sub-Grid & Covered Plant Locations": "SM9 - Metro Davao / Davao del Norte / Sur", "Reg_Events": min_ev, "Reg_Curt": min_curt},
        {"Dist #": "10", "Grid": "MINDANAO", "Sub-Grid & Covered Plant Locations": "NM10 - Misamis Oriental / Bukidnon / CDO / Lanao Norte", "Reg_Events": min_ev, "Reg_Curt": min_curt},
        {"Dist #": "11", "Grid": "MINDANAO", "Sub-Grid & Covered Plant Locations": "Soccsksargen 11 - South Cotabato / GenSan / Sultan Kudarat", "Reg_Events": min_ev, "Reg_Curt": min_curt},
        {"Dist #": "12", "Grid": "MINDANAO", "Sub-Grid & Covered Plant Locations": "WM12 - Zamboanga City / Del Sur / Del Norte / Sibugay", "Reg_Events": min_ev, "Reg_Curt": min_curt},
        {"Dist #": "13", "Grid": "MINDANAO", "Sub-Grid & Covered Plant Locations": "Caraga 13 - Agusan del Norte / Surigao / Butuan", "Reg_Events": min_ev, "Reg_Curt": min_curt},
        {"Dist #": "14", "Grid": "MINDANAO", "Sub-Grid & Covered Plant Locations": "BARMM 14 - Maguindanao / Lanao Sur / Sulu", "Reg_Events": min_ev, "Reg_Curt": min_curt},
    ]
    
    subgrid_df = pd.DataFrame(district_map_data)

    if selected_grid == "Luzon Grid":
        subgrid_df = subgrid_df[subgrid_df["Grid"] == "LUZON"]
    elif selected_grid == "Visayas Grid":
        subgrid_df = subgrid_df[subgrid_df["Grid"] == "VISAYAS"]
    elif selected_grid == "Mindanao Grid":
        subgrid_df = subgrid_df[subgrid_df["Grid"] == "MINDANAO"]

    def assign_status(row):
        if row["Reg_Events"] > 1000 or row["Reg_Curt"] > 50:
            return "YES (HIGH)"
        elif row["Reg_Events"] > 0 or row["Reg_Curt"] > 0:
            return "YES (MODERATE)"
        return "NO"

    subgrid_df["Congested?"] = subgrid_df.apply(assign_status, axis=1)
    subgrid_df["Curtailed RE (MW)"] = subgrid_df["Reg_Curt"].map(lambda x: f"{x:,.1f} MW")

    display_table = subgrid_df[["Dist #", "Grid", "Sub-Grid & Covered Plant Locations", "Congested?", "Curtailed RE (MW)"]]

    selected_event = st.dataframe(
        display_table,
        use_container_width=True,
        hide_index=True,
        height=280,
        on_select="rerun",
        selection_mode="single-row"
    )

    # ---------------------------------------------------------
    # DRILL DOWN: PULL ACTUAL RESOURCE_NAME FROM DATASET
    # ---------------------------------------------------------
    selected_rows = selected_event.get("selection", {}).get("rows", [])
    if selected_rows:
        clicked_idx = selected_rows[0]
        clicked_district = display_table.iloc[clicked_idx]["Dist #"]
        clicked_name = display_table.iloc[clicked_idx]["Sub-Grid & Covered Plant Locations"]

        st.markdown(f'<div class="section-hdr-large" style="color:#00A3FF;">DISTRICT {clicked_district} GENERATOR RESOURCE DRILL-DOWN ({clicked_name})</div>', unsafe_allow_html=True)
        
        if resource_df is not None and not resource_df.empty:
            resource_df["DISTRICT_CODE"] = resource_df["DISTRICT_CODE"].astype(str).str.zfill(2)
            matched_resources = resource_df[resource_df["DISTRICT_CODE"] == str(clicked_district).zfill(2)]

            if not matched_resources.empty:
                display_res = matched_resources[["RESOURCE_NAME", "FUEL_TYPE", "TOTAL_RESOURCE_CURTAILED_MW", "CURTAILMENT_EVENTS_COUNT"]].rename(
                    columns={
                        "RESOURCE_NAME": "Generator Unit (Resource Name)",
                        "FUEL_TYPE": "Fuel Type",
                        "TOTAL_RESOURCE_CURTAILED_MW": "Curtailed Power (MW)",
                        "CURTAILMENT_EVENTS_COUNT": "5-Min Curtailment Occurrences"
                    }
                )
                st.dataframe(display_res, use_container_width=True, hide_index=True)
            else:
                st.warning(f"No specific 5-minute resource curtailment logs found for District {clicked_district} in dataset.")
        else:
            st.info("Run `python process_transmission_congestion_5min.py` to extract resource-level details.")

with bot_right:
    st.markdown('<div class="section-hdr-large">REGIONAL CONGESTION SHARE (%)</div>', unsafe_allow_html=True)
    pie_df = matrix[matrix["Total Events"] > 0]
    fig_pie = go.Figure(go.Pie(
        labels=pie_df["Island Grid"], values=pie_df["Total Events"], hole=0.45,
        textinfo="percent+label", textposition="inside", textfont=dict(size=13, color="#FFFFFF", family="Arial Black"),
        marker=dict(colors=["#00A3FF", "#F97316", "#10B981"])
    ))
    fig_pie.update_layout(template="plotly_dark", paper_bgcolor="#161A22", plot_bgcolor="#161A22", height=280, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_pie, use_container_width=True)