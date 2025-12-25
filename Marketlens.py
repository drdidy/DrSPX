"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║   SPX PROPHET v6.2 - "Where Structure Becomes Foresight"                      ║
║   Legendary Edition with Profit Targets                                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import numpy as np
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import pytz

# =============================================================================
# CONFIGURATION
# =============================================================================

POLYGON_API_KEY = "jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm"
POLYGON_BASE_URL = "https://api.polygon.io"

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

SLOPE_PER_30MIN = 0.45
MIN_CONE_WIDTH = 18.0
STOP_LOSS_PTS = 6.0
RAIL_PROXIMITY = 5.0

PREMIUM_SWEET_LOW = 4.00
PREMIUM_SWEET_HIGH = 7.00
DELTA_IDEAL = 0.33
VIX_TO_SPX_MULTIPLIER = 175

PREMARKET_START = time(8, 30)
RTH_OPEN = time(9, 30)
INST_WINDOW_START = time(9, 0)
INST_WINDOW_END = time(9, 30)
ENTRY_TARGET = time(9, 10)
CUTOFF_TIME = time(11, 30)
REGULAR_CLOSE = time(16, 0)
HALF_DAY_CLOSE = time(12, 0)

HOLIDAYS_2025 = {
    date(2025, 1, 1): "New Year's Day", date(2025, 1, 20): "MLK Day",
    date(2025, 2, 17): "Presidents Day", date(2025, 4, 18): "Good Friday",
    date(2025, 5, 26): "Memorial Day", date(2025, 6, 19): "Juneteenth",
    date(2025, 7, 4): "Independence Day", date(2025, 9, 1): "Labor Day",
    date(2025, 11, 27): "Thanksgiving", date(2025, 12, 25): "Christmas",
}

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
    matched_rail: float = 0.0
    matched_cone: str = ""

@dataclass
class Pivot:
    name: str = ""
    price: float = 0.0
    pivot_time: datetime = None
    pivot_type: str = ""
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
class OptionData:
    spy_strike: float = 0.0
    spy_price: float = 0.0
    spx_strike: int = 0
    spx_price_est: float = 0.0
    delta: float = 0.0
    iv: float = 0.0
    in_sweet_spot: bool = False

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
    option: OptionData = None
    # Profit estimates (SPX equivalent dollars per contract)
    profit_25: float = 0.0
    profit_50: float = 0.0
    profit_75: float = 0.0
    risk_dollars: float = 0.0
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
    return HALF_DAY_CLOSE if is_half_day(d) else REGULAR_CLOSE

def get_next_trading_day(from_date: date = None) -> date:
    if from_date is None:
        now = get_ct_now()
        from_date = now.date()
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

def get_time_until(target: time, from_dt: datetime = None) -> timedelta:
    if from_dt is None:
        from_dt = get_ct_now()
    target_dt = CT_TZ.localize(datetime.combine(from_dt.date(), target))
    return max(target_dt - from_dt, timedelta(0))

def format_countdown(td: timedelta) -> str:
    if td.total_seconds() <= 0:
        return "NOW"
    total_secs = int(td.total_seconds())
    hours, remainder = divmod(total_secs, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

# =============================================================================
# POLYGON API
# =============================================================================

def polygon_request(endpoint: str, params: dict = None) -> Optional[Dict]:
    try:
        if params is None:
            params = {}
        params["apiKey"] = POLYGON_API_KEY
        url = f"{POLYGON_BASE_URL}{endpoint}"
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        pass
    return None

def polygon_get_index_price(ticker: str) -> float:
    data = polygon_request(f"/v3/snapshot", {"ticker.any_of": ticker})
    if data and data.get("results"):
        return data["results"][0].get("value", 0)
    return 0.0

def polygon_get_daily_bars(ticker: str, from_date: date, to_date: date) -> List[Dict]:
    data = polygon_request(
        f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}",
        {"adjusted": "true", "sort": "asc"}
    )
    return data.get("results", []) if data else []

def polygon_get_intraday_bars(ticker: str, from_date: date, to_date: date, multiplier: int = 30) -> List[Dict]:
    data = polygon_request(
        f"/v2/aggs/ticker/{ticker}/range/{multiplier}/minute/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}",
        {"adjusted": "true", "sort": "asc", "limit": 5000}
    )
    return data.get("results", []) if data else []

def build_option_ticker(underlying: str, expiry: date, strike: float, opt_type: str) -> str:
    date_str = expiry.strftime("%y%m%d")
    cp = "C" if opt_type.upper() in ["C", "CALL", "CALLS"] else "P"
    strike_int = int(strike * 1000)
    return f"O:{underlying}{date_str}{cp}{strike_int:08d}"

def get_spy_option_data(spx_entry: float, opt_type: str, expiry: date) -> Optional[OptionData]:
    """Get SPY option data with SPX equivalent pricing."""
    spy_level = spx_entry / 10
    
    # 2 strikes OTM (like your example)
    if opt_type.upper() in ["C", "CALL", "CALLS"]:
        spy_strike = round(spy_level) + 2
        spx_strike = int(round(spx_entry / 5) * 5) + 10
    else:
        spy_strike = round(spy_level) - 2
        spx_strike = int(round(spx_entry / 5) * 5) - 10
    
    ticker = build_option_ticker("SPY", expiry, spy_strike, opt_type)
    
    # Try snapshot endpoint
    data = polygon_request(f"/v3/snapshot/options/{ticker}")
    
    spy_price = 0.0
    delta = 0.0
    iv = 0.0
    
    if data and data.get("results"):
        snap = data["results"]
        greeks = snap.get("greeks", {})
        day = snap.get("day", {})
        quote = snap.get("last_quote", {})
        
        delta = greeks.get("delta", 0)
        iv = snap.get("implied_volatility", 0)
        
        # Get price: try quote first, then day close
        bid = quote.get("bid", 0)
        ask = quote.get("ask", 0)
        if bid and ask:
            spy_price = (bid + ask) / 2
        else:
            spy_price = day.get("close", 0)
    
    if spy_price == 0:
        # Fallback: try prev day close
        prev_data = polygon_request(f"/v2/aggs/ticker/{ticker}/prev")
        if prev_data and prev_data.get("results"):
            spy_price = prev_data["results"][0].get("c", 0)
    
    if spy_price == 0:
        return None
    
    # Calculate SPX equivalent using OTM distance ratio
    spy_otm = abs(spy_strike - spy_level)
    spx_otm = abs(spx_strike - spx_entry)
    multiplier = spx_otm / spy_otm if spy_otm > 0 else 10
    spx_price_est = spy_price * multiplier
    
    return OptionData(
        spy_strike=spy_strike,
        spy_price=round(spy_price, 2),
        spx_strike=spx_strike,
        spx_price_est=round(spx_price_est, 2),
        delta=delta,
        iv=iv,
        in_sweet_spot=(PREMIUM_SWEET_LOW <= spy_price <= PREMIUM_SWEET_HIGH)
    )

