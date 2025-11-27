# spx_prophet_app.py

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, time

# -------------------------------------------------------------------
# CONSTANTS AND CORE PARAMETERS
# -------------------------------------------------------------------

SLOPE_PER_30M = 0.475      # points per 30 minute block (magnitude)
MAX_OFFSETS = 3            # maximum offset channels
MAX_RAIL_DISTANCE = 5.0    # max distance in points between close and rail for valid signal
EFFICIENCY_THRESHOLD = 0.33  # your contract efficiency factor
TZ = "America/Chicago"     # your local market time


# -------------------------------------------------------------------
# UTILITIES
# -------------------------------------------------------------------

def get_today_date():
    return datetime.now().date()


def download_spx_intraday(date, interval="5m"):
    """
    Download SPX intraday data for given date using yfinance.
    Uses ^GSPC (cash index), RTH only.
    """
    symbol = "^GSPC"
    # A bit before open to a bit after close
    start = datetime.combine(date, time(8, 25))
    end = datetime.combine(date + timedelta(days=1), time(3, 10))

    data = yf.download(
        symbol,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=False,
        prepost=False,
        progress=False,
    )

    if data.empty:
        return data

    # convert timezone to Chicago
    data.index = data.index.tz_convert(TZ)
    return data


def resample_to_30m(df):
    if df.empty:
        return df
    df_30 = df.resample("30T").agg(
        {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
    )
    df_30.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)
    return df_30


def blocks_between(t_ref, t_target):
    """
    Number of 30 minute blocks between two timestamps.
    Positive if t_target after t_ref.
    """
    delta = t_target - t_ref
    minutes = delta.total_seconds() / 60.0
    return minutes / 30.0


# -------------------------------------------------------------------
# CHANNEL AND OFFSETS
# -------------------------------------------------------------------

def compute_channel_params(
    structure,
    ref_time,
    bottom_ref_price,
    top_ref_price,
    overnight_high=None,
    overnight_low=None,
):
    """
    Build primary channel and decide number of offsets based on overnight violence.
    structure: 'Ascending', 'Descending', 'Both'
    ref_time: datetime
    bottom_ref_price: bottom rail at ref_time
    top_ref_price: top rail at ref_time
    """
    width = top_ref_price - bottom_ref_price
    if width <= 0:
        width = abs(width) if width != 0 else 1.0

    if overnight_high is not None and overnight_low is not None:
        overnight_range = overnight_high - overnight_low
        violence = overnight_range / width if width > 0 else 0
    else:
        violence = 1.0

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
        "bottom_ref": bottom_ref_price,
        "top_ref": top_ref_price,
        "width": width,
        "violence": violence,
        "offsets": offsets,
        "slope": slope,
    }


def rail_values_at_time(channel, t, side="primary", level=0):
    """
    Compute top and bottom rail at time t.

    side: 'primary', 'offset_up', 'offset_down'
    level: offset index (1, 2, 3)
    """
    ref_time = channel["ref_time"]
    slope = channel["slope"]
    width = channel["width"]

    n_blocks = blocks_between(ref_time, t)
    signed_slope = slope  # you manually choose structure sign

    bottom_at_ref = channel["bottom_ref"]
    top_at_ref = channel["top_ref"]

    bottom_primary = bottom_at_ref + signed_slope * n_blocks
    top_primary = top_at_ref + signed_slope * n_blocks

    if side == "primary":
        return bottom_primary, top_primary

    if side == "offset_up":
        shift = level * width
    elif side == "offset_down":
        shift = -level * width
    else:
        shift = 0

    bottom = bottom_primary + shift
    top = top_primary + shift
    return bottom, top


def classify_day_type(channel, open_price, open_time):
    bottom, top = rail_values_at_time(channel, open_time, side="primary")
    structure = channel["structure"]

    if open_price > top:
        position = "open_above"
    elif open_price < bottom:
        position = "open_below"
    else:
        position = "open_inside"

    if structure in ["Ascending", "Descending"]:
        return f"{structure} channel - {position.replace('_', ' ')}"
    else:
        return f"Dual structure - {position.replace('_', ' ')}"


# -------------------------------------------------------------------
# SIGNAL ENGINE WITH SECOND CANDLE CONFIRMATION
# -------------------------------------------------------------------

