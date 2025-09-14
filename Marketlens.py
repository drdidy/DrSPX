# app.py
# ═══════════════════════════════════════════════════════════════════════════════
# 🔮 SPX PROPHET — Minimal, Robust, SPX-only
# • Anchor: prior session ≤ 3:00 PM CT close (user-input; no network fetch)
# • Slopes: SPX = ±0.25 per 30m (fixed); Contracts = ±0.33 per 30m default
# • Blocks: SPX uses 34 blocks 3:00→8:30 (skip 4–5 PM) → ±8.5 (±1σ), ±17 (±2σ)
#           Contracts use 28 blocks 3:00→3:30 (1) + 7:00 PM→8:30 AM (27) → ±9.24 at 0.33
# • BC Forecast: exactly 2 bounces (21:00–07:00 CT) + (optional) 1–2 contracts’ prices at both bounces
#                → fit slopes; project SPX & contracts across RTH (8:30–14:30)
# • Tables: Close table & High/Low table for every 30m slot; ⭐ highlight 8:30
# • Plan Card: concise 8:00 AM prep using the above
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, date, time, timedelta
from typing import List, Optional, Tuple

# ───────────────────────────────────────────────────────────────────────────────
# CONFIG & CONSTANTS
# ───────────────────────────────────────────────────────────────────────────────
CT = pytz.timezone("America/Chicago")

SLOPE_SPX = 0.25          # per 30m (fixed)
SLOPE_CONTRACT_DEFAULT = 0.33  # per 30m (default; overridden by two prices)

RTH_START = time(8, 30)
RTH_END   = time(14, 30)

# UI defaults
DEFAULT_ANCHOR = 6400.00
DEFAULT_PAD_RANGE = 2.0   # pad for High/Low table (intrabar wiggle)
DEFAULT_STOP_PAD = 2.0    # stop distance beyond edge

# ───────────────────────────────────────────────────────────────────────────────
# TIME / BLOCK HELPERS
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

def is_maintenance(dt: datetime) -> bool:
    # CME maintenance 4–5 PM CT (we skip the *ending* of each 30m block)
    return dt.hour == 16

def in_weekend_gap(dt: datetime) -> bool:
    # Fri ≥ 17:00 → Sun < 17:00 is excluded (for completeness)
    wd = dt.weekday()
    if wd == 5: return True
    if wd == 6 and dt.hour < 17: return True
    if wd == 4 and dt.hour >= 17: return True
    return False

def count_blocks_spx(anchor_time: datetime, target_time: datetime) -> int:
    """Count 30m blocks for SPX from anchor → target, skipping 4–5 PM + weekend gap."""
    anchor_time = fmt_ct(anchor_time); target_time = fmt_ct(target_time)
    if target_time <= anchor_time: return 0
    t = anchor_time
    blocks = 0
    while t < target_time:
        t_next = t + timedelta(minutes=30)
        if not is_maintenance(t_next) and not in_weekend_gap(t_next):
            blocks += 1
        t = t_next
    return blocks

