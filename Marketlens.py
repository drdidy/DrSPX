# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET V7.0 - STRUCTURAL 0DTE TRADING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import pytz
import json
import os
import math
import time as time_module
from datetime import datetime, date, time, timedelta
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SPX Prophet V7", page_icon="🔮", layout="wide")

CT = pytz.timezone("America/Chicago")
ET = pytz.timezone("America/New_York")
POLYGON_OPTIONS_KEY = "6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ"
SLOPE = 0.48
SAVE_FILE = "spx_prophet_v7_inputs.json"

# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════
class ChannelType(Enum):
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"
    EXPANDING = "EXPANDING"
    CONTRACTING = "CONTRACTING"
    UNDETERMINED = "UNDETERMINED"

class Position(Enum):
    ABOVE = "ABOVE"
    INSIDE = "INSIDE"
    BELOW = "BELOW"

class MMBias(Enum):
    CALLS_HEAVY = "CALLS_HEAVY"
    PUTS_HEAVY = "PUTS_HEAVY"
    NEUTRAL = "NEUTRAL"

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
def now_ct():
    return datetime.now(CT)

def blocks_between(start, end):
    if start is None or end is None or end <= start:
        return 0
    return max(0, int((end - start).total_seconds() / 1800))

def save_inputs(data):
    try:
        with open(SAVE_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass

def load_inputs():
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

# ═══════════════════════════════════════════════════════════════════════════════
# BLACK-SCHOLES
# ═══════════════════════════════════════════════════════════════════════════════
def norm_cdf(x):
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p, sign = 0.3275911, 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)

