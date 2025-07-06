import pandas as pd
from datetime import datetime, timedelta

# --- Default Slopes ---
SLOPES = {
    "SPX_HIGH": -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW": -0.2792,
    "TSLA": -0.1508,
    "NVDA": -0.0504,
    "AAPL": -0.1156,
    "AMZN": -0.0782,
    "GOOGL": -0.0485,
}

# --- Generate 30-min Forecast Slots (8:30 AM – 2:30 PM) ---
def generate_time_blocks():
    base = datetime.strptime("08:30", "%H:%M")
    return [(base + timedelta(minutes=30 * i)).strftime("%H:%M") for i in range(13)]

# --- Block Difference Calculator (excluding 4–5PM pause and weekend gap) ---
def calculate_blocks(anchor_time, target_time):
    total_blocks = 0
    while anchor_time < target_time:
        if anchor_time.weekday() >= 5:  # Skip weekends
            anchor_time += timedelta(days=1)
            anchor_time = anchor_time.replace(hour=5, minute=0)
            continue
        if anchor_time.hour == 16:  # Skip 4–5PM break
            anchor_time += timedelta(hours=1)
            continue
        anchor_time += timedelta(minutes=30)
        total_blocks += 1
    return total_blocks

# --- Forecast Table Generator with Entry and Exit ---
def generate_forecast(anchor_price, slope, anchor_dt):
    time_blocks = generate_time_blocks()
    forecast = []
    for t in time_blocks:
        hour, minute = map(int, t.split(":"))
        today_forecast_time = anchor_dt.replace(hour=hour, minute=minute) + timedelta(days=1)
        block_diff = calculate_blocks(anchor_dt, today_forecast_time)
        entry_price = anchor_price + (slope * block_diff)
        exit_price = anchor_price + (abs(slope) * block_diff)
        forecast.append({
            "Time": t,
            "Entry Price": round(entry_price, 2),
            "Exit Price": round(exit_price, 2)
        })
    return pd.DataFrame(forecast)