def raw_candle_signal(channel, candle_time, o, h, l, c):
    """
    Evaluate raw (first pass) signal for a single candle.
    Returns dict with minimal info or None.
    """
    structure = channel["structure"]
    bottom, top = rail_values_at_time(channel, candle_time, side="primary")

    if c > o:
        candle_type = "bull"
    elif c < o:
        candle_type = "bear"
    else:
        candle_type = "neutral"

    # Distances
    dist_bottom = abs(c - bottom)
    dist_top = abs(c - top)

    # Ascending: valid long from bottom or top rail
    if structure == "Ascending":
        # Bottom long
        if (
            candle_type == "bear"
            and l <= bottom <= h
            and c > bottom
            and dist_bottom <= MAX_RAIL_DISTANCE
        ):
            return {
                "time": candle_time,
                "side": "long",
                "rail_name": "primary_bottom",
                "rail_price": bottom,
                "distance": dist_bottom,
                "candle_type": candle_type,
                "o": o,
                "h": h,
                "l": l,
                "c": c,
            }
        # Top long
        if (
            candle_type == "bear"
            and l <= top <= h
            and c > top
            and dist_top <= MAX_RAIL_DISTANCE
        ):
            return {
                "time": candle_time,
                "side": "long",
                "rail_name": "primary_top",
                "rail_price": top,
                "distance": dist_top,
                "candle_type": candle_type,
                "o": o,
                "h": h,
                "l": l,
                "c": c,
            }

    # Descending: valid short from top or bottom rail
    if structure == "Descending":
        # Top short
        if (
            candle_type == "bull"
            and l <= top <= h
            and c < top
            and dist_top <= MAX_RAIL_DISTANCE
        ):
            return {
                "time": candle_time,
                "side": "short",
                "rail_name": "primary_top",
                "rail_price": top,
                "distance": dist_top,
                "candle_type": candle_type,
                "o": o,
                "h": h,
                "l": l,
                "c": c,
            }
        # Bottom short
        if (
            candle_type == "bull"
            and l <= bottom <= h
            and c < bottom
            and dist_bottom <= MAX_RAIL_DISTANCE
        ):
            return {
                "time": candle_time,
                "side": "short",
                "rail_name": "primary_bottom",
                "rail_price": bottom,
                "distance": dist_bottom,
                "candle_type": candle_type,
                "o": o,
                "h": h,
                "l": l,
                "c": c,
            }

    # For Dual structure, use discretion; here no automatic raw signal
    return None


def confirm_signal_with_next_candle(channel, raw_sig, next_time, o2, h2, l2, c2):
    """
    Second candle confirmation filter.
    For long:
      next close should be higher and not break hard below rail.
    For short:
      next close should be lower and not break hard above rail.
    Returns True if confirmed.
    """
    rail = raw_sig["rail_price"]
    first_close = raw_sig["c"]
    side = raw_sig["side"]

    if side == "long":
        # Require continuation up and no decisive break under rail
        if c2 > first_close and l2 > rail - 1.0:
            return True
        else:
            return False

    if side == "short":
        # Require continuation down and no decisive break above rail
        if c2 < first_close and h2 < rail + 1.0:
            return True
        else:
            return False

    return False


def scan_signals_with_confirmation(channel, df_30):
    """
    Scan 30m candles for signals using raw rules plus second candle confirmation.
    Skip first bar of the day for entries.
    """
    signals = []

    idx = df_30.index
    n = len(idx)
    if n < 3:
        return signals

    for i in range(1, n - 1):  # skip first bar (i=0), last bar has no confirm
        t1 = idx[i]
        row1 = df_30.iloc[i]
        o1, h1, l1, c1 = row1["Open"], row1["High"], row1["Low"], row1["Close"]

        raw = raw_candle_signal(channel, t1, o1, h1, l1, c1)
        if raw is None:
            continue

        t2 = idx[i + 1]
        row2 = df_30.iloc[i + 1]
        o2, h2, l2, c2 = row2["Open"], row2["High"], row2["Low"], row2["Close"]

        confirmed = confirm_signal_with_next_candle(channel, raw, t2, o2, h2, l2, c2)
        if not confirmed:
            continue

        bottom, top = rail_values_at_time(channel, t1, side="primary")

        signals.append(
            {
                "signal_time": t1,
                "confirm_time": t2,
                "side": raw["side"],
                "rail_used": raw["rail_name"],
                "rail_price": raw["rail_price"],
                "distance_to_rail": raw["distance"],
                "candle1_open": o1,
                "candle1_close": c1,
                "candle1_high": h1,
                "candle1_low": l1,
                "candle2_open": o2,
                "candle2_close": c2,
                "candle2_high": h2,
                "candle2_low": l2,
                "primary_bottom_at_signal": bottom,
                "primary_top_at_signal": top,
            }
        )

    return signals


# -------------------------------------------------------------------
# SIMPLE OPTIONS LAYER (MODELING ONLY)
# -------------------------------------------------------------------

def expected_spx_move(channel, num_blocks=1):
    return abs(channel["slope"]) * num_blocks


