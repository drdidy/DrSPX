# Dr Didy Forecast  – v1.4.1
# fixes: share-link & Altair rendering

import json, base64, altair as alt
from io import BytesIO
from copy import deepcopy
from datetime import datetime, date, time, timedelta

import pandas as pd
import streamlit as st

# ───────────────────────── CONSTANTS ──────────────────────────────────────────
PAGE_TITLE, PAGE_ICON, LAYOUT, SIDEBAR = "Dr Didy Forecast", "📈", "wide", "expanded"
VERSION  = "1.4.1"
FIXED_CL_SLOPE = -0.5250

BASE_SLOPES = {
    "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792,
    "TSLA": -0.1508, "NVDA": -0.0485, "AAPL": -0.075, "MSFT": -0.1964,
    "AMZN": -0.0782, "GOOGL": -0.0485,
}
STRAT = {k: deepcopy(BASE_SLOPES) for k in ["Mon/Wed/Fri", "Tuesday", "Thursday"]}

ICONS = {"SPX":"🧭","TSLA":"🚗","NVDA":"🧠","AAPL":"🍎",
         "MSFT":"🪟","AMZN":"📦","GOOGL":"🔍"}
CB_COLORS = ["#4e79a7","#f28e2b","#e15759","#76b7b2",
             "#59a14f","#edc948","#af7aa1"]

# ────────────────────── SESSION STATE INIT ────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.update(theme="Light", slopes=deepcopy(BASE_SLOPES),
                            presets={}, mobile=False)

# restore settings from URL suffix
q = st.experimental_get_query_params()
if q.get("s"):
    try:
        st.session_state.slopes.update(
            json.loads(base64.b64decode(q["s"][0]).decode())
        )
    except Exception:
        pass

