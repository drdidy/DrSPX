"""
SPX Prophet — Cross Detector Module
Monitors 8 EMA / 50 EMA crossovers on ES 1-minute chart.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List
import pytz

CT = pytz.timezone("America/Chicago")
DIVERGENCE_THRESHOLD = 10.0
HOUR_BOUNDARY_MINUTES = 10


@dataclass
class CrossEvent:
    timestamp: datetime
    cross_type: str       # "bullish" or "bearish"
    divergence: float
    price_at_cross: float
    ema_8: float
    ema_50: float
    is_valid_divergence: bool
    is_valid_timing: bool
    is_valid: bool
    nearest_hour: str


@dataclass
class CrossMonitorState:
    current_spread: float
    current_ema_8: float
    current_ema_50: float
    current_price: float
    max_divergence: float
    is_diverged_enough: bool
    status: str
    status_detail: str
    last_cross: Optional[CrossEvent] = None
    recent_crosses: List[CrossEvent] = field(default_factory=list)


def detect_crosses(df: pd.DataFrame, lookback_hours: int = 4) -> List[CrossEvent]:
    """Detect all 8/50 EMA crosses in recent data."""
    if df.empty or "EMA_8" not in df.columns:
        return []

    cutoff = df.index[-1] - timedelta(hours=lookback_hours)
    recent = df[df.index >= cutoff]
    if len(recent) < 2:
        return []

    spread = recent["EMA_8"] - recent["EMA_50"]
    crosses = []
    max_div_value = 0.0

    for i in range(1, len(spread)):
        current_spread = spread.iloc[i]
        prev_spread = spread.iloc[i - 1]

        if abs(current_spread) > max_div_value:
            max_div_value = abs(current_spread)

        if prev_spread * current_spread < 0:
            ts = recent.index[i]
            cross_type = "bullish" if current_spread > 0 else "bearish"
            minute = ts.minute
            is_near_hour = minute <= HOUR_BOUNDARY_MINUTES or minute >= (60 - HOUR_BOUNDARY_MINUTES)

            if minute <= HOUR_BOUNDARY_MINUTES:
                nearest_hour = ts.strftime("%I:00 %p")
            else:
                nearest_hour = (ts + timedelta(hours=1)).strftime("%I:00 %p")

            cross = CrossEvent(
                timestamp=ts,
                cross_type=cross_type,
                divergence=max_div_value,
                price_at_cross=float(recent["Close"].iloc[i]),
                ema_8=float(recent["EMA_8"].iloc[i]),
                ema_50=float(recent["EMA_50"].iloc[i]),
                is_valid_divergence=max_div_value >= DIVERGENCE_THRESHOLD,
                is_valid_timing=is_near_hour,
                is_valid=(max_div_value >= DIVERGENCE_THRESHOLD) and is_near_hour,
                nearest_hour=nearest_hour
            )
            crosses.append(cross)
            max_div_value = 0.0

    return crosses


def get_monitor_state(df: pd.DataFrame) -> CrossMonitorState:
    """Get current state of the 8/50 cross monitor."""
    if df.empty or "EMA_8" not in df.columns:
        return CrossMonitorState(0, 0, 0, 0, 0, False, "NO DATA", "Waiting for ES 1-min data...")

    ema8 = float(df["EMA_8"].iloc[-1])
    ema50 = float(df["EMA_50"].iloc[-1])
    spread = ema8 - ema50
    price = float(df["Close"].iloc[-1])
    crosses = detect_crosses(df)

    # Max divergence since last cross
    if crosses:
        since = df[df.index > crosses[-1].timestamp]
        max_div = float((since["EMA_8"] - since["EMA_50"]).abs().max()) if not since.empty else abs(spread)
    else:
        max_div = float((df["EMA_8"] - df["EMA_50"]).abs().max())

    is_diverged = max_div >= DIVERGENCE_THRESHOLD

    # Status
    if crosses and (df.index[-1] - crosses[-1].timestamp).total_seconds() < 300:
        cx = crosses[-1]
        if cx.is_valid:
            status = "CROSS — VALID"
            detail = f"{'BULLISH' if cx.cross_type == 'bullish' else 'BEARISH'} cross at {cx.timestamp.strftime('%I:%M %p')} | Div: {cx.divergence:.1f} pts | Near {cx.nearest_hour}"
        else:
            reasons = []
            if not cx.is_valid_divergence:
                reasons.append(f"div only {cx.divergence:.1f}")
            if not cx.is_valid_timing:
                reasons.append("not near hour")
            status = "CROSS — INVALID"
            detail = f"Cross detected but: {', '.join(reasons)}"
    elif is_diverged and abs(spread) < 3.0:
        status = "READY"
        detail = f"Divergence {max_div:.1f} pts. EMAs converging — cross imminent"
    elif is_diverged:
        status = "WATCHING"
        detail = f"Divergence {max_div:.1f} pts sufficient. Waiting for convergence"
    else:
        status = "WATCHING"
        detail = f"8 EMA {'above' if spread > 0 else 'below'} 50 by {abs(spread):.1f} pts. Max div: {max_div:.1f}"

    return CrossMonitorState(
        current_spread=spread,
        current_ema_8=ema8,
        current_ema_50=ema50,
        current_price=price,
        max_divergence=max_div,
        is_diverged_enough=is_diverged,
        status=status,
        status_detail=detail,
        last_cross=crosses[-1] if crosses else None,
        recent_crosses=crosses[-5:] if crosses else []
    )


def check_line_proximity(price: float, channel_values: dict, threshold: float = 3.0) -> Optional[str]:
    """Check if price is near any projected channel line."""
    lines = {k: v for k, v in channel_values.items() if v is not None}
    if not lines:
        return None
    nearest = min(lines.keys(), key=lambda k: abs(price - lines[k]))
    if abs(price - lines[nearest]) <= threshold:
        return nearest
    return None
