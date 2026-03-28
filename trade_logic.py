"""
SPX Prophet — Trade Logic Module
Alternating day logic, trade scenarios, position assessment, strike calculation, prop firm risk.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime, date, time as dtime
import pytz

CT = pytz.timezone("America/Chicago")
STRIKE_OFFSET = 20
STOP_LOSS_POINTS = 6
TP1_PCT, TP2_PCT, TP3_PCT = 0.25, 0.50, 0.75


@dataclass
class TradeScenario:
    direction: str
    entry_level: float
    entry_label: str
    rationale: str
    target_level: Optional[float] = None
    target_label: Optional[str] = None
    strike: Optional[int] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    is_primary: bool = True
    strength: str = "STANDARD"


@dataclass
class PositionAssessment:
    zone: str
    zone_label: str
    nearest_line: str
    nearest_distance: float
    day_type: str
    scenarios: List[TradeScenario] = field(default_factory=list)


@dataclass
class PropFirmRisk:
    max_es: int = 4
    max_mes: int = 40
    daily_loss_limit: float = 400.0
    current_pnl: float = 0.0

    @property
    def risk_pct(self):
        return min(100, (abs(self.current_pnl) / self.daily_loss_limit) * 100) if self.current_pnl < 0 else 0.0

    @property
    def risk_status(self):
        p = self.risk_pct
        if p == 0: return "CLEAR"
        if p < 50: return "ACTIVE"
        if p < 75: return "CAUTION"
        if p < 100: return "DANGER"
        return "LIMIT HIT"


def _find_nearest(price, lines):
    nearest = min(lines.keys(), key=lambda k: abs(price - lines[k]))
    return nearest, abs(price - lines[nearest])


def _determine_zone(price, af, ac, df_, dc):
    if price > ac: return "ABOVE_ASC", "Above Ascending Channel"
    if price >= af: return "IN_ASC", "Inside Ascending Channel"
    if price > dc: return "BETWEEN", "Between Channels"
    if price >= df_: return "IN_DESC", "Inside Descending Channel"
    return "BELOW_DESC", "Below Descending Channel"


def _add_trade_details(scenarios, channel_width, is_spx=True):
    """Add stop loss, take profits, and strikes to scenarios."""
    for s in scenarios:
        if s.direction in ("CALLS", "LONG ES"):
            if is_spx:
                s.strike = round_strike(s.entry_level + STRIKE_OFFSET)
            s.stop_loss = s.entry_level - (STOP_LOSS_POINTS if is_spx else 2.0)
            s.take_profit_1 = s.entry_level + (channel_width * TP1_PCT)
            s.take_profit_2 = s.entry_level + (channel_width * TP2_PCT)
            s.take_profit_3 = s.entry_level + (channel_width * TP3_PCT)
        elif s.direction in ("PUTS", "SHORT ES"):
            if is_spx:
                s.strike = round_strike(s.entry_level - STRIKE_OFFSET)
            s.stop_loss = s.entry_level + (STOP_LOSS_POINTS if is_spx else 2.0)
            s.take_profit_1 = s.entry_level - (channel_width * TP1_PCT)
            s.take_profit_2 = s.entry_level - (channel_width * TP2_PCT)
            s.take_profit_3 = s.entry_level - (channel_width * TP3_PCT)


def assess_ascending_day(price, cv) -> PositionAssessment:
    af, ac, df_, dc = cv["asc_floor"], cv["asc_ceiling"], cv["desc_floor"], cv["desc_ceiling"]
    zone, zone_label = _determine_zone(price, af, ac, df_, dc)
    lines = {"Asc Floor": af, "Asc Ceiling": ac, "Desc Floor": df_, "Desc Ceiling": dc}
    nearest, dist = _find_nearest(price, lines)
    scenarios = []

    if zone == "IN_ASC":
        scenarios = [
            TradeScenario("CALLS", af, "Ascending Floor", "Buy off ascending floor", ac, "Ascending Ceiling", strength="STRONG"),
            TradeScenario("PUTS", ac, "Ascending Ceiling", "Sell off ascending ceiling", af, "Ascending Floor", is_primary=False),
        ]
    elif zone == "ABOVE_ASC":
        scenarios = [
            TradeScenario("CALLS", ac, "Ascending Ceiling", "Ceiling becomes support — buy higher", strength="STRONG"),
            TradeScenario("CALLS", af, "Ascending Floor", "If drops to floor, buy bounce", is_primary=False),
        ]
    elif zone == "BETWEEN":
        scenarios = [
            TradeScenario("CALLS", dc, "Descending Ceiling", "Rally from desc ceiling to asc floor", af, "Ascending Floor", strength="STRONG"),
            TradeScenario("PUTS", af, "Ascending Floor", "Rejected at asc floor, sell to desc ceiling", dc, "Descending Ceiling", is_primary=False, strength="CAUTION"),
        ]
    elif zone == "IN_DESC":
        scenarios = [
            TradeScenario("CALLS", df_, "Descending Floor", "Rally through desc channel to ascending", af, "Ascending Floor", strength="STRONG"),
            TradeScenario("PUTS", dc, "Descending Ceiling", "Rejection at desc ceiling", is_primary=False, strength="CAUTION"),
        ]
    elif zone == "BELOW_DESC":
        scenarios = [
            TradeScenario("CALLS", df_, "Descending Floor", "Far below on asc day — rally to ascending", af, "Ascending Floor", strength="STRONG"),
        ]

    _add_trade_details(scenarios, ac - af, is_spx=True)
    return PositionAssessment(zone, zone_label, nearest, dist, "ascending", scenarios)


def assess_descending_day(price, cv) -> PositionAssessment:
    af, ac, df_, dc = cv["asc_floor"], cv["asc_ceiling"], cv["desc_floor"], cv["desc_ceiling"]
    zone, zone_label = _determine_zone(price, af, ac, df_, dc)
    lines = {"Asc Floor": af, "Asc Ceiling": ac, "Desc Floor": df_, "Desc Ceiling": dc}
    nearest, dist = _find_nearest(price, lines)
    scenarios = []

    if zone == "IN_DESC":
        scenarios = [
            TradeScenario("CALLS", df_, "Descending Floor", "Buy off descending floor", dc, "Descending Ceiling"),
            TradeScenario("PUTS", dc, "Descending Ceiling", "Sell off descending ceiling", df_, "Descending Floor", strength="STRONG"),
        ]
    elif zone == "BELOW_DESC":
        scenarios = [
            TradeScenario("PUTS", df_, "Descending Floor", "Floor becomes resistance — sell lower", strength="STRONG"),
        ]
    elif zone == "BETWEEN":
        scenarios = [
            TradeScenario("PUTS", af, "Ascending Floor", "Drop from asc floor to desc ceiling", dc, "Descending Ceiling", strength="STRONG"),
            TradeScenario("CALLS", dc, "Descending Ceiling", "Bounce at desc ceiling to asc floor", af, "Ascending Floor", is_primary=False, strength="CAUTION"),
        ]
    elif zone == "IN_ASC":
        scenarios = [
            TradeScenario("PUTS", ac, "Ascending Ceiling", "Drop through ascending to descending", dc, "Descending Ceiling", strength="STRONG"),
            TradeScenario("CALLS", af, "Ascending Floor", "Bounce at asc floor", is_primary=False, strength="CAUTION"),
        ]
    elif zone == "ABOVE_ASC":
        scenarios = [
            TradeScenario("PUTS", ac, "Ascending Ceiling", "Far above on desc day — drop to descending", dc, "Descending Ceiling", strength="STRONG"),
        ]

    _add_trade_details(scenarios, dc - df_, is_spx=True)
    return PositionAssessment(zone, zone_label, nearest, dist, "descending", scenarios)


def assess_asian_session(price, cv) -> PositionAssessment:
    df_, dc = cv["desc_floor"], cv["desc_ceiling"]
    lines = {"Desc Floor": df_, "Desc Ceiling": dc}
    nearest, dist = _find_nearest(price, lines)
    scenarios = []

    if price > dc:
        zone, label = "ABOVE_DESC", "Above Descending Channel"
        scenarios = [
            TradeScenario("LONG ES", dc, "Descending Ceiling", "Broke above — ceiling becomes support", strength="STRONG"),
            TradeScenario("SHORT ES", dc, "Descending Ceiling", "If fails, sell back to floor", df_, "Descending Floor", is_primary=False, strength="CAUTION"),
        ]
    elif price >= df_:
        zone, label = "IN_DESC", "Inside Descending Channel"
        scenarios = [
            TradeScenario("LONG ES", df_, "Descending Floor", "Buy off floor for bounce to ceiling", dc, "Descending Ceiling"),
            TradeScenario("SHORT ES", dc, "Descending Ceiling", "Sell off ceiling for drop to floor", df_, "Descending Floor"),
        ]
    else:
        zone, label = "BELOW_DESC", "Below Descending Channel"
        scenarios = [
            TradeScenario("SHORT ES", df_, "Descending Floor", "Broke below — floor becomes resistance", strength="STRONG"),
            TradeScenario("LONG ES", df_, "Descending Floor", "If reclaims, buy to ceiling", dc, "Descending Ceiling", is_primary=False, strength="CAUTION"),
        ]

    _add_trade_details(scenarios, abs(dc - df_), is_spx=False)
    return PositionAssessment(zone, label, nearest, dist, "asian", scenarios)


def round_strike(price, increment=5):
    return int(round(price / increment) * increment)


def convert_es_to_spx(es_vals, offset):
    return {k: (v - offset if v is not None else None) for k, v in es_vals.items()}


def get_session_mode(current_time=None):
    if current_time is None:
        current_time = datetime.now(CT)
    else:
        current_time = current_time.astimezone(CT)
    h, m = current_time.hour, current_time.minute
    if 17 <= h <= 20: return "asian"
    if 5 <= h < 8 or (h == 8 and m < 30): return "pre_rth"
    if (h == 8 and m >= 30) or (8 < h < 13): return "rth"
    if 13 <= h < 15: return "afternoon"
    return "off"
