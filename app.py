"""SupplierDash - Supplier Performance & Risk Dashboard.

Stable fixed-KPI version restored after removing the dynamic KPI rewrite.
"""

from __future__ import annotations

import html
import io
import re
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="SupplierDash",
    page_icon="SD",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------
COL_SUPPLIER = "Supplier_Name"
COL_CATEGORY = "Category"
COL_DELIVERY = "Delivery_Performance_%"
COL_LEADTIME = "Lead_Time_Days"
COL_QUALITY = "Quality_Score_%"
COL_COMPLAINT = "Complaint_Rate_%"
COL_PRICE_SAVE = "Price_Savings_%"
COL_PRICE_DEV = COL_PRICE_SAVE
COL_UNIT_PRICE = "Unit_Price"
COL_PRICE_VOL = "Price_Volatility_%"
COL_SCORE = "Overall_Score"
COL_STATUS = "Status"
COL_ORDER_STATUS = "Order_Status"
COL_SPEND = "Spend"
COL_NOTES = "Notes"
COL_AUDIT = "Last_Audit_Date"
COL_DATE = "Period_Date"
COL_TOTAL_SHIP = "Total_Shipments"
COL_ONTIME_SHIP = "On_Time_Shipments"

REQUIRED_COLS = [
    COL_SUPPLIER,
]

KPI_COLS = [
    COL_DELIVERY,
    COL_LEADTIME,
    COL_QUALITY,
    COL_COMPLAINT,
    COL_PRICE_DEV,
]

NUMERIC_COLS = [
    COL_DELIVERY,
    COL_LEADTIME,
    COL_QUALITY,
    COL_COMPLAINT,
    COL_PRICE_DEV,
    COL_SCORE,
    COL_SPEND,
    COL_UNIT_PRICE,
    COL_PRICE_VOL,
    COL_TOTAL_SHIP,
    COL_ONTIME_SHIP,
]

AUTO_MAP: dict[str, list[str]] = {
    COL_SUPPLIER: ["suppliername", "supplier", "name", "lieferant", "vendor", "vendorname"],
    COL_CATEGORY: ["category", "kategorie", "itemcategory", "itemcategory", "material", "materialgroup", "commodity"],
    COL_DELIVERY: ["deliveryperformance", "ontimedelivery", "otd", "liefertreue", "deliveryrate"],
    COL_LEADTIME: ["leadtimedays", "leadtime", "leadtimeday", "lieferzeit", "avgleadtime"],
    COL_QUALITY: ["qualityscore", "qualityscore", "quality", "qualitatsrate", "qualityrate", "qualitaet"],
    COL_COMPLAINT: ["complaintrate", "defectratecomplaintrate", "defectrate", "complaints", "reklamationsquote", "claimrate"],
    COL_PRICE_DEV: ["savings", "savingspercent", "savingspct", "pricesavings", "pricesaving", "saving", "costsavings", "pricedeviation", "pricedev", "preisabweichung", "pricevariance"],
    COL_UNIT_PRICE: ["unitprice", "unitcost", "priceperunit", "rate", "unitrate", "purchaseprice"],
    COL_PRICE_VOL: ["pricevolatility", "unitpricevolatility", "pricevolatilitypercent", "pricevolatilitypct"],
    COL_SCORE: ["overallscore", "score", "gesamtscore", "totalscore"],
    COL_STATUS: ["orderstatus", "status", "supplierstatus", "riskstatus"],
    COL_SPEND: ["spendamount", "spend", "annualspend", "totalspend", "purchasevalue", "value"],
    COL_NOTES: ["notes", "comment", "comments", "remark", "remarks"],
    COL_AUDIT: ["lastauditdate", "auditdate", "lastaudit"],
    COL_DATE: ["orderdate", "date", "month", "period", "reportingdate", "reportdate", "datum", "monat"],
    COL_TOTAL_SHIP: ["totalshipments", "shipments", "totaldeliveries"],
    COL_ONTIME_SHIP: ["ontimeshipments", "ontimedeliveries"],
}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "delivery_target": 85.0,
    "quality_target": 90.0,
    "leadtime_limit": 11.0,
    "complaint_limit": 4.0,
    "price_dev_tolerance": 5.0,
    "weight_delivery": 30.0,
    "weight_quality": 25.0,
    "weight_complaint": 20.0,
    "weight_leadtime": 15.0,
    "weight_price": 10.0,
    "penalty_delivery_cutoff": 80.0,
    "penalty_delivery_points": 15.0,
    "penalty_quality_cutoff": 85.0,
    "penalty_quality_points": 10.0,
    "penalty_complaint_cutoff": 8.0,
    "penalty_complaint_points": 15.0,
    "risk_low_threshold": 88.0,
    "risk_medium_threshold": 50.0,
    "top_supplier_rows": 14,
    "show_delivery_trend": True,
}

for key, value in DEFAULT_SETTINGS.items():
    st.session_state.setdefault(key, value)

SETTINGS_DEFAULT_VERSION = "strict_green_threshold_v1"
if st.session_state.get("_settings_default_version") != SETTINGS_DEFAULT_VERSION:
    if float(st.session_state.get("risk_low_threshold", 70.0)) == 70.0:
        st.session_state["risk_low_threshold"] = DEFAULT_SETTINGS["risk_low_threshold"]
    st.session_state["_settings_default_version"] = SETTINGS_DEFAULT_VERSION

for key in DEFAULT_SETTINGS:
    st.session_state[key] = st.session_state[key]


def reset_settings() -> None:
    for key, value in DEFAULT_SETTINGS.items():
        st.session_state[key] = value


