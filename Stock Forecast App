# Dr Didy SPX Forecast  – v1.4.4
# centred header, anchor-trend renaming, stable chart toggles, scroll-restore

import json, base64, altair as alt, streamlit as st
from datetime import datetime, date, time, timedelta
from copy import deepcopy
import pandas as pd

# ───────────────────────── CONSTANTS ──────────────────────────────────────────
PAGE_TITLE, PAGE_ICON = "DRSPX Forecast", "📈"
VERSION  = "1.4.4"
FIXED_CL_SLOPE = -0.5250          # Tuesday fixed SPX slope

BASE_SLOPES = {
    "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792,
    "TSLA": -0.1508, "NVDA": -0.0485, "AAPL": -0.0750, "MSFT": -0.1964,
    "AMZN": -0.0782, "GOOGL": -0.0485,
}
ICONS = {"SPX":"🧭","TSLA":"🚗","NVDA":"🧠","AAPL":"🍎","MSFT":"🪟","AMZN":"📦","GOOGL":"🔍"}
CB = ["#4e79a7","#f28e2b","#e15759","#76b7b2","#59a14f","#edc948","#af7aa1"]

# ──────────────────────── SESSION STATE INIT ──────────────────────────────────
if "init" not in st.session_state:
    st.session_state.init=True
    st.session_state.theme="Light"
    st.session_state.slopes=deepcopy(BASE_SLOPES)
    st.session_state.presets={}
    st.session_state.mobile=False
    st.session_state.toggles={}     # store chart-eye states

# restore state from query suffix (if present)
q=st.query_params
if q.get("s"):
    try:
        st.session_state.slopes.update(json.loads(base64.b64decode(q["s"][0]).decode()))
    except Exception: pass

# ────────────────────────── PAGE CONFIG ───────────────────────────────────────
st.set_page_config(PAGE_TITLE, PAGE_ICON, "wide", initial_sidebar_state="expanded")

# ──────────────────────────── CSS + JS ────────────────────────────────────────
CSS = """
<style>
html,body{font-family:'Inter',sans-serif}
:root{--radius:8px;--shadow:0 4px 12px rgba(0,0,0,.06);}
body.light{--card:#f5f5f5} body.dark{--card:#1e293b;background:#0f172a;color:#e2e8f0}
.banner{background:linear-gradient(90deg,#0062E6 0%,#33AEFF 100%);
        color:#fff;text-align:center;border-radius:var(--radius);
        padding:.8rem 1rem;margin-bottom:1rem;box-shadow:var(--shadow)}
.cards{display:flex;gap:1rem;overflow-x:auto;margin-bottom:1rem}
.card{flex:1;min-width:140px;background:var(--card);border-radius:var(--radius);
      padding:.7rem;display:flex;align-items:center;box-shadow:var(--shadow);}
.ic{font-size:1.6rem;margin-right:.5rem}.ttl{font-size:.8rem;opacity:.7}
.val{font-size:1.2rem;font-weight:700}
@media(max-width:480px){
  .banner{padding:.6rem;font-size:1.1rem}
  .val{font-size:1.05rem}
  body{padding-bottom:80px}
}
</style>
<script>
document.addEventListener("load",()=>{
  const qs=new URLSearchParams(window.location.search);
  const jump=qs.get("jump");
  if(jump){const el=document.querySelector(`#${jump}`); if(el) el.scrollIntoView();}
});
</script>
"""
st.markdown(CSS,unsafe_allow_html=True)

# ───────────────────────── SIDEBAR CONTROLS ───────────────────────────────────
st.session_state.theme = st.sidebar.radio("🎨 Theme",["Light","Dark"],
                                          index=0 if st.session_state.theme=="Light" else 1)
st.sidebar.checkbox("📱 Mobile mode",value=st.session_state.mobile,
                    key="mobile")

fcast_date=st.sidebar.date_input("Forecast Date",date.today()+timedelta(days=1))
weekday=fcast_date.weekday()
day_grp="Tuesday" if weekday==1 else "Thursday" if weekday==3 else "Mon/Wed/Fri"

with st.sidebar.expander("📉 Slopes"):
    for k in st.session_state.slopes:
        st.session_state.slopes[k]=st.slider(k,-1.0,1.0,st.session_state.slopes[k],0.0001)

# preset save/load
with st.sidebar.expander("💾 Presets"):
    pn=st.text_input("Preset name")
    if st.button("Save current"): st.session_state.presets[pn]=deepcopy(st.session_state.slopes)
    if st.session_state.presets:
        sel=st.selectbox("Load preset",list(st.session_state.presets))
        if st.button("Load"): st.session_state.slopes.update(st.session_state.presets[sel])

