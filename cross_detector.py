"""
SPX Prophet — Cross Detector Module
Monitors 8 EMA / 50 EMA crossovers on ES 1-minute chart.
Validates crosses against divergence threshold and hour boundary timing.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List
import pytz

CT = pytz.timezone("America/Chicago")

DIVERGENCE_THRESHOLD = 10.0  # Minimum points 8 EMA must diverge from 50 EMA before cross
HOUR_BOUNDARY_MINUTES = 10   # Cross must be within this many minutes of hour mark


@dataclass
class CrossEvent:
    """Represents a detected 8/50 EMA cross."""
    timestamp: datetime
    cross_type: str           # "bullish" (8 crosses above 50) or "bearish" (8 crosses below 50)
    divergence: float         # Max divergence before the cross
    price_at_cross: float     # ES price at the cross
    ema_8: float
    ema_50: float
    is_valid_divergence: bool  # Was divergence >= threshold?
    is_valid_timing: bool      # Was it near an hour boundary?
    is_valid: bool             # Both conditions met?
    nearest_hour: str          # Which hour boundary it's near


@dataclass
class CrossMonitorState:
    """Current state of the cross monitor."""
    current_spread: float          # Current 8 EMA - 50 EMA
    current_ema_8: float
    current_ema_50: float
    current_price: float
    max_divergence_since_last_cross: float
    divergence_direction: str      # "above" or "below" (8 relative to 50)
    is_diverged_enough: bool       # Has divergence hit threshold?
    status: str                    # "WATCHING", "READY", "CROSS_DETECTED"
    status_detail: str             # Human-readable status description
    last_cross: Optional[CrossEvent] = None
    recent_crosses: List[CrossEvent] = None

    def __post_init__(self):
        if self.recent_crosses is None:
            self.recent_crosses = []


def detect_crosses(df: pd.DataFrame, lookback_hours: int = 4) -> List[CrossEvent]:
    """
    Detect all 8/50 EMA crosses in the dataframe.
    Only looks at the most recent lookback_hours of data.
    """
    if df.empty or "EMA_8" not in df.columns or "EMA_50" not in df.columns:
        return []

    # Filter to recent data
    now = df.index[-1]
    cutoff = now - timedelta(hours=lookback_hours)
    recent = df[df.index >= cutoff].copy()

    if len(recent) < 2:
        return []

    spread = recent["EMA_8"] - recent["EMA_50"]
    crosses = []

    # Track max divergence between crosses
    max_div = 0.0
    max_div_value = 0.0

    for i in range(1, len(spread)):
        current_spread = spread.iloc[i]
        prev_spread = spread.iloc[i - 1]

        # Track divergence
        if abs(current_spread) > abs(max_div):
            max_div = current_spread
            max_div_value = abs(current_spread)

        # Detect cross: sign change in spread
        if prev_spread * current_spread < 0:  # Sign changed
            ts = recent.index[i]
            cross_type = "bullish" if current_spread > 0 else "bearish"

            # Check hour boundary timing
            minute = ts.minute
            is_near_hour = minute <= HOUR_BOUNDARY_MINUTES or minute >= (60 - HOUR_BOUNDARY_MINUTES)

            if minute <= HOUR_BOUNDARY_MINUTES:
                nearest_hour = ts.strftime("%I:00 %p")
            else:
                next_hour = ts + timedelta(hours=1)
                nearest_hour = next_hour.strftime("%I:00 %p")

            # Check divergence threshold
            is_valid_div = max_div_value >= DIVERGENCE_THRESHOLD

            cross = CrossEvent(
                timestamp=ts,
                cross_type=cross_type,
                divergence=max_div_value,
                price_at_cross=float(recent["Close"].iloc[i]),
                ema_8=float(recent["EMA_8"].iloc[i]),
                ema_50=float(recent["EMA_50"].iloc[i]),
                is_valid_divergence=is_valid_div,
                is_valid_timing=is_near_hour,
                is_valid=is_valid_div and is_near_hour,
                nearest_hour=nearest_hour
            )
            crosses.append(cross)

            # Reset divergence tracking after cross
            max_div = 0.0
            max_div_value = 0.0

    return crosses


def get_monitor_state(df: pd.DataFrame) -> CrossMonitorState:
    """
    Get the current state of the 8/50 cross monitor.
    Returns a comprehensive state object for the UI.
    """
    if df.empty or "EMA_8" not in df.columns:
        return CrossMonitorState(
            current_spread=0.0,
            current_ema_8=0.0,
            current_ema_50=0.0,
            current_price=0.0,
            max_divergence_since_last_cross=0.0,
            divergence_direction="flat",
            is_diverged_enough=False,
            status="NO DATA",
            status_detail="Waiting for ES 1-min data..."
        )

    current_ema_8 = float(df["EMA_8"].iloc[-1])
    current_ema_50 = float(df["EMA_50"].iloc[-1])
    current_spread = current_ema_8 - current_ema_50
    current_price = float(df["Close"].iloc[-1])

    # Detect recent crosses
    crosses = detect_crosses(df)

    # Calculate max divergence since last cross
    if crosses:
        last_cross = crosses[-1]
        since_last = df[df.index > last_cross.timestamp]
        if not since_last.empty:
            spreads_since = since_last["EMA_8"] - since_last["EMA_50"]
            max_div = float(spreads_since.abs().max())
        else:
            max_div = abs(current_spread)
    else:
        # No crosses found, use all available data
        all_spreads = df["EMA_8"] - df["EMA_50"]
        # Find max divergence from the beginning
        max_div = float(all_spreads.abs().max())
        last_cross = None

    direction = "above" if current_spread > 0 else "below"
    is_diverged = max_div >= DIVERGENCE_THRESHOLD

    # Determine status
    if is_diverged and abs(current_spread) < 3.0:
        status = "READY"
        status_detail = f"Divergence sufficient ({max_div:.1f} pts). EMAs converging — cross imminent!"
    elif is_diverged:
        status = "WATCHING"
        status_detail = f"Divergence sufficient ({max_div:.1f} pts). Waiting for EMAs to converge."
    elif abs(current_spread) < 3.0:
        status = "WATCHING"
        status_detail = f"EMAs close but divergence only {max_div:.1f} pts (need {DIVERGENCE_THRESHOLD}+)."
    else:
        status = "WATCHING"
        status_detail = f"8 EMA {'above' if current_spread > 0 else 'below'} 50 EMA by {abs(current_spread):.1f} pts. Max divergence: {max_div:.1f} pts."

    # Check if a cross just happened (within last 5 minutes)
    if crosses:
        latest = crosses[-1]
        now = df.index[-1]
        if (now - latest.timestamp).total_seconds() < 300:
            if latest.is_valid:
                status = "CROSS — VALID"
                status_detail = f"{'BULLISH' if latest.cross_type == 'bullish' else 'BEARISH'} cross at {latest.timestamp.strftime('%I:%M %p')} | Divergence: {latest.divergence:.1f} pts | Near {latest.nearest_hour}"
            else:
                reasons = []
                if not latest.is_valid_divergence:
                    reasons.append(f"divergence only {latest.divergence:.1f} pts")
                if not latest.is_valid_timing:
                    reasons.append("not near hour boundary")
                status = "CROSS — INVALID"
                status_detail = f"Cross detected but invalid: {', '.join(reasons)}"

    return CrossMonitorState(
        current_spread=current_spread,
        current_ema_8=current_ema_8,
        current_ema_50=current_ema_50,
        current_price=current_price,
        max_divergence_since_last_cross=max_div,
        divergence_direction=direction,
        is_diverged_enough=is_diverged,
        status=status,
        status_detail=status_detail,
        last_cross=crosses[-1] if crosses else None,
        recent_crosses=crosses[-5:] if crosses else []
    )


def check_line_proximity(
    current_price: float,
    channel_values: dict,
    proximity_threshold: float = 3.0
) -> Optional[str]:
    """
    Check if current price is near any projected channel line.
    Returns the name of the nearest line if within threshold, else None.
    """
    line_checks = [
        ("asc_floor", channel_values.get("asc_floor")),
        ("asc_ceiling", channel_values.get("asc_ceiling")),
        ("asc_extreme", channel_values.get("asc_extreme")),
        ("desc_floor", channel_values.get("desc_floor")),
        ("desc_ceiling", channel_values.get("desc_ceiling")),
        ("desc_extreme", channel_values.get("desc_extreme")),
    ]

    nearest = None
    nearest_dist = float("inf")

    for name, value in line_checks:
        if value is None:
            continue
        dist = abs(current_price - value)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest = name

    if nearest_dist <= proximity_threshold:
        return nearest
    return None
