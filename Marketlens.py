# app.py
# ═══════════════════════════════════════════════════════════════════════════════
# 🔮 SPX PROPHET — SPX-only, focused, no external data
# • SPX slope: ±0.25/30m (fixed); SPX blocks skip 4–5 PM → 3 PM→8:30 AM ≈ 34 → ±8.5 (±1σ), ±17 (±2σ)
# • Contract (single): default slope = −0.33/30m (DESCENDING by default);
#   3 PM→8:30 AM uses 28 valid blocks; BC Forecast (2 bounces) can override slope/direction
# • Inputs: SPX 3 PM, Contract 3 PM, PDH/PDL (+ optional ONH/ONL)
# • BC Forecast: EXACTLY 2 bounces (Asia/Europe) + optional contract prices → project SPX & Contract through RTH
# • Tables (8:30→14:30 every 30m): CLOSE, HIGH, LOW — minimal columns
# • Plan Card (8:00 AM): 4 simple cards with clear plan
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

SLOPE_SPX = 0.25                 # per 30m, fixed (used symmetrically up/down from anchor)
SLOPE_CONTRACT_DEFAULT = -0.33   # per 30m, DEFAULT DESCENDING until BC override

RTH_START = time(8, 30)
RTH_END   = time(14, 30)

DEFAULT_ANCHOR = 6400.00
DEFAULT_CONTRACT_3PM = 20.00

# ───────────────────────────────────────────────────────────────────────────────
# TIME / BLOCK HELPERS
# ───────────────────────────────────────────────────────────────────────────────
def fmt_ct(dt: datetime) -> datetime:
    if dt.tzinfo is None: return CT.localize(dt)
    return dt.astimezone(CT)

def rth_slots_ct(day: date) -> List[datetime]:
    start = fmt_ct(datetime.combine(day, RTH_START))
    end   = fmt_ct(datetime.combine(day, RTH_END))
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur += timedelta(minutes=30)
    return out

def is_maintenance(dt: datetime) -> bool:
    return dt.hour == 16  # CME maintenance 4–5 PM CT

def in_weekend_gap(dt: datetime) -> bool:
    wd = dt.weekday()  # Mon=0..Sun=6
    if wd == 5: return True
    if wd == 6 and dt.hour < 17: return True
    if wd == 4 and dt.hour >= 17: return True
    return False

def count_blocks_spx(t0: datetime, t1: datetime) -> int:
    """SPX 30m blocks, skipping 4–5 PM + weekend gap (count if block END is valid)."""
    t0 = fmt_ct(t0); t1 = fmt_ct(t1)
    if t1 <= t0: return 0
    t, blocks = t0, 0
    while t < t1:
        t_next = t + timedelta(minutes=30)
        if not is_maintenance(t_next) and not in_weekend_gap(t_next):
            blocks += 1
        t = t_next
    return blocks

