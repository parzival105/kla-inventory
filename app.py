import streamlit as st
import pandas as pd

import io

st.set_page_config(
    page_title="KLA Business Suite",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── State ──────────────────────────────────────────────────────────────────────
if "user" not in st.session_state: st.session_state.user = None
if "analysis" not in st.session_state: st.session_state.analysis = None
if "components" not in st.session_state: st.session_state.components = []
if "page" not in st.session_state: st.session_state.page = "dashboard"

def get_user(): return st.session_state.user
def get_an(): return st.session_state.analysis
def is_admin(): u=get_user(); return u and u["role"]=="super_admin"
def is_mgr(): u=get_user(); return u and u["role"] in ["super_admin","area_manager"]
def is_leader(): u=get_user(); return u and u["role"] in ["super_admin","area_manager","store_leader"]

def fmt(v):
    try:
        v=float(v); s="-" if v<0 else ""; a=abs(v)
        if a>=1e9: return f"{s}Rp {a/1e9:.2f}M"
        if a>=1e6: return f"{s}Rp {a/1e6:.1f}Jt"
        if a>=1e3: return f"{s}Rp {a/1e3:.0f}Rb"
        return f"{s}Rp {a:,.0f}"
    except: return "Rp 0"

def go(page): st.session_state.page=page; st.rerun()

# ── Session Persistence via localStorage ─────────────────────────────────────
def save_session_cookie(token):
    # Simpan ke localStorage via JS — persist lewat reload
    st.markdown(f"""<script>
    try{{localStorage.setItem('kla_token','{token}');}}catch(e){{}}
    </script>""", unsafe_allow_html=True)

def clear_session_cookie():
    st.markdown("""<script>
    try{{localStorage.removeItem('kla_token');}}catch(e){{}}
    </script>""", unsafe_allow_html=True)

def get_token_from_storage():
    # Baca dari query param yang di-inject JS saat load
    try:
        return st.query_params.get("_t", None)
    except:
        return None

def inject_token_reader():
    # JS: baca localStorage dan inject ke URL sebagai query param
    st.markdown("""<script>
    (function(){
        try{
            var t=localStorage.getItem('kla_token');
            if(t){
                var url=new URL(window.location.href);
                if(url.searchParams.get('_t')!==t){
                    url.searchParams.set('_t',t);
                    window.history.replaceState({},'',url.toString());
                    window.location.reload();
                }
            }
        }catch(e){}
    })();
    </script>""", unsafe_allow_html=True)

def restore_session():
    # User sudah ada di session — pastikan analysis juga ada
    if st.session_state.get("user"):
        if not st.session_state.get("analysis"):
            try:
                from modules.storage import load_analysis, load_components
                an = load_analysis()
                if an: st.session_state.analysis = an
                comps = load_components()
                if comps: st.session_state.components = comps
            except: pass
        return True
    # Coba restore dari query param _t (diisi JS dari localStorage)
    token = get_token_from_storage()
    if not token: return False
    try:
        from modules.db import validate_token
        user = validate_token(token)
        if user:
            st.session_state.user = user
            st.session_state._token = token
            try:
                from modules.storage import load_analysis, load_components
                an = load_analysis()
                if an: st.session_state.analysis = an
                comps = load_components()
                if comps: st.session_state.components = comps
            except: pass
            return True
    except: pass
    return False

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════
def page_login():
    inject_token_reader()
    st.markdown("""
<style>
.login-logo{background:linear-gradient(135deg,#431061,#6d28a0);border-radius:16px;padding:14px 32px;font-size:32px;font-weight:900;color:white;letter-spacing:.12em;display:inline-block}
</style>
<div style="text-align:center;padding:48px 0 24px">
<div class="login-logo">KLA</div>
<h1 style="color:#e2e8f0;margin:8px 0 4px">Business Suite</h1>
<p style="color:#6b4f8a;margin:0">PT KLA Teknologi Indonesia · Komplit · Nyaman · Bergaransi</p>
</div>""", unsafe_allow_html=True)
    _,col,_=st.columns([1,1.1,1])
    with col:
        with st.form("login"):
            st.subheader("Masuk ke Akun Anda")
            username=st.text_input("Username")
            password=st.text_input("Password",type="password")
            if st.form_submit_button("Masuk →",use_container_width=True,type="primary"):
                if not username or not password:
                    st.error("Lengkapi username dan password")
                else:
                    try:
                        from modules.db import login
                        ok,token,user=login(username,password)
                        if ok:
                            st.session_state.user=user
                            st.session_state._token=token
                            save_session_cookie(token)
                            try:
                                from modules.storage import load_analysis,load_components
                                an=load_analysis()
                                if an: st.session_state.analysis=an
                                comps=load_components()
                                if comps: st.session_state.components=comps
                            except: pass
                            st.rerun()
                        else: st.error("Username atau password salah")
                    except Exception as e: st.error(f"Error: {e}")
        st.caption("Lupa password? Hubungi Super Admin")

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    user=get_user()
    with st.sidebar:
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#431061,#6d28a0);border-radius:12px;padding:12px 16px;margin-bottom:10px">
<span style="font-weight:900;font-size:24px;color:white;letter-spacing:.1em">KLA</span>
<span style="color:#d1b3ff;font-size:12px;margin-left:8px">Business Suite</span>
</div>
<div style="background:#180d28;border:1px solid #2d1a45;border-radius:10px;padding:12px;margin-bottom:14px">
<div style="color:#e2e8f0;font-weight:600;font-size:14px">{user["full_name"]}</div>
<div style="color:#a855f7;font-size:12px">{user.get("role_label",user["role"])}</div>
{"<div style='color:#4a3060;font-size:11px'>📍 "+user.get("branch_name","")+"</div>" if user.get("branch_name") else ""}
</div>""", unsafe_allow_html=True)
        menus=[("🏠 Dashboard","dashboard",True),("📦 Inventory","inventory",is_leader()),("🏢 Branch Intelligence","branch",is_leader()),("🔄 Transfer Engine","transfer",is_leader()),("🛒 Restock Engine","restock",is_leader()),("☠️ Dead Stock","deadstock",is_leader()),("💰 Pricing","pricing",is_leader()),("🤖 AI Recommendation","recs",is_leader()),("🔍 Sales Assistant","sales",True),("🖥️ PC Builder","pcbuilder",True),("📥 Export Excel","export",is_admin()),("👥 User Management","users",is_admin()),("🏪 Kelola Cabang","branches",is_admin())]
        cur=st.session_state.page
        for label,key,show in menus:
            if not show: continue
            if st.button(label,key=f"nav_{key}",use_container_width=True,type="primary" if cur==key else "secondary"):
                go(key)
        st.divider()
        an=get_an()
        if an: st.caption(f"📂 {an.get('filename','')}")
        if st.button("🚪 Logout",use_container_width=True):
            clear_session_cookie()
            try:
                from modules.db import logout
                logout(st.session_state.get("_token",""))
            except: pass
            for k in ["user","analysis","components","page","_token"]:
                if k in st.session_state: del st.session_state[k]
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
def upload_section():
    an=get_an()
    if not is_admin():
        if an: st.info(f"📂 Data aktif: **{an.get('filename','')}** — {len(an.get('df',pd.DataFrame())):,} SKU | Diupload oleh Admin")
        return
    with st.expander("📂 Upload / Update File Stok Excel", expanded=not bool(an)):
        if an: st.success(f"✅ Data aktif: **{an.get('filename','')}** — {len(an.get('df',pd.DataFrame())):,} SKU")
        uploaded=st.file_uploader("Pilih file .xlsx",type=["xlsx","xls"],label_visibility="collapsed")
        if uploaded:
            with st.spinner("Menganalisa file stok... Mohon tunggu (~10-30 detik)"):
                try:
                    from modules.engine import analyze
                    from modules.storage import save_analysis,save_components
                    from modules.db import save_analysis_meta,log_action
                    user=get_user()
                    result=analyze(uploaded.read(), uploaded.name)
                    save_analysis(result); save_components(result.get("components",[]))
                    save_analysis_meta(uploaded.name,user["username"],len(result["df"]))
                    log_action(user["id"],user["username"],"UPLOAD_STOCK",f"{uploaded.name} SKU:{len(result['df'])}")
                    st.session_state.analysis=result
                    st.session_state.components=result.get("components",[])
                    st.success(f"✅ {len(result['df']):,} SKU berhasil dianalisa! {result['rows_excluded']} baris dikecualikan. {result.get('component_count',0)} komponen PC ditemukan.")
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def page_dashboard():
    st.title("📊 Executive Dashboard")
    upload_section()
    an=get_an()
    if not an:
        st.info("Belum ada data. " + ("Upload file stok di atas." if is_admin() else "Super Admin belum mengupload file stok."))
        return
    rev=an.get("revenue",{}); df=an.get("df",pd.DataFrame())
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("💰 Total Inventory",fmt(rev.get("inventory_value",0)),f"{rev.get('total_sku',0):,} SKU")
    with c2: st.metric("☠️ Dead Stock",fmt(rev.get("dead_stock_value",0)),f"{rev.get('dead_stock_pct',0):.1f}%",delta_color="inverse")
    with c3: st.metric("📈 Potensi Profit",fmt(rev.get("potential_profit",0)),"Jika terjual optimal")
    with c4: st.metric("🔄 SKU Fast Moving",f"{rev.get('fast_sku',0):,}",f"Dead: {rev.get('dead_sku',0):,}",delta_color="inverse")
    st.divider()
    col1,col2=st.columns(2)
    with col1:
        st.subheader("Distribusi Kategori")
        if "kategori" in df.columns:
            cc=df["kategori"].value_counts()
            st.bar_chart(cc, color="#a855f7")
    with col2:
        st.subheader("Nilai per Kategori")
        if "kategori" in df.columns and "nilai_inventory" in df.columns:
            cv=df.groupby("kategori")["nilai_inventory"].sum()
            st.bar_chart(cv, color="#7c3aed")
    bs=an.get("branch_summary",pd.DataFrame())
    if not bs.empty:
        st.subheader("🏢 Health Score Cabang")
        hs=bs.set_index("branch")["health_score"].sort_values()
        st.bar_chart(hs, color="#7c3aed")
    dp=rev.get("dead_stock_pct",0)
    if dp>30: st.error(f"🔴 **KRITIS** — Dead stock {dp:.1f}% ({fmt(rev.get('dead_stock_value',0))}). Lakukan clearance segera.")
    elif dp>15: st.warning(f"🟡 **PERHATIAN** — Dead stock {dp:.1f}%. Pertimbangkan bundling/promo.")
    else: st.success(f"🟢 **BAIK** — Dead stock terkontrol {dp:.1f}%.")
    tf=an.get("transfer",pd.DataFrame())
    if not tf.empty: st.info(f"💡 **TRANSFER** — {len(tf):,} rekomendasi transfer senilai {fmt(tf['nilai_transfer'].sum())} tersedia.")

# ══════════════════════════════════════════════════════════════════════════════
# INVENTORY
# ══════════════════════════════════════════════════════════════════════════════
def page_inventory():
    st.title("📦 Inventory Analysis")
    an=get_an()
    if not an: st.info("Belum ada data."); return
    df=an.get("df",pd.DataFrame()).copy(); rev=an.get("revenue",{})
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Total SKU",f"{rev.get('total_sku',0):,}")
    with c2: st.metric("Fast Moving",f"{rev.get('fast_sku',0):,}")
    with c3: st.metric("Dead Stock",f"{rev.get('dead_sku',0):,}",delta_color="inverse")
    with c4: st.metric("Nilai Inventory",fmt(rev.get("inventory_value",0)))
    st.divider()
    col1,col2,col3=st.columns([2,1,1])
    with col1: search=st.text_input("🔍 Cari nama barang","")
    with col2: kat=st.selectbox("Kategori",["Semua","Very Fast","Fast","Slow","Dead Stock"])
    with col3: per_page=st.selectbox("Tampilkan",[50,100,200,500])
    filt=df.copy()
    if search: filt=filt[filt["nama_barang"].str.contains(search,case=False,na=False)]
    if kat!="Semua": filt=filt[filt["kategori"]==kat]
    st.caption(f"Menampilkan {min(per_page,len(filt)):,} dari {len(filt):,} produk")
    cols=["nama_barang","kategori","runrate_bulanan","total_stok","min_stock","stock_day","qty_restock","h1","h2","harga_rekomendasi"]
    if is_mgr(): cols=["nama_barang","kategori","runrate_bulanan","total_stok","min_stock","stock_day","qty_restock","hpp","h1","h2","harga_rekomendasi","margin_persen"]
    elif is_leader(): cols=["nama_barang","kategori","runrate_bulanan","total_stok","min_stock","stock_day","qty_restock","h1","h2","harga_rekomendasi","margin_persen"]
    disp=[c for c in cols if c in filt.columns]
    st.dataframe(filt[disp].head(per_page),use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# BRANCH
# ══════════════════════════════════════════════════════════════════════════════
def page_branch():
    st.title("🏢 Branch Intelligence")
    an=get_an()
    if not an: st.info("Belum ada data."); return
    bs=an.get("branch_summary",pd.DataFrame())
    if bs.empty: st.info("Data per-cabang tidak tersedia."); return
    user=get_user(); role=user["role"]
    if role=="store_leader" and user.get("branch"):
        bs=bs[bs["branch"]==user["branch"]]
    elif role=="area_manager" and user.get("area"):
        from modules.config import AREA_MAP
        bs=bs[bs["branch"].isin(AREA_MAP.get(user["area"],[]))]
    if bs.empty: st.info("Tidak ada data untuk cabang/area Anda."); return
    best=bs.iloc[0]; worst=bs.iloc[-1]
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("🏆 Terbaik",best["branch"],f"Score {best['health_score']:.0f}/100")
    with c2: st.metric("⚠️ Bermasalah",worst["branch"],f"Score {worst['health_score']:.0f}/100",delta_color="inverse")
    with c3: st.metric("📊 Rata-rata",f"{bs['health_score'].mean():.0f}/100",f"{len(bs)} cabang")
    with c4: st.metric("🚨 Critical",f"{bs['critical_count'].sum():,}","Stok < 30 hari",delta_color="inverse")
    st.divider()
    hs=bs.set_index("branch")["health_score"].sort_values()
    st.bar_chart(hs, color="#7c3aed")
    disp=bs[["rank","branch","branch_name","area","health_score","total_sku","inventory_value","dead_stock_value","critical_count"]].copy()
    disp["inventory_value"]=disp["inventory_value"].apply(fmt)
    disp["dead_stock_value"]=disp["dead_stock_value"].apply(fmt)
    st.dataframe(disp,use_container_width=True,hide_index=True)
    st.subheader("🔍 Detail per Cabang")
    opts=bs["branch"].tolist()
    sel=st.selectbox("Pilih cabang",opts,format_func=lambda x:f"{x} — {bs[bs['branch']==x]['branch_name'].values[0]}")
    if sel:
        bl=an.get("branch_long",pd.DataFrame())
        if not bl.empty:
            det=bl[bl["branch"]==sel].copy()
            if "status" not in det.columns:
                from modules.engine import _branch_status
                det["status"]=det.apply(_branch_status,axis=1)
            cols=["nama_barang","kategori","stok_cabang","runrate_cabang","min_stock_cabang","stock_day_cabang","status"]
            st.dataframe(det[[c for c in cols if c in det.columns]],use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TRANSFER
# ══════════════════════════════════════════════════════════════════════════════
def page_transfer():
    st.title("🔄 Transfer Engine")
    an=get_an()
    if not an: st.info("Belum ada data."); return
    tf=an.get("transfer",pd.DataFrame())
    if tf.empty: st.info("Tidak ada rekomendasi transfer."); return
    user=get_user(); role=user["role"]
    if role=="store_leader" and user.get("branch"):
        br=user["branch"]; tf=tf[(tf["dari_cabang"]==br)|(tf["ke_cabang"]==br)]
    elif role=="area_manager" and user.get("area"):
        tf=tf[tf["area"]==user["area"]]
    c1,c2,c3=st.columns(3)
    with c1: st.metric("Total Transfer",f"{len(tf):,}")
    with c2: st.metric("Nilai Transfer",fmt(tf["nilai_transfer"].sum()))
    with c3: st.metric("Area Terlibat",f"{tf['area'].nunique()}")
    st.info(f"💡 Prioritaskan transfer sebelum PO baru. Total hemat: **{fmt(tf['nilai_transfer'].sum())}**")
    st.dataframe(tf,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# RESTOCK
# ══════════════════════════════════════════════════════════════════════════════
def page_restock():
    st.title("🛒 Restock Engine")
    an=get_an()
    if not an: st.info("Belum ada data."); return
    df=an.get("df",pd.DataFrame())
    rs=df[df["qty_restock"]>0].sort_values("nilai_restock",ascending=False).copy() if "qty_restock" in df.columns else pd.DataFrame()
    if rs.empty: st.success("✅ Semua SKU memenuhi minimum stok!"); return
    rs["prioritas"]=range(1,len(rs)+1)
    c1,c2,c3=st.columns(3)
    with c1: st.metric("SKU Perlu Restock",f"{len(rs):,}")
    with c2: st.metric("Total Qty",f"{rs['qty_restock'].sum():,.0f}")
    with c3: st.metric("Est. Nilai",fmt(rs["nilai_restock"].sum()))
    cols=["prioritas","nama_barang","kategori","runrate_bulanan","total_stok","min_stock","qty_restock","nilai_restock"]
    st.dataframe(rs[[c for c in cols if c in rs.columns]].head(200),use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# DEAD STOCK
# ══════════════════════════════════════════════════════════════════════════════
def page_deadstock():
    st.title("☠️ Dead Stock Center")
    an=get_an()
    if not an: st.info("Belum ada data."); return
    dead=an.get("dead_stock",pd.DataFrame())
    if dead.empty: st.success("✅ Tidak ada dead stock!"); return
    total=dead["dead_stock_value"].sum() if "dead_stock_value" in dead.columns else 0
    by_act=dead.groupby("rekomendasi_aksi").agg(count=("nama_barang","count"),value=("dead_stock_value","sum")).to_dict(orient="index") if "rekomendasi_aksi" in dead.columns else {}
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Total SKU Dead Stock",f"{len(dead):,}")
    with c2: st.metric("Nilai Tertahan",fmt(total))
    with c3: st.metric("Perlu Clearance",f"{by_act.get('Clearance',{}).get('count',0):,}")
    with c4: st.metric("Perlu Bundling",f"{by_act.get('Bundling',{}).get('count',0):,}")
    for action,icon in [("Clearance","🚨"),("Bundling","📦"),("Turunkan ke HD","🔽"),("Monitor","👁️")]:
        grp=dead[dead["rekomendasi_aksi"]==action] if "rekomendasi_aksi" in dead.columns else pd.DataFrame()
        if not grp.empty:
            with st.expander(f"{icon} {action} ({len(grp)} SKU, {fmt(grp['dead_stock_value'].sum())})"):
                cols=["nama_barang","kategori","total_stok","dead_stock_value","estimasi_bulan","alasan"]
                st.dataframe(grp[[c for c in cols if c in grp.columns]],use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# PRICING
# ══════════════════════════════════════════════════════════════════════════════
def page_pricing():
    st.title("💰 Pricing Analysis")
    an=get_an()
    if not an: st.info("Belum ada data."); return
    df=an.get("df",pd.DataFrame()).copy()
    cols=["nama_barang","kategori","runrate_bulanan","h1","h2","hd","harga_rekomendasi"]
    if is_mgr(): cols=["nama_barang","kategori","runrate_bulanan","hpp","h1","h2","hd","harga_rekomendasi","margin_persen","margin_nominal"]
    elif is_leader(): cols=["nama_barang","kategori","runrate_bulanan","h1","h2","hd","harga_rekomendasi","margin_persen"]
    kat=st.selectbox("Kategori",["Semua","Very Fast","Fast","Slow","Dead Stock"])
    filt=df if kat=="Semua" else df[df["kategori"]==kat]
    st.dataframe(filt[[c for c in cols if c in filt.columns]],use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# AI RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════
def page_recs():
    st.title("🤖 AI Recommendation")
    an=get_an()
    if not an: st.info("Belum ada data."); return
    recs=an.get("recommendations",[])
    if not recs: st.info("Tidak ada rekomendasi."); return
    PC={"Tinggi":0,"Sedang":1,"Rendah":2}
    CC={"Tinggi":"🔴","Sedang":"🟡","Rendah":"🟢"}
    c1,c2,c3,c4=st.columns(4)
    nH=sum(1 for r in recs if r.get("priority")=="Tinggi")
    nM=sum(1 for r in recs if r.get("priority")=="Sedang")
    cats=list(set(r.get("category","") for r in recs))
    with c1: st.metric("Total Rekomendasi",len(recs))
    with c2: st.metric("Prioritas Tinggi",nH,"Segera")
    with c3: st.metric("Prioritas Sedang",nM)
    with c4: st.metric("Kategori",len(cats))
    st.divider()
    sel_prio=st.multiselect("Filter Prioritas",["Tinggi","Sedang","Rendah"],default=["Tinggi","Sedang","Rendah"])
    sel_cat=st.multiselect("Filter Kategori",cats,default=cats)
    filtered=[r for r in recs if r.get("priority") in sel_prio and r.get("category") in sel_cat]
    filtered.sort(key=lambda r: PC.get(r.get("priority","Rendah"),3))
    st.caption(f"Menampilkan {len(filtered)} dari {len(recs)} rekomendasi")
    for r in filtered:
        prio=r.get("priority","Rendah"); icon=CC.get(prio,"⚪")
        with st.container():
            st.markdown(f"""
<div style="background:#180d28;border:1px solid {'#dc2626' if prio=='Tinggi' else '#d97706' if prio=='Sedang' else '#2d1a45'};border-left:4px solid {'#dc2626' if prio=='Tinggi' else '#d97706' if prio=='Sedang' else '#4a3060'};border-radius:8px;padding:12px 16px;margin-bottom:8px">
<span style="font-size:11px;color:#6b4f8a;font-weight:700;text-transform:uppercase;letter-spacing:.05em">{r.get('icon','')} [{r.get('category','')}] {icon} {prio}</span><br>
<span style="color:#c4b5d4;font-size:14px">{r.get('text','')}</span>
</div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SALES ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════
def page_sales():
    st.title("🔍 Sales Assistant")
    an=get_an()
    if not an: st.info("Belum ada data inventory."); return
    df=an.get("df",pd.DataFrame()); sc=an.get("stock_columns",{})
    from modules.config import BRANCH_FULL
    shortcuts=["Monitor gaming 144Hz budget 2 juta","PC gaming 12 juta","Printer wireless kantor","Mouse wireless Logitech","Tinta Epson L3250","Headset gaming 500rb"]
    st.markdown("**Shortcut:**")
    cols=st.columns(3)
    for i,s in enumerate(shortcuts):
        with cols[i%3]:
            if st.button(s,key=f"sc_{i}",use_container_width=True):
                st.session_state.sales_query=s
    query=st.text_input("💬 Apa yang dicari customer?",value=st.session_state.get("sales_query",""),placeholder='Contoh: "Monitor 24 inch IPS budget 2 juta"',key="sales_input_box")
    if st.button("🔍 Cari Rekomendasi",type="primary") or st.session_state.get("sales_query"):
        st.session_state.sales_query=""
        if not query: st.warning("Masukkan kata kunci pencarian"); return
        import re
        def _tok(t): return [x for x in re.sub(r"[^a-z0-9\s]"," ",str(t).lower()).split() if len(x)>=2]
        terms=_tok(query)
        def _budget(t):
            t=t.lower().replace(".","").replace(",","")
            m=re.search(r"(\d+(?:\.\d+)?)\s*(juta|jt)",t)
            if m: return float(m.group(1))*1e6
            m=re.search(r"(\d+(?:\.\d+)?)\s*(ribu|rb)",t)
            if m: return float(m.group(1))*1e3
            return None
        budget_hint=_budget(query)
        if terms:
            def _match(row):
                s=" ".join(str(row.get(c,"")) for c in ["nama_barang","segment","brand","kategori"]).lower()
                return any(t in s for t in terms)
            results=df[df.apply(_match,axis=1)].copy()
        else: results=df.copy()
        if budget_hint and budget_hint>0 and "h1" in results.columns:
            b=results[results["h1"]<=budget_hint*1.15]
            if not b.empty: results=b
        if results.empty: st.warning("Tidak ada produk cocok."); return
        def _score(row):
            name=str(row.get("nama_barang","")).lower()
            ns=sum(2.0 for t in terms if t in name)
            rr=(row.get("runrate_bulanan",0) or 0)/50; st_=1.0 if (row.get("total_stok",0) or 0)>0 else 0.0
            mg=(row.get("margin_persen",0) or 0)/40
            return ns*0.50+rr*0.25+st_*0.15+mg*0.10
        results=results.copy(); results["_score"]=results.apply(_score,axis=1)
        results=results.nlargest(8,"_score")
        st.success(f"Ditemukan **{len(results)}** produk relevan")
        for i,(_,row) in enumerate(results.iterrows()):
            bs={}
            for br,col in sc.items():
                if col in df.columns:
                    qty=int(float(df.loc[_,col]) if _ in df.index and col in df.columns else 0)
                    if qty>0: bs[br]=qty
            if not bs:
                for br in ["SMG","YK","SLA","TGL","PKL","CRB","KDR","NGL","SKH","MSBY","MJK","BSBY","PWT"]:
                    if br in row.index:
                        qty=int(float(row.get(br,0) or 0))
                        if qty>0: bs[br]=qty
            badge="🥇 Teratas" if i==0 else ""
            h1=float(row.get("h1",0) or 0)
            mp=row.get("margin_persen")
            margin_str=f"Margin {mp:.1f}%" if mp is not None and is_leader() else ""
            stock_badges=" ".join([f"**{BRANCH_FULL.get(br,br)}**: {qty}" for br,qty in sorted(bs.items(),key=lambda x:-x[1])[:6]])
            with st.container():
                st.markdown(f"""
<div style="background:#180d28;border:1px solid {'#431061' if i==0 else '#2d1a45'};border-radius:10px;padding:14px 16px;margin-bottom:8px">
<div style="display:flex;justify-content:space-between;align-items:flex-start">
<div>
{'<span style="background:#431061;color:#d1b3ff;border-radius:10px;padding:2px 8px;font-size:11px;font-weight:700">'+badge+'</span><br>' if badge else ''}
<div style="color:#e2e8f0;font-weight:600;font-size:15px;margin:4px 0 2px">{row.get("nama_barang","")}</div>
<div style="color:#6b4f8a;font-size:12px">{row.get("kategori","")} · {row.get("brand","")}</div>
<div style="color:#4a3060;font-size:11px;margin-top:6px">{stock_badges if stock_badges else "⚠️ Stok kosong semua cabang"}</div>
</div>
<div style="text-align:right">
<div style="color:#a855f7;font-size:20px;font-weight:700;font-family:monospace">{fmt(h1)}</div>
{"<div style='color:#059669;font-size:12px;font-weight:600'>"+margin_str+"</div>" if margin_str else ""}
<div style="color:#4a3060;font-size:11px">Stok: {int(row.get("total_stok",0))} · {row.get("runrate_bulanan",0):.1f}/bln</div>
</div>
</div>
</div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PC BUILDER
# ══════════════════════════════════════════════════════════════════════════════
def page_pcbuilder():
    st.title("🖥️ PC Builder")
    from modules.config import BUILD_TYPES, PC_CATEGORIES, BRANCH_FULL
    from modules.pc_builder import build_pc, build_alternatives
    comps=st.session_state.get("components",[])
    if not comps:
        st.warning("Komponen belum tersedia. Upload file stok terlebih dahulu.")
        return
    st.info(f"✅ {len(comps)} komponen tersedia dari stok KLA")
    col1,col2,col3=st.columns(3)
    with col1: bt=st.selectbox("Tipe Build",BUILD_TYPES)
    with col2:
        budget_labels=["Entry 3-5jt","Mid-Low 5-8jt","Mid 8-12jt","Mid-High 12-18jt","High 18-25jt","Premium 25-35jt"]
        budget_ranges=[(3e6,5e6),(5e6,8e6),(8e6,12e6),(12e6,18e6),(18e6,25e6),(25e6,35e6)]
        tier=st.selectbox("Range Budget",range(len(budget_labels)),format_func=lambda i:budget_labels[i])
        lo,hi=budget_ranges[tier]; budget=st.slider("Budget",int(lo),int(hi),int((lo+hi)/2),500000,format="Rp %d")
        st.caption(f"Budget: **{fmt(budget)}**")
    with col3: brand=st.selectbox("Preferensi CPU",["Tidak Ada","Intel","AMD"])
    if st.button("🔧 Generate Rekomendasi Build",type="primary",use_container_width=True):
        with st.spinner("Memilih komponen terbaik dari stok KLA..."):
            result=build_pc(comps,bt,budget,None if brand=="Tidak Ada" else brand)
        if not result:
            st.error("Tidak dapat membuat build. Budget terlalu rendah atau stok tidak tersedia."); return
        col1,col2=st.columns([1.2,1])
        with col1:
            st.subheader("📋 Komponen Terpilih")
            status="✅ Dalam budget" if result["is_within_budget"] else "⚠️ Sedikit melebihi budget"
            st.caption(status)
            for c in result["components"]:
                bs=c.get("branch_stock",{})
                nama=c.get("nama_barang",c.get("nama",""))
                harga=c.get("selling_price",c.get("h1",0))
                stok_str=" · ".join([f"{BRANCH_FULL.get(br,br)}: {qty}" for br,qty in sorted(bs.items(),key=lambda x:-x[1])[:5]]) if bs else "⚠️ Kosong"
                with st.container():
                    st.markdown(f"""
<div style="background:#130a1e;border:1px solid #2d1a45;border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="color:#4a3060;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em">{c.get("kategori_label",c.get("kategori",""))}</div>
<div style="display:flex;justify-content:space-between;align-items:center">
<div style="color:#e2e8f0;font-size:13px;font-weight:600">{nama}</div>
<div style="color:#a855f7;font-weight:700;font-family:monospace">{fmt(harga)}</div>
</div>
<div style="color:#4a3060;font-size:11px;margin-top:4px">{stok_str}</div>
</div>""",unsafe_allow_html=True)
            st.markdown(f"**TOTAL: <span style='color:#34d399;font-size:20px'>{fmt(result.get('total_price',0))}</span>**",unsafe_allow_html=True)
            st.caption(f"Budget: {fmt(result['budget'])} · Sisa: {fmt(result['sisa_budget'])}")
            for n in result.get("compat_notes",[]): st.success(n)
            for w in result.get("compat_warnings",[]): st.warning(w)
            for w in result.get("build_warnings",[]): st.warning(w)
            user=get_user()
            with st.form("save_build"):
                build_name=st.text_input("Nama Build",value=f"{bt} Rp{result['total_price']/1e6:.0f}Jt")
                if st.form_submit_button("💾 Simpan Build"):
                    try:
                        from modules.db import save_build_history
                        save_build_history(user["id"],user.get("branch",""),build_name,bt,budget,result["total_price"],"")
                        st.success("Build tersimpan!")
                    except Exception as e: st.error(f"Gagal: {e}")
        with col2:
            st.subheader("🤖 Penjelasan AI")
            try:
                from modules.config import ANTHROPIC_KEY
                if ANTHROPIC_KEY:
                    import anthropic, json
                    safe=[{"tipe":c.get("kategori_label",""),"nama":c.get("nama_barang",c.get("nama","")),"harga":fmt(c.get("selling_price",c.get("h1",0)))} for c in result["components"]]
                    prompt=f"Kamu konsultan PC di KLA Computer. Jelaskan build ini untuk customer dalam 3 paragraf Bahasa Indonesia.\nBUILD: {bt} | Total: {fmt(result['total_price'])}\nKOMPONEN: {json.dumps(safe,ensure_ascii=False)}\nFokus pada manfaat, jangan sebut HPP/margin."
                    client=anthropic.Anthropic(api_key=ANTHROPIC_KEY)
                    with st.spinner("Generating AI explanation..."):
                        msg=client.messages.create(model="claude-haiku-4-5",max_tokens=500,messages=[{"role":"user","content":prompt}])
                        st.write(msg.content[0].text)
                else: st.caption("Set ANTHROPIC_API_KEY di Secrets untuk AI explanation.")
            except Exception as e: st.caption(f"AI tidak tersedia: {e}")
            alts=build_alternatives(comps,bt,budget)
            if alts:
                st.subheader("🔀 Alternatif Build")
                for alt in alts:
                    label="💰 Budget Hemat" if alt["total_price"]<result["total_price"] else "⬆️ Upgrade Option"
                    with st.expander(f"{label} — {fmt(alt['total_price'])}"):
                        for c in alt["components"]:
                            st.text(f"  {c.get('kategori_label','')}: {c.get('nama_barang',c.get('nama',''))} — {fmt(c.get('selling_price',c.get('h1',0)))}")

# ══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════════════════
def page_export():
    st.title("📥 Export Excel")
    an=get_an()
    if not an: st.info("Belum ada data."); return
    import xlsxwriter
    df=an.get("df",pd.DataFrame()); rev=an.get("revenue",{})
    rs=df[df["qty_restock"]>0].sort_values("nilai_restock",ascending=False).copy() if "qty_restock" in df.columns else pd.DataFrame()
    if not rs.empty: rs["prioritas"]=range(1,len(rs)+1)
    recs_df=pd.DataFrame(an.get("recommendations",[]))
    rev_df=pd.DataFrame([("Total Inventory",fmt(rev.get("inventory_value",0))),("Dead Stock",fmt(rev.get("dead_stock_value",0))),("Dead Stock %",f"{rev.get('dead_stock_pct',0):.1f}%"),("Potensi Profit",fmt(rev.get("potential_profit",0))),("Total SKU",str(rev.get("total_sku",0)))],columns=["Metrik","Nilai"])
    def sel(d,cols): return d[[c for c in cols if c in d.columns]] if not d.empty else d
    ic=["nama_barang","segment","kategori","runrate_bulanan","total_stok","min_stock","qty_restock","hpp","h1","h2","harga_rekomendasi","margin_persen"]
    sheets={"Executive Summary":rev_df,"AI Recommendation":recs_df,"Inventory":sel(df,ic),"Branch":an.get("branch_summary",pd.DataFrame()),"Restock":sel(rs,ic+["prioritas"]),"Transfer":an.get("transfer",pd.DataFrame()),"Dead Stock":an.get("dead_stock",pd.DataFrame())}
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine="xlsxwriter") as writer:
        wb=writer.book; hf=wb.add_format({"bold":True,"bg_color":"#431061","font_color":"#ffffff"})
        for sname,sdf in sheets.items():
            if sdf is None or sdf.empty: sdf=pd.DataFrame({"Info":["No data"]})
            sdf.to_excel(writer,sheet_name=sname[:31],index=False)
            ws=writer.sheets[sname[:31]]
            for ci,col in enumerate(sdf.columns):
                ws.write(0,ci,col,hf)
                try: w=max(sdf[col].astype(str).map(len).max() if len(sdf) else 0,len(str(col)))
                except: w=len(str(col))
                ws.set_column(ci,ci,min(w+4,50))
    buf.seek(0)
    st.download_button("📥 Download Laporan Lengkap (.xlsx)",data=buf,file_name=f"KLA_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,type="primary")
    st.write("**Sheet yang tersedia:**")
    for s in sheets: st.write(f"• {s}")

# ══════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
def page_users():
    st.title("👥 User Management")
    from modules.db import get_all_users,create_user,update_user,deactivate_user
    from modules.config import ROLE_LABELS,BRANCH_FULL,AREA_MAP,ALL_BRANCHES
    users=get_all_users()
    active=[u for u in users if u.get("is_active")]
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Total Aktif",len(active))
    with c2: st.metric("Admin",sum(1 for u in active if u["role"]=="super_admin"))
    with c3: st.metric("Store Leader",sum(1 for u in active if u["role"]=="store_leader"))
    with c4: st.metric("Sales",sum(1 for u in active if u["role"]=="sales"))
    st.divider()
    tab1,tab2,tab3=st.tabs(["📋 Daftar User","➕ Buat User Baru","✏️ Edit User"])
    with tab1:
        for u in active:
            col1,col2=st.columns([4,1])
            with col1:
                st.markdown(f"**{u['full_name']}** (@{u['username']}) — *{u.get('role_label',u['role'])}*")
                if u.get("branch_name"): st.caption(f"📍 {u['branch_name']}")
            with col2:
                if u["username"]!="admin":
                    if st.button("Nonaktifkan",key=f"del_{u['id']}",type="secondary"):
                        ok,msg=deactivate_user(u["id"])
                        if ok: st.success(msg); st.rerun()
                        else: st.error(msg)
    with tab2:
        with st.form("create_user"):
            c1,c2=st.columns(2)
            with c1:
                fn=st.text_input("Nama Lengkap *")
                un=st.text_input("Username *")
            with c2:
                pw=st.text_input("Password *",type="password")
                pw2=st.text_input("Konfirmasi Password *",type="password")
            role=st.selectbox("Role",list(ROLE_LABELS.keys()),format_func=lambda k:ROLE_LABELS[k])
            branch=None; area=None
            if role in ["store_leader","sales"]:
                branch=st.selectbox("Cabang *",ALL_BRANCHES,format_func=lambda b:f"{b} — {BRANCH_FULL.get(b,b)}")
            elif role=="area_manager":
                area=st.selectbox("Area *",list(AREA_MAP.keys()))
            if st.form_submit_button("Buat User",type="primary"):
                if not fn or not un or not pw: st.error("Lengkapi semua field wajib")
                elif pw!=pw2: st.error("Password tidak cocok")
                elif len(pw)<6: st.error("Password minimal 6 karakter")
                else:
                    ok,msg=create_user(un,pw,fn,role,branch,area)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
    with tab3:
        opts=[u for u in active if u["username"]!="admin"]
        if not opts: st.info("Tidak ada user yang bisa diedit."); return
        sel=st.selectbox("Pilih User",opts,format_func=lambda u:f"{u['full_name']} (@{u['username']})")
        if sel:
            with st.form("edit_user"):
                fn=st.text_input("Nama Lengkap",value=sel["full_name"])
                role=st.selectbox("Role",list(ROLE_LABELS.keys()),index=list(ROLE_LABELS.keys()).index(sel["role"]) if sel["role"] in ROLE_LABELS else 0,format_func=lambda k:ROLE_LABELS[k])
                branch=None; area=None
                if role in ["store_leader","sales"]:
                    branch=st.selectbox("Cabang",ALL_BRANCHES,index=ALL_BRANCHES.index(sel.get("branch",ALL_BRANCHES[0])) if sel.get("branch") in ALL_BRANCHES else 0,format_func=lambda b:f"{b} — {BRANCH_FULL.get(b,b)}")
                elif role=="area_manager":
                    areas=list(AREA_MAP.keys())
                    area=st.selectbox("Area",areas,index=areas.index(sel.get("area",areas[0])) if sel.get("area") in areas else 0)
                is_active=st.checkbox("User Aktif",value=True)
                new_pw=st.text_input("Password Baru (kosongkan jika tidak diubah)",type="password")
                if st.form_submit_button("Simpan Perubahan",type="primary"):
                    ok,msg=update_user(sel["id"],fn,role,branch,area,is_active,new_pw or None)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)

# ══════════════════════════════════════════════════════════════════════════════
# BRANCH MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════
def page_branches():
    st.title("🏪 Kelola Cabang")
    from modules.db import get_branches, add_branch, update_branch, deactivate_branch
    from modules.config import AREA_MAP as _AREA_MAP

    # Reload dari Supabase langsung
    try:
        from modules.db import _get
        rows = _get("branches", {"order":"area.asc,code.asc","select":"*"})
    except Exception as e:
        st.error(f"Error: {e}"); return

    active = [r for r in rows if r.get("is_active")]
    inactive = [r for r in rows if not r.get("is_active")]

    # Ambil daftar area dari yang sudah ada + default
    all_areas = sorted(set(
        list(_AREA_MAP.keys()) +
        [r["area"] for r in rows]
    ))

    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Total Cabang Aktif", len(active))
    with c2: st.metric("Total Area", len(set(r["area"] for r in active)))
    with c3: st.metric("Cabang Nonaktif", len(inactive))

    st.divider()
    tab1, tab2, tab3 = st.tabs(["📋 Daftar Cabang", "➕ Tambah Cabang", "✏️ Edit / Nonaktifkan"])

    with tab1:
        # Group by area
        area_groups = {}
        for r in active:
            area_groups.setdefault(r["area"],[]).append(r)
        for area, branches in sorted(area_groups.items()):
            st.subheader(area)
            for b in branches:
                col1,col2 = st.columns([4,1])
                with col1:
                    st.markdown(f"**{b['code']}** — {b['name']}")
                with col2:
                    st.caption("✅ Aktif")
            st.divider()
        if inactive:
            with st.expander(f"⛔ Cabang Nonaktif ({len(inactive)})"):
                for b in inactive:
                    st.markdown(f"~~**{b['code']}** — {b['name']}~~")

    with tab2:
        with st.form("add_branch"):
            st.subheader("Tambah Cabang Baru")
            c1,c2 = st.columns(2)
            with c1:
                code = st.text_input("Kode Cabang *", placeholder="Contoh: SOLO, TSM, BDG").upper()
                name = st.text_input("Nama Cabang *", placeholder="Contoh: Solo, Tasikmalaya, Bandung")
            with c2:
                area_choice = st.selectbox("Area *", all_areas + ["+ Buat Area Baru"])
                if area_choice == "+ Buat Area Baru":
                    area = st.text_input("Nama Area Baru *", placeholder="Contoh: Area 4 — Jawa Barat")
                else:
                    area = area_choice
            st.caption("⚠️ Setelah tambah cabang, upload ulang file stok agar cabang baru terdeteksi.")
            if st.form_submit_button("➕ Tambah Cabang", type="primary"):
                if not code or not name or not area:
                    st.error("Lengkapi semua field")
                elif len(code) < 2 or len(code) > 6:
                    st.error("Kode cabang harus 2-6 karakter")
                else:
                    ok, msg = add_branch(code, name, area)
                    if ok:
                        st.success(msg)
                        # Reload branch config di session
                        from modules import config as cfg
                        _bc = cfg.get_branch_config()
                        cfg.ALL_BRANCHES = _bc[0]; cfg.BRANCH_FULL = _bc[1]
                        cfg.AREA_MAP = _bc[2]; cfg.BRANCH_TO_AREA = _bc[3]
                        st.rerun()
                    else:
                        st.error(msg)

    with tab3:
        if not rows:
            st.info("Belum ada cabang."); return
        sel = st.selectbox("Pilih Cabang", rows, format_func=lambda r: f"{r['code']} — {r['name']} ({'Aktif' if r.get('is_active') else 'Nonaktif'})")
        if sel:
            with st.form("edit_branch"):
                c1,c2 = st.columns(2)
                with c1:
                    new_name = st.text_input("Nama Cabang", value=sel["name"])
                    new_area = st.selectbox("Area", all_areas, index=all_areas.index(sel["area"]) if sel["area"] in all_areas else 0)
                with c2:
                    is_active = st.checkbox("Cabang Aktif", value=sel.get("is_active", True))
                    st.caption(f"Kode: **{sel['code']}** (tidak bisa diubah)")
                col1,col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Simpan", type="primary"):
                        ok,msg = update_branch(sel["code"], new_name, new_area, is_active)
                        if ok:
                            st.success(msg)
                            from modules import config as cfg
                            _bc = cfg.get_branch_config()
                            cfg.ALL_BRANCHES = _bc[0]; cfg.BRANCH_FULL = _bc[1]
                            cfg.AREA_MAP = _bc[2]; cfg.BRANCH_TO_AREA = _bc[3]
                            st.rerun()
                        else: st.error(msg)
                with col2:
                    if sel.get("is_active") and st.form_submit_button("⛔ Nonaktifkan", type="secondary"):
                        ok,msg = deactivate_branch(sel["code"])
                        if ok: st.success(msg); st.rerun()
                        else: st.error(msg)

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
def main():
    if not get_user():
        if not restore_session():
            page_login(); return
    # Load analysis dari Supabase untuk semua role jika belum ada di session
    if get_user() and not st.session_state.get("analysis"):
        try:
            from modules.storage import load_analysis, load_components
            an = load_analysis()
            if an:
                st.session_state.analysis = an
            comps = load_components()
            if comps:
                st.session_state.components = comps
        except: pass
    render_sidebar()
    p=st.session_state.page
    if p=="dashboard": page_dashboard()
    elif p=="inventory": page_inventory()
    elif p=="branch": page_branch()
    elif p=="transfer": page_transfer()
    elif p=="restock": page_restock()
    elif p=="deadstock": page_deadstock()
    elif p=="pricing": page_pricing()
    elif p=="recs": page_recs()
    elif p=="sales": page_sales()
    elif p=="pcbuilder": page_pcbuilder()
    elif p=="export": page_export()
    elif p=="users": page_users()
    elif p=="branches": page_branches()
    else: page_dashboard()

main()
