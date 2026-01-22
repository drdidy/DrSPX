# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET V7.0 - STRUCTURAL 0DTE TRADING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
# 
# "Where Structure Becomes Foresight"
#
# COMPLETE SYSTEM:
# 1. Overnight Channel (Sydney → Tokyo → London)
# 2. 200 EMA Bias (Call/Put directional bias)
# 3. 8/21 EMA Cross (Trend confirmation)
# 4. VIX Overnight Range (2-6 AM zone)
# 5. VIX Position (Current vs overnight range)
# 6. Retail Positioning (Call/Put buying pressure)
# 7. Decision Engine (Primary/Alternate scenarios)
#
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
# PAGE CONFIG & STYLING
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SPX Prophet V7", page_icon="🔮", layout="wide")

# Custom CSS for animated banner and styling
st.markdown("""
<style>
/* Dark theme base */
.stApp {
    background-color: #0e1117;
}

/* Animated Banner Container */
.banner-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
    margin-bottom: 20px;
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 10px;
    border: 1px solid #30364a;
}

/* Animated Pyramid */
.pyramid-container {
    position: relative;
    width: 80px;
    height: 70px;
    margin-bottom: 15px;
}

.pyramid {
    width: 0;
    height: 0;
    border-left: 40px solid transparent;
    border-right: 40px solid transparent;
    border-bottom: 70px solid #00d4aa;
    position: relative;
    animation: pyramidGlow 2s ease-in-out infinite;
}

.pyramid::before {
    content: '';
    position: absolute;
    top: 25px;
    left: -25px;
    width: 0;
    height: 0;
    border-left: 25px solid transparent;
    border-right: 25px solid transparent;
    border-bottom: 45px solid #00b894;
    animation: pyramidPulse 2s ease-in-out infinite;
}

.pyramid-eye {
    position: absolute;
    top: 35px;
    left: 50%;
    transform: translateX(-50%);
    width: 20px;
    height: 20px;
    background: radial-gradient(circle, #fff 0%, #00d4aa 50%, transparent 70%);
    border-radius: 50%;
    animation: eyeGlow 1.5s ease-in-out infinite;
}

@keyframes pyramidGlow {
    0%, 100% { 
        filter: drop-shadow(0 0 10px #00d4aa) drop-shadow(0 0 20px #00d4aa);
    }
    50% { 
        filter: drop-shadow(0 0 20px #00d4aa) drop-shadow(0 0 40px #00d4aa);
    }
}

@keyframes pyramidPulse {
    0%, 100% { opacity: 0.7; }
    50% { opacity: 1; }
}

@keyframes eyeGlow {
    0%, 100% { 
        box-shadow: 0 0 10px #fff, 0 0 20px #00d4aa;
        transform: translateX(-50%) scale(1);
    }
    50% { 
        box-shadow: 0 0 20px #fff, 0 0 40px #00d4aa;
        transform: translateX(-50%) scale(1.1);
    }
}

/* Brand Text */
.brand-title {
    font-size: 2.5rem;
    font-weight: 700;
    color: #ffffff;
    margin: 0;
    text-shadow: 0 0 10px rgba(0, 212, 170, 0.5);
}

.brand-tagline {
    font-size: 1rem;
    color: #00d4aa;
    margin: 5px 0 0 0;
    letter-spacing: 2px;
}

/* Section Headers */
.section-header {
    background: linear-gradient(90deg, #1e3a5f 0%, transparent 100%);
    padding: 10px 15px;
    border-left: 4px solid #00d4aa;
    margin: 20px 0 15px 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: #ffffff;
}

/* Warning Box */
.warning-box {
    background: linear-gradient(135deg, #4a1a1a 0%, #2d1f1f 100%);
    border: 1px solid #ff6b6b;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
}

.warning-box.puts {
    background: linear-gradient(135deg, #1a4a1a 0%, #1f2d1f 100%);
    border-color: #51cf66;
}

.warning-box.neutral {
    background: linear-gradient(135deg, #1a3a4a 0%, #1f2d3f 100%);
    border-color: #4dabf7;
}

/* Trade Card */
.trade-card {
    background: linear-gradient(135deg, #1a2332 0%, #141c28 100%);
    border: 1px solid #30364a;
    border-radius: 10px;
    padding: 20px;
    margin: 10px 0;
}

.trade-card.calls {
    border-left: 4px solid #51cf66;
}

.trade-card.puts {
    border-left: 4px solid #ff6b6b;
}

/* Level Display */
.level-display {
    background: #141820;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
}

.level-ceiling {
    color: #ff6b6b;
    font-size: 1.3rem;
    font-weight: 600;
}

.level-floor {
    color: #51cf66;
    font-size: 1.3rem;
    font-weight: 600;
}

.level-current {
    color: #ffd43b;
    font-size: 1.1rem;
    padding: 10px 0;
    border-top: 1px dashed #30364a;
    border-bottom: 1px dashed #30364a;
    margin: 10px 0;
}

/* Confluence Box */
.confluence-box {
    background: #141820;
    border-radius: 8px;
    padding: 15px;
    text-align: center;
}

.confluence-score {
    font-size: 2rem;
    font-weight: 700;
}

.confluence-score.high { color: #51cf66; }
.confluence-score.medium { color: #ffd43b; }
.confluence-score.low { color: #ff6b6b; }

/* Metric overrides */
[data-testid="stMetricValue"] {
    font-size: 1.5rem;
}

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
CT = pytz.timezone("America/Chicago")
ET = pytz.timezone("America/New_York")
UTC = pytz.UTC

SLOPE = 0.48
SAVE_FILE = "spx_prophet_v7_inputs.json"

# Polygon API
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
def fetch_spx_with_ema():
    result = {
        "price": None, "ema_200": None, "ema_8": None, "ema_21": None,
        "above_200": None, "ema_cross": None, "ema_bias": Bias.NEUTRAL
    }
    
    try:
        spx = yf.Ticker("^GSPC")
        daily = spx.history(period="1y", interval="1d")
        
        if daily is not None and not daily.empty and len(daily) > 200:
            result["price"] = round(float(daily['Close'].iloc[-1]), 2)
            daily['EMA_200'] = daily['Close'].ewm(span=200, adjust=False).mean()
            result["ema_200"] = round(float(daily['EMA_200'].iloc[-1]), 2)
            daily['EMA_8'] = daily['Close'].ewm(span=8, adjust=False).mean()
            daily['EMA_21'] = daily['Close'].ewm(span=21, adjust=False).mean()
            result["ema_8"] = round(float(daily['EMA_8'].iloc[-1]), 2)
            result["ema_21"] = round(float(daily['EMA_21'].iloc[-1]), 2)
            
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
def fetch_vix_overnight_range(trading_date):
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
                
                zone_start = CT.localize(datetime.combine(trading_date, time(2, 0)))
                zone_end = CT.localize(datetime.combine(trading_date, time(6, 0)))
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
# RETAIL POSITIONING (formerly MM Bias)
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def fetch_retail_positioning():
    """
    Analyze retail positioning via VIX Term Structure.
    - Contango (VIX < VIX3M): Heavy call buying
    - Backwardation (VIX > VIX3M): Heavy put buying
    """
    result = {
        "vix": None, "vix3m": None, "spread": None,
        "positioning": "BALANCED",
        "warning": None,
        "bias": Bias.NEUTRAL
    }
    
    try:
        vix_data = yf.Ticker("^VIX").history(period="2d")
        vix3m_data = yf.Ticker("^VIX3M").history(period="2d")
        
        if not vix_data.empty and not vix3m_data.empty:
            vix = round(float(vix_data['Close'].iloc[-1]), 2)
            vix3m = round(float(vix3m_data['Close'].iloc[-1]), 2)
            spread = round(vix - vix3m, 2)
            
            result["vix"] = vix
            result["vix3m"] = vix3m
            result["spread"] = spread
            
            if spread <= -1.5:
                result["positioning"] = "CALL BUYING HEAVY"
                result["warning"] = "Market often fades the crowd"
                result["bias"] = Bias.PUTS  # Favors puts (fade calls)
            elif spread >= 1.5:
                result["positioning"] = "PUT BUYING HEAVY"
                result["warning"] = "Market often fades the crowd"
                result["bias"] = Bias.CALLS  # Favors calls (fade puts)
            else:
                result["positioning"] = "BALANCED"
                result["warning"] = None
                result["bias"] = Bias.NEUTRAL
    except:
        pass
    
    return result

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
    
    sessions = {
        "sydney": (CT.localize(datetime.combine(overnight_day, time(17, 0))),
                   CT.localize(datetime.combine(overnight_day, time(20, 30)))),
        "tokyo": (CT.localize(datetime.combine(overnight_day, time(21, 0))),
                  CT.localize(datetime.combine(trading_date, time(1, 30)))),
        "london": (CT.localize(datetime.combine(trading_date, time(2, 0))),
                   CT.localize(datetime.combine(trading_date, time(5, 0)))),
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
        result["prior_high_time"] = prior_data['High'].idxmax()
        result["prior_low_time"] = prior_data['Low'].idxmin()
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL LOGIC
# ═══════════════════════════════════════════════════════════════════════════════
def determine_channel(sydney, tokyo, london=None):
    if not sydney or not tokyo:
        return ChannelType.UNDETERMINED, "Missing session data", None, None, None, None
    
    all_highs = [
        (sydney["high"], sydney.get("high_time"), "Sydney"),
        (tokyo["high"], tokyo.get("high_time"), "Tokyo")
    ]
    all_lows = [
        (sydney["low"], sydney.get("low_time"), "Sydney"),
        (tokyo["low"], tokyo.get("low_time"), "Tokyo")
    ]
    
    if london:
        all_highs.append((london["high"], london.get("high_time"), "London"))
        all_lows.append((london["low"], london.get("low_time"), "London"))
    
    highest = max(all_highs, key=lambda x: x[0])
    lowest = min(all_lows, key=lambda x: x[0])
    
    true_high, high_time, high_session = highest
    true_low, low_time, low_session = lowest
    
    tokyo_expanded_high = tokyo["high"] > sydney["high"]
    tokyo_expanded_low = tokyo["low"] < sydney["low"]
    
    london_expanded_high = london["high"] > max(sydney["high"], tokyo["high"]) if london else False
    london_expanded_low = london["low"] < min(sydney["low"], tokyo["low"]) if london else False
    
    expanded_high = tokyo_expanded_high or london_expanded_high
    expanded_low = tokyo_expanded_low or london_expanded_low
    
    if expanded_high and expanded_low:
        reason = f"Range expanded both ways"
        return ChannelType.EXPANDING, reason, true_high, true_low, high_time, low_time
    elif not expanded_high and not expanded_low:
        reason = f"Range contracted"
        return ChannelType.CONTRACTING, reason, true_high, true_low, high_time, low_time
    elif expanded_high:
        reason = f"{high_session} made higher high"
        return ChannelType.ASCENDING, reason, true_high, true_low, high_time, low_time
    else:
        reason = f"{low_session} made lower low"
        return ChannelType.DESCENDING, reason, true_high, true_low, high_time, low_time

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
def analyze_market_state(current_spx, ceiling_spx, floor_spx, channel_type, 
                         retail_bias, ema_bias, vix_position, vix):
    
    result = {
        "no_trade": False,
        "no_trade_reason": None,
        "calls_factors": [],
        "puts_factors": [],
        "primary": None,
        "alternate": None
    }
    
    # Position
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
        
        target_50 = round(entry_premium * 1.50, 2)
        target_75 = round(entry_premium * 1.75, 2)
        target_100 = round(entry_premium * 2.00, 2)
        
        profit_50 = round((target_50 - entry_premium) * 100, 0)
        profit_75 = round((target_75 - entry_premium) * 100, 0)
        profit_100 = round((target_100 - entry_premium) * 100, 0)
        
        return {
            "name": name, "direction": direction,
            "entry": entry, "stop": stop,
            "trigger": trigger, "rationale": rationale, "confidence": confidence,
            "strike": strike,
            "contract": f"SPX {strike}{'C' if direction == 'CALLS' else 'P'} 0DTE",
            "entry_premium": entry_premium,
            "target_50": target_50, "target_75": target_75, "target_100": target_100,
            "profit_50": profit_50, "profit_75": profit_75, "profit_100": profit_100
        }
    
    # Build confluence factors
    if channel_type == ChannelType.ASCENDING:
        result["calls_factors"].append("ASCENDING channel")
    elif channel_type == ChannelType.DESCENDING:
        result["puts_factors"].append("DESCENDING channel")
    
    if ema_bias == Bias.CALLS:
        result["calls_factors"].append("Above 200 EMA + 8>21")
    elif ema_bias == Bias.PUTS:
        result["puts_factors"].append("Below 200 EMA + 8<21")
    
    if retail_bias == Bias.PUTS:  # Call buying heavy = fade calls = favor puts
        result["puts_factors"].append("Calls crowded")
    elif retail_bias == Bias.CALLS:  # Put buying heavy = fade puts = favor calls
        result["calls_factors"].append("Puts crowded")
    
    if vix_position == VIXPosition.BELOW_RANGE:
        result["calls_factors"].append("VIX below range")
    elif vix_position == VIXPosition.ABOVE_RANGE:
        result["puts_factors"].append("VIX above range")
    
    # NO TRADE conditions
    if channel_type == ChannelType.CONTRACTING:
        result["no_trade"] = True
        result["no_trade_reason"] = "CONTRACTING channel - No directional bias"
        return result
    
    if channel_type == ChannelType.UNDETERMINED:
        result["no_trade"] = True
        result["no_trade_reason"] = "Cannot determine channel structure"
        return result
    
    # Determine confidence
    calls_score = len(result["calls_factors"])
    puts_score = len(result["puts_factors"])
    
    def get_confidence(score):
        if score >= 3:
            return "HIGH"
        elif score >= 2:
            return "MEDIUM"
        return "LOW"
    
    # Generate scenarios
    if channel_type == ChannelType.ASCENDING:
        if position == Position.INSIDE or position == Position.BELOW:
            result["primary"] = make_scenario(
                "Floor Bounce", "CALLS", floor_spx, floor_spx - 5,
                "Price touches floor",
                f"Confluence: {', '.join(result['calls_factors'])}" if result['calls_factors'] else "ASCENDING structure",
                get_confidence(calls_score)
            )
            result["alternate"] = make_scenario(
                "Floor Break", "PUTS", floor_spx, floor_spx + 5,
                "If floor breaks down",
                "Failed support becomes resistance",
                "LOW"
            )
        else:
            result["primary"] = make_scenario(
                "Ceiling Pullback", "CALLS", ceiling_spx, ceiling_spx - 5,
                "Price pulls back to ceiling",
                f"Confluence: {', '.join(result['calls_factors'])}" if result['calls_factors'] else "Breakout continuation",
                get_confidence(calls_score)
            )
            result["alternate"] = make_scenario(
                "Ceiling Rejection", "PUTS", ceiling_spx, ceiling_spx + 5,
                "If ceiling acts as resistance",
                "Failed breakout",
                "LOW"
            )
    
    elif channel_type == ChannelType.DESCENDING:
        if position == Position.INSIDE or position == Position.ABOVE:
            result["primary"] = make_scenario(
                "Ceiling Rejection", "PUTS", ceiling_spx, ceiling_spx + 5,
                "Price touches ceiling",
                f"Confluence: {', '.join(result['puts_factors'])}" if result['puts_factors'] else "DESCENDING structure",
                get_confidence(puts_score)
            )
            result["alternate"] = make_scenario(
                "Ceiling Break", "CALLS", ceiling_spx, ceiling_spx - 5,
                "If ceiling breaks up",
                "Failed resistance becomes support",
                "LOW"
            )
        else:
            result["primary"] = make_scenario(
                "Floor Pullback", "PUTS", floor_spx, floor_spx + 5,
                "Price pulls back to floor",
                f"Confluence: {', '.join(result['puts_factors'])}" if result['puts_factors'] else "Breakdown continuation",
                get_confidence(puts_score)
            )
            result["alternate"] = make_scenario(
                "Floor Bounce", "CALLS", floor_spx, floor_spx - 5,
                "If floor acts as support",
                "Failed breakdown",
                "LOW"
            )
    
    elif channel_type == ChannelType.EXPANDING:
        result["primary"] = make_scenario(
            "Fade Ceiling", "PUTS", ceiling_spx, ceiling_spx + 5,
            "Price reaches ceiling",
            "EXPANDING: Fade extremes",
            "MEDIUM"
        )
        result["alternate"] = make_scenario(
            "Fade Floor", "CALLS", floor_spx, floor_spx - 5,
            "Price reaches floor",
            "EXPANDING: Fade extremes",
            "MEDIUM"
        )
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def sidebar():
    saved = load_inputs()
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        
        trading_date = st.date_input("📅 Trading Date", value=date.today())
        offset = st.number_input("ES→SPX Offset", value=float(saved.get("offset", 35.5)), step=0.5)
        
        st.divider()
        override = st.checkbox("📝 Manual Override")
        manual = {}
        if override:
            c1, c2 = st.columns(2)
            manual["sydney_high"] = c1.number_input("Syd H", value=6075.0, step=0.5)
            manual["sydney_low"] = c2.number_input("Syd L", value=6050.0, step=0.5)
            manual["tokyo_high"] = c1.number_input("Tok H", value=6080.0, step=0.5)
            manual["tokyo_low"] = c2.number_input("Tok L", value=6045.0, step=0.5)
            manual["london_high"] = c1.number_input("Lon H", value=6078.0, step=0.5)
            manual["london_low"] = c2.number_input("Lon L", value=6040.0, step=0.5)
            manual["current_es"] = st.number_input("Current ES", value=6065.0, step=0.5)
        
        st.divider()
        ref_time = st.selectbox("⏰ Reference Time", ["9:00 AM", "9:30 AM", "10:00 AM"])
        
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
        "manual": manual, "ref_time": ref_map[ref_time]
    }

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    inputs = sidebar()
    now = now_ct()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DATA LOADING
    # ═══════════════════════════════════════════════════════════════════════════
    with st.spinner("Loading market data..."):
        if inputs["override"]:
            m = inputs["manual"]
            current_es = m["current_es"]
            sydney = {"high": m["sydney_high"], "low": m["sydney_low"],
                      "high_time": CT.localize(datetime.combine(inputs["trading_date"] - timedelta(days=1), time(18, 0))),
                      "low_time": CT.localize(datetime.combine(inputs["trading_date"] - timedelta(days=1), time(19, 0)))}
            tokyo = {"high": m["tokyo_high"], "low": m["tokyo_low"],
                     "high_time": CT.localize(datetime.combine(inputs["trading_date"] - timedelta(days=1), time(23, 0))),
                     "low_time": CT.localize(datetime.combine(inputs["trading_date"], time(0, 30)))}
            london = {"high": m["london_high"], "low": m["london_low"],
                      "high_time": CT.localize(datetime.combine(inputs["trading_date"], time(3, 0))),
                      "low_time": CT.localize(datetime.combine(inputs["trading_date"], time(4, 0)))}
            overnight = {"high": max(m["sydney_high"], m["tokyo_high"], m["london_high"]),
                         "low": min(m["sydney_low"], m["tokyo_low"], m["london_low"])}
            sessions = {}
        else:
            es_candles = fetch_es_candles()
            current_es = fetch_es_current() or 6050
            sessions = extract_sessions(es_candles, inputs["trading_date"]) or {}
            sydney = sessions.get("sydney")
            tokyo = sessions.get("tokyo")
            london = sessions.get("london")
            overnight = sessions.get("overnight")
        
        vix_polygon = fetch_vix_polygon()
        vix = vix_polygon if vix_polygon else fetch_vix_yahoo()
        
        vix_range = fetch_vix_overnight_range(inputs["trading_date"])
        vix_pos, vix_pos_desc = get_vix_position(vix, vix_range)
        
        retail_data = fetch_retail_positioning()
        ema_data = fetch_spx_with_ema()
    
    offset = inputs["offset"]
    current_spx = round(current_es - offset, 2)
    
    # Channel calculation
    channel_type, channel_reason, upper_pivot, lower_pivot, upper_time, lower_time = \
        determine_channel(sydney, tokyo, london)
    
    ref_time = CT.localize(datetime.combine(inputs["trading_date"], time(*inputs["ref_time"])))
    ceiling_es, floor_es = calc_channel_levels(upper_pivot, lower_pivot, upper_time, lower_time, ref_time, channel_type)
    
    if ceiling_es is None:
        ceiling_es, floor_es = 6080, 6040
    
    ceiling_spx = round(ceiling_es - offset, 2)
    floor_spx = round(floor_es - offset, 2)
    position = get_position(current_es, ceiling_es, floor_es)
    
    # Decision engine
    decision = analyze_market_state(
        current_spx, ceiling_spx, floor_spx, channel_type,
        retail_data["bias"], ema_data["ema_bias"], vix_pos, vix
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - ANIMATED BANNER
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("""
    <div class="banner-container">
        <div class="pyramid-container">
            <div class="pyramid"></div>
            <div class="pyramid-eye"></div>
        </div>
        <h1 class="brand-title">SPX PROPHET V7</h1>
        <p class="brand-tagline">WHERE STRUCTURE BECOMES FORESIGHT</p>
    </div>
    """, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - MARKET SNAPSHOT
    # ═══════════════════════════════════════════════════════════════════════════
    c1, c2, c3 = st.columns(3)
    c1.metric("SPX", f"{current_spx:,.2f}", f"ES {current_es:,.2f}")
    c2.metric("VIX", f"{vix}")
    c3.metric("Time", now.strftime("%I:%M %p CT"))
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - TODAY'S BIAS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header">📊 TODAY\'S BIAS</div>', unsafe_allow_html=True)
    
    # Channel + EMA indicators
    c1, c2, c3 = st.columns(3)
    
    with c1:
        chan_icon = {"ASCENDING": "🟢", "DESCENDING": "🔴", "EXPANDING": "🟣", "CONTRACTING": "🟡"}.get(channel_type.value, "⚪")
        st.markdown(f"### {chan_icon} {channel_type.value}")
        st.caption(channel_reason)
    
    with c2:
        ema_icon = "📈" if ema_data["above_200"] else "📉"
        ema_text = "ABOVE 200 EMA" if ema_data["above_200"] else "BELOW 200 EMA"
        st.markdown(f"### {ema_icon} {ema_text}")
        bias_text = "Supports CALLS" if ema_data["above_200"] else "Supports PUTS"
        st.caption(bias_text)
    
    with c3:
        cross_icon = "✅" if ema_data["ema_cross"] == "BULLISH" else "❌"
        st.markdown(f"### {cross_icon} 8/21 {ema_data['ema_cross']}")
        cross_detail = "8 EMA > 21 EMA" if ema_data["ema_cross"] == "BULLISH" else "8 EMA < 21 EMA"
        st.caption(cross_detail)
    
    # Retail positioning warning
    if retail_data["positioning"] != "BALANCED":
        warning_class = "warning-box"
        st.markdown(f"""
        <div class="{warning_class}">
            <strong>⚠️ {retail_data['positioning']}</strong><br>
            <span style="color: #aaa;">{retail_data['warning']}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="warning-box neutral">
            <strong>✅ BALANCED</strong><br>
            <span style="color: #aaa;">No crowd pressure - trade freely</span>
        </div>
        """, unsafe_allow_html=True)
    
    # VIX Position
    vix_icon = {"ABOVE": "⬆️", "IN RANGE": "↔️", "BELOW": "⬇️"}.get(vix_pos.value, "❓")
    if vix_range["available"]:
        st.markdown(f"**VIX Position:** {vix_icon} {vix_pos.value} ({vix_range['bottom']} - {vix_range['top']})")
    else:
        st.markdown(f"**VIX Position:** {vix_icon} {vix_pos.value}")
    
    # Confluence scoreboard
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("**🟢 CALLS**")
        if decision["calls_factors"]:
            for factor in decision["calls_factors"]:
                st.markdown(f"✅ {factor}")
        else:
            st.markdown("❌ No supporting factors")
        calls_score = len(decision["calls_factors"])
        score_class = "high" if calls_score >= 3 else "medium" if calls_score >= 2 else "low"
        st.markdown(f'<div class="confluence-box"><span class="confluence-score {score_class}">{calls_score}</span></div>', unsafe_allow_html=True)
    
    with c2:
        st.markdown("**🔴 PUTS**")
        if decision["puts_factors"]:
            for factor in decision["puts_factors"]:
                st.markdown(f"✅ {factor}")
        else:
            st.markdown("❌ No supporting factors")
        puts_score = len(decision["puts_factors"])
        score_class = "high" if puts_score >= 3 else "medium" if puts_score >= 2 else "low"
        st.markdown(f'<div class="confluence-box"><span class="confluence-score {score_class}">{puts_score}</span></div>', unsafe_allow_html=True)
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - TRADING LEVELS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(f'<div class="section-header">📐 TRADING LEVELS @ {inputs["ref_time"][0]}:{inputs["ref_time"][1]:02d} AM</div>', unsafe_allow_html=True)
    
    dist_to_ceiling = round(ceiling_spx - current_spx, 1)
    dist_to_floor = round(current_spx - floor_spx, 1)
    
    st.markdown(f"""
    <div class="level-display">
        <div class="level-ceiling">▲ CEILING: {ceiling_spx:,.2f} &nbsp;&nbsp;<span style="color:#888;font-size:0.9rem;">← PUTS entry zone</span></div>
        <div class="level-current">● SPX NOW: {current_spx:,.2f} &nbsp;&nbsp;<span style="color:#888;">({dist_to_ceiling} to ceiling | {dist_to_floor} to floor)</span></div>
        <div class="level-floor">▼ FLOOR: {floor_spx:,.2f} &nbsp;&nbsp;<span style="color:#888;font-size:0.9rem;">← CALLS entry zone</span></div>
        <div style="margin-top:10px;color:#888;">Position: <strong>{position.value}</strong></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - PRIMARY TRADE
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header">🎯 PRIMARY TRADE</div>', unsafe_allow_html=True)
    
    if decision["no_trade"]:
        st.error(f"🚫 NO TRADE: {decision['no_trade_reason']}")
    else:
        p = decision["primary"]
        if p:
            trade_class = "calls" if p["direction"] == "CALLS" else "puts"
            icon = "🟢" if p["direction"] == "CALLS" else "🔴"
            
            st.markdown(f"""
            <div class="trade-card {trade_class}">
                <h3>{icon} {p['name']} ({p['confidence']})</h3>
                <h2 style="color:#00d4aa;">📋 {p['contract']}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Entry Premium", f"${p['entry_premium']:.2f}")
            c2.metric("SPX Entry", f"{p['entry']:,.2f}")
            c3.metric("SPX Stop", f"{p['stop']:,.2f}")
            
            st.markdown("**🎯 Profit Targets:**")
            c1, c2, c3 = st.columns(3)
            c1.metric("50%", f"${p['target_50']:.2f}", f"+${p['profit_50']:,.0f}")
            c2.metric("75%", f"${p['target_75']:.2f}", f"+${p['profit_75']:,.0f}")
            c3.metric("100%", f"${p['target_100']:.2f}", f"+${p['profit_100']:,.0f}")
            
            st.markdown(f"**📍 Trigger:** {p['trigger']}")
            st.caption(p['rationale'])
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - ALTERNATE TRADE
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header">↩️ ALTERNATE TRADE</div>', unsafe_allow_html=True)
    
    if not decision["no_trade"]:
        a = decision["alternate"]
        if a:
            trade_class = "calls" if a["direction"] == "CALLS" else "puts"
            icon = "🟢" if a["direction"] == "CALLS" else "🔴"
            
            st.markdown(f"""
            <div class="trade-card {trade_class}">
                <h4>{icon} {a['name']} ({a['confidence']})</h4>
                <p style="color:#00d4aa;">📋 {a['contract']} @ ${a['entry_premium']:.2f}</p>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("50%", f"${a['target_50']:.2f}", f"+${a['profit_50']:,.0f}")
            c2.metric("75%", f"${a['target_75']:.2f}", f"+${a['profit_75']:,.0f}")
            c3.metric("100%", f"${a['target_100']:.2f}", f"+${a['profit_100']:,.0f}")
            
            st.markdown(f"**📍 Trigger:** {a['trigger']}")
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - SESSIONS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header">🌏 SESSIONS</div>', unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    
    def show_session(col, name, emoji, data, is_high=False, is_low=False):
        with col:
            st.markdown(f"**{emoji} {name}**")
            if data:
                h_mark = " ⬆️" if is_high else ""
                l_mark = " ⬇️" if is_low else ""
                st.write(f"H: {data['high']}{h_mark}")
                st.write(f"L: {data['low']}{l_mark}")
            else:
                st.write("No data")
    
    syd_high = sydney and upper_pivot == sydney.get("high") if upper_pivot and sydney else False
    syd_low = sydney and lower_pivot == sydney.get("low") if lower_pivot and sydney else False
    tok_high = tokyo and upper_pivot == tokyo.get("high") if upper_pivot and tokyo else False
    tok_low = tokyo and lower_pivot == tokyo.get("low") if lower_pivot and tokyo else False
    lon_high = london and upper_pivot == london.get("high") if upper_pivot and london else False
    lon_low = london and lower_pivot == london.get("low") if lower_pivot and london else False
    
    show_session(c1, "Sydney", "🦘", sydney, syd_high, syd_low)
    show_session(c2, "Tokyo", "🗼", tokyo, tok_high, tok_low)
    show_session(c3, "London", "🏛️", london, lon_high, lon_low)
    show_session(c4, "Overnight", "🌙", overnight)
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - INDICATOR DETAILS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header">📈 INDICATOR DETAILS</div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("**200 EMA**")
        st.write(f"Price: {ema_data.get('price', 'N/A')}")
        st.write(f"200 EMA: {ema_data.get('ema_200', 'N/A')}")
        if ema_data["above_200"]:
            st.success("✅ ABOVE")
        else:
            st.error("❌ BELOW")
    
    with c2:
        st.markdown("**8/21 EMA**")
        st.write(f"8 EMA: {ema_data.get('ema_8', 'N/A')}")
        st.write(f"21 EMA: {ema_data.get('ema_21', 'N/A')}")
        if ema_data["ema_cross"] == "BULLISH":
            st.success("✅ BULLISH (8>21)")
        else:
            st.error("❌ BEARISH (8<21)")
    
    with c3:
        st.markdown("**VIX Overnight**")
        if vix_range["available"]:
            st.write(f"Range: {vix_range['bottom']} - {vix_range['top']}")
            st.write(f"Current: {vix}")
            if vix_pos == VIXPosition.ABOVE_RANGE:
                st.error(f"⬆️ {vix_pos.value}")
            elif vix_pos == VIXPosition.BELOW_RANGE:
                st.success(f"⬇️ {vix_pos.value}")
            else:
                st.info(f"↔️ {vix_pos.value}")
        else:
            st.write(f"Current: {vix}")
            st.caption("Range not available")

if __name__ == "__main__":
    main()
