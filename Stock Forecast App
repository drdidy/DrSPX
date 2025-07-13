# Dr Didy SPX Forecast – v1.5.8  ← only change: contract line = 5-min blocks
# --------------------------------------------------------------------------
# • Contract Line (Low-1 ↔ Low-2) projects every 5 min; lookup uses same
# • Everything else identical to 1.5.7 (cards, 30-min anchor trends, UI)

import json, base64, streamlit as st
from datetime import datetime, date, time, timedelta
from copy import deepcopy
import pandas as pd

# ── CONSTANTS ────────────────────────────────────────────────────────────────
PAGE_TITLE, PAGE_ICON = "DRSPX Forecast", "📈"
VERSION  = "1.5.8"

BASE_SLOPES = {
    "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792,
    "TSLA": -0.1508, "NVDA": -0.0485, "AAPL": -0.0750,
    "MSFT": -0.17,   "AMZN": -0.03,   "GOOGL": -0.07,
    "META": -0.035,  "NFLX": -0.23,
}
ICONS = {
    "SPX":"🧭","TSLA":"🚗","NVDA":"🧠","AAPL":"🍎",
    "MSFT":"🪟","AMZN":"📦","GOOGL":"🔍",
    "META":"📘","NFLX":"📺"
}

# ── SESSION INIT ─────────────────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.update(
        theme="Light",
        slopes=deepcopy(BASE_SLOPES),
        presets={},
        contract_anchor=None,
        contract_slope=None,
        contract_price=None)

if st.query_params.get("s"):
    try:
        st.session_state.slopes.update(
            json.loads(base64.b64decode(st.query_params["s"][0]).decode()))
    except Exception:
        pass

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(PAGE_TITLE, PAGE_ICON, "wide", initial_sidebar_state="expanded")

# ── CSS, card(), and 30-min helpers are **unchanged** from 1.5.7 ────────────
# (-- keep the entire CSS block, card(), make_slots(), blk_spx(), blk_stock(),
#     tbl() exactly as before – omitted here for brevity)

# ── NEW 5-MIN CONTRACT HELPERS ───────────────────────────────────────────────
def make_slots_5(start=time(7,30), end=time(14,30)):
    cur   = datetime(2025,1,1,start.hour,start.minute)
    stop  = datetime(2025,1,1,end.hour,end.minute)
    slots = []
    while cur <= stop:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=5)
    return slots

CONTRACT_SLOTS = make_slots_5()             # 07:30–14:30 every 5 min

def blk_5min(a, t):                         # 5-minute blocks
    return max(0, int((t - a).total_seconds() // 300))

def tbl_contract(price, slope, anchor, fd):
    rows=[]
    for s in CONTRACT_SLOTS:
        h,m = map(int, s.split(":"))
        tgt = datetime.combine(fd, time(h,m))
        b   = blk_5min(anchor, tgt)
        rows.append({"Time": s, "Projected": round(price + slope * b, 2)})
    return pd.DataFrame(rows)

# ── HEADER & TABS (unchanged) ────────────────────────────────────────────────
st.markdown(f"<div class='banner'><h3>{PAGE_ICON} {PAGE_TITLE}</h3></div>",
            unsafe_allow_html=True)
tabs = st.tabs([f"{ICONS[t]} {t}" for t in ICONS])

# ── SPX TAB ──────────────────────────────────────────────────────────────────
with tabs[0]:
    # ---- underlying inputs (unchanged) ----
    c1,c2,c3 = st.columns(3)
    hp,ht = c1.number_input("High Price",  value=6185.8, min_value=0.0), \
            c1.time_input  ("High Time",   time(11,30))
    cp,ct = c2.number_input("Close Price", value=6170.2, min_value=0.0), \
            c2.time_input  ("Close Time",  time(15))
    lp,lt = c3.number_input("Low  Price",  value=6130.4, min_value=0.0), \
            c3.time_input  ("Low Time",    time(13,30))

    # ---- contract inputs (unchanged UI) ----
    st.subheader("Contract Line (Low-1 ↔ Low-2)")
    o1,o2 = st.columns(2)
    l1_t,l1_p = o1.time_input("Low-1 Time", time(2)), \
                o1.number_input("Low-1 Price", value=10.0, min_value=0.0, step=0.1, key="l1")
    l2_t,l2_p = o2.time_input("Low-2 Time", time(3,30)), \
                o2.number_input("Low-2 Price", value=12.0, min_value=0.0, step=0.1, key="l2")

    if st.button("Run Forecast"):
        # ---- anchor cards + 30-min anchor-trends (UNCHANGED) ----
        st.markdown('<div class="cards">', unsafe_allow_html=True)
        # card() calls and 30-min tbl() loop exactly as before – keep intact

        # ---- build & store 5-min Contract Line ----
        anchor_dt = datetime.combine(fcast_date, l1_t)
        slope_5   = (l2_p - l1_p) / (blk_5min(anchor_dt,
                         datetime.combine(fcast_date, l2_t)) or 1)
        st.session_state.contract_anchor = anchor_dt
        st.session_state.contract_slope  = slope_5
        st.session_state.contract_price  = l1_p

        st.subheader("Contract Line (2-pt, 5-min)")
        st.dataframe(tbl_contract(l1_p, slope_5, anchor_dt, fcast_date),
                     use_container_width=True)

    # ---- lookup widget (now uses 5-min math) ----
    lookup_t = st.time_input("Lookup time", time(9,25),
                             step=300, key="lookup_time")
    if st.session_state.contract_anchor:
        blocks = blk_5min(st.session_state.contract_anchor,
                          datetime.combine(fcast_date, lookup_t))
        val = st.session_state.contract_price + \
              st.session_state.contract_slope * blocks
        st.info(f"Projected @ {lookup_t.strftime('%H:%M')} → **{val:.2f}**")
    else:
        st.info("Enter Low-1 & Low-2 and press **Run Forecast** to activate lookup.")

# ── STOCK TABS + FOOTER (unchanged from 1.5.7) ───────────────────────────────
# … keep your existing stock_tab() and footer exactly as they are …