def suggest_option_contracts(price, expected_move_points):
    expected_contract_move = expected_move_points * EFFICIENCY_THRESHOLD

    safe_strike = round(price - 10)   # ITM feel for calls if long
    opt_strike = round(price)         # ATM
    agg_strike = round(price + 10)    # OTM feel for calls if long

    return {
        "expected_spx_move": expected_move_points,
        "expected_contract_move": expected_contract_move,
        "safe": {
            "strike": safe_strike,
            "label": "Safe (ITM or heavy ATM)",
            "note": "Stable, lower speed, better for reversals or chop.",
        },
        "optimal": {
            "strike": opt_strike,
            "label": "Optimal (ATM)",
            "note": "Best balance for most clean channel trades.",
        },
        "aggressive": {
            "strike": agg_strike,
            "label": "Aggressive (OTM)",
            "note": "Use only on very clean, confirmed signals.",
        },
    }


# -------------------------------------------------------------------
# STREAMLIT APP
# -------------------------------------------------------------------

st.set_page_config(
    page_title="SPX Prophet - Options Channel App",
    layout="wide",
)

st.title("SPX Prophet - Options Channel App (V1.1)")

# ---------------------------------------------------------------
# SIDEBAR - GLOBAL CONTROLS
# ---------------------------------------------------------------

st.sidebar.header("Global Settings")

date_mode = st.sidebar.selectbox(
    "Date mode",
    ["Today", "Custom"],
    index=0,
)

if date_mode == "Today":
    trade_date = get_today_date()
else:
    trade_date = st.sidebar.date_input("Select trade date", value=get_today_date())

