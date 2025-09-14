# app.py
# ═══════════════════════════════════════════════════════════════════════════════
# 🔮 SPX PROPHET — SPX-only, minimal & robust (no external data)
# • Anchor: prior day ≤ 3:00 PM CT close (manual input)
# • SPX slope: ±0.25/30m (fixed) → 34 blocks to 8:30 → ±8.50
# • Contract slope: ±0.33/30m default (28 blocks to 8:30 → ±9.24); override from 2 prices
# • BC Forecast: EXACTLY 2 bounces (21:00–07:00 CT) → project SPX & one contract through RTH
# • Tables (separate): CLOSE / HIGH / LOW, each 30m 08:30→14:30 with minimal columns
# • Plan Card (4 clear cards): ready by 08:00 AM, simple step-by-step
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, date, time, timedelta
from typing import List, Tuple

# ───────────────────────────────────────────────────────────────────────────────
# CONFIG
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="🔮 SPX Prophet", page_icon="📈", layout="wide")

CT = pytz.timezone("America/Chicago")

SLOPE_SPX = 0.25                 # per 30m (fixed)
SLOPE_CONTRACT_DEFAULT = 0.33    # per 30m (default; can be overridden by BC inputs)

RTH_START = time(8, 30)
RTH_END   = time(14, 30)

DEFAULT_ANCHOR = 6400.00
DEFAULT_PAD_RANGE = 2.0          # simple intrabar pad for High/Low tables

# ───────────────────────────────────────────────────────────────────────────────
# TIME HELPERS
# ───────────────────────────────────────────────────────────────────────────────
def fmt_ct(dt: datetime) -> datetime:
    if dt.tzinfo is None: return CT.localize(dt)
    return dt.astimezone(CT)

def rth_slots_ct(day: date) -> List[datetime]:
    start = fmt_ct(datetime.combine(day, RTH_START))
    end   = fmt_ct(datetime.combine(day, RTH_END))
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += timedelta(minutes=30)
    return out

def gen_slots(start_dt: datetime, end_dt: datetime, step_min: int = 30) -> List[datetime]:
    start_dt = fmt_ct(start_dt); end_dt = fmt_ct(end_dt)
    out = []
    cur = start_dt
    while cur <= end_dt:
        out.append(cur)
        cur += timedelta(minutes=step_min)
    return out

def is_maintenance(dt: datetime) -> bool:
    # 4–5 PM CT maintenance excluded for SPX counting
    return dt.hour == 16

def in_weekend_gap(dt: datetime) -> bool:
    wd = dt.weekday()
    if wd == 5: return True
    if wd == 6 and dt.hour < 17: return True
    if wd == 4 and dt.hour >= 17: return True
    return False

def count_blocks_spx(t0: datetime, t1: datetime) -> int:
    """SPX blocks from t0→t1, skipping 4–5 PM and weekend gap."""
    t0 = fmt_ct(t0); t1 = fmt_ct(t1)
    if t1 <= t0: return 0
    t = t0
    blocks = 0
    while t < t1:
        t_next = t + timedelta(minutes=30)
        if not is_maintenance(t_next) and not in_weekend_gap(t_next):
            blocks += 1
        t = t_next
    return blocks

