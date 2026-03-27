"""
SPX Prophet — Channel Builder Module
Constructs ascending and descending channels from prior day 12-3 PM CT data.
Projects lines forward using ±0.52 per 30-minute block.
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
    """A price/time anchor point for line projection."""
    price: float
    timestamp: datetime
    label: str  # e.g., "Lowest Bounce", "Highest Rejection", "Highest Wick", "Lowest Wick"


@dataclass
class ProjectedLine:
    """A projected line from an anchor point."""
    anchor: AnchorPoint
    direction: str  # "ascending" or "descending"
    slope: float  # per 30-min block, positive for ascending, negative for descending

    def value_at(self, target_time: datetime) -> float:
        """Calculate projected value at a given time."""
        blocks = count_blocks(self.anchor.timestamp, target_time)
        return self.anchor.price + (self.slope * blocks)


@dataclass
class Channel:
    """A channel defined by two lines (floor and ceiling)."""
    floor: ProjectedLine
    ceiling: ProjectedLine
    channel_type: str  # "ascending" or "descending"
    extreme_line: Optional[ProjectedLine] = None  # highest wick (asc) or lowest wick (desc)

    def floor_at(self, t: datetime) -> float:
        return self.floor.value_at(t)

    def ceiling_at(self, t: datetime) -> float:
        return self.ceiling.value_at(t)

    def extreme_at(self, t: datetime) -> Optional[float]:
        if self.extreme_line:
            return self.extreme_line.value_at(t)
        return None

    def midpoint_at(self, t: datetime) -> float:
        return (self.floor_at(t) + self.ceiling_at(t)) / 2


@dataclass
class ChannelSystem:
    """Complete channel system with both ascending and descending channels."""
    ascending: Channel
    descending: Channel
    anchor_points: List[AnchorPoint] = field(default_factory=list)
    construction_date: Optional[date] = None


def count_blocks(t0: datetime, t1: datetime) -> float:
    """
    Count 30-minute blocks between two timestamps.
    Skips CME maintenance window (4 PM - 5 PM CT Mon-Thu).
    Skips weekend gap (Fri 4 PM CT to Sun 5 PM CT).
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
            # Partial block
            remaining_mins = (t1 - current).total_seconds() / 60
            partial = remaining_mins / 30.0

            # Check if this partial block is in maintenance or weekend
            if not _is_skip_time(current):
                blocks += partial
            break

        if not _is_skip_time(current):
            blocks += 1.0

        current = next_block

    return blocks


def _is_skip_time(dt: datetime) -> bool:
    """Check if a timestamp falls in maintenance or weekend gap."""
    dt = dt.astimezone(CT)
    wd = dt.weekday()  # Mon=0, Sun=6

    # Weekend: Saturday all day, Sunday before 5 PM
    if wd == 5:
        return True
    if wd == 6 and dt.hour < 17:
        return True

    # Friday after 4 PM
    if wd == 4 and dt.hour >= 16:
        return True

    # Maintenance: 4 PM - 5 PM CT Mon-Thu
    if wd < 4 and dt.hour == 16:
        return True

    return False


def find_bounces_and_rejections(df_1min: pd.DataFrame, lookback: int = 5) -> Tuple[List[AnchorPoint], List[AnchorPoint]]:
    """
    Find bounces (local lows) and rejections (local highs) on the line chart (Close prices).
    Uses a simple local min/max detection with a lookback window.

    Returns: (bounces, rejections)
    """
    if df_1min.empty or len(df_1min) < lookback * 2 + 1:
        return [], []

    close = df_1min["Close"].values
    timestamps = df_1min.index
    bounces = []
    rejections = []

    for i in range(lookback, len(close) - lookback):
        window_before = close[i - lookback:i]
        window_after = close[i + 1:i + lookback + 1]

        # Local minimum (bounce) — price lower than surrounding bars
        if close[i] <= np.min(window_before) and close[i] <= np.min(window_after):
            bounces.append(AnchorPoint(
                price=float(close[i]),
                timestamp=timestamps[i],
                label="Bounce"
            ))

        # Local maximum (rejection) — price higher than surrounding bars
        if close[i] >= np.max(window_before) and close[i] >= np.max(window_after):
            rejections.append(AnchorPoint(
                price=float(close[i]),
                timestamp=timestamps[i],
                label="Rejection"
            ))

    return bounces, rejections


def find_extreme_wicks(df_30min_or_1min: pd.DataFrame) -> Tuple[AnchorPoint, AnchorPoint]:
    """
    Find highest wick (High) and lowest wick (Low) in the 12-3 PM window.
    Uses candlestick data (High/Low columns).

    Returns: (highest_wick, lowest_wick)
    """
    if df_30min_or_1min.empty:
        raise ValueError("No data provided for wick detection")

    # Highest wick
    high_idx = df_30min_or_1min["High"].idxmax()
    highest_wick = AnchorPoint(
        price=float(df_30min_or_1min.loc[high_idx, "High"]),
        timestamp=high_idx,
        label="Highest Wick"
    )

    # Lowest wick
    low_idx = df_30min_or_1min["Low"].idxmin()
    lowest_wick = AnchorPoint(
        price=float(df_30min_or_1min.loc[low_idx, "Low"]),
        timestamp=low_idx,
        label="Lowest Wick"
    )

    return highest_wick, lowest_wick