def get_open_interest_levels(expiry: date, spy_price: float) -> List[Dict]:
    data = polygon_request(
        "/v3/reference/options/contracts",
        {"underlying_ticker": "SPY", "expiration_date": expiry.strftime("%Y-%m-%d"),
         "strike_price.gte": spy_price - 15, "strike_price.lte": spy_price + 15, "limit": 50}
    )
    if not data:
        return []
    
    oi_levels = []
    for c in data.get("results", [])[:30]:
        ticker = c.get("ticker")
        snap_data = polygon_request(f"/v3/snapshot/options/{ticker}")
        if snap_data and snap_data.get("results"):
            oi = snap_data["results"].get("open_interest", 0)
            if oi > 5000:
                oi_levels.append({
                    "spy_strike": c.get("strike_price", 0),
                    "spx_equiv": c.get("strike_price", 0) * 10,
                    "type": c.get("contract_type", ""),
                    "oi": oi
                })
    
    oi_levels.sort(key=lambda x: x["oi"], reverse=True)
    return oi_levels[:10]


# =============================================================================
# VIX, PIVOTS, CONES
# =============================================================================

def analyze_vix_zone(vix_bottom: float, vix_top: float, vix_current: float, cones: List[Cone] = None) -> VIXZone:
    zone = VIXZone(bottom=vix_bottom, top=vix_top, current=vix_current)
    
    if vix_bottom <= 0 or vix_top <= 0:
        zone.bias = "WAIT"
        zone.bias_reason = "VIX zone not set"
        return zone
    
    zone.zone_size = round(vix_top - vix_bottom, 2)
    zone.expected_spx_move = zone.zone_size * VIX_TO_SPX_MULTIPLIER
    
    if vix_current < vix_bottom:
        zones_below = (vix_bottom - vix_current) / zone.zone_size if zone.zone_size > 0 else 0
        zone.zones_away = -int(np.ceil(zones_below))
        zone.position_pct = 0
        zone.bias = "CALLS"
        zone.bias_reason = f"VIX {abs(zone.zones_away)} zone(s) below → return to {vix_bottom:.2f} → SPX UP"
    elif vix_current > vix_top:
        zones_above = (vix_current - vix_top) / zone.zone_size if zone.zone_size > 0 else 0
        zone.zones_away = int(np.ceil(zones_above))
        zone.position_pct = 100
        zone.bias = "PUTS"
        zone.bias_reason = f"VIX {zone.zones_away} zone(s) above → return to {vix_top:.2f} → SPX DOWN"
    else:
        zone.zones_away = 0
        zone.position_pct = ((vix_current - vix_bottom) / zone.zone_size * 100) if zone.zone_size > 0 else 50
        if zone.position_pct >= 75:
            zone.bias = "CALLS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (top 25%) → expect fall → SPX UP"
        elif zone.position_pct <= 25:
            zone.bias = "PUTS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (bottom 25%) → expect rise → SPX DOWN"
        else:
            zone.bias = "WAIT"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (middle) → no clear edge"
    
    # Match to nearest cone rail
    if cones and zone.bias in ["CALLS", "PUTS"]:
        rails = []
        for c in cones:
            if c.is_tradeable:
                if zone.bias == "CALLS":
                    rails.append((c.descending_rail, c.name))
                else:
                    rails.append((c.ascending_rail, c.name))
        if rails:
            rails.sort(key=lambda x: x[0])
            mid = len(rails) // 2
            zone.matched_rail = rails[mid][0]
            zone.matched_cone = rails[mid][1]
    
    return zone

def detect_pivots_auto(bars: List[Dict], pivot_date: date, close_time: time) -> List[Pivot]:
    if not bars or len(bars) < 3:
        return []
    
    pivots = []
    candles = []
    
    for bar in bars:
        ts = bar.get("t", 0)
        dt = datetime.fromtimestamp(ts / 1000, tz=ET_TZ).astimezone(CT_TZ) if isinstance(ts, int) else ts
        candles.append({
            "time": dt, "open": bar.get("o", 0), "high": bar.get("h", 0),
            "low": bar.get("l", 0), "close": bar.get("c", 0),
            "is_green": bar.get("c", 0) >= bar.get("o", 0)
        })
    
    # HIGH pivots
    high_candidates = []
    for i in range(len(candles) - 1):
        curr, nxt = candles[i], candles[i + 1]
        if curr["is_green"] and not nxt["is_green"] and nxt["close"] < curr["open"]:
            high_candidates.append({"price": curr["high"], "time": curr["time"]})
    
    # LOW pivots
    low_candidates = []
    for i in range(len(candles) - 1):
        curr, nxt = candles[i], candles[i + 1]
        if not curr["is_green"] and nxt["is_green"] and nxt["close"] > curr["open"]:
            low_candidates.append({"price": nxt["open"], "time": curr["time"]})
    
    # Primary HIGH
    if high_candidates:
        high_candidates.sort(key=lambda x: x["price"], reverse=True)
        pivots.append(Pivot(name="Prior High", price=high_candidates[0]["price"],
                           pivot_time=high_candidates[0]["time"], pivot_type="HIGH",
                           candle_high=high_candidates[0]["price"]))
        for i, h in enumerate(high_candidates[1:3], 1):
            pivots.append(Pivot(name=f"High {i+1}", price=h["price"], pivot_time=h["time"],
                               pivot_type="HIGH", is_secondary=True, candle_high=h["price"]))
    
    # Primary LOW
    if low_candidates:
        low_candidates.sort(key=lambda x: x["price"])
        pivots.append(Pivot(name="Prior Low", price=low_candidates[0]["price"],
                           pivot_time=low_candidates[0]["time"], pivot_type="LOW",
                           candle_open=low_candidates[0]["price"]))
        for i, l in enumerate(low_candidates[1:3], 1):
            pivots.append(Pivot(name=f"Low {i+1}", price=l["price"], pivot_time=l["time"],
                               pivot_type="LOW", is_secondary=True, candle_open=l["price"]))
    
    # CLOSE
    if candles:
        pivots.append(Pivot(name="Prior Close", price=candles[-1]["close"],
                           pivot_time=CT_TZ.localize(datetime.combine(pivot_date, close_time)),
                           pivot_type="CLOSE"))
    
    return pivots

