"""
SPX Prophet — Channel Builder Module
Constructs ascending/descending channels from prior day 12-3 PM CT data.
Projects lines at ±0.52 per 30-minute block.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import pytz

CT = pytz.timezone("America/Chicago")
SLOPE = 0.52  # Points per 30-minute block


@dataclass
class AnchorPoint:
    price: float
    timestamp: datetime
    label: str


@dataclass
class ProjectedLine:
    anchor: AnchorPoint
    direction: str  # "ascending" or "descending"
    slope: float

    def value_at(self, target_time: datetime) -> float:
        blocks = count_blocks(self.anchor.timestamp, target_time)
        return self.anchor.price + (self.slope * blocks)


@dataclass
class Channel:
    floor: ProjectedLine
    ceiling: ProjectedLine
    channel_type: str
    extreme_line: Optional[ProjectedLine] = None

    def floor_at(self, t: datetime) -> float:
        return self.floor.value_at(t)

    def ceiling_at(self, t: datetime) -> float:
        return self.ceiling.value_at(t)

    def extreme_at(self, t: datetime) -> Optional[float]:
        return self.extreme_line.value_at(t) if self.extreme_line else None

    def width_at(self, t: datetime) -> float:
        return abs(self.ceiling_at(t) - self.floor_at(t))


@dataclass
class ChannelSystem:
    ascending: Channel
    descending: Channel
    anchor_points: List[AnchorPoint] = field(default_factory=list)
    construction_date: Optional[date] = None


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK COUNTING
# ═══════════════════════════════════════════════════════════════════════════════

def count_blocks(t0: datetime, t1: datetime) -> float:
    """
    Count 30-minute blocks between t0 and t1.
    Skips 4-5 PM CT maintenance (Mon-Thu) and weekend gap (Fri 4 PM - Sun 5 PM).
    """
    if t0.tzinfo is None:
        t0 = CT.localize(t0)
    if t1.tzinfo is None:
        t1 = CT.localize(t1)
    t0 = t0.astimezone(CT)
    t1 = t1.astimezone(CT)

    if t1 < t0:
        return -count_blocks(t1, t0)

    blocks = 0.0
    current = t0
    while current < t1:
        next_block = current + timedelta(minutes=30)
        if next_block > t1:
            remaining = (t1 - current).total_seconds() / 60
            if not _is_skip_time(current):
                blocks += remaining / 30.0
            break
        if not _is_skip_time(current):
            blocks += 1.0
        current = next_block
    return blocks


def _is_skip_time(dt: datetime) -> bool:
    """Check if timestamp is in maintenance or weekend gap."""
    dt = dt.astimezone(CT)
    wd = dt.weekday()
    if wd == 5:
        return True
    if wd == 6 and dt.hour < 17:
        return True
    if wd == 4 and dt.hour >= 16:
        return True
    if wd < 4 and dt.hour == 16:
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# BOUNCE/REJECTION DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def find_bounces_and_rejections(df_1min: pd.DataFrame, lookback: int = 5) -> Tuple[List[AnchorPoint], List[AnchorPoint]]:
    """
    Detect local lows (bounces) and local highs (rejections) on the Close (line chart).
    """
    if df_1min.empty or len(df_1min) < lookback * 2 + 1:
        return [], []

    close = df_1min["Close"].values
    timestamps = df_1min.index
    bounces, rejections = [], []

    for i in range(lookback, len(close) - lookback):
        window_before = close[i - lookback:i]
        window_after = close[i + 1:i + lookback + 1]

        if close[i] <= np.min(window_before) and close[i] <= np.min(window_after):
            bounces.append(AnchorPoint(float(close[i]), timestamps[i], "Bounce"))

        if close[i] >= np.max(window_before) and close[i] >= np.max(window_after):
            rejections.append(AnchorPoint(float(close[i]), timestamps[i], "Rejection"))

    return bounces, rejections


def find_extreme_wicks(df: pd.DataFrame) -> Tuple[AnchorPoint, AnchorPoint]:
    """Find highest wick (High) and lowest wick (Low) in the dataframe."""
    high_idx = df["High"].idxmax()
    highest = AnchorPoint(float(df.loc[high_idx, "High"]), high_idx, "Highest Wick")
    low_idx = df["Low"].idxmin()
    lowest = AnchorPoint(float(df.loc[low_idx, "Low"]), low_idx, "Lowest Wick")
    return highest, lowest


# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL BUILDING
# ═══════════════════════════════════════════════════════════════════════════════

def build_channels(lb: AnchorPoint, hr: AnchorPoint, hw: AnchorPoint, lw: AnchorPoint) -> ChannelSystem:
    """
    Build channel system from 4 anchor points.
    Ascending: floor from LB (+0.52), ceiling from HR (+0.52), extreme from HW (+0.52)
    Descending: ceiling from HR (-0.52), floor from LB (-0.52), extreme from LW (-0.52)
    """
    ascending = Channel(
        floor=ProjectedLine(lb, "ascending", SLOPE),
        ceiling=ProjectedLine(hr, "ascending", SLOPE),
        channel_type="ascending",
        extreme_line=ProjectedLine(hw, "ascending", SLOPE)
    )
    descending = Channel(
        ceiling=ProjectedLine(hr, "descending", -SLOPE),
        floor=ProjectedLine(lb, "descending", -SLOPE),
        channel_type="descending",
        extreme_line=ProjectedLine(lw, "descending", -SLOPE)
    )
    return ChannelSystem(
        ascending=ascending,
        descending=descending,
        anchor_points=[lb, hr, hw, lw],
        construction_date=lb.timestamp.date()
    )


def auto_detect_anchors(df_1min: pd.DataFrame, df_30min: pd.DataFrame) -> Optional[dict]:
    """
    Auto-detect the 4 anchor points from afternoon data.
    Tries 30-min data first (matches TradingView line chart), falls back to 1-min.
    Returns dict with 'lb', 'hr', 'hw', 'lw' AnchorPoints or None.
    """
    detected = None

    # Try 30-min data first (preferred — matches line chart)
    if not df_30min.empty and len(df_30min) >= 3:
        bounces, rejections = find_bounces_and_rejections(df_30min, lookback=1)
        if bounces and rejections:
            detected = (bounces, rejections, df_30min)

    # Fallback to 1-min data, round timestamps to nearest 30-min
    if detected is None and not df_1min.empty:
        bounces, rejections = find_bounces_and_rejections(df_1min, lookback=5)
        if bounces and rejections:
            # Round timestamps to nearest 30-min mark
            for b in bounces:
                b.timestamp = _round_to_30min(b.timestamp)
            for r in rejections:
                r.timestamp = _round_to_30min(r.timestamp)
            detected = (bounces, rejections, df_1min)

    if detected is None:
        return None

    bounces, rejections, wick_df = detected
    lb = min(bounces, key=lambda b: b.price)
    lb.label = "Lowest Bounce"
    hr = max(rejections, key=lambda r: r.price)
    hr.label = "Highest Rejection"

    # Wicks from whichever data we have
    wick_source = df_30min if not df_30min.empty else df_1min
    hw, lw = find_extreme_wicks(wick_source)

    return {'lb': lb, 'hr': hr, 'hw': hw, 'lw': lw}


def _round_to_30min(ts: datetime) -> datetime:
    """Round a timestamp to the nearest 30-minute mark."""
    minute = ts.minute
    if minute < 15:
        rounded_min = 0
    elif minute < 45:
        rounded_min = 30
    else:
        rounded_min = 0
        ts = ts + timedelta(hours=1)
    return ts.replace(minute=rounded_min, second=0, microsecond=0)


def get_channel_values_at_time(channels: ChannelSystem, t: datetime) -> dict:
    """Get all channel line values at a specific time."""
    return {
        "asc_floor": channels.ascending.floor_at(t),
        "asc_ceiling": channels.ascending.ceiling_at(t),
        "asc_extreme": channels.ascending.extreme_at(t),
        "desc_ceiling": channels.descending.ceiling_at(t),
        "desc_floor": channels.descending.floor_at(t),
        "desc_extreme": channels.descending.extreme_at(t),
    }