# ──────────────────────── BASIC CSS / THEME ───────────────────────────────────
GRADIENT = "linear-gradient(90deg,#0062E6 0%,#33AEFF 100%)"
CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
  :root{{--radius:8px;--shadow:0 4px 12px rgba(0,0,0,.06)}}
  body,html{{font-family:'Inter',sans-serif}}
  .hdr{{background:{GRADIENT};color:#fff;padding:1rem;border-radius:var(--radius);
        box-shadow:var(--shadow);margin-bottom:1rem}}
  .cards{{display:flex;gap:1rem;overflow-x:auto;margin-bottom:1rem}}
  .card{{flex:1;min-width:160px;background:#f5f5f5;border-radius:var(--radius);
         padding:1rem;display:flex;align-items:center;transition:.2s;
         box-shadow:var(--shadow)}}
  .card:hover{{transform:translateY(-2px);box-shadow:0 8px 18px rgba(0,0,0,.12)}}
  .ic{{font-size:1.8rem;margin-right:.5rem}}
  .ttl{{font-size:.85rem;opacity:.7}}
  .val{{font-size:1.25rem;font-weight:700}}
  .dark body{{background:#0f172a;color:#e2e8f0}}
  .dark .card{{background:#1e293b}}
  .dark .hdr{{background:linear-gradient(90deg,#3677FF 0%,#7695FF 100%)}}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)

# ───────────────────────── CONFIG & SIDEBAR ───────────────────────────────────
st.set_page_config(PAGE_TITLE, PAGE_ICON, LAYOUT, initial_sidebar_state=SIDEBAR)

st.session_state.theme = st.sidebar.radio(
    "🎨 Theme", ["Light", "Dark"],
    index=0 if st.session_state.theme == "Light" else 1
)
if st.session_state.theme == "Dark":
    st.markdown("<body class='dark'>", unsafe_allow_html=True)

fcast_date = st.sidebar.date_input("Forecast Date", date.today() + timedelta(days=1))
wd = fcast_date.weekday()
day_group = "Tuesday" if wd == 1 else "Thursday" if wd == 3 else "Mon/Wed/Fri"

st.session_state.mobile = st.sidebar.checkbox("📱 Mobile mode", value=st.session_state.mobile)

with st.sidebar.expander("📉 Slopes"):
    for k, v in st.session_state.slopes.items():
        st.session_state.slopes[k] = st.slider(k, -1.0, 1.0, v, 0.0001)

with st.sidebar.expander("💾 Presets"):
    name = st.text_input("Preset name")
    if st.button("Save current"):
        st.session_state.presets[name] = deepcopy(st.session_state.slopes)
    if st.session_state.presets:
        sel = st.selectbox("Load preset", list(st.session_state.presets))
        if st.button("Load"):
            st.session_state.slopes.update(st.session_state.presets[sel])

# share link (relative suffix—just append to the current URL)
enc = base64.b64encode(json.dumps(st.session_state.slopes).encode()).decode()
share_suffix = f"?s={enc}"
st.sidebar.text_input("🔗 Share-link suffix", value=share_suffix, disabled=True)

# ───────────────────────── TIME HELPERS ───────────────────────────────────────
def slots(): return [(datetime(2025,1,1,7,30)+timedelta(minutes=30*i)).strftime("%H:%M") for i in range(15)]
def blk_spx(a,t):
    b=0
    while a<t:
        if a.hour!=16: b+=1
        a+=timedelta(minutes=30)
    return b
blk_stock = lambda a,t:max(0,int((t-a).total_seconds()//1800))

def line(p,s,anchor,fd,spx=True):
    rows=[]
    for sstr in slots():
        h,m=map(int,sstr.split(":"))
        tgt=datetime.combine(fd,time(h,m))
        b = blk_spx(anchor,tgt) if spx else blk_stock(anchor,tgt)
        rows.append({"Time":sstr,"Projected":round(p+s*b,2)})
    return pd.DataFrame(rows)

def fan(p,s,anchor,fd,spx=True):
    rows=[]
    for sstr in slots():
        h,m=map(int,sstr.split(":"))
        tgt=datetime.combine(fd,time(h,m))
        b = blk_spx(anchor,tgt) if spx else blk_stock(anchor,tgt)
        rows.append({"Time":sstr,"Entry":round(p+s*b,2),"Exit":round(p-s*b,2)})
    return pd.DataFrame(rows)

# ───────────────────────── LAYOUT HELPERS ─────────────────────────────────────
def cols(n): return (st,) if st.session_state.mobile else st.columns(n)

# ───────────────────────── HEADER & TABS ──────────────────────────────────────
st.markdown(f'<div class="hdr"><h2>{PAGE_ICON} {PAGE_TITLE}</h2></div>', unsafe_allow_html=True)
tabs = st.tabs([f"{ICONS[k]} {k}" for k in ICONS])

# ─────────────────────────── SPX TAB ──────────────────────────────────────────
with tabs[0]:
    st.write(f"### {ICONS['SPX']} SPX Forecast ({day_group})")
    c1,c2,c3 = cols(3)
    hp, ht = c1.number_input("High Price",6185.8), c1.time_input("High Time",time(11,30))
    cp, ct = c2.number_input("Close Price",6170.2), c2.time_input("Close Time",time(15,0))
    lp, lt = c3.number_input("Low Price",6130.4),  c3.time_input("Low Time", time(13,30))

    if day_group == "Tuesday":
        st.subheader("Overnight Contract Line")
        o1,o2 = cols(2)
        cl1_t, cl1_p = o1.time_input("Low-1 Time",time(2,0)),  o1.number_input("Low-1 Price",6100.0)
        cl2_t, cl2_p = o2.time_input("Low-2 Time",time(3,30)), o2.number_input("Low-2 Price",6120.0)
        cl_t,  cl_p  = st.time_input("Contract Low Time",time(7,30)), st.number_input("Contract Low Price",5.0)

    if day_group == "Thursday":
        st.subheader("Overnight Contract Line")
        t1,t2 = cols(2)
        ol1_t, ol1_p = t1.time_input("Low-1 Time",time(2,0)),  t1.number_input("Low-1 Price",6100.0)
        ol2_t, ol2_p = t2.time_input("Low-2 Time",time(3,30)), t2.number_input("Low-2 Price",6120.0)
        b_t, b_p = st.time_input("Bounce Low Time",time(7,30)), st.number_input("Bounce Low Price",6100.0)

    if st.button("Run Forecast"):
        prog = st.progress(0.0)
        ah,ac,al = [datetime.combine(fcast_date-timedelta(days=1),t) for t in (ht,ct,lt)]

        # Tuesday logic
        if day_group == "Tuesday":
            dt1,dt2 = datetime.combine(fcast_date-timedelta(days=1),cl1_t), datetime.combine(fcast_date-timedelta(days=1),cl2_t)
            alt_slope = (cl2_p-cl1_p)/(blk_spx(dt1,dt2) or 1)
            st.write("#### Contract Line (2-pt)")
            df = line(cl1_p,alt_slope,dt1,fcast_date); st.dataframe(df,use_container_width=True)
            st.altair_chart(
                alt.Chart(df).mark_line(color=CB_COLORS[0]).encode(x="Time",y="Projected"),
                use_container_width=True
            )
            prog.progress(0.4)

            st.write("#### Fixed SPX Line")
            df2 = line(cl_p,FIXED_CL_SLOPE,datetime.combine(fcast_date,cl_t),fcast_date)
            st.dataframe(df2,use_container_width=True)
            st.altair_chart(
                alt.Chart(df2).mark_line(strokeDash=[4,2],color=CB_COLORS[1]).encode(x="Time",y="Projected"),
                use_container_width=True
            )
            prog.progress(0.8)

        # Thursday logic
        elif day_group == "Thursday":
            dt1,dt2 = datetime.combine(fcast_date-timedelta(days=1),ol1_t), datetime.combine(fcast_date-timedelta(days=1),ol2_t)
            alt_slope = (ol2_p-ol1_p)/(blk_spx(dt1,dt2) or 1)
            st.write("#### Contract Line (2-pt)")
            df = line(ol1_p,alt_slope,dt1,fcast_date); st.dataframe(df,use_container_width=True)
            st.altair_chart(
                alt.Chart(df).mark_line(color=CB_COLORS[0]).encode(x="Time",y="Projected"),
                use_container_width=True
            )
            prog.progress(0.5)

            st.write("#### Bounce-Low Line")
            df2 = line(b_p,st.session_state.slopes["SPX_LOW"],datetime.combine(fcast_date-timedelta(days=1),b_t),fcast_date)
            st.dataframe(df2,use_container_width=True)
            st.altair_chart(
                alt.Chart(df2).mark_line(strokeDash=[4,2],color=CB_COLORS[1]).encode(x="Time",y="Projected"),
                use_container_width=True
            )
            prog.progress(0.8)

        # Mon/Wed/Fri logic
        else:
            st.markdown('<div class="cards">', unsafe_allow_html=True)
            for t,v,i,c in [("High",hp,"🔼",CB_COLORS[0]),("Close",cp,"⏹️",CB_COLORS[1]),("Low",lp,"🔽",CB_COLORS[2])]:
                st.markdown(f'<div class="card"><span class="ic">{i}</span>'
                            f'<div><div class="ttl">{t} Anchor</div><div class="val">{v:.2f}</div></div></div>',
                            unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            for t,v,s,anc,col in [("High",hp,"SPX_HIGH",ah,CB_COLORS[0]),
                                  ("Close",cp,"SPX_CLOSE",ac,CB_COLORS[1]),
                                  ("Low", lp,"SPX_LOW", al,CB_COLORS[2])]:
                st.write(f"#### {t} Anchor Fan")
                df = fan(v,st.session_state.slopes[s],anc,fcast_date)
                st.dataframe(df,use_container_width=True)
                chart = alt.Chart(df).transform_fold(["Entry","Exit"]).mark_line().encode(
                    x="Time",y="value:Q",color="key:N")
                st.altair_chart(chart,use_container_width=True)
            prog.progress(0.9)

        prog.empty()
        st.success("Done!")

# ───────────────────────── STOCK TABS ─────────────────────────────────────────
def stock(idx,tic,color):
    with tabs[idx]:
        st.write(f"### {ICONS[tic]} {tic}")
        a,b = cols(2)
        lp,lt = a.number_input("Prev-day Low",key=f"{tic}lp"), a.time_input("Low Time",time(7,30),key=f"{tic}lt")
        hp,ht = b.number_input("Prev-day High",key=f"{tic}hp"), b.time_input("High Time",time(7,30),key=f"{tic}ht")
        if st.button("Generate",key=f"go{tic}"):
            low_anchor  = datetime.combine(fcast_date,lt)
            high_anchor = datetime.combine(fcast_date,ht)
            df_low  = fan(lp, st.session_state.slopes[tic], low_anchor,  fcast_date, spx=False)
            df_high = fan(hp, st.session_state.slopes[tic], high_anchor, fcast_date, spx=False)
            st.dataframe(df_low,use_container_width=True)
            st.dataframe(df_high,use_container_width=True)
            layer = alt.layer(
                alt.Chart(df_low ).mark_line(strokeDash=[3,3],color=color).encode(x="Time",y="Entry"),
                alt.Chart(df_high).mark_line(color=color).encode(x="Time",y="Entry")
            )
            st.altair_chart(layer,use_container_width=True)

for i,(tic,col) in enumerate(zip(list(ICONS)[1:],CB_COLORS[1:]),1):
    stock(i,tic,col)

# ───────────────────────── FOOTER ─────────────────────────────────────────────
st.markdown(f"<hr><center style='font-size:.8rem'>v{VERSION} • "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</center>", unsafe_allow_html=True)