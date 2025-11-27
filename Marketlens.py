# spx_prophet_app.py
# SPX Prophet – Light Mode, Manual Input, Styled UI

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

# -------------------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------------------

SLOPE_PER_30M = 0.475        # points per 30-min block (magnitude)
MAX_OFFSETS = 3
MAX_RAIL_DISTANCE = 5.0      # max distance between close and rail for valid signal
EFFICIENCY_THRESHOLD = 0.33  # your contract movement factor


# -------------------------------------------------------------------
# GLOBAL LIGHT-THEME STYLING
# -------------------------------------------------------------------

st.set_page_config(
    page_title="SPX Prophet – Options Channel Engine",
    layout="wide",
)

st.markdown(
    """
<style>
body {
    background-color: #F5F7FB;
    color: #111827;
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E5E7EB;
}

/* Headings */
h1, h2, h3 {
    color: #111827 !important;
    font-family: "Poppins", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* Dataframes */
[data-testid="stDataFrame"] {
    background-color: #FFFFFF;
    border-radius: 14px;
    border: 1px solid #E5E7EB;
}

/* Buttons */
.stButton > button {
    border-radius: 999px;
    background: linear-gradient(135deg, #2563EB, #22C55E);
    color: white;
    font-weight: 600;
    border: none;
    padding: 0.45rem 1.4rem;
    box-shadow: 0 8px 18px rgba(37, 99, 235, 0.25);
}

/* Inputs */
input, textarea {
    border-radius: 10px !important;
}

/* Main container padding */
.block-container {
    padding-top: 0.5rem;
}

/* Card look */
.spx-card {
    padding: 18px 20px;
    background-color: #FFFFFF;
    border-radius: 16px;
    border: 1px solid #E5E7EB;
    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
}

/* Tag styles */
.spx-tag {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.03em;
}
.spx-tag-green {
    background-color: #DCFCE7;
    color: #166534;
}
.spx-tag-red {
    background-color: #FEE2E2;
    color: #B91C1C;
}
.spx-tag-blue {
    background-color: #DBEAFE;
    color: #1D4ED8;
}

/* Signal text */
.spx-signal-long {
    color: #15803D;
    font-weight: 600;
}
.spx-signal-short {
    color: #B91C1C;
    font-weight: 600;
}

/* Data editor */
[data-testid="stDataEditor"] {
    background-color: #FFFFFF;
    border-radius: 16px;
    border: 1px solid #E5E7EB;
}

/* Scrollbars */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-thumb {
    background-color: #CBD5F5;
    border-radius: 999px;
}
</style>
""",
    unsafe_allow_html=True,
)


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def blocks_between(t_ref, t_target):
    """Number of 30-min blocks between two datetimes."""
    delta = t_target - t_ref
    minutes = delta.total_seconds() / 60.0
    return minutes / 30.0


# -------------------------------------------------------------------
# CHANNEL CALCULATIONS
# -------------------------------------------------------------------

def compute_channel_params(structure, ref_time, bottom_ref, top_ref, overnight_high, overnight_low):
    width = top_ref - bottom_ref
    if width <= 0:
        width = abs(width) if width != 0 else 1.0

    overnight_range = overnight_high - overnight_low
    violence = overnight_range / width if width != 0 else 1.0

    if violence <= 0.75:
        offsets = 1
    elif violence <= 1.5:
        offsets = 2
    else:
        offsets = 3
    offsets = min(offsets, MAX_OFFSETS)

    if structure == "Ascending":
        slope = +SLOPE_PER_30M
    elif structure == "Descending":
        slope = -SLOPE_PER_30M
    else:
        slope = SLOPE_PER_30M

    return {
        "structure": structure,
        "ref_time": ref_time,
        "bottom_ref": bottom_ref,
        "top_ref": top_ref,
        "width": width,
        "violence": violence,
        "offsets": offsets,
        "slope": slope,
    }


def rail_values_at_time(channel, t, side="primary", level=0):
    n_blocks = blocks_between(channel["ref_time"], t)
    slope = channel["slope"]

    bottom_primary = channel["bottom_ref"] + slope * n_blocks
    top_primary = channel["top_ref"] + slope * n_blocks

    if side == "primary":
        return bottom_primary, top_primary

    shift = channel["width"] * level * (1 if side == "offset_up" else -1)
    return bottom_primary + shift, top_primary + shift


