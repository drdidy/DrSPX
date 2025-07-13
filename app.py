# Dr Didy SPX Forecast – v1.5.2
# -------------------------------------------------
# • META & NFLX coverage
# • Tuesday & Thursday now show anchor-trend tables first,
#   then their special contract-line tables
# • Contract-Low input exists only on Tuesday
# • Removed mobile-mode checkbox (auto-responsive)
# • 08:30-14:30 SPX trends; 07:30-14:30 others
# • 16:00-17:00 block skipped for SPX
# • Playbook page unchanged

import json, base64, streamlit as st
from datetime import datetime, date, time, timedelta
from copy import deepcopy
import pandas as pd

# ── CONSTANTS ────────────────────────────────────────────────────────────────
PAGE_TITLE, PAGE_ICON = "DRSPX Forecast", "📈"
VERSION  = "1.5.2"
FIXED_CL_SLOPE = -0.5250

BASE_SLOPES = {
    "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792,
    "TSLA": -0.1508, "NVDA": -0.0485, "AAPL": -0.0750,
    "MSFT": -0.17,   "AMZN": -0.03,   "GOOGL": -0.07,
    "META": -0.035,  "NFLX": -0.23,
}
ICONS = {
    "SPX":"🧭","TSLA":"🚗","NVDA":"🧠","AAPL":"🍎",
    "MSFT":"🪟","AMZN":"📦","GOOGL":"🔍",
    "META":"📘","NFLX":"📺"
}

# ── SESSION INIT ─────────────────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.update(theme="Light", slopes=deepcopy(BASE_SLOPES),
                            presets={})

if st.query_params.get("s"):
    try:
        st.session_state.slopes.update(
            json.loads(base64.b64decode(st.query_params["s"][0]).decode()))
    except Exception:
        pass

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(PAGE_TITLE, PAGE_ICON, "wide", initial_sidebar_state="expanded")

# ── CSS (cards + banner) ─────────────────────────────────────────────────────
st.markdown(
"""<style>
html,body{font-family:'Inter',sans-serif}
:root{--r:12px;--sh:0 6px 18px rgba(0,0,0,.08)}
body.light{--card:#f5f5f5}body.dark{--card:#1e293b;background:#0f172a;color:#e2e8f0}
.banner{background:linear-gradient(90deg,#0062e6 0%,#33aeff 100%);
        text-align:center;color:#fff;border-radius:var(--r);
        padding:.8rem;margin-bottom:1rem;box-shadow:var(--sh);
        animation:slide .6s ease-out}@keyframes slide{from{opacity:0;transform:translateY(-25px)}to{opacity:1}}
.cards{display:flex;gap:1rem;overflow-x:auto;margin-bottom:1rem}
.card{flex:1;min-width:220px;padding:1.4rem;border-radius:var(--r);
      display:flex;align-items:center;box-shadow:var(--sh);background:var(--card);transition:.25s}
.card:hover{transform:translateY(-4px);box-shadow:0 10px 24px rgba(0,0,0,.15)}
.ic{width:3rem;height:3rem;border-radius:var(--r);display:flex;align-items:center;
    justify-content:center;font-size:2rem;color:#fff;margin-right:.9rem}
.val{font-size:2rem;font-weight:800;letter-spacing:-.5px}.ttl{font-size:.95rem;opacity:.75}
.high {background:radial-gradient(circle at 30% 30%,rgba(16,185,129,.25),transparent 70%),rgba(16,185,129,.12)}
.close{background:radial-gradient(circle at 30% 30%,rgba(59,130,246,.25),transparent 70%),rgba(59,130,246,.12)}
.low  {background:radial-gradient(circle at 30% 30%,rgba(239,68,68,.25),transparent 70%),rgba(239,68,68,.12)}
.high .ic{background:#10b981}.close .ic{background:#3b82f6}.low .ic{background:#ef4444}
body.dark .high{background:rgba(16,185,129,.25)}body.dark .close{background:rgba(59,130,246,.25)}
body.dark .low{background:rgba(239,68,68,.25)}
@media(max-width:480px){.banner{padding:.6rem;font-size:1.1rem}
.card{min-width:170px;padding:1.1rem}.ic{width:2.4rem;height:2.4rem;font-size:1.6rem}
.val{font-size:1.55rem}body{padding-bottom:80px}}</style>""",
unsafe_allow_html=True)

