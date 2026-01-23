# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET - STRUCTURAL 0DTE TRADING SYSTEM
# "Where Structure Becomes Foresight"
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
from datetime import datetime, date, time, timedelta
from enum import Enum
from typing import Optional, Dict

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SPX Prophet", page_icon="◭", layout="wide")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
CT = pytz.timezone("America/Chicago")
ET = pytz.timezone("America/New_York")
UTC = pytz.UTC

SLOPE = 0.48
SAVE_FILE = "spx_prophet_inputs.json"

POLYGON_API_KEY = "jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm"
POLYGON_BASE_URL = "https://api.polygon.io"

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

class Bias(Enum):
    CALLS = "CALLS"
    PUTS = "PUTS"
    NEUTRAL = "NEUTRAL"

class VIXPosition(Enum):
    ABOVE_RANGE = "ABOVE"
    IN_RANGE = "IN RANGE"
    BELOW_RANGE = "BELOW"
    UNKNOWN = "UNKNOWN"

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

def get_prior_trading_day(ref_date):
    prior = ref_date - timedelta(days=1)
    while prior.weekday() >= 5:
        prior -= timedelta(days=1)
    return prior
# ═══════════════════════════════════════════════════════════════════════════════
# BLACK-SCHOLES PRICING
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

def calc_0dte_iv(vix, hours_to_expiry):
    if hours_to_expiry > 5:
        mult = 1.6
    elif hours_to_expiry > 3:
        mult = 1.7
    else:
        mult = 1.8
    return max((vix / 100) * mult, 0.15)

def estimate_0dte_premium(spot, strike, hours_to_expiry, vix, opt_type):
    iv = calc_0dte_iv(vix, hours_to_expiry)
    T = max(0.0001, hours_to_expiry / (365 * 24))
    premium = black_scholes(spot, strike, T, 0.05, iv, opt_type)
    return max(round(premium, 2), 0.05)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING - Yahoo Finance
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

@st.cache_data(ttl=60, show_spinner=False)
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
@st.cache_data(ttl=60, show_spinner=False)
def fetch_es_with_ema():
    """Fetch ES futures with EMAs based on 30-minute chart from Polygon."""
    result = {
        "price": None, "ema_200": None, "ema_8": None, "ema_21": None,
        "above_200": None, "ema_cross": None, "ema_bias": Bias.NEUTRAL
    }
    try:
        # Fetch 30-minute candles for ES futures - need ~15 trading days for 200 periods
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d")
        
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/C:ESH25/range/30/minute/{start_date}/{end_date}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 200:
                df = pd.DataFrame(data["results"])
                df['datetime'] = pd.to_datetime(df['t'], unit='ms', utc=True).dt.tz_convert(CT)
                df = df.sort_values('datetime')
                
                # Calculate EMAs on 30-minute closes
                df['EMA_8'] = df['c'].ewm(span=8, adjust=False).mean()
                df['EMA_21'] = df['c'].ewm(span=21, adjust=False).mean()
                df['EMA_200'] = df['c'].ewm(span=200, adjust=False).mean()
                
                result["price"] = round(float(df['c'].iloc[-1]), 2)
                result["ema_8"] = round(float(df['EMA_8'].iloc[-1]), 2)
                result["ema_21"] = round(float(df['EMA_21'].iloc[-1]), 2)
                result["ema_200"] = round(float(df['EMA_200'].iloc[-1]), 2)
                result["above_200"] = result["price"] > result["ema_200"]
                result["ema_cross"] = "BULLISH" if result["ema_8"] > result["ema_21"] else "BEARISH"
                
                if result["above_200"] and result["ema_cross"] == "BULLISH":
                    result["ema_bias"] = Bias.CALLS
                elif not result["above_200"] and result["ema_cross"] == "BEARISH":
                    result["ema_bias"] = Bias.PUTS
                else:
                    result["ema_bias"] = Bias.NEUTRAL
    except:
        pass
    return result

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix_yahoo():
    try:
        vix = yf.Ticker("^VIX")
        data = vix.history(period="2d")
        if data is not None and not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except:
        pass
    return 16.0

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING - Polygon API
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix_polygon():
    try:
        url = f"{POLYGON_BASE_URL}/v3/snapshot?ticker.any_of=I:VIX"
        params = {"apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                return round(float(data["results"][0].get("value", 0)), 2)
    except:
        pass
    return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_vix_overnight_range(trading_date, zone_start_hour=2, zone_start_min=0, zone_end_hour=6, zone_end_min=0):
    result = {"bottom": None, "top": None, "range_size": None, "available": False}
    try:
        date_str = trading_date.strftime("%Y-%m-%d")
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/I:VIX/range/1/minute/{date_str}/{date_str}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                df = pd.DataFrame(data["results"])
                df['datetime'] = pd.to_datetime(df['t'], unit='ms', utc=True).dt.tz_convert(CT)
                zone_start = CT.localize(datetime.combine(trading_date, time(zone_start_hour, zone_start_min)))
                zone_end = CT.localize(datetime.combine(trading_date, time(zone_end_hour, zone_end_min)))
                zone_df = df[(df['datetime'] >= zone_start) & (df['datetime'] <= zone_end)]
                if not zone_df.empty and len(zone_df) > 5:
                    result["bottom"] = round(float(zone_df['l'].min()), 2)
                    result["top"] = round(float(zone_df['h'].max()), 2)
                    result["range_size"] = round(result["top"] - result["bottom"], 2)
                    result["available"] = True
    except:
        pass
    return result

def get_vix_position(current_vix, vix_range):
    if not vix_range["available"] or current_vix is None:
        return VIXPosition.UNKNOWN, "No range data"
    bottom, top = vix_range["bottom"], vix_range["top"]
    if current_vix > top:
        return VIXPosition.ABOVE_RANGE, f"{round(current_vix - top, 1)} above"
    elif current_vix < bottom:
        return VIXPosition.BELOW_RANGE, f"{round(bottom - current_vix, 1)} below"
    else:
        return VIXPosition.IN_RANGE, f"Within {bottom}-{top}"

# ═══════════════════════════════════════════════════════════════════════════════
# RETAIL POSITIONING
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def fetch_retail_positioning():
    result = {"vix": None, "vix3m": None, "spread": None, "positioning": "BALANCED", "warning": None, "bias": Bias.NEUTRAL}
    try:
        vix_data = yf.Ticker("^VIX").history(period="2d")
        vix3m_data = yf.Ticker("^VIX3M").history(period="2d")
        if not vix_data.empty and not vix3m_data.empty:
            vix = round(float(vix_data['Close'].iloc[-1]), 2)
            vix3m = round(float(vix3m_data['Close'].iloc[-1]), 2)
            spread = round(vix - vix3m, 2)
            result["vix"], result["vix3m"], result["spread"] = vix, vix3m, spread
            if spread <= -3.0:
                result["positioning"], result["warning"], result["bias"] = "CALL BUYING EXTREME", "Extreme complacency - high fade probability", Bias.PUTS
            elif spread <= -1.5:
                result["positioning"], result["warning"], result["bias"] = "CALL BUYING HEAVY", "Market often fades the crowd", Bias.PUTS
            elif spread >= 3.0:
                result["positioning"], result["warning"], result["bias"] = "PUT BUYING EXTREME", "Extreme fear - high fade probability", Bias.CALLS
            elif spread >= 1.5:
                result["positioning"], result["warning"], result["bias"] = "PUT BUYING HEAVY", "Market often fades the crowd", Bias.CALLS
    except:
        pass
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# PRIOR DAY RTH DATA
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=600, show_spinner=False)
def fetch_prior_day_rth(trading_date):
    """Fetch prior day's RTH (Regular Trading Hours) data for ES futures.
    RTH is 8:30 AM - 3:00 PM CT (9:30 AM - 4:00 PM ET)
    
    Returns:
    - highest_wick: The highest high (wick) of any RTH candle
    - lowest_close: The lowest close of any RTH candle
    """
    result = {
        "highest_wick": None, "highest_wick_time": None,
        "lowest_close": None, "lowest_close_time": None,
        "high": None, "low": None, "close": None,  # Keep for display
        "available": False
    }
    try:
        prior_day = get_prior_trading_day(trading_date)
        date_str = prior_day.strftime("%Y-%m-%d")
        
        # Fetch 5-minute candles for ES futures
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/C:ESH25/range/5/minute/{date_str}/{date_str}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                df = pd.DataFrame(data["results"])
                df['datetime'] = pd.to_datetime(df['t'], unit='ms', utc=True).dt.tz_convert(CT)
                
                # RTH hours: 8:30 AM - 3:00 PM CT
                rth_start = CT.localize(datetime.combine(prior_day, time(8, 30)))
                rth_end = CT.localize(datetime.combine(prior_day, time(15, 0)))
                
                rth_df = df[(df['datetime'] >= rth_start) & (df['datetime'] <= rth_end)]
                
                if not rth_df.empty and len(rth_df) > 5:
                    # Highest Wick = highest high of any candle
                    high_idx = rth_df['h'].idxmax()
                    result["highest_wick"] = round(float(rth_df.loc[high_idx, 'h']), 2)
                    result["highest_wick_time"] = rth_df.loc[high_idx, 'datetime']
                    
                    # Lowest Close = lowest close of any candle (NOT lowest wick)
                    lowest_close_idx = rth_df['c'].idxmin()
                    result["lowest_close"] = round(float(rth_df.loc[lowest_close_idx, 'c']), 2)
                    result["lowest_close_time"] = rth_df.loc[lowest_close_idx, 'datetime']
                    
                    # Also store overall H/L/C for display
                    result["high"] = result["highest_wick"]
                    result["low"] = round(float(rth_df['l'].min()), 2)
                    result["close"] = round(float(rth_df.iloc[-1]['c']), 2)
                    result["available"] = True
    except:
        pass
    return result

