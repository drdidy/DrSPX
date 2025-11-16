# spx_prophet_v7_stunning_fixed.py
# SPX Prophet v7.0 — STUNNING LIGHT MODE EDITION (with robust contract handling)

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet v7.0"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475
BASE_DATE = datetime(2000, 1, 1, 15, 0)


# ===============================
# STUNNING LIGHT MODE UI (UNCHANGED)
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
    /* ------------- ALL YOUR CSS EXACTLY AS BEFORE ------------- */
    /* I’m leaving it unchanged, just truncated here for brevity
       in this explanation. In your real file, keep your full CSS. */
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    st.markdown("""
    <div class="hero-header">
        <div class="status-indicator">System Active ✓</div>
        <h1 class="hero-title">SPX Prophet v7.0</h1>
        <p class="hero-subtitle">Where Structure Becomes Foresight.</p>
    </div>
    """, unsafe_allow_html=True)


def card(title: str, sub: Optional[str] = None, badge: Optional[str] = None, icon: str = ""):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if icon:
        st.markdown(f"<span class='icon-large'>{icon}</span>", unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str):
    return f"""
    <div class='spx-metric'>
        <div class='spx-metric-label'>{label}</div>
        <div class='spx-metric-value'>{value}</div>
    </div>
    """


def section_header(text: str):
    st.markdown(f"<h3 class='section-header'>{text}</h3>", unsafe_allow_html=True)


# ===============================
# SMALL HELPER: SAFE TIME READING
# ===============================

def get_time_from_session(key: str, default: dtime) -> dtime:
    """
    Safely pull a time value from st.session_state.
    Handles cases where an older run stored datetime or string.
    """
    v = st.session_state.get(key, default)

    if isinstance(v, dtime):
        return v
    if isinstance(v, datetime):
        return v.time()
    if isinstance(v, str):
        # Try "HH:MM:SS" then "HH:MM"
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(v, fmt).time()
            except ValueError:
                pass
    # Fallback
    return default


# ===============================
# TIME / BLOCK HELPERS
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


# ===============================
# CHANNEL ENGINE
# ===============================

def build_channel(
    high_price: float,
    high_time: dtime,
    low_price: float,
    low_time: dtime,
    slope_sign: int,
) -> Tuple[pd.DataFrame, float]:
    s = slope_sign * SLOPE_MAG
    dt_hi = align_30min(make_dt_from_time(high_time))
    dt_lo = align_30min(make_dt_from_time(low_time))
    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)
    b_top = high_price - s * k_hi
    b_bottom = low_price - s * k_lo
    channel_height = b_top - b_bottom
    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        top = s * k + b_top
        bottom = s * k + b_bottom
        rows.append({
            "Time": dt.strftime("%H:%M"),
            "Top Rail": round(top, 4),
            "Bottom Rail": round(bottom, 4),
        })
    df = pd.DataFrame(rows)
    return df, round(channel_height, 4)


# ===============================
# CONTRACT ENGINE
# ===============================

def build_contract_projection(
    anchor_a_time: dtime,
    anchor_a_price: float,
    anchor_b_time: dtime,
    anchor_b_price: float,
) -> Tuple[pd.DataFrame, float]:
    dt_a = align_30min(make_dt_from_time(anchor_a_time))
    dt_b = align_30min(make_dt_from_time(anchor_b_time))
    k_a = blocks_from_base(dt_a)
    k_b = blocks_from_base(dt_b)
    if k_a == k_b:
        slope = 0.0
    else:
        slope = (anchor_b_price - anchor_a_price) / (k_b - k_a)
    b_contract = anchor_a_price - slope * k_a
    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        price = slope * k + b_contract
        rows.append({
            "Time": dt.strftime("%H:%M"),
            "Contract Price": round(price, 4),
        })
    df = pd.DataFrame(rows)
    return df, round(slope, 6)


# ===============================
# DAILY FORESIGHT HELPERS
# ===============================