def card(kind,sym,title,val):
    st.markdown(f"""<div class="card {kind}"><div class="ic">{sym}</div>
    <div><div class="ttl">{title}</div><div class="val">{val:.2f}</div></div></div>""",
    unsafe_allow_html=True)

cols = st.columns  # always responsive; Streamlit stacks on phones

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
st.session_state.theme = st.sidebar.radio("🎨 Theme",["Light","Dark"],
    index=0 if st.session_state.theme=="Light" else 1)

fcast_date = st.sidebar.date_input("Forecast Date", date.today()+timedelta(days=1))
wd = fcast_date.weekday()
day_grp = "Tuesday" if wd==1 else "Thursday" if wd==3 else "Mon/Wed/Fri"

with st.sidebar.expander("📉 Slopes"):
    for k in st.session_state.slopes:
        st.session_state.slopes[k]=st.slider(k,-1.0,1.0,st.session_state.slopes[k],0.0001)

with st.sidebar.expander("💾 Presets"):
    pn = st.text_input("Preset name")
    if st.button("Save current"):
        st.session_state.presets[pn]=deepcopy(st.session_state.slopes)
    if st.session_state.presets:
        sel=st.selectbox("Load preset", list(st.session_state.presets))
        if st.button("Load"): st.session_state.slopes.update(st.session_state.presets[sel])

st.sidebar.text_input("🔗 Share-suffix",
    f"?s={base64.b64encode(json.dumps(st.session_state.slopes).encode()).decode()}",
    disabled=True)

# ── TIME / TABLE HELPERS ─────────────────────────────────────────────────────
def make_slots(start=time(7,30)):
    base=datetime(2025,1,1,start.hour,start.minute)
    return [(base+timedelta(minutes=30*i)).strftime("%H:%M")
            for i in range(15-(start.hour==8 and start.minute==30)*2)]
SPX_SLOTS=make_slots(time(8,30)); GEN_SLOTS=make_slots()

def blk_spx(a,t):
    b=0
    while a<t:
        if a.hour!=16:b+=1
        a+=timedelta(minutes=30)
    return b
