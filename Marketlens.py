# app.py
# ═══════════════════════════════════════════════════════════════════════════════
# 🔮 SPX PROPHET — SPX-only, robust, no external data
# • Anchor: prior day ≤ 3:00 PM CT close (manual input)
# • SPX slope: ±0.25/30m (fixed) → 34 blocks to 8:30 → ±8.50 (±1σ), ±17.00 (±2σ)
# • Contract slope: ±0.33/30m default (28 blocks to 8:30 → ±9.24); override from 2 prices
# • BC Forecast: EXACTLY 2 bounces (21:00–07:00 CT) → project SPX & up to 2 contracts through RTH
# • Tables: CLOSE table + HIGH/LOW table for every 30m (8:30→14:30), ⭐ highlights 8:30
# • PDH/PDL (+ optional ONH/ONL): distances, confluence chips, smart stops/targets
# • Plan Card: concise at 8:00 AM
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Optional

# ───────────────────────────────────────────────────────────────────────────────
# CONFIG
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="🔮 SPX Prophet", page_icon="📈", layout="wide")

CT = pytz.timezone("America/Chicago")

SLOPE_SPX = 0.25                 # per 30m, fixed
SLOPE_CONTRACT_DEFAULT = 0.33    # per 30m default; can be overridden via BC inputs

RTH_START = time(8, 30)
RTH_END   = time(14, 30)

DEFAULT_ANCHOR = 6400.00
DEFAULT_PAD_RANGE = 2.0   # intrabar pad for high/low projections & entry zones
DEFAULT_STOP_PAD = 2.0    # stop beyond edge (or beyond PDH/PDL when close)
DEFAULT_CONFLUENCE_THRESH = 2.0  # pts to call a confluence with PDH/PDL/ONH/ONL

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
    # Skip 4–5 PM CT maintenance hour for SPX block counting
    return dt.hour == 16

def in_weekend_gap(dt: datetime) -> bool:
    wd = dt.weekday()  # Mon=0..Sun=6
    if wd == 5: return True
    if wd == 6 and dt.hour < 17: return True
    if wd == 4 and dt.hour >= 17: return True
    return False

def count_blocks_spx(t0: datetime, t1: datetime) -> int:
    """SPX blocks anchor→target, skip 4–5 PM and weekend gap."""
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

