"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ███████╗██████╗ ██╗  ██╗    ██████╗ ██████╗  ██████╗ ██████╗ ██╗  ██╗███████╗████████╗
║   ██╔════╝██╔══██╗╚██╗██╔╝    ██╔══██╗██╔══██╗██╔═══██╗██╔══██╗██║  ██║██╔════╝╚══██╔══╝
║   ███████╗██████╔╝ ╚███╔╝     ██████╔╝██████╔╝██║   ██║██████╔╝███████║█████╗     ██║   
║   ╚════██║██╔═══╝  ██╔██╗     ██╔═══╝ ██╔══██╗██║   ██║██╔═══╝ ██╔══██║██╔══╝     ██║   
║   ███████║██║     ██╔╝ ██╗    ██║     ██║  ██║╚██████╔╝██║     ██║  ██║███████╗   ██║   
║   ╚══════╝╚═╝     ╚═╝  ╚═╝    ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝  ╚═╝╚══════╝   ╚═╝   
║                                                                               ║
║                    "Where Structure Becomes Foresight"                        ║
║                              Version 6.1 Legendary                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import numpy as np
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import pytz
import json

# =============================================================================
# CONFIGURATION
# =============================================================================

POLYGON_API_KEY = "jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm"
POLYGON_BASE_URL = "https://api.polygon.io"

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

# Trading Constants
SLOPE_PER_30MIN = 0.45
MIN_CONE_WIDTH = 18.0
STOP_LOSS_PTS = 6.0
RAIL_PROXIMITY = 5.0

# Premium Preferences (SPY prices)
PREMIUM_MIN = 3.50
PREMIUM_SWEET_LOW = 4.00
PREMIUM_SWEET_HIGH = 7.00
PREMIUM_MAX = 8.00

# Delta Range
DELTA_TARGET_LOW = 0.28
DELTA_TARGET_HIGH = 0.38
DELTA_IDEAL = 0.33

# VIX to SPX Move: Expected SPX Move = Zone Size × 175
VIX_TO_SPX_MULTIPLIER = 175

# Time Windows (CT)
PREMARKET_START = time(8, 30)
RTH_OPEN = time(9, 30)
INST_WINDOW_START = time(9, 0)
INST_WINDOW_END = time(9, 30)
ENTRY_TARGET = time(9, 10)
CUTOFF_TIME = time(11, 30)
REGULAR_CLOSE = time(16, 0)
HALF_DAY_CLOSE = time(12, 0)

# 2025 Holidays (Full Close)
HOLIDAYS_2025 = {
    date(2025, 1, 1): "New Year's Day",
    date(2025, 1, 20): "MLK Day",
    date(2025, 2, 17): "Presidents Day",
    date(2025, 4, 18): "Good Friday",
    date(2025, 5, 26): "Memorial Day",
    date(2025, 6, 19): "Juneteenth",
    date(2025, 7, 4): "Independence Day",
    date(2025, 9, 1): "Labor Day",
    date(2025, 11, 27): "Thanksgiving",
    date(2025, 12, 25): "Christmas",
}

# 2025 Half Days (12:00 PM CT Close)
HALF_DAYS_2025 = {
    date(2025, 7, 3): "Day before July 4th",
    date(2025, 11, 26): "Day before Thanksgiving",
    date(2025, 12, 24): "Christmas Eve",
}

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VIXZone:
    bottom: float = 0.0
    top: float = 0.0
    current: float = 0.0
    zone_size: float = 0.0
    position_pct: float = 50.0
    zones_away: int = 0
    expected_spx_move: float = 0.0
    bias: str = "WAIT"
    bias_reason: str = ""
    return_level: float = 0.0
    matched_rail: float = 0.0
    matched_cone: str = ""

@dataclass
class Pivot:
    name: str = ""
    price: float = 0.0
    pivot_time: datetime = None
    pivot_type: str = ""  # HIGH, LOW, CLOSE
    is_secondary: bool = False
    candle_high: float = 0.0
    candle_open: float = 0.0

@dataclass
class Cone:
    name: str = ""
    pivot: Pivot = None
    ascending_rail: float = 0.0
    descending_rail: float = 0.0
    width: float = 0.0
    blocks: int = 0
    is_tradeable: bool = True

@dataclass
class OptionQuote:
    ticker: str = ""
    underlying: str = ""
    strike: float = 0.0
    option_type: str = ""
    expiry: date = None
    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    iv: float = 0.0
    open_interest: int = 0
    volume: int = 0
    in_sweet_spot: bool = False
    spx_strike: int = 0
    spx_premium_adj: float = 0.0
    spx_premium_x10: float = 0.0

@dataclass
class TradeSetup:
    direction: str = ""
    cone_name: str = ""
    cone_width: float = 0.0
    entry: float = 0.0
    stop: float = 0.0
    target_25: float = 0.0
    target_50: float = 0.0
    target_75: float = 0.0
    distance: float = 0.0
    is_active: bool = False
    spy_option: OptionQuote = None
    spx_strike: int = 0
    spx_premium_adj: float = 0.0
    spx_premium_x10: float = 0.0
    risk_dollars: float = 0.0
    reward_50_dollars: float = 0.0
    rr_ratio: float = 0.0
    status: str = "WAIT"

@dataclass
class DayScore:
    total: int = 0
    vix_cone_alignment: int = 0
    vix_clarity: int = 0
    cone_width: int = 0
    premium_quality: int = 0
    confluence: int = 0
    grade: str = ""
    color: str = ""

@dataclass
class PivotTableRow:
    time_block: str = ""
    time_ct: time = None
    prior_high_asc: float = 0.0
    prior_high_desc: float = 0.0
    prior_low_asc: float = 0.0
    prior_low_desc: float = 0.0
    prior_close_asc: float = 0.0
    prior_close_desc: float = 0.0

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_ct_now() -> datetime:
    return datetime.now(CT_TZ)

def is_holiday(d: date) -> bool:
    return d in HOLIDAYS_2025

def is_half_day(d: date) -> bool:
    return d in HALF_DAYS_2025

def get_market_close_time(d: date) -> time:
    if is_half_day(d):
        return HALF_DAY_CLOSE
    return REGULAR_CLOSE

def get_next_trading_day(from_date: date = None) -> date:
    if from_date is None:
        now = get_ct_now()
        from_date = now.date()
        # If after market close, start from tomorrow
        if now.time() > get_market_close_time(from_date):
            from_date += timedelta(days=1)
    
    next_day = from_date
    while next_day.weekday() >= 5 or is_holiday(next_day):
        next_day += timedelta(days=1)
    return next_day

def get_prior_trading_day(from_date: date) -> date:
    prior = from_date - timedelta(days=1)
    while prior.weekday() >= 5 or is_holiday(prior):
        prior -= timedelta(days=1)
    return prior

def format_currency(value: float) -> str:
    if value == 0:
        return "--"
    return f"${value:,.2f}"

def format_price(value: float) -> str:
    if value == 0:
        return "--"
    return f"{value:,.2f}"

def calculate_expected_spx_move(zone_size: float) -> float:
    return zone_size * VIX_TO_SPX_MULTIPLIER

def get_time_until(target: time, from_dt: datetime = None) -> timedelta:
    if from_dt is None:
        from_dt = get_ct_now()
    target_dt = CT_TZ.localize(datetime.combine(from_dt.date(), target))
    if target_dt < from_dt:
        return timedelta(0)
    return target_dt - from_dt

def format_countdown(td: timedelta) -> str:
    if td.total_seconds() <= 0:
        return "NOW"
    total_secs = int(td.total_seconds())
    hours, remainder = divmod(total_secs, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


# =============================================================================
# POLYGON API FUNCTIONS
# =============================================================================

def polygon_request(endpoint: str, params: dict = None) -> Optional[Dict]:
    """Generic Polygon API request handler"""
    try:
        if params is None:
            params = {}
        params["apiKey"] = POLYGON_API_KEY
        url = f"{POLYGON_BASE_URL}{endpoint}"
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return None

def polygon_get_index_price(ticker: str) -> float:
    """Get index price (SPX, VIX)"""
    data = polygon_request(f"/v3/snapshot", {"ticker.any_of": ticker})
    if data and data.get("results"):
        return data["results"][0].get("value", 0)
    return 0.0

def polygon_get_stock_price(ticker: str) -> float:
    """Get stock price (SPY, ES)"""
    data = polygon_request(f"/v2/aggs/ticker/{ticker}/prev")
    if data and data.get("results"):
        return data["results"][0].get("c", 0)
    return 0.0

def polygon_get_daily_bars(ticker: str, from_date: date, to_date: date) -> List[Dict]:
    """Get daily OHLC bars"""
    data = polygon_request(
        f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}",
        {"adjusted": "true", "sort": "asc"}
    )
    if data:
        return data.get("results", [])
    return []

def polygon_get_intraday_bars(ticker: str, from_date: date, to_date: date, multiplier: int = 30) -> List[Dict]:
    """Get intraday bars (30-min default)"""
    data = polygon_request(
        f"/v2/aggs/ticker/{ticker}/range/{multiplier}/minute/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}",
        {"adjusted": "true", "sort": "asc", "limit": 5000}
    )
    if data:
        return data.get("results", [])
    return []