blk_stock=lambda a,t:max(0,int((t-a).total_seconds()//1800))

def tbl(price,slope,anchor,fd,slots,spx=True,fan=False):
    rows=[]
    for s in slots:
        h,m=map(int,s.split(":"))
        tgt=datetime.combine(fd,time(h,m))
        b=blk_spx(anchor,tgt) if spx else blk_stock(anchor,tgt)
        rows.append({"Time":s,"Projected":round(price+slope*b,2)} if not fan else
                    {"Time":s,"Entry":round(price+slope*b,2),"Exit":round(price-slope*b,2)})
    return pd.DataFrame(rows)

# ── HEADER & TABS ────────────────────────────────────────────────────────────
st.markdown(f"<div class='banner'><h3>{PAGE_ICON} {PAGE_TITLE}</h3></div>", unsafe_allow_html=True)
tabs=st.tabs([f"{ICONS[t]} {t}" for t in ICONS])

# ── SPX TAB ───────────────────────────────────────────────────────────────────
with tabs[0]:
    st.write(f"### {ICONS['SPX']} SPX Forecast ({day_grp})")
    c1,c2,c3=cols(3)
    hp,ht=c1.number_input("High Price",6185.8), c1.time_input("High Time",time(11,30))
    cp,ct=c2.number_input("Close Price",6170.2), c2.time_input("Close Time",time(15))
    lp,lt=c3.number_input("Low Price",6130.4),  c3.time_input("Low Time", time(13,30))

    if day_grp=="Tuesday":
        st.subheader("Overnight Contract Line (Low-1 & Low-2)")
        o1,o2=cols(2)
        cl1_t,cl1_p=o1.time_input("Low-1 Time",time(2)),  o1.number_input("Low-1 Price",6100.0)
        cl2_t,cl2_p=o2.time_input("Low-2 Time",time(3,30)),o2.number_input("Low-2 Price",6120.0)
        cl_t, cl_p = st.time_input("Contract Low Time",time(7,30)), st.number_input("Contract Low Price",5.0)

    if day_grp=="Thursday":
        st.subheader("Overnight Contract Line (Low-1 & Low-2)")
        p1,p2=cols(2)
        ol1_t,ol1_p=p1.time_input("Low-1 Time",time(2)),  p1.number_input("Low-1 Price",6100.0)
        ol2_t,ol2_p=p2.time_input("Low-2 Time",time(3,30)),p2.number_input("Low-2 Price",6120.0)
        b_t,b_p=st.time_input("Bounce Low Time",time(7,30)), st.number_input("Bounce Low Price",6100.0)

    if st.button("Run Forecast"):
        ah,ac,al=[datetime.combine(fcast_date-timedelta(days=1),t) for t in (ht,ct,lt)]

        # ── ① Cards + anchor-trend tables (shown every day) ───────────────────
        st.markdown('<div class="cards">',unsafe_allow_html=True)
        card("high","▲","High Anchor",hp)
        card("close","■","Close Anchor",cp)
        card("low","▼","Low Anchor",lp)
        st.markdown('</div>',unsafe_allow_html=True)

        for lbl,price,key,anc in [("High",hp,"SPX_HIGH",ah),
                                  ("Close",cp,"SPX_CLOSE",ac),
                                  ("Low",lp,"SPX_LOW",al)]:
            st.subheader(f"{lbl} Anchor Trend")
            st.dataframe(tbl(price,st.session_state.slopes[key],anc,
                             fcast_date,SPX_SLOTS,fan=True),use_container_width=True)

        # ── ② Tuesday extras ─────────────────────────────────────────────────
        if day_grp=="Tuesday":
            dt1,dt2=[datetime.combine(fcast_date-timedelta(days=1),t) for t in (cl1_t,cl2_t)]
            alt_slope=(cl2_p-cl1_p)/(blk_spx(dt1,dt2) or 1)
            st.subheader("Contract Line (2-pt)"); st.dataframe(tbl(cl1_p,alt_slope,dt1,fcast_date,GEN_SLOTS))
            st.subheader("Fixed SPX Contract Line"); st.dataframe(tbl(cl_p,FIXED_CL_SLOPE,
                datetime.combine(fcast_date,cl_t),fcast_date,GEN_SLOTS))

        # ── ③ Thursday extras ────────────────────────────────────────────────
        if day_grp=="Thursday":
            dt1,dt2=[datetime.combine(fcast_date-timedelta(days=1),t) for t in (ol1_t,ol2_t)]
            alt_slope=(ol2_p-ol1_p)/(blk_spx(dt1,dt2) or 1)
            st.subheader("Contract Line (2-pt)"); st.dataframe(tbl(ol1_p,alt_slope,dt1,fcast_date,GEN_SLOTS))
            st.subheader("Bounce-Low Line"); st.dataframe(tbl(b_p,st.session_state.slopes["SPX_LOW"],
                datetime.combine(fcast_date-timedelta(days=1),b_t),fcast_date,GEN_SLOTS))

# ── STOCK TABS ────────────────────────────────────────────────────────────────
def stock_tab(idx,tic):
    with tabs[idx]:
        st.write(f"### {ICONS[tic]} {tic}")
        a,b=cols(2)
        lp,lt=a.number_input("Prev-day Low",key=f"{tic}lp"), a.time_input("Low Time",time(7,30),key=f"{tic}lt")
        hp,ht=b.number_input("Prev-day High",key=f"{tic}hp"), b.time_input("High Time",time(7,30),key=f"{tic}ht")
        if st.button("Generate",key=f"go_{tic}"):
            low  = tbl(lp,st.session_state.slopes[tic],datetime.combine(fcast_date,lt),fcast_date,GEN_SLOTS,False,True)
            high = tbl(hp,st.session_state.slopes[tic],datetime.combine(fcast_date,ht),fcast_date,GEN_SLOTS,False,True)
            st.subheader("Low Anchor Trend");  st.dataframe(low ,use_container_width=True)
            st.subheader("High Anchor Trend"); st.dataframe(high,use_container_width=True)

for i,tic in enumerate(list(ICONS)[1:],1): stock_tab(i,tic)

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown(f"<hr><center style='font-size:.8rem'>v{VERSION} • {datetime.now():%Y-%m-%d %H:%M:%S}</center>",
            unsafe_allow_html=True)