def classify_day_type(channel, open_price, open_time):
    bottom, top = rail_values_at_time(channel, open_time, side="primary")
    structure = channel["structure"]

    if open_price > top:
        position = "open above"
    elif open_price < bottom:
        position = "open below"
    else:
        position = "open inside"

    if structure in ["Ascending", "Descending"]:
        return f"{structure} channel – {position}"
    return f"Dual structure – {position}"


# -------------------------------------------------------------------
# SIGNAL ENGINE
# -------------------------------------------------------------------

def raw_candle_signal(channel, t, o, h, l, c):
    structure = channel["structure"]
    bottom, top = rail_values_at_time(channel, t, side="primary")

    if c > o:
        ctype = "bull"
    elif c < o:
        ctype = "bear"
    else:
        ctype = "neutral"

    dist_bottom = abs(c - bottom)
    dist_top = abs(c - top)

    if structure == "Ascending":
        # Long from bottom rail
        if (
            ctype == "bear"
            and l <= bottom <= h
            and c > bottom
            and dist_bottom <= MAX_RAIL_DISTANCE
        ):
            return {
                "side": "long",
                "rail_price": bottom,
                "rail_name": "primary_bottom",
                "distance": dist_bottom,
                "c": c,
            }
        # Long from top rail
        if (
            ctype == "bear"
            and l <= top <= h
            and c > top
            and dist_top <= MAX_RAIL_DISTANCE
        ):
            return {
                "side": "long",
                "rail_price": top,
                "rail_name": "primary_top",
                "distance": dist_top,
                "c": c,
            }

    if structure == "Descending":
        # Short from top rail
        if (
            ctype == "bull"
            and l <= top <= h
            and c < top
            and dist_top <= MAX_RAIL_DISTANCE
        ):
            return {
                "side": "short",
                "rail_price": top,
                "rail_name": "primary_top",
                "distance": dist_top,
                "c": c,
            }
        # Short from bottom rail
        if (
            ctype == "bull"
            and l <= bottom <= h
            and c < bottom
            and dist_bottom <= MAX_RAIL_DISTANCE
        ):
            return {
                "side": "short",
                "rail_price": bottom,
                "rail_name": "primary_bottom",
                "distance": dist_bottom,
                "c": c,
            }

    return None


def confirm_signal(side, rail, first_close, o2, h2, l2, c2):
    if side == "long":
        return c2 > first_close and l2 > rail - 1.0
    if side == "short":
        return c2 < first_close and h2 < rail + 1.0
    return False


def scan_signals_with_confirmation(channel, df_30):
    signals = []
    if df_30.empty or len(df_30) < 2:
        return signals

    for i in range(len(df_30) - 1):
        row1 = df_30.iloc[i]
        row2 = df_30.iloc[i + 1]

        t1 = row1["Time_dt"]
        t2 = row2["Time_dt"]
        o1, h1, l1, c1 = row1["Open"], row1["High"], row1["Low"], row1["Close"]
        o2, h2, l2, c2 = row2["Open"], row2["High"], row2["Low"], row2["Close"]

        raw = raw_candle_signal(channel, t1, o1, h1, l1, c1)
        if raw is None:
            continue

        if not confirm_signal(raw["side"], raw["rail_price"], raw["c"], o2, h2, l2, c2):
            continue

        signals.append(
            {
                "Signal time": t1,
                "Confirm time": t2,
                "Side": raw["side"],
                "Rail used": raw["rail_name"],
                "Rail price": round(raw["rail_price"], 2),
                "Distance to rail": round(raw["distance"], 2),
                "Candle1 close": c1,
                "Candle2 close": c2,
            }
        )

    return signals


# -------------------------------------------------------------------
# OPTIONS LAYER
# -------------------------------------------------------------------

def expected_spx_move(channel, num_blocks=1):
    return abs(channel["slope"]) * num_blocks