def calc_prior_day_targets(prior_rth, ref_time, position, overnight_ceiling, overnight_floor):
    """Calculate targets from prior day when price is outside overnight cone.
    - Above overnight: Target ascending (+0.48/30min) from prior day HIGHEST WICK
    - Below overnight: Target descending (-0.48/30min) from prior day LOWEST CLOSE
    """
    if not prior_rth["available"]:
        return None, None, None
    
    if position == Position.ABOVE and prior_rth["highest_wick"] is not None:
        # Ascending target from prior day highest wick
        blocks = blocks_between(prior_rth["highest_wick_time"], ref_time) if prior_rth["highest_wick_time"] else 0
        target = round(prior_rth["highest_wick"] + SLOPE * blocks, 2)
        return target, "ASCENDING", f"Prior RTH Highest Wick ({prior_rth['highest_wick']:.2f}) + {blocks} blocks × {SLOPE}"
    
    elif position == Position.BELOW and prior_rth["lowest_close"] is not None:
        # Descending target from prior day lowest close
        blocks = blocks_between(prior_rth["lowest_close_time"], ref_time) if prior_rth["lowest_close_time"] else 0
        target = round(prior_rth["lowest_close"] - SLOPE * blocks, 2)
        return target, "DESCENDING", f"Prior RTH Lowest Close ({prior_rth['lowest_close']:.2f}) - {blocks} blocks × {SLOPE}"
    
    return None, None, None
    
    return None, None, None

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def extract_sessions(es_candles, trading_date):
    if es_candles is None or es_candles.empty:
        return None
    result = {}
    overnight_day = get_prior_trading_day(trading_date)
    df = es_candles.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize(ET).tz_convert(CT)
    else:
        df.index = df.index.tz_convert(CT)
    
    sessions = {
        "sydney": (CT.localize(datetime.combine(overnight_day, time(17, 0))),
                   CT.localize(datetime.combine(overnight_day, time(20, 30)))),
        "tokyo": (CT.localize(datetime.combine(overnight_day, time(21, 0))),
                  CT.localize(datetime.combine(trading_date, time(1, 30)))),
        "london": (CT.localize(datetime.combine(trading_date, time(2, 0))),
                   CT.localize(datetime.combine(trading_date, time(5, 30)))),  # London ends at 5:30 AM CT
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
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL LOGIC
# ═══════════════════════════════════════════════════════════════════════════════
def determine_channel(sydney, tokyo, london=None):
    if not sydney or not tokyo:
        return ChannelType.UNDETERMINED, "Missing session data", None, None, None, None
    
    all_highs = [(sydney["high"], sydney.get("high_time"), "Sydney"), (tokyo["high"], tokyo.get("high_time"), "Tokyo")]
    all_lows = [(sydney["low"], sydney.get("low_time"), "Sydney"), (tokyo["low"], tokyo.get("low_time"), "Tokyo")]
    
    if london:
        all_highs.append((london["high"], london.get("high_time"), "London"))
        all_lows.append((london["low"], london.get("low_time"), "London"))
    
    highest = max(all_highs, key=lambda x: x[0])
    lowest = min(all_lows, key=lambda x: x[0])
    true_high, high_time, high_session = highest
    true_low, low_time, low_session = lowest
    
    # Check session-to-session expansions
    tokyo_high_expansion = tokyo["high"] - sydney["high"]  # How much Tokyo exceeded Sydney's high
    tokyo_low_expansion = sydney["low"] - tokyo["low"]      # How much Tokyo went below Sydney's low
    
    tokyo_expanded_high = tokyo_high_expansion > 0
    tokyo_expanded_low = tokyo_low_expansion > 0
    
    london_high_expansion = 0
    london_low_expansion = 0
    london_expanded_high = False
    london_expanded_low = False
    
    if london:
        prior_high = max(sydney["high"], tokyo["high"])
        prior_low = min(sydney["low"], tokyo["low"])
        london_high_expansion = london["high"] - prior_high  # How much London exceeded prior high
        london_low_expansion = prior_low - london["low"]      # How much London went below prior low
        london_expanded_high = london_high_expansion > 0
        london_expanded_low = london_low_expansion > 0
    
    expanded_high = tokyo_expanded_high or london_expanded_high
    expanded_low = tokyo_expanded_low or london_expanded_low
    
    # Check for dominant expansion (>6 points in one direction)
    max_high_expansion = max(tokyo_high_expansion, london_high_expansion)
    max_low_expansion = max(tokyo_low_expansion, london_low_expansion)
    
    if expanded_high and expanded_low:
        # Both directions expanded initially = EXPANDING
        # BUT if a subsequent session breaks >6 pts beyond previous session's extreme → directional
        
        # Check if London broke out significantly from Tokyo (or Sydney if no Tokyo expansion)
        if london:
            # London's expansion beyond the prior high/low
            if london_high_expansion > 6:
                # London went >6 pts above prior high → ASCENDING
                return ChannelType.ASCENDING, f"London broke out +{london_high_expansion:.1f} pts above prior high", true_high, true_low, high_time, low_time
            elif london_low_expansion > 6:
                # London went >6 pts below prior low → DESCENDING
                return ChannelType.DESCENDING, f"London broke down +{london_low_expansion:.1f} pts below prior low", true_high, true_low, high_time, low_time
        
        # Check if Tokyo broke out significantly from Sydney
        if tokyo_high_expansion > 6:
            # Tokyo went >6 pts above Sydney high → ASCENDING
            return ChannelType.ASCENDING, f"Tokyo broke out +{tokyo_high_expansion:.1f} pts above Sydney high", true_high, true_low, high_time, low_time
        elif tokyo_low_expansion > 6:
            # Tokyo went >6 pts below Sydney low → DESCENDING
            return ChannelType.DESCENDING, f"Tokyo broke down +{tokyo_low_expansion:.1f} pts below Sydney low", true_high, true_low, high_time, low_time
        
        # True expanding - no session broke >6 pts beyond previous
        return ChannelType.EXPANDING, f"Range expanded both ways (no >6pt breakout)", true_high, true_low, high_time, low_time
    elif not expanded_high and not expanded_low:
        return ChannelType.CONTRACTING, "Range contracted", true_high, true_low, high_time, low_time
    elif expanded_high:
        return ChannelType.ASCENDING, f"{high_session} made higher high (+{max_high_expansion:.1f} pts)", true_high, true_low, high_time, low_time
    else:
        return ChannelType.DESCENDING, f"{low_session} made lower low (+{max_low_expansion:.1f} pts)", true_high, true_low, high_time, low_time

def calc_channel_levels(upper_pivot, lower_pivot, upper_time, lower_time, ref_time, channel_type):
    if upper_pivot is None or lower_pivot is None:
        return None, None
    blocks_high = blocks_between(upper_time, ref_time) if upper_time and ref_time else 0
    blocks_low = blocks_between(lower_time, ref_time) if lower_time and ref_time else 0
    
    if channel_type == ChannelType.ASCENDING:
        ceiling = round(upper_pivot + SLOPE * blocks_high, 2)
        floor = round(lower_pivot + SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.DESCENDING:
        ceiling = round(upper_pivot - SLOPE * blocks_high, 2)
        floor = round(lower_pivot - SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.EXPANDING:
        ceiling = round(upper_pivot + SLOPE * blocks_high, 2)
        floor = round(lower_pivot - SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.CONTRACTING:
        ceiling = round(upper_pivot - SLOPE * blocks_high, 2)
        floor = round(lower_pivot + SLOPE * blocks_low, 2)
    else:
        ceiling, floor = upper_pivot, lower_pivot
    return ceiling, floor

def get_position(price, ceiling, floor):
    if price > ceiling:
        return Position.ABOVE
    elif price < floor:
        return Position.BELOW
    return Position.INSIDE

# ═══════════════════════════════════════════════════════════════════════════════
# DECISION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
def analyze_market_state(current_spx, ceiling_spx, floor_spx, channel_type, retail_bias, ema_bias, vix_position, vix):
    if current_spx is None or ceiling_spx is None or floor_spx is None:
        return {"no_trade": True, "no_trade_reason": "Missing price data", "calls_factors": [], "puts_factors": [], "primary": None, "alternate": None}
    
    result = {"no_trade": False, "no_trade_reason": None, "calls_factors": [], "puts_factors": [], "primary": None, "alternate": None}
    
    if current_spx > ceiling_spx:
        position = Position.ABOVE
    elif current_spx < floor_spx:
        position = Position.BELOW
    else:
        position = Position.INSIDE
    
    def make_scenario(name, direction, entry, stop, trigger, rationale, confidence):
        if direction == "CALLS":
            strike = int(math.ceil((entry + 20) / 5) * 5)
            opt_type = "CALL"
        else:
            strike = int(math.floor((entry - 20) / 5) * 5)
            opt_type = "PUT"
        entry_premium = estimate_0dte_premium(entry, strike, 6.0, vix, opt_type)
        target_50, target_75, target_100 = round(entry_premium * 1.50, 2), round(entry_premium * 1.75, 2), round(entry_premium * 2.00, 2)
        return {
            "name": name, "direction": direction, "entry": entry, "stop": stop, "trigger": trigger, "rationale": rationale, "confidence": confidence,
            "strike": strike, "contract": f"SPX {strike}{'C' if direction == 'CALLS' else 'P'} 0DTE", "entry_premium": entry_premium,
            "target_50": target_50, "target_75": target_75, "target_100": target_100,
            "profit_50": round((target_50 - entry_premium) * 100, 0), "profit_75": round((target_75 - entry_premium) * 100, 0), "profit_100": round((target_100 - entry_premium) * 100, 0)
        }
    
    if channel_type == ChannelType.ASCENDING:
        result["calls_factors"].append("ASCENDING channel")
    elif channel_type == ChannelType.DESCENDING:
        result["puts_factors"].append("DESCENDING channel")
    
    if ema_bias == Bias.CALLS:
        result["calls_factors"].append("Above 200 EMA + 8>21")
    elif ema_bias == Bias.PUTS:
        result["puts_factors"].append("Below 200 EMA + 8<21")
    
    if retail_bias == Bias.PUTS:
        result["puts_factors"].append("Calls crowded")
    elif retail_bias == Bias.CALLS:
        result["calls_factors"].append("Puts crowded")
    
    if vix_position == VIXPosition.BELOW_RANGE:
        result["calls_factors"].append("VIX below range")
    elif vix_position == VIXPosition.ABOVE_RANGE:
        result["puts_factors"].append("VIX above range")
    
    if channel_type == ChannelType.CONTRACTING:
        result["no_trade"] = True
        result["no_trade_reason"] = "CONTRACTING channel - No directional bias"
        return result
    if channel_type == ChannelType.UNDETERMINED:
        result["no_trade"] = True
        result["no_trade_reason"] = "Cannot determine channel structure"
        return result
    
    calls_score, puts_score = len(result["calls_factors"]), len(result["puts_factors"])
    def get_confidence(score):
        return "HIGH" if score >= 3 else "MEDIUM" if score >= 2 else "LOW"
    
    if channel_type == ChannelType.ASCENDING:
        if position in [Position.INSIDE, Position.BELOW]:
            result["primary"] = make_scenario("Floor Bounce", "CALLS", floor_spx, floor_spx - 5, "Price touches floor",
                f"Confluence: {', '.join(result['calls_factors'])}" if result['calls_factors'] else "ASCENDING structure", get_confidence(calls_score))
            result["alternate"] = make_scenario("Floor Break", "PUTS", floor_spx, floor_spx + 5, "If floor breaks down", "Failed support becomes resistance", "LOW")
        else:
            result["primary"] = make_scenario("Ceiling Pullback", "CALLS", ceiling_spx, ceiling_spx - 5, "Price pulls back to ceiling",
                f"Confluence: {', '.join(result['calls_factors'])}" if result['calls_factors'] else "Breakout continuation", get_confidence(calls_score))
            result["alternate"] = make_scenario("Ceiling Rejection", "PUTS", ceiling_spx, ceiling_spx + 5, "If ceiling acts as resistance", "Failed breakout", "LOW")
    elif channel_type == ChannelType.DESCENDING:
        if position in [Position.INSIDE, Position.ABOVE]:
            result["primary"] = make_scenario("Ceiling Rejection", "PUTS", ceiling_spx, ceiling_spx + 5, "Price touches ceiling",
                f"Confluence: {', '.join(result['puts_factors'])}" if result['puts_factors'] else "DESCENDING structure", get_confidence(puts_score))
            result["alternate"] = make_scenario("Ceiling Break", "CALLS", ceiling_spx, ceiling_spx - 5, "If ceiling breaks up", "Failed resistance becomes support", "LOW")
        else:
            result["primary"] = make_scenario("Floor Pullback", "PUTS", floor_spx, floor_spx + 5, "Price pulls back to floor",
                f"Confluence: {', '.join(result['puts_factors'])}" if result['puts_factors'] else "Breakdown continuation", get_confidence(puts_score))
            result["alternate"] = make_scenario("Floor Bounce", "CALLS", floor_spx, floor_spx - 5, "If floor acts as support", "Failed breakdown", "LOW")
    elif channel_type == ChannelType.EXPANDING:
        result["primary"] = make_scenario("Fade Ceiling", "PUTS", ceiling_spx, ceiling_spx + 5, "Price reaches ceiling", "EXPANDING: Fade extremes", "MEDIUM")
        result["alternate"] = make_scenario("Fade Floor", "CALLS", floor_spx, floor_spx - 5, "Price reaches floor", "EXPANDING: Fade extremes", "MEDIUM")
    
    return result
# ═══════════════════════════════════════════════════════════════════════════════
# LEGENDARY CSS STYLING
# ═══════════════════════════════════════════════════════════════════════════════
CSS_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&family=Syne:wght@400;500;600;700;800&display=swap');

:root {
    --bg-primary: #06080d;
    --bg-secondary: #0a0e17;
    --bg-tertiary: #0f1520;
    --bg-glass: rgba(255, 255, 255, 0.03);
    --accent-primary: #00f5d4;
    --accent-secondary: #7b61ff;
    --accent-gold: #ffd700;
    --calls-primary: #00f5a0;
    --calls-secondary: rgba(0, 245, 160, 0.15);
    --puts-primary: #ff4757;
    --puts-secondary: rgba(255, 71, 87, 0.15);
    --neutral-primary: #4dabf7;
    --text-primary: #ffffff;
    --text-secondary: rgba(255, 255, 255, 0.7);
    --text-tertiary: rgba(255, 255, 255, 0.4);
    --text-muted: rgba(255, 255, 255, 0.25);
    --border-subtle: rgba(255, 255, 255, 0.06);
    --border-accent: rgba(0, 245, 212, 0.3);
    --gradient-primary: linear-gradient(135deg, #00f5d4 0%, #7b61ff 100%);
}

.stApp {
    background: var(--bg-primary);
    background-image: 
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0, 245, 212, 0.08) 0%, transparent 50%),
        radial-gradient(ellipse 60% 40% at 80% 50%, rgba(123, 97, 255, 0.05) 0%, transparent 50%);
    font-family: 'Outfit', sans-serif;
}

#MainMenu, footer, .stDeployButton {display: none !important; visibility: hidden !important;}

::-webkit-scrollbar {width: 6px; height: 6px;}
::-webkit-scrollbar-track {background: var(--bg-secondary);}
::-webkit-scrollbar-thumb {background: var(--border-subtle); border-radius: 3px;}

/* Hero Banner */
.hero-banner {
    position: relative;
    padding: 30px 25px;
    margin: -1rem -1rem 20px -1rem;
    background: linear-gradient(180deg, #0a0e17 0%, #06080d 100%);
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 30px;
    overflow: hidden;
}

.hero-banner::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 30% 50%, rgba(0, 245, 212, 0.1) 0%, transparent 40%),
                radial-gradient(circle at 70% 50%, rgba(123, 97, 255, 0.08) 0%, transparent 40%);
    animation: heroGlow 8s ease-in-out infinite;
}

@keyframes heroGlow {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
}

/* Animated Logo */
.prophet-logo {
    position: relative;
    width: 85px;
    height: 85px;
    flex-shrink: 0;
    z-index: 2;
}

.logo-pyramid {
    position: absolute;
    width: 100%;
    height: 100%;
    animation: pyramidFloat 6s ease-in-out infinite;
}

@keyframes pyramidFloat {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-5px); }
}