def get_active_channel() -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[float]]:
    mode = st.session_state.get("channel_mode")
    df_asc = st.session_state.get("channel_asc_df")
    df_desc = st.session_state.get("channel_desc_df")
    h_asc = st.session_state.get("channel_asc_height")
    h_desc = st.session_state.get("channel_desc_height")

    if mode == "Ascending":
        return "Ascending", df_asc, h_asc
    if mode == "Descending":
        return "Descending", df_desc, h_desc
    if mode == "Both":
        scenario = st.selectbox(
            "Active scenario for Foresight",
            ["Ascending", "Descending"],
            index=0,
            key="foresight_scenario",
        )
        if scenario == "Ascending":
            return "Ascending", df_asc, h_asc
        else:
            return "Descending", df_desc, h_desc
    return None, None, None


# ===============================
# MAIN APP
# ===============================

def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(f"<span class='spx-sub' style='font-size:1.05rem;'>{TAGLINE}</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("#### ⚡ Core Slope")
        st.write(f"SPX rail slope magnitude: **{SLOPE_MAG} pts / 30 min**")
        st.caption("All calculations use a uniform 30-minute grid.")
        
        st.markdown("---")
        st.markdown("#### 📋 Notes")
        st.caption(
            "Underlying maintenance: 16:00–17:00 CT\n\n"
            "Contracts maintenance: 16:00–19:00 CT\n\n"
            "RTH projection window: 08:30–14:30 CT."
        )

    hero()

    tabs = st.tabs([
        "🧱 SPX Channel Setup",
        "📐 Contract Slope Setup",
        "🔮 Daily Foresight Card",
        "ℹ️ About",
    ])

    # ==================================
    # TAB 1 — SPX CHANNEL SETUP
    # ==================================
    with tabs[0]:
        card(
            "SPX Channel Setup",
            "Define your engulfing pivots, pick the channel direction, and project parallel rails across the session.",
            badge="Rails Engine",
            icon="🧱"
        )

        section_header("⚙️ Pivots Configuration")
        st.markdown(
            "<p class='spx-sub' style='margin-bottom:24px;'>"
            "Choose the highest and lowest engulfing reversals you trust between 15:00 and 07:30 CT."
            "</p>",
            unsafe_allow_html=True
        )
        
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("#### 📈 High Pivot")
            high_price = st.number_input(
                "High pivot price",
                value=5200.0,
                step=0.25,
                key="pivot_high_price",
            )
            high_time = st.time_input(
                "High pivot time (CT)",
                value=dtime(19, 30),
                step=1800,
                key="pivot_high_time",
            )
        with c2:
            st.markdown("#### 📉 Low Pivot")
            low_price = st.number_input(
                "Low pivot price",
                value=5100.0,
                step=0.25,
                key="pivot_low_price",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
                value=dtime(3, 0),
                step=1800,
                key="pivot_low_time",
            )

        section_header("📊 Channel Regime")
        mode = st.radio(
            "Select your channel mode",
            ["Ascending", "Descending", "Both"],
            index=0,
            key="channel_mode",
            horizontal=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("⚡ Build Channel", key="build_channel_btn", use_container_width=True):
                if mode in ("Ascending", "Both"):
                    df_asc, h_asc = build_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=+1,
                    )
                    st.session_state["channel_asc_df"] = df_asc
                    st.session_state["channel_asc_height"] = h_asc
                else:
                    st.session_state["channel_asc_df"] = None
                    st.session_state["channel_asc_height"] = None

                if mode in ("Descending", "Both"):
                    df_desc, h_desc = build_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=-1,
                    )
                    st.session_state["channel_desc_df"] = df_desc
                    st.session_state["channel_desc_height"] = h_desc
                else:
                    st.session_state["channel_desc_df"] = None
                    st.session_state["channel_desc_height"] = None

                st.success("✨ Channel generated successfully! Review the tables and the Daily Foresight tab.")

        df_asc = st.session_state.get("channel_asc_df")
        df_desc = st.session_state.get("channel_desc_df")
        h_asc = st.session_state.get("channel_asc_height")
        h_desc = st.session_state.get("channel_desc_height")

        section_header("📊 Channel Projections • RTH 08:30–14:30 CT")
        
        if df_asc is None and df_desc is None:
            st.info("📊 Build at least one channel to view projections.")
        else:
            if df_asc is not None:
                st.markdown("<h4 style='font-size:1.4rem; margin:20px 0;'>📈 Ascending Channel</h4>", unsafe_allow_html=True)
                c_top = st.columns([3, 1], gap="large")
                with c_top[0]:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True, height=400)
                with c_top[1]:
                    st.markdown(metric_card("Channel Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download CSV",
                        df_asc.to_csv(index=False).encode(),
                        "spx_ascending_rails.csv",
                        "text/csv",
                        key="dl_asc_channel",
                        use_container_width=True,
                    )

            if df_desc is not None:
                st.markdown("<h4 style='font-size:1.4rem; margin:28px 0 20px;'>📉 Descending Channel</h4>", unsafe_allow_html=True)
                c_bot = st.columns([3, 1], gap="large")
                with c_bot[0]:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True, height=400)
                with c_bot[1]:
                    st.markdown(metric_card("Channel Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download CSV",
                        df_desc.to_csv(index=False).encode(),
                        "spx_descending_rails.csv",
                        "text/csv",
                        key="dl_desc_channel",
                        use_container_width=True,
                    )

        end_card()

    # ==================================
    # TAB 2 — CONTRACT SLOPE SETUP
    # ==================================
    with tabs[1]:
        card(
            "Contract Slope Setup",
            "Use two contract prices to define a simple line on the same time grid as the rails.",
            badge="Contract Engine",
            icon="📐"
        )

        # SAFE: read pivot times from session with type normalization
        ph_time: dtime = get_time_from_session("pivot_high_time", dtime(15, 0))
        pl_time: dtime = get_time_from_session("pivot_low_time", dtime(3, 0))

        section_header("⚓ Anchor A — Contract Origin")
        anchor_a_source = st.radio(
            "Use which time for Anchor A",
            ["High pivot time", "Low pivot time", "Custom time"],
            index=0,
            key="contract_anchor_a_source",
            horizontal=True,
        )

        if anchor_a_source == "High pivot time":
            anchor_a_time = ph_time
            st.markdown(
                f"<div class='muted'>✓ Anchor A time set to high pivot time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT</div>",
                unsafe_allow_html=True,
            )
        elif anchor_a_source == "Low pivot time":
            anchor_a_time = pl_time
            st.markdown(
                f"<div class='muted'>✓ Anchor A time set to low pivot time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT</div>",
                unsafe_allow_html=True,
            )
        else:
            anchor_a_time = st.time_input(
                "Custom Anchor A time (CT)",
                value=dtime(1, 0),
                step=1800,
                key="contract_anchor_a_time_custom",
            )

        anchor_a_price = st.number_input(
            "Contract price at Anchor A time",
            value=10.0,
            step=0.1,
            key="contract_anchor_a_price",
        )

        section_header("⚓ Anchor B — Second Contract Point")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            anchor_b_time = st.time_input(
                "Anchor B time (CT)",
                value=dtime(7, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
        with c2:
            anchor_b_price = st.number_input(
                "Contract price at Anchor B time",
                value=8.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("⚡ Build Contract", key="build_contract_btn", use_container_width=True):
                df_contract, slope_contract = build_contract_projection(
                    anchor_a_time=anchor_a_time,
                    anchor_a_price=anchor_a_price,
                    anchor_b_time=anchor_b_time,
                    anchor_b_price=anchor_b_price,
                )
                st.session_state["contract_df"] = df_contract
                st.session_state["contract_slope"] = slope_contract
                st.session_state["contract_anchor_a_time"] = anchor_a_time
                st.session_state["contract_anchor_a_price"] = anchor_a_price
                st.session_state["contract_anchor_b_time"] = anchor_b_time
                st.session_state["contract_anchor_b_price"] = anchor_b_price
                st.success("✨ Contract projection generated successfully! Review the table and Daily Foresight tab.")

        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        section_header("📊 Contract Projection • RTH 08:30–14:30 CT")
        
        if df_contract is None:
            st.info("📊 Build a contract projection to see projected prices.")
        else:
            c_top = st.columns([3, 1], gap="large")
            with c_top[0]:
                st.dataframe(df_contract, use_container_width=True, hide_index=True, height=400)
            with c_top[1]:
                st.markdown(metric_card("Contract Slope", f"{slope_contract:+.4f} / 30m"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "📥 Download CSV",
                    df_contract.to_csv(index=False).encode(),
                    "contract_projection.csv",
                    "text/csv",
                    key="dl_contract",
                    use_container_width=True,
                )

        end_card()

    # ==================================
    # TAB 3 — DAILY FORESIGHT CARD
    # ==================================
    with tabs[2]:
        card(
            "Daily Foresight Card",
            "Rails and contract line combined into a simple time-based playbook.",
            badge="Foresight",
            icon="🔮"
        )

        df_mode, df_ch, h_ch = get_active_channel()
        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        if df_ch is None or h_ch is None:
            st.warning("⚠️ No active channel found. Build a channel in the SPX Channel Setup tab first.")
            end_card()
        elif df_contract is None or slope_contract is None:
            st.warning("⚠️ No contract projection found. Build one in the Contract Slope Setup tab first.")
            end_card()
        else:
            merged = df_ch.merge(df_contract, on="Time", how="left")
            blocks_for_channel = h_ch / SLOPE_MAG if SLOPE_MAG != 0 else 0.0
            contract_move_per_channel = slope_contract * blocks_for_channel if blocks_for_channel != 0 else 0.0
            contract_gain_abs = abs(contract_move_per_channel)

            section_header("📊 Structure Summary")
            c1, c2, c3 = st.columns(3, gap="large")
            with c1:
                st.markdown(metric_card("Active Channel", df_mode or "Not set"), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_card("Channel Height", f"{h_ch:.2f} pts"), unsafe_allow_html=True)
            with c3:
                st.markdown(metric_card("Contract Change", f"{contract_gain_abs:.2f} units"), unsafe_allow_html=True)

            section_header("📈 Inside Channel Play")
            st.markdown(f"""
            <div class='spx-sub' style='font-size:1.05rem; line-height:1.8;'>
              <p><strong style='color:#6366f1; font-size:1.15rem;'>🟢 Long Idea</strong> → Buy at the lower rail, exit at the upper rail</p>
              <ul style='margin-left:24px;'>
                <li>Underlying move: about <strong style='color:#10b981;'>{h_ch:.2f} points</strong> in your favor</li>
                <li>Typical contract change for a full swing: about <strong style='color:#10b981;'>{contract_gain_abs:.2f} units</strong> based on current slope</li>
              </ul>

              <p><strong style='color:#6366f1; font-size:1.15rem;'>🔴 Short Idea</strong> → Sell at the upper rail, exit at the lower rail</p>
              <ul style='margin-left:24px;'>
                <li>Underlying move: about <strong style='color:#ef4444;'>{h_ch:.2f} points</strong> in your favor, opposite direction</li>
                <li>Same contract size of move in the opposite direction</li>
              </ul>

              <p style='margin-top:16px; color:#64748b;'><em>This is a structural size of move, not a full options model. Real moves may be larger due to volatility and time effects.</em></p>
            </div>
            """, unsafe_allow_html=True)

            section_header("💥 Breakout and Breakdown Ideas")
            st.markdown(f"""
            <div class='spx-sub' style='font-size:1.05rem; line-height:1.8;'>
              <p><strong style='color:#6366f1; font-size:1.15rem;'>🚀 Breakout Above Upper Rail</strong></p>
              <ul style='margin-left:24px;'>
                <li>Entry on clean retest of the upper rail from above</li>
                <li>Continuation target: roughly one additional channel height beyond the rail</li>
                <li>Same channel-size contract move estimate used as a guide</li>
              </ul>

              <p><strong style='color:#6366f1; font-size:1.15rem;'>⬇️ Breakdown Below Lower Rail</strong></p>
              <ul style='margin-left:24px;'>
                <li>Entry on clean retest of the lower rail from below</li>
                <li>Continuation target: roughly one additional channel height below that rail</li>
              </ul>
            </div>
            """, unsafe_allow_html=True)

            section_header("🧮 Contract Trade Estimator")

            times = merged["Time"].tolist()
            if times:
                col_e, col_x = st.columns(2, gap="large")
                with col_e:
                    entry_time = st.selectbox(
                        "Entry time when the rail is touched",
                        times,
                        index=0,
                        key="foresight_entry_time",
                    )
                with col_x:
                    exit_time = st.selectbox(
                        "Exit time",
                        times,
                        index=min(len(times) - 1, 4),
                        key="foresight_exit_time",
                    )

                entry_row = merged[merged["Time"] == entry_time].iloc[0]
                exit_row = merged[merged["Time"] == exit_time].iloc[0]
                entry_contract = float(entry_row["Contract Price"])
                exit_contract = float(exit_row["Contract Price"])
                pnl_contract = exit_contract - entry_contract

                c1_est, c2_est, c3_est = st.columns(3, gap="large")
                with c1_est:
                    st.markdown(metric_card("Entry Contract", f"{entry_contract:.2f}"), unsafe_allow_html=True)
                with c2_est:
                    st.markdown(metric_card("Exit Contract", f"{exit_contract:.2f}"), unsafe_allow_html=True)
                with c3_est:
                    st.markdown(metric_card("Projected P&L", f"{pnl_contract:+.2f} units"), unsafe_allow_html=True)

                st.markdown(
                    "<div class='muted'><strong>💡 How to use this estimator:</strong> "
                    "Pick the time you expect the rail touch to happen as your entry, "
                    "pick your planned exit time, and compare this projected contract move with what the market actually gave you. "
                    "The difference is your volatility and skew bonus on that day.</div>",
                    unsafe_allow_html=True,
                )

            section_header("🗺️ Time-Aligned Map")
            st.caption("Every row is a 30-minute slot in RTH. If SPX tags a rail at that time, this is the structural contract level from your anchors.")
            st.dataframe(merged, use_container_width=True, hide_index=True, height=480)

            st.markdown(
                "<div class='muted'><strong>📖 Reading the map:</strong> "
                "The grid does not tell you <em>when</em> the tag will happen. "
                "It tells you what your structure expects the contract to be worth <em>if</em> the tag happens at a given time.</div>",
                unsafe_allow_html=True,
            )

            end_card()

    # ==================================
    # TAB 4 — ABOUT
    # ==================================
    with tabs[3]:
        card("About SPX Prophet v7.0", TAGLINE, badge="Version 7.0", icon="ℹ️")
        st.markdown(
            """
            <div class='spx-sub' style='font-size:1.08rem; line-height:1.8;'>
            <p>SPX Prophet is built on a simple idea:</p>

            <p style='font-size:1.2rem; color:#6366f1; font-weight:600; margin:20px 0;'>
            Two pivots define the rails and the slope carries that structure into the session.
            </p>

            <ul style='margin-left:24px; font-size:1.05rem;'>
                <li>Rails are projected with a <strong style='color:#6366f1;'>uniform slope of ±0.475 points per 30 minutes</strong></li>
                <li>Pivots are <strong style='color:#6366f1;'>engulfing reversals</strong> chosen by you between 15:00 and 07:30 CT</li>
                <li>Channels can be viewed as <strong style='color:#6366f1;'>ascending, descending, or inspected both ways</strong></li>
                <li>Contracts follow a straight line defined by <strong style='color:#6366f1;'>two anchor prices</strong> on the same grid</li>
            </ul>

            <p style='margin-top:24px;'>The app does not claim to model full options behavior. It gives you a clean structural map so that when price returns to your rails, you are not reacting blindly. You already have a framework and a plan.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='muted'><strong>🔧 Maintenance windows:</strong> "
            "SPX 16:00–17:00 CT. Contracts 16:00–19:00 CT.</div>",
            unsafe_allow_html=True,
        )
        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet v7.0 • Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()