def suggest_option_contracts(price, expected_move, side):
    expected_contract_move = expected_move * EFFICIENCY_THRESHOLD

    if side == "long":
        safe_strike = round(price - 10)
        opt_strike = round(price)
        agg_strike = round(price + 10)
    else:
        safe_strike = round(price + 10)
        opt_strike = round(price)
        agg_strike = round(price - 10)

    return {
        "expected_spx_move": expected_move,
        "expected_contract_move": expected_contract_move,
        "safe": {
            "strike": safe_strike,
            "label": "Safe (ITM-heavy)",
            "note": "Stable, smaller swings. Best for reversals or noisy days.",
        },
        "optimal": {
            "strike": opt_strike,
            "label": "Optimal (ATM)",
            "note": "Best balance of cost vs speed on clean channel trades.",
        },
        "aggressive": {
            "strike": agg_strike,
            "label": "Aggressive (OTM)",
            "note": "Use only on very clean, confirmed signals in high-confidence days.",
        },
    }


# -------------------------------------------------------------------
# HEADER
# -------------------------------------------------------------------

st.markdown(
    """
<div style="text-align:center; margin-top: 0.5rem; margin-bottom: 1.5rem;">
  <div style="
      display:inline-block;
      padding: 10px 22px;
      border-radius: 999px;
      background: linear-gradient(135deg,#2563EB,#22C55E);
      color: white;
      font-weight: 600;
      font-family: Poppins, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 0.8rem;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      margin-bottom: 0.6rem;">
    SPX Prophet
  </div>
  <h1 style="margin-bottom: 0; font-size: 2.3rem;">Options Channel Engine</h1>
  <p style="margin-top: 0.3rem; color: #6B7280; font-size: 0.95rem;">
    Manual-precision market structure, institutional-style entries, and options-aware planning.
  </p>
</div>
""",
    unsafe_allow_html=True,
)


# -------------------------------------------------------------------
# SIDEBAR – SESSION SETUP
# -------------------------------------------------------------------

st.sidebar.title("Session Setup")

session_date = st.sidebar.date_input("Session date", value=datetime.today().date())

structure = st.sidebar.selectbox(
    "Market structure",
    ["Ascending", "Descending", "Both"],
    index=0,
)

ref_time_str = st.sidebar.text_input(
    "Reference time (HH:MM)",
    value="03:00",
)
try:
    rh, rm = map(int, ref_time_str.split(":"))
    ref_time = datetime.combine(session_date, time(rh, rm))
except Exception:
    ref_time = datetime.combine(session_date, time(3, 0))

bottom_ref = st.sidebar.number_input(
    "Bottom rail @ reference",
    value=4700.0,
    step=1.0,
    format="%.1f",
)
top_ref = st.sidebar.number_input(
    "Top rail @ reference",
    value=4720.0,
    step=1.0,
    format="%.1f",
)

st.sidebar.markdown("---")
overnight_low = st.sidebar.number_input(
    "Overnight low (ES)",
    value=4690.0,
    step=1.0,
    format="%.1f",
)
overnight_high = st.sidebar.number_input(
    "Overnight high (ES)",
    value=4730.0,
    step=1.0,
    format="%.1f",
)

holding_blocks = st.sidebar.slider(
    "Expected holding time (30-min blocks)",
    min_value=1,
    max_value=4,
    value=2,
)


# -------------------------------------------------------------------
# CHANNEL SUMMARY
# -------------------------------------------------------------------

channel = compute_channel_params(
    structure,
    ref_time,
    bottom_ref,
    top_ref,
    overnight_high,
    overnight_low,
)

col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    st.subheader("Channel Geometry")
    st.write(f"**Structure:** {channel['structure']}")
    st.write(f"**Slope per 30 min:** {channel['slope']:+.3f} pts")
    st.write(f"**Width:** {channel['width']:.2f} pts")
    st.write(f"**Violence (range/width):** {channel['violence']:.2f}")
    st.write(f"**Offsets used:** {channel['offsets']}")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    st.subheader("Reference & Overnight")
    st.write(f"**Reference time:** {channel['ref_time']}")
    st.write(f"**Bottom rail @ ref:** {channel['bottom_ref']:.2f}")
    st.write(f"**Top rail @ ref:** {channel['top_ref']:.2f}")
    st.write(f"**Overnight low:** {overnight_low:.2f}")
    st.write(f"**Overnight high:** {overnight_high:.2f}")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")