.pyramid-body {
    position: absolute;
    top: 6px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 40px solid transparent;
    border-right: 40px solid transparent;
    border-bottom: 70px solid rgba(0, 245, 212, 0.15);
    animation: pyramidPulse 3s ease-in-out infinite;
}

@keyframes pyramidPulse {
    0%, 100% { border-bottom-color: rgba(0, 245, 212, 0.15); filter: drop-shadow(0 0 15px rgba(0,245,212,0.2)); }
    50% { border-bottom-color: rgba(0, 245, 212, 0.25); filter: drop-shadow(0 0 30px rgba(0,245,212,0.4)); }
}

.pyramid-inner {
    position: absolute;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 26px solid transparent;
    border-right: 26px solid transparent;
    border-bottom: 45px solid rgba(123, 97, 255, 0.2);
}

.eye-container {
    position: absolute;
    top: 30px;
    left: 50%;
    transform: translateX(-50%);
    width: 30px;
    height: 18px;
}

.eye-outer {
    position: absolute;
    width: 30px;
    height: 16px;
    border: 2px solid var(--accent-primary);
    border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
    animation: eyeBlink 4s ease-in-out infinite;
    box-shadow: 0 0 10px rgba(0, 245, 212, 0.5), inset 0 0 10px rgba(0, 245, 212, 0.2);
}

@keyframes eyeBlink {
    0%, 45%, 55%, 100% { transform: scaleY(1); }
    50% { transform: scaleY(0.1); }
}

.eye-iris {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 11px;
    height: 11px;
    background: radial-gradient(circle, var(--accent-primary) 0%, var(--accent-secondary) 60%, transparent 70%);
    border-radius: 50%;
    animation: irisGlow 2s ease-in-out infinite, irisLook 8s ease-in-out infinite;
}

@keyframes irisGlow {
    0%, 100% { box-shadow: 0 0 10px var(--accent-primary), 0 0 20px var(--accent-primary); }
    50% { box-shadow: 0 0 20px var(--accent-primary), 0 0 40px var(--accent-primary); }
}

@keyframes irisLook {
    0%, 100% { transform: translate(-50%, -50%); }
    25% { transform: translate(-40%, -50%); }
    75% { transform: translate(-60%, -50%); }
}

.eye-pupil {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 4px;
    height: 4px;
    background: #fff;
    border-radius: 50%;
    box-shadow: 0 0 8px #fff;
}

.eye-rays {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 50px;
    height: 50px;
    animation: raysRotate 20s linear infinite;
}

@keyframes raysRotate {
    from { transform: translate(-50%, -50%) rotate(0deg); }
    to { transform: translate(-50%, -50%) rotate(360deg); }
}

.eye-rays::before, .eye-rays::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 2px;
    height: 50px;
    background: linear-gradient(180deg, transparent 0%, rgba(0,245,212,0.3) 30%, transparent 100%);
}

