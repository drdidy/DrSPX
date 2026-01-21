import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import pytz

# -----------------------------------------------------------------------------
# 1. CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SPXW SKEW | 0DTE",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    /* TERMINAL AESTHETIC */
    .stApp {
        background-color: #0a0a0a;
        color: #e0e0e0;
        font-family: 'Consolas', 'Courier New', monospace;
    }
    
    /* METRIC CARDS */
    .skew-card {
        background: #111;
        border: 1px solid #333;
        padding: 20px;
        border-radius: 4px;
        text-align: center;
        margin-bottom: 20px;
    }
    .skew-card h3 { margin: 0; font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 2px; }
    .skew-card .value { font-size: 2.2rem; font-weight: bold; margin: 10px 0; }
    
    /* SENTIMENT COLORS */
    .bullish { color: #00ffcc; text-shadow: 0 0 10px rgba(0, 255, 204, 0.2); }
    .bearish { color: #ff0066; text-shadow: 0 0 10px rgba(255, 0, 102, 0.2); }
    .neutral { color: #ffcc00; }
    
    /* HIDE JUNK */
    header, footer, #MainMenu {visibility: hidden;}
    
    /* DATE PICKER FIX */
    input[type="date"] {
        color: #fff !important; 
        background: #333 !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. DATA ENGINE
# -----------------------------------------------------------------------------
TZ_CT = pytz.timezone('US/Central')
API_KEY = "6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ"

def get_current_date():
    return datetime.now(TZ_CT).date()

def get_smart_default_date():
    """Defaults to TOMORROW if market is closed (After 4PM CT)."""
    now = datetime.now(TZ_CT)
    if now.hour >= 16: 
        d = now.date() + timedelta(days=1)
        while d.weekday() > 4: d += timedelta(days=1) # Skip weekends
        return d
    return now.date()

@st.cache_data(ttl=60)
def fetch_option_data(date_str):
    """
    Fetches the SPXW (Weekly/Daily) Option Chain.
    """
    # 1. Get Spot Price (Uses I:SPX Index)
    try:
        r_spot = requests.get(f"https://api.polygon.io/v3/snapshot?ticker.any_of=I:SPX&apiKey={API_KEY}", timeout=3)
        spot_data = r_spot.json()
        spx_price = spot_data['results'][0]['value'] if 'results' in spot_data else 0
    except:
        spx_price = 0

    # 2. Get Option Chain (Uses SPXW for PM-Settled 0DTEs)
    # Note: We query underlying_asset=SPXW to get the PM settled chains
    url = f"https://api.polygon.io/v3/snapshot/options/SPXW?expiration_date={date_str}&limit=1000&apiKey={API_KEY}"
    
    results = []
    try:
        while url:
            r = requests.get(url, timeout=5)
            data = r.json()
            if 'results' in data:
                results.extend(data['results'])
            
            url = data.get('next_url')
            if url: url += f"&apiKey={API_KEY}"
            
    except Exception as e:
        return None

    if not results:
        return None

    # 3. Process & Calculate
    calls_vol, puts_vol = 0, 0
    calls_oi, puts_oi = 0, 0
    
    df_data = []
    
    for c in results:
        details = c.get('details', {})
        stats = c.get('day', {})
        
        strike = details.get('strike_price')
        c_type = details.get('contract_type')
        
        vol = stats.get('volume', 0)
        oi = c.get('open_interest', 0)
        
        if c_type == 'call':
            calls_vol += vol
            calls_oi += oi
        elif c_type == 'put':
            puts_vol += vol
            puts_oi += oi
            
        if vol > 0 or oi > 0:
            df_data.append({
                'strike': strike,
                'type': c_type,
                'volume': vol,
                'oi': oi
            })

    # 4. Return Structured Data
    return {
        "spx_price": spx_price,
        "total_calls_vol": calls_vol,
        "total_puts_vol": puts_vol,
        "total_calls_oi": calls_oi,
        "total_puts_oi": puts_oi,
        "pcr_vol": puts_vol / calls_vol if calls_vol else 0,
        "pcr_oi": puts_oi / calls_oi if calls_oi else 0,
        "df": pd.DataFrame(df_data)
    }

# -----------------------------------------------------------------------------
# 3. UI LOGIC
# -----------------------------------------------------------------------------
def main():
    # --- CONTROLS ---
    c_head, c_inputs = st.columns([2, 1])
    
    with c_head:
        st.markdown("## 🦅 SPXW SKEW<br><span style='font-size:0.8rem; color:#888'>PM-SETTLED 0DTE ANALYZER</span>", unsafe_allow_html=True)
        
    with c_inputs:
        default_date = get_smart_default_date()
        target_date = st.date_input("Select Expiry", default_date)

    st.markdown("---")

    # --- DATA FETCH ---
    date_str = target_date.strftime('%Y-%m-%d')
    
    with st.spinner(f"Pulling SPXW Chain for {date_str}..."):
        data = fetch_option_data(date_str)

    if not data:
        st.error(f"❌ No SPXW Data Found for {date_str}.")
        st.info("💡 Ensure you are selecting a valid trading day. If looking for 0DTE planning after hours, select **Tomorrow**.")
        return

    # --- DASHBOARD ---
    is_future = target_date > get_current_date()
    focus_metric = "OI" if is_future else "VOL"
    
    # Sentiment Calculation
    pcr_val = data['pcr_oi'] if is_future else data['pcr_vol']
    
    bias_text = "NEUTRAL"
    bias_color = "neutral"
    if pcr_val > 1.3:
        bias_text = "BEARISH HEDGING"
        bias_color = "bearish"
        bias_desc = "Significant PUT skew detected. Market is paying up for downside protection."
    elif pcr_val < 0.7:
        bias_text = "BULLISH POSITIONING"
        bias_color = "bullish"
        bias_desc = "Significant CALL skew detected. Market is chasing upside exposure."
    else:
        bias_desc = "Balanced Put/Call structure. No directional edge from skew alone."

    # METRICS
    st.markdown(f"### 📊 SPXW (PM) REPORT: <span style='color:#fff'>{date_str}</span>", unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div class="skew-card">
            <h3>Put/Call Ratio ({focus_metric})</h3>
            <div class="value {bias_color}">{pcr_val:.2f}</div>
            <div style="font-size:0.7rem; color:#888;">{bias_text}</div>
        </div>""", unsafe_allow_html=True)
    with m2:
        val = data['total_puts_oi'] if is_future else data['total_puts_vol']
        st.markdown(f"""
        <div class="skew-card">
            <h3>Total Puts ({focus_metric})</h3>
            <div class="value bearish">{val:,}</div>
        </div>""", unsafe_allow_html=True)
    with m3:
        val = data['total_calls_oi'] if is_future else data['total_calls_vol']
        st.markdown(f"""
        <div class="skew-card">
            <h3>Total Calls ({focus_metric})</h3>
            <div class="value bullish">{val:,}</div>
        </div>""", unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="skew-card">
            <h3>SPX Index</h3>
            <div class="value" style="color:#fff;">{data['spx_price']:,.0f}</div>
        </div>""", unsafe_allow_html=True)
        
    st.markdown(f"<div style='text-align:center; color:#666; font-size:0.8rem; margin-bottom:20px;'>ℹ️ {bias_desc}</div>", unsafe_allow_html=True)

    # VISUALIZATION
    df = data['df']
    if not df.empty:
        center = data['spx_price'] if data['spx_price'] > 0 else 4000
        if center == 0: center = df['strike'].median()
            
        range_pts = 75 # Zoom tighter for 0DTE precision
        mask = (df['strike'] >= center - range_pts) & (df['strike'] <= center + range_pts)
        chart_df = df[mask]
        
        plot_col = 'oi' if is_future else 'volume'
        plot_title = "OPEN INTEREST (Net Positioning)" if is_future else "VOLUME (Intraday Flow)"
        
        pivot = chart_df.pivot_table(index='strike', columns='type', values=plot_col, aggfunc='sum').fillna(0)
        
        fig = go.Figure()
        if 'call' in pivot.columns:
            fig.add_trace(go.Bar(x=pivot.index, y=pivot['call'], name='CALLS', marker_color='#00ffcc', opacity=0.7))
        if 'put' in pivot.columns:
            fig.add_trace(go.Bar(x=pivot.index, y=pivot['put'], name='PUTS', marker_color='#ff0066', opacity=0.7))

        fig.update_layout(
            title=f"SPXW {plot_title} SKEW",
            title_font_color="#fff",
            xaxis_title="Strike Price",
            yaxis_title=plot_title,
            barmode='overlay',
            plot_bgcolor='#0a0a0a',
            paper_bgcolor='#0a0a0a',
            font=dict(color="#ccc", family="Consolas"),
            xaxis=dict(gridcolor='#222'),
            yaxis=dict(gridcolor='#222'),
            height=500,
            bargap=0.0
        )
        
        if data['spx_price'] > 0:
            fig.add_vline(x=data['spx_price'], line_width=1, line_dash="dash", line_color="white")
            fig.add_annotation(x=data['spx_price'], y=0, text="SPOT", showarrow=True, arrowhead=1, ax=0, ay=-30)

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No strike data available to chart.")

if __name__ == "__main__":
    main()