def build_channels(
    lowest_bounce: AnchorPoint,
    highest_rejection: AnchorPoint,
    highest_wick: AnchorPoint,
    lowest_wick: AnchorPoint
) -> ChannelSystem:
    """
    Build the complete channel system from anchor points.

    Ascending channel:
      - Floor: ascending line from lowest_bounce (+0.52/block)
      - Ceiling: ascending line from highest_rejection (+0.52/block)
      - Extreme: ascending line from highest_wick (+0.52/block)

    Descending channel:
      - Ceiling: descending line from highest_rejection (-0.52/block)
      - Floor: descending line from lowest_bounce (-0.52/block)
      - Extreme: descending line from lowest_wick (-0.52/block)
    """

    # Ascending channel
    asc_floor = ProjectedLine(
        anchor=lowest_bounce,
        direction="ascending",
        slope=SLOPE
    )
    asc_ceiling = ProjectedLine(
        anchor=highest_rejection,
        direction="ascending",
        slope=SLOPE
    )
    asc_extreme = ProjectedLine(
        anchor=highest_wick,
        direction="ascending",
        slope=SLOPE
    )

    ascending = Channel(
        floor=asc_floor,
        ceiling=asc_ceiling,
        channel_type="ascending",
        extreme_line=asc_extreme
    )

    # Descending channel
    desc_ceiling = ProjectedLine(
        anchor=highest_rejection,
        direction="descending",
        slope=-SLOPE
    )
    desc_floor = ProjectedLine(
        anchor=lowest_bounce,
        direction="descending",
        slope=-SLOPE
    )
    desc_extreme = ProjectedLine(
        anchor=lowest_wick,
        direction="descending",
        slope=-SLOPE
    )

    descending = Channel(
        floor=desc_floor,
        ceiling=desc_ceiling,
        channel_type="descending",
        extreme_line=desc_extreme
    )

    return ChannelSystem(
        ascending=ascending,
        descending=descending,
        anchor_points=[lowest_bounce, highest_rejection, highest_wick, lowest_wick],
        construction_date=lowest_bounce.timestamp.date()
    )


def auto_build_channels(df_1min: pd.DataFrame, df_30min: pd.DataFrame) -> Optional[ChannelSystem]:
    """
    Automatically build channels from raw data.
    Uses 1-min for bounce/rejection detection, 30-min or 1-min for wick detection.
    """
    if df_1min.empty:
        return None

    # Find bounces and rejections on line chart
    bounces, rejections = find_bounces_and_rejections(df_1min, lookback=5)

    if not bounces or not rejections:
        return None

    # Find lowest bounce and highest rejection
    lowest_bounce = min(bounces, key=lambda b: b.price)
    lowest_bounce.label = "Lowest Bounce"

    highest_rejection = max(rejections, key=lambda r: r.price)
    highest_rejection.label = "Highest Rejection"

    # Find extreme wicks — use whichever dataframe has data
    wick_df = df_30min if not df_30min.empty else df_1min
    highest_wick, lowest_wick = find_extreme_wicks(wick_df)

    return build_channels(lowest_bounce, highest_rejection, highest_wick, lowest_wick)


def get_channel_values_at_time(
    channels: ChannelSystem,
    target_time: datetime
) -> dict:
    """
    Get all channel values at a specific time.
    Returns dict with all line values for easy access.
    """
    return {
        "asc_floor": channels.ascending.floor_at(target_time),
        "asc_ceiling": channels.ascending.ceiling_at(target_time),
        "asc_extreme": channels.ascending.extreme_at(target_time),
        "asc_midpoint": channels.ascending.midpoint_at(target_time),
        "desc_floor": channels.descending.floor_at(target_time),
        "desc_ceiling": channels.descending.ceiling_at(target_time),
        "desc_extreme": channels.descending.extreme_at(target_time),
        "desc_midpoint": channels.descending.midpoint_at(target_time),
    }


def get_projection_table(
    channels: ChannelSystem,
    start_time: datetime,
    end_time: datetime,
    interval_minutes: int = 30
) -> pd.DataFrame:
    """
    Generate a projection table from start_time to end_time.
    Shows all channel values at each time interval.
    """
    times = []
    current = start_time
    while current <= end_time:
        times.append(current)
        current += timedelta(minutes=interval_minutes)

    rows = []
    for t in times:
        vals = get_channel_values_at_time(channels, t)
        rows.append({
            "Time": t.strftime("%I:%M %p"),
            "Asc Extreme": round(vals["asc_extreme"], 2) if vals["asc_extreme"] else "-",
            "Asc Ceiling": round(vals["asc_ceiling"], 2),
            "Asc Floor": round(vals["asc_floor"], 2),
            "Desc Ceiling": round(vals["desc_ceiling"], 2),
            "Desc Floor": round(vals["desc_floor"], 2),
            "Desc Extreme": round(vals["desc_extreme"], 2) if vals["desc_extreme"] else "-",
        })

    return pd.DataFrame(rows)