.eye-rays::before { transform: translate(-50%, -50%) rotate(0deg); }
.eye-rays::after { transform: translate(-50%, -50%) rotate(90deg); }

.hero-content {
    position: relative;
    z-index: 2;
    text-align: left;
}

.brand-name {
    font-family: 'Syne', sans-serif;
    font-size: 2.5rem;
    font-weight: 800;
    letter-spacing: -1px;
    background: var(--gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    line-height: 1;
}

.brand-tagline {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    color: var(--text-secondary);
    letter-spacing: 3px;
    margin-top: 6px;
    text-transform: uppercase;
}

/* Glass Cards */
.glass-card {
    background: var(--bg-glass);
    backdrop-filter: blur(20px);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 18px;
    transition: all 0.3s ease;
}

.glass-card:hover {
    border-color: var(--border-accent);
    transform: translateY(-2px);
}

.glass-card-calls {
    background: linear-gradient(135deg, rgba(0,245,160,0.08) 0%, rgba(0,245,160,0.02) 100%);
    border: 1px solid rgba(0, 245, 160, 0.25);
    border-left: 4px solid var(--calls-primary);
}

.glass-card-puts {
    background: linear-gradient(135deg, rgba(255,71,87,0.08) 0%, rgba(255,71,87,0.02) 100%);
    border: 1px solid rgba(255, 71, 87, 0.25);
    border-left: 4px solid var(--puts-primary);
}

/* Section Headers */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 25px 0 15px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-subtle);
    position: relative;
}

.section-header::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    width: 45px;
    height: 2px;
    background: var(--gradient-primary);
}

.section-icon {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: 7px;
    font-size: 1rem;
}

.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
}

/* Metric Cards */
.metric-card {
    background: var(--bg-glass);
    backdrop-filter: blur(10px);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    transition: all 0.3s ease;
}

.metric-card:hover {
    transform: translateY(-2px);
    border-color: var(--border-accent);
}

.metric-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 5px;
}

.metric-value {
    font-family: 'Outfit', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1;
}

.metric-value.accent { color: var(--accent-primary); }
.metric-value.calls { color: var(--calls-primary); }
.metric-value.puts { color: var(--puts-primary); }
.metric-value.gold { color: var(--accent-gold); }

.metric-delta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 4px;
}

/* Bias Pills */
.bias-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 50px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.bias-pill-calls { background: var(--calls-secondary); border: 1px solid var(--calls-primary); color: var(--calls-primary); }
.bias-pill-puts { background: var(--puts-secondary); border: 1px solid var(--puts-primary); color: var(--puts-primary); }
.bias-pill-neutral { background: rgba(77,171,247,0.15); border: 1px solid var(--neutral-primary); color: var(--neutral-primary); }

/* Channel Badges */
.channel-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 18px;
    border-radius: 8px;
    font-family: 'Syne', sans-serif;
    font-size: 0.9rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    position: relative;
    overflow: hidden;
}

.channel-badge::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    animation: badgeShine 3s ease-in-out infinite;
}

@keyframes badgeShine {
    0% { left: -100%; }
    100% { left: 100%; }
}

.channel-badge-ascending { background: linear-gradient(135deg, rgba(0,245,160,0.2) 0%, rgba(0,245,160,0.05) 100%); border: 1px solid var(--calls-primary); color: var(--calls-primary); }
.channel-badge-descending { background: linear-gradient(135deg, rgba(255,71,87,0.2) 0%, rgba(255,71,87,0.05) 100%); border: 1px solid var(--puts-primary); color: var(--puts-primary); }
.channel-badge-expanding { background: linear-gradient(135deg, rgba(123,97,255,0.2) 0%, rgba(123,97,255,0.05) 100%); border: 1px solid var(--accent-secondary); color: var(--accent-secondary); }
.channel-badge-contracting { background: linear-gradient(135deg, rgba(255,215,0,0.2) 0%, rgba(255,215,0,0.05) 100%); border: 1px solid var(--accent-gold); color: var(--accent-gold); }

/* Levels Display */
.levels-container { background: var(--bg-tertiary); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 18px; }
.level-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px dashed var(--border-subtle); }
.level-row:last-child { border-bottom: none; }
.level-label { display: flex; align-items: center; gap: 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; }
.level-label.ceiling { color: var(--puts-primary); }
.level-label.current { color: var(--accent-gold); }
.level-label.floor { color: var(--calls-primary); }
.level-value { font-family: 'Outfit', sans-serif; font-size: 1.2rem; font-weight: 700; }
.level-value.ceiling { color: var(--puts-primary); }
.level-value.current { color: var(--accent-gold); }
.level-value.floor { color: var(--calls-primary); }
.level-note { font-family: 'Outfit', sans-serif; font-size: 0.8rem; color: var(--text-tertiary); }

/* Prior Day Target */
.prior-day-target {
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 18px;
    margin-top: 16px;
    position: relative;
    overflow: hidden;
}
.prior-day-target::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
}
.prior-day-target-calls::before { background: linear-gradient(90deg, var(--calls-primary), transparent); }
.prior-day-target-puts::before { background: linear-gradient(90deg, var(--puts-primary), transparent); }
.prior-target-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
}
.prior-target-icon { font-size: 1.2rem; }
.prior-target-title {
    font-family: 'Syne', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-primary);
}
.prior-target-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    padding: 4px 10px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.prior-target-badge.calls { background: var(--calls-secondary); color: var(--calls-primary); }
.prior-target-badge.puts { background: var(--puts-secondary); color: var(--puts-primary); }
.prior-target-value {
    font-family: 'Outfit', sans-serif;
    font-size: 2rem;
    font-weight: 800;
    color: var(--accent-primary);
    margin-bottom: 8px;
}
.prior-target-details {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}
.prior-target-sep { color: var(--text-muted); }
.prior-target-note {
    font-family: 'Outfit', sans-serif;
    font-size: 0.8rem;
    color: var(--text-tertiary);
    font-style: italic;
    padding-top: 10px;
    border-top: 1px dashed var(--border-subtle);
}

/* Prior Day Info (when inside cone) */
.prior-day-info {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    margin-top: 12px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: var(--text-secondary);
}
.prior-day-label {
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 0.75rem;
}
.prior-day-sep { color: var(--text-muted); }

/* Confluence Cards */
.confluence-card { background: var(--bg-glass); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 16px; }
.confluence-card-calls { border-top: 3px solid var(--calls-primary); }
.confluence-card-puts { border-top: 3px solid var(--puts-primary); }
.confluence-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.confluence-title { font-family: 'Syne', sans-serif; font-size: 0.875rem; font-weight: 600; color: var(--text-primary); }
.confluence-score { font-family: 'Outfit', sans-serif; font-size: 1.6rem; font-weight: 800; padding: 5px 12px; border-radius: 6px; }
.confluence-score.high { background: var(--calls-secondary); color: var(--calls-primary); }
.confluence-score.medium { background: rgba(255,215,0,0.15); color: var(--accent-gold); }
.confluence-score.low { background: var(--puts-secondary); color: var(--puts-primary); }
.confluence-factor { display: flex; align-items: center; gap: 8px; padding: 7px 0; font-family: 'Outfit', sans-serif; font-size: 0.875rem; color: var(--text-secondary); border-bottom: 1px solid var(--border-subtle); }
.confluence-factor:last-child { border-bottom: none; }
.factor-check { width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; border-radius: 50%; font-size: 0.75rem; }
.factor-check.active { background: var(--calls-secondary); color: var(--calls-primary); }
.factor-check.inactive { background: rgba(255,255,255,0.05); color: var(--text-muted); }