def black_scholes(S, K, T, r, sigma, opt_type):
    if T <= 0:
        return max(0, S - K) if opt_type == "CALL" else max(0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt_type == "CALL":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

def get_strike(entry_level, direction):
    if direction == "CALLS":
        return int(round((entry_level + 15) / 5) * 5)
    return int(round((entry_level - 15) / 5) * 5)

def estimate_premium(entry_spx, direction, vix, hours_to_expiry):
    strike = get_strike(entry_spx, direction)
    opt_type = "CALL" if direction == "CALLS" else "PUT"
    iv_mult = 2.0 if hours_to_expiry < 3 else 1.8 if hours_to_expiry < 5 else 1.5
    iv = max((vix / 100) * iv_mult, 0.20)
    T = max(0.0001, hours_to_expiry / (365 * 24))
    premium = black_scholes(entry_spx, strike, T, 0.05, iv, opt_type)
    return max(round(premium, 2), 0.10), strike

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def fetch_es_current():
    try:
        es = yf.Ticker("ES=F")
        d = es.history(period="2d", interval="5m")
        if d is not None and not d.empty:
            return round(float(d['Close'].iloc[-1]), 2)
    except:
        pass
    return None

@st.cache_data(ttl=120, show_spinner=False)
def fetch_es_candles(days=7):
    try:
        es = yf.Ticker("ES=F")
        data = es.history(period=f"{days}d", interval="30m")
        if data is not None and not data.empty and len(data) > 10:
            return data
    except:
        pass
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix():
    try:
        vix = yf.Ticker("^VIX")
        data = vix.history(period="2d")
        if data is not None and not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except:
        pass
    return 16.0

@st.cache_data(ttl=300, show_spinner=False)
def fetch_put_call_ratio(target_date=None):
    """
    Fetch Put/Call Open Interest from Polygon
    Uses TODAY's date for expiration (like working tester)
    """
    # Use TODAY's date - this is what the working tester used
    expiration_date = date.today().isoformat()
    
    url = "https://api.polygon.io/v3/snapshot/options/SPY"
    params = {
        "expiration_date": expiration_date,
        "limit": 250,
        "apiKey": POLYGON_OPTIONS_KEY
    }
    
    all_results = []
    error_msg = None
    
    try:
        while True:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code != 200:
                error_msg = f"API status {r.status_code}"
                break
            data = r.json()
            if "results" not in data:
                error_msg = data.get("message", "No results")
                break
            all_results.extend(data["results"])
            if "next_url" in data:
                url = data["next_url"]
                params = {"apiKey": POLYGON_OPTIONS_KEY}
            else:
                break
    except Exception as e:
        error_msg = str(e)
    
    # Extract OI - exact same as working tester
    total_calls_oi = 0
    total_puts_oi = 0
    debug_sample = all_results[0] if all_results else None
    
    for opt in all_results:
        details = opt.get("details", {})
        day = opt.get("day", {})
        
        contract_type = details.get("contract_type", "").lower()
        oi = day.get("open_interest", 0) or 0
        
        if contract_type == "call":
            total_calls_oi += oi
        elif contract_type == "put":
            total_puts_oi += oi
    
    # Calculate ratio and bias
    if total_calls_oi > 0:
        ratio = round(total_puts_oi / total_calls_oi, 4)
    else:
        ratio = 1.0
    
    if total_calls_oi > total_puts_oi * 1.1:
        bias = MMBias.CALLS_HEAVY
    elif total_puts_oi > total_calls_oi * 1.1:
        bias = MMBias.PUTS_HEAVY
    else:
        bias = MMBias.NEUTRAL
    
    return {
        "calls_oi": total_calls_oi,
        "puts_oi": total_puts_oi,
        "ratio": ratio,
        "bias": bias,
        "error": error_msg if (total_calls_oi == 0 and total_puts_oi == 0) else None,
        "contracts_found": len(all_results),
        "expiration_used": expiration_date,
        "debug_sample": debug_sample
    }

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def extract_sessions(es_candles, trading_date):
    if es_candles is None or es_candles.empty:
        return None
    
    result = {}
    overnight_day = trading_date - timedelta(days=1)
    if overnight_day.weekday() >= 5:
        overnight_day -= timedelta(days=(overnight_day.weekday() - 4))
    
    df = es_candles.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize(ET).tz_convert(CT)
    else:
        df.index = df.index.tz_convert(CT)
    
    # Session times (CT)
    sessions = {
        "sydney": (CT.localize(datetime.combine(overnight_day, time(17, 0))),
                   CT.localize(datetime.combine(overnight_day, time(20, 30)))),
        "tokyo": (CT.localize(datetime.combine(overnight_day, time(21, 0))),
                  CT.localize(datetime.combine(trading_date, time(1, 30)))),
        "london": (CT.localize(datetime.combine(trading_date, time(2, 0))),
                   CT.localize(datetime.combine(trading_date, time(4, 0)))),
        "overnight": (CT.localize(datetime.combine(overnight_day, time(17, 0))),
                      CT.localize(datetime.combine(trading_date, time(8, 30))))
    }
    
    for name, (start, end) in sessions.items():
        mask = (df.index >= start) & (df.index <= end)
        data = df[mask]
        if not data.empty:
            result[name] = {
                "high": round(data['High'].max(), 2),
                "low": round(data['Low'].min(), 2),
                "high_time": data['High'].idxmax(),
                "low_time": data['Low'].idxmin()
            }
    
    # Prior RTH
    prior_day = trading_date - timedelta(days=1)
    if prior_day.weekday() >= 5:
        prior_day -= timedelta(days=(prior_day.weekday() - 4))
    prior_start = CT.localize(datetime.combine(prior_day, time(8, 30)))
    prior_end = CT.localize(datetime.combine(prior_day, time(15, 0)))
    prior_mask = (df.index >= prior_start) & (df.index <= prior_end)
    prior_data = df[prior_mask]
    if not prior_data.empty:
        result["prior_close"] = round(prior_data['Close'].iloc[-1], 2)
        result["prior_high"] = round(prior_data['High'].max(), 2)
        result["prior_low"] = round(prior_data['Low'].min(), 2)
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL LOGIC
# ═══════════════════════════════════════════════════════════════════════════════
def determine_channel(sydney, tokyo):
    """
    ASCENDING:   Tokyo High > Sydney High
    DESCENDING:  Tokyo Low < Sydney Low
    EXPANDING:   Both
    CONTRACTING: Neither
    """
    if not sydney or not tokyo:
        return ChannelType.UNDETERMINED, "Missing data"
    
    higher_high = tokyo["high"] > sydney["high"]
    lower_low = tokyo["low"] < sydney["low"]
    
    if higher_high and lower_low:
        return ChannelType.EXPANDING, f"Tokyo expanded both (H:{tokyo['high']}>{sydney['high']}, L:{tokyo['low']}<{sydney['low']})"
    elif not higher_high and not lower_low:
        return ChannelType.CONTRACTING, f"Tokyo contracted (H:{tokyo['high']}≤{sydney['high']}, L:{tokyo['low']}≥{sydney['low']})"
    elif higher_high:
        return ChannelType.ASCENDING, f"Tokyo High ({tokyo['high']}) > Sydney High ({sydney['high']})"
    else:
        return ChannelType.DESCENDING, f"Tokyo Low ({tokyo['low']}) < Sydney Low ({sydney['low']})"

def calc_channel_levels(overnight, ref_time, channel_type):
    """Calculate ceiling/floor with 0.48 slope"""
    if not overnight:
        return None, None
    
    on_high, on_low = overnight["high"], overnight["low"]
    blocks_high = blocks_between(overnight.get("high_time"), ref_time)
    blocks_low = blocks_between(overnight.get("low_time"), ref_time)
    
    if channel_type == ChannelType.ASCENDING:
        ceiling = round(on_high + SLOPE * blocks_high, 2)
        floor = round(on_low + SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.DESCENDING:
        ceiling = round(on_high - SLOPE * blocks_high, 2)
        floor = round(on_low - SLOPE * blocks_low, 2)
    else:
        ceiling, floor = on_high, on_low
    
    return ceiling, floor

def get_position(price, ceiling, floor):
    if price > ceiling:
        return Position.ABOVE
    elif price < floor:
        return Position.BELOW
    return Position.INSIDE

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO GENERATION
# ═══════════════════════════════════════════════════════════════════════════════
def generate_scenarios(channel_type, position, ceiling_es, floor_es, mm_bias, offset, vix, hours_to_expiry):
    scenarios = []
    ceiling_spx = round(ceiling_es - offset, 2)
    floor_spx = round(floor_es - offset, 2)
    mid_spx = round((ceiling_spx + floor_spx) / 2, 2)
    
    def add(condition, action, entry_spx, direction, target_spx, trigger, notes, confidence="HIGH"):
        premium, strike = estimate_premium(entry_spx, direction, vix, hours_to_expiry) if direction != "NO_TRADE" else (0, 0)
        scenarios.append({
            "condition": condition, "action": action,
            "entry_spx": entry_spx, "direction": direction,
            "target_spx": target_spx, "trigger": trigger,
            "notes": notes, "confidence": confidence,
            "premium": premium, "strike": strike
        })
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ASCENDING CHANNEL
    # ═══════════════════════════════════════════════════════════════════════════
    if channel_type == ChannelType.ASCENDING:
        if position == Position.ABOVE:
            if mm_bias == MMBias.CALLS_HEAVY:
                add("ABOVE + Calls Heavy", "Price breaks through ceiling, rallies back", ceiling_spx, "PUTS", floor_spx,
                    "Wait for rally back to ceiling, enter PUTS on rejection", "MMs destroy call buyers → push to floor")
                add("ABOVE + Calls Heavy (Alt)", "If price reaches floor", floor_spx, "CALLS", ceiling_spx,
                    "Price touches floor and closes above", "Bounce from floor to ceiling", "MEDIUM")
            else:
                add("ABOVE ascending", "Price drops to ceiling for support", ceiling_spx, "CALLS", ceiling_spx + 20,
                    "Price touches ceiling and holds (closes above)", "Ceiling is support in ascending channel")
        
        elif position == Position.INSIDE:
            add("INSIDE → Breaks UP", "Break above ceiling, retrace for entry", ceiling_spx, "CALLS", ceiling_spx + 25,
                "30-min close above ceiling, then retrace to ceiling", "Ceiling becomes support after break")
            add("INSIDE → Breaks DOWN", "Break below floor, rally back for entry", floor_spx, "PUTS", floor_spx - 25,
                "30-min close below floor, then rally back to floor", "Floor becomes resistance after break")
            add("INSIDE → Touch floor, close inside", "Rejection at floor", floor_spx, "CALLS", ceiling_spx,
                "Candle touches floor but closes above it", "Floor rejection = bullish in ascending")
            add("INSIDE → Touch ceiling, close inside", "Rejection at ceiling, wait for dip", floor_spx, "CALLS", ceiling_spx,
                "Wait for drop to floor, enter CALLS", "Buy the dip in ascending channel", "MEDIUM")
        
        elif position == Position.BELOW:
            add("BELOW ascending", "Rally to floor, rejection", floor_spx, "PUTS", floor_spx - 25,
                "Rally to floor, touch it, close below = PUTS", "Floor is resistance when below ascending channel")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DESCENDING CHANNEL
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.DESCENDING:
        if position == Position.BELOW:
            if mm_bias == MMBias.PUTS_HEAVY:
                add("BELOW + Puts Heavy", "Price breaks through floor, drops back", floor_spx, "CALLS", ceiling_spx,
                    "Wait for drop back to floor, enter CALLS on support", "MMs destroy put buyers → push to ceiling")
                add("BELOW + Puts Heavy (Alt)", "If price reaches ceiling", ceiling_spx, "PUTS", floor_spx,
                    "Price touches ceiling and closes below", "Fade rally from ceiling", "MEDIUM")
            else:
                add("BELOW descending", "Price rallies to floor for resistance", floor_spx, "PUTS", floor_spx - 20,
                    "Price touches floor and fails (closes below)", "Floor is resistance in descending channel")
        
        elif position == Position.INSIDE:
            add("INSIDE → Breaks DOWN", "Break below floor, retrace for entry", floor_spx, "PUTS", floor_spx - 25,
                "30-min close below floor, then retrace to floor", "Floor becomes resistance after break")
            add("INSIDE → Breaks UP", "Break above ceiling, drop back for entry", ceiling_spx, "CALLS", ceiling_spx + 25,
                "30-min close above ceiling, then drop back to ceiling", "Ceiling becomes support after break")
            add("INSIDE → Touch ceiling, close inside", "Rejection at ceiling", ceiling_spx, "PUTS", floor_spx,
                "Candle touches ceiling but closes below it", "Ceiling rejection = bearish in descending")
            add("INSIDE → Touch floor, close inside", "Rejection at floor, wait for rally", ceiling_spx, "PUTS", floor_spx,
                "Wait for rally to ceiling, enter PUTS", "Sell the rally in descending channel", "MEDIUM")
        
        elif position == Position.ABOVE:
            add("ABOVE descending", "Drop to ceiling, support", ceiling_spx, "CALLS", ceiling_spx + 25,
                "Drop to ceiling, touch it, close above = CALLS", "Ceiling is support when above descending channel")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXPANDING - Trade Boundaries
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.EXPANDING:
        add("EXPANDING → At Ceiling", "Fade extremes", ceiling_spx, "PUTS", mid_spx,
            "Price reaches ceiling → PUTS to midpoint", "Expanding = fade extremes", "MEDIUM")
        add("EXPANDING → At Floor", "Fade extremes", floor_spx, "CALLS", mid_spx,
            "Price reaches floor → CALLS to midpoint", "Expanding = fade extremes", "MEDIUM")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTRACTING - NO TRADE
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.CONTRACTING:
        add("CONTRACTING", "NO TRADE", 0, "NO_TRADE", 0,
            "Do not trade contracting channels", "Wait for channel to expand", "N/A")
    
    return scenarios

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def sidebar():
    saved = load_inputs()
    with st.sidebar:
        st.title("🔮 SPX Prophet V7")
        st.caption("Structural 0DTE System")
        st.divider()
        
        trading_date = st.date_input("📅 Trading Date", value=date.today())
        offset = st.number_input("⚙️ ES→SPX Offset", value=float(saved.get("offset", 18.0)), step=0.5)
        
        st.divider()
        override = st.checkbox("📝 Manual Session Override")
        manual = {}
        if override:
            c1, c2 = st.columns(2)
            manual["sydney_high"] = c1.number_input("Sydney High", value=6075.0, step=0.5)
            manual["sydney_low"] = c2.number_input("Sydney Low", value=6050.0, step=0.5)
            manual["tokyo_high"] = c1.number_input("Tokyo High", value=6080.0, step=0.5)
            manual["tokyo_low"] = c2.number_input("Tokyo Low", value=6045.0, step=0.5)
            manual["current_es"] = st.number_input("Current ES", value=6065.0, step=0.5)
        
        st.divider()
        pc_override = st.checkbox("📊 Manual P/C Override")
        pc_manual = {}
        if pc_override:
            c1, c2 = st.columns(2)
            pc_manual["calls_oi"] = c1.number_input("Calls OI", value=500000, step=10000)
            pc_manual["puts_oi"] = c2.number_input("Puts OI", value=400000, step=10000)
        
        st.divider()
        ref_time = st.selectbox("⏰ Reference Time", ["9:00 AM", "9:30 AM", "10:00 AM"])
        debug = st.checkbox("🔧 Debug Mode")
        
        c1, c2 = st.columns(2)
        if c1.button("💾 Save", use_container_width=True):
            save_inputs({"offset": offset})
            st.success("Saved!")
        if c2.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    ref_map = {"9:00 AM": (9, 0), "9:30 AM": (9, 30), "10:00 AM": (10, 0)}
    return {
        "trading_date": trading_date, "offset": offset, "override": override,
        "manual": manual, "pc_override": pc_override, "pc_manual": pc_manual,
        "ref_time": ref_map[ref_time], "debug": debug
    }

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    inputs = sidebar()
    now = now_ct()
    
    # Fetch data
    with st.spinner("Loading..."):
        es_candles = fetch_es_candles(7)
        if inputs["override"] and inputs["manual"].get("current_es"):
            current_es = inputs["manual"]["current_es"]
        else:
            current_es = fetch_es_current() or 6050
        vix = fetch_vix()
        
        # P/C data - use manual if enabled, otherwise fetch for trading date
        if inputs["pc_override"] and inputs["pc_manual"]:
            calls_oi = inputs["pc_manual"]["calls_oi"]
            puts_oi = inputs["pc_manual"]["puts_oi"]
            ratio = round(puts_oi / calls_oi, 4) if calls_oi > 0 else 1.0
            if calls_oi > puts_oi * 1.1:
                mm_bias = MMBias.CALLS_HEAVY
            elif puts_oi > calls_oi * 1.1:
                mm_bias = MMBias.PUTS_HEAVY
            else:
                mm_bias = MMBias.NEUTRAL
            pc_data = {"calls_oi": calls_oi, "puts_oi": puts_oi, "ratio": ratio, "bias": mm_bias, "error": None}
        else:
            pc_data = fetch_put_call_ratio(inputs["trading_date"])
    
    offset = inputs["offset"]
    current_spx = round(current_es - offset, 2)
    
    # Sessions
    if inputs["override"]:
        m = inputs["manual"]
        sydney = {"high": m["sydney_high"], "low": m["sydney_low"]}
        tokyo = {"high": m["tokyo_high"], "low": m["tokyo_low"]}
        overnight = {
            "high": max(m["sydney_high"], m["tokyo_high"]),
            "low": min(m["sydney_low"], m["tokyo_low"]),
            "high_time": CT.localize(datetime.combine(inputs["trading_date"] - timedelta(days=1), time(22, 0))),
            "low_time": CT.localize(datetime.combine(inputs["trading_date"], time(2, 0)))
        }
    else:
        sessions = extract_sessions(es_candles, inputs["trading_date"]) or {}
        sydney = sessions.get("sydney")
        tokyo = sessions.get("tokyo")
        overnight = sessions.get("overnight")
    
    # Channel
    channel_type, channel_reason = determine_channel(sydney, tokyo)
    ref_time = CT.localize(datetime.combine(inputs["trading_date"], time(*inputs["ref_time"])))
    ceiling_es, floor_es = calc_channel_levels(overnight, ref_time, channel_type)
    
    if ceiling_es is None:
        ceiling_es, floor_es = 6080, 6040
    
    ceiling_spx = round(ceiling_es - offset, 2)
    floor_spx = round(floor_es - offset, 2)
    position = get_position(current_es, ceiling_es, floor_es)
    mm_bias = pc_data["bias"]
    pc_error = pc_data.get("error")
    
    hours_to_expiry = max(0.5, (CT.localize(datetime.combine(inputs["trading_date"], time(15, 0))) - now).total_seconds() / 3600)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI
    # ═══════════════════════════════════════════════════════════════════════════
    st.title("🔮 SPX Prophet V7")
    st.caption("Three Pillars. One Vision. Total Clarity.")
    
    # Channel Banner
    colors = {
        ChannelType.ASCENDING: ("🟢", "green"),
        ChannelType.DESCENDING: ("🔴", "red"),
        ChannelType.EXPANDING: ("🟣", "violet"),
        ChannelType.CONTRACTING: ("🟡", "orange")
    }
    icon, color = colors.get(channel_type, ("⚪", "gray"))
    
    col1, col2, col3 = st.columns([2, 1, 1])
    col1.metric(f"{icon} Channel", channel_type.value, channel_reason)
    col2.metric("SPX", f"{current_spx:,.2f}", f"ES {current_es:,.2f}")
    col3.metric("Position", position.value)
    
    # NO TRADE Warning
    if channel_type == ChannelType.CONTRACTING:
        st.warning("⚠️ **NO TRADE — CONTRACTING CHANNEL**\n\nTokyo contracted inside Sydney. Wait for expansion.")
    
    st.divider()
    
    # Sessions
    st.subheader("🌏 Session Data")
    c1, c2, c3, c4 = st.columns(4)
    
    def show_session(col, name, emoji, data):
        with col:
            st.markdown(f"**{emoji} {name}**")
            if data:
                st.write(f"High: **{data['high']}**")
                st.write(f"Low: **{data['low']}**")
            else:
                st.write("No data")
    
    show_session(c1, "Sydney", "🦘", sydney)
    show_session(c2, "Tokyo", "🗼", tokyo)
    show_session(c3, "London", "🏛️", sessions.get("london") if not inputs["override"] else None)
    show_session(c4, "Overnight", "🌙", overnight)
    
    st.divider()
    
    # MM Bias
    st.subheader("🏦 Market Maker Bias")
    calls_oi = pc_data.get("calls_oi", 0)
    puts_oi = pc_data.get("puts_oi", 0)
    ratio = pc_data["ratio"]
    total = calls_oi + puts_oi
    contracts_found = pc_data.get("contracts_found", 0)
    exp_used = pc_data.get("expiration_used", "")
    
    # Show error if API failed
    if pc_error and total == 0:
        st.warning(f"⚠️ P/C API Error: {pc_error}\n\nUse **Manual P/C Override** in sidebar to enter data manually.")
    elif contracts_found > 0:
        st.caption(f"📊 Found {contracts_found:,} contracts for {exp_used} | Using Open Interest for MM bias")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Calls OI", f"{calls_oi:,}")
    c2.metric("Puts OI", f"{puts_oi:,}")
    c3.metric("P/C Ratio", f"{ratio:.2f}")
    
    if total > 0:
        calls_pct = calls_oi / total
        st.progress(calls_pct, text=f"CALLS {calls_pct*100:.0f}% | PUTS {(1-calls_pct)*100:.0f}%")
    
    if mm_bias == MMBias.CALLS_HEAVY:
        st.error("📉 **CALLS HEAVY** — MMs will push price DOWN toward floor")
    elif mm_bias == MMBias.PUTS_HEAVY:
        st.success("📈 **PUTS HEAVY** — MMs will push price UP toward ceiling")
    else:
        st.info("⚖️ **NEUTRAL** — No strong directional bias")
    
    st.divider()
    
    # Channel Levels
    st.subheader("📊 Channel Levels @ 9:00 AM")
    c1, c2 = st.columns(2)
    c1.metric("🟢 Ceiling", f"{ceiling_spx}", f"ES {ceiling_es}")
    c2.metric("🔴 Floor", f"{floor_spx}", f"ES {floor_es}")
    
    st.divider()
    
    # Scenarios
    if channel_type != ChannelType.CONTRACTING:
        st.subheader("🎯 Trade Scenarios")
        scenarios = generate_scenarios(channel_type, position, ceiling_es, floor_es, mm_bias, offset, vix, hours_to_expiry)
        
        for s in scenarios:
            direction = s["direction"]
            if direction == "CALLS":
                box = st.container(border=True)
                box.markdown(f"### 🟢 {s['condition']}")
            elif direction == "PUTS":
                box = st.container(border=True)
                box.markdown(f"### 🔴 {s['condition']}")
            else:
                box = st.container(border=True)
                box.markdown(f"### ⚠️ {s['condition']}")
            
            with box:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Entry", f"{s['entry_spx']}")
                c2.metric("Strike", f"{s['strike']}")
                c3.metric("Premium", f"${s['premium']:.2f}")
                c4.metric("Target", f"{s['target_spx']}")
                
                st.markdown(f"**Action:** {s['action']}")
                st.markdown(f"**Trigger:** {s['trigger']}")
                st.caption(f"💡 {s['notes']} | Confidence: {s['confidence']}")
    
    # Debug
    if inputs["debug"]:
        with st.expander("🔧 Debug"):
            st.json({
                "sydney": sydney, "tokyo": tokyo, "overnight": overnight,
                "channel": channel_type.value, "ceiling_es": ceiling_es, "floor_es": floor_es,
                "position": position.value, "mm_bias": mm_bias.value,
                "pc_data": {"calls": calls_oi, "puts": puts_oi, "ratio": ratio, "contracts": pc_data.get("contracts_found", 0)},
                "pc_debug_sample": pc_data.get("debug_sample")
            })

if __name__ == "__main__":
    main()