def count_blocks_contract(anchor_day: date, target_dt: datetime) -> int:
    """
    Contract valid overnight blocks from 3:00 PM anchor-day to target_dt:
    • Count 3:00→3:30 PM = 1 block
    • Skip 3:30 PM → 7:00 PM
    • Count 7:00 PM (anchor-day) → target_dt in 30m steps
    Assumes target_dt is on the projection day (next trading day).
    """
    target_dt = fmt_ct(target_dt)
    anchor_3pm   = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    anchor_330pm = fmt_ct(datetime.combine(anchor_day, time(15, 30)))
    anchor_7pm   = fmt_ct(datetime.combine(anchor_day, time(19, 0)))

    if target_dt <= anchor_3pm: return 0
    blocks = 0
    # 3:00 → 3:30
    if target_dt > anchor_3pm:
        blocks += 1 if target_dt >= anchor_330pm else 0
    # 7:00 PM → target
    if target_dt > anchor_7pm:
        delta_min = int((target_dt - anchor_7pm).total_seconds() // 60)
        blocks += delta_min // 30
    return blocks

def gen_slots(start_dt: datetime, end_dt: datetime, step_min: int = 30) -> List[datetime]:
    start_dt = fmt_ct(start_dt); end_dt = fmt_ct(end_dt)
    out = []
    cur = start_dt
    while cur <= end_dt:
        out.append(cur)
        cur += timedelta(minutes=step_min)
    return out

# ───────────────────────────────────────────────────────────────────────────────
# FAN & PROJECTIONS
# ───────────────────────────────────────────────────────────────────────────────
def fan_levels_for_slot(anchor_close: float, anchor_time: datetime, slot_dt: datetime) -> Tuple[float, float, float]:
    blocks = count_blocks_spx(anchor_time, slot_dt)
    top = anchor_close + SLOPE_SPX * blocks
    bot = anchor_close - SLOPE_SPX * blocks
    return round(top, 2), round(bot, 2), round(top - bot, 2)

def sigma_bands_at_830(anchor_close: float, anchor_day: date) -> Tuple[float, float]:
    # SPX: 3:00 PM → 8:30 AM = 34 valid blocks → ±8.5
    anchor_3pm = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    next_830   = fmt_ct(datetime.combine(anchor_day + timedelta(days=1), time(8, 30)))
    blocks_830 = count_blocks_spx(anchor_3pm, next_830)  # should be 34
    move = SLOPE_SPX * blocks_830
    return round(move, 2), round(2 * move, 2)  # (±1σ, ±2σ)

def project_line_from_two_points(p1_dt: datetime, p1_price: float,
                                 p2_dt: datetime, p2_price: float,
                                 block_counter) -> Tuple[float, datetime]:
    """Return slope per 30m using supplied block_counter between p1→p2, anchored at p2."""
    b = block_counter(p1_dt, p2_dt) if block_counter != count_blocks_spx else block_counter(p1_dt, p2_dt)  # noqa
    if b <= 0: return 0.0, p2_dt
    slope = (p2_price - p1_price) / b
    return float(slope), p2_dt

def project_value_from_ref(ref_dt: datetime, ref_price: float, slope_per_block: float,
                           target_dt: datetime, block_counter) -> float:
    b = block_counter(ref_dt, target_dt) if block_counter != count_blocks_spx else block_counter(ref_dt, target_dt)  # noqa
    return round(ref_price + slope_per_block * b, 2)

# ───────────────────────────────────────────────────────────────────────────────
# UI LAYOUT
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="🔮 SPX Prophet", page_icon="📈", layout="wide")

