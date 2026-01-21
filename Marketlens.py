import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from polygon import RESTClient
from datetime import date, timedelta

# --- Page Config ---
st.set_page_config(page_title="Polygon Options Analyzer", layout="wide")

st.title("📊 Options Open Interest & Max Pain Analyzer")
st.markdown("""
This tool fetches the **Option Chain Snapshot** from Polygon.io to analyze:
1. **Open Interest (OI) Walls:** High OI often acts as support/resistance.
2. **Max Pain:** The strike price where option buyers lose the most money (often a magnet for expiration).
""")

# --- Sidebar ---
st.sidebar.header("Configuration")

# 1. API Key Handling
api_key = st.secrets.get("POLYGON_API_KEY")
if not api_key:
    api_key = st.sidebar.text_input("Enter Polygon API Key", type="password")

# 2. User Inputs
ticker = st.sidebar.text_input("Ticker Symbol", value="SPY").upper()
# Default to next Friday for expiration example
default_date = date.today() + timedelta((4 - date.today().weekday()) % 7)
expiry = st.sidebar.date_input("Expiration Date", value=default_date)

# --- Helper Functions ---

@st.cache_data(ttl=600) # Cache data for 10 mins to save API credits
def fetch_option_chain(_client, ticker, expiration_date):
    """Fetches the snapshot for all options expiring on a specific date."""
    try:
        # Convert date to string YYYY-MM-DD
        expiry_str = expiration_date.strftime("%Y-%m-%d")
        
        # Polygon API call: Snapshot of the options chain
        chain_data = []
        # Note: We iterate because list_snapshot_options_chain yields results
        for contract in _client.list_snapshot_options_chain(
            ticker, 
            params={
                "expiration_date": expiry_str,
            }
        ):
            chain_data.append({
                "strike": contract.details.strike_price,
                "type": contract.details.contract_type, # 'call' or 'put'
                "open_interest": contract.open_interest or 0,
                "volume": contract.day.volume or 0,
                "implied_volatility": contract.greeks.implied_volatility if contract.greeks else 0,
                "last_price": contract.day.close or 0
            })
            
        return pd.DataFrame(chain_data)
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

def calculate_max_pain(df):
    """
    Calculates Max Pain: The strike price with the lowest cumulative loss for option holders.
    """
    if df.empty:
        return None, None

    strikes = sorted(df['strike'].unique())
    cash_values = []

    for price_point in strikes:
        # Calculate Call Loss (Intrinsic Value if stock expires at price_point)
        # Call Value = max(0, price_point - Strike) * OI
        call_loss = df[df['type'] == 'call'].apply(
            lambda x: max(0, price_point - x['strike']) * x['open_interest'], axis=1
        ).sum()

        # Calculate Put Loss
        # Put Value = max(0, Strike - price_point) * OI
        put_loss = df[df['type'] == 'put'].apply(
            lambda x: max(0, x['strike'] - price_point) * x['open_interest'], axis=1
        ).sum()

        total_loss = call_loss + put_loss
        cash_values.append({"strike": price_point, "total_loss": total_loss})

    pain_df = pd.DataFrame(cash_values)
    # The "Max Pain" is the strike with the MINIMUM total loss for the market
    max_pain_strike = pain_df.loc[pain_df['total_loss'].idxmin()]['strike']
    
    return max_pain_strike, pain_df

# --- Main Logic ---

if st.sidebar.button("Analyze Options"):
    if not api_key:
        st.warning("Please provide a Polygon API Key.")
        st.stop()

    client = RESTClient(api_key)
    
    with st.spinner(f"Fetching Option Chain for {ticker} expiring {expiry}..."):
        df = fetch_option_chain(client, ticker, expiry)

    if not df.empty:
        # Separate Calls and Puts
        calls = df[df['type'] == 'call']
        puts = df[df['type'] == 'put']

        # 1. Metrics
        total_call_oi = calls['open_interest'].sum()
        total_put_oi = puts['open_interest'].sum()
        pcr_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 0
        max_pain, pain_df = calculate_max_pain(df)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Call OI", f"{int(total_call_oi):,}")
        col2.metric("Total Put OI", f"{int(total_put_oi):,}")
        col3.metric("Put/Call Ratio (OI)", f"{pcr_ratio:.2f}")
        col4.metric("Max Pain Price", f"${max_pain}")

        # 2. Open Interest Bar Chart
        st.subheader(f"Open Interest by Strike ({expiry})")
        
        # Filter out deep OTM strikes to make chart readable (optional)
        # We'll take the middle 80% range of strikes or simple min/max based on volume
        active_strikes = df[df['open_interest'] > 0]
        if not active_strikes.empty:
             min_strike = active_strikes['strike'].min()
             max_strike = active_strikes['strike'].max()
             # Create a grouped bar chart
             fig_oi = px.bar(
                 df, 
                 x='strike', 
                 y='open_interest', 
                 color='type',
                 title=f"Open Interest Distribution for {ticker}",
                 color_discrete_map={'call': '#00CC96', 'put': '#EF553B'},
                 labels={"open_interest": "Open Interest", "strike": "Strike Price"}
             )
             fig_oi.update_layout(barmode='group', xaxis_range=[min_strike, max_strike])
             st.plotly_chart(fig_oi, use_container_width=True)

        # 3. Max Pain Chart
        if pain_df is not None:
            st.subheader("Max Pain Curve")
            st.markdown("The lowest point on this curve represents the price where option writers (market makers) pay out the least amount of money.")
            
            fig_pain = go.Figure()
            fig_pain.add_trace(go.Scatter(
                x=pain_df['strike'], 
                y=pain_df['total_loss'],
                mode='lines',
                name='Total Option Value'
            ))
            # Add vertical line for Max Pain
            fig_pain.add_vline(x=max_pain, line_dash="dash", line_color="red", annotation_text=f"Max Pain: {max_pain}")
            
            fig_pain.update_layout(
                title="Total Value of Options at Expiration (The 'Pain' Curve)",
                xaxis_title="Stock Price at Expiration",
                yaxis_title="Total Value ($)",
            )
            st.plotly_chart(fig_pain, use_container_width=True)

        # 4. Raw Data Explorer
        with st.expander("View Raw Data"):
            st.dataframe(df)

    else:
        st.error("No data found. Check the ticker, expiration date, or API key permissions.")