/* Trade Cards */
.trade-card { background: var(--bg-glass); backdrop-filter: blur(20px); border: 1px solid var(--border-subtle); border-radius: 16px; padding: 22px; position: relative; overflow: hidden; }
.trade-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; border-radius: 16px 16px 0 0; }
.trade-card-calls::before { background: linear-gradient(90deg, var(--calls-primary) 0%, rgba(0,245,160,0.3) 100%); }
.trade-card-puts::before { background: linear-gradient(90deg, var(--puts-primary) 0%, rgba(255,71,87,0.3) 100%); }
.trade-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.trade-name { font-family: 'Syne', sans-serif; font-size: 1.1rem; font-weight: 700; color: var(--text-primary); }
.trade-confidence { padding: 4px 10px; border-radius: 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
.trade-confidence-high { background: var(--calls-secondary); color: var(--calls-primary); border: 1px solid var(--calls-primary); }
.trade-confidence-medium { background: rgba(255,215,0,0.15); color: var(--accent-gold); border: 1px solid var(--accent-gold); }
.trade-confidence-low { background: rgba(255,255,255,0.05); color: var(--text-secondary); border: 1px solid var(--border-subtle); }
.trade-contract { font-family: 'JetBrains Mono', monospace; font-size: 1.2rem; font-weight: 600; padding: 12px 18px; border-radius: 8px; text-align: center; margin-bottom: 16px; }
.trade-contract-calls { background: var(--calls-secondary); color: var(--calls-primary); border: 1px solid rgba(0,245,160,0.3); }
.trade-contract-puts { background: var(--puts-secondary); color: var(--puts-primary); border: 1px solid rgba(255,71,87,0.3); }
.trade-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.trade-metric { background: var(--bg-tertiary); border-radius: 8px; padding: 12px; text-align: center; }
.trade-metric-label { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.trade-metric-value { font-family: 'Outfit', sans-serif; font-size: 1rem; font-weight: 700; color: var(--text-primary); }
.trade-targets { background: var(--bg-tertiary); border-radius: 8px; padding: 12px; }
.targets-header { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px; }
.targets-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.target-item { text-align: center; padding: 8px; border-radius: 6px; background: var(--bg-glass); border: 1px solid var(--border-subtle); }
.target-label { font-size: 0.75rem; color: var(--text-tertiary); margin-bottom: 2px; }
.target-price { font-size: 1rem; font-weight: 700; color: var(--text-primary); }
.target-profit { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: var(--calls-primary); margin-top: 2px; }
.trade-trigger { margin-top: 12px; padding: 10px 14px; background: rgba(255,255,255,0.03); border-radius: 6px; border-left: 3px solid var(--accent-primary); }
.trigger-label { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--accent-primary); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px; }
.trigger-text { font-family: 'Outfit', sans-serif; font-size: 0.875rem; color: var(--text-secondary); }

/* Session Cards */
.session-card { background: var(--bg-glass); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 14px; text-align: center; transition: all 0.3s ease; }
.session-card:hover { transform: translateY(-2px); border-color: var(--border-accent); }
.session-icon { font-size: 1.4rem; margin-bottom: 6px; }
.session-name { font-family: 'Syne', sans-serif; font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.session-data { display: flex; flex-direction: column; gap: 5px; }
.session-value { display: flex; align-items: center; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.session-high { color: var(--puts-primary); }
.session-low { color: var(--calls-primary); }

/* Indicator Cards */
.indicator-card { background: var(--bg-glass); border: 1px solid var(--border-subtle); border-radius: 12px; padding: 16px; }
.indicator-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border-subtle); }
.indicator-icon { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; background: var(--bg-tertiary); border-radius: 5px; font-size: 0.9rem; }
.indicator-title { font-family: 'Syne', sans-serif; font-size: 0.9rem; font-weight: 600; color: var(--text-primary); }
.indicator-row { display: flex; justify-content: space-between; padding: 5px 0; font-family: 'Outfit', sans-serif; font-size: 0.85rem; }
.indicator-label { color: var(--text-tertiary); }
.indicator-value { color: var(--text-primary); font-weight: 500; }
.indicator-status { display: inline-flex; align-items: center; gap: 4px; padding: 5px 10px; border-radius: 5px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 600; margin-top: 8px; }
.indicator-status-bullish { background: var(--calls-secondary); color: var(--calls-primary); }
.indicator-status-bearish { background: var(--puts-secondary); color: var(--puts-primary); }

/* Alert Boxes */
.alert-box { display: flex; align-items: flex-start; gap: 10px; padding: 14px 18px; border-radius: 10px; margin: 12px 0; }
.alert-box-warning { background: linear-gradient(135deg, rgba(255,215,0,0.1) 0%, rgba(255,215,0,0.03) 100%); border: 1px solid rgba(255,215,0,0.3); }
.alert-box-danger { background: linear-gradient(135deg, rgba(255,71,87,0.1) 0%, rgba(255,71,87,0.03) 100%); border: 1px solid rgba(255,71,87,0.3); }
.alert-box-success { background: linear-gradient(135deg, rgba(0,245,160,0.1) 0%, rgba(0,245,160,0.03) 100%); border: 1px solid rgba(0,245,160,0.3); }
.alert-box-info { background: linear-gradient(135deg, rgba(77,171,247,0.1) 0%, rgba(77,171,247,0.03) 100%); border: 1px solid rgba(77,171,247,0.3); }
.alert-icon { font-size: 1.1rem; flex-shrink: 0; }
.alert-content { flex: 1; }
.alert-title { font-family: 'Syne', sans-serif; font-size: 0.9rem; font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }
.alert-text { font-family: 'Outfit', sans-serif; font-size: 0.85rem; color: var(--text-secondary); }

/* No Trade Card */
.no-trade-card { background: linear-gradient(135deg, rgba(255,71,87,0.1) 0%, rgba(255,71,87,0.02) 100%); border: 1px solid rgba(255,71,87,0.3); border-radius: 16px; padding: 30px; text-align: center; }
.no-trade-icon { font-size: 2.2rem; margin-bottom: 12px; opacity: 0.8; }
.no-trade-title { font-family: 'Syne', sans-serif; font-size: 1.2rem; font-weight: 700; color: var(--puts-primary); margin-bottom: 5px; }
.no-trade-reason { font-family: 'Outfit', sans-serif; font-size: 0.9rem; color: var(--text-secondary); }

/* Live Indicator */
.live-indicator { display: inline-flex; align-items: center; gap: 4px; }
.live-dot { width: 6px; height: 6px; background: var(--calls-primary); border-radius: 50%; animation: livePulse 1.5s ease-in-out infinite; box-shadow: 0 0 6px var(--calls-primary); }
@keyframes livePulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

/* Quick Action Bar */
.quick-action-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px 16px;
    margin-bottom: 12px;
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
}
.action-hint {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: var(--text-tertiary);
    letter-spacing: 0.5px;
}