structure = st.sidebar.selectbox(
    "Market structure",
    ["Ascending", "Descending", "Both"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.write("Channel reference (from overnight or futures):")

ref_time_input = st.sidebar.text_input(
    "Reference time (HH:MM, local)",
    value="03:00",
    help="Time (America/Chicago) where your bottom and top reference prices apply.",
)

try:
    ref_hour, ref_minute = map(int, ref_time_input.split(":"))
    ref_time = datetime.combine(trade_date, time(ref_hour, ref_minute))
except Exception:
    ref_time = datetime.combine(trade_date, time(3, 0))

bottom_ref_price = st.sidebar.number_input(
    "Bottom rail price at reference time",
    value=4700.0,
    step=1.0,
    format="%.1f",
)

top_ref_price = st.sidebar.number_input(
    "Top rail price at reference time",
    value=4720.0,
    step=1.0,
    format="%.1f",
)

st.sidebar.markdown("Overnight range from ES (optional but useful):")
overnight_low = st.sidebar.number_input(
    "Overnight low",
    value=4690.0,
    step=1.0,
    format="%.1f",
)
overnight_high = st.sidebar.number_input(
    "Overnight high",
    value=4730.0,
    step=1.0,
    format="%.1f",
)

# ---------------------------------------------------------------
# BUILD CHANNEL
# ---------------------------------------------------------------

channel = compute_channel_params(
    structure=structure,
    ref_time=ref_time,
    bottom_ref_price=bottom_ref_price,
    top_ref_price=top_ref_price,
    overnight_high=overnight_high,
    overnight_low=overnight_low,
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Channel Overview")
    st.write(f"Structure: {channel['structure']}")
    st.write(f"Slope per 30 minutes: {channel['slope']:+.3f} points")
    st.write(f"Channel width: {channel['width']:.2f} points")
    st.write(f"Violence score (range / width): {channel['violence']:.2f}")
    st.write(f"Offsets used: {channel['offsets']}")

with col2:
    st.subheader("Reference and Overnight")
    st.write(f"Reference time: {channel['ref_time']}")
    st.write(f"Bottom rail at ref: {channel['bottom_ref']:.2f}")
    st.write(f"Top rail at ref: {channel['top_ref']:.2f}")
    st.write(f"Overnight low: {overnight_low:.2f}")
    st.write(f"Overnight high: {overnight_high:.2f}")

st.markdown("---")

# ---------------------------------------------------------------
# DOWNLOAD AND PROCESS SPX DATA
# ---------------------------------------------------------------

st.subheader("SPX Data and Daily Card")

with st.spinner("Downloading SPX intraday data from yfinance..."):
    spx_5m = download_spx_intraday(trade_date, interval="5m")

if spx_5m.empty:
    st.error("No SPX data retrieved. Check date or yfinance availability.")
    st.stop()

spx_30m = resample_to_30m(spx_5m)

first_idx = spx_30m.index[0]
spx_open = spx_30m.iloc[0]["Open"]

day_type = classify_day_type(channel, spx_open, first_idx)

card_col1, card_col2 = st.columns(2)

with card_col1:
    st.markdown("### Daily Card - High Level")
    st.write(f"Trade date: {trade_date}")
    st.write(f"SPX open (first 30m candle): {spx_open:.2f}")
    st.write(f"Day type: {day_type}")
    st.write("Options focused bias:")

    if "Ascending channel - open above" in day_type:
        st.write(
            "- Up structure and open above channel, calls at open are extended.\n"
            "- Wait for pullback to a rail and a clean bear candle touch and close above.\n"
            "- Puts only if a strong flip below rails forms."
        )
    elif "Ascending channel - open below" in day_type:
        st.write(
            "- Up structure and open below channel, true bearish day inside uptrend.\n"
            "- Puts can be strong until bottom rail is tagged.\n"
            "- At bottom rail with your candle rule, calls become explosive."
        )
    elif "Descending channel - open below" in day_type:
        st.write(
            "- Down structure and open below, stretched downside.\n"
            "- Wait for bull candle touch and close below rail to take puts.\n"
            "- Calls only if a clear flip above rails forms."
        )
    elif "Descending channel - open above" in day_type:
        st.write(
            "- Down structure and open above, true bullish day inside downtrend.\n"
            "- Early puts are dangerous, calls favored after top rail confirmation.\n"
        )
    else:
        st.write(
            "- Dual or inside structure, treat as potential chop.\n"
            "- Prefer ATM contracts and wait for confirmation."
        )

with card_col2:
    st.markdown("### Expected Move and Option Model")
    proj_move = expected_spx_move(channel, num_blocks=1)
    st.write(f"Projected SPX move next 30 minutes along channel: {proj_move:.2f} points")
    opt_model = suggest_option_contracts(spx_open, proj_move)
    st.write(f"Minimum expected contract move with 0.33 factor: {opt_model['expected_contract_move']:.2f} dollars")

    st.write("Contract suggestions (model based, you will map to real chain):")
    st.write(
        f"- {opt_model['safe']['label']}: strike about {opt_model['safe']['strike']}, {opt_model['safe']['note']}"
    )
    st.write(
        f"- {opt_model['optimal']['label']}: strike about {opt_model['optimal']['strike']}, {opt_model['optimal']['note']}"
    )
    st.write(
        f"- {opt_model['aggressive']['label']}: strike about {opt_model['aggressive']['strike']}, {opt_model['aggressive']['note']}"
    )

st.markdown("---")

# ---------------------------------------------------------------
# CHANNEL TABLE
# ---------------------------------------------------------------

st.subheader("Channel Table - Rails by Time")

times = []
t_cursor = datetime.combine(trade_date, time(8, 30))
market_close = datetime.combine(trade_date, time(15, 0))

while t_cursor <= market_close:
    times.append(t_cursor)
    t_cursor += timedelta(minutes=30)

rows = []
for t in times:
    bottom_primary, top_primary = rail_values_at_time(channel, t, side="primary")

    row = {
        "Time": t.strftime("%H:%M"),
        "Primary Bottom": round(bottom_primary, 2),
        "Primary Top": round(top_primary, 2),
    }

    for level in range(1, channel["offsets"] + 1):
        b_up, t_up = rail_values_at_time(channel, t, side="offset_up", level=level)
        b_down, t_down = rail_values_at_time(channel, t, side="offset_down", level=level)

        row[f"Offset +{level} Bottom"] = round(b_up, 2)
        row[f"Offset +{level} Top"] = round(t_up, 2)
        row[f"Offset -{level} Bottom"] = round(b_down, 2)
        row[f"Offset -{level} Top"] = round(t_down, 2)

    rows.append(row)

df_channels = pd.DataFrame(rows)
st.dataframe(df_channels, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------
# SIGNAL SCAN WITH SECOND CANDLE CONFIRMATION
# ---------------------------------------------------------------

st.subheader("Confirmed Signals (Channel plus Candle Rules plus Second Candle Filter)")

signals = scan_signals_with_confirmation(channel, spx_30m)

if signals:
    df_signals = pd.DataFrame(signals)
    # Make times more readable
    df_signals["signal_time"] = df_signals["signal_time"].dt.strftime("%Y-%m-%d %H:%M")
    df_signals["confirm_time"] = df_signals["confirm_time"].dt.strftime("%Y-%m-%d %H:%M")
    st.write("Confirmed high quality signals:")
    st.dataframe(df_signals, use_container_width=True)
else:
    st.info("No signals passed your strict rules plus second candle confirmation today. That is protective for your account.")

st.markdown(
    """
Notes:
- Entries use your bear or bull candle touch and close rules at the rail, with the 5 point distance filter.
- First 30 minute bar is skipped for entries due to noise and liquidation moves.
- Second candle confirmation must agree with the direction and not violate the rail, which cuts many false starts.
- Options layer is a model based view, you will plug in your broker option chain and still use the 0.33 filter and safe or optimal or aggressive contract logic.
"""
)