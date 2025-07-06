import streamlit as st
from datetime import datetime, timedelta
import pandas as pd

# --- SLOPES (in points per 30-minute block) ---
SLOPES = {
    "SPX": -0.048837,
    "TSLA": -0.1508,
    "NVDA": -0.0485,
    "AAPL": -0.1137,
    "MSFT": -0.1574,
    "AMZN": -0.0782,
    "GOOGL": -0.0485,
}

# --- FUNCTION TO COUNT VALID BLOCKS ---
def count_blocks(t1, t2):
    if t2 < t1:
        return 0
    blocks = 0
    current = t1
    while current < t2:
        # Exclude 4–5 PM daily pause
        if not (current.hour == 16):
            # Exclude weekend gap from Friday 4 PM to Sunday 5 PM
            if not (current.weekday() == 4 and current.hour >= 16) and not (current.weekday() == 5 or (current.weekday() == 6 and current.hour < 17)):
                blocks += 1
        current += timedelta(minutes=30)
    return blocks

# --- FUNCTION TO CALCULATE PROJECTED PRICE ---
def calculate_price(anchor_time, anchor_price, target_time, slope):
    blocks = count_blocks(anchor_time, target_time)
    return anchor_price + (slope * blocks), blocks

# --- UI LAYOUT ---
st.set_page_config(page_title="DrSPX Forecast App", layout="centered")
st.title("📈 DrSPX Forecast App")

selected_tab = st.sidebar.selectbox("Select Ticker", list(SLOPES.keys()))

with st.form(f"forecast_form_{selected_tab}"):
    st.subheader(f"🔹 Forecast for {selected_tab}")

    col1, col2 = st.columns(2)
    with col1:
        anchor_date = st.date_input("Anchor Date", value=datetime(2025, 6, 26).date(), key=f"anchor_date_{selected_tab}")
        anchor_hour = st.selectbox("Anchor Hour", list(range(0, 24)), index=15, key=f"anchor_hour_{selected_tab}")
        anchor_minute = st.selectbox("Anchor Minute", [0, 30], index=0, key=f"anchor_minute_{selected_tab}")
    with col2:
        anchor_price = st.number_input("Anchor Price", value=6000.0, step=0.1, key=f"anchor_price_{selected_tab}")

    col3, col4 = st.columns(2)
    with col3:
        target_date = st.date_input("Target Date", value=datetime(2025, 6, 27).date(), key=f"target_date_{selected_tab}")
        target_hour = st.selectbox("Target Hour", list(range(0, 24)), index=13, key=f"target_hour_{selected_tab}")
        target_minute = st.selectbox("Target Minute", [0, 30], index=0, key=f"target_minute_{selected_tab}")

    submitted = st.form_submit_button("📊 Forecast")

    if submitted:
        anchor_dt = datetime.combine(anchor_date, datetime.min.time()) + timedelta(hours=anchor_hour, minutes=anchor_minute)
        target_dt = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=target_hour, minutes=target_minute)
        slope = SLOPES[selected_tab]
        price, blocks = calculate_price(anchor_dt, anchor_price, target_dt, slope)

        st.success(f"📍 Projected price at {target_dt.strftime('%Y-%m-%d %H:%M')} is **{price:.2f}**")
        st.info(f"(Blocks counted: {blocks}, Slope used: {slope})")

    # Show full-day forecast table for SPX
    if selected_tab == "SPX":
        st.subheader("📆 Full-Day Forecast Table (RTH: 8:30 AM to 2:30 PM)")
        forecast_date = datetime.combine(target_date, datetime.min.time())
        times = [forecast_date + timedelta(hours=8, minutes=30) + timedelta(minutes=30*i) for i in range(13)]
        forecast_data = []
        for t in times:
            price, _ = calculate_price(anchor_dt, anchor_price, t, SLOPES["SPX"])
            forecast_data.append({"Time": t.strftime("%Y-%m-%d %H:%M"), "Projected Price": round(price, 2)})
        df_forecast = pd.DataFrame(forecast_data)
        st.dataframe(df_forecast, use_container_width=True)