def create_manual_pivots(high_price, high_time_str, low_price, low_time_str, close_price,
                         pivot_date, close_time, secondary_highs=None, secondary_lows=None) -> List[Pivot]:
    def parse_t(s):
        try:
            parts = s.replace(" ", "").split(":")
            return time(int(parts[0]), int(parts[1]))
        except:
            return time(12, 0)
    
    pivots = []
    if high_price > 0:
        pivots.append(Pivot(name="Prior High", price=high_price,
                           pivot_time=CT_TZ.localize(datetime.combine(pivot_date, parse_t(high_time_str))),
                           pivot_type="HIGH", candle_high=high_price))
    if low_price > 0:
        pivots.append(Pivot(name="Prior Low", price=low_price,
                           pivot_time=CT_TZ.localize(datetime.combine(pivot_date, parse_t(low_time_str))),
                           pivot_type="LOW", candle_open=low_price))
    if close_price > 0:
        pivots.append(Pivot(name="Prior Close", price=close_price,
                           pivot_time=CT_TZ.localize(datetime.combine(pivot_date, close_time)),
                           pivot_type="CLOSE"))
    
    if secondary_highs:
        for i, (p, t) in enumerate(secondary_highs, 1):
            if p > 0:
                pivots.append(Pivot(name=f"High {i+1}", price=p,
                                   pivot_time=CT_TZ.localize(datetime.combine(pivot_date, parse_t(t))),
                                   pivot_type="HIGH", is_secondary=True, candle_high=p))
    if secondary_lows:
        for i, (p, t) in enumerate(secondary_lows, 1):
            if p > 0:
                pivots.append(Pivot(name=f"Low {i+1}", price=p,
                                   pivot_time=CT_TZ.localize(datetime.combine(pivot_date, parse_t(t))),
                                   pivot_type="LOW", is_secondary=True, candle_open=p))
    return pivots

def count_blocks(start_time: datetime, eval_time: datetime) -> int:
    if eval_time <= start_time:
        return 0
    
    MAINT_START, MAINT_END = time(16, 0), time(17, 0)
    if start_time.tzinfo is None:
        start_time = CT_TZ.localize(start_time)
    if eval_time.tzinfo is None:
        eval_time = CT_TZ.localize(eval_time)
    
    blocks = 0
    current = start_time
    
    for _ in range(2000):
        if current >= eval_time:
            break
        wd, ct = current.weekday(), current.time()
        
        if wd >= 5:
            current = CT_TZ.localize(datetime.combine(
                current.date() + timedelta(days=(7 - wd) if wd == 5 else 1), MAINT_END))
            continue
        if MAINT_START <= ct < MAINT_END:
            current = CT_TZ.localize(datetime.combine(current.date(), MAINT_END))
            continue
        if wd == 4 and ct >= MAINT_START:
            current = CT_TZ.localize(datetime.combine(current.date() + timedelta(days=2), MAINT_END))
            continue
        
        next_block = current + timedelta(minutes=30)
        if next_block > eval_time:
            break
        if ct < MAINT_START and next_block.time() >= MAINT_START:
            blocks += 1
            current = CT_TZ.localize(datetime.combine(current.date(), MAINT_END))
            continue
        
        blocks += 1
        current = next_block
    
    return max(blocks, 1)

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    cones = []
    for pivot in pivots:
        if pivot.price <= 0 or pivot.pivot_time is None:
            continue
        
        blocks = count_blocks(pivot.pivot_time + timedelta(minutes=30), eval_time)
        exp = blocks * SLOPE_PER_30MIN
        
        if pivot.pivot_type == "HIGH":
            base = pivot.candle_high if pivot.candle_high > 0 else pivot.price
            asc, desc = base + exp, pivot.price - exp
        elif pivot.pivot_type == "LOW":
            base = pivot.candle_open if pivot.candle_open > 0 else pivot.price
            asc, desc = pivot.price + exp, base - exp
        else:
            asc, desc = pivot.price + exp, pivot.price - exp
        
        width = asc - desc
        cones.append(Cone(name=pivot.name, pivot=pivot, ascending_rail=round(asc, 2),
                         descending_rail=round(desc, 2), width=round(width, 2),
                         blocks=blocks, is_tradeable=(width >= MIN_CONE_WIDTH)))
    return cones

def build_pivot_table(pivots: List[Pivot], trading_date: date) -> List[PivotTableRow]:
    rows = []
    time_blocks = [("8:30 AM", time(8, 30)), ("9:00 AM", time(9, 0)), ("9:30 AM", time(9, 30)),
                   ("10:00 AM", time(10, 0)), ("10:30 AM", time(10, 30)), ("11:00 AM", time(11, 0)),
                   ("11:30 AM", time(11, 30)), ("12:00 PM", time(12, 0))]
    
    high_p = next((p for p in pivots if p.name == "Prior High"), None)
    low_p = next((p for p in pivots if p.name == "Prior Low"), None)
    close_p = next((p for p in pivots if p.name == "Prior Close"), None)
    
    for label, t in time_blocks:
        eval_dt = CT_TZ.localize(datetime.combine(trading_date, t))
        row = PivotTableRow(time_block=label, time_ct=t)
        
        for piv, attr_asc, attr_desc in [(high_p, "prior_high_asc", "prior_high_desc"),
                                          (low_p, "prior_low_asc", "prior_low_desc"),
                                          (close_p, "prior_close_asc", "prior_close_desc")]:
            if piv and piv.pivot_time:
                blocks = count_blocks(piv.pivot_time + timedelta(minutes=30), eval_dt)
                exp = blocks * SLOPE_PER_30MIN
                if piv.pivot_type == "HIGH":
                    base = piv.candle_high if piv.candle_high > 0 else piv.price
                    setattr(row, attr_asc, round(base + exp, 2))
                    setattr(row, attr_desc, round(piv.price - exp, 2))
                elif piv.pivot_type == "LOW":
                    base = piv.candle_open if piv.candle_open > 0 else piv.price
                    setattr(row, attr_asc, round(piv.price + exp, 2))
                    setattr(row, attr_desc, round(base - exp, 2))
                else:
                    setattr(row, attr_asc, round(piv.price + exp, 2))
                    setattr(row, attr_desc, round(piv.price - exp, 2))
        rows.append(row)
    return rows


# =============================================================================
# SETUP GENERATION WITH PROFIT TARGETS
# =============================================================================