def count_blocks_contract(anchor_day: date, target_dt: datetime) -> int:
    """
    Contract valid blocks from 3 PM anchor-day to target:
    - Count 3:00→3:30 PM = 1
    - Skip 3:30→7:00 PM
    - Count 7:00 PM → target in 30m steps
    (3 PM → 8:30 AM = 28 blocks)
    """
    target_dt = fmt_ct(target_dt)
    anchor_3pm   = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    anchor_330pm = fmt_ct(datetime.combine(anchor_day, time(15, 30)))
    anchor_7pm   = fmt_ct(datetime.combine(anchor_day, time(19, 0)))
    if target_dt <= anchor_3pm: return 0
    blocks = 1 if target_dt >= anchor_330pm else 0  # 3:00→3:30
    if target_dt > anchor_7pm:
        delta_min = int((target_dt - anchor_7pm).total_seconds() // 60)
        blocks += delta_min // 30
    return blocks

def blocks_simple_30m(d1: datetime, d2: datetime) -> int:
    """Plain 30m step count (used between two overnight bounces and after 8:30)."""
    d1 = fmt_ct(d1); d2 = fmt_ct(d2)
    if d2 <= d1: return 0
    return int((d2 - d1).total_seconds() // (30*60))

# ───────────────────────────────────────────────────────────────────────────────
# FAN & PROJECTIONS
# ───────────────────────────────────────────────────────────────────────────────
def fan_levels_for_slot(anchor_close: float, anchor_time: datetime, slot_dt: datetime) -> Tuple[float,float]:
    blocks = count_blocks_spx(anchor_time, slot_dt)
    top = round(anchor_close + SLOPE_SPX * blocks, 2)
    bot = round(anchor_close - SLOPE_SPX * blocks, 2)
    return top, bot

def sigma_bands_at_830(anchor_close: float, anchor_day: date) -> Tuple[float, float, int]:
    anchor_3pm = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    next_830   = fmt_ct(datetime.combine(anchor_day + timedelta(days=1), time(8, 30)))
    blocks_830 = count_blocks_spx(anchor_3pm, next_830)  # ≈34
    move = SLOPE_SPX * blocks_830
    return round(move, 2), round(2*move, 2), blocks_830  # ±move, ±2*move

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
hr { border-top: 1px solid var(--border); }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# SIDEBAR — Inputs (PDH/PDL visible)
# ───────────────────────────────────────────────────────────────────────────────
st.sidebar.title("🔧 Settings")

today_ct = fmt_ct(datetime.now()).date()
prev_day = st.sidebar.date_input("Previous Trading Day", value=today_ct - timedelta(days=1))
proj_day = st.sidebar.date_input("Projection Day", value=prev_day + timedelta(days=1))

anchor_close = st.sidebar.number_input("SPX Anchor (≤ 3:00 PM CT Close)", value=float(DEFAULT_ANCHOR), step=0.25, format="%.2f")
contract_3pm = st.sidebar.number_input("Contract Price @ 3:00 PM", value=float(DEFAULT_CONTRACT_3PM), step=0.05, format="%.2f")

pdh = st.sidebar.number_input("Previous Day High (PDH)", value=anchor_close + 10.0, step=0.25, format="%.2f")
pdl = st.sidebar.number_input("Previous Day Low (PDL)",  value=anchor_close - 10.0, step=0.25, format="%.2f")

st.sidebar.markdown("---")
use_on = st.sidebar.checkbox("Also track Overnight High/Low (optional)", value=False)
onh = st.sidebar.number_input("Overnight High (ONH)", value=anchor_close + 5.0, step=0.25, format="%.2f", disabled=not use_on)
onl = st.sidebar.number_input("Overnight Low (ONL)",  value=anchor_close - 5.0, step=0.25, format="%.2f", disabled=not use_on)

# Precompute sigma @ 8:30 for header
sigma1, sigma2, spx_blocks_to_830 = sigma_bands_at_830(anchor_close, prev_day)  # ~±8.5, ±17.0

# ───────────────────────────────────────────────────────────────────────────────
# HEADER METRICS
# ───────────────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"<div class='card'><div class='kicker'>Anchor (≤3:00 PM CT)</div><div class='metric'>💠 {anchor_close:.2f}</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='card'><div class='kicker'>SPX to 08:30 ({spx_blocks_to_830} blocks @ {SLOPE_SPX:.2f})</div><div class='metric'>± {sigma1:.2f} (1σ) • ± {sigma2:.2f} (2σ)</div></div>", unsafe_allow_html=True)
with c3:
    # show magnitude to 8:30; direction handled by slope sign and proj logic
    mag_to_830 = abs(SLOPE_CONTRACT_DEFAULT)*28
    st.markdown(f"<div class='card'><div class='kicker'>Contract to 08:30 (28 blocks @ {SLOPE_CONTRACT_DEFAULT:.2f})</div><div class='metric'>≈ ±{mag_to_830:.2f}</div></div>", unsafe_allow_html=True)
with c4:
    extra = f" • ONH/ONL {onh:.2f}/{onl:.2f}" if use_on else ""
    st.markdown(f"<div class='card'><div class='kicker'>PDH / PDL</div><div class='metric'>{pdh:.2f} / {pdl:.2f}</div><div class='kicker'>{extra}</div></div>", unsafe_allow_html=True)

st.markdown("---")

# ───────────────────────────────────────────────────────────────────────────────
# TABS
# ───────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["SPX Anchors", "BC Forecast", "Plan Card"])

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 1 — SPX Anchors (Close, High, Low tables)                               ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab1:
    st.subheader("SPX Anchors — 30-min levels (08:30 → 14:30)")
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))

    # Use BC result if available (recalibrated contract slope/anchor); else defaults
    bc = st.session_state.get("bc_result", None)
    contract_slope = SLOPE_CONTRACT_DEFAULT           # NOTE: negative by default
    contract_ref_dt = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    contract_ref_px = float(contract_3pm)
    if bc and "contract" in bc:
        contract_slope = float(bc["contract"]["slope"])
        contract_ref_dt = bc["contract"]["ref_dt"]
        contract_ref_px = float(bc["contract"]["ref_price"])

    def contract_proj_for_slot(slot_dt: datetime) -> float:
        """
        If ref is 3pm prior day -> use contract's valid-block logic up to 8:30,
        then simple 30m steps from 8:30 to the slot.
        If ref is an overnight bounce -> simple 30m from ref to slot.
        """
        dt_830 = fmt_ct(datetime.combine(proj_day, time(8,30)))
        if contract_ref_dt.time() == time(15,0) and contract_ref_dt.date() == prev_day:
            base_blocks = count_blocks_contract(prev_day, min(slot_dt, dt_830))
            if slot_dt <= dt_830:
                total_blocks = base_blocks
            else:
                total_blocks = base_blocks + blocks_simple_30m(dt_830, slot_dt)
        else:
            total_blocks = blocks_simple_30m(contract_ref_dt, slot_dt)
        return round(contract_ref_px + contract_slope * total_blocks, 2)

    # Tables
    rows_close, rows_high, rows_low = [], [], []

    for slot in rth_slots_ct(proj_day):
        tlabel = slot.strftime("%H:%M")
        top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot)

        # SPX projection from BC (if available)
        spx_proj_val = ""
        if bc and "table" in bc:
            try:
                spx_proj_val = float(bc["table"].loc[bc["table"]["Time"]==tlabel, "SPX Proj"].iloc[0])
            except Exception:
                spx_proj_val = ""

        # Contract projection (will DESCEND with negative default slope)
        c_proj = contract_proj_for_slot(slot)

        rows_close.append({
            "⭐": "⭐" if tlabel=="08:30" else "",
            "Time": tlabel,
            "Top": top,
            "Bottom": bot,
            "SPX Proj (if BC)": spx_proj_val,
            "Contract Proj": c_proj,
        })
        rows_high.append({
            "⭐": "⭐" if tlabel=="08:30" else "",
            "Time": tlabel,
            "Top": top,
            "Contract Proj": c_proj,
        })
        rows_low.append({
            "⭐": "⭐" if tlabel=="08:30" else "",
            "Time": tlabel,
            "Bottom": bot,
            "Contract Proj": c_proj,
        })

    st.markdown("### Close Table")
    st.dataframe(pd.DataFrame(rows_close), use_container_width=True, hide_index=True)

    st.markdown("### High Table")
    st.dataframe(pd.DataFrame(rows_high), use_container_width=True, hide_index=True)

    st.markdown("### Low Table")
    st.dataframe(pd.DataFrame(rows_low), use_container_width=True, hide_index=True)

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 2 — BC Forecast (EXACTLY 2 bounces)                                     ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab2:
    st.subheader("BC Forecast — Fit from 2 Overnight Bounces (Asia/Europe)")

    overnight_start = fmt_ct(datetime.combine(prev_day, time(21, 0)))
    overnight_end   = fmt_ct(datetime.combine(proj_day, time(7, 0)))
    # Build list of 30m slots from 21:00 → 07:00 CT
    tmp_slots, cur = [], overnight_start
    while cur <= overnight_end:
        tmp_slots.append(cur)
        cur += timedelta(minutes=30)
    overnight_slots = [dt.strftime("%Y-%m-%d %H:%M") for dt in tmp_slots]

    with st.form("bc_form", clear_on_submit=False):
        st.markdown("**Select two 30-min slots & enter SPX prices**")
        c1, c2 = st.columns(2)
        with c1:
            b1_sel = st.selectbox("Bounce #1 (CT)", overnight_slots, index=0, key="bc_b1")
            spx_b1 = st.number_input("SPX @ Bounce #1", value=anchor_close, step=0.25, format="%.2f")
        with c2:
            b2_sel = st.selectbox("Bounce #2 (CT)", overnight_slots, index=min(6, len(overnight_slots)-1), key="bc_b2")
            spx_b2 = st.number_input("SPX @ Bounce #2", value=anchor_close, step=0.25, format="%.2f")

        st.markdown("---")
        st.markdown("**Contract (optional)** — prices at the SAME two times")
        cA1, cA2 = st.columns(2)
        with cA1:
            c_b1 = st.number_input("Contract Price @ Bounce #1", value=contract_3pm, step=0.05, format="%.2f")
        with cA2:
            c_b2 = st.number_input("Contract Price @ Bounce #2", value=contract_3pm, step=0.05, format="%.2f")

        submitted = st.form_submit_button("📈 Build Forecast")

    if submitted:
        try:
            b1_dt = fmt_ct(datetime.strptime(b1_sel, "%Y-%m-%d %H:%M"))
            b2_dt = fmt_ct(datetime.strptime(b2_sel, "%Y-%m-%d %H:%M"))
            if b2_dt <= b1_dt:
                st.error("Bounce #2 must be after Bounce #1.")
            else:
                spx_blocks = count_blocks_spx(b1_dt, b2_dt)
                if spx_blocks <= 0:
                    st.error("Bounce times must be at least 30 minutes apart.")
                else:
                    spx_slope = (float(spx_b2) - float(spx_b1)) / spx_blocks

                    # Contract slope between the two overnight bounces (simple 30m blocks)
                    bounce_blocks = blocks_simple_30m(b1_dt, b2_dt)
                    contract_slope = SLOPE_CONTRACT_DEFAULT  # start from default (negative)
                    if bounce_blocks > 0 and (c_b2 != c_b1):
                        contract_slope = float((float(c_b2) - float(c_b1)) / bounce_blocks)

                    # Build RTH projections table (SPX & Contract)
                    rows = []
                    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
                    for slot in rth_slots_ct(proj_day):
                        top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot)
                        spx_proj = round(float(spx_b2) + spx_slope * count_blocks_spx(b2_dt, slot), 2)
                        blocks_from_b2 = blocks_simple_30m(b2_dt, slot)
                        c_proj = round(float(c_b2) + contract_slope * blocks_from_b2, 2)
                        rows.append({
                            "⭐": "⭐" if slot.strftime("%H:%M")=="08:30" else "",
                            "Time": slot.strftime("%H:%M"),
                            "Top": top, "Bottom": bot,
                            "SPX Proj": spx_proj,
                            "Contract Proj": c_proj
                        })
                    out_df = pd.DataFrame(rows)
                    st.markdown("### RTH Projection (from 2 bounces)")
                    st.dataframe(out_df, use_container_width=True, hide_index=True)

                    # Bands at 8:30 (magnitude only)
                    spx_band = sigma1
                    c_band_28 = round(abs(contract_slope) * 28, 2)
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        st.markdown(f"<div class='card'><div class='kicker'>SPX ± to 08:30</div><div class='metric'>± {spx_band:.2f} (1σ) • ± {sigma2:.2f} (2σ)</div></div>", unsafe_allow_html=True)
                    with cc2:
                        st.markdown(f"<div class='card'><div class='kicker'>Contract ± to 08:30 (28 blocks)</div><div class='metric'>± {c_band_28:.2f}</div></div>", unsafe_allow_html=True)

                    # Save for other tabs
                    st.session_state["bc_result"] = {
                        "table": out_df,
                        "spx_slope": spx_slope,
                        "b2_dt": b2_dt,
                        "spx_b2": float(spx_b2),
                        "contract": {"slope": contract_slope, "ref_price": float(c_b2), "ref_dt": b2_dt},
                    }

        except Exception as e:
            st.error(f"Could not build forecast: {e}")

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 3 — Plan Card (8:00 AM)                                                 ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab3:
    st.subheader("Plan Card — Clear session plan (ready by 08:00 AM)")

    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    slot_830    = fmt_ct(datetime.combine(proj_day, time(8, 30)))
    top_830, bot_830 = fan_levels_for_slot(anchor_close, anchor_time, slot_830)

    # Pull BC result if exists (for projected values at markers)
    bc = st.session_state.get("bc_result", None)

    # Card 1 — Anchor & Bands
    c1, c2 = st.columns(2)
    with c1:
        on_extra = f" • ONH/ONL {onh:.2f}/{onl:.2f}" if use_on else ""
        st.markdown(f"""
<div class='card'>
  <div class='kicker'>Card 1 — Anchor & Bands</div>
  <div class='metric'>Anchor: {anchor_close:.2f}</div>
  <div class='kicker'>8:30 Fan → Top {top_830:.2f} • Bottom {bot_830:.2f}</div>
  <div class='kicker'>Bands → ±{sigma1:.2f} (1σ) • ±{sigma2:.2f} (2σ)</div>
  <div class='kicker'>PDH / PDL → {pdh:.2f} / {pdl:.2f}{on_extra}</div>
</div>
""", unsafe_allow_html=True)
    with c2:
        # Contract snapshot at 8:30 using either BC slope or default slope from 3 PM
        if bc and "contract" in bc:
            c_slope = float(bc["contract"]["slope"])
            c_ref_dt = bc["contract"]["ref_dt"]
            c_ref_px = float(bc["contract"]["ref_price"])
            blocks = blocks_simple_30m(c_ref_dt, slot_830)
            c_830 = round(c_ref_px + c_slope * blocks, 2)
            slope_used = c_slope
        else:
            # From 3 PM prior-day using 28 valid blocks (NEGATIVE default slope)
            c_830 = round(float(DEFAULT_CONTRACT_3PM if pd.isna(contract_3pm) else contract_3pm) + SLOPE_CONTRACT_DEFAULT * 28, 2)
            slope_used = SLOPE_CONTRACT_DEFAULT

        st.markdown(f"""
<div class='card'>
  <div class='kicker'>Card 2 — Contract Snapshot</div>
  <div class='metric'>3:00 PM: {float(contract_3pm):.2f} → 8:30: {c_830:.2f}</div>
  <div class='kicker'>Slope used: {slope_used:.2f} per 30m (default negative unless BC overrides)</div>
</div>
""", unsafe_allow_html=True)

    # Card 3 — Key Action Levels
    k1, k2 = st.columns(2)
    with k1:
        st.markdown(f"""
<div class='card'>
  <div class='kicker'>Card 3 — Key Action Levels</div>
  <div class='kicker'>Sell from: near Top {top_830:.2f} (or PDH {pdh:.2f} if closer)</div>
  <div class='kicker'>Buy from: near Bottom {bot_830:.2f} (or PDL {pdl:.2f} if closer)</div>
  <div class='kicker'>Stops: just beyond the edge/PDH/PDL</div>
  <div class='kicker'>Targets: opposite edge first; stretch to PDH/PDL if nearer</div>
</div>
""", unsafe_allow_html=True)
    with k2:
        # If BC exists, show projected values at markers
        markers = ["08:30","10:00","13:30","14:30"]
        proj_rows = []
        if bc and "table" in bc:
            tdf = bc["table"]
            for m in markers:
                try:
                    spxv = float(tdf.loc[tdf["Time"]==m, "SPX Proj"].iloc[0])
                except Exception:
                    spxv = np.nan
                try:
                    cv = float(tdf.loc[tdf["Time"]==m, "Contract Proj"].iloc[0])
                except Exception:
                    cv = np.nan
                proj_rows.append({"Time": m, "SPX Proj": spxv, "Contract Proj": cv})
        else:
            for m in markers:
                proj_rows.append({"Time": m, "SPX Proj": "", "Contract Proj": ""})

        st.markdown("<div class='card'><div class='kicker'>Card 4 — Projections @ Key Slots</div></div>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(proj_rows), use_container_width=True, hide_index=True)