def count_blocks_contract_overnight(anchor_day: date, target_dt: datetime) -> int:
    """
    Contract valid blocks from 3:00 PM anchor-day to target_dt:
      • 3:00→3:30 PM = 1 block
      • skip 3:30 PM → 7:00 PM
      • 7:00 PM → target in 30m steps
    3 PM → 8:30 AM = 28 blocks total.
    """
    target_dt = fmt_ct(target_dt)
    anchor_3pm   = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    anchor_330pm = fmt_ct(datetime.combine(anchor_day, time(15, 30)))
    anchor_7pm   = fmt_ct(datetime.combine(anchor_day, time(19, 0)))
    if target_dt <= anchor_3pm: return 0
    blocks = 0
    if target_dt >= anchor_330pm: blocks += 1
    if target_dt > anchor_7pm:
        delta_min = int((target_dt - anchor_7pm).total_seconds() // 60)
        blocks += delta_min // 30
    return blocks

def blocks_simple_30m(d1: datetime, d2: datetime) -> int:
    """Plain 30m steps between two times (used inside overnight & forward RTH)."""
    d1 = fmt_ct(d1); d2 = fmt_ct(d2)
    if d2 <= d1: return 0
    return int((d2 - d1).total_seconds() // (30*60))

# ───────────────────────────────────────────────────────────────────────────────
# FAN & PROJECTIONS
# ───────────────────────────────────────────────────────────────────────────────
def fan_levels_for_slot(anchor_close: float, anchor_time: datetime, slot_dt: datetime) -> Tuple[float, float]:
    blocks = count_blocks_spx(anchor_time, slot_dt)
    top = anchor_close + SLOPE_SPX * blocks
    bot = anchor_close - SLOPE_SPX * blocks
    return round(top, 2), round(bot, 2)

def sigma_to_830(anchor_day: date) -> float:
    """SPX ± move to 8:30 from 3:00 PM (should be 34 blocks × 0.25 = 8.5)."""
    anchor_3pm = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    next_830   = fmt_ct(datetime.combine(anchor_day + timedelta(days=1), time(8, 30)))
    blocks_830 = count_blocks_spx(anchor_3pm, next_830)
    return round(blocks_830 * SLOPE_SPX, 2)

# ───────────────────────────────────────────────────────────────────────────────
# STYLES
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root { --brand:#2563eb; --surface:#ffffff; --muted:#f8fafc; --text:#0f172a; --sub:#475569; --border:#e2e8f0; }
html, body { background: var(--muted); color: var(--text); }
.card { background: rgba(255,255,255,0.94); border:1px solid var(--border); border-radius:16px; padding:16px; box-shadow:0 12px 32px rgba(2,6,23,0.07); }
.metric { font-size:1.8rem; font-weight:700; }
.kicker { color:var(--sub); font-size:.85rem; }
.dataframe { border-radius:12px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# SIDEBAR — Inputs
# ───────────────────────────────────────────────────────────────────────────────
st.sidebar.title("🔧 Settings")

today_ct = fmt_ct(datetime.now()).date()
prev_day = st.sidebar.date_input("Previous Trading Day", value=today_ct - timedelta(days=1))
proj_day = st.sidebar.date_input("Projection Day", value=prev_day + timedelta(days=1))

anchor_close = st.sidebar.number_input("Prev Day ≤ 3:00 PM CT Close (SPX)", value=float(DEFAULT_ANCHOR), step=0.25, format="%.2f")

with st.sidebar.expander("Intrabar Range Pad for High/Low Tables", expanded=False):
    intrabar_pad = st.number_input("Pad (pts)", value=float(DEFAULT_PAD_RANGE), step=0.25, format="%.2f")

st.sidebar.caption(f"SPX slope = {SLOPE_SPX:.2f}/30m • Contract slope = {SLOPE_CONTRACT_DEFAULT:.2f}/30m (default)")

# Precompute sigma @ 8:30
sigma_830 = sigma_to_830(prev_day)  # expected 8.50

# ───────────────────────────────────────────────────────────────────────────────
# HEADER — Key Metrics
# ───────────────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"<div class='card'><div class='kicker'>Anchor (≤ 3:00 PM CT)</div><div class='metric'>💠 {anchor_close:.2f}</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='card'><div class='kicker'>SPX ± to 8:30 (34 blocks @ 0.25)</div><div class='metric'>± {sigma_830:.2f}</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div class='card'><div class='kicker'>Contract ± to 8:30 (28 blocks @ 0.33)</div><div class='metric'>± {28*SLOPE_CONTRACT_DEFAULT:.2f}</div></div>", unsafe_allow_html=True)

st.markdown("---")

# ───────────────────────────────────────────────────────────────────────────────
# TABS
# ───────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["SPX Anchors", "BC Forecast", "Plan Card"])

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 1 — SPX Anchors (Three minimal tables)                                  ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab1:
    st.subheader("SPX Anchors — Minimal Tables (every 30m 08:30→14:30)")
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))

    # If BC Forecast ran, pull slopes & reference for contract projection
    bc = st.session_state.get("bc_one_contract", None)
    if bc:
        contract_name = bc["name"]
        contract_slope = bc["slope"]
        contract_ref_price = bc["ref_price"]
        contract_ref_dt = bc["ref_dt"]
    else:
        contract_name = "ATM"
        contract_slope = SLOPE_CONTRACT_DEFAULT
        # For default mode (no two prices), we project deltas from 3 PM anchor: require 3 PM option price.
        # Since we don't fetch, ask for it here simply:
        with st.expander("Optional: Contract 3:00 PM Price (for default projections)", expanded=False):
            contract_ref_price = st.number_input(f"{contract_name} Price @ 3:00 PM", value=20.00, step=0.05, format="%.2f")
        contract_ref_dt = fmt_ct(datetime.combine(prev_day, time(15, 0)))

    # Helper to project contract at any slot using slope from ref point
    def contract_proj_at(slot_dt: datetime) -> float:
        blocks = blocks_simple_30m(contract_ref_dt, slot_dt) if bc else count_blocks_contract_overnight(prev_day, slot_dt)
        return round(contract_ref_price + contract_slope * blocks, 2)

    # Build rows for three tables
    rows_close, rows_high, rows_low = [], [], []
    for slot in rth_slots_ct(proj_day):
        top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot)
        time_str = slot.strftime("%H:%M")
        star = "⭐" if time_str == "08:30" else ""
        # SPX projected "close" line: for simplicity we use fan mid (anchor-aligned), or BC if available later
        # In this minimal version, keep Close as midpoint between Top/Bottom (neutral anchor line)
        spx_close_proj = round((top + bot) / 2.0, 2)

        # Contract projection
        c_proj = contract_proj_at(slot)

        rows_close.append({
            "⭐": star, "Time": time_str,
            "Top": top, "Bottom": bot,
            "SPX Close Proj": spx_close_proj,
            f"{contract_name} Proj": c_proj
        })

        # High / Low expected using a simple intrabar pad around the mid
        mid = spx_close_proj
        exp_high = round(mid + float(intrabar_pad), 2)
        exp_low  = round(mid - float(intrabar_pad), 2)

        rows_high.append({
            "⭐": star, "Time": time_str,
            "Top": top,
            "Exp High (SPX)": exp_high,
            f"{contract_name} Proj": c_proj
        })

        rows_low.append({
            "⭐": star, "Time": time_str,
            "Bottom": bot,
            "Exp Low (SPX)": exp_low,
            f"{contract_name} Proj": c_proj
        })

    st.markdown("### Close Table")
    st.dataframe(pd.DataFrame(rows_close), use_container_width=True, hide_index=True)

    st.markdown("### High Table")
    st.dataframe(pd.DataFrame(rows_high), use_container_width=True, hide_index=True)

    st.markdown("### Low Table")
    st.dataframe(pd.DataFrame(rows_low), use_container_width=True, hide_index=True)

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 2 — BC Forecast (EXACTLY 2 bounces, ONE contract)                       ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab2:
    st.subheader("BC Forecast — Two Overnight Bounces (SPX & ONE Contract)")

    overnight_start = fmt_ct(datetime.combine(prev_day, time(21, 0)))
    overnight_end   = fmt_ct(datetime.combine(proj_day, time(7, 0)))
    overnight_slots = gen_slots(overnight_start, overnight_end, 30)
    slot_labels = [dt.strftime("%Y-%m-%d %H:%M") for dt in overnight_slots]

    with st.form("bc_form_one", clear_on_submit=False):
        st.markdown("**Bounce Inputs (required)** — pick two slots & enter SPX prices")
        c1, c2 = st.columns(2)
        with c1:
            b1_sel = st.selectbox("Bounce #1 (CT)", slot_labels, index=0, key="b1")
            spx_b1 = st.number_input("SPX @ Bounce #1", value=anchor_close, step=0.25, format="%.2f")
        with c2:
            b2_sel = st.selectbox("Bounce #2 (CT)", slot_labels, index=min(6, len(slot_labels)-1), key="b2")
            spx_b2 = st.number_input("SPX @ Bounce #2", value=anchor_close, step=0.25, format="%.2f")

        st.markdown("---")
        st.markdown("**Contract (ONE, optional)** — prices at the SAME two bounces")
        cc = st.columns(3)
        with cc[0]:
            c_name = st.text_input("Contract Name", value="ATM")
        with cc[1]:
            c_b1 = st.number_input("Contract @ Bounce #1", value=10.00, step=0.05, format="%.2f")
        with cc[2]:
            c_b2 = st.number_input("Contract @ Bounce #2", value=10.30, step=0.05, format="%.2f")

        submitted = st.form_submit_button("📈 Project")

    if submitted:
        try:
            b1_dt = fmt_ct(datetime.strptime(b1_sel, "%Y-%m-%d %H:%M"))
            b2_dt = fmt_ct(datetime.strptime(b2_sel, "%Y-%m-%d %H:%M"))
            if b2_dt <= b1_dt:
                st.error("Bounce #2 must be after Bounce #1.")
            else:
                # SPX slope from bounces (SPX block logic)
                spx_blocks = count_blocks_spx(b1_dt, b2_dt)
                if spx_blocks <= 0:
                    st.error("Selected bounce times must be at least 30 minutes apart.")
                else:
                    spx_slope = (float(spx_b2) - float(spx_b1)) / spx_blocks

                    # Contract slope from the two prices (simple 30m steps between bounces)
                    bounce_blocks_30m = blocks_simple_30m(b1_dt, b2_dt)
                    c_slope = SLOPE_CONTRACT_DEFAULT
                    if bounce_blocks_30m > 0 and (c_b2 != c_b1):
                        c_slope = float((float(c_b2) - float(c_b1)) / bounce_blocks_30m)

                    # Build RTH projections table (minimal)
                    rows = []
                    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
                    for slot in rth_slots_ct(proj_day):
                        top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot)
                        spx_proj = round(float(spx_b2) + spx_slope * count_blocks_spx(b2_dt, slot), 2)
                        blocks_from_b2 = blocks_simple_30m(b2_dt, slot)
                        c_proj = round(float(c_b2) + c_slope * blocks_from_b2, 2)

                        rows.append({
                            "⭐": "⭐" if slot.strftime("%H:%M") == "08:30" else "",
                            "Time": slot.strftime("%H:%M"),
                            "Top": top, "Bottom": bot,
                            "SPX Proj": spx_proj,
                            f"{c_name} Proj": c_proj
                        })

                    out_df = pd.DataFrame(rows)
                    st.markdown("### RTH Projection (SPX & Contract)")
                    st.dataframe(out_df, use_container_width=True, hide_index=True)

                    # Bands to 8:30
                    c_band_28 = round(abs(c_slope) * 28, 2)
                    colA, colB = st.columns(2)
                    with colA:
                        st.markdown(f"<div class='card'><div class='kicker'>SPX ± to 8:30</div><div class='metric'>± {sigma_to_830(prev_day):.2f}</div></div>", unsafe_allow_html=True)
                    with colB:
                        st.markdown(f"<div class='card'><div class='kicker'>{c_name} ± to 8:30 (28 blocks)</div><div class='metric'>± {c_band_28:.2f}</div></div>", unsafe_allow_html=True)

                    # Save for Plan Card & Tab 1 default projections
                    st.session_state["bc_one_contract"] = {
                        "name": c_name,
                        "slope": c_slope,
                        "ref_price": float(c_b2),
                        "ref_dt": b2_dt,
                        "table": out_df
                    }

        except Exception as e:
            st.error(f"Could not compute projection: {e}")

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 3 — Plan Card (4 simple cards, 08:00 AM)                                 ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab3:
    st.subheader("Plan Card — simple, ready by 08:00 AM")

    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    slot_830    = fmt_ct(datetime.combine(proj_day, time(8, 30)))
    top_830, bot_830 = fan_levels_for_slot(anchor_close, anchor_time, slot_830)

    # If BC exists, pull projections for key times; else blank
    bc = st.session_state.get("bc_one_contract", None)
    key_times = ["08:30", "10:00", "13:30", "14:30"]
    plan_rows = []

    if bc and "table" in bc:
        tdf = bc["table"]
        c_name = bc["name"]
        for t in key_times:
            try:
                r = tdf.loc[tdf["Time"] == t].iloc[0]
                plan_rows.append({
                    "Time": t,
                    "SPX": float(r["SPX Proj"]),
                    c_name: float(r[f"{c_name} Proj"])
                })
            except Exception:
                plan_rows.append({"Time": t, "SPX": "", (bc["name"] if bc else "ATM"): ""})
    else:
        c_name = "ATM"
        for t in key_times:
            plan_rows.append({"Time": t, "SPX": "", c_name: ""})

    # CARD 1 — Levels
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"<div class='card'>"
            f"<div class='kicker'>Card 1 — Levels</div>"
            f"<div class='metric'>Anchor {anchor_close:.2f}</div>"
            f"<div class='kicker'>8:30 Fan → Top {top_830:.2f} • Bottom {bot_830:.2f} • SPX ±{sigma_to_830(prev_day):.2f}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    # CARD 2 — Primary Setup (plain-English)
    with c2:
        st.markdown(
            "<div class='card'>"
            "<div class='kicker'>Card 2 — Primary Setup</div>"
            "<div>• If price tags <b>Top</b> and closes bearish (inside/above), plan a <b>sell-from-top</b>.</div>"
            "<div>• If price tags <b>Bottom</b> and closes bullish (inside/below), plan a <b>buy-from-bottom</b>.</div>"
            "<div>• If neither edge is tagged, wait for an edge touch; 08:30 is priority slot.</div>"
            "</div>",
            unsafe_allow_html=True
        )

    # CARD 3 — Key Slot Projections (from BC if given)
    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("<div class='kicker'>Card 3 — Key Slot Projections</div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(plan_rows), use_container_width=True, hide_index=True)

    # CARD 4 — Simple Execution Steps
    st.markdown("<div class='kicker'>Card 4 — Simple Execution Steps</div>", unsafe_allow_html=True)
    st.write(
        "- **At 08:30**: check where price is vs Fan Top/Bottom.\n"
        "- If at Top → wait for bearish close to short (risk above Top by small pad).\n"
        "- If at Bottom → wait for bullish close to buy (risk below Bottom by small pad).\n"
        "- Scale out at mid/opposite edge; avoid fighting a clean break that closes beyond the edge."
    )