def generate_setups(cones: List[Cone], current_price: float, expiry: date, is_after_cutoff: bool = False) -> List[TradeSetup]:
    """Generate trade setups with profit estimates at 25%, 50%, 75% targets."""
    
    setups = []
    
    for cone in cones:
        if not cone.is_tradeable:
            continue
        
        # ===== CALLS (enter at descending rail) =====
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        stop_c = round(entry_c - STOP_LOSS_PTS, 2)
        t25_c = round(entry_c + cone.width * 0.25, 2)
        t50_c = round(entry_c + cone.width * 0.50, 2)
        t75_c = round(entry_c + cone.width * 0.75, 2)
        
        opt_c = get_spy_option_data(entry_c, "C", expiry)
        status_c = "GREY" if is_after_cutoff else ("ACTIVE" if dist_c <= RAIL_PROXIMITY else "WAIT")
        
        # Calculate profit estimates
        # Profit = (target move in SPX points) × delta × 100 (per contract)
        delta_c = abs(opt_c.delta) if opt_c and opt_c.delta != 0 else DELTA_IDEAL
        
        move_25 = cone.width * 0.25
        move_50 = cone.width * 0.50
        move_75 = cone.width * 0.75
        
        profit_25_c = round(move_25 * delta_c * 100, 0)
        profit_50_c = round(move_50 * delta_c * 100, 0)
        profit_75_c = round(move_75 * delta_c * 100, 0)
        risk_c = round(STOP_LOSS_PTS * delta_c * 100, 0)
        
        setups.append(TradeSetup(
            direction="CALLS", cone_name=cone.name, cone_width=cone.width,
            entry=entry_c, stop=stop_c, target_25=t25_c, target_50=t50_c, target_75=t75_c,
            distance=round(dist_c, 1), option=opt_c,
            profit_25=profit_25_c, profit_50=profit_50_c, profit_75=profit_75_c,
            risk_dollars=risk_c, status=status_c
        ))
        
        # ===== PUTS (enter at ascending rail) =====
        entry_p = cone.ascending_rail
        dist_p = abs(current_price - entry_p)
        stop_p = round(entry_p + STOP_LOSS_PTS, 2)
        t25_p = round(entry_p - cone.width * 0.25, 2)
        t50_p = round(entry_p - cone.width * 0.50, 2)
        t75_p = round(entry_p - cone.width * 0.75, 2)
        
        opt_p = get_spy_option_data(entry_p, "P", expiry)
        status_p = "GREY" if is_after_cutoff else ("ACTIVE" if dist_p <= RAIL_PROXIMITY else "WAIT")
        
        delta_p = abs(opt_p.delta) if opt_p and opt_p.delta != 0 else DELTA_IDEAL
        
        profit_25_p = round(move_25 * delta_p * 100, 0)
        profit_50_p = round(move_50 * delta_p * 100, 0)
        profit_75_p = round(move_75 * delta_p * 100, 0)
        risk_p = round(STOP_LOSS_PTS * delta_p * 100, 0)
        
        setups.append(TradeSetup(
            direction="PUTS", cone_name=cone.name, cone_width=cone.width,
            entry=entry_p, stop=stop_p, target_25=t25_p, target_50=t50_p, target_75=t75_p,
            distance=round(dist_p, 1), option=opt_p,
            profit_25=profit_25_p, profit_50=profit_50_p, profit_75=profit_75_p,
            risk_dollars=risk_p, status=status_p
        ))
    
    return setups

def calculate_day_score(vix_zone: VIXZone, cones: List[Cone], setups: List[TradeSetup], current_price: float) -> DayScore:
    score = DayScore()
    
    # 1. VIX-Cone Alignment (25 pts)
    if vix_zone.bias in ["CALLS", "PUTS"]:
        aligned = any(s.direction == vix_zone.bias and s.distance <= 10 for s in setups)
        score.vix_cone_alignment = 25 if aligned else 10 if any(s.direction == vix_zone.bias for s in setups) else 0
    
    # 2. VIX Clarity (25 pts)
    if vix_zone.bias == "WAIT":
        score.vix_clarity = 0
    elif vix_zone.position_pct >= 75 or vix_zone.position_pct <= 25 or vix_zone.zones_away != 0:
        score.vix_clarity = 25
    elif 60 <= vix_zone.position_pct or vix_zone.position_pct <= 40:
        score.vix_clarity = 15
    else:
        score.vix_clarity = 5
    
    # 3. Cone Width (20 pts)
    tradeable = [c for c in cones if c.is_tradeable]
    if tradeable:
        best = max(c.width for c in tradeable)
        score.cone_width = 20 if best >= 30 else 15 if best >= 25 else 10 if best >= 20 else 5
    
    # 4. Premium Quality (15 pts)
    sweet = sum(1 for s in setups if s.option and s.option.in_sweet_spot)
    score.premium_quality = 15 if sweet >= 3 else 10 if sweet >= 1 else 5
    
    # 5. Confluence (15 pts)
    rails = []
    for c in tradeable:
        rails.extend([c.ascending_rail, c.descending_rail])
    confluence = any(abs(r1 - r2) <= 5 for i, r1 in enumerate(rails) for r2 in rails[i+1:])
    score.confluence = 15 if confluence else 0
    
    score.total = score.vix_cone_alignment + score.vix_clarity + score.cone_width + score.premium_quality + score.confluence
    
    if score.total >= 80:
        score.grade, score.color = "A", "#10b981"
    elif score.total >= 60:
        score.grade, score.color = "B", "#3b82f6"
    elif score.total >= 40:
        score.grade, score.color = "C", "#f59e0b"
    else:
        score.grade, score.color = "D", "#ef4444"
    
    return score

def check_alerts(setups: List[TradeSetup], vix_zone: VIXZone, current_time: time) -> List[Dict]:
    alerts = []
    
    for s in setups:
        if s.status == "ACTIVE":
            alerts.append({"priority": "HIGH", "message": f"🎯 {s.direction} at {s.cone_name} ACTIVE! Entry: {s.entry:,.2f}"})
        elif 5 < s.distance <= 15 and s.status != "GREY":
            alerts.append({"priority": "MEDIUM", "message": f"⚠️ {s.direction} {s.cone_name} approaching ({s.distance:.0f} pts)"})
    
    if vix_zone.zones_away != 0:
        alerts.append({"priority": "HIGH", "message": f"📊 VIX {abs(vix_zone.zones_away)} zone(s) {'above' if vix_zone.zones_away > 0 else 'below'}"})
    
    if INST_WINDOW_START <= current_time <= INST_WINDOW_END:
        alerts.append({"priority": "INFO", "message": "🏛️ Institutional Window (9:00-9:30 CT)"})
    
    return alerts