def polygon_get_options_contracts(underlying: str, expiry: date, strike_min: float = None, strike_max: float = None) -> List[Dict]:
    """Get options contracts for underlying"""
    params = {
        "underlying_ticker": underlying,
        "expiration_date": expiry.strftime("%Y-%m-%d"),
        "limit": 250
    }
    if strike_min:
        params["strike_price.gte"] = strike_min
    if strike_max:
        params["strike_price.lte"] = strike_max
    
    data = polygon_request("/v3/reference/options/contracts", params)
    if data:
        return data.get("results", [])
    return []

def polygon_get_option_snapshot(ticker: str) -> Optional[Dict]:
    """Get option snapshot with greeks"""
    data = polygon_request(f"/v3/snapshot/options/{ticker}")
    if data:
        return data.get("results")
    return None

def polygon_get_option_quote(ticker: str) -> Optional[Dict]:
    """Get latest option quote"""
    data = polygon_request(f"/v3/quotes/{ticker}", {"limit": 1})
    if data and data.get("results"):
        return data["results"][0]
    return None

def build_option_ticker(underlying: str, expiry: date, strike: float, opt_type: str) -> str:
    """Build Polygon option ticker: O:SPY251226C00605000"""
    date_str = expiry.strftime("%y%m%d")
    cp = "C" if opt_type.upper() in ["C", "CALL", "CALLS"] else "P"
    strike_int = int(strike * 1000)
    return f"O:{underlying}{date_str}{cp}{strike_int:08d}"

def get_spy_option_data(spx_entry: float, opt_type: str, expiry: date) -> Optional[OptionQuote]:
    """
    Get SPY option data and calculate SPX equivalent premiums.
    Uses delta-matched OTM distance ratio for SPX estimate.
    """
    # Calculate SPY equivalent level
    spy_level = spx_entry / 10
    
    # Determine OTM strike (2 strikes away like in example)
    if opt_type.upper() in ["C", "CALL", "CALLS"]:
        # For calls: strike above entry
        spy_strike = round(spy_level) + 2  # 2 strikes OTM ($1 increments)
        spx_strike = int(round(spx_entry / 5) * 5) + 10  # 2 strikes OTM ($5 increments)
    else:
        # For puts: strike below entry  
        spy_strike = round(spy_level) - 2
        spx_strike = int(round(spx_entry / 5) * 5) - 10
    
    # Build ticker and get data
    ticker = build_option_ticker("SPY", expiry, spy_strike, opt_type)
    
    # Try snapshot first (has greeks)
    snapshot = polygon_get_option_snapshot(ticker)
    
    bid, ask, mid = 0, 0, 0
    delta, gamma, theta, vega, iv = 0, 0, 0, 0, 0
    oi, volume = 0, 0
    
    if snapshot:
        greeks = snapshot.get("greeks", {})
        day = snapshot.get("day", {})
        last_quote = snapshot.get("last_quote", {})
        
        delta = greeks.get("delta", 0)
        gamma = greeks.get("gamma", 0)
        theta = greeks.get("theta", 0)
        vega = greeks.get("vega", 0)
        iv = snapshot.get("implied_volatility", 0)
        oi = snapshot.get("open_interest", 0)
        volume = day.get("volume", 0)
        
        bid = last_quote.get("bid", 0) or day.get("close", 0)
        ask = last_quote.get("ask", 0) or day.get("close", 0)
        mid = (bid + ask) / 2 if bid and ask else day.get("close", 0)
    
    # Fallback to quote endpoint
    if mid == 0:
        quote = polygon_get_option_quote(ticker)
        if quote:
            bid = quote.get("bid_price", 0)
            ask = quote.get("ask_price", 0)
            mid = (bid + ask) / 2 if bid and ask else 0
    
    if mid == 0:
        return None
    
    # Calculate SPX equivalent premiums
    # Method 1: OTM distance ratio
    spy_otm_distance = abs(spy_strike - spy_level)
    spx_otm_distance = abs(spx_strike - spx_entry)
    if spy_otm_distance > 0:
        multiplier = spx_otm_distance / spy_otm_distance
    else:
        multiplier = 10
    
    spx_premium_adj = mid * multiplier
    spx_premium_x10 = mid * 10
    
    # Check sweet spot
    in_sweet_spot = PREMIUM_SWEET_LOW <= mid <= PREMIUM_SWEET_HIGH
    
    return OptionQuote(
        ticker=ticker,
        underlying="SPY",
        strike=spy_strike,
        option_type=opt_type[0].upper(),
        expiry=expiry,
        bid=bid,
        ask=ask,
        mid=mid,
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        iv=iv,
        open_interest=oi,
        volume=volume,
        in_sweet_spot=in_sweet_spot,
        spx_strike=spx_strike,
        spx_premium_adj=round(spx_premium_adj, 2),
        spx_premium_x10=round(spx_premium_x10, 2)
    )

def get_open_interest_levels(expiry: date, spy_price: float) -> List[Dict]:
    """Get high OI strikes as magnet levels"""
    contracts = polygon_get_options_contracts("SPY", expiry, spy_price - 15, spy_price + 15)
    
    if not contracts:
        return []
    
    oi_levels = []
    for contract in contracts[:50]:
        ticker = contract.get("ticker")
        snapshot = polygon_get_option_snapshot(ticker)
        if snapshot:
            oi = snapshot.get("open_interest", 0)
            if oi > 5000:
                oi_levels.append({
                    "spy_strike": contract.get("strike_price", 0),
                    "spx_equiv": contract.get("strike_price", 0) * 10,
                    "type": contract.get("contract_type", ""),
                    "oi": oi
                })
    
    oi_levels.sort(key=lambda x: x["oi"], reverse=True)
    return oi_levels[:10]

def get_es_overnight_data() -> Dict:
    """Get ES futures overnight data for SPX offset calculation"""
    # ES futures trade nearly 24 hours
    # We want: prior close (4pm CT) vs current/overnight level
    
    es_price = polygon_get_stock_price("ES=F")  # May need adjustment for Polygon ticker
    
    # Try alternative: use /ES mini futures
    if es_price == 0:
        # Fallback: estimate from SPY after-hours or just return empty
        return {"es_price": 0, "es_change": 0, "spx_offset": 0}
    
    return {
        "es_price": es_price,
        "es_change": 0,  # Would need prior close to calculate
        "spx_offset": 0
    }


# =============================================================================
# VIX ZONE ANALYSIS
# =============================================================================

def analyze_vix_zone(vix_bottom: float, vix_top: float, vix_current: float, cones: List[Cone] = None) -> VIXZone:
    """Analyze VIX position and determine bias with cone matching"""
    
    zone = VIXZone(bottom=vix_bottom, top=vix_top, current=vix_current)
    
    if vix_bottom <= 0 or vix_top <= 0:
        zone.bias = "WAIT"
        zone.bias_reason = "VIX zone not set"
        return zone
    
    zone.zone_size = round(vix_top - vix_bottom, 2)
    zone.expected_spx_move = calculate_expected_spx_move(zone.zone_size)
    
    # Position relative to zone
    if vix_current < vix_bottom:
        zones_below = (vix_bottom - vix_current) / zone.zone_size if zone.zone_size > 0 else 0
        zone.zones_away = -int(np.ceil(zones_below))
        zone.position_pct = 0
        zone.return_level = vix_bottom
        zone.bias = "CALLS"
        zone.bias_reason = f"VIX {abs(zone.zones_away)} zone(s) below → will return to {vix_bottom:.2f} → SPX UP"
        
    elif vix_current > vix_top:
        zones_above = (vix_current - vix_top) / zone.zone_size if zone.zone_size > 0 else 0
        zone.zones_away = int(np.ceil(zones_above))
        zone.position_pct = 100
        zone.return_level = vix_top
        zone.bias = "PUTS"
        zone.bias_reason = f"VIX {zone.zones_away} zone(s) above → will return to {vix_top:.2f} → SPX DOWN"
        
    else:
        zone.zones_away = 0
        zone.position_pct = ((vix_current - vix_bottom) / zone.zone_size * 100) if zone.zone_size > 0 else 50
        
        if zone.position_pct >= 75:
            zone.bias = "CALLS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (top 25%) → expect fall → SPX UP"
            zone.return_level = vix_top
        elif zone.position_pct <= 25:
            zone.bias = "PUTS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (bottom 25%) → expect rise → SPX DOWN"
            zone.return_level = vix_bottom
        else:
            zone.bias = "WAIT"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (middle) → no clear edge"
            zone.return_level = (vix_top + vix_bottom) / 2
    
    # Match VIX bias to closest cone rail (CRITICAL FEATURE)
    if cones and zone.bias in ["CALLS", "PUTS"]:
        target_rails = []
        for cone in cones:
            if not cone.is_tradeable:
                continue
            if zone.bias == "CALLS":
                # CALLS = enter at descending rail
                target_rails.append((cone.descending_rail, cone.name))
            else:
                # PUTS = enter at ascending rail
                target_rails.append((cone.ascending_rail, cone.name))
        
        if target_rails:
            # Find closest rail by proximity
            # We'll use the first cone's current price estimate or just pick closest
            sorted_rails = sorted(target_rails, key=lambda x: x[0])
            # Pick middle one as likely target (could be refined)
            mid_idx = len(sorted_rails) // 2
            zone.matched_rail = sorted_rails[mid_idx][0]
            zone.matched_cone = sorted_rails[mid_idx][1]
    
    return zone