/* Streamlit Overrides */
[data-testid="stMetricValue"] { font-family: 'Outfit', sans-serif !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { font-family: 'JetBrains Mono', monospace !important; text-transform: uppercase !important; letter-spacing: 1px !important; }

/* Sidebar Styling */
section[data-testid="stSidebar"] { background-color: #0a0e17 !important; }
section[data-testid="stSidebar"] > div { background-color: #0a0e17 !important; }
section[data-testid="stSidebar"] h3 { color: #ffffff !important; font-family: 'Syne', sans-serif !important; }
section[data-testid="stSidebar"] h4 { color: #00f5d4 !important; font-family: 'Syne', sans-serif !important; font-size: 0.95rem !important; }
section[data-testid="stSidebar"] h5 { color: rgba(255,255,255,0.7) !important; font-family: 'Outfit', sans-serif !important; font-size: 0.85rem !important; }
section[data-testid="stSidebar"] label { color: rgba(255,255,255,0.7) !important; font-family: 'Outfit', sans-serif !important; }
section[data-testid="stSidebar"] input { background-color: #0f1520 !important; color: #ffffff !important; border: 1px solid rgba(255,255,255,0.1) !important; }
section[data-testid="stSidebar"] .stSelectbox > div > div { background-color: #0f1520 !important; color: #ffffff !important; }
section[data-testid="stSidebar"] p { color: rgba(255,255,255,0.6) !important; }

.stButton > button { font-family: 'JetBrains Mono', monospace !important; font-weight: 600 !important; border-radius: 6px !important; }
hr { border: none !important; height: 1px !important; background: var(--border-subtle) !important; margin: 18px 0 !important; }

@media (max-width: 768px) {
    .hero-banner { flex-direction: column; padding: 20px 12px; gap: 12px; }
    .hero-content { text-align: center; }
    .brand-name { font-size: 1.8rem; }
}
</style>
"""
# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def sidebar():
    saved = load_inputs()
    
    with st.sidebar:
        st.markdown("### ⚙️ SPX Prophet Settings")
        
        # ─────────────────────────────────────────────────────────────────────
        # BASIC SETTINGS
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("#### 📅 Trading Session")
        trading_date = st.date_input("Trading Date", value=date.today())
        
        col1, col2 = st.columns(2)
        ref_hour = col1.selectbox("Ref Hour", options=list(range(8, 12)), index=1, format_func=lambda x: f"{x}:00")
        ref_min = col2.selectbox("Ref Min", options=[0, 15, 30, 45], index=0, format_func=lambda x: f":{x:02d}")
        
        st.divider()
        
        # ─────────────────────────────────────────────────────────────────────
        # ES/SPX OFFSET
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("#### 📊 ES → SPX Conversion")
        offset = st.number_input(
            "Offset (ES - SPX)", 
            value=float(saved.get("offset", 35.5)), 
            step=0.5,
            help="Difference between ES futures and SPX cash index"
        )
        
        st.divider()
        
        # ─────────────────────────────────────────────────────────────────────
        # VIX SETTINGS
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("#### 📉 VIX Configuration")
        
        use_manual_vix = st.checkbox("Manual VIX Override", value=False)
        if use_manual_vix:
            manual_vix = st.number_input("Current VIX", value=16.0, step=0.1, format="%.2f")
        else:
            manual_vix = None
        
        st.markdown("##### Overnight Zone (CT)")
        col1, col2 = st.columns(2)
        vix_zone_start = col1.time_input("Zone Start", value=time(2, 0))
        vix_zone_end = col2.time_input("Zone End", value=time(6, 0))
        
        use_manual_vix_range = st.checkbox("Manual VIX Range Override", value=False)
        if use_manual_vix_range:
            col1, col2 = st.columns(2)
            manual_vix_low = col1.number_input("VIX Low", value=15.0, step=0.1, format="%.2f")
            manual_vix_high = col2.number_input("VIX High", value=17.0, step=0.1, format="%.2f")
        else:
            manual_vix_low = None
            manual_vix_high = None
        
        st.divider()
        
        # ─────────────────────────────────────────────────────────────────────
        # PRIOR DAY RTH DATA
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("#### 📈 Prior Day RTH (ES)")
        use_manual_prior = st.checkbox("Manual Prior Day Override", value=False)
        if use_manual_prior:
            col1, col2 = st.columns(2)
            prior_highest_wick = col1.number_input("Highest Wick", value=6100.0, step=0.5, help="Highest high of any RTH candle")
            prior_lowest_close = col2.number_input("Lowest Close", value=6050.0, step=0.5, help="Lowest close of any RTH candle")
            prior_close = st.number_input("RTH Close", value=6075.0, step=0.5, help="Final RTH close")
        else:
            prior_highest_wick = None
            prior_lowest_close = None
            prior_close = None
        
        st.divider()
        
        # ─────────────────────────────────────────────────────────────────────
        # OVERNIGHT SESSION DATA
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("#### 🌙 Overnight Session (ES)")
        use_manual_overnight = st.checkbox("Manual ON Session Override", value=False)
        if use_manual_overnight:
            col1, col2 = st.columns(2)
            on_high = col1.number_input("ON High", value=6090.0, step=0.5)
            on_low = col2.number_input("ON Low", value=6055.0, step=0.5)
        else:
            on_high = None
            on_low = None
        
        st.divider()
        
        # ─────────────────────────────────────────────────────────────────────
        # GLOBAL SESSION OVERRIDES
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("#### 🌏 Session Breakdown (ES)")
        use_manual_sessions = st.checkbox("Manual Session Override", value=False)
        
        if use_manual_sessions:
            st.markdown("##### Sydney (5-8:30 PM CT)")
            col1, col2 = st.columns(2)
            sydney_high = col1.number_input("Syd High", value=6075.0, step=0.5, key="syd_h")
            sydney_low = col2.number_input("Syd Low", value=6060.0, step=0.5, key="syd_l")
            
            st.markdown("##### Tokyo (9 PM - 1:30 AM CT)")
            col1, col2 = st.columns(2)
            tokyo_high = col1.number_input("Tok High", value=6080.0, step=0.5, key="tok_h")
            tokyo_low = col2.number_input("Tok Low", value=6055.0, step=0.5, key="tok_l")
            
            st.markdown("##### London (2-5 AM CT)")
            col1, col2 = st.columns(2)
            london_high = col1.number_input("Lon High", value=6085.0, step=0.5, key="lon_h")
            london_low = col2.number_input("Lon Low", value=6050.0, step=0.5, key="lon_l")
        else:
            sydney_high = sydney_low = tokyo_high = tokyo_low = london_high = london_low = None
        
        st.divider()
        
        # ─────────────────────────────────────────────────────────────────────
        # CURRENT PRICE OVERRIDE
        # ─────────────────────────────────────────────────────────────────────
        st.markdown("#### 💹 Current Price")
        use_manual_price = st.checkbox("Manual ES Price Override", value=False)
        if use_manual_price:
            manual_es = st.number_input("Current ES", value=6070.0, step=0.5)
        else:
            manual_es = None
        
        st.divider()
        
        # ─────────────────────────────────────────────────────────────────────
        # SESSION TIMES (for extraction)
        # ─────────────────────────────────────────────────────────────────────
        with st.expander("⏰ Session Time Config", expanded=False):
            st.markdown("**Sydney Session (CT)**")
            col1, col2 = st.columns(2)
            sydney_start = col1.time_input("Start", value=time(17, 0), key="syd_start")
            sydney_end = col2.time_input("End", value=time(20, 30), key="syd_end")
            
            st.markdown("**Tokyo Session (CT)**")
            col1, col2 = st.columns(2)
            tokyo_start = col1.time_input("Start", value=time(21, 0), key="tok_start")
            tokyo_end = col2.time_input("End", value=time(1, 30), key="tok_end")
            
            st.markdown("**London Session (CT)**")
            col1, col2 = st.columns(2)
            london_start = col1.time_input("Start", value=time(2, 0), key="lon_start")
            london_end = col2.time_input("End", value=time(5, 0), key="lon_end")
        
        st.divider()
        
        # ─────────────────────────────────────────────────────────────────────
        # ACTION BUTTONS
        # ─────────────────────────────────────────────────────────────────────
        col1, col2 = st.columns(2)
        if col1.button("💾 Save", use_container_width=True):
            save_inputs({"offset": offset})
            st.success("✓ Saved!")
        if col2.button("🔄 Refresh", use_container_width=True):
            # Clear only market data caches
            fetch_es_current.clear()
            fetch_vix_polygon.clear()
            fetch_vix_yahoo.clear()
            fetch_es_with_ema.clear()
            fetch_retail_positioning.clear()
            fetch_prior_day_rth.clear()
            st.rerun()
    
    # Build return dict with all manual overrides
    return {
        "trading_date": trading_date,
        "offset": offset,
        "ref_time": (ref_hour, ref_min),
        "vix_zone_start": vix_zone_start,
        "vix_zone_end": vix_zone_end,
        # Manual overrides
        "manual_vix": manual_vix,
        "manual_vix_range": {"low": manual_vix_low, "high": manual_vix_high} if use_manual_vix_range else None,
        "manual_prior": {"highest_wick": prior_highest_wick, "lowest_close": prior_lowest_close, "close": prior_close} if use_manual_prior else None,
        "manual_overnight": {"high": on_high, "low": on_low} if use_manual_overnight else None,
        "manual_sessions": {
            "sydney": {"high": sydney_high, "low": sydney_low},
            "tokyo": {"high": tokyo_high, "low": tokyo_low},
            "london": {"high": london_high, "low": london_low}
        } if use_manual_sessions else None,
        "manual_es": manual_es,
    }
# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown(CSS_STYLES, unsafe_allow_html=True)
    inputs = sidebar()
    now = now_ct()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LOAD DATA (with manual override support)
    # ═══════════════════════════════════════════════════════════════════════════
    with st.spinner("Loading market data..."):
        
        # --- Current ES Price ---
        if inputs["manual_es"] is not None:
            current_es = inputs["manual_es"]
        else:
            current_es = fetch_es_current() or 6050
        
        # --- Session Data ---
        if inputs["manual_sessions"] is not None:
            m = inputs["manual_sessions"]
            overnight_day = get_prior_trading_day(inputs["trading_date"])
            sydney = {
                "high": m["sydney"]["high"], "low": m["sydney"]["low"],
                "high_time": CT.localize(datetime.combine(overnight_day, time(18, 0))),
                "low_time": CT.localize(datetime.combine(overnight_day, time(19, 0)))
            }
            tokyo = {
                "high": m["tokyo"]["high"], "low": m["tokyo"]["low"],
                "high_time": CT.localize(datetime.combine(overnight_day, time(23, 0))),
                "low_time": CT.localize(datetime.combine(inputs["trading_date"], time(0, 30)))
            }
            london = {
                "high": m["london"]["high"], "low": m["london"]["low"],
                "high_time": CT.localize(datetime.combine(inputs["trading_date"], time(3, 0))),
                "low_time": CT.localize(datetime.combine(inputs["trading_date"], time(4, 0)))
            }
        else:
            es_candles = fetch_es_candles()
            sessions = extract_sessions(es_candles, inputs["trading_date"]) or {}
            sydney = sessions.get("sydney")
            tokyo = sessions.get("tokyo")
            london = sessions.get("london")
        
        # --- Overnight High/Low ---
        if inputs["manual_overnight"] is not None:
            overnight = {
                "high": inputs["manual_overnight"]["high"],
                "low": inputs["manual_overnight"]["low"]
            }
        elif sydney and tokyo and london:
            overnight = {
                "high": max(sydney["high"], tokyo["high"], london["high"]),
                "low": min(sydney["low"], tokyo["low"], london["low"])
            }
        elif inputs["manual_sessions"] is not None:
            m = inputs["manual_sessions"]
            overnight = {
                "high": max(m["sydney"]["high"], m["tokyo"]["high"], m["london"]["high"]),
                "low": min(m["sydney"]["low"], m["tokyo"]["low"], m["london"]["low"])
            }
        else:
            es_candles = fetch_es_candles()
            sessions = extract_sessions(es_candles, inputs["trading_date"]) or {}
            overnight = sessions.get("overnight")
        
        # --- VIX Current ---
        if inputs["manual_vix"] is not None:
            vix = inputs["manual_vix"]
        else:
            vix_polygon = fetch_vix_polygon()
            vix = vix_polygon if vix_polygon else fetch_vix_yahoo()
        
        # --- VIX Overnight Range ---
        if inputs["manual_vix_range"] is not None:
            vix_range = {
                "bottom": inputs["manual_vix_range"]["low"],
                "top": inputs["manual_vix_range"]["high"],
                "range_size": round(inputs["manual_vix_range"]["high"] - inputs["manual_vix_range"]["low"], 2),
                "available": True
            }
        else:
            vix_range = fetch_vix_overnight_range(
                inputs["trading_date"], 
                inputs["vix_zone_start"].hour, inputs["vix_zone_start"].minute, 
                inputs["vix_zone_end"].hour, inputs["vix_zone_end"].minute
            )
        
        vix_pos, vix_pos_desc = get_vix_position(vix, vix_range)
        retail_data = fetch_retail_positioning()
        ema_data = fetch_es_with_ema()
        
        # --- Prior Day RTH Data ---
        if inputs["manual_prior"] is not None:
            prior_day = get_prior_trading_day(inputs["trading_date"])
            prior_rth = {
                "highest_wick": inputs["manual_prior"]["highest_wick"],
                "highest_wick_time": CT.localize(datetime.combine(prior_day, time(12, 0))),
                "lowest_close": inputs["manual_prior"]["lowest_close"],
                "lowest_close_time": CT.localize(datetime.combine(prior_day, time(12, 0))),
                "high": inputs["manual_prior"]["highest_wick"],
                "low": inputs["manual_prior"]["lowest_close"],
                "close": inputs["manual_prior"]["close"],
                "available": True
            }
        else:
            prior_rth = fetch_prior_day_rth(inputs["trading_date"])
    
    offset = inputs["offset"]
    current_spx = round(current_es - offset, 2)
    channel_type, channel_reason, upper_pivot, lower_pivot, upper_time, lower_time = determine_channel(sydney, tokyo, london)
    ref_time_dt = CT.localize(datetime.combine(inputs["trading_date"], time(*inputs["ref_time"])))
    ceiling_es, floor_es = calc_channel_levels(upper_pivot, lower_pivot, upper_time, lower_time, ref_time_dt, channel_type)
    
    if ceiling_es is None:
        ceiling_es, floor_es = 6080, 6040
    
    ceiling_spx = round(ceiling_es - offset, 2)
    floor_spx = round(floor_es - offset, 2)
    position = get_position(current_es, ceiling_es, floor_es)
    
    # Calculate prior day target if outside overnight cone
    prior_target_es, prior_target_direction, prior_target_reason = calc_prior_day_targets(
        prior_rth, ref_time_dt, position, ceiling_es, floor_es
    )
    prior_target_spx = round(prior_target_es - offset, 2) if prior_target_es else None
    
    decision = analyze_market_state(current_spx, ceiling_spx, floor_spx, channel_type, retail_data["bias"], ema_data["ema_bias"], vix_pos, vix)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HERO BANNER
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <div class="hero-banner">
        <div class="prophet-logo">
            <div class="logo-pyramid">
                <div class="pyramid-body"></div>
                <div class="pyramid-inner"></div>
                <div class="eye-container">
                    <div class="eye-rays"></div>
                    <div class="eye-outer"></div>
                    <div class="eye-iris"><div class="eye-pupil"></div></div>
                </div>
            </div>
        </div>
        <div class="hero-content">
            <h1 class="brand-name">SPX PROPHET</h1>
            <p class="brand-tagline">Where Structure Becomes Foresight</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # QUICK ACTION BAR
    # ═══════════════════════════════════════════════════════════════════════════
    col1, col2, col3 = st.columns([2, 1, 2])
    with col1:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:10px 0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.8rem;color:rgba(255,255,255,0.5);">
                📅 {inputs["trading_date"].strftime("%A, %B %d, %Y")}
            </span>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if st.button("🔄 Refresh", use_container_width=True, help="Refresh all market data"):
            fetch_es_current.clear()
            fetch_vix_polygon.clear()
            fetch_vix_yahoo.clear()
            fetch_es_with_ema.clear()
            fetch_retail_positioning.clear()
            fetch_prior_day_rth.clear()
            st.rerun()
    with col3:
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:10px 0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.8rem;color:rgba(255,255,255,0.5);">
                ⏰ {now.strftime("%I:%M %p CT")}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MARKET SNAPSHOT
    # ═══════════════════════════════════════════════════════════════════════════
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">SPX Index</div><div class="metric-value accent">{current_spx:,.2f}</div><div class="metric-delta">ES {current_es:,.2f}</div></div>', unsafe_allow_html=True)
    with col2:
        vix_color = "puts" if vix > 20 else "calls" if vix < 15 else ""
        st.markdown(f'<div class="metric-card"><div class="metric-label">VIX Index</div><div class="metric-value {vix_color}">{vix:.2f}</div><div class="metric-delta">Volatility</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Position</div><div class="metric-value">{position.value}</div><div class="metric-delta">In Channel</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Time</div><div class="metric-value">{now.strftime("%I:%M")}</div><div class="metric-delta live-indicator"><span class="live-dot"></span> {now.strftime("%p CT")}</div></div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TODAY'S BIAS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header"><div class="section-icon">◎</div><h2 class="section-title">Today\'s Bias</h2></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        chan_class = channel_type.value.lower()
        chan_icon = {"ASCENDING": "↗", "DESCENDING": "↘", "EXPANDING": "⟷", "CONTRACTING": "⟶"}.get(channel_type.value, "○")
        st.markdown(f'<div class="glass-card"><div class="channel-badge channel-badge-{chan_class}"><span style="font-size:1.2rem;">{chan_icon}</span><span>{channel_type.value}</span></div><p style="margin-top:10px;color:var(--text-secondary);font-size:0.875rem;">{channel_reason}</p></div>', unsafe_allow_html=True)
    with col2:
        ema_class = "calls" if ema_data["above_200"] else "puts"
        ema_icon = "↑" if ema_data["above_200"] else "↓"
        ema_text = "Above 200 EMA" if ema_data["above_200"] else "Below 200 EMA"
        st.markdown(f'<div class="glass-card"><div class="bias-pill bias-pill-{ema_class}"><span>{ema_icon}</span><span>{ema_text}</span></div><p style="margin-top:10px;color:var(--text-secondary);font-size:0.875rem;">{"Supports CALLS" if ema_data["above_200"] else "Supports PUTS"}</p></div>', unsafe_allow_html=True)
    with col3:
        cross_class = "calls" if ema_data["ema_cross"] == "BULLISH" else "puts"
        cross_icon = "✓" if ema_data["ema_cross"] == "BULLISH" else "✗"
        st.markdown(f'<div class="glass-card"><div class="bias-pill bias-pill-{cross_class}"><span>{cross_icon}</span><span>8/21 {ema_data["ema_cross"]}</span></div><p style="margin-top:10px;color:var(--text-secondary);font-size:0.875rem;">{"8 EMA > 21 EMA" if ema_data["ema_cross"] == "BULLISH" else "8 EMA < 21 EMA"}</p></div>', unsafe_allow_html=True)
    
    # Retail positioning alert
    if retail_data["positioning"] != "BALANCED":
        alert_class = "warning" if "HEAVY" in retail_data["positioning"] else "danger"
        alert_icon = "⚡" if "EXTREME" in retail_data["positioning"] else "⚠"
        st.markdown(f'<div class="alert-box alert-box-{alert_class}"><span class="alert-icon">{alert_icon}</span><div class="alert-content"><div class="alert-title">{retail_data["positioning"]}</div><div class="alert-text">{retail_data["warning"]}</div></div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-box alert-box-success"><span class="alert-icon">✓</span><div class="alert-content"><div class="alert-title">BALANCED POSITIONING</div><div class="alert-text">No crowd pressure detected - trade freely with structure</div></div></div>', unsafe_allow_html=True)
    
    # VIX Position
    if vix_range["available"]:
        vix_icon = {"ABOVE": "▲", "IN RANGE": "◆", "BELOW": "▼"}.get(vix_pos.value, "○")
        st.markdown(f'<div class="alert-box alert-box-info"><span class="alert-icon">{vix_icon}</span><div class="alert-content"><div class="alert-title">VIX {vix_pos.value}</div><div class="alert-text">Overnight range: {vix_range["bottom"]} - {vix_range["top"]} | Current: {vix}</div></div></div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONFLUENCE
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header"><div class="section-icon">⚖</div><h2 class="section-title">Confluence Analysis</h2></div>', unsafe_allow_html=True)
    
    calls_score, puts_score = len(decision["calls_factors"]), len(decision["puts_factors"])
    calls_class = "high" if calls_score >= 3 else "medium" if calls_score >= 2 else "low"
    puts_class = "high" if puts_score >= 3 else "medium" if puts_score >= 2 else "low"
    
    col1, col2 = st.columns(2)
    with col1:
        factors_html = "".join([f'<div class="confluence-factor"><span class="factor-check active">✓</span>{f}</div>' for f in decision["calls_factors"]]) or '<div class="confluence-factor"><span class="factor-check inactive">—</span>No supporting factors</div>'
        st.markdown(f'<div class="confluence-card confluence-card-calls"><div class="confluence-header"><span class="confluence-title">🟢 CALLS</span><span class="confluence-score {calls_class}">{calls_score}</span></div>{factors_html}</div>', unsafe_allow_html=True)
    with col2:
        factors_html = "".join([f'<div class="confluence-factor"><span class="factor-check active">✓</span>{f}</div>' for f in decision["puts_factors"]]) or '<div class="confluence-factor"><span class="factor-check inactive">—</span>No supporting factors</div>'
        st.markdown(f'<div class="confluence-card confluence-card-puts"><div class="confluence-header"><span class="confluence-title">🔴 PUTS</span><span class="confluence-score {puts_class}">{puts_score}</span></div>{factors_html}</div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRADING LEVELS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(f'<div class="section-header"><div class="section-icon">◫</div><h2 class="section-title">Trading Levels @ {inputs["ref_time"][0]}:{inputs["ref_time"][1]:02d} AM</h2></div>', unsafe_allow_html=True)
    
    dist_ceil, dist_floor = round(ceiling_spx - current_spx, 1), round(current_spx - floor_spx, 1)
    st.markdown(f'''
    <div class="levels-container">
        <div class="level-row"><div class="level-label ceiling"><span>▲</span><span>CEILING</span></div><div class="level-value ceiling">{ceiling_spx:,.2f}</div><div class="level-note">PUTS entry • {dist_ceil} pts away</div></div>
        <div class="level-row" style="background:rgba(255,215,0,0.05);margin:0 -18px;padding:12px 18px;"><div class="level-label current"><span>●</span><span>CURRENT</span></div><div class="level-value current">{current_spx:,.2f}</div><div class="level-note">Position: {position.value}</div></div>
        <div class="level-row"><div class="level-label floor"><span>▼</span><span>FLOOR</span></div><div class="level-value floor">{floor_spx:,.2f}</div><div class="level-note">CALLS entry • {dist_floor} pts away</div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIOR DAY TARGET (when outside overnight cone)
    # ═══════════════════════════════════════════════════════════════════════════
    if position != Position.INSIDE and prior_target_spx:
        target_color = "calls" if position == Position.ABOVE else "puts"
        target_icon = "🎯"
        if position == Position.ABOVE:
            direction_text = "ASCENDING from Highest Wick"
            anchor_label = "Highest Wick"
            anchor_value = prior_rth['highest_wick']
        else:
            direction_text = "DESCENDING from Lowest Close"
            anchor_label = "Lowest Close"
            anchor_value = prior_rth['lowest_close']
        dist_target = round(abs(prior_target_spx - current_spx), 1)
        
        st.markdown(f'''
        <div class="prior-day-target prior-day-target-{target_color}">
            <div class="prior-target-header">
                <span class="prior-target-icon">{target_icon}</span>
                <span class="prior-target-title">Prior Day Cone Target</span>
                <span class="prior-target-badge {target_color}">{direction_text}</span>
            </div>
            <div class="prior-target-value">{prior_target_spx:,.2f}</div>
            <div class="prior-target-details">
                <span>{dist_target} pts from current</span>
                <span class="prior-target-sep">•</span>
                <span>Prior RTH {anchor_label}: {anchor_value:,.2f}</span>
            </div>
            <div class="prior-target-note">Price outside ON cone → drawn to prior day {'+0.48' if position == Position.ABOVE else '-0.48'}/30min line</div>
        </div>
        ''', unsafe_allow_html=True)
    elif prior_rth["available"]:
        st.markdown(f'''
        <div class="prior-day-info">
            <span class="prior-day-label">Prior RTH:</span>
            <span>Highest Wick: {prior_rth['highest_wick']:,.2f}</span>
            <span class="prior-day-sep">|</span>
            <span>Lowest Close: {prior_rth['lowest_close']:,.2f}</span>
            <span class="prior-day-sep">|</span>
            <span>Close: {prior_rth['close']:,.2f}</span>
        </div>
        ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIMARY TRADE
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header"><div class="section-icon">◉</div><h2 class="section-title">Primary Trade Setup</h2></div>', unsafe_allow_html=True)
    
    if decision["no_trade"]:
        st.markdown(f'<div class="no-trade-card"><div class="no-trade-icon">⊘</div><div class="no-trade-title">NO TRADE</div><div class="no-trade-reason">{decision["no_trade_reason"]}</div></div>', unsafe_allow_html=True)
    else:
        p = decision["primary"]
        if p:
            tc = "calls" if p["direction"] == "CALLS" else "puts"
            di = "↗" if p["direction"] == "CALLS" else "↘"
            st.markdown(f'''
            <div class="trade-card trade-card-{tc}">
                <div class="trade-header"><div class="trade-name">{di} {p["name"]}</div><div class="trade-confidence trade-confidence-{p["confidence"].lower()}">{p["confidence"]} CONFIDENCE</div></div>
                <div class="trade-contract trade-contract-{tc}">{p["contract"]}</div>
                <div class="trade-grid">
                    <div class="trade-metric"><div class="trade-metric-label">Entry Premium</div><div class="trade-metric-value">${p["entry_premium"]:.2f}</div></div>
                    <div class="trade-metric"><div class="trade-metric-label">SPX Entry</div><div class="trade-metric-value">{p["entry"]:,.2f}</div></div>
                    <div class="trade-metric"><div class="trade-metric-label">SPX Stop</div><div class="trade-metric-value">{p["stop"]:,.2f}</div></div>
                </div>
                <div class="trade-targets">
                    <div class="targets-header">◎ Profit Targets</div>
                    <div class="targets-grid">
                        <div class="target-item"><div class="target-label">50%</div><div class="target-price">${p["target_50"]:.2f}</div><div class="target-profit">+${p["profit_50"]:,.0f}</div></div>
                        <div class="target-item"><div class="target-label">75%</div><div class="target-price">${p["target_75"]:.2f}</div><div class="target-profit">+${p["profit_75"]:,.0f}</div></div>
                        <div class="target-item"><div class="target-label">100%</div><div class="target-price">${p["target_100"]:.2f}</div><div class="target-profit">+${p["profit_100"]:,.0f}</div></div>
                    </div>
                </div>
                <div class="trade-trigger"><div class="trigger-label">◈ Entry Trigger</div><div class="trigger-text">{p["trigger"]}</div></div>
            </div>
            ''', unsafe_allow_html=True)
            with st.expander("📋 Trade Rationale"):
                st.write(p["rationale"])
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ALTERNATE TRADE
    # ═══════════════════════════════════════════════════════════════════════════
    if not decision["no_trade"] and decision["alternate"]:
        st.markdown('<div class="section-header"><div class="section-icon">◌</div><h2 class="section-title">Alternate Setup</h2></div>', unsafe_allow_html=True)
        a = decision["alternate"]
        tc = "calls" if a["direction"] == "CALLS" else "puts"
        di = "↗" if a["direction"] == "CALLS" else "↘"
        st.markdown(f'''
        <div class="glass-card glass-card-{tc}" style="opacity:0.85;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
                <div style="font-family:'Syne',sans-serif;font-size:1.05rem;font-weight:600;">{di} {a["name"]}</div>
                <div class="trade-confidence trade-confidence-low">{a["confidence"]}</div>
            </div>
            <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:1rem;color:var(--{tc}-primary);">{a["contract"]} @ ${a["entry_premium"]:.2f}</div>
                <div style="display:flex;gap:14px;">
                    <span style="font-size:0.875rem;color:var(--text-secondary);">50%: <span style="color:var(--calls-primary);">${a["target_50"]:.2f}</span></span>
                    <span style="font-size:0.875rem;color:var(--text-secondary);">75%: <span style="color:var(--calls-primary);">${a["target_75"]:.2f}</span></span>
                    <span style="font-size:0.875rem;color:var(--text-secondary);">100%: <span style="color:var(--calls-primary);">${a["target_100"]:.2f}</span></span>
                </div>
            </div>
            <div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border-subtle);font-size:0.875rem;color:var(--text-tertiary);"><strong style="color:var(--accent-primary);">Trigger:</strong> {a["trigger"]}</div>
        </div>
        ''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SESSIONS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header"><div class="section-icon">◐</div><h2 class="section-title">Global Sessions</h2></div>', unsafe_allow_html=True)
    
    session_data = [("🦘", "Sydney", sydney), ("🗼", "Tokyo", tokyo), ("🏛", "London", london), ("🌙", "Overnight", overnight)]
    cols = st.columns(4)
    for i, (icon, name, data) in enumerate(session_data):
        with cols[i]:
            if data:
                h_mark = " ⬆" if upper_pivot and upper_pivot == data.get("high") else ""
                l_mark = " ⬇" if lower_pivot and lower_pivot == data.get("low") else ""
                st.markdown(f'<div class="session-card"><div class="session-icon">{icon}</div><div class="session-name">{name}</div><div class="session-data"><div class="session-value"><span style="color:var(--text-tertiary);">H</span><span class="session-high">{data["high"]:,.2f}{h_mark}</span></div><div class="session-value"><span style="color:var(--text-tertiary);">L</span><span class="session-low">{data["low"]:,.2f}{l_mark}</span></div></div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="session-card" style="opacity:0.5;"><div class="session-icon">{icon}</div><div class="session-name">{name}</div><div class="session-data"><div style="color:var(--text-muted);font-size:0.85rem;">No data</div></div></div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INDICATORS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header"><div class="section-icon">◧</div><h2 class="section-title">Technical Indicators</h2></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        sc = "bullish" if ema_data["above_200"] else "bearish"
        st.markdown(f'<div class="indicator-card"><div class="indicator-header"><div class="indicator-icon">📊</div><div class="indicator-title">200 EMA Bias</div></div><div class="indicator-row"><span class="indicator-label">Price</span><span class="indicator-value">{ema_data.get("price", "N/A")}</span></div><div class="indicator-row"><span class="indicator-label">200 EMA</span><span class="indicator-value">{ema_data.get("ema_200", "N/A")}</span></div><div class="indicator-status indicator-status-{sc}">{"✓ ABOVE" if ema_data["above_200"] else "✗ BELOW"}</div></div>', unsafe_allow_html=True)
    with col2:
        sc = "bullish" if ema_data["ema_cross"] == "BULLISH" else "bearish"
        st.markdown(f'<div class="indicator-card"><div class="indicator-header"><div class="indicator-icon">📈</div><div class="indicator-title">8/21 EMA Cross</div></div><div class="indicator-row"><span class="indicator-label">8 EMA</span><span class="indicator-value">{ema_data.get("ema_8", "N/A")}</span></div><div class="indicator-row"><span class="indicator-label">21 EMA</span><span class="indicator-value">{ema_data.get("ema_21", "N/A")}</span></div><div class="indicator-status indicator-status-{sc}">{"✓" if ema_data["ema_cross"] == "BULLISH" else "✗"} {ema_data["ema_cross"]}</div></div>', unsafe_allow_html=True)
    with col3:
        if vix_range["available"]:
            vix_icon_ind = {"ABOVE": "▲", "IN RANGE": "◆", "BELOW": "▼"}.get(vix_pos.value, "○")
            sc = "bearish" if vix_pos == VIXPosition.ABOVE_RANGE else "bullish"
            st.markdown(f'<div class="indicator-card"><div class="indicator-header"><div class="indicator-icon">📉</div><div class="indicator-title">VIX Overnight</div></div><div class="indicator-row"><span class="indicator-label">Range</span><span class="indicator-value">{vix_range["bottom"]} - {vix_range["top"]}</span></div><div class="indicator-row"><span class="indicator-label">Current</span><span class="indicator-value">{vix}</span></div><div class="indicator-status indicator-status-{sc}">{vix_icon_ind} {vix_pos.value}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="indicator-card"><div class="indicator-header"><div class="indicator-icon">📉</div><div class="indicator-title">VIX Overnight</div></div><div class="indicator-row"><span class="indicator-label">Current</span><span class="indicator-value">{vix}</span></div><div style="margin-top:8px;color:var(--text-muted);font-size:0.85rem;">Range data unavailable</div></div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown('<div style="margin-top:40px;padding:20px 0;border-top:1px solid var(--border-subtle);text-align:center;"><p style="font-family:\'JetBrains Mono\',monospace;font-size:0.75rem;color:var(--text-muted);letter-spacing:2px;">SPX PROPHET • STRUCTURAL 0DTE TRADING SYSTEM</p></div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