def count_blocks_contract(anchor_day: date, target_dt: datetime) -> int:
    """
    Contract valid blocks: 3:00→3:30 PM (1) + 7:00 PM→target in 30m steps.
    Used for 3 PM → 8:30 AM = 28 blocks.
    """
    target_dt = fmt_ct(target_dt)
    anchor_3pm   = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    anchor_330pm = fmt_ct(datetime.combine(anchor_day, time(15, 30)))
    anchor_7pm   = fmt_ct(datetime.combine(anchor_day, time(19, 0)))

    if target_dt <= anchor_3pm: return 0
    blocks = 0
    if target_dt >= anchor_330pm:
        blocks += 1  # 3:00→3:30
    if target_dt > anchor_7pm:
        delta_min = int((target_dt - anchor_7pm).total_seconds() // 60)
        blocks += delta_min // 30
    return blocks

# Simple 30m difference used within overnight (between two bounce points)
def blocks_simple_30m(d1: datetime, d2: datetime) -> int:
    d1 = fmt_ct(d1); d2 = fmt_ct(d2)
    if d2 <= d1: return 0
    return int((d2 - d1).total_seconds() // (30*60))

# ───────────────────────────────────────────────────────────────────────────────
# FAN & PROJECTIONS
# ───────────────────────────────────────────────────────────────────────────────
def fan_levels_for_slot(anchor_close: float, anchor_time: datetime, slot_dt: datetime) -> Tuple[float, float, float]:
    blocks = count_blocks_spx(anchor_time, slot_dt)
    top = anchor_close + SLOPE_SPX * blocks
    bot = anchor_close - SLOPE_SPX * blocks
    return round(top, 2), round(bot, 2), round(top - bot, 2)

def sigma_bands_at_830(anchor_close: float, anchor_day: date) -> Tuple[float, float, int]:
    anchor_3pm = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    next_830   = fmt_ct(datetime.combine(anchor_day + timedelta(days=1), time(8, 30)))
    blocks_830 = count_blocks_spx(anchor_3pm, next_830)  # should be 34
    move = SLOPE_SPX * blocks_830
    return round(move, 2), round(2*move, 2), blocks_830

def confluence_chips(top: float, bottom: float,
                     pdh: Optional[float], pdl: Optional[float],
                     onh: Optional[float], onl: Optional[float],
                     thr: float) -> str:
    chips = []
    def near(a,b): return (a is not None) and (b is not None) and (abs(a-b) <= thr)
    if near(top, pdh): chips.append("Top≈PDH")
    if near(bottom, pdl): chips.append("Bottom≈PDL")
    if onh is not None and near(top, onh): chips.append("Top≈ONH")
    if onl is not None and near(bottom, onl): chips.append("Bottom≈ONL")
    return " • ".join(chips)

def smart_stop(is_sell_from_top: bool, top: float, bottom: float,
               pdh: Optional[float], pdl: Optional[float], pad: float) -> str:
    if is_sell_from_top:
        level = pdh if (pdh is not None and pdh >= top and abs(pdh - top) <= 2*pad) else top
        return f"{level + pad:.2f}"
    else:
        level = pdl if (pdl is not None and pdl <= bottom and abs(bottom - pdl) <= 2*pad) else bottom
        return f"{level - pad:.2f}"

def smart_tp(is_sell_from_top: bool, top: float, bottom: float,
             pdh: Optional[float], pdl: Optional[float]) -> str:
    if is_sell_from_top:
        if pdl is not None and abs(bottom - pdl) < abs(bottom - top):
            return f"{pdl:.2f} (PDL)"
        return f"{bottom:.2f} (Bottom)"
    else:
        if pdh is not None and abs(top - pdh) < abs(top - bottom):
            return f"{pdh:.2f} (PDH)"
        return f"{top:.2f} (Top)"

# ───────────────────────────────────────────────────────────────────────────────
# STYLES
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root { --brand:#2563eb; --surface:#ffffff; --muted:#f8fafc; --text:#0f172a; --sub:#475569; --border:#e2e8f0; }
html, body { background: var(--muted); color: var(--text); }
.card { background: rgba(255,255,255,0.92); border:1px solid var(--border); border-radius:16px; padding:16px; box-shadow:0 12px 32px rgba(2,6,23,0.07); }
.metric { font-size:1.8rem; font-weight:700; }
.kicker { color:var(--sub); font-size:.85rem; }
.badge { background:#e2e8f0; border:1px solid #cbd5e1; border-radius:999px; padding:2px 8px; font-weight:600; font-size:.75rem; }
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

with st.sidebar.expander("Key Levels (previous/overnight)", expanded=True):
    pdh = st.number_input("Prev Day High (PDH)", value=anchor_close+10.0, step=0.25, format="%.2f")
    pdl = st.number_input("Prev Day Low (PDL)",  value=anchor_close-10.0, step=0.25, format="%.2f")
    use_on = st.checkbox("Also track Overnight High/Low", value=False)
    onh = st.number_input("Overnight High (ONH)", value=anchor_close+5.0, step=0.25, format="%.2f", disabled=not use_on)
    onl = st.number_input("Overnight Low (ONL)",  value=anchor_close-5.0, step=0.25, format="%.2f", disabled=not use_on)

with st.sidebar.expander("Pads & Confluence", expanded=False):
    intrabar_pad = st.number_input("Intrabar Range Pad (pts)", value=float(DEFAULT_PAD_RANGE), step=0.25, format="%.2f")
    stop_pad     = st.number_input("Stop Pad beyond Edge (pts)", value=float(DEFAULT_STOP_PAD), step=0.25, format="%.2f")
    confl_thr    = st.number_input("Confluence Threshold (pts)", value=float(DEFAULT_CONFLUENCE_THRESH), step=0.25, format="%.2f")

st.sidebar.caption(f"SPX slope = ±{SLOPE_SPX:.2f}/30m • Contracts = ±{SLOPE_CONTRACT_DEFAULT:.2f}/30m (default)")

# Precompute sigma @ 8:30
sigma1, sigma2, spx_blocks_to_830 = sigma_bands_at_830(anchor_close, prev_day)  # expected 34 blocks → 8.5 & 17.0

# ───────────────────────────────────────────────────────────────────────────────
# HEADER METRICS
# ───────────────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"<div class='card'><div class='kicker'>Anchor (≤3:00 PM CT)</div><div class='metric'>💠 {anchor_close:.2f}</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='card'><div class='kicker'>SPX to 8:30 ({spx_blocks_to_830} blocks @ {SLOPE_SPX:.2f})</div><div class='metric'>± {sigma1:.2f} (1σ) • ± {sigma2:.2f} (2σ)</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div class='card'><div class='kicker'>Contracts to 8:30 (28 blocks @ {SLOPE_CONTRACT_DEFAULT:.2f})</div><div class='metric'>± {SLOPE_CONTRACT_DEFAULT*28:.2f}</div></div>", unsafe_allow_html=True)
with c4:
    st.markdown(f"<div class='card'><div class='kicker'>Confluence Threshold</div><div class='metric'>{confl_thr:.2f} pts</div></div>", unsafe_allow_html=True)

st.markdown("---")

# ───────────────────────────────────────────────────────────────────────────────
# TABS
# ───────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["SPX Anchors", "BC Forecast", "Plan Card"])

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 1 — SPX Anchors                                                         ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab1:
    st.subheader("SPX Anchors — Entries & Exits (every 30m from 08:30→14:30)")
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))

    close_rows = []
    hilo_rows  = []
    for slot in rth_slots_ct(proj_day):
        top, bot, width = fan_levels_for_slot(anchor_close, anchor_time, slot)

        # Distances to key levels (safe fallbacks if user clears values)
        pdh_val = float(pdh) if pdh is not None else None
        pdl_val = float(pdl) if pdl is not None else None
        onh_val = float(onh) if (use_on and onh is not None) else None
        onl_val = float(onl) if (use_on and onl is not None) else None

        pdh_dist = round(top - pdh_val, 2) if pdh_val is not None else ""
        pdl_dist = round(bot - pdl_val, 2) if pdl_val is not None else ""
        onh_dist = round(top - onh_val, 2) if onh_val is not None else ""
        onl_dist = round(bot - onl_val, 2) if onl_val is not None else ""
        chips = confluence_chips(top, bot, pdh_val, pdl_val, onh_val, onl_val, float(confl_thr))

        # CLOSE table
        entry_plan  = "Top touch & bearish close → Sell  |  Bottom touch & bullish close → Buy"
        trigger     = "Touch edge, close inside/above(Top) or inside/below(Bottom)"
        stop_sell   = smart_stop(True, top, bot, pdh_val, pdl_val, float(stop_pad))
        stop_buy    = smart_stop(False, top, bot, pdh_val, pdl_val, float(stop_pad))
        tp_sell     = smart_tp(True, top, bot, pdh_val, pdl_val)
        tp_buy      = smart_tp(False, top, bot, pdh_val, pdl_val)

        close_rows.append({
            "⭐": "⭐" if slot.strftime("%H:%M") == "08:30" else "",
            "Time": slot.strftime("%H:%M"),
            "Top": top, "Bottom": bot, "Width": width,
            "PDH Dist": pdh_dist, "PDL Dist": pdl_dist,
            **({"ONH Dist": onh_dist, "ONL Dist": onl_dist} if use_on else {}),
            "Confluence": chips,
            "Entry Plan": entry_plan,
            "Trigger": trigger,
            "Stop (Sell/Buy)": f"{stop_sell} / {stop_buy}",
            "TP1 (Sell/Buy)": f"{tp_sell} / {tp_buy}",
        })

        # HIGH/LOW table (intrabar excursion)
        mid = round((top + bot)/2.0, 2)
        exp_high = round(mid + float(intrabar_pad), 2)
        exp_low  = round(mid - float(intrabar_pad), 2)
        hilo_rows.append({
            "⭐": "⭐" if slot.strftime("%H:%M") == "08:30" else "",
            "Time": slot.strftime("%H:%M"),
            "Top": top, "Bottom": bot, "Width": width,
            "Exp High (SPX)": exp_high, "Exp Low (SPX)": exp_low,
            "Entry Zone": f"Sell near Top±{float(intrabar_pad):.2f} • Buy near Bottom±{float(intrabar_pad):.2f}",
            "Exit Zone": "Mirror side ± pad",
            "Confluence": chips
        })

    st.markdown("### Close Table — actionable entries/exits")
    st.dataframe(pd.DataFrame(close_rows), use_container_width=True, hide_index=True)

    st.markdown("### High/Low Table — excursion-based entries/exits")
    st.dataframe(pd.DataFrame(hilo_rows), use_container_width=True, hide_index=True)

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 2 — BC Forecast (EXACTLY 2 bounces)                                     ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab2:
    st.subheader("BC Forecast — Two Overnight Bounces → Project SPX & Contracts")

    overnight_start = fmt_ct(datetime.combine(prev_day, time(21, 0)))
    overnight_end   = fmt_ct(datetime.combine(proj_day, time(7, 0)))
    overnight_slots = gen_slots(overnight_start, overnight_end, 30)
    slot_labels = [dt.strftime("%Y-%m-%d %H:%M") for dt in overnight_slots]

    with st.form("bc_form", clear_on_submit=False):
        st.markdown("**Bounce Inputs (required)** — choose two 30-min slots & enter SPX prices")
        c1, c2 = st.columns(2)
        with c1:
            b1_sel = st.selectbox("Bounce #1 (slot, CT)", slot_labels, index=0, key="bc_b1")
            spx_b1 = st.number_input("SPX @ Bounce #1", value=anchor_close, step=0.25, format="%.2f")
        with c2:
            b2_sel = st.selectbox("Bounce #2 (slot, CT)", slot_labels, index=min(6, len(slot_labels)-1), key="bc_b2")
            spx_b2 = st.number_input("SPX @ Bounce #2", value=anchor_close, step=0.25, format="%.2f")

        st.markdown("---")
        st.markdown("**Contracts (optional)** — prices at the SAME two bounce times")
        cA1, cA2, cB1, cB2 = st.columns(4)
        with cA1:
            nameA = st.text_input("Contract A (e.g., 6525c)", value="ATM-A")
        with cA2:
            cA_b1 = st.number_input("A price @ Bounce #1", value=10.00, step=0.05, format="%.2f")
        with cB1:
            nameB = st.text_input("Contract B (optional)", value="ATM-B")
        with cB2:
            cB_b1 = st.number_input("B price @ Bounce #1", value=9.50, step=0.05, format="%.2f")
        cA3, cA4, cB3, cB4 = st.columns(4)
        with cA3:
            cA_b2 = st.number_input("A price @ Bounce #2", value=10.50, step=0.05, format="%.2f")
        with cA4:
            cB_b2 = st.number_input("B price @ Bounce #2", value=9.80, step=0.05, format="%.2f")

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

                    # Contract slopes from the two provided prices (simple 30m steps between bounces)
                    bounce_blocks_30m = blocks_simple_30m(b1_dt, b2_dt)
                    slope_A = SLOPE_CONTRACT_DEFAULT
                    slope_B = SLOPE_CONTRACT_DEFAULT
                    if bounce_blocks_30m > 0 and (cA_b2 != cA_b1):
                        slope_A = float((float(cA_b2) - float(cA_b1)) / bounce_blocks_30m)
                    if bounce_blocks_30m > 0 and (cB_b2 != cB_b1):
                        slope_B = float((float(cB_b2) - float(cB_b1)) / bounce_blocks_30m)

                    # Build RTH projections table
                    rows = []
                    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
                    for slot in rth_slots_ct(proj_day):
                        # Fan
                        top, bot, width = fan_levels_for_slot(anchor_close, anchor_time, slot)
                        # SPX projection from bounce line (anchor at Bounce #2)
                        spx_proj = round(float(spx_b2) + spx_slope * count_blocks_spx(b2_dt, slot), 2)
                        # Contracts projections anchored at Bounce #2
                        blocks_from_b2 = blocks_simple_30m(b2_dt, slot)
                        A_proj = round(float(cA_b2) + slope_A * blocks_from_b2, 2)
                        B_proj = round(float(cB_b2) + slope_B * blocks_from_b2, 2)

                        rows.append({
                            "⭐": "⭐" if slot.strftime("%H:%M") == "08:30" else "",
                            "Time": slot.strftime("%H:%M"),
                            "Top": top, "Bottom": bot, "SPX Proj": spx_proj,
                            f"{nameA} Proj": A_proj,
                            f"{nameB} Proj": B_proj
                        })

                    out_df = pd.DataFrame(rows)
                    st.markdown("### RTH Projection (SPX & Contracts)")
                    st.dataframe(out_df, use_container_width=True, hide_index=True)

                    # Bands at 8:30
                    A_band_28 = round(abs(slope_A) * 28, 2)
                    B_band_28 = round(abs(slope_B) * 28, 2)
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"<div class='card'><div class='kicker'>SPX ± to 8:30</div><div class='metric'>± {sigma1:.2f} (1σ) • ± {sigma2:.2f} (2σ)</div></div>", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"<div class='card'><div class='kicker'>{nameA} ± to 8:30 (28 blocks)</div><div class='metric'>± {A_band_28:.2f}</div></div>", unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"<div class='card'><div class='kicker'>{nameB} ± to 8:30 (28 blocks)</div><div class='metric'>± {B_band_28:.2f}</div></div>", unsafe_allow_html=True)

                    # Save for Plan Card
                    st.session_state["bc_result"] = {
                        "table": out_df,
                        "spx_slope": spx_slope,
                        "b2_dt": b2_dt,
                        "spx_b2": float(spx_b2),
                        "contract_A": {"name": nameA, "slope": slope_A, "ref_price": float(cA_b2), "ref_dt": b2_dt},
                        "contract_B": {"name": nameB, "slope": slope_B, "ref_price": float(cB_b2), "ref_dt": b2_dt},
                    }

        except Exception as e:
            st.error(f"Could not compute projection: {e}")

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 3 — Plan Card (8:00 AM)                                                 ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab3:
    st.subheader("Plan Card — concise session prep (ready by 08:00 AM)")

    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    slot_830    = fmt_ct(datetime.combine(proj_day, time(8, 30)))
    top_830, bot_830, width_830 = fan_levels_for_slot(anchor_close, anchor_time, slot_830)
    chips_830 = confluence_chips(top_830, bot_830,
                                 float(pdh) if pdh is not None else None,
                                 float(pdl) if pdl is not None else None,
                                 (float(onh) if (use_on and onh is not None) else None),
                                 (float(onl) if (use_on and onl is not None) else None),
                                 float(confl_thr))

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='card'><div class='kicker'>Anchor (≤3:00 PM CT)</div><div class='metric'>💠 {anchor_close:.2f}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='card'><div class='kicker'>8:30 Fan</div><div class='metric'>Top {top_830:.2f} • Bottom {bot_830:.2f}</div><div class='kicker'>Width {width_830:.2f}</div></div>", unsafe_allow_html=True)
    with c3:
        sigma1, sigma2, _ = sigma_bands_at_830(anchor_close, prev_day)
        st.markdown(f"<div class='card'><div class='kicker'>Bands to 8:30</div><div class='metric'>±1σ {sigma1:.2f} • ±2σ {sigma2:.2f}</div></div>", unsafe_allow_html=True)

    st.markdown("### Key Slots (SPX & Contracts)")
    key_slots = ["08:30","10:00","13:30","14:30"]
    rows_plan = []
    bc = st.session_state.get("bc_result", None)

    for label in key_slots:
        dt = fmt_ct(datetime.combine(proj_day, datetime.strptime(label, "%H:%M").time()))
        top, bot, width = fan_levels_for_slot(anchor_close, anchor_time, dt)
        row = {
            "⭐":"⭐" if label=="08:30" else "",
            "Time": label,
            "Top": top, "Bottom": bot, "Width": width,
            "Confluence": confluence_chips(
                top, bot,
                float(pdh) if pdh is not None else None,
                float(pdl) if pdl is not None else None,
                (float(onh) if (use_on and onh is not None) else None),
                (float(onl) if (use_on and onl is not None) else None),
                float(confl_thr)
            )
        }
        if bc and "table" in bc:
            tdf = bc["table"]
            # pull SPX proj
            try:
                row["SPX Proj"] = float(tdf.loc[tdf["Time"]==label, "SPX Proj"].iloc[0])
            except Exception:
                row["SPX Proj"] = ""
            # pull contract columns if present
            for key in ["contract_A","contract_B"]:
                info = bc.get(key)
                if info:
                    colname = f"{info['name']} Proj"
                    try:
                        row[colname] = float(tdf.loc[tdf["Time"]==label, colname].iloc[0])
                    except Exception:
                        row[colname] = ""
        else:
            row["SPX Proj"] = ""
        row["Entry Plan"] = "Top touch & bearish close → Sell  |  Bottom touch & bullish close → Buy"
        row["Stops/Targets"] = f"Stop: Top+{float(DEFAULT_STOP_PAD):.2f} / Bottom-{float(DEFAULT_STOP_PAD):.2f} • TP1: opp edge • TP2: edge±width"
        rows_plan.append(row)

    st.dataframe(pd.DataFrame(rows_plan), use_container_width=True, hide_index=True)

    st.markdown("### Notes for 08:30")
    st.write(f"- **Confluence** at 08:30: {chips_830 or 'None'}")
    st.write(f"- **PDH/PDL**: {float(pdh):.2f} / {float(pdl):.2f}" + (f" • **ONH/ONL**: {float(onh):.2f} / {float(onl):.2f}" if use_on else ""))