def get_vix_extensions(zone: VIXZone, num_ext: int = 4) -> Dict:
    """Calculate VIX zone extensions"""
    if zone.zone_size <= 0:
        return {"above": [], "below": [], "zone": {}}
    
    extensions = {
        "above": [],
        "below": [],
        "zone": {"bottom": zone.bottom, "top": zone.top}
    }
    
    for i in range(1, num_ext + 1):
        extensions["above"].append({
            "level": i,
            "bottom": round(zone.top + (i-1) * zone.zone_size, 2),
            "top": round(zone.top + i * zone.zone_size, 2)
        })
        extensions["below"].append({
            "level": -i,
            "top": round(zone.bottom - (i-1) * zone.zone_size, 2),
            "bottom": round(zone.bottom - i * zone.zone_size, 2)
        })
    
    return extensions

# =============================================================================
# PIVOT DETECTION AND CONE BUILDING
# =============================================================================

def detect_pivots_auto(bars: List[Dict], pivot_date: date, close_time: time) -> List[Pivot]:
    """
    Auto-detect pivots from 30-min candles.
    HIGH pivot: Green candle followed by red that breaks below green's open (use HIGH of green)
    LOW pivot: Red candle followed by green that breaks above red's open (use OPEN of green)
    """
    if not bars or len(bars) < 3:
        return []
    
    pivots = []
    candles = []
    
    for bar in bars:
        ts = bar.get("t", 0)
        if isinstance(ts, int):
            dt = datetime.fromtimestamp(ts / 1000, tz=ET_TZ).astimezone(CT_TZ)
        else:
            dt = ts
        candles.append({
            "time": dt,
            "open": bar.get("o", 0),
            "high": bar.get("h", 0),
            "low": bar.get("l", 0),
            "close": bar.get("c", 0),
            "is_green": bar.get("c", 0) >= bar.get("o", 0)
        })
    
    # Find HIGH pivots
    high_candidates = []
    for i in range(len(candles) - 1):
        curr, next_c = candles[i], candles[i + 1]
        if curr["is_green"] and not next_c["is_green"]:
            if next_c["close"] < curr["open"]:
                high_candidates.append({
                    "price": curr["high"],  # Highest wick
                    "time": curr["time"],
                    "candle_high": curr["high"]
                })
    
    # Find LOW pivots  
    low_candidates = []
    for i in range(len(candles) - 1):
        curr, next_c = candles[i], candles[i + 1]
        if not curr["is_green"] and next_c["is_green"]:
            if next_c["close"] > curr["open"]:
                low_candidates.append({
                    "price": next_c["open"],  # Open of bullish candle AFTER
                    "time": curr["time"],
                    "candle_open": next_c["open"]
                })
    
    # Primary HIGH (highest)
    if high_candidates:
        high_candidates.sort(key=lambda x: x["price"], reverse=True)
        h = high_candidates[0]
        pivots.append(Pivot(
            name="Prior High",
            price=h["price"],
            pivot_time=h["time"],
            pivot_type="HIGH",
            is_secondary=False,
            candle_high=h["candle_high"]
        ))
        # Secondary highs (up to 3 total)
        for i, h in enumerate(high_candidates[1:3], 1):
            pivots.append(Pivot(
                name=f"High {i+1}",
                price=h["price"],
                pivot_time=h["time"],
                pivot_type="HIGH",
                is_secondary=True,
                candle_high=h["candle_high"]
            ))
    
    # Primary LOW (lowest)
    if low_candidates:
        low_candidates.sort(key=lambda x: x["price"])
        l = low_candidates[0]
        pivots.append(Pivot(
            name="Prior Low",
            price=l["price"],
            pivot_time=l["time"],
            pivot_type="LOW",
            is_secondary=False,
            candle_open=l["candle_open"]
        ))
        for i, l in enumerate(low_candidates[1:3], 1):
            pivots.append(Pivot(
                name=f"Low {i+1}",
                price=l["price"],
                pivot_time=l["time"],
                pivot_type="LOW",
                is_secondary=True,
                candle_open=l["candle_open"]
            ))
    
    # CLOSE pivot (last candle's close at market close time)
    if candles:
        last = candles[-1]
        pivots.append(Pivot(
            name="Prior Close",
            price=last["close"],
            pivot_time=CT_TZ.localize(datetime.combine(pivot_date, close_time)),
            pivot_type="CLOSE",
            is_secondary=False
        ))
    
    return pivots

def create_manual_pivots(
    high_price: float, high_time_str: str,
    low_price: float, low_time_str: str,
    close_price: float,
    pivot_date: date,
    close_time: time,
    secondary_highs: List[Tuple[float, str]] = None,
    secondary_lows: List[Tuple[float, str]] = None
) -> List[Pivot]:
    """Create pivots from manual inputs"""
    
    def parse_time(time_str: str) -> time:
        try:
            parts = time_str.replace(" ", "").split(":")
            return time(int(parts[0]), int(parts[1]))
        except:
            return time(12, 0)
    
    pivots = []
    
    if high_price > 0:
        ht = parse_time(high_time_str)
        pivots.append(Pivot(
            name="Prior High",
            price=high_price,
            pivot_time=CT_TZ.localize(datetime.combine(pivot_date, ht)),
            pivot_type="HIGH",
            is_secondary=False,
            candle_high=high_price
        ))
    
    if low_price > 0:
        lt = parse_time(low_time_str)
        pivots.append(Pivot(
            name="Prior Low",
            price=low_price,
            pivot_time=CT_TZ.localize(datetime.combine(pivot_date, lt)),
            pivot_type="LOW",
            is_secondary=False,
            candle_open=low_price
        ))
    
    if close_price > 0:
        pivots.append(Pivot(
            name="Prior Close",
            price=close_price,
            pivot_time=CT_TZ.localize(datetime.combine(pivot_date, close_time)),
            pivot_type="CLOSE",
            is_secondary=False
        ))
    
    if secondary_highs:
        for i, (price, time_str) in enumerate(secondary_highs, 1):
            if price > 0:
                ht = parse_time(time_str)
                pivots.append(Pivot(
                    name=f"High {i+1}",
                    price=price,
                    pivot_time=CT_TZ.localize(datetime.combine(pivot_date, ht)),
                    pivot_type="HIGH",
                    is_secondary=True,
                    candle_high=price
                ))
    
    if secondary_lows:
        for i, (price, time_str) in enumerate(secondary_lows, 1):
            if price > 0:
                lt = parse_time(time_str)
                pivots.append(Pivot(
                    name=f"Low {i+1}",
                    price=price,
                    pivot_time=CT_TZ.localize(datetime.combine(pivot_date, lt)),
                    pivot_type="LOW",
                    is_secondary=True,
                    candle_open=price
                ))
    
    return pivots

def count_blocks(start_time: datetime, eval_time: datetime) -> int:
    """Count 30-min blocks accounting for maintenance window and weekends"""
    if eval_time <= start_time:
        return 0
    
    MAINT_START = time(16, 0)
    MAINT_END = time(17, 0)
    
    if start_time.tzinfo is None:
        start_time = CT_TZ.localize(start_time)
    if eval_time.tzinfo is None:
        eval_time = CT_TZ.localize(eval_time)
    
    blocks = 0
    current = start_time
    max_iter = 2000
    
    for _ in range(max_iter):
        if current >= eval_time:
            break
        
        wd = current.weekday()
        ct = current.time()
        
        # Skip weekends
        if wd >= 5:
            if wd == 5:  # Saturday
                current = CT_TZ.localize(datetime.combine(current.date() + timedelta(days=2), MAINT_END))
            else:  # Sunday before 5pm
                if ct < MAINT_END:
                    current = CT_TZ.localize(datetime.combine(current.date(), MAINT_END))
                else:
                    current = CT_TZ.localize(datetime.combine(current.date() + timedelta(days=1), MAINT_END))
            continue
        
        # Skip maintenance window
        if MAINT_START <= ct < MAINT_END:
            current = CT_TZ.localize(datetime.combine(current.date(), MAINT_END))
            continue
        
        # Friday after 4pm -> Sunday 5pm
        if wd == 4 and ct >= MAINT_START:
            current = CT_TZ.localize(datetime.combine(current.date() + timedelta(days=2), MAINT_END))
            continue
        
        next_block = current + timedelta(minutes=30)
        if next_block > eval_time:
            break
        
        # Handle crossing into maintenance
        if ct < MAINT_START and next_block.time() >= MAINT_START:
            blocks += 1
            current = CT_TZ.localize(datetime.combine(current.date(), MAINT_END))
            continue
        
        blocks += 1
        current = next_block
    
    return max(blocks, 1)

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    """Build structural cones from pivots at evaluation time"""
    cones = []
    
    for pivot in pivots:
        if pivot.price <= 0 or pivot.pivot_time is None:
            continue
        
        start_time = pivot.pivot_time + timedelta(minutes=30)
        blocks = count_blocks(start_time, eval_time)
        expansion = blocks * SLOPE_PER_30MIN
        
        if pivot.pivot_type == "HIGH":
            base = pivot.candle_high if pivot.candle_high > 0 else pivot.price
            ascending = base + expansion
            descending = pivot.price - expansion
        elif pivot.pivot_type == "LOW":
            base = pivot.candle_open if pivot.candle_open > 0 else pivot.price
            ascending = pivot.price + expansion
            descending = base - expansion
        else:  # CLOSE
            ascending = pivot.price + expansion
            descending = pivot.price - expansion
        
        width = ascending - descending
        
        cones.append(Cone(
            name=pivot.name,
            pivot=pivot,
            ascending_rail=round(ascending, 2),
            descending_rail=round(descending, 2),
            width=round(width, 2),
            blocks=blocks,
            is_tradeable=(width >= MIN_CONE_WIDTH)
        ))
    
    return cones