# =============================================================================
# UI GENERATION - UPDATED COLUMNS
# =============================================================================

def render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score, 
                     oi_levels, alerts, spx_price, trading_date, is_historical, theme):
    
    # Theme
    if theme == "dark":
        bg, bg2, card_bg = "#0a0a0f", "#12121a", "rgba(25,25,35,0.8)"
        text1, text2, text3 = "#ffffff", "#9ca3af", "#6b7280"
        border, shadow = "rgba(255,255,255,0.08)", "rgba(0,0,0,0.5)"
    else:
        bg, bg2, card_bg = "#f8fafc", "#f1f5f9", "rgba(255,255,255,0.8)"
        text1, text2, text3 = "#0f172a", "#475569", "#94a3b8"
        border, shadow = "rgba(0,0,0,0.08)", "rgba(0,0,0,0.1)"
    
    green, red, amber, blue, purple = "#10b981", "#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6"
    
    bias_color = green if vix_zone.bias == "CALLS" else red if vix_zone.bias == "PUTS" else amber
    bias_icon = "▲" if vix_zone.bias == "CALLS" else "▼" if vix_zone.bias == "PUTS" else "●"
    
    now = get_ct_now()
    time_to_910 = get_time_until(ENTRY_TARGET)
    time_to_1130 = get_time_until(CUTOFF_TIME)
    marker_pos = min(max(vix_zone.position_pct, 5), 95) if vix_zone.zone_size > 0 else 50
    
    html = f'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Inter',sans-serif; background:{bg}; color:{text1}; padding:20px; }}