# share suffix
enc=base64.b64encode(json.dumps(st.session_state.slopes).encode()).decode()
st.sidebar.text_input("🔗 Share-link suffix",f"?s={enc}",disabled=True)

# ───────────────────── TIME & BLOCK HELPERS ───────────────────────────────────
def slots(): return [(datetime(2025,1,1,7,30)+timedelta(minutes=30*i)).strftime("%H:%M") for i in range(15)]
def blk_spx(a,t):
    b=0
    while a<t:
        if a.hour!=16:b+=1
        a+=timedelta(minutes=30)
    return b
blk_stock=lambda a,t:max(0,int((t-a).total_seconds()//1800))
def line(p,s,anchor,fd,spx=True):
    rows=[]
    for sstr in slots():
        h,m=map(int,sstr.split(":"))
        tgt=datetime.combine(fd,time(h,m))
        b=blk_spx(anchor,tgt) if spx else blk_stock(anchor,tgt)
        rows.append({"Time":sstr,"Projected":round(p+s*b,2)})
    return pd.DataFrame(rows)
def fan(p,s,anchor,fd,spx=True):
    rows=[]
    for sstr in slots():
        h,m=map(int,sstr.split(":"))
        tgt=datetime.combine(fd,time(h,m))
        b=blk_spx(anchor,tgt) if spx else blk_stock(anchor,tgt)
        rows.append({"Time":sstr,"Entry":round(p+s*b,2),"Exit":round(p-s*b,2)})
    return pd.DataFrame(rows)
def delta_chart(df,color,field="Projected"):
    base=df[field].iloc[0]
    d=df.assign(delta=df[field]-base)
    return alt.Chart(d).mark_line(color=color).encode(
        x="Time",y=alt.Y("delta:Q",title="Δ vs anchor"),tooltip=["Time",field])

def toggle(key,default=False):   # centralised toggle preserving state
    return st.toggle("👁️ Show chart",value=st.session_state.toggles.get(key,default),key=key)

# responsive columns
cols=lambda n:(st,) if st.session_state.mobile else st.columns(n)

# ──────────────────────────── HEADER ──────────────────────────────────────────
st.markdown(f"<div class='banner'><h3>{PAGE_ICON}&nbsp;{PAGE_TITLE}</h3></div>",unsafe_allow_html=True)
st.caption("An **anchor trend** projects prices from a chosen prior-day point "
           "(high, close, or low) using your configured slope for each 30-min block.")

tabs=st.tabs([f"{ICONS[t]} {t}" for t in ICONS])

# ─────────────────────────── SPX TAB ──────────────────────────────────────────
with tabs[0]:
    st.write(f"### {ICONS['SPX']} SPX Forecast ({day_grp})")
    c1,c2,c3=cols(3)
    hp,ht=c1.number_input("High Price",6185.8),c1.time_input("High Time",time(11,30))
    cp,ct=c2.number_input("Close Price",6170.2),c2.time_input("Close Time",time(15))
    lp,lt=c3.number_input("Low Price",6130.4), c3.time_input("Low Time", time(13,30))

    # special day UIs
    if day_grp=="Tuesday":
        st.subheader("Overnight Contract Line")
        o1,o2=cols(2)
        cl1_t,cl1_p=o1.time_input("Low-1 Time",time(2)),  o1.number_input("Low-1 Price",6100.0)
        cl2_t,cl2_p=o2.time_input("Low-2 Time",time(3,30)),o2.number_input("Low-2 Price",6120.0)
        cl_t,cl_p=st.time_input("Contract Low Time",time(7,30)),st.number_input("Contract Low Price",5.0)
    if day_grp=="Thursday":
        st.subheader("Overnight Contract Line")
        p1,p2=cols(2)
        ol1_t,ol1_p=p1.time_input("Low-1 Time",time(2)),p1.number_input("Low-1 Price",6100.0)
        ol2_t,ol2_p=p2.time_input("Low-2 Time",time(3,30)),p2.number_input("Low-2 Price",6120.0)
        b_t,b_p=st.time_input("Bounce Low Time",time(7,30)),st.number_input("Bounce Low Price",6100.0)

    if st.button("Run Forecast"):
        ah,ac,al=[datetime.combine(fcast_date-timedelta(days=1),t) for t in (ht,ct,lt)]

        # Tuesday logic
        if day_grp=="Tuesday":
            dt1,dt2=[datetime.combine(fcast_date-timedelta(days=1),t) for t in (cl1_t,cl2_t)]
            alt_slope=(cl2_p-cl1_p)/(blk_spx(dt1,dt2) or 1)
            df=line(cl1_p,alt_slope,dt1,fcast_date)
            st.subheader("Contract Line (2-pt)")
            st.dataframe(df,use_container_width=True)
            if toggle("tue_contract",not st.session_state.mobile):
                st.altair_chart(delta_chart(df,CB[0]),use_container_width=True)
            df2=line(cl_p,FIXED_CL_SLOPE,datetime.combine(fcast_date,cl_t),fcast_date)
            st.subheader("Fixed SPX Line")
            st.dataframe(df2,use_container_width=True)
            if toggle("tue_fixed"):
                st.altair_chart(delta_chart(df2,CB[1]),use_container_width=True)

        # Thursday logic
        elif day_grp=="Thursday":
            dt1,dt2=[datetime.combine(fcast_date-timedelta(days=1),t) for t in (ol1_t,ol2_t)]
            alt_slope=(ol2_p-ol1_p)/(blk_spx(dt1,dt2) or 1)
            df=line(ol1_p,alt_slope,dt1,fcast_date)
            st.subheader("Contract Line (2-pt)")
            st.dataframe(df,use_container_width=True)
            if toggle("thu_contract",not st.session_state.mobile):
                st.altair_chart(delta_chart(df,CB[0]),use_container_width=True)
            df2=line(b_p,st.session_state.slopes["SPX_LOW"],
                     datetime.combine(fcast_date-timedelta(days=1),b_t),fcast_date)
            st.subheader("Bounce-Low Line")
            st.dataframe(df2,use_container_width=True)
            if toggle("thu_bounce"):
                st.altair_chart(delta_chart(df2,CB[1]),use_container_width=True)

        # Mon/Wed/Fri default
        else:
            st.markdown('<div class="cards">',unsafe_allow_html=True)
            for txt,val,ic in [("High",hp,"🔼"),("Close",cp,"⏹️"),("Low",lp,"🔽")]:
                st.markdown(f'<div class="card"><span class="ic">{ic}</span>'
                            f'<div><div class="ttl">{txt} Anchor</div><div class="val">{val:.2f}</div></div></div>',
                            unsafe_allow_html=True)
            st.markdown('</div>',unsafe_allow_html=True)

            for txt,val,slope_key,anchor,col in [
                ("High",hp,"SPX_HIGH",ah,CB[0]),
                ("Close",cp,"SPX_CLOSE",ac,CB[1]),
                ("Low", lp,"SPX_LOW",  al,CB[2])]:
                df=fan(val,st.session_state.slopes[slope_key],anchor,fcast_date)
                tag=f"{txt.lower()}_fan"
                st.subheader(f"{txt} Anchor Trend")
                st.dataframe(df,use_container_width=True)
                if toggle(tag):
                    d=df.assign(EntryΔ=df["Entry"]-df["Entry"].iloc[0],
                                ExitΔ=df["Exit"]-df["Entry"].iloc[0])
                    ch=alt.Chart(d).transform_fold(["EntryΔ","ExitΔ"]).mark_line().encode(
                          x="Time",y=alt.Y("value:Q",title="Δ vs anchor"),color="key:N")
                    st.altair_chart(ch,use_container_width=True)

# ───────────────────────── STOCK TABS ─────────────────────────────────────────
def stock(idx,tic,col):
    with tabs[idx]:
        st.write(f"### {ICONS[tic]} {tic}")
        a,b=cols(2)
        lp,lt=a.number_input("Prev-day Low",key=f"{tic}_lp"),a.time_input("Low Time",time(7,30),key=f"{tic}_lt")
        hp,ht=b.number_input("Prev-day High",key=f"{tic}_hp"),b.time_input("High Time",time(7,30),key=f"{tic}_ht")
        if st.button("Generate",key=f"go_{tic}"):
            df_low =fan(lp,st.session_state.slopes[tic],datetime.combine(fcast_date,lt),fcast_date,False)
            df_hi  =fan(hp,st.session_state.slopes[tic],datetime.combine(fcast_date,ht),fcast_date,False)
            st.dataframe(df_low,use_container_width=True)
            st.dataframe(df_hi ,use_container_width=True)
            if toggle(f"{tic}_chart"):
                ch=alt.layer(
                    delta_chart(df_low,"grey","Entry").encode(y=alt.Y("delta:Q",title="Δ")),
                    delta_chart(df_hi ,col,"Entry")
                )
                st.altair_chart(ch,use_container_width=True)

for i,(tic,col) in enumerate(zip(list(ICONS)[1:],CB[1:]),1): stock(i,tic,col)

# ───────────────────────── FOOTER ─────────────────────────────────────────────
st.markdown(f"<hr><center style='font-size:.8rem'>v{VERSION} • "
            f"{datetime.now():%Y-%m-%d %H:%M:%S}</center>",unsafe_allow_html=True)