def get_effective_rules() -> dict[str, float | str]:
    return {
        "delivery_target": float(st.session_state["delivery_target"]),
        "quality_target": float(st.session_state["quality_target"]),
        "leadtime_limit": float(st.session_state["leadtime_limit"]),
        "complaint_limit": float(st.session_state["complaint_limit"]),
        "price_dev_tolerance": float(st.session_state["price_dev_tolerance"]),
        "delivery_threshold": float(st.session_state["delivery_target"]),
        "quality_threshold": float(st.session_state["quality_target"]),
        "leadtime_threshold": float(st.session_state["leadtime_limit"]),
        "complaint_threshold": float(st.session_state["complaint_limit"]),
        "price_threshold": float(st.session_state["price_dev_tolerance"]),
        "weight_delivery": float(st.session_state["weight_delivery"]),
        "weight_quality": float(st.session_state["weight_quality"]),
        "weight_complaint": float(st.session_state["weight_complaint"]),
        "weight_leadtime": float(st.session_state["weight_leadtime"]),
        "weight_price": float(st.session_state["weight_price"]),
        "penalty_delivery_cutoff": float(st.session_state["penalty_delivery_cutoff"]),
        "penalty_delivery_points": float(st.session_state["penalty_delivery_points"]),
        "penalty_quality_cutoff": float(st.session_state["penalty_quality_cutoff"]),
        "penalty_quality_points": float(st.session_state["penalty_quality_points"]),
        "penalty_complaint_cutoff": float(st.session_state["penalty_complaint_cutoff"]),
        "penalty_complaint_points": float(st.session_state["penalty_complaint_points"]),
        "risk_low_threshold": float(st.session_state["risk_low_threshold"]),
        "risk_medium_threshold": float(st.session_state["risk_medium_threshold"]),
    }


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
html, body, [class*="css"] { font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif !important; scroll-behavior:smooth !important; }
.stApp { background:
    radial-gradient(circle at 15% 0%, rgba(56,139,253,.08), transparent 28%),
    radial-gradient(circle at 85% 8%, rgba(63,185,80,.045), transparent 25%),
    #0d1117 !important; color:#e6edf3 !important; }
.block-container { padding:1rem 1.55rem 2rem 1.55rem !important; max-width:100% !important; }
#MainMenu, footer { visibility:hidden !important; }
header[data-testid="stHeader"] { background:transparent !important; height:2.75rem !important; }
section[data-testid="stSidebar"] { background:linear-gradient(180deg,#161b22,#10161f) !important;
    border-right:1px solid #30363d !important; box-shadow:14px 0 34px rgba(0,0,0,.24) !important; }
section[data-testid="stSidebar"] * { color:#c9d1d9 !important; }
@keyframes softPageIn {
    from { opacity:0; transform:translateY(var(--nav-start-y, 18px)); filter:blur(2px); }
    to { opacity:1; transform:translateY(0); filter:blur(0); }
}
section.main, div[data-testid="stAppViewContainer"], div[data-testid="stMain"] {
    scroll-behavior:smooth !important;
}
@keyframes softNavIn {
    from { opacity:.86; transform:translateX(-4px); }
    to { opacity:1; transform:translateX(0); }
}
section.main .block-container > div:first-child,
.top-bar,.metric-grid,.s-card,.anomaly-summary-grid,.category-grid,
div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {
    animation:softPageIn .46s cubic-bezier(.18,.82,.22,1) both;
    animation-duration:var(--nav-duration, .46s);
}
@media (prefers-reduced-motion: reduce) {
    section.main .block-container > div:first-child,
    .top-bar,.metric-grid,.s-card,.anomaly-summary-grid,.category-grid,
    div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] { animation:none !important; }
}
.logo-box { font-size:1.05rem; font-weight:900; color:#e6edf3; padding:.7rem .35rem 1rem;
    border-bottom:1px solid #30363d; margin-bottom:.85rem; }
.side-title { font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; color:#8b949e !important;
    font-weight:900; margin:1rem .35rem .35rem; }
.file-panel { margin-top:1.2rem; padding:.85rem; border:1px solid #30363d; border-radius:14px;
    background:linear-gradient(145deg,#161b22,#101722); box-shadow:0 12px 28px rgba(0,0,0,.20); }
.file-panel-title { color:#e6edf3; font-size:.8rem; font-weight:950; margin-bottom:.45rem; }
.file-chip { display:flex; align-items:center; gap:.55rem; padding:.55rem .6rem; border-radius:10px;
    background:#0d1117; border:1px solid #21262d; margin:.45rem 0 .65rem; }
.file-chip-icon { width:30px; height:30px; border-radius:8px; background:rgba(88,166,255,.14); color:#58a6ff;
    display:flex; align-items:center; justify-content:center; font-weight:950; flex-shrink:0; }
.file-chip-name { color:#f0f6fc; font-size:.78rem; font-weight:850; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.file-chip-note { color:#8b949e; font-size:.68rem; font-weight:750; }
div[role="radiogroup"] { overflow:visible !important; }
div[role="radiogroup"] label { position:relative; display:flex !important; width:100% !important;
    box-sizing:border-box !important; background:transparent !important; border-radius:10px !important;
    padding:.62rem .78rem !important; margin:.08rem 0 !important; cursor:pointer !important;
    user-select:none !important; border:1px solid transparent !important;
    transition:transform .24s cubic-bezier(.2,.8,.2,1), box-shadow .24s ease, background .24s ease, border-color .24s ease; }
div[role="radiogroup"] label:hover { background:rgba(33,38,45,.55) !important; transform:translateX(1px); }
div[role="radiogroup"] label:has(input:checked) {
    width:calc(100% + .95rem) !important;
    margin-right:-.95rem !important;
    background:linear-gradient(90deg, rgba(31,111,235,.32), rgba(22,27,34,.90) 62%, rgba(22,27,34,.30) 84%, rgba(22,27,34,0)) !important;
    border:1px solid transparent !important;
    border-left-color:rgba(88,166,255,.48) !important;
    border-right:0 !important;
    border-radius:12px 0 0 12px !important;
    box-shadow:0 10px 22px rgba(0,0,0,.20), 16px 0 30px rgba(31,111,235,.06),
        inset 4px 0 0 #58a6ff !important;
    -webkit-mask-image:linear-gradient(90deg,#000 0%,#000 68%,rgba(0,0,0,.55) 84%,transparent 100%);
    mask-image:linear-gradient(90deg,#000 0%,#000 68%,rgba(0,0,0,.55) 84%,transparent 100%);
    transform:none;
    animation:softNavIn .34s cubic-bezier(.16,.84,.22,1) both;
}
div[role="radiogroup"] label:has(input:checked)::before {
    display:none;
}
div[role="radiogroup"] label:has(input:checked)::after {
    content:""; display:block; position:absolute; right:0; top:0; bottom:0; width:72px;
    background:linear-gradient(90deg, rgba(16,22,31,0), rgba(16,22,31,.55) 58%, #10161f 100%);
    pointer-events:none;
}
div[role="radiogroup"] label:has(input:checked) p {
    color:#f0f6fc !important;
}
div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child { display:none !important; }
div[role="radiogroup"] label, div[role="radiogroup"] label * { cursor:pointer !important; }
div[role="radiogroup"] label p { font-size:.86rem !important; font-weight:750 !important; }
.stSelectbox label,.stTextInput label,.stFileUploader label,.stSlider label,.stCheckbox label {
    color:#8b949e !important; font-size:.78rem !important; font-weight:750 !important; }
div[data-baseweb="select"] > div,.stTextInput input { background:linear-gradient(180deg,#242a33,#1f242d) !important;
    border:1px solid #363d49 !important; color:#e6edf3 !important; border-radius:10px !important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.035), 0 8px 18px rgba(0,0,0,.14) !important; }
div[data-baseweb="select"], div[data-baseweb="select"] *, .stCheckbox label, .stCheckbox label *,
.stSlider [role="slider"], .stButton > button, .stDownloadButton > button { cursor:pointer !important; }
.stButton > button,.stDownloadButton > button { background:#1f3a5f !important; border:1px solid #388bfd !important;
    color:#58a6ff !important; border-radius:9px !important; font-weight:800 !important; }
.top-bar { background:linear-gradient(135deg,#171d26,#111820); border:1px solid #30363d; border-radius:14px; padding:1rem 1.2rem;
    margin-bottom:1rem; display:flex; justify-content:space-between; align-items:center; gap:.8rem; flex-wrap:wrap;
    box-shadow:0 18px 42px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.035); }
.top-title { font-size:1.35rem; font-weight:900; color:#e6edf3; }
.top-sub { font-size:.82rem; color:#8b949e; margin-top:.15rem; }
.metric-grid { display:grid; grid-template-columns:repeat(7,minmax(145px,1fr)); gap:.8rem; margin-bottom:.9rem; }
@media (max-width:1600px) and (min-width:901px){
    .metric-grid{ grid-template-columns:repeat(12,minmax(0,1fr)); }
    .metric-grid .kpi-card{ grid-column:span 3; }
    .metric-grid .kpi-card:nth-child(n+5){ grid-column:span 4; }
}
@media (max-width:900px){
    .metric-grid{ grid-template-columns:repeat(1,minmax(160px,1fr)); }
    .metric-grid .kpi-card{ grid-column:auto; }
}
.kpi-card { position:relative; background:linear-gradient(145deg,#171d26,#101722); border:1px solid #303946; border-radius:14px; padding:1rem 1.1rem;
    display:flex; align-items:center; gap:.85rem; min-height:96px; overflow:hidden;
    box-shadow:0 16px 34px rgba(0,0,0,.24), inset 0 1px 0 rgba(255,255,255,.04); }
.kpi-card::before { content:""; position:absolute; inset:0 0 auto 0; height:3px;
    background:linear-gradient(90deg,#58a6ff,#39d0c8,#3fb950); opacity:.78; }
.kpi-card:hover { transform:translateY(-1px); border-color:#42526a; box-shadow:0 22px 44px rgba(0,0,0,.30), 0 0 0 1px rgba(88,166,255,.08) inset; }
.kpi-icon { width:44px; height:44px; border-radius:12px; display:flex; align-items:center; justify-content:center;
    font-size:.82rem; font-weight:900; flex-shrink:0; background:linear-gradient(135deg,rgba(56,139,253,.24),rgba(56,139,253,.08));
    color:#58a6ff; box-shadow:inset 0 1px 0 rgba(255,255,255,.08); }
.kpi-label { font-size:.76rem; color:#8b949e; font-weight:800; }
.kpi-value { font-size:1.55rem; font-weight:900; color:#e6edf3; line-height:1.12; }
.kpi-scope { font-size:.68rem; color:#8b949e; font-weight:700; margin-top:2px; }
.kpi-good { font-size:.74rem; color:#3fb950; font-weight:850; }
.kpi-bad { font-size:.74rem; color:#f85149; font-weight:850; }
.kpi-muted { font-size:.72rem; color:#6e7681; }
.health-grid { display:grid; grid-template-columns:repeat(3,minmax(150px,1fr)); gap:.75rem; margin-bottom:.9rem; }
@media (max-width:900px){ .health-grid{ grid-template-columns:1fr; } }
.health-card { position:relative; overflow:hidden; background:linear-gradient(145deg,#171d26,#101722);
    border:1px solid #303946; border-radius:14px; padding:.95rem 1rem;
    box-shadow:0 16px 34px rgba(0,0,0,.24), inset 0 1px 0 rgba(255,255,255,.035); }
.health-card::before { content:""; position:absolute; inset:0 auto 0 0; width:5px; background:var(--health-color,#58a6ff); }
.health-label { color:#8b949e; font-size:.74rem; font-weight:850; text-transform:uppercase; letter-spacing:.04em; }
.health-value { color:#f0f6fc; font-size:2rem; font-weight:950; line-height:1.08; margin-top:.2rem; }
.health-note { color:#8b949e; font-size:.74rem; font-weight:750; margin-top:.25rem; }
.s-card { background:linear-gradient(145deg,#171d26,#101722); border:1px solid #303946; border-radius:14px;
    padding:1rem 1.1rem; height:100%; overflow:hidden; margin-bottom:.9rem;
    box-shadow:0 16px 36px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.035); }
.s-card-title { font-size:.98rem; font-weight:950; color:#f0f6fc; margin-bottom:.85rem; letter-spacing:-.01em; }
.status-low,.status-medium,.status-high { padding:.15rem .55rem; border-radius:16px; font-size:.72rem;
    font-weight:850; display:inline-block; }
.status-low { background:rgba(63,185,80,.12); color:#3fb950; border:1px solid rgba(63,185,80,.35); }
.status-medium { background:rgba(210,153,34,.12); color:#d29922; border:1px solid rgba(210,153,34,.35); }
.status-high { background:rgba(248,81,73,.12); color:#f85149; border:1px solid rgba(248,81,73,.35); }
.chip-row { margin-top:.35rem; display:flex; flex-wrap:wrap; gap:4px; }
.kpi-chip { position:relative; padding:.12rem .5rem; border-radius:8px; font-size:.7rem; font-weight:800;
    white-space:nowrap; background:rgba(248,81,73,.10); color:#f85149; border:1px solid rgba(248,81,73,.30); }
.kpi-chip.amber { background:rgba(210,153,34,.10); color:#d29922; border-color:rgba(210,153,34,.30); }
.kpi-chip:hover::after { content:attr(title); position:absolute; left:0; bottom:calc(100% + 8px); z-index:9999;
    min-width:210px; max-width:280px; white-space:normal; background:#f0f6fc; color:#0d1117;
    border:1px solid #8b949e; border-radius:8px; padding:.48rem .6rem; box-shadow:0 8px 24px rgba(0,0,0,.35);
    font-size:.72rem; line-height:1.35; font-weight:800; }
.anomaly-table-wrap { max-height:560px; overflow:auto; border:1px solid #30363d; border-radius:10px; }
.anomaly-table { width:100%; min-width:1120px; border-collapse:separate; border-spacing:0; table-layout:fixed; }
.anomaly-table th { position:sticky; top:0; z-index:2; background:#1b1f27; color:#c9d1d9; font-size:.74rem;
    text-align:left; padding:.7rem .65rem; border-bottom:1px solid #30363d; white-space:nowrap; }
.anomaly-table td { background:#0d1117; color:#f0f6fc; font-size:.76rem; font-weight:750; padding:.72rem .65rem;
    border-bottom:1px solid #21262d; vertical-align:middle; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.anomaly-table .num { text-align:right; font-variant-numeric:tabular-nums; }
.anomaly-table th:nth-child(1), .anomaly-table td:nth-child(1) { width:180px; }
.anomaly-table th:nth-child(2), .anomaly-table td:nth-child(2) { width:170px; }
.anomaly-table th:nth-child(3), .anomaly-table td:nth-child(3) { width:130px; }
.anomaly-table th:nth-child(4), .anomaly-table td:nth-child(4),
.anomaly-table th:nth-child(5), .anomaly-table td:nth-child(5),
.anomaly-table th:nth-child(6), .anomaly-table td:nth-child(6),
.anomaly-table th:nth-child(7), .anomaly-table td:nth-child(7),
.anomaly-table th:nth-child(8), .anomaly-table td:nth-child(8) { width:92px; }
.anomaly-table th:nth-child(9), .anomaly-table td:nth-child(9) { width:96px; }
.anomaly-table th:nth-child(10), .anomaly-table td:nth-child(10) { width:74px; }
.anomaly-table th:nth-child(11), .anomaly-table td:nth-child(11) { width:150px; overflow:visible; }
.issue-summary { position:relative; display:inline-block; padding:.22rem .62rem; border-radius:999px;
    font-size:.72rem; font-weight:850; color:#f85149; background:rgba(248,81,73,.10); border:1px solid rgba(248,81,73,.34); }
.issue-summary.clear { color:#3fb950; background:rgba(63,185,80,.10); border-color:rgba(63,185,80,.34); }
.issue-summary:hover::after { content:attr(title); position:absolute; right:0; top:calc(100% + 8px); z-index:9999;
    min-width:260px; max-width:360px; white-space:normal; background:#f0f6fc; color:#0d1117;
    border:1px solid #8b949e; border-radius:8px; padding:.55rem .65rem; box-shadow:0 8px 24px rgba(0,0,0,.35);
    font-size:.72rem; line-height:1.4; font-weight:800; }
.anomaly-summary-grid { display:grid; grid-template-columns:repeat(4,minmax(160px,1fr)); gap:.75rem; margin-bottom:.85rem; }
@media (max-width:1100px){ .anomaly-summary-grid{ grid-template-columns:repeat(2,minmax(160px,1fr)); } }
.anomaly-summary-card { background:linear-gradient(135deg,#171d26,#111820); border:1px solid #303946;
    border-radius:14px; padding:.95rem 1rem; min-height:98px; box-shadow:0 16px 34px rgba(0,0,0,.24), inset 0 1px 0 rgba(255,255,255,.035); }
.anomaly-summary-label { color:#8b949e; font-size:.72rem; font-weight:850; text-transform:uppercase; letter-spacing:.04em; }
.anomaly-summary-value { color:#e6edf3; font-size:1.55rem; font-weight:950; margin-top:.2rem; line-height:1.1; }
.anomaly-summary-note { color:#8b949e; font-size:.74rem; font-weight:750; margin-top:.32rem; }
.priority-list { display:flex; flex-direction:column; gap:.55rem; }
.priority-row { display:grid; grid-template-columns:1.5fr 1fr .75fr 1.35fr .55fr; gap:.75rem; align-items:center;
    background:rgba(13,17,23,.82); border:1px solid #263040; border-radius:12px; padding:.72rem .85rem;
    box-shadow:0 10px 22px rgba(0,0,0,.15); }
@media (max-width:1200px){ .priority-row{ grid-template-columns:1fr; align-items:start; } }
.priority-title { color:#f0f6fc; font-weight:950; }
.priority-sub { color:#8b949e; font-size:.72rem; font-weight:750; margin-top:.1rem; }
.severity-pill { display:inline-block; border-radius:999px; padding:.22rem .62rem; font-size:.72rem; font-weight:900; }
.severity-critical { color:#f85149; background:rgba(248,81,73,.12); border:1px solid rgba(248,81,73,.38); }
.severity-warning { color:#d29922; background:rgba(210,153,34,.12); border:1px solid rgba(210,153,34,.38); }
.severity-watch { color:#58a6ff; background:rgba(88,166,255,.12); border:1px solid rgba(88,166,255,.38); }
.trend-target-chip { display:inline-flex; align-items:center; gap:.38rem; padding:.2rem .7rem; border-radius:999px;
    color:#79c0ff; background:linear-gradient(135deg,rgba(88,166,255,.18),rgba(88,166,255,.06));
    border:1px solid rgba(88,166,255,.50); font-size:.72rem; font-weight:950;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.05), 0 8px 18px rgba(31,111,235,.10); }
.trend-target-chip::before { content:"Target"; color:#0d1117; background:#79c0ff; border-radius:999px;
    padding:.05rem .38rem; font-size:.62rem; font-weight:950; letter-spacing:.02em; }
.trend-summary-chip { display:inline-flex; align-items:center; gap:.38rem; padding:.2rem .7rem; border-radius:999px;
    color:#e6edf3; background:rgba(139,148,158,.12); border:1px solid rgba(139,148,158,.34);
    font-size:.72rem; font-weight:900; }
.category-grid { display:grid; grid-template-columns:repeat(3,minmax(230px,1fr)); gap:.75rem; margin-top:.85rem; }
@media (max-width:1200px){ .category-grid{ grid-template-columns:repeat(2,minmax(230px,1fr)); } }
@media (max-width:800px){ .category-grid{ grid-template-columns:1fr; } }
.category-card { position:relative; overflow:hidden; background:linear-gradient(145deg,#171d26,#0f151d);
    border:1px solid #303946; border-radius:16px; padding:1rem; min-height:150px;
    box-shadow:0 18px 38px rgba(0,0,0,.26), inset 0 1px 0 rgba(255,255,255,.035); }
.category-card::before { content:""; position:absolute; inset:0 auto 0 0; width:5px; background:var(--cat-color,#58a6ff); }
.category-card-title { color:#f0f6fc; font-size:1rem; font-weight:950; padding-left:.25rem; }
.category-card-status { display:inline-block; margin-top:.45rem; padding:.2rem .55rem; border-radius:999px;
    font-size:.7rem; font-weight:900; color:var(--cat-color,#58a6ff); background:rgba(88,166,255,.10); border:1px solid color-mix(in srgb, var(--cat-color,#58a6ff) 45%, transparent); }
.category-card-metrics { display:grid; grid-template-columns:repeat(3,1fr); gap:.5rem; margin-top:.85rem; }
.category-card-metrics div { background:rgba(255,255,255,.025); border:1px solid #21262d; border-radius:10px; padding:.45rem; }
.category-card-metrics span { display:block; color:#8b949e; font-size:.66rem; font-weight:800; }
.category-card-metrics b { color:#e6edf3; font-size:.95rem; }
.category-action { color:#8b949e; font-size:.74rem; font-weight:750; margin-top:.75rem; }
.category-supplier-row { display:grid; grid-template-columns:62px minmax(0,1fr) auto; gap:.45rem; align-items:center;
    background:rgba(13,17,23,.62); border:1px solid #21262d; border-radius:10px; padding:.48rem .55rem; margin-top:.55rem; }
.category-supplier-tag { color:#8b949e; font-size:.64rem; font-weight:900; text-transform:uppercase; letter-spacing:.04em; }
.category-supplier-name { color:#e6edf3; font-size:.76rem; font-weight:900; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.category-supplier-score { font-size:.75rem; font-weight:950; }
.weakness-pill { display:inline-block; margin-top:.65rem; border-radius:999px; padding:.22rem .55rem;
    color:#f778ba; background:rgba(247,120,186,.10); border:1px solid rgba(247,120,186,.34);
    font-size:.68rem; font-weight:900; }
.profile-avatar { width:48px; height:48px; border-radius:14px; background:linear-gradient(135deg,#1f6feb,#58a6ff);
    display:flex; align-items:center; justify-content:center; color:white; font-weight:900; }
.kpi-ring-grid { display:grid; grid-template-columns:repeat(3,minmax(74px,1fr)); gap:.65rem; margin-top:1rem; }
.kpi-ring-card { background:rgba(255,255,255,.025); border:1px solid #21262d; border-radius:13px; padding:.65rem .45rem;
    text-align:center; box-shadow:inset 0 1px 0 rgba(255,255,255,.025); }
.kpi-ring { position:relative; width:58px; height:58px; border-radius:50%; margin:0 auto .42rem;
    display:grid; place-items:center; background:conic-gradient(var(--ring-color,#58a6ff) var(--ring-value,0%), #30363d 0);
    box-shadow:0 10px 22px rgba(0,0,0,.24); }
.kpi-ring::before { content:""; position:absolute; width:42px; height:42px; border-radius:50%; background:#0d1117; border:1px solid #21262d; }
.kpi-ring span { position:relative; z-index:1; color:#e6edf3; font-size:.68rem; font-weight:950;
    max-width:38px; line-height:1.05; text-align:center; }
.kpi-ring-label { color:#8b949e; font-size:.66rem; font-weight:850; text-transform:uppercase; letter-spacing:.03em; }
.kpi-ring-detail { color:#e6edf3; font-size:.77rem; font-weight:900; margin-top:.1rem; }
.spend-mini { background:rgba(88,166,255,.055); border:1px solid rgba(88,166,255,.22); border-radius:13px;
    padding:.7rem .75rem; margin-top:.85rem; }
.spend-mini-label { color:#8b949e; font-size:.68rem; font-weight:850; text-transform:uppercase; letter-spacing:.04em; }
.spend-mini-value { color:#e6edf3; font-size:1.12rem; font-weight:950; margin-top:.08rem; }
.spend-bar { height:8px; border-radius:999px; overflow:hidden; background:#21262d; border:1px solid #30363d; margin-top:.52rem; }
.spend-bar div { height:100%; border-radius:999px; background:linear-gradient(90deg,#58a6ff,#3fb950); }
.spend-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:.7rem; align-items:center; margin:.62rem 0; }
.spend-row-name { color:#e6edf3; font-size:.74rem; font-weight:850; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.spend-row-value { color:#8b949e; font-size:.72rem; font-weight:850; }
.spend-row-bar { grid-column:1 / -1; height:7px; background:#21262d; border-radius:999px; overflow:hidden; }
.spend-row-bar div { height:100%; border-radius:999px; background:linear-gradient(90deg,#388bfd,#2ea043); }
.diag-legend { display:flex; flex-wrap:wrap; gap:.55rem .8rem; margin:.55rem 0 .25rem; }
.diag-legend-item { display:inline-flex; align-items:center; gap:.38rem; color:#c9d1d9; font-size:.74rem; font-weight:850; }
.diag-legend-dot { width:10px; height:10px; border-radius:999px; display:inline-block; box-shadow:0 0 0 3px rgba(255,255,255,.035); }
div[data-testid="stDataFrame"] { border:1px solid #303946 !important; border-radius:12px !important;
    overflow:hidden !important; box-shadow:0 14px 30px rgba(0,0,0,.18) !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def auto_detect_columns(df: pd.DataFrame) -> dict[str, str | None]:
    norm_to_actual = {normalize_name(col): str(col) for col in df.columns}
    result: dict[str, str | None] = {}
    used: set[str] = set()
    for internal, candidates in AUTO_MAP.items():
        found = None
        for cand in candidates:
            actual = norm_to_actual.get(cand)
            if actual and actual not in used:
                found = actual
                break
        if found is None:
            for cand in candidates:
                for norm, actual in norm_to_actual.items():
                    if actual not in used and len(cand) >= 5 and cand in norm:
                        found = actual
                        break
                if found:
                    break
        result[internal] = found
        if found:
            used.add(found)
    return result


def apply_session_column_mapping_overrides(
    col_map: dict[str, str | None], file_cols: list[str]
) -> dict[str, str | None]:
    mapping_cols = [
        COL_SUPPLIER,
        COL_CATEGORY,
        COL_DATE,
        COL_STATUS,
        *KPI_COLS,
        COL_SPEND,
        COL_UNIT_PRICE,
        COL_PRICE_VOL,
        COL_TOTAL_SHIP,
        COL_ONTIME_SHIP,
    ]
    allowed_choices = set(file_cols)
    allowed_choices.add("-- not present --")
    for internal in mapping_cols:
        state_key = f"map_{internal}" if internal in REQUIRED_COLS else f"optional_map_{internal}"
        choice = st.session_state.get(state_key)
        if choice in allowed_choices:
            col_map[internal] = None if choice == "-- not present --" else str(choice)
    return col_map


def clean_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(r"[€$%\s]", "", regex=True)
        .str.replace(",", "", regex=False)
    )
    cleaned = cleaned.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "-": pd.NA})
    return pd.to_numeric(cleaned, errors="coerce")


@st.cache_data(show_spinner=False)
def load_excel(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(file_bytes))
    df.columns = [str(col).strip() for col in df.columns]
    return df


def normalized_kpi_scores(row: pd.Series, rules: dict[str, float | str]) -> list[tuple[float, float]]:
    scores: list[tuple[float, float]] = []

    delivery = row.get("Delivery", row.get(COL_DELIVERY))
    delivery_target = float(rules["delivery_target"])
    if pd.notna(delivery) and delivery_target > 0:
        scores.append((min((delivery / delivery_target) * 100.0, 100.0), float(rules["weight_delivery"])))

    quality = row.get("Quality", row.get(COL_QUALITY))
    quality_target = float(rules["quality_target"])
    if pd.notna(quality) and quality_target > 0:
        scores.append((min((quality / quality_target) * 100.0, 100.0), float(rules["weight_quality"])))

    def lower_is_better_score(actual: float, limit: float) -> float:
        if actual <= limit:
            return 100.0
        overrun_ratio = (actual - limit) / limit
        return max(0.0, 100.0 - overrun_ratio * 100.0)

    complaint = row.get("Complaint", row.get(COL_COMPLAINT))
    complaint_limit = float(rules["complaint_limit"])
    if pd.notna(complaint) and complaint_limit > 0:
        scores.append((lower_is_better_score(float(complaint), complaint_limit), float(rules["weight_complaint"])))

    leadtime = row.get("LeadTime", row.get(COL_LEADTIME))
    leadtime_limit = float(rules["leadtime_limit"])
    if pd.notna(leadtime) and leadtime_limit > 0:
        scores.append((lower_is_better_score(float(leadtime), leadtime_limit), float(rules["weight_leadtime"])))

    price_volatility = row.get("PriceVolatility", row.get(COL_PRICE_VOL))
    price_threshold = float(rules["price_dev_tolerance"])
    if pd.notna(price_volatility) and price_threshold > 0:
        scores.append((lower_is_better_score(float(price_volatility), price_threshold), float(rules["weight_price"])))
    else:
        price_savings = row.get("PriceSaving", row.get(COL_PRICE_DEV))
        if pd.notna(price_savings) and price_threshold > 0:
            scores.append((max(0.0, min((price_savings / price_threshold) * 100.0, 100.0)), float(rules["weight_price"])))

    return scores


def calc_score(row: pd.Series, rules: dict[str, float | str]) -> float:
    kpi_scores = normalized_kpi_scores(row, rules)
    if not kpi_scores:
        return float("nan")

    total_weight = sum(weight for _, weight in kpi_scores)
    if total_weight <= 0:
        return float("nan")
    score = sum(kpi_score * weight for kpi_score, weight in kpi_scores) / total_weight

    delivery = row.get("Delivery", row.get(COL_DELIVERY))
    quality = row.get("Quality", row.get(COL_QUALITY))
    complaint = row.get("Complaint", row.get(COL_COMPLAINT))
    if pd.notna(delivery) and delivery < float(rules["penalty_delivery_cutoff"]):
        score -= float(rules["penalty_delivery_points"])
    if pd.notna(quality) and quality < float(rules["penalty_quality_cutoff"]):
        score -= float(rules["penalty_quality_points"])
    if pd.notna(complaint) and complaint > float(rules["penalty_complaint_cutoff"]):
        score -= float(rules["penalty_complaint_points"])

    return float(max(0.0, min(100.0, round(score, 1))))


def score_kpi_count(row: pd.Series, rules: dict[str, float | str]) -> int:
    return len(normalized_kpi_scores(row, rules))


def risk_label(score: float) -> str:
    if pd.isna(score):
        return "High"
    low_threshold = float(st.session_state["risk_low_threshold"])
    medium_threshold = min(float(st.session_state["risk_medium_threshold"]), low_threshold)
    if score >= low_threshold:
        return "Low"
    if score >= medium_threshold:
        return "Medium"
    return "High"


def risk_html(risk: str) -> str:
    css = {"Low": "status-low", "Medium": "status-medium", "High": "status-high"}.get(risk, "status-medium")
    return f'<span class="{css}">{html.escape(risk)}</span>'


def score_color(score: float) -> str:
    if pd.isna(score):
        return "#8b949e"
    low_threshold = float(st.session_state["risk_low_threshold"])
    medium_threshold = min(float(st.session_state["risk_medium_threshold"]), low_threshold)
    if score >= low_threshold:
        return "#3fb950"
    if score >= medium_threshold:
        return "#d29922"
    return "#f85149"


def component_score_color(score: float) -> str:
    if pd.isna(score):
        return "#8b949e"
    if score >= 80:
        return "#3fb950"
    if score >= 50:
        return "#d29922"
    return "#f85149"


def lower_is_better_component_score(actual: float, limit: float) -> float:
    if limit <= 0:
        return float("nan")
    if actual <= limit:
        return 100.0
    overrun_ratio = (actual - limit) / limit
    return max(0.0, 100.0 - overrun_ratio * 100.0)


def higher_is_better_component_score(actual: float, target: float) -> float:
    if target <= 0:
        return float("nan")
    return max(0.0, min((actual / target) * 100.0, 100.0))


def supplier_kpi_ring_html(row: pd.Series, rules: dict[str, float | str]) -> str:
    price_volatility = row.get("PriceVolatility", row.get(COL_PRICE_VOL))
    if pd.notna(price_volatility):
        price_item = (
            "Price Volatility",
            price_volatility,
            lambda value: lower_is_better_component_score(value, float(rules["price_dev_tolerance"])),
            float(rules["price_dev_tolerance"]),
            "lower",
            "%",
            2,
            lambda value: fmt_num(value, "%", 2),
        )
    else:
        price_item = (
            "Savings",
            row.get("PriceSaving", row.get(COL_PRICE_DEV)),
            lambda value: higher_is_better_component_score(value, float(rules["price_dev_tolerance"])),
            float(rules["price_dev_tolerance"]),
            "higher",
            "%",
            2,
            lambda value: "N/A" if pd.isna(value) else f"{value:+.2f}%",
        )

    items = [
        (
            "Delivery",
            row.get("Delivery", row.get(COL_DELIVERY)),
            lambda value: higher_is_better_component_score(value, float(rules["delivery_target"])),
            float(rules["delivery_target"]),
            "higher",
            "%",
            1,
            lambda value: fmt_num(value, "%", 1),
        ),
        (
            "Quality",
            row.get("Quality", row.get(COL_QUALITY)),
            lambda value: higher_is_better_component_score(value, float(rules["quality_target"])),
            float(rules["quality_target"]),
            "higher",
            "%",
            1,
            lambda value: fmt_num(value, "%", 1),
        ),
        (
            "Lead Time",
            row.get("LeadTime", row.get(COL_LEADTIME)),
            lambda value: lower_is_better_component_score(value, float(rules["leadtime_limit"])),
            float(rules["leadtime_limit"]),
            "lower",
            "d",
            1,
            lambda value: fmt_num(value, "d", 1),
        ),
        (
            "Complaints",
            row.get("Complaint", row.get(COL_COMPLAINT)),
            lambda value: lower_is_better_component_score(value, float(rules["complaint_limit"])),
            float(rules["complaint_limit"]),
            "lower",
            "%",
            2,
            lambda value: fmt_num(value, "%", 2),
        ),
        price_item,
    ]

    cards = []
    for label, raw_value, scorer, target, direction, suffix, decimals, formatter in items:
        if pd.isna(raw_value):
            score = float("nan")
            ring_value = "0%"
            ring_text = "N/A"
            detail = "No data"
        else:
            value = float(raw_value)
            score = scorer(value)
            safe_score = 0 if pd.isna(score) else int(round(max(0.0, min(100.0, score))))
            gap = value - target if direction == "higher" else target - value
            ring_value = f"{safe_score}%"
            ring_text = f"{gap:+.{decimals}f}{suffix}"
            detail = f"Actual {formatter(value)} | Target {fmt_num(target, suffix, decimals)}"

        cards.append(
            f"""
<div class="kpi-ring-card">
  <div class="kpi-ring" style="--ring-value:{ring_value};--ring-color:{component_score_color(score)};"><span>{html.escape(ring_text)}</span></div>
  <div class="kpi-ring-label">{html.escape(label)}</div>
  <div class="kpi-ring-detail">{html.escape(detail)}</div>
</div>
"""
        )
    return '<div class="kpi-ring-grid">' + "".join(cards) + "</div>"


def initials(name: str) -> str:
    parts = str(name).strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return str(name).strip()[:2].upper() or "?"


def fmt_num(value: float, suffix: str = "", decimals: int = 1) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:.{decimals}f}{suffix}"


def fmt_spend(value: float) -> str:
    if pd.isna(value) or value <= 0:
        return "N/A"
    if value >= 1_000_000:
        return f"€{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"€{value / 1_000:.0f}k"
    return f"€{value:.0f}"


def fmt_spend(value: float) -> str:
    if pd.isna(value) or value <= 0:
        return "N/A"
    if value >= 1_000_000:
        return f"EUR {value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"EUR {value / 1_000:.0f}k"
    return f"EUR {value:.0f}"


def price_signal(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    if value > 0:
        return f"+{value:.2f}%"
    return f"{value:.2f}%"


def year_span_label(years: int) -> str:
    if years <= 0:
        return "current filter"
    if years == 1:
        return "1 year"
    return f"{years} years"


def plotly_theme(height: int = 320) -> dict:
    return {
        "height": height,
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#c9d1d9", "size": 11},
        "margin": {"t": 25, "b": 45, "l": 45, "r": 18},
        "xaxis": {"gridcolor": "#21262d", "linecolor": "#30363d", "zerolinecolor": "#30363d"},
        "yaxis": {"gridcolor": "#21262d", "linecolor": "#30363d", "zerolinecolor": "#30363d"},
        "legend": {"font": {"color": "#c9d1d9", "size": 10}, "title_font": {"size": 11}},
    }


RISK_COLORS = {"Low": "#3fb950", "Medium": "#d29922", "High": "#f85149"}
PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


def issue_list(row: pd.Series, rules: dict[str, float | str]) -> list[str]:
    issues = []
    kpi_count = row.get("Score_KPI_Count")
    if pd.notna(kpi_count) and kpi_count < 3:
        issues.append(f"Limited KPI coverage ({int(kpi_count)} KPI used)")
    delivery = row.get("Delivery")
    if pd.notna(delivery) and delivery < float(rules["delivery_threshold"]):
        issues.append(f"Delivery below threshold ({delivery:.1f}%)")
    quality = row.get("Quality")
    if pd.notna(quality) and quality < float(rules["quality_threshold"]):
        issues.append(f"Quality below threshold ({quality:.1f}%)")
    leadtime = row.get("LeadTime")
    if pd.notna(leadtime) and leadtime > float(rules["leadtime_threshold"]):
        issues.append(f"Lead time above threshold ({leadtime:.1f} days)")
    complaint = row.get("Complaint")
    if pd.notna(complaint) and complaint > float(rules["complaint_threshold"]):
        issues.append(f"Complaint rate above limit ({complaint:.1f}%)")
    price_savings = row.get("PriceSaving")
    if pd.notna(price_savings) and price_savings < float(rules["price_threshold"]):
        issues.append(f"Price savings below target ({price_savings:+.1f}%)")
    return issues


def issue_chips(issues: list[str]) -> str:
    if not issues:
        return '<div class="chip-row"><span class="kpi-chip amber" title="No KPI breach">Clear</span></div>'
    chips = []
    for issue in issues:
        label = issue.split(" ", 2)[0]
        chips.append(f'<span class="kpi-chip" title="{html.escape(issue)}">{html.escape(label)}</span>')
    return '<div class="chip-row">' + "".join(chips) + "</div>"


def issue_summary(issues: list[str]) -> str:
    if not issues:
        return '<span class="issue-summary clear" title="No KPI breach">Clear</span>'
    detail = " | ".join(issues)
    count = len(issues)
    label = f"{count} KPI breach" if count == 1 else f"{count} KPI breaches"
    return f'<span class="issue-summary" title="{html.escape(detail)}">{html.escape(label)}</span>'


def issue_category(issue: str) -> str:
    issue_lower = issue.lower()
    if "limited" in issue_lower:
        return "Limited data"
    if "delivery" in issue_lower:
        return "Delivery"
    if "quality" in issue_lower:
        return "Quality"
    if "lead" in issue_lower:
        return "Lead time"
    if "complaint" in issue_lower:
        return "Complaints"
    if "price" in issue_lower:
        return "Price"
    return "Other"


def main_issue_text(issues: list[str]) -> str:
    categories = [issue_category(issue) for issue in issues if issue_category(issue) != "Limited data"]
    if not categories:
        categories = [issue_category(issue) for issue in issues]
    if not categories:
        return "No active anomaly"
    ordered = ["Delivery", "Lead time", "Quality", "Complaints", "Price", "Limited data", "Other"]
    categories = sorted(set(categories), key=lambda item: ordered.index(item) if item in ordered else len(ordered))
    if len(categories) == 1:
        return categories[0]
    return " + ".join(categories[:2])


def recommended_action(issues: list[str]) -> str:
    categories = {issue_category(issue) for issue in issues}
    if "Complaints" in categories or "Quality" in categories:
        return "Start quality review"
    if "Lead time" in categories or "Delivery" in categories:
        return "Request delivery recovery plan"
    if "Price" in categories:
        return "Review price / contract"
    if "Limited data" in categories:
        return "Add KPI coverage"
    return "Monitor supplier"


ISSUE_STATUSES = ("Cancelled", "Pending", "Partially Delivered")


def build_issue_diagnostics(source_df: pd.DataFrame) -> pd.DataFrame:
    status_col = None
    if COL_ORDER_STATUS in source_df.columns:
        status_col = COL_ORDER_STATUS
    elif COL_STATUS in source_df.columns:
        status_values = source_df[COL_STATUS].astype("string").str.strip()
        if status_values.isin(ISSUE_STATUSES).any():
            status_col = COL_STATUS
    if status_col is None or COL_SUPPLIER not in source_df.columns or COL_CATEGORY not in source_df.columns:
        return pd.DataFrame()

    diag = source_df[[COL_SUPPLIER, COL_CATEGORY, status_col]].copy()
    diag = diag.dropna(subset=[COL_SUPPLIER, COL_CATEGORY])
    if diag.empty:
        return pd.DataFrame()

    diag["Is_Issue"] = diag[status_col].astype("string").str.strip().isin(ISSUE_STATUSES)
    overall_issue_rate = float(diag["Is_Issue"].mean() * 100.0)

    supplier_issue_rate = (
        diag.groupby(COL_SUPPLIER, as_index=False)["Is_Issue"]
        .mean()
        .rename(columns={"Is_Issue": "Supplier_Issue_Rate_%"})
    )
    supplier_issue_rate["Supplier_Issue_Rate_%"] *= 100.0

    category_issue_rate = (
        diag.groupby(COL_CATEGORY, as_index=False)["Is_Issue"]
        .mean()
        .rename(columns={"Is_Issue": "Category_Issue_Rate_%"})
    )
    category_issue_rate["Category_Issue_Rate_%"] *= 100.0

    combo = (
        diag.groupby([COL_SUPPLIER, COL_CATEGORY], as_index=False)["Is_Issue"]
        .mean()
        .rename(columns={"Is_Issue": "Combo_Issue_Rate_%"})
    )
    combo["Combo_Issue_Rate_%"] *= 100.0
    combo = combo.merge(supplier_issue_rate, on=COL_SUPPLIER, how="left")
    combo = combo.merge(category_issue_rate, on=COL_CATEGORY, how="left")
    combo["Overall_Issue_Rate_%"] = overall_issue_rate

    def diagnose(row: pd.Series) -> str:
        combo_rate = float(row["Combo_Issue_Rate_%"])
        supplier_rate = float(row["Supplier_Issue_Rate_%"])
        category_rate = float(row["Category_Issue_Rate_%"])
        overall_rate = float(row["Overall_Issue_Rate_%"])
        if combo_rate > supplier_rate + 10 and combo_rate > category_rate + 10:
            return "Supplier+Category combination issue"
        if supplier_rate > overall_rate + 10 and category_rate <= overall_rate + 10:
            return "Supplier-wide issue"
        if category_rate > overall_rate + 10 and supplier_rate <= overall_rate + 10:
            return "Category-wide issue"
        if combo_rate <= overall_rate + 5:
            return "No significant issue"
        return "Mixed / unclear"

    combo["Diagnosis"] = combo.apply(diagnose, axis=1)
    percentage_cols = [
        "Combo_Issue_Rate_%",
        "Supplier_Issue_Rate_%",
        "Category_Issue_Rate_%",
        "Overall_Issue_Rate_%",
    ]
    combo[percentage_cols] = combo[percentage_cols].round(1)
    return combo


def diagnosis_badge(diagnosis: str) -> str:
    if diagnosis == "No significant issue":
        css = "status-low"
    elif diagnosis == "Supplier+Category combination issue":
        css = "status-high"
    else:
        css = "status-medium"
    return f'<span class="{css}">{html.escape(diagnosis)}</span>'


def severity_badge(anomaly_count: int, risk: str) -> str:
    if anomaly_count >= 4 or risk == "High":
        return '<span class="severity-pill severity-critical">Critical</span>'
    if anomaly_count >= 2 or risk == "Medium":
        return '<span class="severity-pill severity-warning">Warning</span>'
    return '<span class="severity-pill severity-watch">Watch</span>'


def clear_uploaded_file() -> None:
    st.session_state.pop("uploaded_file_bytes", None)
    st.session_state.pop("uploaded_file_name", None)


# ---------------------------------------------------------------------------
# Sidebar, upload, settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="logo-box">SupplierDash</div>', unsafe_allow_html=True)
    page_options = [
        "Overview",
        "Suppliers",
        "Performance",
        "Anomalies",
        "Issue Diagnostics",
        "Scorecards",
        "Spend Analysis",
        "Category Insights",
        "Trends",
        "Settings",
    ]
    st.markdown('<div class="side-title">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("Navigation", page_options, label_visibility="collapsed", key="page_nav")
    st.markdown('<div class="file-panel"><div class="file-panel-title">Data File</div>', unsafe_allow_html=True)
    if "uploaded_file_bytes" in st.session_state:
        file_name = st.session_state.get("uploaded_file_name", "supplier data")
        file_size = len(st.session_state.get("uploaded_file_bytes", b"")) / 1024
        st.markdown(
            f"""
<div class="file-chip">
  <div class="file-chip-icon">XL</div>
  <div style="min-width:0;">
    <div class="file-chip-name">{html.escape(str(file_name))}</div>
    <div class="file-chip-note">{file_size:.1f} KB loaded</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    else:
        st.caption("No Excel file loaded.")

    sidebar_file = st.file_uploader(
        "Add or replace Excel file",
        type=["xlsx", "xls"],
        key="sidebar_file_upload",
        label_visibility="collapsed",
    )
    if sidebar_file is not None:
        new_file_bytes = sidebar_file.getvalue()
        if new_file_bytes != st.session_state.get("uploaded_file_bytes"):
            st.session_state["uploaded_file_bytes"] = new_file_bytes
            st.session_state["uploaded_file_name"] = sidebar_file.name
            st.rerun()

    if "uploaded_file_bytes" in st.session_state:
        st.button("Remove file", on_click=clear_uploaded_file, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

previous_page = st.session_state.get("_previous_page_nav", page)
previous_index = page_options.index(previous_page) if previous_page in page_options else page_options.index(page)
current_index = page_options.index(page)
if current_index > previous_index:
    nav_start_y = "58px"
    nav_duration = ".82s"
elif current_index < previous_index:
    nav_start_y = "-58px"
    nav_duration = ".82s"
else:
    nav_start_y = "12px"
    nav_duration = ".42s"
st.session_state["_previous_page_nav"] = page

st.markdown(
    f"""
<style>
:root {{
    --nav-start-y: {nav_start_y};
    --nav-duration: {nav_duration};
}}
</style>
""",
    unsafe_allow_html=True,
)

now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
st.markdown(
    f"""
<div class="top-bar">
  <div>
    <div class="top-title">Supplier Performance Dashboard</div>
    <div class="top-sub">Real-time supplier KPI monitoring and anomaly detection</div>
  </div>
  <div style="font-size:.78rem;color:#8b949e;">{now_str}</div>
</div>
""",
    unsafe_allow_html=True,
)

if "uploaded_file_bytes" not in st.session_state:
    upload_col, note_col = st.columns([1.4, 4.8])
    with upload_col:
        uploaded_file = st.file_uploader("Upload supplier Excel", type=["xlsx", "xls"], label_visibility="collapsed")
    with note_col:
        st.caption("Upload your supplier KPI Excel file. Columns can be in any order and can be mapped manually if needed.")
    if uploaded_file is not None:
        st.session_state["uploaded_file_bytes"] = uploaded_file.getvalue()
        st.session_state["uploaded_file_name"] = uploaded_file.name
        st.rerun()


def render_settings(
    raw_data: pd.DataFrame | None = None,
    clean_data: pd.DataFrame | None = None,
    quality_report: list[str] | None = None,
    col_map: dict[str, str | None] | None = None,
) -> None:
    st.markdown('<div class="s-card"><div class="s-card-title">Dashboard Settings</div>', unsafe_allow_html=True)
    st.caption("These settings control KPI cards, anomaly detection, risk scoring, and supplier table display.")

    st.markdown(
        """
<div style="background:rgba(88,166,255,.08);border:1px solid rgba(88,166,255,.22);border-radius:12px;padding:.85rem 1rem;margin:.75rem 0 1rem;">
  <div style="font-weight:950;color:#f0f6fc;margin-bottom:.25rem;">Scoring Summary</div>
  <div style="color:#8b949e;font-size:.82rem;line-height:1.55;">
    Final score = weighted KPI score - hard penalties. Missing KPI values are ignored and the remaining available KPI weights are redistributed.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if clean_data is not None:
        baseline_parts = []
        baseline_specs = [
            ("Delivery target", "Delivery", "%", 1),
            ("Quality target", "Quality", "%", 1),
            ("Lead time limit", "LeadTime", " days", 1),
            ("Complaint limit", "Complaint", "%", 2),
            ("Price savings target", "PriceSaving", "%", 2),
        ]
        for label, col, suffix, decimals in baseline_specs:
            if col in clean_data.columns and clean_data[col].notna().any():
                value = clean_data[col].mean()
                baseline_parts.append(
                    f"<div><span>{html.escape(label)}</span><b>{value:.{decimals}f}{suffix}</b></div>"
                )
        if baseline_parts:
            st.markdown(
                f"""
<div class="s-card" style="padding:.85rem 1rem;margin-bottom:1rem;">
  <div class="s-card-title" style="margin-bottom:.35rem;">Current Data Averages</div>
  <div class="kpi-muted" style="margin-bottom:.65rem;">Use these as relaxed baseline settings if you want the dashboard to compare suppliers against your current dataset average.</div>
  <div class="category-card-metrics" style="grid-template-columns:repeat(5,minmax(100px,1fr));margin-top:0;">
    {''.join(baseline_parts)}
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### KPI Targets")
        st.slider("Delivery target (%)", 50.0, 100.0, step=0.5, key="delivery_target")
        st.slider("Quality target (%)", 50.0, 100.0, step=0.5, key="quality_target")
        st.slider("Lead time limit (days)", 1.0, 60.0, step=0.5, key="leadtime_limit")
        st.slider("Complaint rate limit (%)", 0.0, 20.0, step=0.1, key="complaint_limit")
        st.slider("Price savings target (%)", 0.0, 25.0, step=0.1, key="price_dev_tolerance")
        st.markdown("#### Score Weights (%)")
        w1, w2 = st.columns([1.7, 1])
        with w1:
            st.caption("Delivery weight")
        with w2:
            st.number_input("Delivery weight", 0.0, 100.0, step=1.0, key="weight_delivery", label_visibility="collapsed")
        w3, w4 = st.columns([1.7, 1])
        with w3:
            st.caption("Quality weight")
        with w4:
            st.number_input("Quality weight", 0.0, 100.0, step=1.0, key="weight_quality", label_visibility="collapsed")
        w5, w6 = st.columns([1.7, 1])
        with w5:
            st.caption("Complaint weight")
        with w6:
            st.number_input("Complaint weight", 0.0, 100.0, step=1.0, key="weight_complaint", label_visibility="collapsed")
        w7, w8 = st.columns([1.7, 1])
        with w7:
            st.caption("Lead time weight")
        with w8:
            st.number_input("Lead time weight", 0.0, 100.0, step=1.0, key="weight_leadtime", label_visibility="collapsed")
        w9, w10 = st.columns([1.7, 1])
        with w9:
            st.caption("Price savings weight")
        with w10:
            st.number_input("Price savings weight", 0.0, 100.0, step=1.0, key="weight_price", label_visibility="collapsed")
        current_weight_total = (
            st.session_state["weight_delivery"]
            + st.session_state["weight_quality"]
            + st.session_state["weight_complaint"]
            + st.session_state["weight_leadtime"]
            + st.session_state["weight_price"]
        )
        st.caption("Weights should total 100%. Missing KPIs are ignored and remaining weights are redistributed.")
        st.markdown(f"**Total weight: {current_weight_total:.0f}%**")
        if current_weight_total == 100:
            st.success("Good: weights total 100%.")
        elif current_weight_total < 100:
            st.warning(f"Add {100 - current_weight_total:.0f}% more to reach 100%.")
        else:
            st.error(f"Reduce {current_weight_total - 100:.0f}% to reach 100%.")
    with c2:
        st.markdown("#### Anomaly & Display")
        st.slider("Top supplier table rows", 5, 50, step=1, key="top_supplier_rows")
        st.markdown("#### Risk Thresholds")
        st.caption("These thresholds convert the final score into Low, Medium, or High risk.")
        r1, r2 = st.columns(2)
        with r1:
            st.number_input("Low risk from", 0.0, 100.0, step=1.0, key="risk_low_threshold")
        with r2:
            st.number_input("Medium risk from", 0.0, 100.0, step=1.0, key="risk_medium_threshold")
        st.caption(
            f"Low >= {st.session_state['risk_low_threshold']:.0f}, "
            f"Medium >= {st.session_state['risk_medium_threshold']:.0f}, "
            f"High < {st.session_state['risk_medium_threshold']:.0f}"
        )
        st.markdown("#### Reset")
        st.button("Reset all settings to default", on_click=reset_settings)

    with st.expander("Advanced Scoring Penalties", expanded=False):
        st.caption("Extra score deductions for serious KPI problems. Use these only when a KPI failure should pull the final score down even if other KPIs are healthy.")

        p1, p2 = st.columns(2)
        with p1:
            st.number_input("Delivery below", 0.0, 100.0, step=0.5, key="penalty_delivery_cutoff")
        with p2:
            st.number_input("Subtract delivery points", 0.0, 50.0, step=1.0, key="penalty_delivery_points")
        st.caption(
            f"If delivery is below {st.session_state['penalty_delivery_cutoff']:.1f}%, "
            f"subtract {st.session_state['penalty_delivery_points']:.0f} points."
        )

        p3, p4 = st.columns(2)
        with p3:
            st.number_input("Quality below", 0.0, 100.0, step=0.5, key="penalty_quality_cutoff")
        with p4:
            st.number_input("Subtract quality points", 0.0, 50.0, step=1.0, key="penalty_quality_points")
        st.caption(
            f"If quality is below {st.session_state['penalty_quality_cutoff']:.1f}%, "
            f"subtract {st.session_state['penalty_quality_points']:.0f} points."
        )

        p5, p6 = st.columns(2)
        with p5:
            st.number_input("Complaints above", 0.0, 30.0, step=0.5, key="penalty_complaint_cutoff")
        with p6:
            st.number_input("Subtract complaint points", 0.0, 50.0, step=1.0, key="penalty_complaint_points")
        st.caption(
            f"If complaints are above {st.session_state['penalty_complaint_cutoff']:.1f}%, "
            f"subtract {st.session_state['penalty_complaint_points']:.0f} points."
        )

    rules = get_effective_rules()
    total_weight = sum(
        float(rules[key])
        for key in ["weight_delivery", "weight_quality", "weight_complaint", "weight_leadtime", "weight_price"]
    )
    if total_weight <= 0:
        st.warning("All score weights are 0. Supplier scores will be N/A until at least one weight is above 0.")
    if float(rules["risk_medium_threshold"]) > float(rules["risk_low_threshold"]):
        st.warning("Medium risk threshold is above Low risk threshold. The app will cap Medium at the Low threshold during scoring.")
    st.markdown("#### Effective Anomaly Thresholds")
    st.dataframe(
        pd.DataFrame(
            {
                "Rule": [
                    "Delivery alert if below",
                    "Quality alert if below",
                    "Lead time alert if above",
                    "Complaint rate alert if above",
                    "Price savings alert if below",
                ],
                "Effective Threshold": [
                    f"{float(rules['delivery_threshold']):.1f}%",
                    f"{float(rules['quality_threshold']):.1f}%",
                    f"{float(rules['leadtime_threshold']):.1f} days",
                    f"{float(rules['complaint_threshold']):.2f}%",
                    f"{float(rules['price_threshold']):.2f}%",
                ],
            }
        ),
        width="stretch",
        hide_index=True,
    )
    if raw_data is not None:
        st.markdown("#### Data Quality Overview")
        a, b, c, d = st.columns(4)
        a.metric("Uploaded Rows", len(raw_data))
        b.metric("Valid Rows Used", len(clean_data) if clean_data is not None else 0)
        c.metric("Columns Detected", len(raw_data.columns))
        d.metric("Missing Values", int(raw_data.isna().sum().sum()))
        if col_map is not None:
            st.markdown("#### Column Mapping")
            st.caption("Review the current auto-detected columns or choose them manually here. If a required column is missing, the app will still prompt for manual mapping automatically.")
            with st.expander("Review or update mapped columns", expanded=False):
                file_cols = ["-- not present --"] + raw_data.columns.astype(str).tolist()
                mapping_cols = [
                    COL_SUPPLIER,
                    COL_CATEGORY,
                    COL_DATE,
                    COL_STATUS,
                    *KPI_COLS,
                    COL_SPEND,
                    COL_UNIT_PRICE,
                    COL_PRICE_VOL,
                    COL_TOTAL_SHIP,
                    COL_ONTIME_SHIP,
                ]
                for internal in mapping_cols:
                    state_key = f"map_{internal}" if internal in REQUIRED_COLS else f"optional_map_{internal}"
                    current = st.session_state.get(state_key, col_map.get(internal))
                    if current not in file_cols:
                        current = "-- not present --"
                    idx = file_cols.index(current) if current in file_cols else 0
                    label = "Order_Status" if internal == COL_STATUS else internal
                    st.selectbox(f"Column for {label}", file_cols, index=idx, key=state_key)
        if quality_report:
            for msg in quality_report:
                st.warning(msg)
    st.markdown("</div>", unsafe_allow_html=True)


if "uploaded_file_bytes" not in st.session_state:
    if page == "Settings":
        render_settings()
    else:
        st.markdown(
            """
<div class="s-card" style="max-width:760px;margin:55px auto;">
  <div class="s-card-title">Upload your supplier data</div>
  <div style="color:#8b949e;line-height:1.6;">
    Required column: Supplier Name. Add any available KPI columns such as Delivery Performance %,
    Lead Time Days, Quality Score %, Complaint Rate %, or Price Savings % to calculate scores.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    st.stop()


# ---------------------------------------------------------------------------
# Load and process
# ---------------------------------------------------------------------------
raw = load_excel(st.session_state["uploaded_file_bytes"])
if raw.empty:
    st.error("The Excel file is empty.")
    st.stop()

col_map = auto_detect_columns(raw)
col_map = apply_session_column_mapping_overrides(col_map, raw.columns.astype(str).tolist())
missing_required = [col for col in REQUIRED_COLS if col_map.get(col) is None]

can_derive_delivery = (
    col_map.get(COL_DELIVERY) is None
    and col_map.get(COL_TOTAL_SHIP) is not None
    and col_map.get(COL_ONTIME_SHIP) is not None
)

if missing_required:
    st.warning("Supplier name could not be auto-detected. Map it manually below.")
    with st.expander("Manual Column Mapping", expanded=True):
        file_cols = ["-- not present --"] + raw.columns.astype(str).tolist()
        for internal in REQUIRED_COLS:
            current = col_map.get(internal)
            idx = file_cols.index(current) if current in file_cols else 0
            choice = st.selectbox(f"Column for {internal}", file_cols, index=idx, key=f"map_{internal}")
            col_map[internal] = None if choice == "-- not present --" else choice
    still_missing = [col for col in REQUIRED_COLS if col_map.get(col) is None]
    if still_missing:
        st.error("Still missing: " + ", ".join(still_missing) + ". The dashboard cannot run without these columns.")
        st.stop()

rename_map = {actual: internal for internal, actual in col_map.items() if actual is not None}
df = raw.rename(columns=rename_map).copy()
quality_report: list[str] = []

if COL_STATUS in df.columns:
    df[COL_ORDER_STATUS] = df[COL_STATUS].where(df[COL_STATUS].notna(), pd.NA).astype("string").str.strip()

for col in NUMERIC_COLS:
    if col in df.columns:
        before = df[col].notna().sum()
        df[col] = clean_numeric(df[col])
        invalid = int(before - df[col].notna().sum())
        if invalid > 0:
            quality_report.append(f"{col}: {invalid} invalid numeric value(s) were ignored.")

if COL_DATE in df.columns:
    before_dates = df[COL_DATE].notna().sum()
    df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors="coerce", dayfirst=True)
    invalid_dates = int(before_dates - df[COL_DATE].notna().sum())
    if invalid_dates > 0:
        quality_report.append(f"{COL_DATE}: {invalid_dates} invalid date value(s) were ignored for trends.")

if COL_DELIVERY not in df.columns and can_derive_delivery:
    df[COL_DELIVERY] = (df[COL_ONTIME_SHIP] / df[COL_TOTAL_SHIP] * 100).round(1)
    quality_report.append("Delivery_Performance_% was derived from On_Time_Shipments / Total_Shipments.")

if COL_CATEGORY not in df.columns:
    df[COL_CATEGORY] = "Uncategorized"
else:
    df[COL_CATEGORY] = df[COL_CATEGORY].fillna("Uncategorized").replace("", "Uncategorized")

if COL_ORDER_STATUS in df.columns and COL_LEADTIME in df.columns and df[COL_LEADTIME].notna().any():
    category_median_leadtime = df.groupby(COL_CATEGORY)[COL_LEADTIME].median()
    median_leadtime = df[COL_CATEGORY].map(category_median_leadtime)
    status_text = df[COL_ORDER_STATUS].astype("string").str.strip()
    comparable = df[COL_LEADTIME].notna() & median_leadtime.notna()

    df["Delivery_Performance_Median_%"] = pd.Series(float("nan"), index=df.index, dtype="float64")
    df.loc[status_text.isin(("Cancelled", "Pending")), "Delivery_Performance_Median_%"] = 0.0

    partial = status_text.eq("Partially Delivered").fillna(False) & comparable
    delivered = status_text.eq("Delivered").fillna(False) & comparable
    on_or_before_median = df[COL_LEADTIME] <= median_leadtime

    df.loc[partial & on_or_before_median, "Delivery_Performance_Median_%"] = 50.0
    df.loc[partial & ~on_or_before_median, "Delivery_Performance_Median_%"] = 0.0
    df.loc[delivered & on_or_before_median, "Delivery_Performance_Median_%"] = 100.0
    df.loc[delivered & ~on_or_before_median, "Delivery_Performance_Median_%"] = 0.0
    quality_report.append(
        "Delivery_Performance_Median_% was calculated using each order's lead time vs. the median lead time for its category."
    )

missing_kpis = [col for col in KPI_COLS if col not in df.columns]
if missing_kpis:
    for col in missing_kpis:
        df[col] = float("nan")
    quality_report.append("Missing KPI columns were ignored: " + ", ".join(missing_kpis) + ".")

rows_before = len(df)
df = df.dropna(subset=[COL_SUPPLIER]).copy()
df[COL_SUPPLIER] = df[COL_SUPPLIER].astype(str).str.strip()
df = df[df[COL_SUPPLIER] != ""].copy()
dropped = rows_before - len(df)
if dropped:
    quality_report.append(f"{dropped} row(s) were dropped because supplier name was missing.")
if df.empty:
    st.error("After cleaning, no valid supplier rows remain. Check the Supplier name column in your file.")
    st.stop()

df["Profile_Key"] = df[COL_SUPPLIER].astype(str) + " | " + df[COL_CATEGORY].astype(str)
df["Profile_Label"] = df[COL_SUPPLIER].astype(str) + " - " + df[COL_CATEGORY].astype(str)

for col, default in [(COL_SPEND, pd.NA), (COL_NOTES, ""), (COL_STATUS, "")]:
    if col not in df.columns:
        df[col] = default

if COL_ORDER_STATUS in df.columns:
    order_status_normalized = df[COL_ORDER_STATUS].astype("string").str.strip().str.lower()
    df["Score_Eligible"] = ~order_status_normalized.isin(["cancelled", "pending"])
else:
    df["Score_Eligible"] = True

excluded_from_scoring = int((~df["Score_Eligible"]).sum())
if excluded_from_scoring:
    quality_report.append(
        f"{excluded_from_scoring} Cancelled/Pending row(s) were excluded from KPI scoring but kept for issue diagnostics."
    )

df["Delivery"] = df[COL_DELIVERY].where(df["Score_Eligible"])
df["LeadTime"] = df[COL_LEADTIME].where(df["Score_Eligible"])
df["Quality"] = df[COL_QUALITY].where(df["Score_Eligible"])
df["Complaint"] = df[COL_COMPLAINT].where(df["Score_Eligible"])
df["PriceSaving"] = df[COL_PRICE_DEV].where(df["Score_Eligible"])

rules = get_effective_rules()
df[COL_SCORE] = df.apply(lambda row: calc_score(row, rules), axis=1)
df["Score_KPI_Count"] = df.apply(lambda row: score_kpi_count(row, rules), axis=1)
df["KPI_Coverage_%"] = (df["Score_KPI_Count"] / len(KPI_COLS) * 100.0).round(0)
no_valid_kpi_data = int(df["Score_KPI_Count"].max(skipna=True) or 0) == 0
df["Risk"] = df[COL_SCORE].apply(risk_label)
df["Status"] = df["Risk"].map({"Low": "Green / Good", "Medium": "Yellow / Monitor", "High": "Red / High Risk"})

df["Score"] = df[COL_SCORE]
df["Issues"] = df.apply(lambda row: issue_list(row, rules), axis=1)
df["Anomalies"] = df["Issues"].apply(len)
issue_diagnostics = build_issue_diagnostics(df)

agg = (
    df.groupby([COL_SUPPLIER, COL_CATEGORY], as_index=False)
    .agg(
        Delivery=("Delivery", "mean"),
        LeadTime=("LeadTime", "mean"),
        Quality=("Quality", "mean"),
        Complaint=("Complaint", "mean"),
        PriceSaving=("PriceSaving", "mean"),
        Score=("Score", "mean"),
        Score_KPI_Count=("Score_KPI_Count", "min"),
        KPI_Coverage=("KPI_Coverage_%", "min"),
        LeadTime_Std=("LeadTime", "std"),
        Scored_Orders=("Score_Eligible", "sum"),
        Total_Orders=("Score_Eligible", "size"),
        Spend=(COL_SPEND, "sum"),
        Anomalies=("Anomalies", "sum"),
    )
    .round(2)
)
agg["Category"] = agg[COL_CATEGORY]
agg["Profile_Key"] = agg[COL_SUPPLIER].astype(str) + " | " + agg["Category"].astype(str)
agg["Profile_Label"] = agg[COL_SUPPLIER].astype(str) + " - " + agg["Category"].astype(str)
agg["Risk"] = agg["Score"].apply(risk_label)
agg["Issues"] = agg.apply(lambda row: issue_list(row, rules), axis=1)
agg["LeadTime_Std"] = agg["LeadTime_Std"].fillna(0)
quality_gap = (100.0 - agg["Quality"]).clip(lower=0.1)
agg["Value_Index"] = (agg["PriceSaving"] / quality_gap).where(agg["PriceSaving"].notna() & agg["Quality"].notna())
category_avg_score = agg.groupby("Category")["Score"].transform("mean")
agg["Score_vs_Category_Avg"] = (agg["Score"] - category_avg_score).round(1)
HAS_SPEND = agg["Spend"].notna().any() and agg["Spend"].sum(skipna=True) > 0

if page == "Settings":
    render_settings(raw, df, quality_report, col_map)
    st.stop()

if no_valid_kpi_data:
    st.info("No KPI found for scoring. Add at least one KPI column such as Delivery, Quality, Lead Time, Complaint Rate, or Price Savings.")
    st.stop()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
f1, f2, f3 = st.columns([1.2, 1.2, 2.0])
with f1:
    sel_category = st.selectbox("Category", ["All Categories"] + sorted(agg["Category"].dropna().astype(str).unique()))
with f2:
    sel_risk = st.selectbox("Risk Level", ["All Risk Levels", "Low", "Medium", "High"])
with f3:
    search_q = st.text_input("Search suppliers", placeholder="Search suppliers...")

filt = agg.copy()
if sel_category != "All Categories":
    filt = filt[filt["Category"].astype(str) == sel_category]
if sel_risk != "All Risk Levels":
    filt = filt[filt["Risk"] == sel_risk]
if search_q.strip():
    filt = filt[filt[COL_SUPPLIER].astype(str).str.lower().str.contains(search_q.strip().lower(), na=False)]
filt = filt.reset_index(drop=True)

if filt.empty:
    st.warning("No suppliers match the selected filters.")
    st.stop()

profile_keys = filt["Profile_Key"].astype(str).tolist()
profile_labels = dict(zip(filt["Profile_Key"].astype(str), filt["Profile_Label"].astype(str)))
if "selected_profile_key" not in st.session_state or st.session_state["selected_profile_key"] not in profile_keys:
    st.session_state["selected_profile_key"] = profile_keys[0]
selected_row = filt[filt["Profile_Key"].astype(str) == st.session_state["selected_profile_key"]].iloc[0]


# ---------------------------------------------------------------------------
# Render blocks
# ---------------------------------------------------------------------------
def render_kpi_cards() -> None:
    avg_delivery = filt["Delivery"].mean()
    avg_lead = filt["LeadTime"].mean()
    avg_quality = filt["Quality"].mean()
    avg_complaint = filt["Complaint"].mean()
    active_suppliers = filt[COL_SUPPLIER].nunique()
    active_combinations = len(filt)
    flagged_suppliers = filt.loc[filt["Anomalies"] > 0, COL_SUPPLIER].nunique()
    anomaly_breaches = int(filt["Anomalies"].sum())
    detail_source = df[df["Profile_Key"].astype(str).isin(profile_keys)].copy()
    breach_years = (
        detail_source[COL_DATE].dropna().dt.year.nunique()
        if COL_DATE in detail_source.columns and detail_source[COL_DATE].notna().any()
        else 0
    )
    sel_score = float(selected_row["Score"])
    cards = []
    if pd.notna(avg_delivery):
        cards.append(
            f"""<div class="kpi-card"><div class="kpi-icon">DP</div><div><div class="kpi-label">On-Time Delivery %</div><div class="kpi-value">{avg_delivery:.1f}%</div><div class="kpi-scope">Overall avg - current filter</div><div class="{'kpi-good' if avg_delivery >= st.session_state['delivery_target'] else 'kpi-bad'}">{'meets' if avg_delivery >= st.session_state['delivery_target'] else 'below'} {st.session_state['delivery_target']:.1f}% target</div></div></div>"""
        )
    if pd.notna(avg_lead):
        cards.append(
            f"""<div class="kpi-card"><div class="kpi-icon">LT</div><div><div class="kpi-label">Avg Lead Time</div><div class="kpi-value">{avg_lead:.1f}d</div><div class="kpi-scope">Overall avg - current filter</div><div class="{'kpi-good' if avg_lead <= st.session_state['leadtime_limit'] else 'kpi-bad'}">{'within' if avg_lead <= st.session_state['leadtime_limit'] else 'above'} {st.session_state['leadtime_limit']:.1f}d target</div></div></div>"""
        )
    if pd.notna(avg_quality):
        cards.append(
            f"""<div class="kpi-card"><div class="kpi-icon">QS</div><div><div class="kpi-label">Quality Score</div><div class="kpi-value">{avg_quality:.1f}%</div><div class="kpi-scope">Overall avg - current filter</div><div class="{'kpi-good' if avg_quality >= st.session_state['quality_target'] else 'kpi-bad'}">{'meets' if avg_quality >= st.session_state['quality_target'] else 'below'} {st.session_state['quality_target']:.1f}% target</div></div></div>"""
        )
    if pd.notna(avg_complaint):
        cards.append(
            f"""<div class="kpi-card"><div class="kpi-icon">CR</div><div><div class="kpi-label">Complaint Rate</div><div class="kpi-value">{avg_complaint:.2f}%</div><div class="kpi-scope">Overall avg - current filter</div><div class="{'kpi-good' if avg_complaint <= st.session_state['complaint_limit'] else 'kpi-bad'}">{'within' if avg_complaint <= st.session_state['complaint_limit'] else 'above'} {st.session_state['complaint_limit']:.1f}% limit</div></div></div>"""
        )
    cards.extend(
        [
            f"""<div class="kpi-card"><div class="kpi-icon">SP</div><div><div class="kpi-label">Active Suppliers</div><div class="kpi-value">{active_suppliers}</div><div class="kpi-muted">{active_combinations} supplier-category profiles</div></div></div>""",
            f"""<div class="kpi-card"><div class="kpi-icon">AL</div><div><div class="kpi-label">Suppliers Flagged</div><div class="kpi-value">{flagged_suppliers}</div><div class="{'kpi-bad' if flagged_suppliers else 'kpi-good'}">{anomaly_breaches} KPI breaches over {year_span_label(int(breach_years))}</div></div></div>""",
            f"""<div class="kpi-card"><div class="kpi-icon">SS</div><div><div class="kpi-label">Selected Profile</div><div class="kpi-value" style="font-size:1.1rem;color:{score_color(sel_score)};">{fmt_num(sel_score, '/100', 0)}</div><div class="kpi-muted">{html.escape(str(selected_row['Profile_Label']))}</div></div></div>""",
        ]
    )
    st.markdown(
        '<div class="metric-grid">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


def render_health_snapshot() -> None:
    counts = filt["Risk"].value_counts()
    green = int(counts.get("Low", 0))
    yellow = int(counts.get("Medium", 0))
    red = int(counts.get("High", 0))
    total = max(1, green + yellow + red)
    snapshot_html = f"""
<div class="s-card">
  <div class="s-card-title">Supplier-Category Base Health</div>
  <div class="health-grid">
    <div class="health-card" style="--health-color:#3fb950;">
      <div class="health-label">Green / Low risk</div>
      <div class="health-value">{green}</div>
      <div class="health-note">{green / total * 100:.0f}% of profiles in current filter</div>
    </div>
    <div class="health-card" style="--health-color:#d29922;">
      <div class="health-label">Yellow / Monitor</div>
      <div class="health-value">{yellow}</div>
      <div class="health-note">{yellow / total * 100:.0f}% of profiles in current filter</div>
    </div>
    <div class="health-card" style="--health-color:#f85149;">
      <div class="health-label">Red / High risk</div>
      <div class="health-value">{red}</div>
      <div class="health-note">{red / total * 100:.0f}% of profiles in current filter</div>
    </div>
  </div>
  <div class="kpi-muted">Health is counted by supplier-category profile, matching the Top Suppliers table.</div>
</div>
"""
    st.markdown(snapshot_html, unsafe_allow_html=True)


def render_risk_movement() -> None:
    st.markdown('<div class="s-card"><div class="s-card-title">Supplier Risk Journey</div>', unsafe_allow_html=True)
    selected_key = st.selectbox(
        "View supplier-category profile",
        profile_keys,
        index=profile_keys.index(st.session_state["selected_profile_key"]),
        format_func=lambda key: profile_labels.get(str(key), str(key)),
        key="selected_profile_key",
    )
    if COL_DATE not in df.columns or df[COL_DATE].notna().sum() == 0:
        st.info("Add Period_Date to show how the selected supplier-category profile moves through risk bands over time.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    selected_key = str(selected_key)
    selected_label = profile_labels.get(selected_key, selected_key)
    source = df[df["Profile_Key"].astype(str) == selected_key].dropna(subset=[COL_DATE, "Score"]).copy()
    if source.empty:
        st.info("No monthly risk history is available for the selected supplier-category profile.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    source["Period_Month"] = source[COL_DATE].dt.to_period("M").dt.to_timestamp()
    monthly = (
        source.groupby("Period_Month", as_index=False)
        .agg(Score=("Score", "mean"))
        .sort_index()
    )
    monthly["Risk"] = monthly["Score"].apply(risk_label)
    monthly = monthly.sort_values("Period_Month").reset_index(drop=True)

    low_threshold = float(st.session_state["risk_low_threshold"])
    medium_threshold = min(float(st.session_state["risk_medium_threshold"]), low_threshold)
    latest = monthly.iloc[-1]
    if len(monthly) > 1:
        previous = monthly.iloc[-2]
        delta_score = float(latest["Score"]) - float(previous["Score"])
        delta_text = f"vs previous month: {delta_score:+.1f} score points"
    else:
        delta_text = "Only one month of risk history is available."

    st.markdown(
        f"""
<div style="display:flex;gap:.55rem;flex-wrap:wrap;margin:.1rem 0 .75rem;">
  <span class="severity-pill severity-watch">{html.escape(str(selected_label))}</span>
  {risk_html(str(latest["Risk"]))}
  <span class="trend-summary-chip">Latest score {float(latest["Score"]):.0f}/100</span>
  <span class="kpi-muted" style="align-self:center;font-weight:850;">{delta_text}</span>
</div>
""",
        unsafe_allow_html=True,
    )

    fig = go.Figure()
    fig.add_hrect(
        y0=low_threshold,
        y1=100,
        fillcolor="rgba(63,185,80,.12)",
        line_width=0,
        annotation_text="Green / Low risk",
        annotation_position="top left",
        annotation_font_color="#3fb950",
    )
    fig.add_hrect(
        y0=medium_threshold,
        y1=low_threshold,
        fillcolor="rgba(210,153,34,.12)",
        line_width=0,
        annotation_text="Yellow / Monitor",
        annotation_position="top left",
        annotation_font_color="#d29922",
    )
    fig.add_hrect(
        y0=0,
        y1=medium_threshold,
        fillcolor="rgba(248,81,73,.10)",
        line_width=0,
        annotation_text="Red / Immediate action",
        annotation_position="bottom left",
        annotation_font_color="#f85149",
    )
    fig.add_trace(
        go.Scatter(
            x=monthly["Period_Month"],
            y=monthly["Score"],
            name="Overall Score",
            mode="lines+markers",
            line=dict(color="#79c0ff", width=3, shape="spline", smoothing=0.65),
            marker=dict(
                size=9,
                color=monthly["Risk"].map(RISK_COLORS),
                line=dict(color="#0d1117", width=1.5),
            ),
            customdata=monthly[["Risk"]],
            hovertemplate=(
                "<b>%{x|%b %Y}</b><br>"
                "Score: %{y:.1f}/100<br>"
                "Risk: %{customdata[0]}<extra></extra>"
            ),
        )
    )
    layout = plotly_theme(300)
    layout["xaxis"] = {
        **layout["xaxis"],
        "tickformat": "%b %Y",
        "title": "Month",
    }
    layout["yaxis"] = {
        **layout["yaxis"],
        "title": "Overall score",
        "range": [0, 100],
    }
    layout["legend"] = {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1}
    fig.update_layout(**layout)
    st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
    st.markdown("</div>", unsafe_allow_html=True)


def render_overview_category_summaries() -> None:
    detail = df[df["Profile_Key"].astype(str).isin(profile_keys)].copy()
    category_cols = st.columns(3)
    card_specs = [
        ("Complaint", "Complaint rate by category (%)", "#c97d16", "%", 1, False),
        ("LeadTime", "Average lead time by category (days)", "#3f6db3", "d", 0, False),
        ("PriceSaving", "Savings % by category", "#32ad7d", "%", 1, False),
    ]
    for idx, (col, title, color, suffix, decimals, ascending) in enumerate(card_specs):
        with category_cols[idx]:
            st.markdown(f'<div class="s-card"><div class="s-card-title">{title}</div>', unsafe_allow_html=True)
            if col not in detail.columns or detail[col].notna().sum() == 0:
                st.info("No category data available.")
                st.markdown("</div>", unsafe_allow_html=True)
                continue

            grouped = (
                detail.groupby("Category", as_index=False)[col]
                .mean()
                .dropna(subset=[col])
                .sort_values(col, ascending=ascending)
                .head(5)
                .reset_index(drop=True)
            )
            if grouped.empty:
                st.info("No category data available.")
                st.markdown("</div>", unsafe_allow_html=True)
                continue

            max_value = float(grouped[col].max()) if grouped[col].notna().any() else 0.0
            rows_html = []
            for _, item in grouped.iterrows():
                value = float(item[col])
                width = 100.0 if max_value <= 0 else max(12.0, min(100.0, value / max_value * 100.0))
                value_text = f"{value:.{decimals}f}{suffix}"
                rows_html.append(
                    f"""
<div class="spend-row" style="margin:.5rem 0;">
  <div class="spend-row-name">{html.escape(str(item["Category"]))}</div>
  <div class="spend-row-value" style="color:#e6edf3;">{html.escape(value_text)}</div>
  <div class="spend-row-bar" style="height:10px;background:#21262d;"><div style="width:{width:.0f}%;background:{color};"></div></div>
</div>
"""
                )
            st.markdown("".join(rows_html), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)


def render_order_volume_trend() -> None:
    st.markdown('<div class="s-card"><div class="s-card-title">Monthly order volume and non-compliance trend</div>', unsafe_allow_html=True)
    if COL_DATE not in df.columns or df[COL_DATE].notna().sum() == 0:
        st.info("Add Period_Date to show monthly volume and non-compliance history.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    detail = df[df["Profile_Key"].astype(str).isin(profile_keys)].dropna(subset=[COL_DATE]).copy()
    if detail.empty:
        st.info("No monthly order history is available for the current filters.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    detail["Period_Month"] = detail[COL_DATE].dt.to_period("M").dt.to_timestamp()
    monthly = (
        detail.groupby("Period_Month", as_index=False)
        .agg(
            Orders=(COL_SUPPLIER, "size"),
            Non_Compliant=("Anomalies", lambda values: int((values > 0).sum())),
        )
        .sort_values("Period_Month")
    )
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly["Period_Month"],
            y=monthly["Orders"],
            name="Monthly orders",
            marker_color="rgba(121,192,255,.72)",
            hovertemplate="<b>%{x|%b %Y}</b><br>Orders: %{y}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=monthly["Period_Month"],
            y=monthly["Non_Compliant"],
            name="Non-compliant",
            marker_color="rgba(248,81,73,.86)",
            hovertemplate="<b>%{x|%b %Y}</b><br>Non-compliant: %{y}<extra></extra>",
        )
    )
    layout = plotly_theme(300)
    layout["barmode"] = "group"
    layout["xaxis"] = {
        **layout["xaxis"],
        "tickformat": "%b %y",
        "title": "Month",
    }
    layout["yaxis"] = {
        **layout["yaxis"],
        "title": "Orders",
    }
    fig.update_layout(**layout)
    st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
    st.markdown("</div>", unsafe_allow_html=True)


def render_supplier_selector() -> pd.Series:
    selected_key = st.selectbox(
        "View supplier-category profile",
        profile_keys,
        index=profile_keys.index(st.session_state["selected_profile_key"]),
        format_func=lambda key: profile_labels.get(str(key), str(key)),
        key="selected_profile_key",
    )
    return filt[filt["Profile_Key"].astype(str) == str(selected_key)].iloc[0]


def render_supplier_profile(row: pd.Series) -> None:
    color = score_color(float(row["Score"]))
    score_text = fmt_num(row["Score"], "", 0)
    score_suffix = "" if pd.isna(row["Score"]) else '<span style="font-size:1rem;color:#8b949e;">/100</span>'
    ring_html = supplier_kpi_ring_html(row, rules)
    insight_html = f"""
  <div class="category-card-metrics" style="grid-template-columns:repeat(3,1fr);margin:.85rem 0 0;">
    <div><span>KPI Coverage</span><b>{fmt_num(row.get("KPI_Coverage", float("nan")), "%", 0)}</b></div>
    <div><span>Lead Volatility</span><b>{fmt_num(row.get("LeadTime_Std", float("nan")), "d", 1)}</b></div>
    <div><span>Vs Category</span><b>{fmt_num(row.get("Score_vs_Category_Avg", float("nan")), "", 1)}</b></div>
  </div>
"""
    spend_html = ""
    spend_value = row.get("Spend")
    max_spend = filt["Spend"].max(skipna=True) if "Spend" in filt.columns else float("nan")
    if HAS_SPEND and pd.notna(spend_value) and pd.notna(max_spend) and float(max_spend) > 0:
        spend_share = max(0.0, min(100.0, float(spend_value) / float(max_spend) * 100.0))
        spend_html = f"""
  <div class="spend-mini">
    <div class="spend-mini-label">Total spend for this profile</div>
    <div class="spend-mini-value">{html.escape(fmt_spend(float(spend_value)))}</div>
    <div class="spend-bar"><div style="width:{spend_share:.0f}%;"></div></div>
    <div class="kpi-muted" style="margin-top:.35rem;">{spend_share:.0f}% of the highest spend profile in current filter</div>
  </div>
"""
    st.markdown(
        f"""
<div class="s-card">
  <div class="s-card-title">Selected Supplier</div>
  <div style="display:flex;gap:12px;align-items:center;margin-bottom:14px;">
    <div class="profile-avatar">{html.escape(initials(row[COL_SUPPLIER]))}</div>
    <div>
      <div style="font-weight:900;font-size:1rem;color:#e6edf3;">{html.escape(str(row[COL_SUPPLIER]))}</div>
      <div style="font-size:.78rem;color:#8b949e;">{html.escape(str(row['Category']))}</div>
      <div style="margin-top:5px;">{risk_html(str(row['Risk']))}</div>
    </div>
  </div>
  <div style="font-size:.75rem;color:#8b949e;">Overall Score</div>
  <div style="font-size:2.15rem;font-weight:900;color:{color};">{score_text}{score_suffix}</div>
  <div style="font-size:.68rem;color:#8b949e;font-weight:800;margin-top:.35rem;">KPI rings - center is gap vs target, bottom shows actual and target</div>
  {ring_html}
  {insight_html}
  {spend_html}
</div>
""",
        unsafe_allow_html=True,
    )


def render_top_table(data: pd.DataFrame, rows: int | None = None) -> None:
    rows = rows or int(st.session_state["top_supplier_rows"])
    visible_rows = min(rows, len(data))
    table_height = min(720, max(150, 42 + visible_rows * 36))
    show = (
        data.sort_values("Score", ascending=False)
        .head(rows)[
            [
                COL_SUPPLIER,
                "Category",
                "Delivery",
                "Quality",
                "LeadTime",
                "LeadTime_Std",
                "Complaint",
                "PriceSaving",
                "Risk",
                "Score",
                "Score_vs_Category_Avg",
                "KPI_Coverage",
                "Anomalies",
            ]
        ]
        .rename(
            columns={
                COL_SUPPLIER: "Supplier",
                "Delivery": "Delivery %",
                "Quality": "Quality %",
                "LeadTime": "Lead Time",
                "LeadTime_Std": "Lead Volatility",
                "Complaint": "Complaint %",
                "PriceSaving": "Price Savings %",
                "Score_vs_Category_Avg": "Vs Category Avg",
                "KPI_Coverage": "KPI Coverage %",
            }
        )
    )
    st.dataframe(show, width="stretch", hide_index=True, height=table_height)


def render_spend_snapshot() -> None:
    if not HAS_SPEND or "Spend" not in filt.columns:
        return
    spend_data = filt.dropna(subset=["Spend"]).copy()
    spend_data = spend_data[spend_data["Spend"] > 0]
    if spend_data.empty:
        return

    total_spend = float(spend_data["Spend"].sum())
    top_spend = spend_data.nlargest(5, "Spend")
    max_spend = float(top_spend["Spend"].max())
    rows_html = []
    for _, item in top_spend.iterrows():
        width = max(2.0, min(100.0, float(item["Spend"]) / max_spend * 100.0)) if max_spend > 0 else 0
        is_selected = str(item["Profile_Key"]) == str(st.session_state.get("selected_profile_key", ""))
        bar_color = "linear-gradient(90deg,#d29922,#3fb950)" if is_selected else "linear-gradient(90deg,#388bfd,#2ea043)"
        rows_html.append(
            f"""
<div class="spend-row">
  <div class="spend-row-name">{html.escape(str(item["Profile_Label"]))}</div>
  <div class="spend-row-value">{html.escape(fmt_spend(float(item["Spend"])))}</div>
  <div class="spend-row-bar"><div style="width:{width:.0f}%;background:{bar_color};"></div></div>
</div>
"""
        )

    st.markdown(
        f"""
<div class="s-card" style="margin-top:.8rem;">
  <div class="s-card-title">Spend Snapshot</div>
  <div class="kpi-muted">Total spend in current filter</div>
  <div style="font-size:1.55rem;font-weight:950;color:#e6edf3;margin:.2rem 0 .65rem;">{html.escape(fmt_spend(total_spend))}</div>
  <div class="kpi-muted" style="margin-bottom:.35rem;">Top spend profiles</div>
  {''.join(rows_html)}
</div>
""",
        unsafe_allow_html=True,
    )


def render_overview() -> None:
    render_health_snapshot()
    render_kpi_cards()
    render_overview_category_summaries()
    left, right = st.columns([2.45, 1])
    with left:
        render_order_volume_trend()
        st.markdown('<div class="s-card"><div class="s-card-title">Delivery vs Quality - Supplier Comparison</div>', unsafe_allow_html=True)
        top_rows = int(st.session_state["top_supplier_rows"])
        trend = filt.sort_values("Score", ascending=False).head(top_rows)
        if trend["Delivery"].notna().any() or trend["Quality"].notna().any():
            fig = go.Figure()
            if trend["Delivery"].notna().any():
                fig.add_trace(go.Bar(
                    x=trend["Profile_Label"],
                    y=trend["Delivery"],
                    name="On-Time Delivery %",
                    marker_color="#388bfd",
                    hovertemplate="<b>%{x}</b><br>Delivery: %{y:.1f}%<extra></extra>",
                ))
            if trend["Quality"].notna().any():
                fig.add_trace(go.Scatter(
                    x=trend["Profile_Label"],
                    y=trend["Quality"],
                    name="Quality Score %",
                    mode="lines+markers",
                    line=dict(color="#3fb950"),
                    hovertemplate="<b>%{x}</b><br>Quality: %{y:.1f}%<extra></extra>",
                ))
            fig.update_layout(**plotly_theme(360), yaxis_title="Score (%)", xaxis_title="Supplier - Category")
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        else:
            st.info("Delivery and Quality KPIs are not available in this file.")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="s-card" style="margin-top:.8rem;"><div class="s-card-title">Anomaly Detection</div>', unsafe_allow_html=True)
        anomalies = filt[filt["Anomalies"] > 0].sort_values("Score").head(8)
        if anomalies.empty:
            st.success("No anomalies detected in current filters.")
        else:
            for _, item in anomalies.iterrows():
                st.markdown(
                    f"""
<div style="border-bottom:1px solid #21262d;padding:.65rem 0;">
  <div style="display:flex;justify-content:space-between;gap:8px;"><b>{html.escape(str(item[COL_SUPPLIER]))}</b>{risk_html(str(item['Risk']))}</div>
  {issue_chips(item['Issues'])}
  <div class="kpi-muted">Score {fmt_num(item['Score'])}</div>
</div>
""",
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="s-card" style="margin-top:.8rem;"><div class="s-card-title">Top Suppliers</div>', unsafe_allow_html=True)
    render_top_table(filt)
    st.markdown("</div>", unsafe_allow_html=True)

    bottom_left, bottom_right = st.columns([2.45, 1])
    with bottom_left:
        render_risk_movement()
    with bottom_right:
        row = selected_row
        render_supplier_profile(row)
        render_spend_snapshot()


def render_suppliers() -> None:
    left, right = st.columns([2.45, 1])
    with right:
        row = render_supplier_selector()
        render_supplier_profile(row)
    with left:
        st.markdown('<div class="s-card"><div class="s-card-title">Supplier Directory</div>', unsafe_allow_html=True)
        render_top_table(filt, rows=25)
        csv = filt.drop(columns=["Profile_Key", "Profile_Label"], errors="ignore").to_csv(index=False).encode("utf-8")
        st.download_button("Download filtered suppliers (CSV)", csv, file_name="suppliers_filtered.csv", mime="text/csv")
        st.markdown("</div>", unsafe_allow_html=True)


def render_performance() -> None:
    if filt["Score"].notna().sum() == 0:
        st.info("No KPI found for scoring. Add at least one KPI with a valid target/limit and weight in Settings.")
        return

    chart_data = filt.copy()
    chart_data["BubbleSize"] = chart_data["Score"].fillna(30).clip(lower=5)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="s-card"><div class="s-card-title">Delivery Reliability vs Quality Score</div>', unsafe_allow_html=True)
        delivery_quality = chart_data.dropna(subset=["Delivery", "Quality"])
        if delivery_quality.empty:
            st.info("This chart needs both Delivery and Quality KPI values.")
        else:
            fig = px.scatter(
                delivery_quality,
                x="Delivery",
                y="Quality",
                size="BubbleSize",
                color="Risk",
                color_discrete_map=RISK_COLORS,
                hover_name="Profile_Label",
                hover_data={"BubbleSize": False, "Score": ":.0f", "Delivery": ":.1f", "Quality": ":.1f", "Risk": True},
                labels={"Delivery": "Delivery (%)", "Quality": "Quality (%)", "Score": "Score", "Risk": "Risk level"},
            )
            fig.update_layout(**plotly_theme(390), xaxis_title="Delivery (%)", yaxis_title="Quality (%)")
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="s-card"><div class="s-card-title">Lead Time vs Complaint Rate</div>', unsafe_allow_html=True)
        lead_complaint = chart_data.dropna(subset=["LeadTime", "Complaint"])
        if lead_complaint.empty:
            st.info("This chart needs both Lead Time and Complaint Rate KPI values.")
        else:
            fig = px.scatter(
                lead_complaint,
                x="LeadTime",
                y="Complaint",
                size="BubbleSize",
                color="Risk",
                color_discrete_map=RISK_COLORS,
                hover_name="Profile_Label",
                hover_data={"BubbleSize": False, "Score": ":.0f", "LeadTime": ":.1f", "Complaint": ":.2f", "Risk": True},
                labels={"LeadTime": "Lead time (days)", "Complaint": "Complaint rate (%)", "Score": "Score", "Risk": "Risk level"},
            )
            fig.update_layout(**plotly_theme(390), xaxis_title="Lead Time (Days)", yaxis_title="Complaint Rate (%)")
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        st.markdown("</div>", unsafe_allow_html=True)


def render_anomalies() -> None:
    anomalies = filt[filt["Anomalies"] > 0].sort_values(["Score", "Anomalies"], ascending=[True, False]).copy()
    if anomalies.empty:
        st.markdown('<div class="s-card"><div class="s-card-title">Anomaly Management</div>', unsafe_allow_html=True)
        st.success("No anomaly found in the current filter.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    all_issue_categories = [
        issue_category(issue)
        for issues in anomalies["Issues"]
        for issue in issues
        if issue_category(issue) != "Limited data"
    ]
    if not all_issue_categories:
        all_issue_categories = [issue_category(issue) for issues in anomalies["Issues"] for issue in issues]
    issue_counts = pd.Series(all_issue_categories).value_counts().reset_index()
    issue_counts.columns = ["Issue Type", "Suppliers"]

    critical_count = int(((anomalies["Anomalies"] >= 4) | (anomalies["Risk"] == "High")).sum())
    most_common_issue = str(issue_counts.iloc[0]["Issue Type"]) if not issue_counts.empty else "None"
    worst_supplier = anomalies.iloc[0]
    avg_flagged_score = anomalies["Score"].mean()

    st.markdown(
        f"""
<div class="anomaly-summary-grid">
  <div class="anomaly-summary-card">
    <div class="anomaly-summary-label">Critical suppliers</div>
    <div class="anomaly-summary-value" style="color:#f85149;">{critical_count}</div>
    <div class="anomaly-summary-note">Need attention first</div>
  </div>
  <div class="anomaly-summary-card">
    <div class="anomaly-summary-label">Most common issue</div>
    <div class="anomaly-summary-value" style="font-size:1.15rem;">{html.escape(most_common_issue)}</div>
    <div class="anomaly-summary-note">Across current filters</div>
  </div>
  <div class="anomaly-summary-card">
    <div class="anomaly-summary-label">Lowest score</div>
    <div class="anomaly-summary-value">{fmt_num(worst_supplier['Score'], '', 0)}</div>
    <div class="anomaly-summary-note">{html.escape(str(worst_supplier[COL_SUPPLIER]))}</div>
  </div>
  <div class="anomaly-summary-card">
    <div class="anomaly-summary-label">Avg flagged score</div>
    <div class="anomaly-summary-value">{fmt_num(avg_flagged_score, '', 0)}</div>
    <div class="anomaly-summary-note">{len(anomalies)} flagged suppliers</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.05, 1.45])
    with left:
        st.markdown('<div class="s-card"><div class="s-card-title">Issue Breakdown</div>', unsafe_allow_html=True)
        fig = px.bar(
            issue_counts,
            x="Suppliers",
            y="Issue Type",
            orientation="h",
            color="Issue Type",
            color_discrete_map={
                "Delivery": "#58a6ff",
                "Lead time": "#a371f7",
                "Quality": "#d29922",
                "Complaints": "#f97316",
                "Price": "#f778ba",
                "Limited data": "#8b949e",
                "Other": "#8b949e",
            },
            labels={"Suppliers": "Suppliers", "Issue Type": "Issue"},
        )
        fig.update_layout(**plotly_theme(310), showlegend=False, xaxis_title="Suppliers", yaxis_title="")
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="s-card"><div class="s-card-title">Priority Suppliers & Recommended Action</div>', unsafe_allow_html=True)
        priority_rows = []
        for _, row in anomalies.head(8).iterrows():
            main_issue = main_issue_text(row["Issues"])
            action = recommended_action(row["Issues"])
            priority_rows.append(
                f"""
<div class="priority-row">
  <div>
    <div class="priority-title">{html.escape(str(row[COL_SUPPLIER]))}</div>
    <div class="priority-sub">{html.escape(str(row['Category']))}</div>
  </div>
  <div>
    <div class="kpi-label">Main issue</div>
    <div style="font-weight:900;color:#e6edf3;">{html.escape(main_issue)}</div>
  </div>
  <div>{severity_badge(int(row['Anomalies']), str(row['Risk']))}</div>
  <div>
    <div class="kpi-label">Recommended action</div>
    <div style="font-weight:850;color:#c9d1d9;">{html.escape(action)}</div>
  </div>
  <div style="text-align:right;">
    <div class="kpi-label">Score</div>
    <div style="font-weight:950;color:{score_color(float(row['Score']))};">{fmt_num(row['Score'], '', 0)}</div>
  </div>
</div>
"""
            )
        st.markdown('<div class="priority-list">' + "".join(priority_rows) + "</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Detailed KPI table", expanded=False):
        rows_html = []
        for _, row in anomalies.iterrows():
            rows_html.append(
                f"""
<tr>
  <td>{html.escape(str(row[COL_SUPPLIER]))}</td>
  <td>{html.escape(str(row['Category']))}</td>
  <td class="num">{row['Delivery']:.1f}</td>
  <td class="num">{row['LeadTime']:.0f}</td>
  <td class="num">{row['Quality']:.1f}</td>
  <td class="num">{row['Complaint']:.1f}</td>
  <td class="num">{row['PriceSaving']:+.1f}</td>
  <td>{risk_html(str(row['Risk']))}</td>
  <td class="num">{row['Score']:.0f}</td>
  <td>{issue_summary(row['Issues'])}</td>
</tr>
"""
            )
        st.markdown(
            f"""
<div class="anomaly-table-wrap">
  <table class="anomaly-table">
    <thead><tr><th>Supplier</th><th>Category</th><th>Delivery %</th><th>Lead Time</th><th>Quality %</th><th>Complaint %</th><th>Price Savings %</th><th>Risk</th><th>Score</th><th>Issues</th></tr></thead>
    {''.join(rows_html)}
  </table>
</div>
""",
            unsafe_allow_html=True,
        )


def render_issue_diagnostics() -> None:
    st.markdown('<div class="s-card"><div class="s-card-title">Issue Rate Heatmap</div>', unsafe_allow_html=True)
    if issue_diagnostics.empty:
        st.info("Order_Status data is needed for issue diagnostics.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    heatmap_data = issue_diagnostics.pivot(
        index=COL_SUPPLIER,
        columns=COL_CATEGORY,
        values="Combo_Issue_Rate_%",
    ).sort_index()
    if heatmap_data.empty:
        st.info("No issue diagnostics are available for the uploaded data.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    fig = px.imshow(
        heatmap_data,
        color_continuous_scale="RdYlGn_r",
        text_auto=".1f",
        aspect="auto",
        labels={"x": "Category", "y": "Supplier", "color": "Issue rate %"},
    )
    fig.update_layout(**plotly_theme(420), coloraxis_colorbar={"title": "Issue %"})
    fig.update_xaxes(side="top")
    st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
    st.markdown("</div>", unsafe_allow_html=True)

    supplier_order = (
        issue_diagnostics.groupby(COL_SUPPLIER)["Combo_Issue_Rate_%"]
        .max()
        .sort_values(ascending=False)
        .index.astype(str)
        .tolist()
    )
    selected_diag_supplier = st.selectbox("Select supplier for issue drill-down", supplier_order)
    supplier_diag = (
        issue_diagnostics[issue_diagnostics[COL_SUPPLIER].astype(str) == selected_diag_supplier]
        .sort_values("Combo_Issue_Rate_%", ascending=False)
        .copy()
    )
    overall_issue_rate = float(issue_diagnostics["Overall_Issue_Rate_%"].iloc[0])

    st.markdown(
        """
<div class="s-card">
  <div class="s-card-title">Supplier vs Category Issue Rates</div>
  <div class="diag-legend">
    <span class="diag-legend-item"><span class="diag-legend-dot" style="background:#58a6ff;"></span>Supplier + selected category</span>
    <span class="diag-legend-item"><span class="diag-legend-dot" style="background:#d29922;"></span>Supplier overall</span>
    <span class="diag-legend-item"><span class="diag-legend-dot" style="background:#3fb950;"></span>Category overall</span>
    <span class="diag-legend-item"><span class="diag-legend-dot" style="background:#f85149;"></span>Overall baseline</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="s-card">', unsafe_allow_html=True)
    bar = go.Figure()
    bar.add_bar(
        name="Supplier + Category",
        x=supplier_diag[COL_CATEGORY],
        y=supplier_diag["Combo_Issue_Rate_%"],
        marker_color="#58a6ff",
        hovertemplate="<b>%{x}</b><br>Supplier + category issue rate: %{y:.1f}%<extra></extra>",
    )
    bar.add_bar(
        name="Supplier overall",
        x=supplier_diag[COL_CATEGORY],
        y=supplier_diag["Supplier_Issue_Rate_%"],
        marker_color="#d29922",
        hovertemplate="<b>%{x}</b><br>Supplier overall issue rate: %{y:.1f}%<extra></extra>",
    )
    bar.add_bar(
        name="Category overall",
        x=supplier_diag[COL_CATEGORY],
        y=supplier_diag["Category_Issue_Rate_%"],
        marker_color="#3fb950",
        hovertemplate="<b>%{x}</b><br>Category overall issue rate: %{y:.1f}%<extra></extra>",
    )
    bar.add_hline(
        y=overall_issue_rate,
        line_dash="dash",
        line_color="#f85149",
        annotation_text="Overall baseline",
        annotation_position="top left",
    )
    bar_layout = plotly_theme(380)
    bar.update_layout(
        **bar_layout,
        barmode="group",
        xaxis_title="Category",
        yaxis_title="Issue rate (%)",
        showlegend=False,
    )
    st.plotly_chart(bar, width="stretch", config=PLOT_CONFIG)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Detailed diagnostics table", expanded=False):
        detail = issue_diagnostics.sort_values("Combo_Issue_Rate_%", ascending=False)
        rows_html = []
        for _, row in detail.iterrows():
            rows_html.append(
                f"""
<tr>
  <td>{html.escape(str(row[COL_SUPPLIER]))}</td>
  <td>{html.escape(str(row[COL_CATEGORY]))}</td>
  <td class="num">{float(row['Combo_Issue_Rate_%']):.1f}</td>
  <td class="num">{float(row['Supplier_Issue_Rate_%']):.1f}</td>
  <td class="num">{float(row['Category_Issue_Rate_%']):.1f}</td>
  <td class="num">{float(row['Overall_Issue_Rate_%']):.1f}</td>
  <td>{diagnosis_badge(str(row['Diagnosis']))}</td>
</tr>
"""
            )
        st.markdown(
            f"""
<div class="anomaly-table-wrap">
  <table class="anomaly-table">
    <thead>
      <tr>
        <th>Supplier</th>
        <th>Category</th>
        <th>Combo %</th>
        <th>Supplier %</th>
        <th>Category %</th>
        <th>Overall %</th>
        <th>Diagnosis</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</div>
""",
            unsafe_allow_html=True,
        )


def render_scorecards() -> None:
    st.markdown('<div class="s-card"><div class="s-card-title">Supplier Scorecards</div>', unsafe_allow_html=True)
    render_top_table(filt.sort_values("Score", ascending=False), rows=50)
    st.markdown("</div>", unsafe_allow_html=True)


def render_spend_analysis() -> None:
    st.markdown('<div class="s-card"><div class="s-card-title">Spend Analysis</div>', unsafe_allow_html=True)
    if not HAS_SPEND:
        st.info("No Spend column was found in your Excel file.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            spend_cat = filt.groupby("Category", as_index=False)["Spend"].sum().sort_values("Spend", ascending=False)
            fig = px.bar(
                spend_cat,
                x="Category",
                y="Spend",
                color="Spend",
                color_continuous_scale="Blues",
                labels={"Category": "Category", "Spend": "Total spend"},
            )
            fig.update_layout(**plotly_theme(390), yaxis_title="Total Spend")
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        with c2:
            top_spend = filt.nlargest(12, "Spend")
            fig = px.bar(
                top_spend.sort_values("Spend"),
                x="Spend",
                y="Profile_Label",
                orientation="h",
                color="Risk",
                color_discrete_map=RISK_COLORS,
                labels={"Spend": "Spend", "Profile_Label": "Supplier - Category", "Risk": "Risk level"},
            )
            fig.update_layout(**plotly_theme(390), xaxis_title="Spend", yaxis_title="Supplier - Category")
            st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
    value_data = filt.dropna(subset=["Value_Index", "PriceSaving", "Quality", "Score"]).copy()
    if not value_data.empty:
        st.markdown('<div class="s-card-title" style="margin-top:.8rem;">Value for Money: Savings vs Quality</div>', unsafe_allow_html=True)
        value_data["BubbleSize"] = value_data["Spend"] if HAS_SPEND else value_data["Score"].clip(lower=1)
        fig = px.scatter(
            value_data,
            x="Quality",
            y="PriceSaving",
            size="BubbleSize",
            color="Risk",
            color_discrete_map=RISK_COLORS,
            hover_name="Profile_Label",
            hover_data={
                "BubbleSize": False,
                "Value_Index": ":.2f",
                "Score": ":.0f",
                "Spend": ":,.0f" if HAS_SPEND else False,
                "Risk": True,
            },
            labels={
                "Quality": "Quality score (%)",
                "PriceSaving": "Price savings (%)",
                "Value_Index": "Value index",
                "Risk": "Risk level",
            },
        )
        fig.update_layout(**plotly_theme(360), xaxis_title="Quality Score (%)", yaxis_title="Price Savings (%)")
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
    st.markdown("</div>", unsafe_allow_html=True)


def render_category_insights() -> None:
    category = filt.groupby("Category", as_index=False).agg(
        Profiles=(COL_SUPPLIER, "count"),
        Suppliers=(COL_SUPPLIER, "nunique"),
        Avg_Score=("Score", "mean"),
        Avg_Delivery=("Delivery", "mean"),
        Avg_Quality=("Quality", "mean"),
        Avg_Lead_Time=("LeadTime", "mean"),
        Avg_Complaint=("Complaint", "mean"),
        Avg_Price_Savings=("PriceSaving", "mean"),
        Spend=("Spend", "sum"),
        Alerts=("Anomalies", "sum"),
    ).round(2).sort_values("Avg_Score", ascending=False)
    if category.empty:
        st.info("No category data available in the current filter.")
        return

    risk_counts = pd.crosstab(filt["Category"], filt["Risk"])
    for risk in ["Low", "Medium", "High"]:
        category[risk] = category["Category"].map(risk_counts.get(risk, pd.Series(dtype=int))).fillna(0).astype(int)

    scored_profiles = filt.dropna(subset=["Score"]).copy()
    best_profiles = (
        scored_profiles.sort_values("Score", ascending=False)
        .drop_duplicates("Category")
        .set_index("Category")
    )
    worst_profiles = (
        scored_profiles.sort_values("Score", ascending=True)
        .drop_duplicates("Category")
        .set_index("Category")
    )
    category["Best_Profile"] = category["Category"].map(best_profiles["Profile_Label"]) if not best_profiles.empty else "N/A"
    category["Best_Score"] = category["Category"].map(best_profiles["Score"]) if not best_profiles.empty else float("nan")
    category["Worst_Profile"] = category["Category"].map(worst_profiles["Profile_Label"]) if not worst_profiles.empty else "N/A"
    category["Worst_Score"] = category["Category"].map(worst_profiles["Score"]) if not worst_profiles.empty else float("nan")

    def main_weakness(row: pd.Series) -> str:
        checks = []
        if pd.notna(row["Avg_Delivery"]):
            checks.append(("Delivery", higher_is_better_component_score(float(row["Avg_Delivery"]), float(rules["delivery_target"]))))
        if pd.notna(row["Avg_Quality"]):
            checks.append(("Quality", higher_is_better_component_score(float(row["Avg_Quality"]), float(rules["quality_target"]))))
        if pd.notna(row["Avg_Lead_Time"]):
            checks.append(("Lead time", lower_is_better_component_score(float(row["Avg_Lead_Time"]), float(rules["leadtime_limit"]))))
        if pd.notna(row["Avg_Complaint"]):
            checks.append(("Complaints", lower_is_better_component_score(float(row["Avg_Complaint"]), float(rules["complaint_limit"]))))
        if pd.notna(row["Avg_Price_Savings"]):
            checks.append(("Savings", higher_is_better_component_score(float(row["Avg_Price_Savings"]), float(rules["price_dev_tolerance"]))))
        checks = [(label, score) for label, score in checks if pd.notna(score)]
        if not checks:
            return "Insufficient KPI data"
        label, score = min(checks, key=lambda item: item[1])
        if score >= 80:
            return "No major KPI weakness"
        return f"Weakest: {label}"

    category["Main_Weakness"] = category.apply(main_weakness, axis=1)
    category["Portfolio_Status"] = category.apply(
        lambda row: "Stable"
        if pd.notna(row["Avg_Score"]) and row["Avg_Score"] >= float(st.session_state["risk_low_threshold"])
        else "Watchlist"
        if pd.notna(row["Avg_Score"]) and row["Avg_Score"] >= float(st.session_state["risk_medium_threshold"])
        else "Strategic Risk",
        axis=1,
    )
    status_colors = {"Strategic Risk": "#f85149", "Watchlist": "#d29922", "Stable": "#3fb950"}

    chart_col, guide_col = st.columns([3.2, 1])
    with chart_col:
        matrix_title = "Category Spend vs Risk Matrix" if HAS_SPEND else "Category Risk Matrix"
        x_axis = "Spend" if HAS_SPEND else "Profiles"
        x_title = "Total Spend" if HAS_SPEND else "Supplier-category profiles"
        st.markdown(f'<div class="s-card"><div class="s-card-title">{matrix_title}</div>', unsafe_allow_html=True)
        fig = px.scatter(
            category,
            x=x_axis,
            y="Avg_Score",
            size="Profiles",
            color="Portfolio_Status",
            color_discrete_map=status_colors,
            hover_name="Category",
            hover_data={
                "Suppliers": True,
                "Profiles": True,
                "Spend": ":,.0f" if HAS_SPEND else False,
                "Avg_Delivery": ":.1f",
                "Avg_Quality": ":.1f",
                "Avg_Complaint": ":.2f",
                "Avg_Price_Savings": ":.2f",
                "Avg_Lead_Time": ":.1f",
                "Avg_Score": ":.1f",
                "Alerts": True,
                "Main_Weakness": True,
                "Portfolio_Status": False,
            },
            labels={
                "Avg_Score": "Average score",
                "Spend": "Total spend",
                "Suppliers": "Suppliers",
                "Profiles": "Profiles",
                "Avg_Delivery": "Avg delivery",
                "Avg_Quality": "Avg quality",
                "Avg_Complaint": "Avg complaint",
                "Avg_Price_Savings": "Avg savings",
                "Avg_Lead_Time": "Avg lead time",
                "Main_Weakness": "Main weakness",
                "Portfolio_Status": "Category status",
            },
        )
        fig.add_hline(
            y=float(st.session_state["risk_low_threshold"]),
            line_dash="dot",
            line_color="#3fb950",
            annotation_text="Low risk line",
            annotation_position="top left",
        )
        fig.add_hline(
            y=float(st.session_state["risk_medium_threshold"]),
            line_dash="dot",
            line_color="#d29922",
            annotation_text="Medium line",
            annotation_position="bottom left",
        )
        if HAS_SPEND and category["Spend"].sum(skipna=True) > 0:
            fig.add_vline(
                x=float(category["Spend"].mean()),
                line_dash="dash",
                line_color="#8b949e",
                annotation_text="Avg spend",
                annotation_position="top right",
            )
        fig.update_layout(
            **plotly_theme(430),
            xaxis_title=x_title,
            yaxis_title="Average Score",
            legend_title_text="Category Status",
        )
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
        st.markdown("</div>", unsafe_allow_html=True)
    with guide_col:
        low_threshold = float(st.session_state["risk_low_threshold"])
        medium_threshold = float(st.session_state["risk_medium_threshold"])
        st.markdown(
            f"""
<div class="s-card">
  <div class="s-card-title">Status Guide</div>
  <div style="display:flex;flex-direction:column;gap:.75rem;">
    <div><span class="severity-pill severity-watch" style="color:#3fb950;background:rgba(63,185,80,.12);border-color:rgba(63,185,80,.38);">Stable / Green</span><div class="kpi-muted" style="margin-top:.25rem;">Avg score >= {low_threshold:.0f}</div></div>
    <div><span class="severity-pill severity-warning">Watchlist / Yellow</span><div class="kpi-muted" style="margin-top:.25rem;">Avg score {medium_threshold:.0f} to {low_threshold - 1:.0f}</div></div>
    <div><span class="severity-pill severity-critical">Strategic Risk / Red</span><div class="kpi-muted" style="margin-top:.25rem;">Avg score < {medium_threshold:.0f}</div></div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    cards = []
    status_order = {"Strategic Risk": 0, "Watchlist": 1, "Stable": 2}
    for _, row in category.assign(_status_order=category["Portfolio_Status"].map(status_order)).sort_values(
        ["_status_order", "Spend", "Alerts"], ascending=[True, False, False]
    ).iterrows():
        status = str(row["Portfolio_Status"])
        if status == "Strategic Risk":
            action = "Prioritize supplier recovery plan"
        elif status == "Watchlist":
            action = "Monitor category and review weak suppliers"
        else:
            action = "Maintain current supplier strategy"
        spend_text = fmt_spend(float(row["Spend"])) if HAS_SPEND else "N/A"
        best_score_color = score_color(float(row["Best_Score"])) if pd.notna(row["Best_Score"]) else "#8b949e"
        worst_score_color = score_color(float(row["Worst_Score"])) if pd.notna(row["Worst_Score"]) else "#8b949e"
        cards.append(
            f"""
<div class="category-card" style="--cat-color:{status_colors[status]};">
  <div class="category-card-title">{html.escape(str(row['Category']))}</div>
  <div class="category-card-status">{html.escape(status)}</div>
  <div class="category-card-metrics" style="grid-template-columns:repeat(4,1fr);">
    <div><span>Score</span><b>{fmt_num(row['Avg_Score'], '', 0)}</b></div>
    <div><span>Spend</span><b>{html.escape(spend_text)}</b></div>
    <div><span>Suppliers</span><b>{int(row['Suppliers'])}</b></div>
    <div><span>Alerts</span><b>{int(row['Alerts'])}</b></div>
  </div>
  <div class="category-supplier-row">
    <div class="category-supplier-tag">Best</div>
    <div class="category-supplier-name">{html.escape(str(row['Best_Profile']))}</div>
    <div class="category-supplier-score" style="color:{best_score_color};">{fmt_num(row['Best_Score'], '', 0)}</div>
  </div>
  <div class="category-supplier-row">
    <div class="category-supplier-tag">Weak</div>
    <div class="category-supplier-name">{html.escape(str(row['Worst_Profile']))}</div>
    <div class="category-supplier-score" style="color:{worst_score_color};">{fmt_num(row['Worst_Score'], '', 0)}</div>
  </div>
  <div class="weakness-pill">{html.escape(str(row['Main_Weakness']))}</div>
  <div class="category-action">{html.escape(action)}</div>
</div>
"""
        )
    st.markdown('<div class="category-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)

    with st.expander("Detailed category table", expanded=False):
        table_cols = [
            "Category",
            "Portfolio_Status",
            "Avg_Score",
            "Spend",
            "Suppliers",
            "Profiles",
            "Low",
            "Medium",
            "High",
            "Alerts",
            "Main_Weakness",
            "Best_Profile",
            "Best_Score",
            "Worst_Profile",
            "Worst_Score",
            "Avg_Delivery",
            "Avg_Quality",
            "Avg_Lead_Time",
            "Avg_Complaint",
            "Avg_Price_Savings",
        ]
        st.dataframe(category[table_cols].round(2), width="stretch", hide_index=True)


def render_trends() -> None:
    st.markdown('<div class="s-card"><div class="s-card-title">Monthly Supplier KPI Trend</div>', unsafe_allow_html=True)
    if COL_DATE not in df.columns or df[COL_DATE].notna().sum() == 0:
        st.info("No usable Order_Date column found. Add Order_Date to enable monthly trend charts.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    metric_labels = {
        "Score": "Avg Score",
        "Delivery": "Delivery (%)",
        "Quality": "Quality (%)",
        "LeadTime": "Lead time (days)",
        "Complaint": "Complaint rate (%)",
        "PriceSaving": "Price savings (%)",
    }
    metric_targets = {
        "Score": float(st.session_state["risk_low_threshold"]),
        "Delivery": float(st.session_state["delivery_target"]),
        "Quality": float(st.session_state["quality_target"]),
        "LeadTime": float(st.session_state["leadtime_limit"]),
        "Complaint": float(st.session_state["complaint_limit"]),
        "PriceSaving": float(st.session_state["price_dev_tolerance"]),
    }
    lower_is_better = {"LeadTime", "Complaint"}
    metric_options = ["Score"] + [
        metric for metric in ["Delivery", "Quality", "LeadTime", "Complaint", "PriceSaving"] if df[metric].notna().any()
    ]

    profile_options = filt.sort_values("Score", ascending=False)["Profile_Key"].astype(str).tolist()
    profile_label_map = dict(zip(filt["Profile_Key"].astype(str), filt["Profile_Label"].astype(str)))
    if not profile_options:
        st.info("No supplier-category profiles are available in the current filter.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    metric = st.selectbox("Choose KPI", metric_options, format_func=lambda item: metric_labels.get(item, item))
    target = metric_targets[metric]
    direction_text = "Lower is better" if metric in lower_is_better else "Higher is better"
    st.markdown(
        f"""
<div style="display:flex;gap:.55rem;flex-wrap:wrap;margin:.25rem 0 .85rem;">
  <span class="status-low">Green = meets target</span>
  <span class="status-high">Red = misses target</span>
  <span class="status-medium">Blank = no orders that month</span>
  <span class="trend-target-chip">{html.escape(direction_text)} | {target:.1f}</span>
</div>
""",
        unsafe_allow_html=True,
    )

    heatmap_keys = profile_options[: min(18, len(profile_options))]
    heatmap_source = df[df["Profile_Key"].astype(str).isin(heatmap_keys)].dropna(subset=[COL_DATE, metric]).copy()
    if heatmap_source.empty:
        st.info("No monthly trend data available for the selected filters and KPI.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    heatmap_source["Period_Month"] = heatmap_source[COL_DATE].dt.to_period("M").astype(str)
    heatmap_grouped = (
        heatmap_source.groupby(["Profile_Label", "Period_Month"], as_index=False)
        .agg(Value=(metric, "mean"), Orders=(metric, "size"))
    )
    if metric in lower_is_better:
        heatmap_grouped["Gap"] = target - heatmap_grouped["Value"]
    else:
        heatmap_grouped["Gap"] = heatmap_grouped["Value"] - target
    heatmap = heatmap_grouped.pivot(index="Profile_Label", columns="Period_Month", values="Gap")
    value_heatmap = heatmap_grouped.pivot(index="Profile_Label", columns="Period_Month", values="Value")
    orders_heatmap = heatmap_grouped.pivot(index="Profile_Label", columns="Period_Month", values="Orders")
    heatmap_order = [profile_label_map[key] for key in heatmap_keys if profile_label_map.get(key) in heatmap.index]
    heatmap = heatmap.reindex(heatmap_order)
    value_heatmap = value_heatmap.reindex(index=heatmap.index, columns=heatmap.columns)
    orders_heatmap = orders_heatmap.reindex(index=heatmap.index, columns=heatmap.columns)
    heatmap_text = None
    if len(heatmap) <= 12 and len(heatmap.columns) <= 14:
        heatmap_text = [
            ["" if pd.isna(value_heatmap.loc[row, col]) else f"{value_heatmap.loc[row, col]:.0f}" for col in heatmap.columns]
            for row in heatmap.index
        ]
    customdata = [
        [
            [
                None if pd.isna(value_heatmap.loc[row, col]) else float(value_heatmap.loc[row, col]),
                float(target),
                0 if pd.isna(orders_heatmap.loc[row, col]) else int(orders_heatmap.loc[row, col]),
                None if pd.isna(heatmap.loc[row, col]) else float(heatmap.loc[row, col]),
            ]
            for col in heatmap.columns
        ]
        for row in heatmap.index
    ]

    heatmap_fig = go.Figure(
        data=go.Heatmap(
            z=heatmap.values,
            x=heatmap.columns,
            y=heatmap.index,
            zmid=0,
            colorscale=[[0, "#f85149"], [0.48, "#fff3b0"], [0.5, "#30363d"], [0.52, "#d8f285"], [1, "#3fb950"]],
            colorbar={"title": "Gap vs target"},
            customdata=customdata,
            text=heatmap_text,
            texttemplate="%{text}" if heatmap_text is not None else None,
            hoverongaps=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Month: %{x}<br>"
                f"{metric_labels.get(metric, metric)}: " + "%{customdata[0]:.1f}<br>"
                "Target: %{customdata[1]:.1f}<br>"
                "Gap: %{customdata[3]:.1f}<br>"
                "Orders: %{customdata[2]}<extra></extra>"
            ),
            xgap=2,
            ygap=2,
        )
    )
    heatmap_height = max(360, min(620, 140 + len(heatmap) * 24))
    heatmap_fig.update_layout(
        **plotly_theme(heatmap_height),
        xaxis_title="Month",
        yaxis_title="Supplier - Category",
    )
    st.plotly_chart(heatmap_fig, width="stretch", config=PLOT_CONFIG)
    st.markdown("</div>", unsafe_allow_html=True)

    selected_profile = st.selectbox(
        "Select supplier-category profile for monthly drill-down",
        profile_options,
        format_func=lambda key: profile_label_map.get(str(key), str(key)),
    )

    selected_source = df[df["Profile_Key"].astype(str) == str(selected_profile)].dropna(subset=[COL_DATE, metric]).copy()
    st.markdown('<div class="s-card"><div class="s-card-title">Selected Profile - Monthly Target Gap</div>', unsafe_allow_html=True)
    if selected_source.empty:
        st.info("No monthly data available for the selected supplier-category profile.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    selected_source["Period_Month"] = selected_source[COL_DATE].dt.to_period("M").astype(str)
    monthly = (
        selected_source.groupby("Period_Month", as_index=False)
        .agg(Value=(metric, "mean"), Orders=(metric, "size"))
        .sort_values("Period_Month")
    )
    monthly["Target"] = target
    if metric in lower_is_better:
        monthly["Gap"] = target - monthly["Value"]
        gap_label = f"Better than target ({metric_labels[metric]})"
    else:
        monthly["Gap"] = monthly["Value"] - target
        gap_label = f"Above target ({metric_labels[metric]})"
    monthly["Result"] = monthly["Gap"].apply(lambda value: "Good" if value >= 0 else "Needs attention")
    monthly["Color"] = monthly["Result"].map({"Good": "#3fb950", "Needs attention": "#f85149"})

    gap_fig = go.Figure()
    gap_fig.add_bar(
        x=monthly["Gap"],
        y=monthly["Period_Month"],
        orientation="h",
        marker_color=monthly["Color"],
        customdata=monthly[["Value", "Target", "Orders", "Result"]],
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Actual: %{customdata[0]:.1f}<br>"
            "Target: %{customdata[1]:.1f}<br>"
            "Gap: %{x:.1f}<br>"
            "Orders: %{customdata[2]}<br>"
            "%{customdata[3]}<extra></extra>"
        ),
    )
    gap_fig.add_vline(x=0, line_dash="dash", line_color="#8b949e")
    gap_fig.update_layout(
        **plotly_theme(380),
        xaxis_title=gap_label,
        yaxis_title="Month",
        showlegend=False,
    )
    st.plotly_chart(gap_fig, width="stretch", config=PLOT_CONFIG)

    with st.expander("Detailed monthly table", expanded=False):
        table = monthly[["Period_Month", "Value", "Target", "Gap", "Result", "Orders"]].rename(
            columns={
                "Period_Month": "Month",
                "Value": metric_labels.get(metric, metric),
                "Target": "Target",
                "Gap": "Gap vs Target",
            }
        )
        st.dataframe(table.round(2), width="stretch", hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
if page == "Overview":
    render_overview()
elif page == "Suppliers":
    render_suppliers()
elif page == "Performance":
    render_performance()
elif page == "Anomalies":
    render_anomalies()
elif page == "Issue Diagnostics":
    render_issue_diagnostics()
elif page == "Scorecards":
    render_scorecards()
elif page == "Spend Analysis":
    render_spend_analysis()
elif page == "Category Insights":
    render_category_insights()
elif page == "Trends":
    render_trends()

st.markdown(
    '<div style="text-align:center;color:#6e7681;font-size:.75rem;padding:24px 0 8px;">'
    'SupplierDash - Interactive KPI Monitoring - Powered by Streamlit</div>',
    unsafe_allow_html=True,
)