.container {{ max-width:1600px; margin:0 auto; }}
.glass {{ background:{card_bg}; backdrop-filter:blur(20px); border:1px solid {border}; border-radius:20px; padding:20px; margin-bottom:16px; }}
.section-header {{ display:flex; justify-content:space-between; align-items:center; cursor:pointer; margin-bottom:12px; }}
.section-title {{ font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:2px; color:{text3}; }}
.toggle {{ font-size:14px; color:{text3}; }}
.collapsed .content {{ display:none; }}
.header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:12px; }}
.logo {{ display:flex; align-items:center; gap:10px; }}
.logo-icon {{ width:48px; height:48px; background:linear-gradient(135deg,{blue},{purple}); border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:16px; font-weight:800; color:white; }}
.logo h1 {{ font-size:22px; font-weight:800; }}
.tagline {{ font-size:11px; color:{text2}; font-style:italic; }}
.header-right {{ display:flex; align-items:center; gap:16px; }}
.time-display {{ font-family:'JetBrains Mono'; font-size:24px; font-weight:600; }}
.countdown {{ text-align:right; }}
.countdown-label {{ font-size:9px; text-transform:uppercase; letter-spacing:1px; color:{text3}; }}
.countdown-value {{ font-family:'JetBrains Mono'; font-size:14px; color:{amber}; }}
.banner {{ padding:14px 18px; border-radius:12px; display:flex; align-items:center; gap:14px; margin-bottom:14px; }}
.banner-hist {{ background:linear-gradient(135deg,{purple}30,{purple}10); border:2px solid {purple}50; }}
.banner-inst {{ background:linear-gradient(135deg,{amber}30,{amber}10); border:2px solid {amber}50; animation:pulse 2s infinite; }}
@keyframes pulse {{ 0%,100%{{opacity:1;}} 50%{{opacity:0.7;}} }}
.banner-icon {{ font-size:24px; }}
.banner-title {{ font-weight:700; font-size:14px; }}
.banner-sub {{ font-size:11px; color:{text2}; }}
.grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
.grid-4 {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }}
@media(max-width:900px) {{ .grid-2,.grid-4 {{ grid-template-columns:1fr; }} }}
.vix-ladder {{ position:relative; height:70px; background:rgba(255,255,255,0.03); border-radius:10px; margin:12px 0; }}
.vix-bar {{ position:absolute; left:16px; right:16px; height:28px; top:50%; transform:translateY(-50%); background:linear-gradient(90deg,{green}40,{bg2},{bg2},{red}40); border-radius:14px; }}
.vix-marker {{ position:absolute; width:18px; height:18px; background:{bias_color}; border-radius:50%; top:50%; transform:translate(-50%,-50%); box-shadow:0 0 16px {bias_color}; border:2px solid {card_bg}; z-index:10; }}
.vix-labels {{ position:absolute; bottom:6px; left:16px; right:16px; display:flex; justify-content:space-between; font-family:'JetBrains Mono'; font-size:10px; color:{text3}; }}
.bias-card {{ text-align:center; padding:24px; background:linear-gradient(135deg,{bias_color}20,{bias_color}05); border:2px solid {bias_color}50; }}
.bias-icon {{ font-size:40px; color:{bias_color}; text-shadow:0 0 24px {bias_color}; }}
.bias-label {{ font-size:24px; font-weight:800; color:{bias_color}; letter-spacing:2px; margin-top:6px; }}
.bias-reason {{ font-size:12px; color:{text2}; margin-top:10px; }}
.bias-match {{ font-size:11px; color:{blue}; margin-top:6px; }}
.score-circle {{ width:90px; height:90px; border-radius:50%; margin:0 auto 12px; display:flex; flex-direction:column; align-items:center; justify-content:center; font-family:'JetBrains Mono'; border:4px solid; }}
.score-value {{ font-size:28px; font-weight:700; }}
.score-grade {{ font-size:12px; font-weight:600; }}
.stat {{ background:rgba(255,255,255,0.03); border-radius:10px; padding:14px; text-align:center; }}
.stat-value {{ font-family:'JetBrains Mono'; font-size:18px; font-weight:600; }}
.stat-label {{ font-size:9px; text-transform:uppercase; letter-spacing:1px; color:{text3}; margin-top:3px; }}
table {{ width:100%; border-collapse:collapse; }}
th {{ font-size:9px; font-weight:600; text-transform:uppercase; letter-spacing:1px; color:{text3}; padding:10px 6px; text-align:left; border-bottom:1px solid {border}; }}
td {{ padding:12px 6px; font-size:12px; border-bottom:1px solid {border}; }}
tr:hover {{ background:rgba(255,255,255,0.02); }}
tr.active {{ background:linear-gradient(90deg,{green}20,transparent); animation:glow 2s infinite; }}
tr.grey {{ opacity:0.4; }}
@keyframes glow {{ 0%,100%{{opacity:1;}} 50%{{opacity:0.6;}} }}
.mono {{ font-family:'JetBrains Mono'; }}
.green {{ color:{green}; }}
.red {{ color:{red}; }}
.amber {{ color:{amber}; }}
.blue {{ color:{blue}; }}
.pill {{ display:inline-block; padding:3px 10px; border-radius:100px; font-size:10px; font-weight:600; font-family:'JetBrains Mono'; }}
.pill-green {{ background:{green}20; color:{green}; }}
.pill-red {{ background:{red}20; color:{red}; }}
.pill-amber {{ background:{amber}20; color:{amber}; }}
.pill-grey {{ background:rgba(107,114,128,0.2); color:#6b7280; }}
.sweet {{ color:{green}; }}
.sweet::before {{ content:"★ "; }}
.alert {{ padding:10px 14px; border-radius:8px; margin-bottom:6px; font-size:12px; }}
.alert-HIGH {{ background:{red}15; border-left:3px solid {red}; }}
.alert-MEDIUM {{ background:{amber}15; border-left:3px solid {amber}; }}
.alert-INFO {{ background:{blue}15; border-left:3px solid {blue}; }}
.footer {{ text-align:center; padding:24px; color:{text3}; font-size:10px; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
    <div class="logo">
        <div class="logo-icon">SP</div>
        <div><h1>SPX Prophet v6.2</h1><div class="tagline">Where Structure Becomes Foresight</div></div>
    </div>
    <div class="header-right">
        <div class="countdown"><div class="countdown-label">To 9:10 AM</div><div class="countdown-value">{format_countdown(time_to_910)}</div></div>
        <div class="countdown"><div class="countdown-label">To 11:30 Cutoff</div><div class="countdown-value">{format_countdown(time_to_1130)}</div></div>
        <div class="time-display">{now.strftime("%H:%M")} CT</div>
    </div>
</div>
'''
    
    # Historical banner
    if is_historical:
        html += f'<div class="banner banner-hist"><div class="banner-icon">📅</div><div><div class="banner-title" style="color:{purple}">Historical: {trading_date.strftime("%A, %B %d, %Y")}</div></div></div>'
    
    # Institutional window
    is_inst = INST_WINDOW_START <= now.time() <= INST_WINDOW_END
    if is_inst and not is_historical:
        html += f'<div class="banner banner-inst"><div class="banner-icon">🏛️</div><div><div class="banner-title" style="color:{amber}">INSTITUTIONAL WINDOW ACTIVE</div><div class="banner-sub">9:00 - 9:30 AM CT</div></div></div>'
    
    # Alerts
    if alerts:
        html += '<div class="glass" style="padding:14px;">'
        for a in alerts[:4]:
            html += f'<div class="alert alert-{a["priority"]}">{a["message"]}</div>'
        html += '</div>'
    
    # VIX Zone
    html += f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title">📊 VIX ZONE ANALYSIS</div><span class="toggle">▼</span>
    </div>
    <div class="content">
        <div class="grid-2">
            <div>
                <div class="vix-ladder">
                    <div class="vix-bar"></div>
                    <div class="vix-marker" style="left:{marker_pos}%;"></div>
                    <div class="vix-labels"><span>{vix_zone.bottom:.2f}</span><span>Zone: {vix_zone.zone_size:.2f}</span><span>{vix_zone.top:.2f}</span></div>
                </div>
                <div class="grid-4">
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
                {"<div class='bias-match'>Matched: " + vix_zone.matched_cone + " @ " + f"{vix_zone.matched_rail:,.2f}" + "</div>" if vix_zone.matched_rail > 0 else ""}
            </div>
        </div>
    </div>
</div>
'''
    
    # Setup tables - NEW COLUMNS
    def render_setup_table(direction, setups_list, color):
        icon = "▲" if direction == "CALLS" else "▼"
        filtered = [s for s in setups_list if s.direction == direction]
        
        h = f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title" style="color:{color}">{icon} {direction} SETUPS</div><span class="toggle">▼</span>
    </div>
    <div class="content">
        <table>
            <thead><tr>
                <th>Cone</th><th>SPX Entry</th><th>SPY Strike</th><th>SPY $</th>
                <th>SPX Est $</th><th>Delta</th><th>IV</th>
                <th>Stop</th><th>T25%</th><th>T50%</th><th>T75%</th>
                <th>Est +25%</th><th>Est +50%</th><th>Est +75%</th><th>Risk</th><th>Status</th>
            </tr></thead>
            <tbody>
'''
        for s in filtered:
            row_class = "active" if s.status == "ACTIVE" else "grey" if s.status == "GREY" else ""
            opt = s.option
            
            if opt:
                spy_strike = f"{int(opt.spy_strike)}{s.direction[0]}"
                spy_price = f"${opt.spy_price:.2f}"
                spx_est = f"${opt.spx_price_est:.0f}"
                delta = f"{abs(opt.delta):.2f}" if opt.delta else "--"
                iv = f"{opt.iv*100:.0f}%" if opt.iv else "--"
                sweet_cls = "sweet" if opt.in_sweet_spot else ""
            else:
                spy_strike = spy_price = spx_est = delta = iv = "--"
                sweet_cls = ""
            
            status = f'<span class="pill pill-green">🎯 ACTIVE</span>' if s.status == "ACTIVE" else \
                     f'<span class="pill pill-grey">CLOSED</span>' if s.status == "GREY" else \
                     f'<span class="pill pill-amber">{s.distance:.0f} pts</span>'
            
            entry_cls = "green" if direction == "CALLS" else "red"
            
            h += f'''<tr class="{row_class}">
                <td><strong>{s.cone_name}</strong></td>
                <td class="mono {entry_cls}">{s.entry:,.2f}</td>
                <td class="mono {sweet_cls}">{spy_strike}</td>
                <td class="mono">{spy_price}</td>
                <td class="mono">{spx_est}</td>
                <td class="mono">{delta}</td>
                <td class="mono">{iv}</td>
                <td class="mono red">{s.stop:,.2f}</td>
                <td class="mono">{s.target_25:,.2f}</td>
                <td class="mono">{s.target_50:,.2f}</td>
                <td class="mono">{s.target_75:,.2f}</td>
                <td class="mono green">+${s.profit_25:,.0f}</td>
                <td class="mono green">+${s.profit_50:,.0f}</td>
                <td class="mono green">+${s.profit_75:,.0f}</td>
                <td class="mono red">-${s.risk_dollars:,.0f}</td>
                <td>{status}</td>
            </tr>'''
        
        h += '</tbody></table></div></div>'
        return h
    
    html += render_setup_table("CALLS", setups, green)
    html += render_setup_table("PUTS", setups, red)
    
    # Prior Session
    html += f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title">📈 PRIOR SESSION</div><span class="toggle">▼</span>
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
        <div class="section-title">🎯 DAY SCORE</div><span class="toggle">▼</span>
    </div>
    <div class="content">
        <div class="grid-2">
            <div style="text-align:center;">
                <div class="score-circle" style="border-color:{day_score.color}; color:{day_score.color};">
                    <div class="score-value">{day_score.total}</div>
                    <div class="score-grade">Grade {day_score.grade}</div>
                </div>
                <div style="font-size:12px; color:{text2};">
                    {"🟢 Excellent" if day_score.total >= 80 else "🔵 Good" if day_score.total >= 60 else "🟠 Marginal" if day_score.total >= 40 else "🔴 Skip"}
                </div>
            </div>
            <div class="grid-2" style="gap:8px;">
                <div class="stat"><div class="stat-value">{day_score.vix_cone_alignment}/25</div><div class="stat-label">VIX-Cone</div></div>
                <div class="stat"><div class="stat-value">{day_score.vix_clarity}/25</div><div class="stat-label">Clarity</div></div>
                <div class="stat"><div class="stat-value">{day_score.cone_width}/20</div><div class="stat-label">Width</div></div>
                <div class="stat"><div class="stat-value">{day_score.premium_quality}/15</div><div class="stat-label">Premium</div></div>
            </div>
        </div>
    </div>
</div>
'''
    
    # Structural Cones
    html += f'''
<div class="glass">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title">📐 STRUCTURAL CONES</div><span class="toggle">▼</span>
    </div>
    <div class="content">
        <table>
            <thead><tr><th>Pivot</th><th>Ascending (PUTS)</th><th>Descending (CALLS)</th><th>Width</th><th>Blocks</th><th>Tradeable</th></tr></thead>
            <tbody>
'''
    for c in cones:
        width_cls = "green" if c.width >= 25 else "amber" if c.width >= MIN_CONE_WIDTH else "red"
        trade_pill = f'<span class="pill pill-green">YES</span>' if c.is_tradeable else f'<span class="pill pill-red">NO</span>'
        html += f'<tr><td><strong>{c.name}</strong></td><td class="mono red">{c.ascending_rail:,.2f}</td><td class="mono green">{c.descending_rail:,.2f}</td><td class="mono {width_cls}">{c.width:.0f}</td><td class="mono">{c.blocks}</td><td>{trade_pill}</td></tr>'
    html += '</tbody></table></div></div>'
    
    # Pivot Table
    html += f'''
<div class="glass collapsed">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title">📋 PIVOT TABLE (8:30AM - 12PM CT)</div><span class="toggle">▼</span>
    </div>
    <div class="content">
        <table>
            <thead><tr><th>Time</th><th>High ▲</th><th>High ▼</th><th>Low ▲</th><th>Low ▼</th><th>Close ▲</th><th>Close ▼</th></tr></thead>
            <tbody>
'''
    for row in pivot_table:
        is_inst_row = INST_WINDOW_START <= row.time_ct <= INST_WINDOW_END
        style = f'background:{amber}10;' if is_inst_row else ""
        html += f'<tr style="{style}"><td><strong>{row.time_block}</strong>{"🏛️" if is_inst_row else ""}</td><td class="mono red">{row.prior_high_asc:,.2f}</td><td class="mono green">{row.prior_high_desc:,.2f}</td><td class="mono red">{row.prior_low_asc:,.2f}</td><td class="mono green">{row.prior_low_desc:,.2f}</td><td class="mono red">{row.prior_close_asc:,.2f}</td><td class="mono green">{row.prior_close_desc:,.2f}</td></tr>'
    html += '</tbody></table></div></div>'
    
    # OI Levels
    if oi_levels:
        html += f'''
<div class="glass collapsed">
    <div class="section-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="section-title">🎯 OPEN INTEREST MAGNETS</div><span class="toggle">▼</span>
    </div>
    <div class="content">
        <table><thead><tr><th>SPY Strike</th><th>SPX Equiv</th><th>Type</th><th>OI</th></tr></thead><tbody>
'''
        for oi in oi_levels[:8]:
            t_cls = "green" if oi["type"] == "call" else "red"
            html += f'<tr><td class="mono">{oi["spy_strike"]}</td><td class="mono">{oi["spx_equiv"]:,.0f}</td><td class="{t_cls}">{oi["type"].upper()}</td><td class="mono">{oi["oi"]:,}</td></tr>'
        html += '</tbody></table></div></div>'
    
    # Footer
    html += f'''
<div class="footer">SPX Prophet v6.2 • "Where Structure Becomes Foresight" • Data via Polygon.io</div>
</div></body></html>
'''
    return html


# =============================================================================
# STREAMLIT MAIN APPLICATION
# =============================================================================

def main():
    st.set_page_config(page_title="SPX Prophet v6.2", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
    
    # Session state
    defaults = {
        'theme': 'light', 'vix_bottom': 0.0, 'vix_top': 0.0, 'vix_current': 0.0,
        'use_manual_pivots': False, 'high_price': 0.0, 'high_time': "10:30",
        'low_price': 0.0, 'low_time': "14:00", 'close_price': 0.0,
        'sec_highs': [], 'sec_lows': [], 'trading_date': None, 'last_refresh': None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 📈 SPX Prophet v6.2")
        st.markdown("*Legendary Edition*")
        st.divider()
        
        theme = st.radio("🎨 Theme", ["Light", "Dark"], horizontal=True, index=0 if st.session_state.theme == "light" else 1)
        st.session_state.theme = theme.lower()
        
        st.divider()
        st.markdown("### 📅 Trading Date")
        
        today = get_ct_now().date()
        next_trade = get_next_trading_day(today)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📍 Next Trade", use_container_width=True):
                st.session_state.trading_date = next_trade
        with col2:
            if st.button("📆 Yesterday", use_container_width=True):
                st.session_state.trading_date = get_prior_trading_day(today)
        
        selected_date = st.date_input("Select Date", value=st.session_state.trading_date or next_trade,
                                       min_value=today - timedelta(days=730), max_value=today + timedelta(days=7))
        st.session_state.trading_date = selected_date
        
        if is_holiday(selected_date):
            st.warning(f"🚫 {HOLIDAYS_2025.get(selected_date, 'Holiday')} - Closed")
        elif is_half_day(selected_date):
            st.info(f"⏰ {HALF_DAYS_2025.get(selected_date, 'Half day')} - 12pm Close")
        
        st.divider()
        st.markdown("### 📊 VIX Zone (5pm-3am)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input("Bottom", value=st.session_state.vix_bottom, step=0.01, format="%.2f")
        with col2:
            st.session_state.vix_top = st.number_input("Top", value=st.session_state.vix_top, step=0.01, format="%.2f")
        
        st.session_state.vix_current = st.number_input("Current VIX", value=st.session_state.vix_current, step=0.01, format="%.2f")
        
        if st.button("🔄 Fetch VIX"):
            vix = polygon_get_index_price("I:VIX")
            if vix > 0:
                st.session_state.vix_current = round(vix, 2)
                st.success(f"VIX: {vix:.2f}")
        
        st.divider()
        st.markdown("### 📍 Prior Day Pivots")
        
        st.session_state.use_manual_pivots = st.checkbox("Manual Override", st.session_state.use_manual_pivots)
        
        if st.session_state.use_manual_pivots:
            st.markdown("**HIGH** (highest wick)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.high_price = st.number_input("Price##hp", value=st.session_state.high_price, step=0.01, format="%.2f")
            with c2:
                st.session_state.high_time = st.text_input("Time##ht", value=st.session_state.high_time)
            
            st.markdown("**LOW** (open after)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.low_price = st.number_input("Price##lp", value=st.session_state.low_price, step=0.01, format="%.2f")
            with c2:
                st.session_state.low_time = st.text_input("Time##lt", value=st.session_state.low_time)
            
            st.session_state.close_price = st.number_input("Close", value=st.session_state.close_price, step=0.01, format="%.2f")
            
            st.markdown("---")
            st.markdown("**Secondary Pivots**")
            
            num_sh = st.number_input("# Sec Highs", 0, 3, len(st.session_state.sec_highs), key="nsh")
            num_sl = st.number_input("# Sec Lows", 0, 3, len(st.session_state.sec_lows), key="nsl")
            
            while len(st.session_state.sec_highs) < num_sh:
                st.session_state.sec_highs.append([0.0, "11:00"])
            st.session_state.sec_highs = st.session_state.sec_highs[:num_sh]
            
            while len(st.session_state.sec_lows) < num_sl:
                st.session_state.sec_lows.append([0.0, "13:00"])
            st.session_state.sec_lows = st.session_state.sec_lows[:num_sl]
            
            for i in range(num_sh):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.session_state.sec_highs[i][0] = st.number_input(f"H{i+2} Price", value=float(st.session_state.sec_highs[i][0]), step=0.01, format="%.2f", key=f"shp{i}")
                with c2:
                    st.session_state.sec_highs[i][1] = st.text_input(f"H{i+2} Time", value=st.session_state.sec_highs[i][1], key=f"sht{i}")
            
            for i in range(num_sl):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.session_state.sec_lows[i][0] = st.number_input(f"L{i+2} Price", value=float(st.session_state.sec_lows[i][0]), step=0.01, format="%.2f", key=f"slp{i}")
                with c2:
                    st.session_state.sec_lows[i][1] = st.text_input(f"L{i+2} Time", value=st.session_state.sec_lows[i][1], key=f"slt{i}")
        
        st.divider()
        
        if st.button("🔄 REFRESH DATA", use_container_width=True, type="primary"):
            st.session_state.last_refresh = get_ct_now()
            st.rerun()
        
        if st.session_state.last_refresh:
            st.caption(f"Last: {st.session_state.last_refresh.strftime('%H:%M:%S CT')}")
    
    # Main processing
    now = get_ct_now()
    trading_date = st.session_state.trading_date or get_next_trading_day()
    
    if is_holiday(trading_date):
        trading_date = get_next_trading_day(trading_date)
    
    pivot_date = get_prior_trading_day(trading_date)
    pivot_close_time = get_market_close_time(pivot_date)
    
    is_historical = trading_date < now.date() or (trading_date == now.date() and now.time() > CUTOFF_TIME)
    expiry = trading_date
    
    # Prior session
    prior_bars = polygon_get_daily_bars("I:SPX", pivot_date, pivot_date)
    prior_session = {}
    if prior_bars:
        prior_session = {"high": prior_bars[0].get("h", 0), "low": prior_bars[0].get("l", 0),
                         "close": prior_bars[0].get("c", 0), "open": prior_bars[0].get("o", 0)}
    
    # Pivots
    if st.session_state.use_manual_pivots and st.session_state.high_price > 0:
        sec_highs = [(h[0], h[1]) for h in st.session_state.sec_highs if h[0] > 0]
        sec_lows = [(l[0], l[1]) for l in st.session_state.sec_lows if l[0] > 0]
        pivots = create_manual_pivots(st.session_state.high_price, st.session_state.high_time,
                                      st.session_state.low_price, st.session_state.low_time,
                                      st.session_state.close_price, pivot_date, pivot_close_time,
                                      sec_highs, sec_lows)
    else:
        bars_30m = polygon_get_intraday_bars("I:SPX", pivot_date, pivot_date, 30)
        if bars_30m:
            pivots = detect_pivots_auto(bars_30m, pivot_date, pivot_close_time)
        else:
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
    
    # Cones at 9:00 AM
    eval_time = CT_TZ.localize(datetime.combine(trading_date, time(9, 0)))
    cones = build_cones(pivots, eval_time)
    
    # VIX zone
    vix_zone = analyze_vix_zone(st.session_state.vix_bottom, st.session_state.vix_top,
                                 st.session_state.vix_current, cones)
    
    # Current price
    spx_price = polygon_get_index_price("I:SPX")
    if spx_price == 0:
        spx_price = prior_session.get("close", 0)
    
    is_after_cutoff = (trading_date == now.date() and now.time() > CUTOFF_TIME) or is_historical
    
    # Setups
    setups = generate_setups(cones, spx_price, expiry, is_after_cutoff)
    
    # Score
    day_score = calculate_day_score(vix_zone, cones, setups, spx_price)
    
    # Pivot table
    pivot_table = build_pivot_table(pivots, trading_date)
    
    # OI
    spy_price = spx_price / 10 if spx_price > 0 else 600
    oi_levels = get_open_interest_levels(expiry, spy_price) if not is_historical else []
    
    # Alerts
    alerts = check_alerts(setups, vix_zone, now.time()) if not is_historical else []
    
    # Render
    html = render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score,
                            oi_levels, alerts, spx_price, trading_date, is_historical,
                            st.session_state.theme)
    
    components.html(html, height=3200, scrolling=True)


if __name__ == "__main__":
    main()
