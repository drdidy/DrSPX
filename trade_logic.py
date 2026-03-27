"""
SPX Prophet — Trade Logic Module
Handles alternating day logic, trade scenarios, position assessment,
strike calculation, and prop firm risk management.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime, date, time as dtime
import pytz

CT = pytz.timezone("America/Chicago")

STRIKE_OFFSET = 20  # ±20 from entry for 0DTE strike selection


STOP_LOSS_POINTS = 6       # SPX points for stop loss
TP1_PCT = 0.25             # 25% of channel width
TP2_PCT = 0.50             # 50% of channel width
TP3_PCT = 0.75             # 75% of channel width
ES_STOP_TICKS = 8          # ES ticks for prop firm stop (8 ticks = 2 pts)
ES_TP_MULTIPLIER = 2.0     # Risk:Reward for ES trades


@dataclass
class TradeScenario:
    """A potential trade scenario based on price position and day type."""
    direction: str          # "CALLS" or "PUTS"
    entry_level: float      # Price level for entry
    entry_label: str        # Which line (e.g., "Ascending Floor")
    rationale: str          # Why this trade
    target_level: Optional[float] = None
    target_label: Optional[str] = None
    strike: Optional[int] = None
    contract_ticker: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    is_primary: bool = True
    strength: str = "STANDARD"  # "STRONG", "STANDARD", "CAUTION"


@dataclass
class PositionAssessment:
    """Assessment of where price is relative to the channels."""
    zone: str               # "ABOVE_ASC", "IN_ASC", "BETWEEN", "IN_DESC", "BELOW_DESC"
    zone_label: str         # Human-readable zone description
    nearest_line: str       # Nearest channel line
    nearest_distance: float # Distance to nearest line
    day_type: str           # "ascending" or "descending"
    scenarios: List[TradeScenario] = None

    def __post_init__(self):
        if self.scenarios is None:
            self.scenarios = []


@dataclass
class PropFirmRisk:
    """Prop firm risk tracking for The Futures Desk."""
    max_es_contracts: int = 4
    max_mes_contracts: int = 40
    daily_loss_limit: float = 400.0
    current_contracts_es: int = 0
    current_contracts_mes: int = 0
    current_pnl: float = 0.0

    @property
    def remaining_loss_capacity(self) -> float:
        return self.daily_loss_limit + self.current_pnl  # pnl is negative when losing

    @property
    def risk_pct(self) -> float:
        if self.current_pnl >= 0:
            return 0.0
        return min(100.0, (abs(self.current_pnl) / self.daily_loss_limit) * 100)

    @property
    def risk_status(self) -> str:
        pct = self.risk_pct
        if pct == 0:
            return "CLEAR"
        elif pct < 50:
            return "ACTIVE"
        elif pct < 75:
            return "CAUTION"
        elif pct < 100:
            return "DANGER"
        else:
            return "LIMIT HIT"


def determine_position(
    price: float,
    asc_floor: float,
    asc_ceiling: float,
    desc_floor: float,
    desc_ceiling: float,
    asc_extreme: Optional[float] = None,
    desc_extreme: Optional[float] = None
) -> str:
    """
    Determine where price is relative to the channels.
    Returns zone identifier.
    """
    if price > asc_ceiling:
        if asc_extreme and price > asc_extreme:
            return "ABOVE_ASC_EXTREME"
        return "ABOVE_ASC"
    elif price >= asc_floor:
        return "IN_ASC"
    elif price > desc_ceiling:
        return "BETWEEN"
    elif price >= desc_floor:
        return "IN_DESC"
    else:
        if desc_extreme and price < desc_extreme:
            return "BELOW_DESC_EXTREME"
        return "BELOW_DESC"


def get_zone_label(zone: str) -> str:
    """Human-readable zone label."""
    labels = {
        "ABOVE_ASC_EXTREME": "Above Ascending Extreme",
        "ABOVE_ASC": "Above Ascending Channel",
        "IN_ASC": "Inside Ascending Channel",
        "BETWEEN": "Between Channels",
        "IN_DESC": "Inside Descending Channel",
        "BELOW_DESC": "Below Descending Channel",
        "BELOW_DESC_EXTREME": "Below Descending Extreme",
    }
    return labels.get(zone, zone)


def assess_position_ascending_day(
    price: float,
    channel_values: dict
) -> PositionAssessment:
    """
    Assess position and generate trade scenarios for an ASCENDING day.
    On ascending days, the ascending channel is the active channel.
    """
    af = channel_values["asc_floor"]
    ac = channel_values["asc_ceiling"]
    df_ = channel_values["desc_floor"]
    dc = channel_values["desc_ceiling"]
    ae = channel_values.get("asc_extreme")
    de = channel_values.get("desc_extreme")

    zone = determine_position(price, af, ac, df_, dc, ae, de)
    zone_label = get_zone_label(zone)

    # Find nearest line
    lines = {
        "Asc Floor": af, "Asc Ceiling": ac,
        "Desc Floor": df_, "Desc Ceiling": dc,
    }
    if ae:
        lines["Asc Extreme"] = ae
    if de:
        lines["Desc Extreme"] = de

    nearest_line = min(lines.keys(), key=lambda k: abs(price - lines[k]))
    nearest_dist = abs(price - lines[nearest_line])

    scenarios = []

    if zone == "IN_ASC":
        # Inside ascending channel on ascending day
        scenarios.append(TradeScenario(
            direction="CALLS",
            entry_level=af,
            entry_label="Ascending Floor",
            rationale="Buy off the ascending channel floor on ascending day",
            target_level=ac,
            target_label="Ascending Ceiling",
            strength="STRONG"
        ))
        scenarios.append(TradeScenario(
            direction="PUTS",
            entry_level=ac,
            entry_label="Ascending Ceiling",
            rationale="Sell off the ascending channel ceiling",
            target_level=af,
            target_label="Ascending Floor",
            is_primary=False
        ))

    elif zone == "ABOVE_ASC" or zone == "ABOVE_ASC_EXTREME":
        # Above ascending channel on ascending day
        scenarios.append(TradeScenario(
            direction="CALLS",
            entry_level=ac,
            entry_label="Ascending Ceiling",
            rationale="Ascending ceiling becomes support — buy higher",
            target_level=ae,
            target_label="Ascending Extreme",
            strength="STRONG"
        ))
        scenarios.append(TradeScenario(
            direction="CALLS",
            entry_level=af,
            entry_label="Ascending Floor",
            rationale="If drops to ascending floor, buy for bounce",
            is_primary=False
        ))

    elif zone == "BETWEEN":
        # Between channels on ascending day
        scenarios.append(TradeScenario(
            direction="CALLS",
            entry_level=dc,
            entry_label="Descending Ceiling",
            rationale="Rally from descending ceiling up to ascending floor",
            target_level=af,
            target_label="Ascending Floor",
            strength="STRONG"
        ))
        scenarios.append(TradeScenario(
            direction="PUTS",
            entry_level=af,
            entry_label="Ascending Floor",
            rationale="Rejected at ascending floor — sell back to descending ceiling",
            target_level=dc,
            target_label="Descending Ceiling",
            is_primary=False,
            strength="CAUTION"
        ))

    elif zone == "IN_DESC":
        # Inside descending channel on ascending day — could rally through
        scenarios.append(TradeScenario(
            direction="CALLS",
            entry_level=df_,
            entry_label="Descending Floor",
            rationale="On ascending day, market can rally through descending channel to ascending boundary",
            target_level=af,
            target_label="Ascending Floor",
            strength="STRONG"
        ))
        scenarios.append(TradeScenario(
            direction="PUTS",
            entry_level=dc,
            entry_label="Descending Ceiling",
            rationale="Rejection at descending ceiling before continuation lower",
            is_primary=False,
            strength="CAUTION"
        ))

    elif zone in ("BELOW_DESC", "BELOW_DESC_EXTREME"):
        # Below descending channel on ascending day — strong rally potential
        scenarios.append(TradeScenario(
            direction="CALLS",
            entry_level=df_,
            entry_label="Descending Floor",
            rationale="Far below on ascending day — market could rally through descending to ascending channel",
            target_level=af,
            target_label="Ascending Floor",
            strength="STRONG"
        ))

    # Calculate strikes, stop loss, take profits, and contract ticker
    channel_width = ac - af
    for s in scenarios:
        if s.direction == "CALLS":
            s.strike = round_strike(s.entry_level - STRIKE_OFFSET)
            s.stop_loss = s.entry_level - STOP_LOSS_POINTS
            s.take_profit_1 = s.entry_level + (channel_width * TP1_PCT)
            s.take_profit_2 = s.entry_level + (channel_width * TP2_PCT)
            s.take_profit_3 = s.entry_level + (channel_width * TP3_PCT)
        else:
            s.strike = round_strike(s.entry_level + STRIKE_OFFSET)
            s.stop_loss = s.entry_level + STOP_LOSS_POINTS
            s.take_profit_1 = s.entry_level - (channel_width * TP1_PCT)
            s.take_profit_2 = s.entry_level - (channel_width * TP2_PCT)
            s.take_profit_3 = s.entry_level - (channel_width * TP3_PCT)

    return PositionAssessment(
        zone=zone,
        zone_label=zone_label,
        nearest_line=nearest_line,
        nearest_distance=nearest_dist,
        day_type="ascending",
        scenarios=scenarios
    )


def assess_position_descending_day(
    price: float,
    channel_values: dict
) -> PositionAssessment:
    """
    Assess position and generate trade scenarios for a DESCENDING day.
    On descending days, the descending channel is the active channel.
    """
    af = channel_values["asc_floor"]
    ac = channel_values["asc_ceiling"]
    df_ = channel_values["desc_floor"]
    dc = channel_values["desc_ceiling"]
    ae = channel_values.get("asc_extreme")
    de = channel_values.get("desc_extreme")

    zone = determine_position(price, af, ac, df_, dc, ae, de)
    zone_label = get_zone_label(zone)

    lines = {
        "Asc Floor": af, "Asc Ceiling": ac,
        "Desc Floor": df_, "Desc Ceiling": dc,
    }
    if ae:
        lines["Asc Extreme"] = ae
    if de:
        lines["Desc Extreme"] = de

    nearest_line = min(lines.keys(), key=lambda k: abs(price - lines[k]))
    nearest_dist = abs(price - lines[nearest_line])

    scenarios = []

    if zone == "IN_DESC":
        # Inside descending channel on descending day
        scenarios.append(TradeScenario(
            direction="CALLS",
            entry_level=df_,
            entry_label="Descending Floor",
            rationale="Buy off the descending channel floor on descending day",
            target_level=dc,
            target_label="Descending Ceiling",
        ))
        scenarios.append(TradeScenario(
            direction="PUTS",
            entry_level=dc,
            entry_label="Descending Ceiling",
            rationale="Sell off the descending channel ceiling",
            target_level=df_,
            target_label="Descending Floor",
            strength="STRONG"
        ))

    elif zone in ("BELOW_DESC", "BELOW_DESC_EXTREME"):
        # Below descending channel on descending day
        scenarios.append(TradeScenario(
            direction="PUTS",
            entry_level=df_,
            entry_label="Descending Floor",
            rationale="Descending floor becomes resistance — sell lower",
            target_level=de,
            target_label="Descending Extreme",
            strength="STRONG"
        ))

    elif zone == "BETWEEN":
        # Between channels on descending day
        scenarios.append(TradeScenario(
            direction="PUTS",
            entry_level=af,
            entry_label="Ascending Floor",
            rationale="Drop from ascending floor to descending ceiling",
            target_level=dc,
            target_label="Descending Ceiling",
            strength="STRONG"
        ))
        scenarios.append(TradeScenario(
            direction="CALLS",
            entry_level=dc,
            entry_label="Descending Ceiling",
            rationale="Bounce at descending ceiling back to ascending floor",
            target_level=af,
            target_label="Ascending Floor",
            is_primary=False,
            strength="CAUTION"
        ))

    elif zone == "IN_ASC":
        # Inside ascending channel on descending day — could drop through
        scenarios.append(TradeScenario(
            direction="PUTS",
            entry_level=ac,
            entry_label="Ascending Ceiling",
            rationale="On descending day, market can drop through ascending channel to descending boundary",
            target_level=dc,
            target_label="Descending Ceiling",
            strength="STRONG"
        ))
        scenarios.append(TradeScenario(
            direction="CALLS",
            entry_level=af,
            entry_label="Ascending Floor",
            rationale="Bounce at ascending floor before continuation",
            is_primary=False,
            strength="CAUTION"
        ))

    elif zone in ("ABOVE_ASC", "ABOVE_ASC_EXTREME"):
        # Above ascending channel on descending day — strong drop potential
        scenarios.append(TradeScenario(
            direction="PUTS",
            entry_level=ac,
            entry_label="Ascending Ceiling",
            rationale="Far above on descending day — market could drop through ascending to descending channel",
            target_level=dc,
            target_label="Descending Ceiling",
            strength="STRONG"
        ))

    # Calculate strikes, stop loss, take profits, and contract ticker
    channel_width = dc - df_
    for s in scenarios:
        if s.direction == "CALLS":
            s.strike = round_strike(s.entry_level - STRIKE_OFFSET)
            s.stop_loss = s.entry_level - STOP_LOSS_POINTS
            s.take_profit_1 = s.entry_level + (channel_width * TP1_PCT)
            s.take_profit_2 = s.entry_level + (channel_width * TP2_PCT)
            s.take_profit_3 = s.entry_level + (channel_width * TP3_PCT)
        else:
            s.strike = round_strike(s.entry_level + STRIKE_OFFSET)
            s.stop_loss = s.entry_level + STOP_LOSS_POINTS
            s.take_profit_1 = s.entry_level - (channel_width * TP1_PCT)
            s.take_profit_2 = s.entry_level - (channel_width * TP2_PCT)
            s.take_profit_3 = s.entry_level - (channel_width * TP3_PCT)

    return PositionAssessment(
        zone=zone,
        zone_label=zone_label,
        nearest_line=nearest_line,
        nearest_distance=nearest_dist,
        day_type="descending",
        scenarios=scenarios
    )


def assess_asian_session(
    price: float,
    channel_values: dict
) -> PositionAssessment:
    """
    Assess position for Asian session prop firm trading (6 PM - 9 PM CT).
    Asian session primarily uses the descending channel.
    All values in ES terms (no SPX conversion needed).
    """
    df_ = channel_values["desc_floor"]
    dc = channel_values["desc_ceiling"]
    de = channel_values.get("desc_extreme")

    # For Asian session, we focus on descending channel
    if price > dc:
        zone = "ABOVE_DESC"
        zone_label = "Above Descending Channel"
    elif price >= df_:
        zone = "IN_DESC"
        zone_label = "Inside Descending Channel"
    else:
        zone = "BELOW_DESC"
        zone_label = "Below Descending Channel"

    lines = {"Desc Floor": df_, "Desc Ceiling": dc}
    if de:
        lines["Desc Extreme"] = de
    nearest_line = min(lines.keys(), key=lambda k: abs(price - lines[k]))
    nearest_dist = abs(price - lines[nearest_line])

    scenarios = []

    if zone == "IN_DESC":
        scenarios.append(TradeScenario(
            direction="LONG ES",
            entry_level=df_,
            entry_label="Descending Floor",
            rationale="Buy off descending floor for bounce to ceiling",
            target_level=dc,
            target_label="Descending Ceiling",
        ))
        scenarios.append(TradeScenario(
            direction="SHORT ES",
            entry_level=dc,
            entry_label="Descending Ceiling",
            rationale="Sell off descending ceiling for drop to floor",
            target_level=df_,
            target_label="Descending Floor",
        ))

    elif zone == "ABOVE_DESC":
        # Broke above — ceiling becomes support
        scenarios.append(TradeScenario(
            direction="LONG ES",
            entry_level=dc,
            entry_label="Descending Ceiling",
            rationale="Broke above ceiling — ceiling becomes support, buy higher",
            strength="STRONG"
        ))
        scenarios.append(TradeScenario(
            direction="SHORT ES",
            entry_level=dc,
            entry_label="Descending Ceiling",
            rationale="If fails to hold above ceiling, sell back to floor",
            target_level=df_,
            target_label="Descending Floor",
            is_primary=False,
            strength="CAUTION"
        ))

    elif zone == "BELOW_DESC":
        # Broke below — floor becomes resistance
        scenarios.append(TradeScenario(
            direction="SHORT ES",
            entry_level=df_,
            entry_label="Descending Floor",
            rationale="Broke below floor — floor becomes resistance, sell lower",
            strength="STRONG"
        ))
        scenarios.append(TradeScenario(
            direction="LONG ES",
            entry_level=df_,
            entry_label="Descending Floor",
            rationale="If reclaims above floor, buy back to ceiling",
            target_level=dc,
            target_label="Descending Ceiling",
            is_primary=False,
            strength="CAUTION"
        ))

    return PositionAssessment(
        zone=zone,
        zone_label=zone_label,
        nearest_line=nearest_line,
        nearest_distance=nearest_dist,
        day_type="asian_session",
        scenarios=scenarios
    )


def round_strike(price: float, increment: int = 5) -> int:
    """Round to nearest strike increment (default 5 for SPX)."""
    return int(round(price / increment) * increment)


def format_spxw_ticker(strike: int, expiration_date: date, is_call: bool) -> str:
    """Format SPXW option ticker symbol."""
    date_str = expiration_date.strftime("%y%m%d")
    cp = "C" if is_call else "P"
    strike_str = f"{strike * 1000:08d}"
    return f"O:SPXW{date_str}{cp}{strike_str}"


def convert_es_to_spx(es_values: dict, offset: float) -> dict:
    """Convert all ES channel values to SPX by subtracting the offset."""
    spx_values = {}
    for key, value in es_values.items():
        if value is not None:
            spx_values[key] = value - offset
        else:
            spx_values[key] = None
    return spx_values


def get_session_mode(current_time: datetime = None) -> str:
    """
    Determine which trading mode based on current time.
    Returns: 'asian', 'pre_rth', 'rth', 'afternoon', 'off'
    """
    if current_time is None:
        current_time = datetime.now(CT)
    else:
        current_time = current_time.astimezone(CT)

    hour = current_time.hour
    minute = current_time.minute

    if 18 <= hour <= 20:  # 6 PM - 9 PM
        return "asian"
    elif 5 <= hour < 8 or (hour == 8 and minute < 30):
        return "pre_rth"
    elif (hour == 8 and minute >= 30) or (8 < hour < 11) or (hour == 11 and minute <= 30):
        return "rth"
    elif 11 < hour < 15:
        return "afternoon"
    else:
        return "off"
