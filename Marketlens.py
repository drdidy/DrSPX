# spx_prophet_v7.py
# SPX Prophet v7.0 — "Where Structure Becomes Foresight."
# Futuristic quant aesthetic. Streamlit-only. No external data.
# Core: two pivots define parallel rails with slope ±0.475 per 30 minutes.
# Contract line projected from two contract anchors. Daily Foresight Card links both.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet v7.0"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475          # points per 30-minute block for SPX rails
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # synthetic 15:00 "start" for block indexing


# ===============================
# FUTURISTIC QUANT THEME (CSS)
# ===============================

def inject_css():
    css = """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(1000px 800px at 10% 0%, rgba(0, 255, 255, 0.13), transparent 60%),
          radial-gradient(900px 900px at 90% 0%, rgba(0, 255, 135, 0.12), transparent 65%),
          linear-gradient(145deg, #020412 0%, #050716 35%, #040510 100%);
        background-attachment: fixed;
        color: #E6ECFF;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(160deg, rgba(5,10,30,0.96), rgba(10,20,45,0.98));
        border-right: 1px solid rgba(0,255,200,0.16);
        backdrop-filter: blur(22px);
    }
    h1, h2, h3, h4, h5, h6, label, p, span, div {
        color: #E6ECFF;
    }
    .spx-card {
        background: radial-gradient(circle at top left, rgba(0,255,255,0.10), transparent 60%),
                    radial-gradient(circle at bottom right, rgba(0,255,135,0.10), transparent 60%),
                    rgba(9,12,32,0.88);
        border-radius: 20px;
        border: 1px solid rgba(0,255,200,0.18);
        box-shadow:
          0 18px 60px rgba(0,0,0,0.7),
          0 0 40px rgba(0,255,255,0.15);
        padding: 18px 20px;
        margin-bottom: 16px;
        backdrop-filter: blur(18px);
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    }
    .spx-card:hover {
        transform: translateY(-2px);
        border-color: rgba(0,255,255,0.8);
        box-shadow:
          0 24px 70px rgba(0,0,0,0.9),
          0 0 70px rgba(0,255,255,0.32);
    }
    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        padding: 4px 12px;
        border-radius: 999px;
        border: 1px solid rgba(0,255,200,0.35);
        background: radial-gradient(circle at top left, rgba(0,255,200,0.24), transparent 60%);
        font-size: .8rem;
        text-transform: uppercase;
        letter-spacing: .08em;
        color: #00ffe0;
    }
    .spx-sub {
        color: #A2ABCC;
        font-size: .92rem;
    }
    .spx-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
    }
    .muted {
        color: #9AA4C5;
        font-size: .85rem;
    }
    .spx-metric {
        padding: 10px 12px;
        border-radius: 12px;
        background: radial-gradient(circle at top, rgba(0,255,255,0.18), transparent 55%);
        border: 1px solid rgba(0,255,255,0.28);
        font-size: .9rem;
    }
    .spx-metric-label {
        font-size: .75rem;
        text-transform: uppercase;
        letter-spacing: .06em;
        color: #9AA4C5;
    }
    .spx-metric-value {
        font-size: 1.05rem;
        font-weight: 700;
        color: #E6ECFF;
    }
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(90deg, #00e5ff, #00ff9d);
        color: #020412;
        border-radius: 999px;
        border: none;
        padding: 8px 16px;
        font-weight: 700;
        font-size: .9rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.6), 0 0 30px rgba(0,255,255,0.28);
        cursor: pointer;
    }
    .stButton>button:hover, .stDownloadButton>button:hover {
        filter: brightness(1.07);
        transform: translateY(-1px);
    }
    .stDataFrame div[data-testid="StyledTable"] {
        font-variant-numeric: tabular-nums;
        font-size: .85rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def card(title: str, sub: Optional[str] = None, badge: Optional[str] = None):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='margin:6px 0 4px 0'>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


# ===============================
# TIME / BLOCK HELPERS (SYNTHETIC TIMELINE)
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    """
    Map a time to a synthetic date around BASE_DATE.
    Times >= 15:00 are treated as 'day 1' (previous afternoon/evening),
    times < 15:00 as 'day 2' (overnight / morning).
    """
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    """Snap a datetime to nearest 30-min boundary (00 or 30)."""
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    """Return number of 30-min blocks from BASE_DATE 15:00."""
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """RTH 08:30–14:30 on synthetic day2."""
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
    """
    Build parallel rails given high/low pivots and slope sign.
    slope_sign: +1 for ascending, -1 for descending.
    Returns (df, channel_height).
    """
    s = slope_sign * SLOPE_MAG

    dt_hi = align_30min(make_dt_from_time(high_time))
    dt_lo = align_30min(make_dt_from_time(low_time))
    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)

    # lines: P = s * k + b
    b_top = high_price - s * k_hi
    b_bottom = low_price - s * k_lo

    # channel height is constant difference between lines
    channel_height = b_top - b_bottom

    # project across RTH
    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        top = s * k + b_top
        bottom = s * k + b_bottom
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Top Rail": round(top, 4),
                "Bottom Rail": round(bottom, 4),
            }
        )

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
    """
    Build a contract line from two anchor points (time+price).
    Returns (projection_df, slope_per_block).
    """
    dt_a = align_30min(make_dt_from_time(anchor_a_time))
    dt_b = align_30min(make_dt_from_time(anchor_b_time))
    k_a = blocks_from_base(dt_a)
    k_b = blocks_from_base(dt_b)

    if k_a == k_b:
        slope = 0.0
    else:
        slope = (anchor_b_price - anchor_a_price) / (k_b - k_a)

    # projection based on: P = slope*k + b
    b_contract = anchor_a_price - slope * k_a
    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        price = slope * k + b_contract
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Contract Price": round(price, 4),
            }
        )
    df = pd.DataFrame(rows)
    return df, round(slope, 6)


# ===============================
# DAILY FORESIGHT CARD LOGIC
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

    # Sidebar
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(f"<span class='spx-sub'>{TAGLINE}</span>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("#### Core Slope")
        st.write(f"SPX rail slope magnitude: **{SLOPE_MAG} pts / 30 min**")
        st.caption("All calculations use a uniform per-block slope. Time grid = 30-minute candles.")
        st.markdown("---")
        st.markdown("#### Notes")
        st.caption(
            "Underlying maintenance: 16:00–17:00 CT\n\n"
            "Contracts maintenance: 16:00–19:00 CT\n\n"
            "RTH projection window: 08:30–14:30 CT."
        )

    tabs = st.tabs(
        [
            "🧱 SPX Channel Setup",
            "📐 Contract Slope Setup",
            "🔮 Daily Foresight Card",
            "ℹ️ About",
        ]
    )

    # ==========================
    # TAB 1 — CHANNEL SETUP
    # ==========================
    with tabs[0]:
        card(
            "SPX Channel Setup",
            "Define your high and low pivots, choose the channel regime, and project parallel rails across RTH.",
            badge="Rails Engine",
        )

        st.markdown("##### Pivots (3:00 PM to 7:30 AM, manual)")
        c1, c2 = st.columns(2)
        with c1:
            high_price = st.number_input(
                "High Pivot Price",
                value=5200.0,
                step=0.25,
                key="pivot_high_price",
            )
            high_time = st.time_input(
                "High Pivot Time (CT)",
                value=dtime(15, 0),
                step=1800,
                key="pivot_high_time",
            )
        with c2:
            low_price = st.number_input(
                "Low Pivot Price",
                value=5100.0,
                step=0.25,
                key="pivot_low_price",
            )
            low_time = st.time_input(
                "Low Pivot Time (CT)",
                value=dtime(3, 0),
                step=1800,
                key="pivot_low_time",
            )

        st.markdown("##### Channel Regime")
        mode = st.radio(
            "Channel Mode",
            ["Ascending", "Descending", "Both"],
            index=0,
            key="channel_mode",
            horizontal=True,
        )

        if st.button("Build Channel", key="build_channel_btn"):
            # Ascending
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

            # Descending
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

            st.success("Channel(s) generated. Check tables below and the Daily Foresight Card tab.")

        # Display results if present
        df_asc = st.session_state.get("channel_asc_df")
        df_desc = st.session_state.get("channel_desc_df")
        h_asc = st.session_state.get("channel_asc_height")
        h_desc = st.session_state.get("channel_desc_height")

        st.markdown("### Channel Projections (RTH 08:30–14:30 CT)")
        if df_asc is None and df_desc is None:
            st.info("Build a channel to view projections.")
        else:
            if df_asc is not None:
                st.markdown("#### Ascending Channel")
                c_top = st.columns([3, 1])
                with c_top[0]:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True)
                with c_top[1]:
                    st.markdown("<div class='spx-metric'>"
                                "<div class='spx-metric-label'>Channel Height (Ascending)</div>"
                                f"<div class='spx-metric-value'>{h_asc:.2f} pts</div>"
                                "</div>", unsafe_allow_html=True)
                    st.download_button(
                        "Download Ascending Rails CSV",
                        df_asc.to_csv(index=False).encode(),
                        "spx_ascending_rails.csv",
                        "text/csv",
                        key="dl_asc_channel",
                    )

            if df_desc is not None:
                st.markdown("#### Descending Channel")
                c_bot = st.columns([3, 1])
                with c_bot[0]:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True)
                with c_bot[1]:
                    st.markdown("<div class='spx-metric'>"
                                "<div class='spx-metric-label'>Channel Height (Descending)</div>"
                                f"<div class='spx-metric-value'>{h_desc:.2f} pts</div>"
                                "</div>", unsafe_allow_html=True)
                    st.download_button(
                        "Download Descending Rails CSV",
                        df_desc.to_csv(index=False).encode(),
                        "spx_descending_rails.csv",
                        "text/csv",
                        key="dl_desc_channel",
                    )

        end_card()

    # ==========================
    # TAB 2 — CONTRACT SLOPE
    # ==========================
    with tabs[1]:
        card(
            "Contract Slope Setup",
            "Anchor your contract line to a pivot or custom time, define a second point, and project value across RTH.",
            badge="Contract Engine",
        )

        # Need channel pivots available for pivot-based Anchor A selection
        ph_time: dtime = st.session_state.get("pivot_high_time", dtime(15, 0))
        pl_time: dtime = st.session_state.get("pivot_low_time", dtime(3, 0))

        st.markdown("##### Anchor A — Contract Origin")
        anchor_a_source = st.radio(
            "Use which time for Anchor A?",
            ["High Pivot Time", "Low Pivot Time", "Custom Time"],
            index=0,
            key="contract_anchor_a_source",
            horizontal=True,
        )

        if anchor_a_source == "High Pivot Time":
            anchor_a_time = ph_time
            st.markdown(
                f"<div class='muted'>Anchor A time set to High Pivot Time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT.</div>",
                unsafe_allow_html=True,
            )
        elif anchor_a_source == "Low Pivot Time":
            anchor_a_time = pl_time
            st.markdown(
                f"<div class='muted'>Anchor A time set to Low Pivot Time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT.</div>",
                unsafe_allow_html=True,
            )
        else:
            anchor_a_time = st.time_input(
                "Custom Anchor A Time (CT)",
                value=dtime(1, 0),
                step=1800,
                key="contract_anchor_a_time_custom",
            )

        anchor_a_price = st.number_input(
            "Contract Price at Anchor A Time",
            value=10.0,
            step=0.1,
            key="contract_anchor_a_price",
        )

        st.markdown("##### Anchor B — Second Contract Point")
        c1, c2 = st.columns(2)
        with c1:
            anchor_b_time = st.time_input(
                "Anchor B Time (CT)",
                value=dtime(7, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
        with c2:
            anchor_b_price = st.number_input(
                "Contract Price at Anchor B Time",
                value=8.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        if st.button("Build Contract Projection", key="build_contract_btn"):
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
            st.success("Contract projection generated. Check the table below and the Daily Foresight Card tab.")

        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        st.markdown("### Contract Projection (RTH 08:30–14:30 CT)")
        if df_contract is None:
            st.info("Build a contract projection to view projected contract prices.")
        else:
            c_top = st.columns([3, 1])
            with c_top[0]:
                st.dataframe(df_contract, use_container_width=True, hide_index=True)
            with c_top[1]:
                st.markdown("<div class='spx-metric'>"
                            "<div class='spx-metric-label'>Contract Slope</div>"
                            f"<div class='spx-metric-value'>{slope_contract:+.4f} / 30m</div>"
                            "</div>", unsafe_allow_html=True)
                st.download_button(
                    "Download Contract Projection CSV",
                    df_contract.to_csv(index=False).encode(),
                    "contract_projection.csv",
                    "text/csv",
                    key="dl_contract",
                )

        end_card()

    # ==========================
    # TAB 3 — DAILY FORESIGHT
    # ==========================
    with tabs[2]:
        card(
            "Daily Foresight Card",
            "Channel structure + contract slope combined into a simple playbook for the session.",
            badge="Foresight",
        )

        mode = st.session_state.get("channel_mode")
        df_mode, df_ch, h_ch = get_active_channel()
        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        if df_ch is None or h_ch is None:
            st.warning("No active channel found. Build a channel in the SPX Channel Setup tab first.")
            end_card()
        elif df_contract is None or slope_contract is None:
            st.warning("No contract projection found. Build one in the Contract Slope Setup tab first.")
            end_card()
        else:
            # Merge channel and contract projections by Time
            merged = df_ch.merge(df_contract, on="Time", how="left")

            # Expected contract move per channel-height move in underlying
            blocks_for_channel = h_ch / SLOPE_MAG if SLOPE_MAG != 0 else 0
            contract_move_per_channel = slope_contract * blocks_for_channel if blocks_for_channel != 0 else 0

            # Summary metrics row
            st.markdown("### Structure Summary")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    "<div class='spx-metric'>"
                    "<div class='spx-metric-label'>Active Channel</div>"
                    f"<div class='spx-metric-value'>{df_mode}</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    "<div class='spx-metric'>"
                    "<div class='spx-metric-label'>Channel Height</div>"
                    f"<div class='spx-metric-value'>{h_ch:.2f} pts</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    "<div class='spx-metric'>"
                    "<div class='spx-metric-label'>Contract Move per Channel</div>"
                    f"<div class='spx-metric-value'>{contract_move_per_channel:+.2f} units</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("### Inside-Channel Play (If Price Stays Between Rails)")
            st.markdown(
                f"""
                - **Long Play**: Buy at bottom rail, exit at top rail  
                  - Underlying reward ≈ **+{h_ch:.2f} pts**  
                  - Contract expectation ≈ **{contract_move_per_channel:+.2f}** units  
                - **Short Play**: Sell at top rail, exit at bottom rail  
                  - Underlying reward ≈ **-{h_ch:.2f} pts**  
                  - Contract expectation ≈ **{(-contract_move_per_channel):+.2f}** units  
                """.strip()
            )

            st.markdown("### Breakout / Breakdown Play (If Price Leaves the Channel)")
            st.markdown(
                f"""
                - **Bullish Breakout**:  
                  - Entry on retest of top rail from above  
                  - Underlying continuation target ≈ **Top Rail + {h_ch:.2f} pts**  
                  - Contract expectation per full channel move ≈ **{contract_move_per_channel:+.2f}** units  
                - **Bearish Breakdown**:  
                  - Entry on retest of bottom rail from below  
                  - Underlying continuation target ≈ **Bottom Rail − {h_ch:.2f} pts**  
                  - Contract expectation per full channel move ≈ **{contract_move_per_channel:+.2f}** units  
                """.strip()
            )

            st.markdown("### Time-Aligned Map (Rails + Contract)")
            st.caption("Each row is a 30-minute slot in RTH. Use this as a conditional map: if price tags a rail at that time, this is the expected contract level.")
            st.dataframe(merged, use_container_width=True, hide_index=True)

            st.markdown(
                "<div class='muted'>Interpretation: "
                "The map does not predict exactly *when* SPX will hit a rail. "
                "It tells you what the contract should roughly be worth *if* that touch happens at a given time.</div>",
                unsafe_allow_html=True,
            )

            end_card()

    # ==========================
    # TAB 4 — ABOUT
    # ==========================
    with tabs[3]:
        card("About SPX Prophet v7.0", TAGLINE, badge="Version 7.0")
        st.markdown(
            """
            **SPX Prophet v7.0** is built around a single idea:

            > Two pivots define the rails. The slope defines the future.

            - Rails are projected using a **uniform slope** of **±0.475 pts per 30 minutes**  
            - Pivots are **engulfing reversals** chosen between **15:00 and 07:30 CT**  
            - Channels can be **ascending, descending, or inspected both ways**  
            - Contracts are projected from **two anchor prices** on the same 30-minute grid  

            The app does not guess volatility, gamma, or implied pricing.  
            It respects one thing: **structure**.

            When the market returns to your rails, you are no longer surprised.  
            You are prepared.
            """.strip()
        )
        st.markdown("<div class='muted'>Maintenance windows: SPX 16:00–17:00 CT, contracts 16:00–19:00 CT.</div>", unsafe_allow_html=True)
        end_card()

    st.markdown(
        "<div class='muted' style='margin-top:10px'>© 2025 SPX Prophet v7.0 • Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()