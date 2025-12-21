"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                           SPX PROPHET v5.1 PREMIUM                            ║
║                    The Complete 0DTE Trading System                           ║
║                       NEOMORPHIC UI + LIVE OPTIONS PRICING                    ║
║                                                                               ║
║  FIXES IN THIS VERSION:                                                       ║
║  • CALLS strikes now OTM (entry + distance instead of entry - distance)      ║
║  • All times converted to Central Time (CT)                                  ║
║  • Both current price AND estimated premium shown in tables                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, time
import pytz
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import streamlit.components.v1 as components
import yfinance as yf

# ============================================================================
# POLYGON.IO CONFIGURATION
# ============================================================================

POLYGON_API_KEY = "DCWuTS1R_fukpfjgf7QnXrLTEOS_giq6"
POLYGON_BASE_URL = "https://api.polygon.io"

POLYGON_SPX = "I:SPX"
POLYGON_VIX = "I:VIX"

POLYGON_HAS_INDICES = True
POLYGON_HAS_OPTIONS = True
POLYGON_HAS_STOCKS = True

# ============================================================================
# CONFIGURATION
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

VIX_TO_SPX_MOVE = {
    0.10: (35, 40),
    0.15: (40, 45),
    0.20: (45, 50),
    0.25: (50, 55),
    0.30: (55, 60),
}

SLOPE_PER_30MIN = 0.45
MIN_CONE_WIDTH = 18.0
CONFLUENCE_THRESHOLD = 5.0
STOP_LOSS_PTS = 6.0
STRIKE_OTM_DISTANCE = 17.5
DELTA = 0.33
CONTRACT_MULTIPLIER = 100
LOW_VIX_THRESHOLD = 13.0
NARROW_CONE_THRESHOLD = 25.0

def get_ct_now() -> datetime:
    return datetime.now(CT_TZ)

def convert_to_ct(dt: datetime) -> datetime:
    """Convert any datetime to Central Time."""
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(CT_TZ)

def format_time_ct(dt: datetime) -> str:
    """Format a datetime as CT time string."""
    ct_time = convert_to_ct(dt)
    return ct_time.strftime('%H:%M CT')

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Pivot:
    price: float
    time: datetime
    name: str
    is_secondary: bool = False
    price_for_ascending: float = 0.0
    price_for_descending: float = 0.0
    
    def __post_init__(self):
        if self.price_for_ascending == 0.0:
            self.price_for_ascending = self.price
        if self.price_for_descending == 0.0:
            self.price_for_descending = self.price

@dataclass
class Cone:
    name: str
    pivot: Pivot
    ascending_rail: float
    descending_rail: float
    width: float
    blocks: int

@dataclass
class VIXZone:
    bottom: float
    top: float
    current: float
    position_pct: float
    status: str
    bias: str
    breakout_time: str
    zones_above: List[float]
    zones_below: List[float]
    zone_size: float = 0.15
    expected_move: tuple = (40, 45)
    auto_detected: bool = False

@dataclass
class OptionQuote:
    ticker: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    mid: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_vol: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    underlying_price: float = 0.0
    in_the_money: bool = False

@dataclass
class TradeSetup:
    direction: str
    cone_name: str
    cone_width: float
    entry: float
    stop: float
    target_25: float
    target_50: float
    target_75: float
    strike: int
    spx_pts_25: float
    spx_pts_50: float
    spx_pts_75: float
    profit_25: float
    profit_50: float
    profit_75: float
    risk_per_contract: float
    rr_ratio: float
    distance: float
    is_active: bool = False
    current_option_price: float = 0.0
    est_entry_price_10am: float = 0.0
    spy_strike_used: int = 0
    using_spy: bool = False
    option_delta: float = 0.33
    stop_loss_pts: float = 6.0
    stop_loss_dollars: float = 0.0
    risk_dollars: float = 0.0
    reward_t1_dollars: float = 0.0
    reward_t2_dollars: float = 0.0
    reward_t3_dollars: float = 0.0

@dataclass
class ESData:
    current_price: float = 0.0
    prior_close: float = 0.0
    overnight_change: float = 0.0
    overnight_change_pct: float = 0.0
    spx_offset: float = 0.0
    spx_equivalent: float = 0.0
    direction: str = "FLAT"
    likely_cone: str = ""
    vix_aligned: bool = False
    conflict_warning: str = ""

@dataclass
class ActiveConeInfo:
    cone_name: str = ""
    is_inside: bool = False
    ascending_rail: float = 0.0
    descending_rail: float = 0.0
    cone_width: float = 0.0
    distance_to_ascending: float = 0.0
    distance_to_descending: float = 0.0
    position_pct: float = 0.0
    nearest_rail: str = ""
    nearest_rail_price: float = 0.0
    at_rail: bool = False
    trade_direction: str = ""

@dataclass
class DayAssessment:
    tradeable: bool
    score: int
    reasons: List[str]
    warnings: List[str]
    recommendation: str

@dataclass
class PolygonStatus:
    connected: bool = False
    last_update: Optional[datetime] = None
    data_delay: str = "Unknown"
    spx_price: float = 0.0
    vix_price: float = 0.0
    error_message: str = ""
    options_available: bool = False

# ============================================================================
# POLYGON API - OPTIONS PRICING
# ============================================================================

def build_option_ticker(underlying: str, expiry_date: datetime, strike: float, option_type: str) -> str:
    date_str = expiry_date.strftime("%y%m%d")
    cp = "C" if option_type.upper() in ["CALL", "C"] else "P"
    strike_str = f"{int(strike * 1000):08d}"
    return f"O:{underlying}{date_str}{cp}{strike_str}"