# -------------------------------------------------------------------
# CANDLE INPUT – EDITOR (BACKWARDS COMPATIBLE)
# -------------------------------------------------------------------

st.markdown('<div class="spx-card">', unsafe_allow_html=True)
st.subheader("30-Minute Candle Input")

st.caption(
    "Edit the table below with your actual 30-min candles. "
    "Times should be HH:MM (24h)."
)

# Default template
default_times = []
cursor = datetime.combine(session_date, time(8, 30))
end_time = datetime.combine(session_date, time(15, 0))
while cursor <= end_time:
    default_times.append(cursor.strftime("%H:%M"))
    cursor += timedelta(minutes=30)

template_rows = min(len(default_times), 10)
df_template = pd.DataFrame(
    {
        "Time": default_times[:template_rows],
        "Open": [bottom_ref + 5.0] * template_rows,
        "High": [bottom_ref + 10.0] * template_rows,
        "Low": [bottom_ref] * template_rows,
        "Close": [bottom_ref + 6.0] * template_rows,
    }
)

# Use data_editor if available, else experimental_data_editor
try:
    df_candles = st.data_editor(
        df_template,
        num_rows="dynamic",
        use_container_width=True,
        key="candles_editor",
    )
except AttributeError:
    df_candles = st.experimental_data_editor(
        df_template,
        num_rows="dynamic",
        use_container_width=True,
        key="candles_editor",
    )

st.markdown("</div>", unsafe_allow_html=True)

# Convert to usable dataframe
valid_rows = []
for _, row in df_candles.iterrows():
    t_str = str(row.get("Time", "")).strip()
    if not t_str:
        continue
    try:
        t_dt = datetime.combine(session_date, datetime.strptime(t_str, "%H:%M").time())
    except Exception:
        continue
    try:
        o = float(row["Open"])
        h = float(row["High"])
        l = float(row["Low"])
        c = float(row["Close"])
    except Exception:
        continue
    valid_rows.append(
        {"Time": t_str, "Time_dt": t_dt, "Open": o, "High": h, "Low": l, "Close": c}
    )

df_30 = pd.DataFrame(valid_rows)


# -------------------------------------------------------------------
# DAILY TYPE
# -------------------------------------------------------------------

if not df_30.empty:
    first_row = df_30.iloc[0]
    open_price = first_row["Open"]
    open_time = first_row["Time_dt"]
    day_type = classify_day_type(channel, open_price, open_time)
else:
    day_type = "No candles yet."

st.markdown('<div class="spx-card">', unsafe_allow_html=True)
st.subheader("Daily Card – Bias Snapshot")

tag_class = "spx-tag-blue"
if "Ascending" in day_type:
    tag_class = "spx-tag-green"
elif "Descending" in day_type:
    tag_class = "spx-tag-red"

st.markdown(
    f"<div class='spx-tag {tag_class}'>DAY TYPE</div> "
    f"<span style='margin-left:6px; font-weight:600;'>{day_type}</span>",
    unsafe_allow_html=True,
)

if "Ascending channel – open above" in day_type:
    st.write(
        "- Up structure and open above rails; calls at open are stretched.\n"
        "- Edge is from bear candle touches & closes above rails."
    )
elif "Ascending channel – open below" in day_type:
    st.write(
        "- Up structure with bearish open; puts strong into bottom rail.\n"
        "- Calls become powerful from a clean bottom-rail touch rule."
    )
elif "Descending channel – open below" in day_type:
    st.write(
        "- Down structure with bearish open; puts powerful from bull candle rule at rail.\n"
        "- Calls only from flips above rails."
    )
elif "Descending channel – open above" in day_type:
    st.write(
        "- Down structure but bullish open; early puts dangerous.\n"
        "- Wait for top-rail tests and flips."
    )
else:
    st.write(
        "- Dual or inside structure; reduce aggression and prefer ATM contracts.\n"
        "- Let the second-candle confirmation filter most setups."
    )

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")


# -------------------------------------------------------------------
# CHANNEL TABLE
# -------------------------------------------------------------------

st.markdown('<div class="spx-card">', unsafe_allow_html=True)
st.subheader("Price–Time Channel Table")