def build_pivot_table(pivots: List[Pivot], trading_date: date) -> List[PivotTableRow]:
    """Build table showing rail levels at each 30-min block from 8:30am to 12:00pm CT"""
    
    rows = []
    time_blocks = [
        ("8:30 AM", time(8, 30)),
        ("9:00 AM", time(9, 0)),
        ("9:30 AM", time(9, 30)),
        ("10:00 AM", time(10, 0)),
        ("10:30 AM", time(10, 30)),
        ("11:00 AM", time(11, 0)),
        ("11:30 AM", time(11, 30)),
        ("12:00 PM", time(12, 0)),
    ]
    
    # Find primary pivots
    high_pivot = next((p for p in pivots if p.name == "Prior High"), None)
    low_pivot = next((p for p in pivots if p.name == "Prior Low"), None)
    close_pivot = next((p for p in pivots if p.name == "Prior Close"), None)
    
    for label, t in time_blocks:
        eval_dt = CT_TZ.localize(datetime.combine(trading_date, t))
        
        row = PivotTableRow(time_block=label, time_ct=t)
        
        # Calculate rails for each pivot at this time
        for pivot, attr_asc, attr_desc in [
            (high_pivot, "prior_high_asc", "prior_high_desc"),
            (low_pivot, "prior_low_asc", "prior_low_desc"),
            (close_pivot, "prior_close_asc", "prior_close_desc")
        ]:
            if pivot and pivot.pivot_time:
                start = pivot.pivot_time + timedelta(minutes=30)
                blocks = count_blocks(start, eval_dt)
                exp = blocks * SLOPE_PER_30MIN
                
                if pivot.pivot_type == "HIGH":
                    base = pivot.candle_high if pivot.candle_high > 0 else pivot.price
                    setattr(row, attr_asc, round(base + exp, 2))
                    setattr(row, attr_desc, round(pivot.price - exp, 2))
                elif pivot.pivot_type == "LOW":
                    base = pivot.candle_open if pivot.candle_open > 0 else pivot.price
                    setattr(row, attr_asc, round(pivot.price + exp, 2))
                    setattr(row, attr_desc, round(base - exp, 2))
                else:
                    setattr(row, attr_asc, round(pivot.price + exp, 2))
                    setattr(row, attr_desc, round(pivot.price - exp, 2))
        
        rows.append(row)
    
    return rows


# =============================================================================
# TRADE SETUP GENERATION AND DAY SCORE
# =============================================================================

def generate_setups(cones: List[Cone], current_price: float, vix_bias: str, expiry: date, is_after_cutoff: bool = False) -> List[TradeSetup]:
    """Generate trade setups with real options data"""
    
    setups = []
    
    for cone in cones:
        if not cone.is_tradeable:
            continue
        
        # CALLS (enter at descending rail)
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        stop_c = round(entry_c - STOP_LOSS_PTS, 2)
        t25_c = round(entry_c + cone.width * 0.25, 2)
        t50_c = round(entry_c + cone.width * 0.50, 2)
        t75_c = round(entry_c + cone.width * 0.75, 2)
        
        spy_opt_c = get_spy_option_data(entry_c, "C", expiry)
        spx_strike_c = int(round((entry_c + 10) / 5) * 5)  # 2 strikes OTM
        
        status_c = "GREY" if is_after_cutoff else ("ACTIVE" if dist_c <= RAIL_PROXIMITY else "WAIT")
        
        delta_c = abs(spy_opt_c.delta) if spy_opt_c else DELTA_IDEAL
        risk_pts = STOP_LOSS_PTS * delta_c
        reward_pts = cone.width * 0.50 * delta_c
        
        setup_c = TradeSetup(
            direction="CALLS",
            cone_name=cone.name,
            cone_width=cone.width,
            entry=entry_c,
            stop=stop_c,
            target_25=t25_c,
            target_50=t50_c,
            target_75=t75_c,
            distance=round(dist_c, 1),
            is_active=(dist_c <= RAIL_PROXIMITY),
            spy_option=spy_opt_c,
            spx_strike=spx_strike_c,
            spx_premium_adj=spy_opt_c.spx_premium_adj if spy_opt_c else 0,
            spx_premium_x10=spy_opt_c.spx_premium_x10 if spy_opt_c else 0,
            risk_dollars=round(risk_pts * 100, 0),
            reward_50_dollars=round(reward_pts * 100, 0),
            rr_ratio=round(reward_pts / risk_pts, 1) if risk_pts > 0 else 0,
            status=status_c
        )
        setups.append(setup_c)
        
        # PUTS (enter at ascending rail)
        entry_p = cone.ascending_rail
        dist_p = abs(current_price - entry_p)
        stop_p = round(entry_p + STOP_LOSS_PTS, 2)
        t25_p = round(entry_p - cone.width * 0.25, 2)
        t50_p = round(entry_p - cone.width * 0.50, 2)
        t75_p = round(entry_p - cone.width * 0.75, 2)
        
        spy_opt_p = get_spy_option_data(entry_p, "P", expiry)
        spx_strike_p = int(round((entry_p - 10) / 5) * 5)
        
        status_p = "GREY" if is_after_cutoff else ("ACTIVE" if dist_p <= RAIL_PROXIMITY else "WAIT")
        
        delta_p = abs(spy_opt_p.delta) if spy_opt_p else DELTA_IDEAL
        risk_pts_p = STOP_LOSS_PTS * delta_p
        reward_pts_p = cone.width * 0.50 * delta_p
        
        setup_p = TradeSetup(
            direction="PUTS",
            cone_name=cone.name,
            cone_width=cone.width,
            entry=entry_p,
            stop=stop_p,
            target_25=t25_p,
            target_50=t50_p,
            target_75=t75_p,
            distance=round(dist_p, 1),
            is_active=(dist_p <= RAIL_PROXIMITY),
            spy_option=spy_opt_p,
            spx_strike=spx_strike_p,
            spx_premium_adj=spy_opt_p.spx_premium_adj if spy_opt_p else 0,
            spx_premium_x10=spy_opt_p.spx_premium_x10 if spy_opt_p else 0,
            risk_dollars=round(risk_pts_p * 100, 0),
            reward_50_dollars=round(reward_pts_p * 100, 0),
            rr_ratio=round(reward_pts_p / risk_pts_p, 1) if risk_pts_p > 0 else 0,
            status=status_p
        )
        setups.append(setup_p)
    
    return setups

def calculate_day_score(vix_zone: VIXZone, cones: List[Cone], setups: List[TradeSetup], current_price: float) -> DayScore:
    """
    Calculate day trading score based on 5 factors:
    1. VIX-Cone Alignment (25 pts)
    2. VIX Zone Clarity (25 pts)
    3. Cone Width Quality (20 pts)
    4. Premium Sweet Spot (15 pts)
    5. Multiple Cone Confluence (15 pts)
    """
    
    score = DayScore()
    
    # 1. VIX-Cone Alignment (25 pts)
    # Check if VIX bias direction has a cone rail within 10 pts
    if vix_zone.bias in ["CALLS", "PUTS"]:
        aligned = False
        for setup in setups:
            if setup.direction == vix_zone.bias and setup.distance <= 10:
                aligned = True
                break
        score.vix_cone_alignment = 25 if aligned else 10 if any(s.direction == vix_zone.bias for s in setups) else 0
    else:
        score.vix_cone_alignment = 0
    
    # 2. VIX Zone Clarity (25 pts)
    if vix_zone.bias == "WAIT":
        score.vix_clarity = 0
    elif vix_zone.position_pct >= 75 or vix_zone.position_pct <= 25 or vix_zone.zones_away != 0:
        score.vix_clarity = 25
    elif 60 <= vix_zone.position_pct <= 75 or 25 <= vix_zone.position_pct <= 40:
        score.vix_clarity = 15
    else:
        score.vix_clarity = 5
    
    # 3. Cone Width Quality (20 pts)
    tradeable_cones = [c for c in cones if c.is_tradeable]
    if tradeable_cones:
        best_width = max(c.width for c in tradeable_cones)
        if best_width >= 30:
            score.cone_width = 20
        elif best_width >= 25:
            score.cone_width = 15
        elif best_width >= 20:
            score.cone_width = 10
        else:
            score.cone_width = 5
    else:
        score.cone_width = 0
    
    # 4. Premium Sweet Spot (15 pts)
    sweet_spot_count = sum(1 for s in setups if s.spy_option and s.spy_option.in_sweet_spot)
    if sweet_spot_count >= 3:
        score.premium_quality = 15
    elif sweet_spot_count >= 1:
        score.premium_quality = 10
    else:
        # Check if any are in acceptable range
        acceptable = sum(1 for s in setups if s.spy_option and PREMIUM_MIN <= s.spy_option.mid <= PREMIUM_MAX)
        score.premium_quality = 5 if acceptable > 0 else 0
    
    # 5. Multiple Cone Confluence (15 pts)
    # Check if 2+ rails are within 5 pts of each other
    all_rails = []
    for cone in tradeable_cones:
        all_rails.extend([cone.ascending_rail, cone.descending_rail])
    
    confluence_found = False
    for i, r1 in enumerate(all_rails):
        for r2 in all_rails[i+1:]:
            if abs(r1 - r2) <= 5:
                confluence_found = True
                break
        if confluence_found:
            break
    
    score.confluence = 15 if confluence_found else 0
    
    # Total
    score.total = (score.vix_cone_alignment + score.vix_clarity + 
                   score.cone_width + score.premium_quality + score.confluence)
    
    # Grade
    if score.total >= 80:
        score.grade = "A"
        score.color = "#10b981"  # Green
    elif score.total >= 60:
        score.grade = "B"
        score.color = "#3b82f6"  # Blue
    elif score.total >= 40:
        score.grade = "C"
        score.color = "#f59e0b"  # Amber
    else:
        score.grade = "D"
        score.color = "#ef4444"  # Red
    
    return score