st.markdown("""
<style>
:root { --brand:#2563eb; --surface:#ffffff; --muted:#f8fafc; --text:#0f172a; --sub:#475569; --border:#e2e8f0; }
html, body { background: var(--muted); color: var(--text); }
.card { background: rgba(255,255,255,0.9); border:1px solid var(--border); border-radius:16px; padding:16px; box-shadow:0 12px 32px rgba(2,6,23,0.07); }
.metric { font-size:1.8rem; font-weight:700; }
.kicker { color:var(--sub); font-size:.85rem; }
.badge { background:#e2e8f0; border:1px solid #cbd5e1; border-radius:999px; padding:2px 8px; font-weight:600; font-size:.75rem; }
.dataframe { border-radius:12px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# SIDEBAR — Global Inputs
# ───────────────────────────────────────────────────────────────────────────────
st.sidebar.title("🔧 Settings")

today_ct = fmt_ct(datetime.now()).date()
prev_day = st.sidebar.date_input("Previous Trading Day", value=today_ct - timedelta(days=1))
proj_day = st.sidebar.date_input("Projection Day", value=prev_day + timedelta(days=1))

anchor_close = st.sidebar.number_input("Prev Day ≤ 3:00 PM CT Close (SPX)", value=float(DEFAULT_ANCHOR), step=0.25, format="%.2f")

with st.sidebar.expander("Risk Pads (for entries/exits)", expanded=False):
    intrabar_pad = st.number_input("Intrabar Range Pad (pts)", value=float(DEFAULT_PAD_RANGE), step=0.25, format="%.2f")
    stop_pad     = st.number_input("Stop Pad beyond Edge (pts)", value=float(DEFAULT_STOP_PAD), step=0.25, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.caption(f"SPX slope = ±{SLOPE_SPX:.2f} / 30m • Contract default slope = ±{SLOPE_CONTRACT_DEFAULT:.2f} / 30m")

# Precompute sigma @ 8:30 for header
sigma1, sigma2 = sigma_bands_at_830(anchor_close, prev_day)

# ───────────────────────────────────────────────────────────────────────────────
# HEADER METRICS
# ───────────────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"<div class='card'><div class='kicker'>Anchor (≤ 3:00 PM CT)</div><div class='metric'>💠 {anchor_close:.2f}</div></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='card'><div class='kicker'>±1σ to 8:30</div><div class='metric'>± {sigma1:.2f}</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='card'><div class='kicker'>±2σ to 8:30</div><div class='metric'>± {sigma2:.2f}</div></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='card'><div class='kicker'>Contracts (28 blocks @ {SLOPE_CONTRACT_DEFAULT:.2f})</div><div class='metric'>± {SLOPE_CONTRACT_DEFAULT*28:.2f}</div></div>", unsafe_allow_html=True)

st.markdown("---")

# ───────────────────────────────────────────────────────────────────────────────
# TABS
# ───────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["SPX Anchors", "BC Forecast", "Plan Card"])

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 1 — SPX Anchors                                                         ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab1:
    st.subheader("SPX Anchors — Entries & Exits (8:30 → 14:30, every 30m)")
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))

    rows_close = []
    rows_hilo  = []
    for slot in rth_slots_ct(proj_day):
        top, bot, width = fan_levels_for_slot(anchor_close, anchor_time, slot)

        # Close table: generic plan triggers (your edge logic summarized as prompts)
        entry_plan  = "Top touch & bearish close → Sell  |  Bottom touch & bullish close → Buy"
        entry_trig  = "Touch edge + candle closes inside/above(Top) or inside/below(Bottom)"
        stop_txt    = f"If selling: Top+{stop_pad:.2f}  |  If buying: Bottom-{stop_pad:.2f}"
        tp1_txt     = "Opposite edge"
        tp2_txt     = "Opposite edge ± fan width (optional)"
        rows_close.append({
            "⭐": "⭐" if slot.strftime("%H:%M") == "08:30" else "",
            "Time": slot.strftime("%H:%M"),
            "Top": top, "Bottom": bot,
            "Entry Plan": entry_plan,
            "Trigger": entry_trig,
            "Stop": stop_txt, "TP1": tp1_txt, "TP2": tp2_txt,
        })

        # High/Low table: show expected excursion zones using a simple intrabar pad
        exp_mid = round((top + bot)/2.0, 2)
        exp_high = round(exp_mid + intrabar_pad, 2)
        exp_low  = round(exp_mid - intrabar_pad, 2)
        rows_hilo.append({
            "⭐": "⭐" if slot.strftime("%H:%M") == "08:30" else "",
            "Time": slot.strftime("%H:%M"),
            "Top": top, "Bottom": bot,
            "Exp High (SPX)": exp_high, "Exp Low (SPX)": exp_low,
            "Entry Zone": f"Sell near Top±{intrabar_pad:.2f}  |  Buy near Bottom±{intrabar_pad:.2f}",
            "Exit Zone": "Mirror side ± pad"
        })

    st.markdown("### Close Table — actionable entries/exits (per 30m)")
    st.dataframe(pd.DataFrame(rows_close), use_container_width=True, hide_index=True)

    st.markdown("### High/Low Table — excursion-based entries/exits (per 30m)")
    st.dataframe(pd.DataFrame(rows_hilo), use_container_width=True, hide_index=True)

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 2 — BC Forecast (EXACTLY 2 bounces)                                     ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab2:
    st.subheader("BC Forecast — Two Overnight Bounces → Project SPX & Contracts")

    # Build slot list for 21:00 (prev_day) → 07:00 (proj_day)
    overnight_start = fmt_ct(datetime.combine(prev_day, time(21, 0)))
    overnight_end   = fmt_ct(datetime.combine(proj_day, time(7, 0)))
    overnight_slots = gen_slots(overnight_start, overnight_end, 30)
    slot_labels = [dt.strftime("%Y-%m-%d %H:%M") for dt in overnight_slots]

    with st.form("bc_form", clear_on_submit=False):
        st.markdown("**Bounce Inputs (required)** — choose two slots and enter SPX prices")
        c1, c2 = st.columns(2)
        with c1:
            b1_sel = st.selectbox("Bounce #1 (slot, CT)", slot_labels, index=0, key="bc_b1")
            spx_b1 = st.number_input("SPX @ Bounce #1", value=anchor_close, step=0.25, format="%.2f")
        with c2:
            b2_sel = st.selectbox("Bounce #2 (slot, CT)", slot_labels, index=min(6, len(slot_labels)-1), key="bc_b2")
            spx_b2 = st.number_input("SPX @ Bounce #2", value=anchor_close, step=0.25, format="%.2f")

        st.markdown("---")
        st.markdown("**Contracts (optional)** — enter prices at the same two bounce times")
        cA1, cA2, cB1, cB2 = st.columns(4)
        with cA1:
            nameA = st.text_input("Contract A (e.g., 6525c)", value="ATM-A")
        with cA2:
            cA_b1 = st.number_input("A price @ B#1", value=10.00, step=0.05, format="%.2f")
        with cB1:
            nameB = st.text_input("Contract B (optional)", value="ATM-B")
        with cB2:
            cB_b1 = st.number_input("B price @ B#1", value=9.50, step=0.05, format="%.2f")
        cA3, cA4, cB3, cB4 = st.columns(4)
        with cA3:
            cA_b2 = st.number_input("A price @ B#2", value=10.50, step=0.05, format="%.2f")
        with cA4:
            cB_b2 = st.number_input("B price @ B#2", value=9.80, step=0.05, format="%.2f")
        st.caption("If either A or B is not truly used, just ignore its columns — default slope 0.33 will apply for projections.")

        submitted = st.form_submit_button("📈 Project")

    if submitted:
        try:
            b1_dt = fmt_ct(datetime.strptime(b1_sel, "%Y-%m-%d %H:%M"))
            b2_dt = fmt_ct(datetime.strptime(b2_sel, "%Y-%m-%d %H:%M"))
            if b2_dt <= b1_dt:
                st.error("Bounce #2 must be after Bounce #1.")
            else:
                # Underlying slope from bounces (use SPX block logic)
                spx_slope, ref_dt = project_line_from_two_points(b1_dt, float(spx_b1), b2_dt, float(spx_b2), count_blocks_spx)

                # Contract slopes from bounces (straight 30m blocks between two bounce times; both are within 21:00–07:00)
                def blocks_simple(d1: datetime, d2: datetime) -> int:
                    d1 = fmt_ct(d1); d2 = fmt_ct(d2)
                    if d2 <= d1: return 0
                    return int((d2 - d1).total_seconds() // (30*60))

                slope_A = SLOPE_CONTRACT_DEFAULT
                slope_B = SLOPE_CONTRACT_DEFAULT
                if all(x is not None for x in [cA_b1, cA_b2]) and (cA_b2 != cA_b1):
                    bA = blocks_simple(b1_dt, b2_dt)
                    if bA > 0:
                        slope_A = float((float(cA_b2) - float(cA_b1)) / bA)
                if all(x is not None for x in [cB_b1, cB_b2]) and (cB_b2 != cB_b1):
                    bB = blocks_simple(b1_dt, b2_dt)
                    if bB > 0:
                        slope_B = float((float(cB_b2) - float(cB_b1)) / bB)

                # Build RTH projections table
                rows = []
                for slot in rth_slots_ct(proj_day):
                    # SPX fan
                    top, bot, width = fan_levels_for_slot(anchor_close, fmt_ct(datetime.combine(prev_day, time(15,0))), slot)

                    # SPX projection from bounce line
                    spx_proj = project_value_from_ref(ref_dt, float(spx_b2), spx_slope, slot, count_blocks_spx)

                    # Contracts projected from B#2 using their slopes (contract blocks forward from B#2)
                    def contract_blocks_from_ref(ref_dt_, tgt_dt_):
                        # both ref (overnight) and target (RTH) use simple 30m steps post 7pm
                        return int((fmt_ct(tgt_dt_) - fmt_ct(ref_dt_)).total_seconds() // (30*60))

                    A_proj = round(float(cA_b2) + slope_A * contract_blocks_from_ref(b2_dt, slot), 2)
                    B_proj = round(float(cB_b2) + slope_B * contract_blocks_from_ref(b2_dt, slot), 2)

                    rows.append({
                        "⭐": "⭐" if slot.strftime("%H:%M") == "08:30" else "",
                        "Time": slot.strftime("%H:%M"),
                        "Top": top, "Bottom": bot,
                        "SPX Proj": spx_proj,
                        f"{nameA} Proj": A_proj,
                        f"{nameB} Proj": B_proj
                    })

                out_df = pd.DataFrame(rows)
                st.markdown("### RTH Projection (SPX & Contracts)")
                st.dataframe(out_df, use_container_width=True, hide_index=True)

                # Bands at 8:30 (SPX 34 blocks; Contracts 28 blocks)
                anchor_3pm = fmt_ct(datetime.combine(prev_day, time(15,0)))
                slot_830   = fmt_ct(datetime.combine(proj_day, time(8,30)))
                spx_blocks_to_830 = count_blocks_spx(anchor_3pm, slot_830)  # ≈34
                A_band_28 = round(abs(slope_A) * 28, 2)
                B_band_28 = round(abs(slope_B) * 28, 2)

                colA, colB, colC = st.columns(3)
                with colA:
                    st.markdown(f"<div class='card'><div class='kicker'>SPX ± to 8:30 ({spx_blocks_to_830} blocks @ 0.25)</div><div class='metric'>± {SLOPE_SPX*spx_blocks_to_830:.2f}</div></div>", unsafe_allow_html=True)
                with colB:
                    st.markdown(f"<div class='card'><div class='kicker'>{nameA} ± to 8:30 (28 blocks)</div><div class='metric'>± {A_band_28:.2f}</div></div>", unsafe_allow_html=True)
                with colC:
                    st.markdown(f"<div class='card'><div class='kicker'>{nameB} ± to 8:30 (28 blocks)</div><div class='metric'>± {B_band_28:.2f}</div></div>", unsafe_allow_html=True)

                # Save for Plan Card
                st.session_state["bc_result"] = {
                    "table": out_df,
                    "spx_slope": spx_slope,
                    "contract_A": {"name": nameA, "slope": slope_A, "ref_price": float(cA_b2), "ref_dt": b2_dt},
                    "contract_B": {"name": nameB, "slope": slope_B, "ref_price": float(cB_b2), "ref_dt": b2_dt},
                }

        except Exception as e:
            st.error(f"Could not compute projection: {e}")

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 3 — Plan Card (8:00 AM)                                                 ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab3:
    st.subheader("Plan Card — concise session prep (ready for 8:00 AM)")

    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    slot_830    = fmt_ct(datetime.combine(proj_day, time(8, 30)))
    fan_top_830, fan_bot_830, width_830 = fan_levels_for_slot(anchor_close, anchor_time, slot_830)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='card'><div class='kicker'>Anchor</div><div class='metric'>💠 {anchor_close:.2f}</div><div class='kicker'>Prev ≤ 3:00 PM CT</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='card'><div class='kicker'>8:30 Fan</div><div class='metric'>Top {fan_top_830:.2f} • Bottom {fan_bot_830:.2f}</div><div class='kicker'>Width {width_830:.2f}</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='card'><div class='kicker'>Bands to 8:30</div><div class='metric'>±1σ {sigma1:.2f} • ±2σ {sigma2:.2f}</div></div>", unsafe_allow_html=True)

    st.markdown("### Key Slots (SPX & Contracts)")
    key_slots = ["08:30","10:00","13:30","14:30"]
    rows_plan = []
    # Pull BC result if available
    bc = st.session_state.get("bc_result", None)

    # Contract defaults if no BC inputs
    def contract_projection_from_3pm(name: str, slope: float, slot_dt: datetime) -> float:
        # Requires you to know the 3pm contract price; since we don't fetch, we leave blank unless BC gave a ref
        return np.nan

    for label in key_slots:
        dt = fmt_ct(datetime.combine(proj_day, datetime.strptime(label, "%H:%M").time()))
        top, bot, width = fan_levels_for_slot(anchor_close, anchor_time, dt)

        row = {"⭐":"⭐" if label=="08:30" else "", "Time": label, "Top": top, "Bottom": bot}

        if bc:
            # SPX projected from BC slope (anchored at B#2)
            spx_proj = project_value_from_ref(
                bc["table"].iloc[0:0].get("dummy", pd.Series()).index.min() or fmt_ct(datetime.combine(prev_day, time(21,0))),  # dummy for signature
                # We anchored spx line at b2_dt with spx_b2 in the tab above; stash slope & reconstruct via fan at need.
                # Simpler: reuse the already-rendered table if available:
                0.0, 0.0, dt, count_blocks_spx
            )
            # Instead of recomputing, pull from saved table if present:
            try:
                spx_row = bc["table"][bc["table"]["Time"] == label]
                if not spx_row.empty:
                    row["SPX Proj"] = float(spx_row["SPX Proj"].iloc[0])
                else:
                    row["SPX Proj"] = np.nan
            except Exception:
                row["SPX Proj"] = np.nan

            # Contracts from saved table
            for key in ["contract_A","contract_B"]:
                info = bc.get(key, None)
                if info:
                    colname = f"{info['name']} Proj"
                    try:
                        row[colname] = float(bc["table"].loc[bc["table"]["Time"]==label, colname].iloc[0])
                    except Exception:
                        row[colname] = np.nan
        else:
            row["SPX Proj"] = np.nan

        # Entry/Exit outline for the slot
        row["Entry Plan"] = "Top touch & bearish close → Sell  |  Bottom touch & bullish close → Buy"
        row["Stops / Targets"] = f"Stop: Top+{stop_pad:.2f} or Bottom-{stop_pad:.2f} • TP1: opposite edge • TP2: edge±width"
        rows_plan.append(row)

    st.dataframe(pd.DataFrame(rows_plan), use_container_width=True, hide_index=True)

    st.caption("Tip: use BC Forecast to populate SPX & contract projections in this Plan Card. Default slopes are fixed (SPX 0.25, Contracts 0.33).")