times_for_table = []
cursor = datetime.combine(session_date, time(8, 30))
end_time = datetime.combine(session_date, time(15, 0))
while cursor <= end_time:
    times_for_table.append(cursor)
    cursor += timedelta(minutes=30)

rows = []
for t in times_for_table:
    b_primary, t_primary = rail_values_at_time(channel, t, side="primary")
    row = {
        "Time": t.strftime("%H:%M"),
        "Primary Bottom": round(b_primary, 2),
        "Primary Top": round(t_primary, 2),
    }
    for lvl in range(1, channel["offsets"] + 1):
        b_up, t_up = rail_values_at_time(channel, t, side="offset_up", level=lvl)
        b_dn, t_dn = rail_values_at_time(channel, t, side="offset_down", level=lvl)
        row[f"Offset +{lvl} Bottom"] = round(b_up, 2)
        row[f"Offset +{lvl} Top"] = round(t_up, 2)
        row[f"Offset -{lvl} Bottom"] = round(b_dn, 2)
        row[f"Offset -{lvl} Top"] = round(t_dn, 2)
    rows.append(row)

df_channels = pd.DataFrame(rows)
st.dataframe(df_channels, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")


# -------------------------------------------------------------------
# SIGNALS + TRADE PLANNER
# -------------------------------------------------------------------

st.markdown('<div class="spx-card">', unsafe_allow_html=True)
st.subheader("Confirmed Signals")

if df_30.empty or len(df_30) < 2:
    st.info("Enter at least 2 valid 30-min candles to scan for signals.")
    st.markdown("</div>", unsafe_allow_html=True)
else:
    signals = scan_signals_with_confirmation(channel, df_30)

    if not signals:
        st.info("No signals passed your channel + second-candle filters.")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        df_signals = pd.DataFrame(signals)
        df_signals["Signal time"] = df_signals["Signal time"].dt.strftime("%H:%M")
        df_signals["Confirm time"] = df_signals["Confirm time"].dt.strftime("%H:%M")
        st.dataframe(df_signals, use_container_width=True)

        st.markdown("---")
        st.subheader("Trade Planner (First Confirmed Signal)")

        sig0 = signals[0]
        side = sig0["Side"]
        rail_price = sig0["Rail price"]
        signal_time = sig0["Signal time"]
        confirm_time = sig0["Confirm time"]

        exp_move = expected_spx_move(channel, num_blocks=holding_blocks)
        opt_plan = suggest_option_contracts(rail_price, exp_move, side)

        if side == "long":
            side_html = "<span class='spx-signal-long'>LONG (Calls)</span>"
        else:
            side_html = "<span class='spx-signal-short'>SHORT (Puts)</span>"

        st.markdown(
            f"**Direction:** {side_html} &nbsp; | &nbsp; "
            f"**Signal @** {signal_time.strftime('%H:%M')} &nbsp;→&nbsp; "
            f"**Confirmed @** {confirm_time.strftime('%H:%M')}",
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            st.write("**Rail price**")
            st.write(f"{rail_price:.2f}")
            st.write("**Distance to rail**")
            st.write(f"{sig0['Distance to rail']:.2f} pts")

        with c2:
            st.write("**Projected SPX move**")
            st.write(f"{opt_plan['expected_spx_move']:.2f} pts")
            st.write("**Min contract move (0.33)**")
            st.write(f"{opt_plan['expected_contract_move']:.2f} $")

        with c3:
            st.write("**Contract map (model)**")
            st.write(f"Safe: {opt_plan['safe']['label']} @ {opt_plan['safe']['strike']}")
            st.caption(opt_plan["safe"]["note"])
            st.write(f"Optimal: {opt_plan['optimal']['label']} @ {opt_plan['optimal']['strike']}")
            st.caption(opt_plan["optimal"]["note"])
            st.write(f"Aggressive: {opt_plan['aggressive']['label']} @ {opt_plan['aggressive']['strike']}")
            st.caption(opt_plan["aggressive"]["note"])

        st.caption(
            "Use your broker’s live option chain for actual contracts. "
            "The hierarchy Safe → Optimal → Aggressive and the 0.33 factor are your edge filters."
        )

        st.markdown("</div>", unsafe_allow_html=True)