@st.cache_data(ttl=30)
def polygon_get_option_quote(option_ticker: str) -> Optional[OptionQuote]:
    try:
        url = f"{POLYGON_BASE_URL}/v3/quotes/{option_ticker}"
        params = {"limit": 1, "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        
        quote = OptionQuote(ticker=option_ticker)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                result = data["results"][0]
                quote.bid = result.get("bid_price", 0) or 0
                quote.ask = result.get("ask_price", 0) or 0
                quote.mid = round((quote.bid + quote.ask) / 2, 2) if quote.bid and quote.ask else 0
        
        url2 = f"{POLYGON_BASE_URL}/v3/trades/{option_ticker}"
        params2 = {"limit": 1, "apiKey": POLYGON_API_KEY}
        response2 = requests.get(url2, params=params2, timeout=10)
        
        if response2.status_code == 200:
            data2 = response2.json()
            if data2.get("results") and len(data2["results"]) > 0:
                quote.last = data2["results"][0].get("price", 0) or 0
        
        url3 = f"{POLYGON_BASE_URL}/v3/snapshot/options/{option_ticker}"
        params3 = {"apiKey": POLYGON_API_KEY}
        response3 = requests.get(url3, params=params3, timeout=10)
        
        if response3.status_code == 200:
            data3 = response3.json()
            if data3.get("results"):
                result = data3["results"]
                quote.open_interest = result.get("open_interest", 0) or 0
                quote.implied_vol = result.get("implied_volatility", 0) or 0
                greeks = result.get("greeks", {})
                quote.delta = greeks.get("delta", 0) or 0
                quote.gamma = greeks.get("gamma", 0) or 0
                quote.theta = greeks.get("theta", 0) or 0
                quote.vega = greeks.get("vega", 0) or 0
                quote.underlying_price = result.get("underlying_asset", {}).get("price", 0) or 0
        
        if quote.bid > 0 or quote.ask > 0 or quote.last > 0:
            return quote
        return None
    except:
        return None

def get_next_trading_day() -> datetime:
    now = get_ct_now()
    today = now.date()
    weekday = today.weekday()
    current_time = now.time()
    market_close = time(16, 0)
    
    if weekday == 5:
        next_day = today + timedelta(days=2)
    elif weekday == 6:
        next_day = today + timedelta(days=1)
    elif current_time > market_close:
        if weekday == 4:
            next_day = today + timedelta(days=3)
        else:
            next_day = today + timedelta(days=1)
    else:
        next_day = today
    return datetime.combine(next_day, time(0, 0))

def get_trading_day_label() -> str:
    now = get_ct_now()
    today = now.date()
    next_trading = get_next_trading_day().date()
    
    if next_trading == today:
        return "Today"
    elif next_trading == today + timedelta(days=1):
        return "Tomorrow"
    else:
        return next_trading.strftime("%A, %b %d")

def estimate_option_price_at_entry(current_price: float, current_spx: float, entry_spx: float, 
                                    strike: float, direction: str, delta: float = 0.33) -> float:
    spx_move = entry_spx - current_spx
    if direction == "CALLS":
        price_change = spx_move * delta
    else:
        price_change = -spx_move * delta
    estimated_price = current_price + price_change
    return max(round(estimated_price * 10) / 10, 0.10)

def round_to_ten_cents(value: float) -> float:
    return round(value * 10) / 10

def get_option_pricing_for_setup(setup: TradeSetup, current_spx: float) -> TradeSetup:
    expiry = get_next_trading_day()
    option_type = "C" if setup.direction == "CALLS" else "P"
    
    current_mid = 0.0
    delta = 0.33
    
    spx_ticker = build_option_ticker("SPX", expiry, setup.strike, option_type)
    spx_quote = polygon_get_option_quote(spx_ticker)
    
    if spx_quote and (spx_quote.bid > 0 or spx_quote.ask > 0):
        setup.using_spy = False
        current_mid = spx_quote.mid if spx_quote.mid > 0 else (spx_quote.bid + spx_quote.ask) / 2
        if spx_quote.delta and abs(spx_quote.delta) > 0:
            delta = abs(spx_quote.delta)
    else:
        spy_strike = round(setup.strike / 10)
        setup.spy_strike_used = spy_strike
        spy_ticker = build_option_ticker("SPY", expiry, spy_strike, option_type)
        spy_quote = polygon_get_option_quote(spy_ticker)
        
        if spy_quote and (spy_quote.bid > 0 or spy_quote.ask > 0):
            setup.using_spy = True
            spy_mid = spy_quote.mid if spy_quote.mid > 0 else (spy_quote.bid + spy_quote.ask) / 2
            current_mid = spy_mid * 10
            if spy_quote.delta and abs(spy_quote.delta) > 0:
                delta = abs(spy_quote.delta)
    
    setup.current_option_price = round_to_ten_cents(current_mid)
    setup.option_delta = delta
    
    if current_mid > 0:
        setup.est_entry_price_10am = estimate_option_price_at_entry(
            current_price=current_mid,
            current_spx=current_spx,
            entry_spx=setup.entry,
            strike=setup.strike,
            direction=setup.direction,
            delta=delta
        )
    else:
        distance_to_strike = abs(setup.entry - setup.strike)
        setup.est_entry_price_10am = round_to_ten_cents(max(distance_to_strike * delta * 0.5, 1.00))
    
    return setup

# ============================================================================
# POLYGON API - MARKET DATA
# ============================================================================

@st.cache_data(ttl=30)
def polygon_get_snapshot(ticker: str) -> Optional[Dict]:
    try:
        url = f"{POLYGON_BASE_URL}/v3/snapshot?ticker.any_of={ticker}"
        params = {"apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                result = data["results"][0]
                return {
                    "price": result.get("value", 0),
                    "change": result.get("session", {}).get("change", 0),
                    "change_pct": result.get("session", {}).get("change_percent", 0),
                    "timestamp": result.get("last_updated", 0)
                }
        return None
    except:
        return None

@st.cache_data(ttl=60)
def polygon_get_overnight_vix_range(session_date: datetime) -> Optional[Dict]:
    try:
        session_date_str = session_date.strftime("%Y-%m-%d")
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{POLYGON_VIX}/range/1/minute/{session_date_str}/{session_date_str}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                df = pd.DataFrame(data["results"])
                # Convert from UTC/ET to CT
                df['datetime'] = pd.to_datetime(df['t'], unit='ms', utc=True).dt.tz_convert(CT_TZ)
                
                zone_start = CT_TZ.localize(datetime.combine(session_date.date(), time(2, 0)))
                zone_end = CT_TZ.localize(datetime.combine(session_date.date(), time(6, 0)))
                
                zone_df = df[(df['datetime'] >= zone_start) & (df['datetime'] <= zone_end)]
                
                if not zone_df.empty:
                    return {
                        'bottom': round(float(zone_df['l'].min()), 2),
                        'top': round(float(zone_df['h'].max()), 2),
                        'zone_size': round(float(zone_df['h'].max()) - float(zone_df['l'].min()), 2),
                        'bar_count': len(zone_df)
                    }
        return None
    except:
        return None

@st.cache_data(ttl=60)
def polygon_get_prior_day_data(ticker: str) -> Optional[Dict]:
    try:
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{ticker}/prev"
        params = {"adjusted": "true", "apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                r = data["results"][0]
                return {"open": r.get("o", 0), "high": r.get("h", 0), "low": r.get("l", 0), "close": r.get("c", 0)}
        return None
    except:
        return None

# ============================================================================
# FALLBACK DATA
# ============================================================================

@st.cache_data(ttl=60)
def yf_fetch_current_spx() -> float:
    try:
        spx = yf.Ticker("^GSPC")
        data = spx.history(period='1d', interval='1m')
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    return 0.0

@st.cache_data(ttl=60)
def yf_fetch_current_vix() -> float:
    try:
        vix = yf.Ticker("^VIX")
        data = vix.history(period='1d', interval='1m')
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    return 0.0

@st.cache_data(ttl=300)
def fetch_historical_day_data(ticker: str, date: datetime) -> Dict:
    try:
        t = yf.Ticker(ticker)
        start = date - timedelta(days=5)
        end = date + timedelta(days=1)
        data = t.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), interval='1d')
        
        if not data.empty:
            target_str = date.strftime('%Y-%m-%d')
            for idx in data.index:
                if idx.strftime('%Y-%m-%d') == target_str:
                    row = data.loc[idx]
                    return {
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'close': float(row['Close'])
                    }
            row = data.iloc[-1]
            return {
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close'])
            }
    except:
        pass
    return {'open': 0, 'high': 0, 'low': 0, 'close': 0}

@st.cache_data(ttl=60)
def yf_fetch_es_futures() -> Dict:
    try:
        es = yf.Ticker("ES=F")
        data = es.history(period='2d', interval='1m')
        if not data.empty:
            current_price = float(data['Close'].iloc[-1])
            info = es.info
            prior_close = info.get('previousClose', 0) or info.get('regularMarketPreviousClose', 0)
            
            if prior_close == 0:
                today = datetime.now().date()
                yesterday_data = data[data.index.date < today]
                if not yesterday_data.empty:
                    prior_close = float(yesterday_data['Close'].iloc[-1])
            
            overnight_change = current_price - prior_close if prior_close > 0 else 0
            overnight_change_pct = (overnight_change / prior_close * 100) if prior_close > 0 else 0
            
            return {
                'current': round(current_price, 2),
                'prior_close': round(prior_close, 2),
                'change': round(overnight_change, 2),
                'change_pct': round(overnight_change_pct, 2)
            }
    except:
        pass
    return {'current': 0, 'prior_close': 0, 'change': 0, 'change_pct': 0}

def analyze_es_data(es_data: Dict, current_spx: float, vix_zone: VIXZone) -> ESData:
    es = ESData()
    
    if es_data.get('current', 0) == 0:
        return es
    
    es.current_price = es_data['current']
    es.prior_close = es_data['prior_close']
    es.overnight_change = es_data['change']
    es.overnight_change_pct = es_data['change_pct']
    
    if current_spx > 0:
        es.spx_offset = round(es.current_price - current_spx, 2)
        es.spx_equivalent = round(es.current_price - es.spx_offset, 2)
    
    if es.overnight_change >= 5:
        es.direction = "UP"
        es.likely_cone = "HIGH"
    elif es.overnight_change <= -5:
        es.direction = "DOWN"
        es.likely_cone = "LOW"
    else:
        es.direction = "FLAT"
        es.likely_cone = ""
    
    if es.direction == "UP":
        if vix_zone.status == "BELOW_ZONE":
            es.vix_aligned = True
        elif vix_zone.status == "ABOVE_ZONE":
            es.vix_aligned = False
            es.conflict_warning = "ES bullish but VIX bearish - wait for confirmation"
        else:
            es.vix_aligned = False
            es.conflict_warning = "VIX in zone - wait for breakout"
    elif es.direction == "DOWN":
        if vix_zone.status == "ABOVE_ZONE":
            es.vix_aligned = True
        elif vix_zone.status == "BELOW_ZONE":
            es.vix_aligned = False
            es.conflict_warning = "ES bearish but VIX bullish - wait for confirmation"
        else:
            es.vix_aligned = False
            es.conflict_warning = "VIX in zone - wait for breakout"
    else:
        es.vix_aligned = False
        es.conflict_warning = "ES flat - no clear direction"
    
    return es

# ============================================================================
# VIX ZONE LOGIC
# ============================================================================

def get_expected_move(zone_size: float) -> Tuple[int, int]:
    for threshold, move in sorted(VIX_TO_SPX_MOVE.items()):
        if zone_size <= threshold:
            return move
    return (60, 70)

def analyze_vix_zone(current: float, bottom: float, top: float) -> VIXZone:
    zone_size = round(top - bottom, 2)
    expected_move = get_expected_move(zone_size)
    
    if top - bottom > 0:
        position_pct = ((current - bottom) / (top - bottom)) * 100
    else:
        position_pct = 50.0
    
    position_pct = max(0, min(100, position_pct))
    
    zones_above = [round(top + (i * zone_size), 2) for i in range(1, 4)]
    zones_below = [round(bottom - (i * zone_size), 2) for i in range(1, 4)]
    
    if current < bottom:
        status = "BELOW_ZONE"
        bias = "CALLS"
    elif current > top:
        status = "ABOVE_ZONE"
        bias = "PUTS"
    else:
        status = "IN_ZONE"
        if position_pct < 30:
            bias = "CALLS"
        elif position_pct > 70:
            bias = "PUTS"
        else:
            bias = "WAIT"
    
    ct_now = get_ct_now()
    breakout_time = ""
    if time(6, 0) <= ct_now.time() <= time(6, 30):
        breakout_time = "RELIABLE BREAKOUT WINDOW"
    elif time(6, 30) < ct_now.time() <= time(9, 30):
        breakout_time = "DANGER ZONE - High reversal risk"
    
    return VIXZone(
        bottom=bottom, top=top, current=current,
        position_pct=position_pct, status=status, bias=bias,
        breakout_time=breakout_time, zones_above=zones_above,
        zones_below=zones_below, zone_size=zone_size, expected_move=expected_move
    )

# ============================================================================
# CONE & SETUP LOGIC
# ============================================================================

def count_blocks(start: datetime, end: datetime) -> int:
    diff = (end - start).total_seconds()
    return max(int(diff // 1800), 1)

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    cones = []
    for pivot in pivots:
        start_time = pivot.time + timedelta(minutes=30)
        blocks = count_blocks(start_time, eval_time)
        ascending = pivot.price_for_ascending + (blocks * SLOPE_PER_30MIN)
        descending = pivot.price_for_descending - (blocks * SLOPE_PER_30MIN)
        width = ascending - descending
        cones.append(Cone(
            name=pivot.name, pivot=pivot,
            ascending_rail=round(ascending, 2),
            descending_rail=round(descending, 2),
            width=round(width, 2), blocks=blocks
        ))
    return cones

def find_active_cone(price: float, cones: List[Cone]) -> Dict:
    result = {'inside_cone': None, 'nearest_cone': None, 'distance': 0, 'at_rail': False, 'rail_type': None}
    if not cones:
        return result
    
    for cone in cones:
        if cone.descending_rail <= price <= cone.ascending_rail:
            result['inside_cone'] = cone
            dist_asc = cone.ascending_rail - price
            dist_desc = price - cone.descending_rail
            if dist_asc <= 3:
                result['at_rail'] = True
                result['rail_type'] = 'ascending'
                result['distance'] = round(dist_asc, 2)
            elif dist_desc <= 3:
                result['at_rail'] = True
                result['rail_type'] = 'descending'
                result['distance'] = round(dist_desc, 2)
            return result
    
    min_dist = float('inf')
    for cone in cones:
        for rail, rtype in [(cone.ascending_rail, 'ascending'), (cone.descending_rail, 'descending')]:
            d = abs(price - rail)
            if d < min_dist:
                min_dist = d
                result['nearest_cone'] = cone
                result['rail_type'] = rtype
                result['distance'] = round(d, 2)
    return result

def get_detailed_active_cone(price: float, cones: List[Cone]) -> ActiveConeInfo:
    info = ActiveConeInfo()
    
    if not cones:
        return info
    
    for cone in cones:
        if cone.descending_rail <= price <= cone.ascending_rail:
            info.cone_name = cone.name
            info.is_inside = True
            info.ascending_rail = cone.ascending_rail
            info.descending_rail = cone.descending_rail
            info.cone_width = cone.width
            info.distance_to_ascending = round(cone.ascending_rail - price, 2)
            info.distance_to_descending = round(price - cone.descending_rail, 2)
            info.position_pct = round((price - cone.descending_rail) / cone.width * 100, 1)
            
            if info.distance_to_ascending <= info.distance_to_descending:
                info.nearest_rail = "ascending"
                info.nearest_rail_price = cone.ascending_rail
                info.trade_direction = "PUTS"
            else:
                info.nearest_rail = "descending"
                info.nearest_rail_price = cone.descending_rail
                info.trade_direction = "CALLS"
            
            info.at_rail = min(info.distance_to_ascending, info.distance_to_descending) <= 5
            return info
    
    min_dist = float('inf')
    nearest_cone = None
    nearest_rail_type = ""
    
    for cone in cones:
        for rail_price, rail_type in [(cone.ascending_rail, 'ascending'), (cone.descending_rail, 'descending')]:
            d = abs(price - rail_price)
            if d < min_dist:
                min_dist = d
                nearest_cone = cone
                nearest_rail_type = rail_type
                info.nearest_rail_price = rail_price
    
    if nearest_cone:
        info.cone_name = nearest_cone.name
        info.is_inside = False
        info.ascending_rail = nearest_cone.ascending_rail
        info.descending_rail = nearest_cone.descending_rail
        info.cone_width = nearest_cone.width
        info.distance_to_ascending = round(abs(nearest_cone.ascending_rail - price), 2)
        info.distance_to_descending = round(abs(price - nearest_cone.descending_rail), 2)
        info.nearest_rail = nearest_rail_type
        info.trade_direction = "PUTS" if nearest_rail_type == "ascending" else "CALLS"
        info.at_rail = min_dist <= 5
    
    return info

def generate_setups(cones: List[Cone], current_price: float, vix_bias: str) -> List[TradeSetup]:
    setups = []
    for cone in cones:
        if cone.width < MIN_CONE_WIDTH:
            continue
        
        # CALLS - Entry at descending rail, targets going UP
        # FIX: Strike should be ABOVE entry (OTM call = strike > entry)
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        t25_c = round(entry_c + cone.width * 0.25, 2)
        t50_c = round(entry_c + cone.width * 0.50, 2)
        t75_c = round(entry_c + cone.width * 0.75, 2)
        # OTM call strike = entry + distance (strike ABOVE entry)
        strike_c = int(round((entry_c + STRIKE_OTM_DISTANCE) / 5) * 5)
        
        stop_loss_dollars_c = round(STOP_LOSS_PTS * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t1_c = round(cone.width * 0.25 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t2_c = round(cone.width * 0.50 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t3_c = round(cone.width * 0.75 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        
        setup_c = TradeSetup(
            direction="CALLS", cone_name=cone.name, cone_width=cone.width,
            entry=entry_c, stop=round(entry_c - STOP_LOSS_PTS, 2),
            target_25=t25_c, target_50=t50_c, target_75=t75_c,
            strike=strike_c,
            spx_pts_25=round(cone.width * 0.25, 2),
            spx_pts_50=round(cone.width * 0.50, 2),
            spx_pts_75=round(cone.width * 0.75, 2),
            profit_25=reward_t1_c,
            profit_50=reward_t2_c,
            profit_75=reward_t3_c,
            risk_per_contract=stop_loss_dollars_c,
            rr_ratio=round((cone.width * 0.50) / STOP_LOSS_PTS, 2),
            distance=round(dist_c, 1),
            is_active=(dist_c <= 5 and vix_bias in ["CALLS", "WAIT"]),
            stop_loss_pts=STOP_LOSS_PTS,
            stop_loss_dollars=stop_loss_dollars_c,
            risk_dollars=stop_loss_dollars_c,
            reward_t1_dollars=reward_t1_c,
            reward_t2_dollars=reward_t2_c,
            reward_t3_dollars=reward_t3_c
        )
        setups.append(setup_c)
        
        # PUTS - Entry at ascending rail, targets going DOWN
        # Strike should be BELOW entry (OTM put = strike < entry)
        entry_p = cone.ascending_rail
        dist_p = abs(current_price - entry_p)
        t25_p = round(entry_p - cone.width * 0.25, 2)
        t50_p = round(entry_p - cone.width * 0.50, 2)
        t75_p = round(entry_p - cone.width * 0.75, 2)
        # OTM put strike = entry - distance (strike BELOW entry)
        strike_p = int(round((entry_p - STRIKE_OTM_DISTANCE) / 5) * 5)
        
        stop_loss_dollars_p = round(STOP_LOSS_PTS * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t1_p = round(cone.width * 0.25 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t2_p = round(cone.width * 0.50 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        reward_t3_p = round(cone.width * 0.75 * DELTA * CONTRACT_MULTIPLIER / 10) * 10
        
        setup_p = TradeSetup(
            direction="PUTS", cone_name=cone.name, cone_width=cone.width,
            entry=entry_p, stop=round(entry_p + STOP_LOSS_PTS, 2),
            target_25=t25_p, target_50=t50_p, target_75=t75_p,
            strike=strike_p,
            spx_pts_25=round(cone.width * 0.25, 2),
            spx_pts_50=round(cone.width * 0.50, 2),
            spx_pts_75=round(cone.width * 0.75, 2),
            profit_25=reward_t1_p,
            profit_50=reward_t2_p,
            profit_75=reward_t3_p,
            risk_per_contract=stop_loss_dollars_p,
            rr_ratio=round((cone.width * 0.50) / STOP_LOSS_PTS, 2),
            distance=round(dist_p, 1),
            is_active=(dist_p <= 5 and vix_bias in ["PUTS", "WAIT"]),
            stop_loss_pts=STOP_LOSS_PTS,
            stop_loss_dollars=stop_loss_dollars_p,
            risk_dollars=stop_loss_dollars_p,
            reward_t1_dollars=reward_t1_p,
            reward_t2_dollars=reward_t2_p,
            reward_t3_dollars=reward_t3_p
        )
        setups.append(setup_p)
    
    return setups

def assess_day(vix: VIXZone, cones: List[Cone]) -> DayAssessment:
    score = 50
    reasons = []
    warnings = []
    
    if vix.zone_size >= 0.15:
        score += 15
        reasons.append(f"Good VIX zone size: {vix.zone_size}")
    else:
        score -= 10
        warnings.append(f"Tight VIX zone: {vix.zone_size}")
    
    if vix.current < LOW_VIX_THRESHOLD:
        score -= 15
        warnings.append(f"Low VIX ({vix.current}) = choppy conditions")
    
    wide_cones = [c for c in cones if c.width >= NARROW_CONE_THRESHOLD]
    if len(wide_cones) >= 2:
        score += 20
        reasons.append(f"{len(wide_cones)} wide cones available")
    elif len(wide_cones) == 1:
        score += 10
        reasons.append("1 wide cone available")
    else:
        score -= 15
        warnings.append("No wide cones - limited setups")
    
    score = max(0, min(100, score))
    
    if score >= 70:
        rec = "FULL"
    elif score >= 50:
        rec = "REDUCED"
    else:
        rec = "SKIP"
    
    return DayAssessment(tradeable=score >= 50, score=score, reasons=reasons, warnings=warnings, recommendation=rec)

# ============================================================================
# NEOMORPHIC UI RENDERING
# ============================================================================

def render_neomorphic_dashboard(spx: float, vix: VIXZone, cones: List[Cone], setups: List[TradeSetup],
                                 assessment: DayAssessment, prior: Dict, active_cone_info: Dict = None,
                                 polygon_status: PolygonStatus = None, pivots: List[Pivot] = None,
                                 es_data: ESData = None, detailed_cone: ActiveConeInfo = None,
                                 trading_date: datetime = None, is_historical: bool = False) -> str:
    
    if pivots is None:
        pivots = []
    if es_data is None:
        es_data = ESData()
    if detailed_cone is None:
        detailed_cone = ActiveConeInfo()
    if trading_date is None:
        trading_date = get_ct_now()
    
    if hasattr(trading_date, 'date'):
        eval_date = trading_date.date()
    else:
        eval_date = trading_date
    
    # Color palette
    bg = "#e8eef3"
    card_bg = "#e8eef3"
    shadow_dark = "#c5ccd3"
    shadow_light = "#ffffff"
    text_dark = "#2d3748"
    text_med = "#4a5568"
    text_light = "#718096"
    green = "#10b981"
    green_glow = "#34d399"
    red = "#ef4444"
    red_glow = "#f87171"
    amber = "#f59e0b"
    blue = "#3b82f6"
    
    if vix.bias == 'CALLS':
        bias_color, bias_glow, bias_text, bias_icon = green, green_glow, "BULLISH", "▲"
    elif vix.bias == 'PUTS':
        bias_color, bias_glow, bias_text, bias_icon = red, red_glow, "BEARISH", "▼"
    else:
        bias_color, bias_glow, bias_text, bias_icon = amber, "#fbbf24", "NEUTRAL", "●"
    
    score_color = green if assessment.score >= 70 else amber if assessment.score >= 50 else red
    
    if polygon_status and polygon_status.connected:
        conn_html = f'<span style="display:inline-flex;align-items:center;gap:6px;"><span style="width:10px;height:10px;background:{green};border-radius:50%;box-shadow:0 0 8px {green};"></span><span style="color:{green};font-weight:600;font-size:12px;">LIVE</span></span>'
    else:
        conn_html = f'<span style="display:inline-flex;align-items:center;gap:6px;"><span style="width:10px;height:10px;background:{text_light};border-radius:50%;"></span><span style="color:{text_light};font-weight:600;font-size:12px;">OFFLINE</span></span>'
    
    ct_now = get_ct_now()
    time_display = ct_now.strftime('%H:%M') + ' CT'
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; background: {bg}; color: {text_dark}; min-height: 100vh; padding: 32px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .neo-card {{ background: {card_bg}; border-radius: 24px; box-shadow: 8px 8px 16px {shadow_dark}, -8px -8px 16px {shadow_light}; padding: 28px; margin-bottom: 24px; }}
        .neo-inset {{ background: {card_bg}; border-radius: 16px; box-shadow: inset 4px 4px 8px {shadow_dark}, inset -4px -4px 8px {shadow_light}; padding: 20px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }}
        .logo {{ display: flex; align-items: center; gap: 16px; }}
        .logo-icon {{ width: 52px; height: 52px; background: linear-gradient(135deg, {blue} 0%, #8b5cf6 100%); border-radius: 14px; display: flex; align-items: center; justify-content: center; box-shadow: 6px 6px 12px {shadow_dark}, -6px -6px 12px {shadow_light}; }}
        .logo-icon span {{ font-size: 20px; font-weight: 800; color: white; }}
        .logo-text h1 {{ font-size: 20px; font-weight: 800; color: {text_dark}; margin-bottom: 2px; }}
        .logo-tagline {{ font-size: 12px; color: {text_med}; font-style: italic; margin-bottom: 2px; }}
        .logo-text p {{ font-size: 11px; color: {text_light}; }}
        .header-right {{ display: flex; align-items: center; gap: 20px; }}
        .time-display {{ font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 600; color: {text_dark}; }}
        .hero-grid {{ display: grid; grid-template-columns: 1fr 1fr 320px; gap: 24px; margin-bottom: 32px; }}
        .price-label {{ font-size: 12px; font-weight: 600; color: {text_light}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }}
        .price-value {{ font-family: 'JetBrains Mono', monospace; font-size: 36px; font-weight: 700; color: {text_dark}; margin-bottom: 12px; }}
        .price-meta {{ display: flex; gap: 24px; }}
        .meta-label {{ font-size: 11px; font-weight: 600; color: {text_light}; text-transform: uppercase; }}
        .meta-value {{ font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 600; color: {text_dark}; }}
        .vix-zone-bar {{ height: 16px; border-radius: 8px; background: linear-gradient(90deg, {green}40 0%, {bg} 40%, {bg} 60%, {red}40 100%); position: relative; margin: 16px 0; box-shadow: inset 2px 2px 4px {shadow_dark}, inset -2px -2px 4px {shadow_light}; }}
        .vix-marker {{ position: absolute; top: 50%; transform: translate(-50%, -50%); width: 24px; height: 24px; background: {bias_color}; border-radius: 50%; box-shadow: 0 0 12px {bias_glow}; border: 3px solid {card_bg}; }}
        .vix-labels {{ display: flex; justify-content: space-between; font-size: 12px; color: {text_light}; font-family: 'JetBrains Mono', monospace; }}
        .bias-card {{ display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; background: linear-gradient(135deg, {bias_color}15 0%, {bias_color}05 100%); border: 2px solid {bias_color}30; }}
        .bias-icon {{ font-size: 32px; color: {bias_color}; margin-bottom: 8px; }}
        .bias-label {{ font-size: 20px; font-weight: 800; color: {bias_color}; }}
        .bias-sub {{ font-size: 12px; color: {text_med}; margin-top: 8px; }}
        .bias-pct {{ font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 700; color: {bias_color}; background: {card_bg}; padding: 8px 20px; border-radius: 50px; margin-top: 16px; box-shadow: 4px 4px 8px {shadow_dark}, -4px -4px 8px {shadow_light}; }}
        .score-section {{ display: flex; align-items: center; gap: 28px; margin-bottom: 32px; }}
        .score-circle {{ width: 100px; height: 100px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; background: {card_bg}; box-shadow: 8px 8px 16px {shadow_dark}, -8px -8px 16px {shadow_light}, inset 0 0 0 4px {score_color}30; }}
        .score-value {{ font-family: 'JetBrains Mono', monospace; font-size: 24px; font-weight: 700; color: {score_color}; }}
        .score-label {{ font-size: 11px; font-weight: 600; color: {text_light}; text-transform: uppercase; }}
        .score-info {{ flex: 1; }}
        .score-rec {{ display: inline-block; padding: 6px 16px; border-radius: 8px; font-size: 12px; font-weight: 700; background: {score_color}20; color: {score_color}; margin-bottom: 12px; }}
        .score-warnings {{ font-size: 12px; color: {text_med}; }}
        .section-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
        .section-title {{ font-size: 14px; font-weight: 700; color: {text_light}; text-transform: uppercase; letter-spacing: 2px; }}
        table {{ width: 100%; border-collapse: separate; border-spacing: 0; }}
        thead {{ background: {bg}; }}
        th {{ font-size: 11px; font-weight: 700; color: {text_light}; text-transform: uppercase; padding: 16px 12px; text-align: left; border-bottom: 2px solid {shadow_dark}; }}
        td {{ font-size: 13px; padding: 14px 12px; color: {text_dark}; border-bottom: 1px solid {shadow_dark}50; }}
        tr:last-child td {{ border-bottom: none; }}
        tbody tr:hover {{ background: {shadow_light}; }}
        .mono {{ font-family: 'JetBrains Mono', monospace; font-weight: 500; }}
        .text-green {{ color: {green}; }}
        .text-red {{ color: {red}; }}
        .text-amber {{ color: {amber}; }}
        .text-muted {{ color: {text_light}; }}
        .font-bold {{ font-weight: 700; }}
        .pill {{ display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 50px; font-size: 12px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
        .pill-green {{ background: {green}20; color: {green}; }}
        .pill-red {{ background: {red}20; color: {red}; }}
        .pill-amber {{ background: {amber}20; color: {amber}; }}
        .pill-neutral {{ background: {bg}; color: {text_med}; box-shadow: 2px 2px 4px {shadow_dark}, -2px -2px 4px {shadow_light}; }}
        .row-active {{ background: linear-gradient(90deg, {green}15, transparent) !important; }}
        .data-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }}
        .data-cell {{ text-align: center; padding: 16px; }}
        .data-cell-label {{ font-size: 11px; font-weight: 600; color: {text_light}; text-transform: uppercase; margin-bottom: 6px; }}
        .data-cell-value {{ font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 700; color: {text_dark}; }}
        .premium-cell {{ display: flex; flex-direction: column; gap: 2px; }}
        .premium-current {{ font-size: 11px; color: {text_light}; }}
        .premium-est {{ font-size: 14px; font-weight: 700; color: {green}; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="logo">
            <div class="logo-icon"><span>SP</span></div>
            <div class="logo-text">
                <h1>SPX Prophet</h1>
                <div class="logo-tagline">Where Structure Becomes Foresight</div>
                <p>v5.1 Premium</p>
            </div>
        </div>
        <div class="header-right">
            {conn_html}
            <div class="time-display">{'📅 ' + eval_date.strftime('%b %d, %Y') if is_historical else time_display}</div>
        </div>
    </div>
'''
    
    if is_historical:
        html += f'''
    <div class="neo-card" style="background:linear-gradient(135deg, {amber}15, {amber}05);border:2px solid {amber}50;">
        <div style="display:flex;align-items:center;gap:16px;">
            <div style="font-size:24px;">📅</div>
            <div>
                <div style="font-weight:700;font-size:14px;color:{amber};">Historical Mode — {eval_date.strftime('%A, %B %d, %Y')}</div>
                <div style="font-size:12px;color:{text_med};margin-top:4px;">SPX close: <strong>{spx:,.2f}</strong></div>
            </div>
        </div>
    </div>
'''
    
    html += f'''
    <div class="hero-grid">
        <div class="neo-card">
            <div class="price-label">S&P 500 Index{' (Close)' if is_historical else ''}</div>
            <div class="price-value">{spx:,.2f}</div>
            <div class="price-meta">
                <div><span class="meta-label">VIX</span><br><span class="meta-value">{vix.current:.2f}</span></div>
                <div><span class="meta-label">Expected</span><br><span class="meta-value">±{vix.expected_move[0]}-{vix.expected_move[1]}</span></div>
            </div>
        </div>
        <div class="neo-card">
            <div class="price-label">VIX Overnight Zone (2-6 AM CT)</div>
            <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:8px;">
                <span class="meta-value">{vix.bottom:.2f}</span>
                <span style="color:{text_light};">—</span>
                <span class="meta-value">{vix.top:.2f}</span>
                <span class="pill pill-neutral" style="margin-left:auto;">Δ {vix.zone_size:.2f}</span>
            </div>
            <div class="vix-zone-bar"><div class="vix-marker" style="left:{vix.position_pct}%;"></div></div>
            <div class="vix-labels"><span>{vix.bottom:.2f}</span><span>VIX @ {vix.position_pct:.0f}%</span><span>{vix.top:.2f}</span></div>
        </div>
        <div class="neo-card bias-card">
            <div class="bias-icon">{bias_icon}</div>
            <div class="bias-label">{bias_text}</div>
            <div class="bias-sub">Market Bias</div>
            <div class="bias-pct">{vix.position_pct:.0f}%</div>
        </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px;">
'''
    
    # ES Futures Card
    if not is_historical and es_data.current_price > 0:
        es_color = green if es_data.direction == "UP" else red if es_data.direction == "DOWN" else text_light
        es_arrow = "▲" if es_data.direction == "UP" else "▼" if es_data.direction == "DOWN" else "●"
        es_sign = "+" if es_data.overnight_change >= 0 else ""
        align_icon = "✅" if es_data.vix_aligned else "⚠️"
        align_text = "VIX Aligned" if es_data.vix_aligned else es_data.conflict_warning
        align_color = green if es_data.vix_aligned else amber
        
        html += f'''
        <div class="neo-card">
            <div class="price-label">ES Futures Overnight</div>
            <div style="display:flex;align-items:center;gap:16px;margin:12px 0;">
                <span style="font-size:24px;color:{es_color};">{es_arrow}</span>
                <div>
                    <div class="mono" style="font-size:20px;font-weight:700;">{es_data.current_price:,.2f}</div>
                    <div class="mono" style="font-size:12px;color:{es_color};">{es_sign}{es_data.overnight_change:,.2f} ({es_sign}{es_data.overnight_change_pct:.2f}%)</div>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px;">
                <div class="neo-inset" style="padding:12px;text-align:center;">
                    <div style="font-size:11px;color:{text_light};">SPX Offset</div>
                    <div class="mono" style="font-size:14px;">{es_data.spx_offset:+.2f} pts</div>
                </div>
                <div class="neo-inset" style="padding:12px;text-align:center;">
                    <div style="font-size:11px;color:{text_light};">Likely Cone</div>
                    <div style="font-size:14px;font-weight:700;color:{es_color};">{es_data.likely_cone or "—"}</div>
                </div>
            </div>
            <div style="margin-top:16px;padding:10px;background:{align_color}15;border-radius:8px;border-left:3px solid {align_color};">
                <span style="font-weight:600;font-size:12px;color:{align_color};">{align_icon} {align_text}</span>
            </div>
        </div>
'''
    else:
        msg = "📅 Historical Mode - ES data not available" if is_historical else "Loading ES data..."
        html += f'<div class="neo-card"><div class="price-label">ES Futures Overnight</div><div style="color:{text_light};padding:20px 0;text-align:center;">{msg}</div></div>'
    
    # Active Cone Card
    if detailed_cone.cone_name:
        pos_color = green if detailed_cone.position_pct < 30 else red if detailed_cone.position_pct > 70 else amber
        dir_color = green if detailed_cone.trade_direction == "CALLS" else red
        dir_arrow = "▲" if detailed_cone.trade_direction == "CALLS" else "▼"
        status = "INSIDE" if detailed_cone.is_inside else "OUTSIDE"
        rail_badge = f'<span class="pill pill-green" style="margin-left:12px;">🎯 AT RAIL</span>' if detailed_cone.at_rail and not is_historical else ''
        
        html += f'''
        <div class="neo-card">
            <div class="price-label">{"Cone Position (at Close)" if is_historical else "Active Cone Position"}</div>
            <div style="display:flex;align-items:center;justify-content:space-between;margin:12px 0;">
                <div style="font-size:16px;font-weight:700;">{detailed_cone.cone_name}</div>
                <span class="pill pill-neutral">{status}</span>{rail_badge}
            </div>
            <div style="margin:16px 0;">
                <div style="display:flex;justify-content:space-between;font-size:11px;color:{text_light};margin-bottom:6px;"><span>▲ CALLS Zone</span><span>▼ PUTS Zone</span></div>
                <div style="height:10px;border-radius:5px;background:linear-gradient(90deg, {green}40 0%, {bg} 30%, {bg} 70%, {red}40 100%);position:relative;box-shadow:inset 2px 2px 4px {shadow_dark},inset -2px -2px 4px {shadow_light};">
                    <div style="position:absolute;top:50%;left:{detailed_cone.position_pct}%;transform:translate(-50%,-50%);width:16px;height:16px;background:{pos_color};border-radius:50%;border:2px solid {card_bg};box-shadow:0 0 8px {pos_color};"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:11px;margin-top:6px;">
                    <span class="mono" style="color:{green};">{detailed_cone.descending_rail:,.2f}</span>
                    <span class="mono" style="color:{text_med};">SPX @ {detailed_cone.position_pct:.0f}%</span>
                    <span class="mono" style="color:{red};">{detailed_cone.ascending_rail:,.2f}</span>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
                <div class="neo-inset" style="padding:10px;text-align:center;"><div style="font-size:11px;color:{text_light};">To Ascending</div><div class="mono" style="font-size:12px;color:{red};">{detailed_cone.distance_to_ascending:.1f} pts</div></div>
                <div class="neo-inset" style="padding:10px;text-align:center;"><div style="font-size:11px;color:{text_light};">Cone Width</div><div class="mono" style="font-size:12px;">{detailed_cone.cone_width:.0f} pts</div></div>
                <div class="neo-inset" style="padding:10px;text-align:center;"><div style="font-size:11px;color:{text_light};">To Descending</div><div class="mono" style="font-size:12px;color:{green};">{detailed_cone.distance_to_descending:.1f} pts</div></div>
            </div>
            <div style="margin-top:14px;padding:10px;background:{dir_color}15;border-radius:8px;text-align:center;">
                <span style="font-size:16px;color:{dir_color};">{dir_arrow}</span>
                <span style="font-weight:700;font-size:12px;color:{dir_color};margin-left:8px;">Nearest: {detailed_cone.nearest_rail.upper()} RAIL → {detailed_cone.trade_direction}</span>
            </div>
        </div>
'''
    else:
        html += f'<div class="neo-card"><div class="price-label">Active Cone Position</div><div style="color:{text_light};padding:20px 0;">No cone data available</div></div>'
    
    html += '</div>'
    
    # Score Section
    warnings_text = ' • '.join(assessment.warnings) if assessment.warnings else 'No warnings'
    html += f'''
    <div class="neo-card score-section">
        <div class="score-circle"><div class="score-value">{assessment.score}</div><div class="score-label">Score</div></div>
        <div class="score-info">
            <div class="score-rec">{assessment.recommendation} SIZE</div>
            <div style="font-size:16px;font-weight:700;margin-bottom:8px;">Day Assessment</div>
            <div class="score-warnings">{warnings_text}</div>
        </div>
    </div>
'''
    
    # Cones Table
    html += f'''
    <div class="section-header"><div class="section-title">Structural Cones @ 10:00 AM CT</div></div>
    <div class="neo-card"><table><thead><tr><th>Pivot</th><th>Ascending Rail</th><th>Descending Rail</th><th style="text-align:center;">Width</th><th style="text-align:center;">Blocks</th></tr></thead><tbody>
'''
    for cone in cones:
        wpill = 'pill-green' if cone.width >= 25 else 'pill-amber' if cone.width >= MIN_CONE_WIDTH else 'pill-red'
        html += f'<tr><td class="font-bold">{cone.name}</td><td class="mono text-red">{cone.ascending_rail:,.2f}</td><td class="mono text-green">{cone.descending_rail:,.2f}</td><td style="text-align:center;"><span class="pill {wpill}">{cone.width:.0f} pts</span></td><td class="mono text-muted" style="text-align:center;">{cone.blocks}</td></tr>'
    html += '</tbody></table></div>'
    
    # Trading day info
    if is_historical:
        date_badge = f'<span class="pill pill-amber" style="font-size:11px;">📅 Historical</span>'
    else:
        trading_label = get_trading_day_label()
        next_expiry = get_next_trading_day()
        date_badge = f'<span class="pill pill-neutral" style="font-size:11px;">0DTE {next_expiry.strftime("%b %d")} ({trading_label})</span>'
    
    # CALLS Setups
    calls_setups = [s for s in setups if s.direction == 'CALLS']
    if calls_setups:
        html += f'''
    <div class="section-header">
        <div class="section-title" style="color:{green};">▲ Calls Setups</div>
        <div style="display:flex;align-items:center;gap:12px;">{date_badge}<span style="font-size:11px;color:{text_light};">Enter at Descending Rail • OTM Strike Above Entry</span></div>
    </div>
    <div class="neo-card" style="overflow-x:auto;"><table><thead><tr><th>Cone</th><th>SPX Entry</th><th>Strike</th><th>Current / Est. Premium</th><th>Stop (pts/$)</th><th>T1 25%</th><th>T2 50%</th><th>T3 75%</th><th>R:R</th><th style="text-align:right;">Dist</th></tr></thead><tbody>
'''
        for s in calls_setups:
            row_class = 'row-active' if s.is_active and not is_historical else ''
            if is_historical:
                prem_html = f'<span class="text-muted" style="font-size:11px;">Historical</span>'
            elif s.current_option_price > 0 or s.est_entry_price_10am > 0:
                curr = f'${s.current_option_price:.1f}' if s.current_option_price > 0 else '—'
                est = f'${s.est_entry_price_10am:.1f}' if s.est_entry_price_10am > 0 else '—'
                prem_html = f'<div class="premium-cell"><span class="premium-current">Now: {curr}</span><span class="premium-est">Est: {est}</span></div>'
                if s.using_spy:
                    prem_html += f'<span style="font-size:9px;color:{text_light};">via SPY {s.spy_strike_used}C</span>'
            else:
                prem_html = '<span class="text-muted">—</span>'
            dpill = 'pill-green' if s.distance <= 5 else 'pill-amber' if s.distance <= 15 else 'pill-neutral'
            html += f'<tr class="{row_class}"><td class="font-bold">{s.cone_name}</td><td class="mono text-green">{s.entry:,.2f}</td><td class="mono">{s.strike}C</td><td>{prem_html}</td><td><span class="mono text-red">{s.stop:,.2f}</span><br><span style="font-size:11px;color:{red};">-${s.stop_loss_dollars:.0f}</span></td><td><span class="mono">{s.target_25:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t1_dollars:.0f}</span></td><td><span class="mono">{s.target_50:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t2_dollars:.0f}</span></td><td><span class="mono">{s.target_75:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t3_dollars:.0f}</span></td><td class="mono" style="color:{green};font-weight:700;">1:{s.rr_ratio:.1f}</td><td style="text-align:right;"><span class="pill {dpill}">{s.distance:.0f}</span></td></tr>'
        html += '</tbody></table></div>'
    
    # PUTS Setups
    puts_setups = [s for s in setups if s.direction == 'PUTS']
    if puts_setups:
        html += f'''
    <div class="section-header">
        <div class="section-title" style="color:{red};">▼ Puts Setups</div>
        <div style="display:flex;align-items:center;gap:12px;">{date_badge}<span style="font-size:11px;color:{text_light};">Enter at Ascending Rail • OTM Strike Below Entry</span></div>
    </div>
    <div class="neo-card" style="overflow-x:auto;"><table><thead><tr><th>Cone</th><th>SPX Entry</th><th>Strike</th><th>Current / Est. Premium</th><th>Stop (pts/$)</th><th>T1 25%</th><th>T2 50%</th><th>T3 75%</th><th>R:R</th><th style="text-align:right;">Dist</th></tr></thead><tbody>
'''
        for s in puts_setups:
            row_class = 'row-active' if s.is_active and not is_historical else ''
            if is_historical:
                prem_html = f'<span class="text-muted" style="font-size:11px;">Historical</span>'
            elif s.current_option_price > 0 or s.est_entry_price_10am > 0:
                curr = f'${s.current_option_price:.1f}' if s.current_option_price > 0 else '—'
                est = f'${s.est_entry_price_10am:.1f}' if s.est_entry_price_10am > 0 else '—'
                prem_html = f'<div class="premium-cell"><span class="premium-current">Now: {curr}</span><span class="premium-est">Est: {est}</span></div>'
                if s.using_spy:
                    prem_html += f'<span style="font-size:9px;color:{text_light};">via SPY {s.spy_strike_used}P</span>'
            else:
                prem_html = '<span class="text-muted">—</span>'
            dpill = 'pill-green' if s.distance <= 5 else 'pill-amber' if s.distance <= 15 else 'pill-neutral'
            html += f'<tr class="{row_class}"><td class="font-bold">{s.cone_name}</td><td class="mono text-red">{s.entry:,.2f}</td><td class="mono">{s.strike}P</td><td>{prem_html}</td><td><span class="mono text-green">{s.stop:,.2f}</span><br><span style="font-size:11px;color:{red};">-${s.stop_loss_dollars:.0f}</span></td><td><span class="mono">{s.target_25:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t1_dollars:.0f}</span></td><td><span class="mono">{s.target_50:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t2_dollars:.0f}</span></td><td><span class="mono">{s.target_75:,.2f}</span><br><span style="font-size:11px;color:{green};">+${s.reward_t3_dollars:.0f}</span></td><td class="mono" style="color:{green};font-weight:700;">1:{s.rr_ratio:.1f}</td><td style="text-align:right;"><span class="pill {dpill}">{s.distance:.0f}</span></td></tr>'
        html += '</tbody></table></div>'
    
    # Prior Session
    if prior:
        html += f'''
    <div class="section-header"><div class="section-title">Prior Session Reference</div></div>
    <div class="neo-card"><div class="data-grid">
        <div class="neo-inset data-cell"><div class="data-cell-label">High</div><div class="data-cell-value">{prior.get('high', 0):,.2f}</div></div>
        <div class="neo-inset data-cell"><div class="data-cell-label">Low</div><div class="data-cell-value">{prior.get('low', 0):,.2f}</div></div>
        <div class="neo-inset data-cell"><div class="data-cell-label">Close</div><div class="data-cell-value">{prior.get('close', 0):,.2f}</div></div>
        <div class="neo-inset data-cell"><div class="data-cell-label">Range</div><div class="data-cell-value">{prior.get('high', 0) - prior.get('low', 0):,.0f}</div></div>
    </div></div>
'''
    
    # Pivot Table
    if pivots:
        time_slots = []
        h, m = 9, 30
        while h < 16 or (h == 16 and m == 0):
            time_slots.append(f"{h}:{m:02d}")
            m += 30
            if m >= 60:
                m = 0
                h += 1
        
        html += f'''
    <div class="section-header" style="margin-top:32px;"><div class="section-title">📊 Pivot Table — All Entries by Time Block (CT)</div></div>
    <div class="neo-card" style="overflow-x:auto;"><table style="font-size:12px;"><thead><tr><th style="position:sticky;left:0;background:{bg};">Time CT</th>
'''
        for p in pivots:
            html += f'<th colspan="2" style="text-align:center;border-left:2px solid {shadow_dark};">{p.name}</th>'
        html += f'</tr><tr><th style="position:sticky;left:0;background:{bg};">Block</th>'
        for p in pivots:
            html += f'<th style="color:{green};text-align:center;border-left:2px solid {shadow_dark};">▲ Calls</th><th style="color:{red};text-align:center;">▼ Puts</th>'
        html += '</tr></thead><tbody>'
        
        for slot in time_slots:
            hr, mn = map(int, slot.split(':'))
            slot_time = CT_TZ.localize(datetime.combine(eval_date, time(hr, mn)))
            is_inst = (hr == 9 and mn >= 30) or (hr == 10 and mn == 0)
            row_style = f'background:linear-gradient(90deg, {amber}20, {amber}05);' if is_inst else ''
            row_mark = f'<span style="color:{amber};font-weight:700;">🏛️</span> ' if is_inst else ''
            
            html += f'<tr style="{row_style}"><td style="position:sticky;left:0;background:{card_bg if not is_inst else amber + "15"};font-weight:600;">{row_mark}{slot} CT</td>'
            
            for pivot in pivots:
                start_time = pivot.time + timedelta(minutes=30)
                if slot_time > start_time:
                    diff_sec = (slot_time - start_time).total_seconds()
                    blocks = max(int(diff_sec // 1800), 1)
                    asc = pivot.price_for_ascending + (blocks * SLOPE_PER_30MIN)
                    desc = pivot.price_for_descending - (blocks * SLOPE_PER_30MIN)
                    calls_e, puts_e = f'{desc:,.2f}', f'{asc:,.2f}'
                else:
                    calls_e, puts_e = '—', '—'
                html += f'<td class="mono" style="text-align:center;color:{green};border-left:2px solid {shadow_dark}40;">{calls_e}</td><td class="mono" style="text-align:center;color:{red};">{puts_e}</td>'
            html += '</tr>'
        
        html += f'</tbody></table><div style="margin-top:16px;padding:12px;background:{amber}15;border-radius:8px;border-left:4px solid {amber};"><span style="font-weight:600;color:{amber};">🏛️ Institutional Window (9:30-10:00 AM CT)</span><span style="color:{text_med};margin-left:12px;">Large institutions typically enter during this period.</span></div></div>'
    
    html += '</div></body></html>'
    return html

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet v5.1 Premium",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    defaults = {
        'use_manual_vix': False,
        'use_manual_pivots': False,
        'vix_bottom': 0.0,
        'vix_top': 0.0,
        'vix_current': 0.0,
        'manual_high_wick': 0.0,
        'manual_high_time': "10:30",
        'manual_low_close': 0.0,
        'manual_low_time': "14:00",
        'manual_close': 0.0,
        'use_secondary_high': False,
        'secondary_high_wick': 0.0,
        'secondary_high_time': "14:30",
        'use_secondary_low': False,
        'secondary_low_close': 0.0,
        'secondary_low_time': "11:00",
        'fetch_options': True,
        'selected_date': None,
        'use_historical': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        st.markdown("### 📅 Trading Date")
        today = get_ct_now().date()
        next_trading = get_next_trading_day().date()
        
        date_mode = st.radio(
            "Select Mode",
            ["Live / Next Trading Day", "Historical Date"],
            index=1 if st.session_state.use_historical else 0,
            horizontal=True
        )
        
        st.session_state.use_historical = (date_mode == "Historical Date")
        
        if st.session_state.use_historical:
            selected = st.date_input(
                "Select Date",
                value=st.session_state.selected_date or today - timedelta(days=1),
                max_value=today,
                min_value=today - timedelta(days=365)
            )
            st.session_state.selected_date = selected
            if selected.weekday() >= 5:
                st.warning(f"⚠️ {selected.strftime('%A, %b %d')} is a weekend")
            else:
                st.info(f"📊 Showing data for **{selected.strftime('%A, %b %d, %Y')}**")
        else:
            trading_label = get_trading_day_label()
            st.info(f"📊 **{trading_label}** ({next_trading.strftime('%b %d, %Y')})")
            st.session_state.selected_date = None
        
        st.markdown("---")
        
        st.markdown("### 📊 VIX Zone")
        use_manual_vix = st.checkbox("Manual VIX Override", value=st.session_state.use_manual_vix)
        st.session_state.use_manual_vix = use_manual_vix
        
        if use_manual_vix:
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.vix_bottom = st.number_input("VIX Bottom", value=st.session_state.vix_bottom, step=0.01, format="%.2f")
            with col2:
                st.session_state.vix_top = st.number_input("VIX Top", value=st.session_state.vix_top, step=0.01, format="%.2f")
        
        st.markdown("### 📍 Prior Day Pivots")
        use_manual_pivots = st.checkbox("Manual Pivot Override", value=st.session_state.use_manual_pivots)
        st.session_state.use_manual_pivots = use_manual_pivots
        
        if use_manual_pivots:
            st.markdown("##### Primary Pivots")
            st.markdown("**High Cone** (highest wick)")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.session_state.manual_high_wick = st.number_input("Highest Wick", value=st.session_state.manual_high_wick, step=0.01, format="%.2f", key="high_wick")
            with col2:
                st.session_state.manual_high_time = st.text_input("Time CT (HH:MM)", value=st.session_state.manual_high_time, key="high_time")
            
            st.markdown("**Low Cone** (lowest close)")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.session_state.manual_low_close = st.number_input("Lowest Close", value=st.session_state.manual_low_close, step=0.01, format="%.2f", key="low_close")
            with col2:
                st.session_state.manual_low_time = st.text_input("Time CT (HH:MM)", value=st.session_state.manual_low_time, key="low_time")
            
            st.session_state.manual_close = st.number_input("Prior Close", value=st.session_state.manual_close, step=0.01, format="%.2f")
            
            st.markdown("---")
            st.markdown("##### Secondary Pivots (Optional)")
            
            st.session_state.use_secondary_high = st.checkbox("Enable Secondary High", value=st.session_state.use_secondary_high)
            if st.session_state.use_secondary_high:
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.session_state.secondary_high_wick = st.number_input("2nd High Wick", value=st.session_state.secondary_high_wick, step=0.01, format="%.2f", key="sec_high_wick")
                with col2:
                    st.session_state.secondary_high_time = st.text_input("Time CT", value=st.session_state.secondary_high_time, key="sec_high_time")
            
            st.session_state.use_secondary_low = st.checkbox("Enable Secondary Low", value=st.session_state.use_secondary_low)
            if st.session_state.use_secondary_low:
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.session_state.secondary_low_close = st.number_input("2nd Low Close", value=st.session_state.secondary_low_close, step=0.01, format="%.2f", key="sec_low_close")
                with col2:
                    st.session_state.secondary_low_time = st.text_input("Time CT", value=st.session_state.secondary_low_time, key="sec_low_time")
        
        st.markdown("### 💰 Options")
        st.session_state.fetch_options = st.checkbox("Fetch Live Option Prices", value=st.session_state.fetch_options)
        
        st.markdown("---")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # ========================================================================
    # DATA FETCHING AND PROCESSING
    # ========================================================================
    
    is_historical = st.session_state.use_historical and st.session_state.selected_date is not None
    selected_date = st.session_state.selected_date
    
    polygon_status = PolygonStatus()
    es_data = ESData()
    vix_auto = False
    vix_bottom = 0.0
    vix_top = 0.0
    current_spx = 0.0
    current_vix = 0.0
    prior_data = {}
    trading_date = None
    pivot_date = None
    
    if is_historical:
        # ====================================================================
        # HISTORICAL MODE
        # ====================================================================
        # selected_date = the day we want to analyze (e.g., Dec 19, 2025)
        # pivot_date = the day BEFORE selected_date (e.g., Dec 18, 2025)
        # prior_data = OHLC from pivot_date
        # current_spx/vix = closing values from selected_date
        
        trading_date = selected_date
        
        # Get the prior trading day (skip weekends)
        pivot_date = selected_date - timedelta(days=1)
        while pivot_date.weekday() >= 5:
            pivot_date -= timedelta(days=1)
        
        # Fetch selected day's data (for "current" price - the close)
        historical_spx = fetch_historical_day_data("^GSPC", datetime.combine(selected_date, time(0, 0)))
        historical_vix = fetch_historical_day_data("^VIX", datetime.combine(selected_date, time(0, 0)))
        
        current_spx = historical_spx.get('close', 0)
        current_vix = historical_vix.get('close', 0)
        
        if current_spx > 0:
            polygon_status.connected = True
            polygon_status.spx_price = current_spx
            polygon_status.vix_price = current_vix
        
        # Fetch prior day's data (for pivots)
        prior_data = fetch_historical_day_data("^GSPC", datetime.combine(pivot_date, time(0, 0)))
        if prior_data.get('high', 0) == 0:
            prior_data = {'high': current_spx + 20, 'low': current_spx - 20, 'close': current_spx, 'open': current_spx}
        
        # VIX zone for historical - use selected day's VIX range
        vix_low = historical_vix.get('low', current_vix)
        vix_high = historical_vix.get('high', current_vix)
        if vix_high > vix_low and vix_low > 0:
            vix_bottom = vix_low
            vix_top = vix_high
        else:
            vix_bottom = current_vix - 0.15
            vix_top = current_vix + 0.15
        
    else:
        # ====================================================================
        # LIVE MODE
        # ====================================================================
        trading_date = get_ct_now().date()
        
        # Get the prior trading day (skip weekends)
        pivot_date = trading_date - timedelta(days=1)
        while pivot_date.weekday() >= 5:
            pivot_date -= timedelta(days=1)
        
        # Fetch current SPX
        spx_snapshot = polygon_get_snapshot(POLYGON_SPX) if POLYGON_HAS_INDICES else None
        if spx_snapshot and spx_snapshot.get('price', 0) > 0:
            current_spx = spx_snapshot['price']
            polygon_status.connected = True
            polygon_status.spx_price = current_spx
        else:
            current_spx = yf_fetch_current_spx()
        
        # Fetch current VIX
        vix_snapshot = polygon_get_snapshot(POLYGON_VIX) if POLYGON_HAS_INDICES else None
        if vix_snapshot and vix_snapshot.get('price', 0) > 0:
            current_vix = vix_snapshot['price']
            polygon_status.vix_price = current_vix
        else:
            current_vix = yf_fetch_current_vix()
        
        # Fetch prior day data
        prior_data = polygon_get_prior_day_data(POLYGON_SPX) if POLYGON_HAS_INDICES else None
        if not prior_data or prior_data.get('high', 0) == 0:
            prior_data = {'high': current_spx + 20, 'low': current_spx - 20, 'close': current_spx, 'open': current_spx}
        
        # VIX zone for live - use overnight range
        overnight = polygon_get_overnight_vix_range(get_ct_now()) if POLYGON_HAS_INDICES else None
        if overnight and overnight.get('bottom', 0) > 0:
            vix_bottom = overnight['bottom']
            vix_top = overnight['top']
            vix_auto = True
        else:
            vix_bottom = current_vix - 0.15
            vix_top = current_vix + 0.15
        
        # Fetch ES futures
        es_raw = yf_fetch_es_futures()
    
    # Manual VIX override (applies to both modes)
    if st.session_state.use_manual_vix and st.session_state.vix_bottom > 0 and st.session_state.vix_top > 0:
        vix_bottom = st.session_state.vix_bottom
        vix_top = st.session_state.vix_top
        vix_auto = False
    
    # Build VIX zone
    vix_zone = analyze_vix_zone(current_vix, vix_bottom, vix_top)
    vix_zone.auto_detected = vix_auto
    
    # Analyze ES data (live mode only)
    if not is_historical:
        es_data = analyze_es_data(es_raw, current_spx, vix_zone)
    
    # ========================================================================
    # BUILD PIVOTS
    # ========================================================================
    
    if st.session_state.use_manual_pivots and st.session_state.manual_high_wick > 0:
        # Manual pivots
        pivots = []
        
        h_parts = st.session_state.manual_high_time.split(':')
        high_time = CT_TZ.localize(datetime.combine(pivot_date, time(int(h_parts[0]), int(h_parts[1]))))
        pivots.append(Pivot(price=st.session_state.manual_high_wick, time=high_time, name="Prior High"))
        
        l_parts = st.session_state.manual_low_time.split(':')
        low_time = CT_TZ.localize(datetime.combine(pivot_date, time(int(l_parts[0]), int(l_parts[1]))))
        pivots.append(Pivot(price=st.session_state.manual_low_close, time=low_time, name="Prior Low"))
        
        pivots.append(Pivot(price=st.session_state.manual_close, time=CT_TZ.localize(datetime.combine(pivot_date, time(16, 0))), name="Prior Close"))
        
        if st.session_state.use_secondary_high and st.session_state.secondary_high_wick > 0:
            sh_parts = st.session_state.secondary_high_time.split(':')
            sec_high_time = CT_TZ.localize(datetime.combine(pivot_date, time(int(sh_parts[0]), int(sh_parts[1]))))
            pivots.append(Pivot(price=st.session_state.secondary_high_wick, time=sec_high_time, name="2nd High"))
        
        if st.session_state.use_secondary_low and st.session_state.secondary_low_close > 0:
            sl_parts = st.session_state.secondary_low_time.split(':')
            sec_low_time = CT_TZ.localize(datetime.combine(pivot_date, time(int(sl_parts[0]), int(sl_parts[1]))))
            pivots.append(Pivot(price=st.session_state.secondary_low_close, time=sec_low_time, name="2nd Low"))
    else:
        # Auto pivots from prior_data
        pivots = [
            Pivot(price=prior_data['high'], time=CT_TZ.localize(datetime.combine(pivot_date, time(10, 30))), name="Prior High"),
            Pivot(price=prior_data['low'], time=CT_TZ.localize(datetime.combine(pivot_date, time(14, 0))), name="Prior Low"),
            Pivot(price=prior_data['close'], time=CT_TZ.localize(datetime.combine(pivot_date, time(16, 0))), name="Prior Close")
        ]
    
    # ========================================================================
    # BUILD CONES AND SETUPS
    # ========================================================================
    
    # Build cones at 10:00 AM CT of the TRADING day
    eval_10am = CT_TZ.localize(datetime.combine(trading_date, time(10, 0)))
    cones = build_cones(pivots, eval_10am)
    
    # Generate setups
    setups = generate_setups(cones, current_spx, vix_zone.bias)
    
    # Fetch options pricing (live mode only)
    if st.session_state.fetch_options and not is_historical:
        with st.spinner("Fetching live options prices..."):
            for i, setup in enumerate(setups):
                setups[i] = get_option_pricing_for_setup(setup, current_spx)
    
    # Get cone info
    active_cone_info = find_active_cone(current_spx, cones)
    detailed_cone = get_detailed_active_cone(current_spx, cones)
    
    # Day assessment
    assessment = assess_day(vix_zone, cones)
    
    # ========================================================================
    # RENDER DASHBOARD
    # ========================================================================
    
    dashboard_html = render_neomorphic_dashboard(
        spx=current_spx,
        vix=vix_zone,
        cones=cones,
        setups=setups,
        assessment=assessment,
        prior=prior_data,
        active_cone_info=active_cone_info,
        polygon_status=polygon_status,
        pivots=pivots,
        es_data=es_data,
        detailed_cone=detailed_cone,
        trading_date=trading_date,
        is_historical=is_historical
    )
    
    components.html(dashboard_html, height=3200, scrolling=True)


if __name__ == "__main__":
    main()