def check_alerts(setups: List[TradeSetup], vix_zone: VIXZone, current_time: time) -> List[Dict]:
    """Check for alert conditions"""
    alerts = []
    
    # Active setups
    for s in setups:
        if s.is_active and s.status != "GREY":
            alerts.append({
                "type": "ACTIVE",
                "priority": "HIGH",
                "message": f"🎯 {s.direction} at {s.cone_name} is ACTIVE! Entry: {s.entry:,.2f}",
                "sound": True
            })
    
    # Approaching rails
    for s in setups:
        if 5 < s.distance <= 15 and s.status != "GREY":
            alerts.append({
                "type": "APPROACHING",
                "priority": "MEDIUM",
                "message": f"⚠️ {s.direction} {s.cone_name} approaching ({s.distance:.0f} pts away)",
                "sound": False
            })
    
    # VIX zone break
    if vix_zone.zones_away != 0:
        direction = "above" if vix_zone.zones_away > 0 else "below"
        alerts.append({
            "type": "VIX_BREAK",
            "priority": "HIGH",
            "message": f"📊 VIX {abs(vix_zone.zones_away)} zone(s) {direction}! Expect return to {vix_zone.return_level:.2f}",
            "sound": True
        })
    
    # Entry window
    if INST_WINDOW_START <= current_time <= INST_WINDOW_END:
        alerts.append({
            "type": "INST_WINDOW",
            "priority": "INFO",
            "message": "🏛️ Institutional Window (9:00-9:30 CT) - Watch for setups!",
            "sound": False
        })
    
    if current_time == ENTRY_TARGET:
        alerts.append({
            "type": "ENTRY",
            "priority": "HIGH",
            "message": "⏰ 9:10 CT - Optimal entry time!",
            "sound": True
        })
    
    return alerts


# =============================================================================
# UI GENERATION - GLASS NEOMORPHISM
# =============================================================================

def render_dashboard(
    vix_zone: VIXZone,
    cones: List[Cone],
    setups: List[TradeSetup],
    pivot_table: List[PivotTableRow],
    prior_session: Dict,
    day_score: DayScore,
    oi_levels: List[Dict],
    alerts: List[Dict],
    spx_price: float,
    trading_date: date,
    is_historical: bool,
    theme: str
) -> str:
    """Generate the legendary glass neomorphism dashboard HTML"""
    
    # Theme colors
    if theme == "dark":
        bg = "#0a0a0f"
        bg2 = "#12121a"
        card_bg = "rgba(25, 25, 35, 0.8)"
        glass = "rgba(255,255,255,0.03)"
        text1 = "#ffffff"
        text2 = "#9ca3af"
        text3 = "#6b7280"
        border = "rgba(255,255,255,0.08)"
        shadow = "rgba(0,0,0,0.5)"
    else:
        bg = "#f8fafc"
        bg2 = "#f1f5f9"
        card_bg = "rgba(255,255,255,0.8)"
        glass = "rgba(255,255,255,0.6)"
        text1 = "#0f172a"
        text2 = "#475569"
        text3 = "#94a3b8"
        border = "rgba(0,0,0,0.08)"
        shadow = "rgba(0,0,0,0.1)"
    
    green = "#10b981"
    red = "#ef4444"
    amber = "#f59e0b"
    blue = "#3b82f6"
    purple = "#8b5cf6"
    
    # Bias styling
    if vix_zone.bias == "CALLS":
        bias_color, bias_icon = green, "▲"
    elif vix_zone.bias == "PUTS":
        bias_color, bias_icon = red, "▼"
    elif vix_zone.bias == "INVALIDATED":
        bias_color, bias_icon = "#6b7280", "✕"
    else:
        bias_color, bias_icon = amber, "●"
    
    now = get_ct_now()
    time_to_910 = get_time_until(ENTRY_TARGET)
    time_to_1130 = get_time_until(CUTOFF_TIME)
    is_inst_window = INST_WINDOW_START <= now.time() <= INST_WINDOW_END
    
    html = f'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ 
    font-family:'Inter',sans-serif; 
    background:{bg}; 
    color:{text1}; 
    padding:20px;
    min-height:100vh;
}}
.container {{ max-width:1600px; margin:0 auto; }}
.glass {{
    background:{card_bg};
    backdrop-filter:blur(20px);
    -webkit-backdrop-filter:blur(20px);
    border:1px solid {border};
    border-radius:20px;
    padding:24px;
    margin-bottom:16px;
    box-shadow:0 8px 32px {shadow};
}}
.glass:hover {{ transform:translateY(-1px); }}
.section-header {{
    display:flex;
    justify-content:space-between;
    align-items:center;
    cursor:pointer;
    margin-bottom:16px;
}}
.section-title {{
    font-size:12px;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:2px;
    color:{text3};
    display:flex;
    align-items:center;
    gap:8px;
}}
.toggle {{ font-size:16px; color:{text3}; transition:transform 0.3s; }}
.collapsed .content {{ display:none; }}
.collapsed .toggle {{ transform:rotate(-90deg); }}

/* Header */
.header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; flex-wrap:wrap; gap:16px; }}
.logo {{ display:flex; align-items:center; gap:12px; }}
.logo-icon {{ 
    width:56px; height:56px; 
    background:linear-gradient(135deg,{blue},{purple}); 
    border-radius:14px; 
    display:flex; align-items:center; justify-content:center;
    font-size:18px; font-weight:800; color:white;
    box-shadow:0 8px 24px rgba(59,130,246,0.4);
}}
.logo h1 {{ font-size:24px; font-weight:800; }}
.tagline {{ font-size:12px; color:{text2}; font-style:italic; }}
.header-right {{ display:flex; align-items:center; gap:20px; }}
.time-display {{ font-family:'JetBrains Mono'; font-size:28px; font-weight:600; }}
.countdown {{ text-align:right; }}
.countdown-label {{ font-size:10px; text-transform:uppercase; letter-spacing:1px; color:{text3}; }}
.countdown-value {{ font-family:'JetBrains Mono'; font-size:16px; color:{amber}; }}

/* Banners */
.banner {{
    padding:16px 20px;
    border-radius:14px;
    display:flex;
    align-items:center;
    gap:16px;
    margin-bottom:16px;
}}
.banner-inst {{ background:linear-gradient(135deg,{amber}30,{amber}10); border:2px solid {amber}50; animation:pulse 2s infinite; }}
.banner-hist {{ background:linear-gradient(135deg,{purple}30,{purple}10); border:2px solid {purple}50; }}
@keyframes pulse {{ 0%,100%{{opacity:1;}} 50%{{opacity:0.7;}} }}
.banner-icon {{ font-size:28px; }}
.banner-title {{ font-weight:700; font-size:15px; }}
.banner-sub {{ font-size:12px; color:{text2}; }}

