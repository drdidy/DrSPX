import streamlit as st
from datetime import datetime, time, timedelta

# --- SLOPE SETTINGS ---
SLOPES = {
    "SPX_HIGH": -0.2792,
    "SPX_CLOSE": -0.2792,
    "SPX_LOW": -0.2792,
    "TSLA": -0.1478,
    "NVDA": -0.0871,
    "AAPL": -0.1775,
    "AMZN": -0.1714,
    "GOOGL": -0.2091,
}

# --- Generate 30-min Slots 08:30–14:30 ---
def generate_time_blocks():
    base = datetime.strptime("08:30","%H:%M")
    return [(base+timedelta(minutes=30*i)).strftime("%H:%M") for i in range(13)]

# --- Block Counters ---
def calculate_spx_blocks(a,t):
    dt,blocks=a,0
    while dt<t:
        if dt.hour!=16: blocks+=1
        dt+=timedelta(minutes=30)
    return blocks

def calculate_stock_blocks(a,t):
    prev_close=a.replace(hour=15,minute=0)
    bp=max(0,int((prev_close-a).total_seconds()//1800))
    no=datetime.combine(t.date(),time(8,30))
    nc=datetime.combine(t.date(),time(15,0))
    if t<=no: bn=0
    else: bn=int((min(t,nc)-no).total_seconds()//1800)
    return bp+bn

# --- Forecast Generators ---
def generate_spx(price,slope,a,fd):
    rows=[]
    for slot in generate_time_blocks():
        h,m=map(int,slot.split(":"))
        tgt=datetime.combine(fd,time(h,m))
        b=calculate_spx_blocks(a,tgt)
        rows.append({"Time":slot,"Entry":round(price+slope*b,2),"Exit":round(price-slope*b,2)})
    return rows

def generate_stock(price,slope,a,fd,invert=False):
    rows=[]
    for slot in generate_time_blocks():
        h,m=map(int,slot.split(":"))
        tgt=datetime.combine(fd,time(h,m))
        b=calculate_stock_blocks(a,tgt)
        if invert:
            rows.append({"Time":slot,"Entry":round(price-slope*b,2),"Exit":round(price+slope*b,2)})
        else:
            rows.append({"Time":slot,"Entry":round(price+slope*b,2),"Exit":round(price-slope*b,2)})
    return rows

# --- Page & CSS ---
st.set_page_config("Dr Didy Forecast","📈","wide")
st.markdown("""
<style>
body {background: #f0f2f6;}
header {visibility:hidden;}
.sidebar .sidebar-content {
    background: #16213e; color: #fff; padding:1rem; border-radius:0 0.5rem 0.5rem 0;
}
.app-header {
    background: url('https://i.imgur.com/Z6XPDKk.jpg') no-repeat center; background-size:cover;
    padding:2rem; border-radius:0.5rem; text-align:center; color:#fff; margin-bottom:1rem;
    font-family: 'Segoe UI', sans-serif;
}
.tab-header {font-size:1.2rem; color:#0f3460; font-weight:600; margin-top:1rem;}
.card {background:#fff; border-radius:0.5rem; padding:1rem; box-shadow:0 4px 12px rgba(0,0,0,0.1); margin-bottom:1rem;}
.btn {background:#16213e; color:#fff;}
</style>
""",unsafe_allow_html=True)

st.markdown('<div class="app-header"><h1>📊 Dr Didy Forecast</h1><p>Your custom entry/exit tables</p></div>',unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    forecast_date=st.date_input("Forecast Date",datetime.now().date()+timedelta(days=1))
    st.divider()
    st.subheader("Slopes")
    for k in SLOPES:
        SLOPES[k]=st.slider(k.replace("_"," "),-1.0,1.0,SLOPES[k],step=0.0001)

# --- Tabs ---
tabs=st.tabs(["🧭 SPX","🚗 TSLA","🧠 NVDA","🍎 AAPL","📦 AMZN","🔍 GOOGL"])

# SPX Tab
with tabs[0]:
    st.markdown('<div class="tab-header">🧭 SPX Forecast (Prev-Day Anchors)</div>',unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    hp=c1.number_input("🔼 High Price",value=6185.8,format="%.2f")
    ht=c1.time_input("🕒 High Time",value=datetime(2025,1,1,11,30).time(),step=1800)
    cp=c2.number_input("⏹️ Close Price",value=6170.2,format="%.2f")
    ct=c2.time_input("🕒 Close Time",value=datetime(2025,1,1,15,0).time(),step=1800)
    lp=c3.number_input("🔽 Low Price",value=6130.4,format="%.2f")
    lt=c3.time_input("🕒 Low Time",value=datetime(2025,1,1,13,30).time(),step=1800)
    if st.button("🔮 Generate SPX",use_container_width=True):
        ah=datetime.combine(forecast_date-timedelta(days=1),ht)
        ac=datetime.combine(forecast_date-timedelta(days=1),ct)
        al=datetime.combine(forecast_date-timedelta(days=1),lt)
        for icon,title,price,slope,anchor in [
            ("🔼","High Anchor",hp,SLOPES["SPX_HIGH"],ah),
            ("⏹️","Close Anchor",cp,SLOPES["SPX_CLOSE"],ac),
            ("🔽","Low Anchor",lp,SLOPES["SPX_LOW"],al),
        ]:
            st.markdown(f"### {icon} {title}")
            st.markdown('<div class="card">',unsafe_allow_html=True)
            st.dataframe(generate_spx(price=price,slope=slope,a=anchor,fd=forecast_date),use_container_width=True)
            st.markdown('</div>',unsafe_allow_html=True)

# Stock Tabs
icons={"TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","AMZN":"📦","GOOGL":"🔍"}
for i,label in enumerate(["TSLA","NVDA","AAPL","AMZN","GOOGL"],start=1):
    with tabs[i]:
        st.markdown(f'<div class="tab-header">{icons[label]} {label} Forecast</div>',unsafe_allow_html=True)
        col=st.columns(2)[0]
        low_p=col.number_input("🔽 Prev-Day Low Price",value=0.0,format="%.2f",key=label+"_lp")
        low_t=col.time_input("🕒 Prev-Day Low Time",value=datetime(2025,1,1,8,30).time(),step=1800,key=label+"_lt")
        high_p=col.number_input("🔼 Prev-Day High Price",value=0.0,format="%.2f",key=label+"_hp")
        high_t=col.time_input("🕒 Prev-Day High Time",value=datetime(2025,1,1,8,30).time(),step=1800,key=label+"_ht")
        if st.button(f"🔮 Generate {label}",use_container_width=True):
            a_low=datetime.combine(forecast_date-timedelta(days=1),low_t)
            a_high=datetime.combine(forecast_date-timedelta(days=1),high_t)
            st.markdown("#### 🔻 Low-Anchor Table")
            st.markdown('<div class="card">',unsafe_allow_html=True)
            st.dataframe(generate_stock(price=low_p,slope=SLOPES[label],a=a_low,fd=forecast_date,invert=True),use_container_width=True)
            st.markdown('</div>',unsafe_allow_html=True)
            st.markdown("#### 🔺 High-Anchor Table")
            st.markdown('<div class="card">',unsafe_allow_html=True)
            st.dataframe(generate_stock(price=high_p,slope=SLOPES[label],a=a_high,fd=forecast_date,invert=False),use_container_width=True)
            st.markdown('</div>',unsafe_allow_html=True)
