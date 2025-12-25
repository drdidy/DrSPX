"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║   SPX PROPHET v6.6 - "Where Structure Becomes Foresight"                      ║
║   Fixed: 15pt OTM from ENTRY RAIL (not current price)                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import numpy as np
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import pytz

# =============================================================================
# CONFIGURATION
# =============================================================================

POLYGON_API_KEY = "jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm"
POLYGON_BASE = "https://api.polygon.io"

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

SLOPE_PER_30MIN = 0.45
MIN_CONE_WIDTH = 18.0
STOP_LOSS_PTS = 6.0
RAIL_PROXIMITY = 5.0

# OTM distance from entry rail to get $4-$8 premium
OTM_DISTANCE_PTS = 15  # 15 points OTM from the entry rail

PREMIUM_SWEET_LOW = 4.00
PREMIUM_SWEET_HIGH = 8.00
DELTA_IDEAL = 0.30  # Typical delta for 15pt OTM
VIX_TO_SPX_MULTIPLIER = 175

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
    # SPY reference (for premium lookup)
    spy_strike: float = 0.0
    spy_price: float = 0.0
    spy_delta: float = 0.0
    # SPX contract you'll actually trade
    spx_strike: int = 0
    spx_price_est: float = 0.0
    otm_distance: float = 0.0  # Distance from entry rail
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

def polygon_get(endpoint: str, params: dict = None) -> Optional[Dict]:
    try:
        if params is None:
            params = {}
        params["apiKey"] = POLYGON_API_KEY
        url = f"{POLYGON_BASE}{endpoint}"
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def polygon_get_daily_bars(ticker: str, from_date: date, to_date: date) -> List[Dict]:
    data = polygon_get(
        f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}",
        {"adjusted": "true", "sort": "asc"}
    )
    return data.get("results", []) if data else []

def polygon_get_intraday_bars(ticker: str, from_date: date, to_date: date, multiplier: int = 30) -> List[Dict]:
    data = polygon_get(
        f"/v2/aggs/ticker/{ticker}/range/{multiplier}/minute/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}",
        {"adjusted": "true", "sort": "asc", "limit": 5000}
    )
    return data.get("results", []) if data else []

def polygon_get_index_price(ticker: str) -> float:
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    data = polygon_get(f"/v2/aggs/ticker/{ticker}/range/1/day/{week_ago}/{today}", {"limit": 5})
    if data and data.get("results"):
        return data["results"][-1].get("c", 0)
    return 0.0

def build_option_ticker(expiry: date, strike: float, opt_type: str) -> str:
    """Build SPY option ticker: O:SPY251226C00600000"""
    date_str = expiry.strftime("%y%m%d")
    cp = "C" if opt_type.upper() in ["C", "CALL", "CALLS"] else "P"
    strike_int = int(strike * 1000)
    return f"O:SPY{date_str}{cp}{strike_int:08d}"