/* Grid layouts */
.grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.grid-3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
.grid-4 {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
@media(max-width:900px) {{ .grid-2,.grid-3,.grid-4 {{ grid-template-columns:1fr; }} }}

/* VIX Zone */
.vix-ladder {{ position:relative; height:80px; background:{glass}; border-radius:12px; margin:16px 0; overflow:hidden; }}
.vix-bar {{ position:absolute; left:20px; right:20px; height:32px; top:50%; transform:translateY(-50%); 
    background:linear-gradient(90deg,{green}40,{bg2},{bg2},{red}40); border-radius:16px; }}
.vix-marker {{ position:absolute; width:20px; height:20px; background:{bias_color}; border-radius:50%;
    top:50%; transform:translate(-50%,-50%); box-shadow:0 0 20px {bias_color}; border:3px solid {card_bg}; z-index:10; }}
.vix-labels {{ position:absolute; bottom:8px; left:20px; right:20px; display:flex; justify-content:space-between;
    font-family:'JetBrains Mono'; font-size:11px; color:{text3}; }}

/* Bias Card */
.bias-card {{ text-align:center; padding:32px; background:linear-gradient(135deg,{bias_color}20,{bias_color}05); border:2px solid {bias_color}50; }}
.bias-icon {{ font-size:48px; color:{bias_color}; text-shadow:0 0 30px {bias_color}; }}
.bias-label {{ font-size:28px; font-weight:800; color:{bias_color}; letter-spacing:3px; margin-top:8px; }}
.bias-reason {{ font-size:13px; color:{text2}; margin-top:12px; }}
.bias-match {{ font-size:12px; color:{blue}; margin-top:8px; }}

/* Score */
.score-circle {{
    width:100px; height:100px; border-radius:50%; margin:0 auto 16px;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    font-family:'JetBrains Mono'; border:4px solid;
}}
.score-value {{ font-size:32px; font-weight:700; }}
.score-grade {{ font-size:14px; font-weight:600; }}

/* Stats */
.stat {{ background:{glass}; border-radius:12px; padding:16px; text-align:center; }}
.stat-value {{ font-family:'JetBrains Mono'; font-size:20px; font-weight:600; }}
.stat-label {{ font-size:10px; text-transform:uppercase; letter-spacing:1px; color:{text3}; margin-top:4px; }}

/* Tables */
table {{ width:100%; border-collapse:collapse; }}
th {{ font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:1px; color:{text3};
    padding:12px 8px; text-align:left; border-bottom:1px solid {border}; }}
td {{ padding:14px 8px; font-size:13px; border-bottom:1px solid {border}; }}
tr:hover {{ background:{glass}; }}
tr.active {{ background:linear-gradient(90deg,{green}20,transparent); animation:glow 2s infinite; }}
tr.grey {{ opacity:0.4; }}
@keyframes glow {{ 0%,100%{{opacity:1;}} 50%{{opacity:0.6;}} }}
.mono {{ font-family:'JetBrains Mono'; }}
.green {{ color:{green}; }}
.red {{ color:{red}; }}
.amber {{ color:{amber}; }}
.blue {{ color:{blue}; }}

/* Pills */
.pill {{ display:inline-block; padding:4px 12px; border-radius:100px; font-size:11px; font-weight:600; font-family:'JetBrains Mono'; }}
.pill-green {{ background:{green}20; color:{green}; }}
.pill-red {{ background:{red}20; color:{red}; }}
.pill-amber {{ background:{amber}20; color:{amber}; }}
.pill-grey {{ background:rgba(107,114,128,0.2); color:#6b7280; }}

/* Alerts */
.alert {{ padding:12px 16px; border-radius:10px; margin-bottom:8px; display:flex; align-items:center; gap:10px; font-size:13px; }}
.alert-high {{ background:{red}15; border-left:3px solid {red}; }}
.alert-medium {{ background:{amber}15; border-left:3px solid {amber}; }}
.alert-info {{ background:{blue}15; border-left:3px solid {blue}; }}

/* Sweet spot */
.sweet {{ color:{green}; }}
.sweet::before {{ content:"★ "; }}

.footer {{ text-align:center; padding:32px; color:{text3}; font-size:11px; }}
</style>
</head>
<body>
<div class="container">
'''
    
    # Header
    html += f'''
<div class="header">
    <div class="logo">
        <div class="logo-icon">SP</div>
        <div>
            <h1>SPX Prophet</h1>
            <div class="tagline">Where Structure Becomes Foresight</div>
        </div>
    </div>
    <div class="header-right">
        <div class="countdown">
            <div class="countdown-label">To 9:10 AM</div>
            <div class="countdown-value">{format_countdown(time_to_910)}</div>
        </div>
        <div class="countdown">
            <div class="countdown-label">To 11:30 Cutoff</div>
            <div class="countdown-value">{format_countdown(time_to_1130)}</div>
        </div>
        <div class="time-display">{now.strftime("%H:%M")} CT</div>
    </div>
</div>
'''
    
    # Historical Banner
    if is_historical:
        html += f'''
<div class="banner banner-hist">
    <div class="banner-icon">📅</div>
    <div>
        <div class="banner-title" style="color:{purple}">Historical Analysis: {trading_date.strftime("%A, %B %d, %Y")}</div>
        <div class="banner-sub">Viewing past data - not live</div>
    </div>
</div>
'''
    
    # Institutional Window Banner
    if is_inst_window and not is_historical:
        html += f'''
<div class="banner banner-inst">
    <div class="banner-icon">🏛️</div>
    <div>
        <div class="banner-title" style="color:{amber}">INSTITUTIONAL WINDOW ACTIVE</div>
        <div class="banner-sub">9:00 - 9:30 AM CT • Watch for large order flow</div>
    </div>
</div>
'''
    
    # Alerts
    if alerts:
        html += '<div class="glass" style="padding:16px;">'
        for a in alerts[:4]:
            cls = f"alert-{a['priority'].lower()}"
            html += f'<div class="alert {cls}">{a["message"]}</div>'
        html += '</div>'
    
    # VIX Zone Section
    marker_pos = min(max(vix_zone.position_pct, 5), 95) if vix_zone.zone_size > 0 else 50
    html += f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title"><span>📊</span> VIX ZONE ANALYSIS</div>
        <span class="toggle">▼</span>
    </div>
    <div class="content">
        <div class="grid-2">
            <div>
                <div class="vix-ladder">
                    <div class="vix-bar"></div>
                    <div class="vix-marker" style="left:{marker_pos}%;"></div>
                    <div class="vix-labels">
                        <span>{vix_zone.bottom:.2f}</span>
                        <span>Zone: {vix_zone.zone_size:.2f}</span>
                        <span>{vix_zone.top:.2f}</span>
                    </div>
                </div>
                <div class="grid-4" style="margin-top:12px;">
                    <div class="stat"><div class="stat-value">{vix_zone.current:.2f}</div><div class="stat-label">Current VIX</div></div>
                    <div class="stat"><div class="stat-value">{vix_zone.position_pct:.0f}%</div><div class="stat-label">Position</div></div>
                    <div class="stat"><div class="stat-value blue">±{vix_zone.expected_spx_move:.0f}</div><div class="stat-label">Exp. SPX Move</div></div>
                    <div class="stat"><div class="stat-value">{vix_zone.zones_away:+d}</div><div class="stat-label">Zones Away</div></div>
                </div>
            </div>
            <div class="bias-card glass">
                <div class="bias-icon">{bias_icon}</div>
                <div class="bias-label">{vix_zone.bias}</div>
                <div class="bias-reason">{vix_zone.bias_reason}</div>
                {"<div class='bias-match'>Matched Rail: " + vix_zone.matched_cone + " @ " + format_price(vix_zone.matched_rail) + "</div>" if vix_zone.matched_rail > 0 else ""}
            </div>
        </div>
    </div>
</div>
'''
    
    # Calls Setups
    calls = [s for s in setups if s.direction == "CALLS"]
    html += f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title" style="color:{green}"><span>▲</span> CALLS SETUPS</div>
        <span class="toggle">▼</span>
    </div>
    <div class="content">
        <table>
            <thead><tr>
                <th>Cone</th><th>SPX Entry</th><th>SPY Strike</th><th>Bid/Ask</th>
                <th>SPX Est.</th><th>Delta</th><th>Theta</th><th>IV</th>
                <th>Stop</th><th>T50%</th><th>R:R</th><th>Status</th>
            </tr></thead>
            <tbody>
'''
    for s in calls:
        opt = s.spy_option
        row_class = "active" if s.status == "ACTIVE" else "grey" if s.status == "GREY" else ""
        
        if opt:
            spy_str = f"{int(opt.strike)}{opt.option_type}"
            bid_ask = f"${opt.bid:.2f}/${opt.ask:.2f}"
            spx_est = f"${s.spx_premium_adj:.0f}" if s.spx_premium_adj > 0 else "--"
            delta_str = f"{abs(opt.delta):.2f}" if opt.delta != 0 else "--"
            theta_str = f"${opt.theta:.2f}" if opt.theta != 0 else "--"
            iv_str = f"{opt.iv*100:.1f}%" if opt.iv > 0 else "--"
            sweet_cls = "sweet" if opt.in_sweet_spot else ""
        else:
            spy_str = bid_ask = spx_est = delta_str = theta_str = iv_str = "--"
            sweet_cls = ""
        
        status_html = f'<span class="pill pill-green">🎯 ACTIVE</span>' if s.status == "ACTIVE" else \
                     f'<span class="pill pill-grey">CLOSED</span>' if s.status == "GREY" else \
                     f'<span class="pill pill-amber">{s.distance:.0f} pts</span>'
        
        html += f'''<tr class="{row_class}">
            <td><strong>{s.cone_name}</strong></td>
            <td class="mono green">{s.entry:,.2f}</td>
            <td class="mono {sweet_cls}">{spy_str}</td>
            <td class="mono">{bid_ask}</td>
            <td class="mono">{spx_est}</td>
            <td class="mono">{delta_str}</td>
            <td class="mono red">{theta_str}</td>
            <td class="mono">{iv_str}</td>
            <td class="mono red">{s.stop:,.2f}</td>
            <td class="mono">{s.target_50:,.2f}</td>
            <td class="mono green"><strong>1:{s.rr_ratio:.1f}</strong></td>
            <td>{status_html}</td>
        </tr>'''
    
    html += '</tbody></table></div></div>'
    
    # Puts Setups
    puts = [s for s in setups if s.direction == "PUTS"]
    html += f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title" style="color:{red}"><span>▼</span> PUTS SETUPS</div>
        <span class="toggle">▼</span>
    </div>
    <div class="content">
        <table>
            <thead><tr>
                <th>Cone</th><th>SPX Entry</th><th>SPY Strike</th><th>Bid/Ask</th>
                <th>SPX Est.</th><th>Delta</th><th>Theta</th><th>IV</th>
                <th>Stop</th><th>T50%</th><th>R:R</th><th>Status</th>
            </tr></thead>
            <tbody>
'''
    for s in puts:
        opt = s.spy_option
        row_class = "active" if s.status == "ACTIVE" else "grey" if s.status == "GREY" else ""
        
        if opt:
            spy_str = f"{int(opt.strike)}{opt.option_type}"
            bid_ask = f"${opt.bid:.2f}/${opt.ask:.2f}"
            spx_est = f"${s.spx_premium_adj:.0f}" if s.spx_premium_adj > 0 else "--"
            delta_str = f"{abs(opt.delta):.2f}" if opt.delta != 0 else "--"
            theta_str = f"${opt.theta:.2f}" if opt.theta != 0 else "--"
            iv_str = f"{opt.iv*100:.1f}%" if opt.iv > 0 else "--"
            sweet_cls = "sweet" if opt.in_sweet_spot else ""
        else:
            spy_str = bid_ask = spx_est = delta_str = theta_str = iv_str = "--"
            sweet_cls = ""
        
        status_html = f'<span class="pill pill-green">🎯 ACTIVE</span>' if s.status == "ACTIVE" else \
                     f'<span class="pill pill-grey">CLOSED</span>' if s.status == "GREY" else \
                     f'<span class="pill pill-amber">{s.distance:.0f} pts</span>'
        
        html += f'''<tr class="{row_class}">
            <td><strong>{s.cone_name}</strong></td>
            <td class="mono red">{s.entry:,.2f}</td>
            <td class="mono {sweet_cls}">{spy_str}</td>
            <td class="mono">{bid_ask}</td>
            <td class="mono">{spx_est}</td>
            <td class="mono">{delta_str}</td>
            <td class="mono red">{theta_str}</td>
            <td class="mono">{iv_str}</td>
            <td class="mono green">{s.stop:,.2f}</td>
            <td class="mono">{s.target_50:,.2f}</td>
            <td class="mono green"><strong>1:{s.rr_ratio:.1f}</strong></td>
            <td>{status_html}</td>
        </tr>'''
    
    html += '</tbody></table></div></div>'
    
    # Prior Session
    html += f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title"><span>📈</span> PRIOR SESSION</div>
        <span class="toggle">▼</span>
    </div>
    <div class="content">
        <div class="grid-4">
            <div class="stat"><div class="stat-value green">{prior_session.get("high", 0):,.2f}</div><div class="stat-label">High</div></div>
            <div class="stat"><div class="stat-value red">{prior_session.get("low", 0):,.2f}</div><div class="stat-label">Low</div></div>
            <div class="stat"><div class="stat-value">{prior_session.get("close", 0):,.2f}</div><div class="stat-label">Close</div></div>
            <div class="stat"><div class="stat-value blue">{prior_session.get("high", 0) - prior_session.get("low", 0):,.0f}</div><div class="stat-label">Range</div></div>
        </div>
    </div>
</div>
'''
    
    # Day Score
    html += f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title"><span>🎯</span> DAY SCORE</div>
        <span class="toggle">▼</span>
    </div>
    <div class="content">
        <div class="grid-2">
            <div style="text-align:center;">
                <div class="score-circle" style="border-color:{day_score.color}; color:{day_score.color};">
                    <div class="score-value">{day_score.total}</div>
                    <div class="score-grade">Grade {day_score.grade}</div>
                </div>
                <div style="font-size:13px; color:{text2};">
                    {"🟢 Excellent day for trading" if day_score.total >= 80 else
                     "🔵 Good setup - proceed with caution" if day_score.total >= 60 else
                     "🟠 Marginal - be selective" if day_score.total >= 40 else
                     "🔴 Skip or reduce size"}
                </div>
            </div>
            <div>
                <div class="grid-2" style="gap:8px;">
                    <div class="stat"><div class="stat-value">{day_score.vix_cone_alignment}/25</div><div class="stat-label">VIX-Cone Align</div></div>
                    <div class="stat"><div class="stat-value">{day_score.vix_clarity}/25</div><div class="stat-label">VIX Clarity</div></div>
                    <div class="stat"><div class="stat-value">{day_score.cone_width}/20</div><div class="stat-label">Cone Width</div></div>
                    <div class="stat"><div class="stat-value">{day_score.premium_quality}/15</div><div class="stat-label">Premium</div></div>
                    <div class="stat" style="grid-column:span 2;"><div class="stat-value">{day_score.confluence}/15</div><div class="stat-label">Confluence</div></div>
                </div>
            </div>
        </div>
    </div>
</div>
'''
    
    # Cone Rails Table
    html += f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title"><span>📐</span> STRUCTURAL CONES</div>
        <span class="toggle">▼</span>
    </div>
    <div class="content">
        <table>
            <thead><tr>
                <th>Pivot</th><th>Ascending (PUTS)</th><th>Descending (CALLS)</th><th>Width</th><th>Blocks</th><th>Tradeable</th>
            </tr></thead>
            <tbody>
'''
    for c in cones:
        width_cls = "green" if c.width >= 25 else "amber" if c.width >= MIN_CONE_WIDTH else "red"
        trade_pill = f'<span class="pill pill-green">YES</span>' if c.is_tradeable else f'<span class="pill pill-red">NO</span>'
        html += f'''<tr>
            <td><strong>{c.name}</strong></td>
            <td class="mono red">{c.ascending_rail:,.2f}</td>
            <td class="mono green">{c.descending_rail:,.2f}</td>
            <td class="mono {width_cls}">{c.width:.0f} pts</td>
            <td class="mono">{c.blocks}</td>
            <td>{trade_pill}</td>
        </tr>'''
    html += '</tbody></table></div></div>'
    
    # Pivot Table (30-min blocks)
    html += f'''
<div class="glass collapsed">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title"><span>📋</span> PIVOT TABLE (8:30 AM - 12:00 PM CT)</div>
        <span class="toggle">▼</span>
    </div>
    <div class="content">
        <table>
            <thead><tr>
                <th>Time</th>
                <th>High ▲</th><th>High ▼</th>
                <th>Low ▲</th><th>Low ▼</th>
                <th>Close ▲</th><th>Close ▼</th>
            </tr></thead>
            <tbody>
'''
    for row in pivot_table:
        is_inst = INST_WINDOW_START <= row.time_ct <= INST_WINDOW_END
        row_style = f'background:{amber}10;' if is_inst else ""
        html += f'''<tr style="{row_style}">
            <td><strong>{row.time_block}</strong>{"🏛️" if is_inst else ""}</td>
            <td class="mono red">{row.prior_high_asc:,.2f}</td>
            <td class="mono green">{row.prior_high_desc:,.2f}</td>
            <td class="mono red">{row.prior_low_asc:,.2f}</td>
            <td class="mono green">{row.prior_low_desc:,.2f}</td>
            <td class="mono red">{row.prior_close_asc:,.2f}</td>
            <td class="mono green">{row.prior_close_desc:,.2f}</td>
        </tr>'''
    html += '</tbody></table></div></div>'
    
    # Open Interest
    if oi_levels:
        html += f'''
<div class="glass collapsed">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title"><span>🎯</span> OPEN INTEREST MAGNETS</div>
        <span class="toggle">▼</span>
    </div>
    <div class="content">
        <table>
            <thead><tr><th>SPY Strike</th><th>SPX Equiv</th><th>Type</th><th>Open Interest</th></tr></thead>
            <tbody>
'''
        for oi in oi_levels[:8]:
            type_cls = "green" if oi["type"] == "call" else "red"
            html += f'''<tr>
                <td class="mono">{oi["spy_strike"]}</td>
                <td class="mono">{oi["spx_equiv"]:,.0f}</td>
                <td class="{type_cls}">{oi["type"].upper()}</td>
                <td class="mono">{oi["oi"]:,}</td>
            </tr>'''
        html += '</tbody></table></div></div>'
    
    # Footer
    html += f'''
<div class="footer">
    SPX Prophet v6.1 Legendary Edition • "Where Structure Becomes Foresight"<br>
    <span style="opacity:0.7;">Data via Polygon.io • Not financial advice • Built for professional trading</span>
</div>
</div>
<script>
function playAlert() {{
    try {{ new Audio('data:audio/wav;base64,UklGRl9vT19teleVBMQAABAAgAZGF0YQoGAACA').play(); }} catch(e){{}}
}}
</script>
</body></html>
'''
    return html


# =============================================================================
# STREAMLIT MAIN APPLICATION
# =============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet v6.1",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Session state defaults
    defaults = {
        'theme': 'light',
        'vix_bottom': 0.0,
        'vix_top': 0.0,
        'vix_current': 0.0,
        'use_manual_pivots': False,
        'high_price': 0.0, 'high_time': "10:30",
        'low_price': 0.0, 'low_time': "14:00",
        'close_price': 0.0,
        'sec_highs': [],
        'sec_lows': [],
        'trading_date': None,
        'last_refresh': None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    # ==================== SIDEBAR ====================
    with st.sidebar:
        st.markdown("## 📈 SPX Prophet v6.1")
        st.markdown("*Legendary Edition*")
        st.divider()
        
        # Theme
        theme = st.radio("🎨 Theme", ["Light", "Dark"], horizontal=True,
                        index=0 if st.session_state.theme == "light" else 1)
        st.session_state.theme = theme.lower()
        
        st.divider()
        
        # Date Selection (ALWAYS VISIBLE)
        st.markdown("### 📅 Trading Date")
        
        today = get_ct_now().date()
        next_trade = get_next_trading_day(today)
        
        # Quick buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📍 Next Trade Day", use_container_width=True):
                st.session_state.trading_date = next_trade
        with col2:
            if st.button("📆 Yesterday", use_container_width=True):
                st.session_state.trading_date = get_prior_trading_day(today)
        
        # Date picker
        selected_date = st.date_input(
            "Select Date",
            value=st.session_state.trading_date or next_trade,
            min_value=today - timedelta(days=730),
            max_value=today + timedelta(days=7)
        )
        st.session_state.trading_date = selected_date
        
        # Show holiday/half-day info
        if is_holiday(selected_date):
            st.warning(f"🚫 {selected_date} is {HOLIDAYS_2025.get(selected_date, 'a holiday')} - Market Closed")
        elif is_half_day(selected_date):
            st.info(f"⏰ {selected_date} is {HALF_DAYS_2025.get(selected_date, 'half day')} - 12pm CT Close")
        
        is_historical = selected_date < today or (selected_date == today and get_ct_now().time() > CUTOFF_TIME)
        
        st.divider()
        
        # VIX Zone Input
        st.markdown("### 📊 VIX Zone (5pm-3am)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input("Zone Bottom", value=st.session_state.vix_bottom, step=0.01, format="%.2f")
        with col2:
            st.session_state.vix_top = st.number_input("Zone Top", value=st.session_state.vix_top, step=0.01, format="%.2f")
        
        st.session_state.vix_current = st.number_input("Current VIX (8am)", value=st.session_state.vix_current, step=0.01, format="%.2f")
        
        if st.button("🔄 Fetch Live VIX"):
            vix = polygon_get_index_price("I:VIX")
            if vix > 0:
                st.session_state.vix_current = round(vix, 2)
                st.success(f"VIX: {vix:.2f}")
            else:
                st.warning("Could not fetch VIX")
        
        st.divider()
        
        # Pivot Input
        st.markdown("### 📍 Prior Day Pivots")
        
        st.session_state.use_manual_pivots = st.checkbox("Manual Override", value=st.session_state.use_manual_pivots)
        
        if st.session_state.use_manual_pivots:
            st.markdown("**Primary HIGH** (highest wick)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.high_price = st.number_input("Price##hp", value=st.session_state.high_price, step=0.01, format="%.2f")
            with c2:
                st.session_state.high_time = st.text_input("Time##ht", value=st.session_state.high_time)
            
            st.markdown("**Primary LOW** (open after)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.low_price = st.number_input("Price##lp", value=st.session_state.low_price, step=0.01, format="%.2f")
            with c2:
                st.session_state.low_time = st.text_input("Time##lt", value=st.session_state.low_time)
            
            st.session_state.close_price = st.number_input("Prior Close", value=st.session_state.close_price, step=0.01, format="%.2f")
            
            st.markdown("---")
            st.markdown("**Secondary Pivots**")
            
            num_sh = st.number_input("# Secondary Highs", 0, 3, len(st.session_state.sec_highs), key="nsh")
            num_sl = st.number_input("# Secondary Lows", 0, 3, len(st.session_state.sec_lows), key="nsl")
            
            # Adjust lists
            while len(st.session_state.sec_highs) < num_sh:
                st.session_state.sec_highs.append([0.0, "11:00"])
            st.session_state.sec_highs = st.session_state.sec_highs[:num_sh]
            
            while len(st.session_state.sec_lows) < num_sl:
                st.session_state.sec_lows.append([0.0, "13:00"])
            st.session_state.sec_lows = st.session_state.sec_lows[:num_sl]
            
            for i in range(num_sh):
                st.markdown(f"*High {i+2}*")
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.session_state.sec_highs[i][0] = st.number_input(f"Price##shp{i}", value=float(st.session_state.sec_highs[i][0]), step=0.01, format="%.2f")
                with c2:
                    st.session_state.sec_highs[i][1] = st.text_input(f"Time##sht{i}", value=st.session_state.sec_highs[i][1])
            
            for i in range(num_sl):
                st.markdown(f"*Low {i+2}*")
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.session_state.sec_lows[i][0] = st.number_input(f"Price##slp{i}", value=float(st.session_state.sec_lows[i][0]), step=0.01, format="%.2f")
                with c2:
                    st.session_state.sec_lows[i][1] = st.text_input(f"Time##slt{i}", value=st.session_state.sec_lows[i][1])
        
        st.divider()
        
        # Refresh
        if st.button("🔄 REFRESH DATA", use_container_width=True, type="primary"):
            st.session_state.last_refresh = get_ct_now()
            st.rerun()
        
        if st.session_state.last_refresh:
            st.caption(f"Last: {st.session_state.last_refresh.strftime('%H:%M:%S CT')}")
    
    # ==================== MAIN PROCESSING ====================
    
    now = get_ct_now()
    trading_date = st.session_state.trading_date or get_next_trading_day()
    
    # Handle holidays - skip to find actual prior trading day
    if is_holiday(trading_date):
        st.warning(f"⚠️ {trading_date} is a holiday. Showing data for next trading day.")
        trading_date = get_next_trading_day(trading_date)
    
    pivot_date = get_prior_trading_day(trading_date)
    pivot_close_time = get_market_close_time(pivot_date)
    
    is_historical = trading_date < now.date() or (trading_date == now.date() and now.time() > CUTOFF_TIME)
    expiry = trading_date
    
    # Get prior session data
    prior_bars = polygon_get_daily_bars("I:SPX", pivot_date, pivot_date)
    prior_session = {}
    if prior_bars:
        prior_session = {
            "high": prior_bars[0].get("h", 0),
            "low": prior_bars[0].get("l", 0),
            "close": prior_bars[0].get("c", 0),
            "open": prior_bars[0].get("o", 0)
        }
    
    # Build Pivots
    if st.session_state.use_manual_pivots and st.session_state.high_price > 0:
        sec_highs = [(h[0], h[1]) for h in st.session_state.sec_highs if h[0] > 0]
        sec_lows = [(l[0], l[1]) for l in st.session_state.sec_lows if l[0] > 0]
        
        pivots = create_manual_pivots(
            st.session_state.high_price, st.session_state.high_time,
            st.session_state.low_price, st.session_state.low_time,
            st.session_state.close_price,
            pivot_date, pivot_close_time,
            sec_highs, sec_lows
        )
    else:
        # Auto-detect
        bars_30m = polygon_get_intraday_bars("I:SPX", pivot_date, pivot_date, 30)
        if bars_30m:
            pivots = detect_pivots_auto(bars_30m, pivot_date, pivot_close_time)
        else:
            # Fallback
            pivots = []
            if prior_session:
                pivots = [
                    Pivot(name="Prior High", price=prior_session.get("high", 0),
                          pivot_time=CT_TZ.localize(datetime.combine(pivot_date, time(10, 30))),
                          pivot_type="HIGH", candle_high=prior_session.get("high", 0)),
                    Pivot(name="Prior Low", price=prior_session.get("low", 0),
                          pivot_time=CT_TZ.localize(datetime.combine(pivot_date, time(14, 0))),
                          pivot_type="LOW", candle_open=prior_session.get("low", 0)),
                    Pivot(name="Prior Close", price=prior_session.get("close", 0),
                          pivot_time=CT_TZ.localize(datetime.combine(pivot_date, pivot_close_time)),
                          pivot_type="CLOSE")
                ]
    
    # Build cones at 9:00 AM CT of trading date
    eval_time = CT_TZ.localize(datetime.combine(trading_date, time(9, 0)))
    cones = build_cones(pivots, eval_time)
    
    # VIX Zone Analysis
    vix_zone = analyze_vix_zone(
        st.session_state.vix_bottom,
        st.session_state.vix_top,
        st.session_state.vix_current,
        cones
    )
    
    # Current price
    spx_price = polygon_get_index_price("I:SPX")
    if spx_price == 0:
        spx_price = prior_session.get("close", 0)
    
    is_after_cutoff = (trading_date == now.date() and now.time() > CUTOFF_TIME) or is_historical
    
    # Generate setups
    setups = generate_setups(cones, spx_price, vix_zone.bias, expiry, is_after_cutoff)
    
    # Day Score
    day_score = calculate_day_score(vix_zone, cones, setups, spx_price)
    
    # Pivot Table
    pivot_table = build_pivot_table(pivots, trading_date)
    
    # Open Interest
    spy_price = spx_price / 10 if spx_price > 0 else 600
    oi_levels = get_open_interest_levels(expiry, spy_price) if not is_historical else []
    
    # Alerts
    alerts = check_alerts(setups, vix_zone, now.time()) if not is_historical else []
    
    # Render Dashboard
    html = render_dashboard(
        vix_zone=vix_zone,
        cones=cones,
        setups=setups,
        pivot_table=pivot_table,
        prior_session=prior_session,
        day_score=day_score,
        oi_levels=oi_levels,
        alerts=alerts,
        spx_price=spx_price,
        trading_date=trading_date,
        is_historical=is_historical,
        theme=st.session_state.theme
    )
    
    components.html(html, height=3000, scrolling=True)


if __name__ == "__main__":
    main()