def get_option_data_for_entry(entry_rail: float, opt_type: str, expiry: date) -> Optional[OptionData]:
    """
    Get option data for contracts that will be $4-$8 at ENTRY.
    
    KEY INSIGHT:
    - Entry rail is where SPX will be when you enter
    - You want contracts ~15 pts OTM from that entry point
    - CALLS: Strike ABOVE entry rail (e.g., entry 6050 → strike 6065C)
    - PUTS: Strike BELOW entry rail (e.g., entry 6050 → strike 6035P)
    """
    
    # Calculate SPX strike: 15 pts OTM from entry rail, rounded to $5 increments
    if opt_type.upper() in ["C", "CALL", "CALLS"]:
        # CALLS: Strike ABOVE entry
        spx_strike_raw = entry_rail + OTM_DISTANCE_PTS
        spx_strike = int(round(spx_strike_raw / 5) * 5)  # Round to nearest $5
    else:
        # PUTS: Strike BELOW entry
        spx_strike_raw = entry_rail - OTM_DISTANCE_PTS
        spx_strike = int(round(spx_strike_raw / 5) * 5)
    
    # Calculate actual OTM distance after rounding
    otm_distance = abs(spx_strike - entry_rail)
    
    # Convert to SPY equivalent for price lookup
    # SPY = SPX / 10, SPY strikes are $1 increments
    spy_level = entry_rail / 10
    spy_otm = otm_distance / 10  # Same ratio
    
    if opt_type.upper() in ["C", "CALL", "CALLS"]:
        spy_strike = int(round(spy_level + spy_otm))  # Round to nearest $1
    else:
        spy_strike = int(round(spy_level - spy_otm))
    
    # Build SPY ticker and fetch price
    ticker = build_option_ticker(expiry, spy_strike, opt_type)
    
    spy_price = 0.0
    delta = 0.0
    
    # Try snapshot first
    snapshot_data = polygon_get(f"/v3/snapshot/options/{ticker}")
    if snapshot_data and snapshot_data.get("results"):
        snap = snapshot_data["results"]
        greeks = snap.get("greeks", {})
        delta = greeks.get("delta", 0) or 0
        
        day = snap.get("day", {})
        quote = snap.get("last_quote", {})
        
        if quote.get("bid") and quote.get("ask"):
            spy_price = (quote["bid"] + quote["ask"]) / 2
        elif day.get("close"):
            spy_price = day["close"]
    
    # Fallback to aggregates
    if spy_price == 0:
        from_d = (expiry - timedelta(days=10)).strftime("%Y-%m-%d")
        to_d = expiry.strftime("%Y-%m-%d")
        agg_data = polygon_get(f"/v2/aggs/ticker/{ticker}/range/1/day/{from_d}/{to_d}", {"limit": 10})
        if agg_data and agg_data.get("results"):
            spy_price = agg_data["results"][-1].get("c", 0)
    
    # Fallback: list contracts
    if spy_price == 0:
        contract_type = "call" if opt_type.upper() in ["C", "CALL", "CALLS"] else "put"
        contracts_data = polygon_get("/v3/reference/options/contracts", {
            "underlying_ticker": "SPY",
            "expiration_date": expiry.strftime("%Y-%m-%d"),
            "strike_price": spy_strike,
            "contract_type": contract_type,
            "limit": 1
        })
        if contracts_data and contracts_data.get("results"):
            contract_ticker = contracts_data["results"][0].get("ticker")
            if contract_ticker:
                from_d = (expiry - timedelta(days=10)).strftime("%Y-%m-%d")
                to_d = expiry.strftime("%Y-%m-%d")
                agg_data = polygon_get(f"/v2/aggs/ticker/{contract_ticker}/range/1/day/{from_d}/{to_d}", {"limit": 10})
                if agg_data and agg_data.get("results"):
                    spy_price = agg_data["results"][-1].get("c", 0)
    
    if spy_price == 0:
        return None
    
    # SPX premium estimate: SPY × 10
    spx_price_est = spy_price * 10
    
    if delta == 0:
        delta = DELTA_IDEAL if opt_type.upper() in ["C", "CALL", "CALLS"] else -DELTA_IDEAL
    
    return OptionData(
        spy_strike=spy_strike,
        spy_price=round(spy_price, 2),
        spy_delta=delta,
        spx_strike=spx_strike,
        spx_price_est=round(spx_price_est, 2),
        otm_distance=round(otm_distance, 1),
        in_sweet_spot=(PREMIUM_SWEET_LOW <= spy_price <= PREMIUM_SWEET_HIGH)
    )


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
        zone.bias_reason = f"VIX {abs(zone.zones_away)} zone(s) below → SPX UP"
    elif vix_current > vix_top:
        zones_above = (vix_current - vix_top) / zone.zone_size if zone.zone_size > 0 else 0
        zone.zones_away = int(np.ceil(zones_above))
        zone.position_pct = 100
        zone.bias = "PUTS"
        zone.bias_reason = f"VIX {zone.zones_away} zone(s) above → SPX DOWN"
    else:
        zone.zones_away = 0
        zone.position_pct = ((vix_current - vix_bottom) / zone.zone_size * 100) if zone.zone_size > 0 else 50
        if zone.position_pct >= 75:
            zone.bias = "CALLS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (top) → SPX UP"
        elif zone.position_pct <= 25:
            zone.bias = "PUTS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (bottom) → SPX DOWN"
        else:
            zone.bias = "WAIT"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (middle)"
    
    if cones and zone.bias in ["CALLS", "PUTS"]:
        rails = []
        for c in cones:
            if c.is_tradeable:
                rails.append((c.descending_rail if zone.bias == "CALLS" else c.ascending_rail, c.name))
        if rails:
            rails.sort(key=lambda x: x[0])
            zone.matched_rail = rails[len(rails)//2][0]
            zone.matched_cone = rails[len(rails)//2][1]
    
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
    
    high_candidates = []
    for i in range(len(candles) - 1):
        curr, nxt = candles[i], candles[i + 1]
        if curr["is_green"] and not nxt["is_green"] and nxt["close"] < curr["open"]:
            high_candidates.append({"price": curr["high"], "time": curr["time"]})
    
    low_candidates = []
    for i in range(len(candles) - 1):
        curr, nxt = candles[i], candles[i + 1]
        if not curr["is_green"] and nxt["is_green"] and nxt["close"] > curr["open"]:
            low_candidates.append({"price": nxt["open"], "time": curr["time"]})
    
    if high_candidates:
        high_candidates.sort(key=lambda x: x["price"], reverse=True)
        pivots.append(Pivot(name="Prior High", price=high_candidates[0]["price"],
                           pivot_time=high_candidates[0]["time"], pivot_type="HIGH",
                           candle_high=high_candidates[0]["price"]))
        for i, h in enumerate(high_candidates[1:3], 1):
            pivots.append(Pivot(name=f"High {i+1}", price=h["price"], pivot_time=h["time"],
                               pivot_type="HIGH", is_secondary=True, candle_high=h["price"]))
    
    if low_candidates:
        low_candidates.sort(key=lambda x: x["price"])
        pivots.append(Pivot(name="Prior Low", price=low_candidates[0]["price"],
                           pivot_time=low_candidates[0]["time"], pivot_type="LOW",
                           candle_open=low_candidates[0]["price"]))
        for i, l in enumerate(low_candidates[1:3], 1):
            pivots.append(Pivot(name=f"Low {i+1}", price=l["price"], pivot_time=l["time"],
                               pivot_type="LOW", is_secondary=True, candle_open=l["price"]))
    
    if candles:
        pivots.append(Pivot(name="Prior Close", price=candles[-1]["close"],
                           pivot_time=CT_TZ.localize(datetime.combine(pivot_date, close_time)),
                           pivot_type="CLOSE"))
    
    return pivots

def create_manual_pivots(high_price, high_time_str, low_price, low_time_str, close_price,
                         pivot_date, close_time) -> List[Pivot]:
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
    time_blocks = [("8:30", time(8, 30)), ("9:00", time(9, 0)), ("9:30", time(9, 30)),
                   ("10:00", time(10, 0)), ("10:30", time(10, 30)), ("11:00", time(11, 0)),
                   ("11:30", time(11, 30)), ("12:00", time(12, 0))]
    
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
# SETUPS AND SCORING
# =============================================================================

def generate_setups(cones: List[Cone], current_price: float, expiry: date, is_after_cutoff: bool = False) -> List[TradeSetup]:
    setups = []
    
    for cone in cones:
        if not cone.is_tradeable:
            continue
        
        # CALLS - enter at descending rail, buy strike 15pts ABOVE entry
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        stop_c = round(entry_c - STOP_LOSS_PTS, 2)
        t25_c = round(entry_c + cone.width * 0.25, 2)
        t50_c = round(entry_c + cone.width * 0.50, 2)
        t75_c = round(entry_c + cone.width * 0.75, 2)
        
        opt_c = get_option_data_for_entry(entry_c, "C", expiry)
        status_c = "GREY" if is_after_cutoff else ("ACTIVE" if dist_c <= RAIL_PROXIMITY else "WAIT")
        
        delta_c = abs(opt_c.spy_delta) if opt_c and opt_c.spy_delta != 0 else DELTA_IDEAL
        
        profit_25_c = round(cone.width * 0.25 * delta_c * 100, 0)
        profit_50_c = round(cone.width * 0.50 * delta_c * 100, 0)
        profit_75_c = round(cone.width * 0.75 * delta_c * 100, 0)
        risk_c = round(STOP_LOSS_PTS * delta_c * 100, 0)
        
        setups.append(TradeSetup(
            direction="CALLS", cone_name=cone.name, cone_width=cone.width,
            entry=entry_c, stop=stop_c, target_25=t25_c, target_50=t50_c, target_75=t75_c,
            distance=round(dist_c, 1), option=opt_c,
            profit_25=profit_25_c, profit_50=profit_50_c, profit_75=profit_75_c,
            risk_dollars=risk_c, status=status_c
        ))
        
        # PUTS - enter at ascending rail, buy strike 15pts BELOW entry
        entry_p = cone.ascending_rail
        dist_p = abs(current_price - entry_p)
        stop_p = round(entry_p + STOP_LOSS_PTS, 2)
        t25_p = round(entry_p - cone.width * 0.25, 2)
        t50_p = round(entry_p - cone.width * 0.50, 2)
        t75_p = round(entry_p - cone.width * 0.75, 2)
        
        opt_p = get_option_data_for_entry(entry_p, "P", expiry)
        status_p = "GREY" if is_after_cutoff else ("ACTIVE" if dist_p <= RAIL_PROXIMITY else "WAIT")
        
        delta_p = abs(opt_p.spy_delta) if opt_p and opt_p.spy_delta != 0 else DELTA_IDEAL
        
        profit_25_p = round(cone.width * 0.25 * delta_p * 100, 0)
        profit_50_p = round(cone.width * 0.50 * delta_p * 100, 0)
        profit_75_p = round(cone.width * 0.75 * delta_p * 100, 0)
        risk_p = round(STOP_LOSS_PTS * delta_p * 100, 0)
        
        setups.append(TradeSetup(
            direction="PUTS", cone_name=cone.name, cone_width=cone.width,
            entry=entry_p, stop=stop_p, target_25=t25_p, target_50=t50_p, target_75=t75_p,
            distance=round(dist_p, 1), option=opt_p,
            profit_25=profit_25_p, profit_50=profit_50_p, profit_75=profit_75_p,
            risk_dollars=risk_p, status=status_p
        ))
    
    return setups

def calculate_day_score(vix_zone: VIXZone, cones: List[Cone], setups: List[TradeSetup]) -> DayScore:
    score = DayScore()
    
    if vix_zone.bias in ["CALLS", "PUTS"]:
        aligned = any(s.direction == vix_zone.bias and s.distance <= 10 for s in setups)
        score.vix_cone_alignment = 25 if aligned else 10 if any(s.direction == vix_zone.bias for s in setups) else 0
    
    if vix_zone.bias == "WAIT":
        score.vix_clarity = 0
    elif vix_zone.position_pct >= 75 or vix_zone.position_pct <= 25 or vix_zone.zones_away != 0:
        score.vix_clarity = 25
    else:
        score.vix_clarity = 10
    
    tradeable = [c for c in cones if c.is_tradeable]
    if tradeable:
        best = max(c.width for c in tradeable)
        score.cone_width = 20 if best >= 30 else 15 if best >= 25 else 10 if best >= 20 else 5
    
    sweet = sum(1 for s in setups if s.option and s.option.in_sweet_spot)
    score.premium_quality = 15 if sweet >= 3 else 10 if sweet >= 1 else 5
    
    rails = [r for c in tradeable for r in [c.ascending_rail, c.descending_rail]]
    confluence = any(abs(rails[i] - rails[j]) <= 5 for i in range(len(rails)) for j in range(i+1, len(rails)))
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
            alerts.append({"priority": "HIGH", "message": f"🎯 {s.direction} {s.cone_name} ACTIVE @ {s.entry:,.2f}"})
        elif 5 < s.distance <= 15 and s.status != "GREY":
            alerts.append({"priority": "MEDIUM", "message": f"⚠️ {s.direction} {s.cone_name} ({s.distance:.0f} pts away)"})
    if vix_zone.zones_away != 0:
        alerts.append({"priority": "HIGH", "message": f"📊 VIX {abs(vix_zone.zones_away)} zone(s) {'above' if vix_zone.zones_away > 0 else 'below'}"})
    if INST_WINDOW_START <= current_time <= INST_WINDOW_END:
        alerts.append({"priority": "INFO", "message": "🏛️ Institutional Window (9:00-9:30 CT)"})
    return alerts


# =============================================================================
# MODERN CARD-BASED UI
# =============================================================================

def render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score, 
                     alerts, spx_price, trading_date, is_historical, theme):
    
    if theme == "dark":
        bg, card_bg = "#0a0a0f", "rgba(25,25,35,0.85)"
        text1, text2, text3 = "#ffffff", "#a1a1aa", "#71717a"
        border = "rgba(255,255,255,0.1)"
        glass = "rgba(255,255,255,0.03)"
    else:
        bg, card_bg = "#f8fafc", "rgba(255,255,255,0.9)"
        text1, text2, text3 = "#09090b", "#52525b", "#a1a1aa"
        border = "rgba(0,0,0,0.1)"
        glass = "rgba(0,0,0,0.02)"
    
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:{bg};color:{text1};padding:20px;line-height:1.5}}
.container{{max-width:1800px;margin:0 auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:16px}}
.logo{{display:flex;align-items:center;gap:12px}}
.logo-icon{{width:52px;height:52px;background:linear-gradient(135deg,{blue},{purple});border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800;color:white;box-shadow:0 8px 32px rgba(59,130,246,0.3)}}
.logo h1{{font-size:24px;font-weight:800;letter-spacing:-0.5px}}
.tagline{{font-size:11px;color:{text2};font-style:italic;margin-top:2px}}
.header-right{{display:flex;align-items:center;gap:20px}}
.time-display{{font-family:'JetBrains Mono';font-size:28px;font-weight:600}}
.countdown{{text-align:right}}
.countdown-label{{font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:{text3};margin-bottom:2px}}
.countdown-value{{font-family:'JetBrains Mono';font-size:16px;color:{amber};font-weight:600}}
.card{{background:{card_bg};backdrop-filter:blur(20px);border:1px solid {border};border-radius:20px;padding:24px;margin-bottom:20px}}
.card-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;cursor:pointer}}
.card-title{{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:{text3};display:flex;align-items:center;gap:8px}}
.collapsed .card-content{{display:none}}
.banner{{padding:16px 20px;border-radius:14px;display:flex;align-items:center;gap:16px;margin-bottom:20px}}
.banner-hist{{background:linear-gradient(135deg,{purple}25,{purple}08);border:2px solid {purple}40}}
.banner-inst{{background:linear-gradient(135deg,{amber}25,{amber}08);border:2px solid {amber}40}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
.grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
@media(max-width:1200px){{.grid-2,.grid-3{{grid-template-columns:1fr}}}}
@media(max-width:800px){{.grid-4{{grid-template-columns:repeat(2,1fr)}}}}
.vix-ladder{{position:relative;height:72px;background:{glass};border-radius:12px;margin:16px 0}}
.vix-bar{{position:absolute;left:20px;right:20px;height:32px;top:50%;transform:translateY(-50%);background:linear-gradient(90deg,{green}50,{bg},{bg},{red}50);border-radius:16px}}
.vix-marker{{position:absolute;width:20px;height:20px;background:{bias_color};border-radius:50%;top:50%;transform:translate(-50%,-50%);box-shadow:0 0 20px {bias_color};border:3px solid {card_bg};z-index:10}}
.vix-labels{{position:absolute;bottom:8px;left:20px;right:20px;display:flex;justify-content:space-between;font-family:'JetBrains Mono';font-size:11px;color:{text3}}}
.bias-card{{text-align:center;padding:32px;background:linear-gradient(135deg,{bias_color}20,{bias_color}05);border:2px solid {bias_color}40;border-radius:20px}}
.bias-icon{{font-size:48px;color:{bias_color};text-shadow:0 0 30px {bias_color}}}
.bias-label{{font-size:28px;font-weight:800;color:{bias_color};letter-spacing:3px;margin-top:8px}}
.bias-reason{{font-size:13px;color:{text2};margin-top:12px}}
.bias-match{{font-size:12px;color:{blue};margin-top:8px;font-weight:600}}
.stat{{background:{glass};border-radius:14px;padding:16px;text-align:center}}
.stat-value{{font-family:'JetBrains Mono';font-size:20px;font-weight:700}}
.stat-label{{font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:{text3};margin-top:4px}}
.score-circle{{width:100px;height:100px;border-radius:50%;margin:0 auto 16px;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'JetBrains Mono';border:5px solid}}
.score-value{{font-size:32px;font-weight:800}}
.score-grade{{font-size:14px;font-weight:700}}

/* SETUP CARDS */
.setup-grid{{display:grid;grid-template-columns:repeat(auto-fill, minmax(380px, 1fr));gap:20px}}
.setup-card{{background:{glass};border:1px solid {border};border-radius:20px;padding:24px;transition:all 0.3s ease}}
.setup-card:hover{{transform:translateY(-4px);box-shadow:0 12px 40px rgba(0,0,0,0.15)}}
.setup-card.active{{border:2px solid {green};background:linear-gradient(135deg,{green}10,transparent)}}
.setup-card.grey{{opacity:0.5}}
.setup-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}}
.setup-cone{{font-size:18px;font-weight:700}}
.setup-direction{{font-size:12px;font-weight:700;padding:6px 16px;border-radius:100px}}
.setup-calls{{background:{green}20;color:{green}}}
.setup-puts{{background:{red}20;color:{red}}}
.setup-entry{{text-align:center;padding:24px;background:{card_bg};border-radius:16px;margin-bottom:20px}}
.setup-entry-label{{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:{text3};margin-bottom:6px}}
.setup-entry-price{{font-family:'JetBrains Mono';font-size:32px;font-weight:800}}
.setup-entry-distance{{font-size:13px;color:{text2};margin-top:8px}}
.setup-contract{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
.setup-contract-box{{background:{card_bg};border-radius:14px;padding:16px;text-align:center}}
.setup-contract-label{{font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:{text3};margin-bottom:6px}}
.setup-contract-strike{{font-family:'JetBrains Mono';font-size:22px;font-weight:700}}
.setup-contract-price{{font-size:14px;color:{text2};margin-top:4px}}
.setup-contract-otm{{font-size:10px;color:{text3}}}
.setup-targets{{margin-bottom:20px}}
.setup-targets-title{{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:{text3};margin-bottom:12px}}
.target-row{{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:{card_bg};border-radius:12px;margin-bottom:10px}}
.target-label{{font-size:13px;color:{text2}}}
.target-price{{font-family:'JetBrains Mono';font-size:14px;color:{text1}}}
.target-profit{{font-family:'JetBrains Mono';font-size:16px;font-weight:700;color:{green}}}
.setup-risk{{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:{red}10;border-radius:14px;border:1px solid {red}30}}
.risk-label{{font-size:12px;color:{red}}}
.risk-stop{{font-family:'JetBrains Mono';font-size:14px;color:{red}}}
.risk-value{{font-family:'JetBrains Mono';font-size:16px;font-weight:700;color:{red}}}

.alert{{padding:12px 16px;border-radius:10px;margin-bottom:8px;font-size:13px}}
.alert-HIGH{{background:{red}12;border-left:4px solid {red}}}
.alert-MEDIUM{{background:{amber}12;border-left:4px solid {amber}}}
.alert-INFO{{background:{blue}12;border-left:4px solid {blue}}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:{text3};padding:10px 8px;text-align:left;border-bottom:1px solid {border}}}
td{{padding:12px 8px;border-bottom:1px solid {border}}}
.mono{{font-family:'JetBrains Mono'}}
.green{{color:{green}}}
.red{{color:{red}}}
.amber{{color:{amber}}}
.blue{{color:{blue}}}
.pill{{display:inline-block;padding:4px 10px;border-radius:100px;font-size:10px;font-weight:600;font-family:'JetBrains Mono'}}
.pill-green{{background:{green}20;color:{green}}}
.pill-red{{background:{red}20;color:{red}}}
.footer{{text-align:center;padding:32px;color:{text3};font-size:10px}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
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
            <div class="countdown-label">Entry Window</div>
            <div class="countdown-value">{format_countdown(time_to_910)}</div>
        </div>
        <div class="countdown">
            <div class="countdown-label">Cutoff</div>
            <div class="countdown-value">{format_countdown(time_to_1130)}</div>
        </div>
        <div class="time-display">{now.strftime("%H:%M")} CT</div>
    </div>
</div>
'''
    
    # Banners
    if is_historical:
        html += f'<div class="banner banner-hist"><div style="font-size:24px">📅</div><div><div style="font-weight:700;font-size:15px;color:{purple}">Historical Analysis: {trading_date.strftime("%B %d, %Y")}</div></div></div>'
    
    is_inst = INST_WINDOW_START <= now.time() <= INST_WINDOW_END
    if is_inst and not is_historical:
        html += f'<div class="banner banner-inst"><div style="font-size:24px">🏛️</div><div><div style="font-weight:700;font-size:15px;color:{amber}">INSTITUTIONAL WINDOW ACTIVE</div></div></div>'
    
    # Alerts
    if alerts:
        html += '<div class="card" style="padding:16px">'
        for a in alerts[:4]:
            html += f'<div class="alert alert-{a["priority"]}">{a["message"]}</div>'
        html += '</div>'
    
    # VIX Zone + Bias
    html += f'''
<div class="card">
    <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="card-title"><span>📊</span> VIX ZONE ANALYSIS</div>
        <span style="color:{text3}">▼</span>
    </div>
    <div class="card-content">
        <div class="grid-2">
            <div>
                <div class="vix-ladder">
                    <div class="vix-bar"></div>
                    <div class="vix-marker" style="left:{marker_pos}%"></div>
                    <div class="vix-labels"><span>{vix_zone.bottom:.2f}</span><span>Zone: {vix_zone.zone_size:.2f}</span><span>{vix_zone.top:.2f}</span></div>
                </div>
                <div class="grid-4" style="margin-top:16px">
                    <div class="stat"><div class="stat-value">{vix_zone.current:.2f}</div><div class="stat-label">Current VIX</div></div>
                    <div class="stat"><div class="stat-value">{vix_zone.position_pct:.0f}%</div><div class="stat-label">Position</div></div>
                    <div class="stat"><div class="stat-value blue">±{vix_zone.expected_spx_move:.0f}</div><div class="stat-label">Exp. Move</div></div>
                    <div class="stat"><div class="stat-value">{vix_zone.zones_away:+d}</div><div class="stat-label">Zones Away</div></div>
                </div>
            </div>
            <div class="bias-card">
                <div class="bias-icon">{bias_icon}</div>
                <div class="bias-label">{vix_zone.bias}</div>
                <div class="bias-reason">{vix_zone.bias_reason}</div>
                {"<div class='bias-match'>Target: " + vix_zone.matched_cone + " @ " + f"{vix_zone.matched_rail:,.2f}" + "</div>" if vix_zone.matched_rail > 0 else ""}
            </div>
        </div>
    </div>
</div>
'''
    
    # Function to render setup cards
    def render_setup_cards(direction, color, icon):
        filtered = [s for s in setups if s.direction == direction]
        h = f'''
<div class="card">
    <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="card-title" style="color:{color}"><span>{icon}</span> {direction} SETUPS</div>
        <span style="color:{text3}">▼</span>
    </div>
    <div class="card-content">
        <div class="setup-grid">
'''
        for s in filtered:
            opt = s.option
            card_class = "active" if s.status == "ACTIVE" else "grey" if s.status == "GREY" else ""
            
            if opt:
                spy_strike = f"{int(opt.spy_strike)}{'C' if direction == 'CALLS' else 'P'}"
                spy_price = f"${opt.spy_price:.2f}" if opt.spy_price > 0 else "--"
                spx_strike = f"{opt.spx_strike}{'C' if direction == 'CALLS' else 'P'}"
                spx_price = f"${opt.spx_price_est:.0f}" if opt.spx_price_est > 0 else "--"
                otm_dist = f"{opt.otm_distance:.0f} pts OTM"
                sweet = "★ SWEET SPOT" if opt.in_sweet_spot else ""
            else:
                spy_strike = spy_price = spx_strike = spx_price = otm_dist = "--"
                sweet = ""
            
            status_text = "🎯 ACTIVE - READY TO TRADE" if s.status == "ACTIVE" else "CLOSED" if s.status == "GREY" else f"{s.distance:.0f} pts away"
            entry_color = green if direction == "CALLS" else red
            
            h += f'''
        <div class="setup-card {card_class}">
            <div class="setup-header">
                <div class="setup-cone">{s.cone_name}</div>
                <div class="setup-direction setup-{direction.lower()}">{direction[:-1]}</div>
            </div>
            
            <div class="setup-entry">
                <div class="setup-entry-label">Entry Level (Rail Touch)</div>
                <div class="setup-entry-price" style="color:{entry_color}">{s.entry:,.2f}</div>
                <div class="setup-entry-distance">{status_text}</div>
            </div>
            
            <div class="setup-contract">
                <div class="setup-contract-box">
                    <div class="setup-contract-label">SPY Reference</div>
                    <div class="setup-contract-strike">{spy_strike}</div>
                    <div class="setup-contract-price">{spy_price} {sweet}</div>
                </div>
                <div class="setup-contract-box">
                    <div class="setup-contract-label">SPX Contract</div>
                    <div class="setup-contract-strike" style="color:{entry_color}">{spx_strike}</div>
                    <div class="setup-contract-price">{spx_price}</div>
                    <div class="setup-contract-otm">{otm_dist}</div>
                </div>
            </div>
            
            <div class="setup-targets">
                <div class="setup-targets-title">Profit Targets</div>
                <div class="target-row">
                    <div class="target-label">25% of Cone</div>
                    <div class="target-price">{s.target_25:,.2f}</div>
                    <div class="target-profit">+${s.profit_25:,.0f}</div>
                </div>
                <div class="target-row">
                    <div class="target-label">50% of Cone</div>
                    <div class="target-price">{s.target_50:,.2f}</div>
                    <div class="target-profit">+${s.profit_50:,.0f}</div>
                </div>
                <div class="target-row">
                    <div class="target-label">75% of Cone</div>
                    <div class="target-price">{s.target_75:,.2f}</div>
                    <div class="target-profit">+${s.profit_75:,.0f}</div>
                </div>
            </div>
            
            <div class="setup-risk">
                <div class="risk-label">Stop Loss</div>
                <div class="risk-stop">{s.stop:,.2f}</div>
                <div class="risk-value">-${s.risk_dollars:,.0f}</div>
            </div>
        </div>
'''
        h += '</div></div></div>'
        return h
    
    html += render_setup_cards("CALLS", green, "▲")
    html += render_setup_cards("PUTS", red, "▼")
    
    # Prior Session + Score
    html += f'''
<div class="grid-2">
    <div class="card">
        <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
            <div class="card-title"><span>📈</span> PRIOR SESSION</div>
            <span style="color:{text3}">▼</span>
        </div>
        <div class="card-content">
            <div class="grid-4">
                <div class="stat"><div class="stat-value green">{prior_session.get("high", 0):,.2f}</div><div class="stat-label">High</div></div>
                <div class="stat"><div class="stat-value red">{prior_session.get("low", 0):,.2f}</div><div class="stat-label">Low</div></div>
                <div class="stat"><div class="stat-value">{prior_session.get("close", 0):,.2f}</div><div class="stat-label">Close</div></div>
                <div class="stat"><div class="stat-value blue">{prior_session.get("high", 0) - prior_session.get("low", 0):,.0f}</div><div class="stat-label">Range</div></div>
            </div>
        </div>
    </div>
    <div class="card">
        <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
            <div class="card-title"><span>🎯</span> DAY SCORE</div>
            <span style="color:{text3}">▼</span>
        </div>
        <div class="card-content" style="text-align:center">
            <div class="score-circle" style="border-color:{day_score.color};color:{day_score.color}">
                <div class="score-value">{day_score.total}</div>
                <div class="score-grade">{day_score.grade}</div>
            </div>
            <div style="font-size:13px;color:{text2}">
                {"🟢 Excellent" if day_score.total >= 80 else "🔵 Good" if day_score.total >= 60 else "🟠 Marginal" if day_score.total >= 40 else "🔴 Skip"}
            </div>
        </div>
    </div>
</div>
'''
    
    # Cones Table
    html += f'''
<div class="card">
    <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="card-title"><span>📐</span> STRUCTURAL CONES</div>
        <span style="color:{text3}">▼</span>
    </div>
    <div class="card-content">
        <table>
            <thead><tr><th>Pivot</th><th>Ascending Rail (Puts Entry)</th><th>Descending Rail (Calls Entry)</th><th>Width</th><th>Tradeable</th></tr></thead>
            <tbody>
'''
    for c in cones:
        w_cls = "green" if c.width >= 25 else "amber" if c.width >= MIN_CONE_WIDTH else "red"
        ok = f'<span class="pill pill-green">YES</span>' if c.is_tradeable else f'<span class="pill pill-red">NO</span>'
        html += f'<tr><td><strong>{c.name}</strong></td><td class="mono red">{c.ascending_rail:,.2f}</td><td class="mono green">{c.descending_rail:,.2f}</td><td class="mono {w_cls}">{c.width:.0f} pts</td><td>{ok}</td></tr>'
    html += '</tbody></table></div></div>'
    
    # Pivot Table
    html += f'''
<div class="card collapsed">
    <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="card-title"><span>📋</span> PIVOT TABLE</div>
        <span style="color:{text3}">▼</span>
    </div>
    <div class="card-content">
        <table>
            <thead><tr><th>Time CT</th><th>High ▲</th><th>High ▼</th><th>Low ▲</th><th>Low ▼</th><th>Close ▲</th><th>Close ▼</th></tr></thead>
            <tbody>
'''
    for row in pivot_table:
        is_inst_row = INST_WINDOW_START <= row.time_ct <= INST_WINDOW_END
        style = f'background:{amber}10;' if is_inst_row else ""
        html += f'<tr style="{style}"><td><strong>{row.time_block}</strong>{"🏛️" if is_inst_row else ""}</td><td class="mono red">{row.prior_high_asc:,.2f}</td><td class="mono green">{row.prior_high_desc:,.2f}</td><td class="mono red">{row.prior_low_asc:,.2f}</td><td class="mono green">{row.prior_low_desc:,.2f}</td><td class="mono red">{row.prior_close_asc:,.2f}</td><td class="mono green">{row.prior_close_desc:,.2f}</td></tr>'
    html += '</tbody></table></div></div>'
    
    html += f'<div class="footer">SPX Prophet v6.6 • Contracts ~15pts OTM from entry rail ($4-$8 sweet spot) • Data via Polygon.io</div></div></body></html>'
    return html


# =============================================================================
# MAIN APP
# =============================================================================

def main():
    st.set_page_config(page_title="SPX Prophet v6.6", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
    
    defaults = {
        'theme': 'light', 'vix_bottom': 0.0, 'vix_top': 0.0, 'vix_current': 0.0,
        'use_manual_pivots': False, 'high_price': 0.0, 'high_time': "10:30",
        'low_price': 0.0, 'low_time': "14:00", 'close_price': 0.0,
        'trading_date': None, 'last_refresh': None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    with st.sidebar:
        st.markdown("## 📈 SPX Prophet v6.6")
        st.caption("15pt OTM from Entry Rail")
        st.divider()
        
        theme = st.radio("🎨 Theme", ["Light", "Dark"], horizontal=True, index=0 if st.session_state.theme == "light" else 1)
        st.session_state.theme = theme.lower()
        
        st.divider()
        st.markdown("### 📅 Trading Date")
        
        today = get_ct_now().date()
        next_trade = get_next_trading_day(today)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📍 Next", use_container_width=True):
                st.session_state.trading_date = next_trade
        with col2:
            if st.button("📆 Prev", use_container_width=True):
                st.session_state.trading_date = get_prior_trading_day(today)
        
        selected_date = st.date_input("Select", value=st.session_state.trading_date or next_trade,
                                       min_value=today - timedelta(days=730), max_value=today + timedelta(days=7))
        st.session_state.trading_date = selected_date
        
        if is_holiday(selected_date):
            st.warning(f"🚫 {HOLIDAYS_2025.get(selected_date, 'Holiday')}")
        elif is_half_day(selected_date):
            st.info(f"⏰ Half Day - 12pm Close")
        
        st.divider()
        st.markdown("### 📊 VIX Zone (5pm-3am)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input("Bottom", value=st.session_state.vix_bottom, step=0.01, format="%.2f")
        with col2:
            st.session_state.vix_top = st.number_input("Top", value=st.session_state.vix_top, step=0.01, format="%.2f")
        
        st.session_state.vix_current = st.number_input("Current VIX", value=st.session_state.vix_current, step=0.01, format="%.2f")
        
        st.divider()
        st.markdown("### 📍 Manual Pivots")
        
        st.session_state.use_manual_pivots = st.checkbox("Override Auto", st.session_state.use_manual_pivots)
        
        if st.session_state.use_manual_pivots:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.high_price = st.number_input("High $", value=st.session_state.high_price, step=0.01, format="%.2f")
            with c2:
                st.session_state.high_time = st.text_input("H Time", value=st.session_state.high_time)
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.low_price = st.number_input("Low $", value=st.session_state.low_price, step=0.01, format="%.2f")
            with c2:
                st.session_state.low_time = st.text_input("L Time", value=st.session_state.low_time)
            
            st.session_state.close_price = st.number_input("Close $", value=st.session_state.close_price, step=0.01, format="%.2f")
        
        st.divider()
        if st.button("🔄 REFRESH", use_container_width=True, type="primary"):
            st.session_state.last_refresh = get_ct_now()
            st.rerun()
        
        if st.session_state.last_refresh:
            st.caption(f"Updated: {st.session_state.last_refresh.strftime('%H:%M:%S CT')}")
    
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
        pivots = create_manual_pivots(st.session_state.high_price, st.session_state.high_time,
                                      st.session_state.low_price, st.session_state.low_time,
                                      st.session_state.close_price, pivot_date, pivot_close_time)
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
    
    eval_time = CT_TZ.localize(datetime.combine(trading_date, time(9, 0)))
    cones = build_cones(pivots, eval_time)
    vix_zone = analyze_vix_zone(st.session_state.vix_bottom, st.session_state.vix_top, st.session_state.vix_current, cones)
    
    spx_price = polygon_get_index_price("I:SPX")
    if spx_price == 0:
        spx_price = prior_session.get("close", 0)
    
    is_after_cutoff = (trading_date == now.date() and now.time() > CUTOFF_TIME) or is_historical
    setups = generate_setups(cones, spx_price, expiry, is_after_cutoff)
    day_score = calculate_day_score(vix_zone, cones, setups)
    pivot_table = build_pivot_table(pivots, trading_date)
    
    alerts = check_alerts(setups, vix_zone, now.time()) if not is_historical else []
    
    html = render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score,
                            alerts, spx_price, trading_date, is_historical, st.session_state.theme)
    
    components.html(html, height=3500, scrolling=True)


if __name__ == "__main__":
    main()