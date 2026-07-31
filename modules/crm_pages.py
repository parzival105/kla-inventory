import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from modules.crm_db import (
    STATUSES, STATUS_MAP, PRIORITY_COLOR, MEDIA_OPTS, FOLLOWUP_RESULTS, LOST_REASONS,
    create_project, get_projects, get_project, update_project, update_project_status,
    add_product, get_products, update_product,
    add_supplier, get_suppliers, select_supplier,
    create_quotation, get_quotations, update_quotation,
    add_followup, get_followups,
    add_replacement, get_replacements, search_knowledge_base,
    get_timeline, get_dashboard_stats, log_timeline,
    add_document, get_documents, download_document, delete_document,
    generate_notifications, get_notifications, mark_notification_read, mark_all_notifications_read,
    NOTIF_RULES_LABEL,
)
from modules.config import BRANCH_FULL, AREA_MAP

def _fmt(v):
    try:
        v=float(v); a=abs(v)
        if a>=1e9: return f"Rp {a/1e9:.2f}M"
        if a>=1e6: return f"Rp {a/1e6:.1f}Jt"
        if a>=1e3: return f"Rp {a/1e3:.0f}Rb"
        return f"Rp {a:,.0f}"
    except: return "Rp 0"

def _status_badge(status):
    label, color = STATUS_MAP.get(status, (status, "#94a3b8"))
    return f'<span style="background:{color};color:white;border-radius:12px;padding:2px 10px;font-size:11px;font-weight:600">{label}</span>'

def _priority_badge(priority):
    color = PRIORITY_COLOR.get(priority,"#94a3b8")
    return f'<span style="background:{color}22;color:{color};border:1px solid {color}44;border-radius:8px;padding:2px 8px;font-size:10px;font-weight:700">{priority}</span>'

def is_admin(user): return user["role"]=="super_admin"
def is_manager(user): return user["role"] in ["super_admin","area_manager"]
def is_leader_up(user): return user["role"] in ["super_admin","area_manager","store_leader"]
def can_pm(user): return user["role"]=="super_admin"
def can_buy(user): return user["role"]=="super_admin"

def get_my_projects(user):
    role = user["role"]
    if role == "sales":
        return get_projects(sales_id=user["id"])
    elif role == "store_leader":
        return get_projects(branch=user.get("branch"))
    elif role == "area_manager":
        area = user.get("area","")
        branches = AREA_MAP.get(area,[])
        all_p = []
        for br in branches:
            all_p += get_projects(branch=br)
        seen = set(); result = []
        for p in all_p:
            if p["id"] not in seen:
                seen.add(p["id"]); result.append(p)
        return result
    else:
        return get_projects()

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def render_dashboard(user):
    st.title("📊 CRM Dashboard")
    branch = user.get("branch") if user["role"]=="store_leader" else None
    stats = get_dashboard_stats(branch=branch)

    c1,c2,c3,c4,c5 = st.columns(5)
    with c1: st.metric("Total Project", stats["total"])
    with c2: st.metric("Deal", stats["deal"], delta=f"{stats['deal_rate']}% rate")
    with c3: st.metric("Lost", stats["lost"], delta_color="inverse")
    with c4: st.metric("On Progress", stats["in_progress"])
    with c5: st.metric("Deal Rate", f"{stats['deal_rate']}%")

    st.divider()
    c1,c2,c3 = st.columns(3)
    with c1:
        st.metric("💰 Potential Revenue", _fmt(stats["potential_revenue"]))
    with c2:
        st.metric("✅ Revenue Deal", _fmt(stats["deal_revenue"]))
    with c3:
        st.metric("❌ Revenue Lost", _fmt(stats["lost_revenue"]))

    st.divider()
    col1,col2 = st.columns(2)
    with col1:
        st.subheader("📋 Project per Status")
        if stats["by_status"]:
            for k,v in sorted(stats["by_status"].items(), key=lambda x:-x[1]):
                label, color = STATUS_MAP.get(k,(k,"#94a3b8"))
                st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #2d1a45"><span>{_status_badge(k)}</span><span style="font-family:monospace;color:#e2e8f0;font-weight:600">{v}</span></div>', unsafe_allow_html=True)
        else:
            st.info("Belum ada project")
    with col2:
        st.subheader("👤 Top Sales")
        if stats["top_sales"]:
            for name,count in sorted(stats["top_sales"].items(), key=lambda x:-x[1])[:10]:
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #2d1a45"><span style="color:#c4b5d4">{name}</span><span style="font-family:monospace;color:#a855f7;font-weight:600">{count} project</span></div>', unsafe_allow_html=True)
        else:
            st.info("Belum ada data")

# ══════════════════════════════════════════════════════════════════════════════
# KANBAN BOARD (drag & drop)
# ══════════════════════════════════════════════════════════════════════════════
def handle_kanban_query_actions(user):
    """Dipanggil di router sebelum render halaman manapun — proses aksi drag&drop
    atau klik kartu yang dikirim via query param oleh komponen HTML Kanban."""
    qp = st.query_params
    drop_pid = qp.get("crm_drop_pid")
    drop_status = qp.get("crm_drop_status")
    open_pid = qp.get("crm_open_pid")
    changed = False
    if drop_pid and drop_status:
        try:
            if drop_status == "lost":
                st.session_state["show_lost_form"] = True
                st.session_state["crm_project_id"] = int(drop_pid)
                st.session_state["crm_view"] = "detail"
            else:
                update_project_status(int(drop_pid), drop_status, actor=user["full_name"], detail="Dipindahkan via drag & drop Kanban")
        except Exception:
            pass
        del st.query_params["crm_drop_pid"]; del st.query_params["crm_drop_status"]
        changed = True
    if open_pid:
        try:
            st.session_state["crm_project_id"] = int(open_pid)
            st.session_state["crm_view"] = "detail"
        except Exception: pass
        del st.query_params["crm_open_pid"]
        changed = True
    if changed:
        st.rerun()

def render_kanban(user):
    st.title("🗂️ Kanban Board")
    st.caption("Seret (drag) kartu antar kolom untuk mengubah status, atau klik kartu untuk membuka detail.")
    projects = get_my_projects(user)
    if not projects:
        st.info("Belum ada project.")
        return

    # Filter
    col1,col2,col3 = st.columns(3)
    with col1:
        search = st.text_input("🔍 Cari project/customer","",key="kb_search")
    with col2:
        prio_filter = st.selectbox("Prioritas",["Semua","High","Medium","Low"],key="kb_prio")
    with col3:
        status_filter = st.selectbox("Status",["Semua"]+[label for _,label,_ in STATUSES],key="kb_status")

    filtered = projects
    if search:
        filtered = [p for p in filtered if search.lower() in (p.get("customer_name","") or "").lower()
                    or search.lower() in (p.get("project_number","") or "").lower()
                    or search.lower() in (p.get("customer_company","") or "").lower()]
    if prio_filter != "Semua":
        filtered = [p for p in filtered if p.get("priority")==prio_filter]
    if status_filter != "Semua":
        rev_map = {label:k for k,label,_ in STATUSES}
        filtered = [p for p in filtered if p.get("status")==rev_map.get(status_filter,"")]

    # Group by status
    by_status = {k:[] for k,_,_ in STATUSES}
    for p in filtered:
        s = p.get("status","new_request")
        if s in by_status: by_status[s].append(p)

    st.caption(f"Menampilkan {len(filtered)} dari {len(projects)} project")

    import streamlit.components.v1 as components

    def _card_html(p):
        prio = p.get("priority","Medium")
        pcolor = PRIORITY_COLOR.get(prio,"#94a3b8")
        deadline = p.get("deadline","") or "-"
        est = _fmt(p.get("estimated_value",0) or 0)
        cname = (p.get("customer_name","") or "").replace("<","").replace(">","")
        ccomp = (p.get("customer_company","") or "").replace("<","").replace(">","")
        sname = (p.get("sales_name","") or "").replace("<","").replace(">","")
        branch = BRANCH_FULL.get(p.get("branch",""),p.get("branch",""))
        return f"""<div class="kb-card" draggable="true" data-id="{p['id']}" ondragstart="kbDragStart(event)" onclick="kbOpen(event,{p['id']})">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
<span style="color:#6b4f8a;font-size:10px;font-weight:700">{p.get('project_number','')}</span>
<span style="background:{pcolor}22;color:{pcolor};border-radius:6px;padding:1px 6px;font-size:9px;font-weight:700">{prio}</span>
</div>
<div style="color:#e2e8f0;font-weight:600;font-size:13px;margin-bottom:2px">{cname}</div>
<div style="color:#6b4f8a;font-size:11px">{ccomp}</div>
<div style="color:#9d7fba;font-size:11px;margin-top:4px">{sname} | {branch}</div>
<div style="display:flex;justify-content:space-between;margin-top:6px">
<span style="color:#a855f7;font-family:monospace;font-size:12px;font-weight:700">{est}</span>
<span style="color:#4a3060;font-size:10px">📅 {deadline}</span>
</div>
</div>"""

    columns_html = []
    for k,label,color in STATUSES:
        cards = by_status[k]
        cards_html = "".join(_card_html(p) for p in cards) if cards else '<div class="kb-empty">Kosong</div>'
        columns_html.append(f"""
<div class="kb-col" data-status="{k}" ondragover="kbDragOver(event)" ondrop="kbDrop(event)">
<div class="kb-col-head" style="border-color:{color}"><span style="color:{color}">●</span> {label} <span class="kb-count">{len(cards)}</span></div>
<div class="kb-col-body">{cards_html}</div>
</div>""")

    html = f"""
<style>
body,html {{ margin:0; background:transparent; }}
.kb-board {{ display:flex; gap:10px; overflow-x:auto; padding:4px 0 12px 0; font-family:-apple-system,Segoe UI,Roboto,sans-serif; }}
.kb-col {{ background:#130a1e; border:1px solid #2d1a45; border-radius:10px; min-width:220px; max-width:220px; flex-shrink:0; }}
.kb-col-head {{ font-size:12px; font-weight:700; color:#e2e8f0; padding:8px 10px; border-bottom:2px solid; display:flex; justify-content:space-between; align-items:center; }}
.kb-count {{ color:#6b4f8a; font-weight:600; }}
.kb-col-body {{ padding:8px; min-height:80px; max-height:520px; overflow-y:auto; }}
.kb-card {{ background:#180d28; border:1px solid #2d1a4544; border-radius:8px; padding:10px 12px; margin-bottom:8px; cursor:grab; transition:transform .1s; }}
.kb-card:hover {{ border-color:#a855f7; transform:translateY(-1px); }}
.kb-card:active {{ cursor:grabbing; }}
.kb-empty {{ color:#4a3060; font-size:11px; text-align:center; padding:16px 0; }}
.kb-col.dragover {{ background:#1a0d2e; border-color:#a855f7; }}
</style>
<div class="kb-board">
{''.join(columns_html)}
</div>
<script>
function kbDragStart(ev) {{
  ev.dataTransfer.setData("text/plain", ev.currentTarget.getAttribute("data-id"));
  ev.dataTransfer.effectAllowed = "move";
}}
function kbDragOver(ev) {{
  ev.preventDefault();
  ev.currentTarget.classList.add("dragover");
}}
function kbDrop(ev) {{
  ev.preventDefault();
  ev.currentTarget.classList.remove("dragover");
  var pid = ev.dataTransfer.getData("text/plain");
  var status = ev.currentTarget.getAttribute("data-status");
  if (!pid || !status) return;
  window.parent.postMessage({{stKanbanDrop:true, pid:pid, status:status}}, "*");
}}
function kbOpen(ev, pid) {{
  window.parent.postMessage({{stKanbanOpen:true, pid:pid}}, "*");
}}
</script>
"""
    components.html(html, height=600, scrolling=True)

    # Listener top-level (di halaman utama, bukan di dalam iframe) — menerima
    # postMessage dari komponen Kanban lalu melakukan navigasi via query param.
    # Dipasang sekali per sesi browser (guard via window.__stKanbanListenerAdded).
    st.markdown("""<script>
(function(){
  if (window.__stKanbanListenerAdded) return;
  window.__stKanbanListenerAdded = true;
  window.addEventListener("message", function(ev){
    var d = ev.data;
    if (!d) return;
    if (d.stKanbanDrop) {
      var url = new URL(window.location.href);
      url.searchParams.set("crm_drop_pid", d.pid);
      url.searchParams.set("crm_drop_status", d.status);
      window.location.href = url.toString();
    } else if (d.stKanbanOpen) {
      var url = new URL(window.location.href);
      url.searchParams.set("crm_open_pid", d.pid);
      window.location.href = url.toString();
    }
  });
})();
</script>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABLE VIEW
# ══════════════════════════════════════════════════════════════════════════════
def render_table(user):
    st.title("📋 Daftar Project")
    projects = get_my_projects(user)
    if not projects:
        st.info("Belum ada project."); return

    col1,col2,col3 = st.columns(3)
    with col1: search = st.text_input("🔍 Cari","",key="tbl_search")
    with col2: status_f = st.selectbox("Status",["Semua"]+[l for _,l,_ in STATUSES],key="tbl_status")
    with col3: prio_f = st.selectbox("Prioritas",["Semua","High","Medium","Low"],key="tbl_prio")

    filtered = projects
    if search:
        filtered = [p for p in filtered if search.lower() in str(p).lower()]
    if status_f != "Semua":
        rev = {l:k for k,l,_ in STATUSES}
        filtered = [p for p in filtered if p.get("status")==rev.get(status_f,"")]
    if prio_f != "Semua":
        filtered = [p for p in filtered if p.get("priority")==prio_f]

    st.caption(f"{len(filtered)} project")
    for p in filtered:
        label,color = STATUS_MAP.get(p.get("status",""),("","#94a3b8"))
        prio = p.get("priority","Medium")
        pcol = PRIORITY_COLOR.get(prio,"#94a3b8")
        col1,col2 = st.columns([5,1])
        with col1:
            st.markdown(f"""
<div style="background:#180d28;border:0.5px solid #2d1a45;border-left:3px solid {color};border-radius:8px;padding:8px 14px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
<div>
<span style="color:#4a3060;font-size:10px">{p.get('project_number','')}</span>
<span style="background:{color};color:white;border-radius:8px;padding:1px 7px;font-size:10px;font-weight:600;margin-left:8px">{label}</span>
<span style="background:{pcol}22;color:{pcol};border-radius:6px;padding:1px 6px;font-size:10px;font-weight:700;margin-left:4px">{prio}</span>
<div style="color:#e2e8f0;font-weight:600;margin-top:2px">{p.get('customer_name','')} — {p.get('customer_company','') or ''}</div>
<div style="color:#6b4f8a;font-size:11px">{p.get('sales_name','')} | {BRANCH_FULL.get(p.get('branch',''),p.get('branch',''))} | Est: {_fmt(p.get('estimated_value',0) or 0)}</div>
</div>
</div>""", unsafe_allow_html=True)
        with col2:
            if st.button("Buka", key=f"tbl_{p['id']}", use_container_width=True):
                st.session_state["crm_project_id"] = p["id"]
                st.session_state["crm_view"] = "detail"
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# NEW PROJECT FORM
# ══════════════════════════════════════════════════════════════════════════════
def render_new_project(user):
    st.title("➕ Buat Project Baru")
    with st.form("new_project"):
        st.subheader("Data Customer")
        c1,c2 = st.columns(2)
        with c1:
            cust_name = st.text_input("Nama Customer *")
            cust_company = st.text_input("Perusahaan")
            cust_pic = st.text_input("PIC")
        with c2:
            cust_phone = st.text_input("No HP")
            cust_email = st.text_input("Email")

        st.subheader("Data Produk Dicari")
        c1,c2,c3 = st.columns(3)
        with c1:
            brand = st.text_input("Brand")
            part_no = st.text_input("Part Number")
        with c2:
            category = st.text_input("Kategori")
            qty = st.number_input("Qty", min_value=1, value=1)
        with c3:
            budget = st.number_input("Budget Customer (Rp)", min_value=0, value=0, step=100000)
            deadline = st.date_input("Deadline", value=None)

        product_name = st.text_input("Nama Produk *")

        # Knowledge base hint
        if product_name and len(product_name) >= 3:
            kb = search_knowledge_base(product_name)
            if kb:
                st.info("💡 KB: Produk ini pernah EOL. Replacement: " +
                    " | ".join([f"{k['replacement_brand']} {k['replacement_model']}" for k in kb[:2]]))

        cust_notes = st.text_area("Catatan Customer")

        st.subheader("Nilai Project")
        c1,c2 = st.columns(2)
        with c1:
            est_value = st.number_input("Estimasi Nilai Project (Rp)", min_value=0, value=0, step=100000)
        with c2:
            priority = st.selectbox("Prioritas", ["High","Medium","Low"], index=1)

        submitted = st.form_submit_button("🚀 Buat Project", type="primary", use_container_width=True)

    if submitted:
        if not cust_name or not product_name:
            st.error("Nama customer dan nama produk wajib diisi")
            return
        try:
            proj = create_project({
                "customer_name": cust_name,
                "customer_company": cust_company,
                "customer_pic": cust_pic,
                "customer_phone": cust_phone,
                "customer_email": cust_email,
                "branch": user.get("branch",""),
                "branch_name": BRANCH_FULL.get(user.get("branch",""),""),
                "sales_id": user["id"],
                "sales_name": user["full_name"],
                "estimated_value": est_value,
                "priority": priority,
                "deadline": str(deadline) if deadline else None,
            })
            add_product(proj["id"], {
                "brand": brand, "part_number": part_no,
                "category": category, "product_name": product_name,
                "qty": qty, "budget_customer": budget,
                "customer_notes": cust_notes,
            })
            st.success(f"✅ Project {proj['project_number']} berhasil dibuat!")
            st.session_state["crm_project_id"] = proj["id"]
            st.session_state["crm_view"] = "detail"
            st.rerun()
        except Exception as e:
            st.error(f"Gagal: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# PROJECT DETAIL
# ══════════════════════════════════════════════════════════════════════════════
def render_project_detail(user, project_id):
    p = get_project(project_id)
    if not p:
        st.error("Project tidak ditemukan")
        if st.button("← Kembali"): st.session_state["crm_view"]="kanban"; st.rerun()
        return

    # Header
    status_label, status_color = STATUS_MAP.get(p["status"],("","#94a3b8"))
    pcolor = PRIORITY_COLOR.get(p.get("priority","Medium"),"#94a3b8")

    col_back, col_title = st.columns([1,8])
    with col_back:
        if st.button("← Kembali"):
            st.session_state["crm_view"] = "kanban"; st.rerun()

    st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-left:4px solid {status_color};border-radius:10px;padding:14px 18px;margin-bottom:16px">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
<div>
<div style="color:#4a3060;font-size:11px;font-weight:700;margin-bottom:4px">{p.get('project_number','')}</div>
<div style="color:#e2e8f0;font-size:18px;font-weight:700">{p.get('customer_name','')} — {p.get('customer_company','') or ''}</div>
<div style="color:#9d7fba;font-size:12px;margin-top:2px">PIC: {p.get('customer_pic','') or '-'} | HP: {p.get('customer_phone','') or '-'} | Email: {p.get('customer_email','') or '-'}</div>
<div style="color:#6b4f8a;font-size:12px;margin-top:2px">Sales: {p.get('sales_name','')} | Cabang: {BRANCH_FULL.get(p.get('branch',''),p.get('branch',''))}</div>
</div>
<div style="text-align:right">
<div><span style="background:{status_color};color:white;border-radius:12px;padding:3px 12px;font-size:12px;font-weight:600">{status_label}</span></div>
<div style="margin-top:4px"><span style="background:{pcolor}22;color:{pcolor};border-radius:8px;padding:2px 8px;font-size:11px;font-weight:700">{p.get('priority','Medium')}</span></div>
<div style="color:#a855f7;font-family:monospace;font-size:16px;font-weight:700;margin-top:4px">{_fmt(p.get('estimated_value',0) or 0)}</div>
<div style="color:#4a3060;font-size:11px">Deadline: {p.get('deadline','-') or '-'}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)

    # Status changer
    st.markdown("**Ubah Status:**")
    status_keys = [k for k,_,_ in STATUSES]
    cur_idx = status_keys.index(p["status"]) if p["status"] in status_keys else 0
    cols = st.columns(len(STATUSES))
    for i,(k,label,color) in enumerate(STATUSES):
        with cols[i]:
            if k == p["status"]:
                st.markdown(f'<div style="background:{color};color:white;border-radius:6px;padding:4px;text-align:center;font-size:9px;font-weight:700">{label}</div>', unsafe_allow_html=True)
            else:
                if st.button(label[:8], key=f"st_{k}_{project_id}", help=label):
                    if k == "lost" and p["status"] != "lost":
                        st.session_state["show_lost_form"] = True
                    else:
                        update_project_status(project_id, k, actor=user["full_name"])
                        st.rerun()

    # Lost reason form
    if st.session_state.get("show_lost_form"):
        with st.form("lost_form"):
            st.subheader("Alasan Lost")
            reason = st.selectbox("Alasan", LOST_REASONS)
            note = st.text_area("Catatan")
            if st.form_submit_button("Konfirmasi Lost", type="primary"):
                update_project(project_id, {
                    "status":"lost","lost_reason":reason,
                    "lost_note":note,"lost_date":str(date.today())
                }, actor=user["full_name"], action="Project Lost", detail=reason)
                st.session_state["show_lost_form"] = False
                st.rerun()

    st.divider()

    # Tabs
    tab_names = ["📦 Produk","🤝 Follow Up","👥 Supplier","💸 Quotation","📎 Dokumen","📜 Timeline"]
    if can_pm(user): tab_names.insert(1,"🔬 PM Review")
    if p["status"]=="deal":
        tab_names.append("🏆 Deal")
    tabs = st.tabs(tab_names)
    tab_idx = 0

    # Tab Produk
    with tabs[tab_idx]:
        products = get_products(project_id)
        for prod in products:
            avail = prod.get("pm_available","")
            avail_label = {"yes":"✅ Tersedia","no":"❌ Tidak Tersedia","eol":"⚠️ EOL"}.get(avail,"⏳ Belum direview")
            st.markdown(f"""
<div style="background:#130a1e;border:1px solid #2d1a45;border-radius:8px;padding:12px;margin-bottom:8px">
<div style="display:flex;justify-content:space-between">
<div>
<div style="color:#e2e8f0;font-weight:600;font-size:14px">{prod.get('product_name','')}</div>
<div style="color:#6b4f8a;font-size:11px">Brand: {prod.get('brand','-')} | Part#: {prod.get('part_number','-')} | Qty: {prod.get('qty',1)} | Budget: {_fmt(prod.get('budget_customer',0))}</div>
<div style="color:#9d7fba;font-size:11px;margin-top:4px">Catatan: {prod.get('customer_notes','-') or '-'}</div>
</div>
<div style="text-align:right"><span style="font-size:12px">{avail_label}</span></div>
</div>
</div>""", unsafe_allow_html=True)
        if is_leader_up(user) or user["id"]==p.get("sales_id"):
            with st.expander("➕ Tambah Produk"):
                with st.form("add_prod"):
                    c1,c2 = st.columns(2)
                    with c1:
                        pn = st.text_input("Nama Produk *",key="ap_name")
                        pb = st.text_input("Brand",key="ap_brand")
                        pno = st.text_input("Part Number",key="ap_pno")
                    with c2:
                        pc = st.text_input("Kategori",key="ap_cat")
                        pq = st.number_input("Qty",min_value=1,value=1,key="ap_qty")
                        pbg = st.number_input("Budget Customer",min_value=0,value=0,key="ap_budget")
                    pnt = st.text_area("Catatan",key="ap_notes")
                    if st.form_submit_button("Tambah"):
                        if pn:
                            add_product(project_id,{"product_name":pn,"brand":pb,"part_number":pno,"category":pc,"qty":pq,"budget_customer":pbg,"customer_notes":pnt})
                            st.success("Produk ditambahkan"); st.rerun()
    tab_idx += 1

    # Tab PM Review (super_admin only)
    if can_pm(user):
        with tabs[tab_idx]:
            products = get_products(project_id)
            for prod in products:
                st.subheader(f"Review: {prod.get('product_name','')}")
                with st.form(f"pm_review_{prod['id']}"):
                    avail = st.selectbox("Produk masih tersedia?",["yes","no","eol"],
                        index=["yes","no","eol"].index(prod.get("pm_available","yes")) if prod.get("pm_available") in ["yes","no","eol"] else 0,
                        format_func=lambda x:{"yes":"Ya","no":"Tidak","eol":"EOL"}[x])
                    pm_notes = st.text_area("Catatan PM", value=prod.get("pm_notes","") or "")
                    eol_reason=""; eol_status=""
                    if avail=="eol":
                        eol_reason = st.text_input("Alasan EOL", value=prod.get("pm_eol_reason","") or "")
                        eol_status = st.selectbox("Status EOL",["end_of_life","end_of_sale","discontinue"],
                            format_func=lambda x:{"end_of_life":"End of Life","end_of_sale":"End of Sale","discontinue":"Discontinue"}[x])
                    if st.form_submit_button("💾 Simpan Review", type="primary"):
                        update_product(prod["id"],{
                            "pm_available":avail,"pm_notes":pm_notes,
                            "pm_eol_reason":eol_reason,"pm_eol_status":eol_status,
                            "pm_reviewed_at":datetime.utcnow().isoformat()+"Z",
                            "pm_reviewed_by":user["full_name"]
                        })
                        next_status = {"yes":"supplier_sourcing","no":"supplier_sourcing","eol":"eol_verification"}.get(avail,"review_pm")
                        update_project_status(project_id, next_status, actor=user["full_name"],
                            detail=f"Produk tersedia: {avail}")
                        st.success("Review disimpan"); st.rerun()

                # Replacement form jika EOL
                if prod.get("pm_available")=="eol":
                    st.subheader("🔄 Replacement Product")
                    reps = get_replacements(project_id)
                    for r in reps:
                        st.markdown(f"• {r.get('original_model','')} → **{r.get('new_brand','')} {r.get('new_model','')}** ({r.get('performance','')})")
                    with st.expander("➕ Tambah Replacement"):
                        with st.form(f"rep_{prod['id']}"):
                            c1,c2 = st.columns(2)
                            with c1:
                                ob=st.text_input("Brand Asli",value=prod.get("brand",""),key=f"ob_{prod['id']}")
                                om=st.text_input("Model Asli",value=prod.get("product_name",""),key=f"om_{prod['id']}")
                            with c2:
                                nb=st.text_input("Brand Baru",key=f"nb_{prod['id']}")
                                nm=st.text_input("Model Baru",key=f"nm_{prod['id']}")
                            c1,c2=st.columns(2)
                            with c1:
                                perf=st.selectbox("Performa",["Setara","Lebih Tinggi","Lebih Rendah"],key=f"pf_{prod['id']}")
                            with c2:
                                price_chg=st.text_input("Perubahan Harga",key=f"pc_{prod['id']}")
                            rn=st.text_area("Catatan",key=f"rn_{prod['id']}")
                            if st.form_submit_button("Tambah Replacement"):
                                if nb and nm:
                                    add_replacement(project_id,{"original_brand":ob,"original_model":om,"new_brand":nb,"new_model":nm,"performance":perf,"price_change":price_chg,"pm_notes":rn},actor=user["full_name"])
                                    update_project_status(project_id,"replacement",actor=user["full_name"])
                                    st.success("Replacement ditambahkan"); st.rerun()
        tab_idx += 1

    # Tab Follow Up
    with tabs[tab_idx]:
        followups = get_followups(project_id)
        if followups:
            for f in followups:
                media_emoji={"WA":"💬","Telepon":"📞","Email":"📧","Meeting":"🤝"}.get(f.get("media",""),"📌")
                st.markdown(f"""
<div style="background:#130a1e;border-left:3px solid #7c3aed;border-radius:0 8px 8px 0;padding:8px 12px;margin-bottom:6px">
<div style="color:#9d7fba;font-size:10px">{f.get('followup_date','')} {f.get('followup_time','')} {media_emoji} {f.get('media','')}</div>
<div style="color:#c4b5d4;font-size:13px;font-weight:600">{f.get('result','')}</div>
<div style="color:#6b4f8a;font-size:11px">{f.get('notes','') or ''}</div>
{f"<div style='color:#059669;font-size:10px'>Next: {f.get('next_followup','')}</div>" if f.get('next_followup') else ''}
</div>""", unsafe_allow_html=True)
        else:
            st.info("Belum ada follow up")

        if user["id"]==p.get("sales_id") or is_leader_up(user):
            with st.expander("➕ Tambah Follow Up"):
                with st.form("add_fu"):
                    c1,c2=st.columns(2)
                    with c1:
                        fd=st.date_input("Tanggal",value=date.today())
                        ft=st.time_input("Jam",value=datetime.now().time())
                    with c2:
                        media=st.selectbox("Media",MEDIA_OPTS)
                        result=st.selectbox("Hasil",FOLLOWUP_RESULTS)
                    fn=st.text_area("Catatan")
                    nxt=st.date_input("Reminder Follow Up Berikutnya",value=None)
                    if st.form_submit_button("Simpan Follow Up",type="primary"):
                        add_followup(project_id,{"followup_date":str(fd),"followup_time":str(ft),"media":media,"result":result,"notes":fn,"next_followup":str(nxt) if nxt else None,"created_by":user["full_name"]},actor=user["full_name"])
                        if result=="Sudah Deal":
                            update_project_status(project_id,"deal",actor=user["full_name"],detail="Customer deal")
                        st.success("Follow up ditambahkan"); st.rerun()
    tab_idx += 1

    # Tab Supplier (super_admin = buyer)
    with tabs[tab_idx]:
        suppliers = get_suppliers(project_id)
        if suppliers:
            for s in suppliers:
                selected = s.get("is_selected",False)
                border = "#059669" if selected else "#2d1a45"
                badge = " ✅ DIPILIH" if selected else ""
                st.markdown(f"""
<div style="background:#130a1e;border:1px solid {border};border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="display:flex;justify-content:space-between;align-items:center">
<div>
<div style="color:#e2e8f0;font-weight:600">{s.get('supplier_name','')}{badge}</div>
<div style="color:#6b4f8a;font-size:11px">Modal: {_fmt(s.get('price_modal',0))} | Stok: {s.get('stock','?')} | Lead: {s.get('lead_time','-')} | MOQ: {s.get('moq',1)} | Garansi: {s.get('warranty','-')}</div>
<div style="color:#9d7fba;font-size:11px">{s.get('notes','') or ''}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)
                if can_buy(user) and not selected:
                    if st.button(f"Pilih {s['supplier_name']}", key=f"sel_sup_{s['id']}"):
                        select_supplier(project_id, s["id"], actor=user["full_name"])
                        st.rerun()
        else:
            st.info("Belum ada supplier")

        if can_buy(user):
            with st.expander("➕ Tambah Supplier"):
                with st.form("add_sup"):
                    c1,c2=st.columns(2)
                    with c1:
                        sn=st.text_input("Nama Supplier *")
                        pm=st.number_input("Harga Modal (Rp)",min_value=0,value=0,step=10000)
                        stk=st.number_input("Stok",min_value=0,value=0)
                    with c2:
                        lt=st.text_input("Lead Time")
                        moq=st.number_input("MOQ",min_value=1,value=1)
                        grs=st.text_input("Garansi")
                    snt=st.text_area("Catatan")
                    if st.form_submit_button("Tambah Supplier",type="primary"):
                        if sn:
                            add_supplier(project_id,{"supplier_name":sn,"price_modal":pm,"stock":stk,"lead_time":lt,"moq":moq,"warranty":grs,"notes":snt,"added_by":user["full_name"]},actor=user["full_name"])
                            update_project_status(project_id,"waiting_quotation",actor=user["full_name"])
                            st.success("Supplier ditambahkan"); st.rerun()
    tab_idx += 1

    # Tab Quotation
    with tabs[tab_idx]:
        quotations = get_quotations(project_id)
        STATUS_Q={"draft":"📝 Draft","sent":"📤 Sent","revised":"✏️ Revised","approved":"✅ Approved"}
        if quotations:
            for q in quotations:
                qs=STATUS_Q.get(q.get("status","draft"),"📝")
                st.markdown(f"""
<div style="background:#130a1e;border:1px solid #2d1a45;border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="display:flex;justify-content:space-between">
<div>
<div style="color:#9d7fba;font-size:10px">{q.get('quotation_number','')}</div>
<div style="color:#e2e8f0;font-weight:600">{q.get('product_name','')} x{q.get('qty',1)}</div>
<div style="color:#6b4f8a;font-size:11px">Modal: {_fmt(q.get('price_modal',0))} | Jual: {_fmt(q.get('price_sell',0))} | Diskon: {_fmt(q.get('discount',0))} | Total: {_fmt(q.get('total_value',0))}</div>
</div>
<div style="text-align:right">
<div>{qs}</div>
<div style="color:#a855f7;font-family:monospace;font-weight:700">{_fmt(q.get('total_value',0))}</div>
</div>
</div>
</div>""", unsafe_allow_html=True)
                if is_leader_up(user):
                    ca,cb,cc=st.columns(3)
                    with ca:
                        if q.get("status")=="draft" and st.button("Kirim ke Customer",key=f"qsent_{q['id']}"):
                            update_quotation(q["id"],{"status":"sent","sent_at":datetime.utcnow().isoformat()+"Z"},project_id=project_id,actor=user["full_name"])
                            update_project_status(project_id,"quotation_sent",actor=user["full_name"])
                            st.rerun()
                    with cb:
                        if q.get("status")=="sent" and st.button("Mark Negosiasi",key=f"qneg_{q['id']}"):
                            update_project_status(project_id,"negotiation",actor=user["full_name"])
                            st.rerun()
                    with cc:
                        if can_pm(user) and st.button("Approve",key=f"qapv_{q['id']}"):
                            update_quotation(q["id"],{"status":"approved","approved_at":datetime.utcnow().isoformat()+"Z"},project_id=project_id,actor=user["full_name"])
                            st.rerun()
        else:
            st.info("Belum ada quotation")

        if can_buy(user) or is_leader_up(user):
            with st.expander("➕ Buat Quotation"):
                products = get_products(project_id)
                suppliers = get_suppliers(project_id)
                sel_sup = next((s for s in suppliers if s.get("is_selected")), suppliers[0] if suppliers else None)
                with st.form("add_quot"):
                    prod_names=[p["product_name"] for p in products]
                    psel=st.selectbox("Produk",prod_names) if prod_names else st.text_input("Produk")
                    c1,c2=st.columns(2)
                    with c1:
                        qq=st.number_input("Qty",min_value=1,value=1)
                        qm=st.number_input("Harga Modal",min_value=0,value=int(sel_sup.get("price_modal",0)) if sel_sup else 0)
                    with c2:
                        qs=st.number_input("Harga Jual",min_value=0,value=0)
                        qd=st.number_input("Diskon",min_value=0,value=0)
                    margin_pct=round((qs-qm)/qs*100,2) if qs>0 else 0
                    total=(qs-qd)*qq
                    st.info(f"Margin: {margin_pct:.1f}% | Total: {_fmt(total)}")
                    qn=st.text_area("Catatan")
                    if st.form_submit_button("Buat Quotation",type="primary"):
                        create_quotation(project_id,{"product_name":psel if prod_names else psel,"qty":qq,"price_modal":qm,"price_sell":qs,"margin_pct":margin_pct,"discount":qd,"total_value":total,"notes":qn,"created_by":user["full_name"]},actor=user["full_name"])
                        update_project_status(project_id,"waiting_quotation",actor=user["full_name"])
                        st.success("Quotation dibuat"); st.rerun()
    tab_idx += 1

    # Tab Dokumen / Lampiran
    with tabs[tab_idx]:
        docs = get_documents(project_id)
        DOC_CATS = ["Quotation","PO","Foto Produk","Lainnya"]
        if docs:
            for d in docs:
                size_kb = (d.get("file_size",0) or 0)/1024
                col1,col2,col3 = st.columns([4,1,1])
                with col1:
                    st.markdown(f"""
<div style="background:#130a1e;border:1px solid #2d1a45;border-radius:8px;padding:8px 12px;margin-bottom:6px">
<div style="color:#e2e8f0;font-weight:600;font-size:13px">📄 {d.get('file_name','')}</div>
<div style="color:#6b4f8a;font-size:11px">{d.get('category','Lainnya')} | {size_kb:.0f} KB | oleh {d.get('uploaded_by','')} | {(d.get('created_at','') or '')[:16].replace('T',' ')}</div>
</div>""", unsafe_allow_html=True)
                with col2:
                    file_bytes = download_document(d.get("storage_path",""))
                    if file_bytes:
                        st.download_button("⬇️", data=file_bytes, file_name=d.get("file_name","file"),
                                            key=f"dl_doc_{d['id']}", use_container_width=True)
                with col3:
                    if is_leader_up(user) or user["id"]==p.get("sales_id"):
                        if st.button("🗑️", key=f"del_doc_{d['id']}", use_container_width=True):
                            delete_document(d["id"], project_id, d.get("storage_path",""), actor=user["full_name"])
                            st.rerun()
        else:
            st.info("Belum ada dokumen/lampiran")

        with st.expander("➕ Upload Dokumen"):
            with st.form("add_doc"):
                up_files = st.file_uploader("Pilih file (bisa lebih dari satu)", accept_multiple_files=True)
                cat = st.selectbox("Kategori", DOC_CATS)
                if st.form_submit_button("Upload", type="primary"):
                    if up_files:
                        for uf in up_files:
                            add_document(project_id, uf.name, uf.read(), uf.type, cat, user["full_name"])
                        st.success(f"{len(up_files)} file berhasil diupload"); st.rerun()
                    else:
                        st.warning("Pilih minimal satu file")
    tab_idx += 1

    # Tab Timeline
    with tabs[tab_idx]:
        timeline = get_timeline(project_id)
        if not timeline:
            st.info("Belum ada aktivitas")
        else:
            for t in reversed(timeline):
                ts = (t.get("created_at","") or "")[:16].replace("T"," ")
                old_s = t.get("old_status","")
                new_s = t.get("new_status","")
                status_change=""
                if old_s and new_s and old_s!=new_s:
                    ol,oc=STATUS_MAP.get(old_s,(old_s,"#94a3b8"))
                    nl,nc=STATUS_MAP.get(new_s,(new_s,"#94a3b8"))
                    status_change=f'<span style="background:{oc};color:white;border-radius:6px;padding:1px 6px;font-size:9px">{ol}</span> → <span style="background:{nc};color:white;border-radius:6px;padding:1px 6px;font-size:9px">{nl}</span>'
                st.markdown(f"""
<div style="display:flex;gap:10px;padding:6px 0;border-bottom:1px solid #1a0530">
<div style="color:#4a3060;font-size:10px;min-width:120px">{ts}</div>
<div>
<div style="color:#9d7fba;font-size:11px;font-weight:600">{t.get('actor','')} — {t.get('action','')}</div>
{f'<div style="color:#6b4f8a;font-size:10px">{t.get("detail","")}</div>' if t.get('detail') else ''}
{f'<div style="margin-top:2px">{status_change}</div>' if status_change else ''}
</div>
</div>""", unsafe_allow_html=True)

    # Tab Deal
    if p["status"]=="deal" and len(tabs)>tab_idx+1:
        with tabs[tab_idx+1]:
            st.subheader("🏆 Project Deal")
            with st.form("deal_form"):
                deal_val = st.number_input("Nilai Deal Aktual (Rp)", min_value=0,
                    value=int(p.get("deal_value",0) or p.get("estimated_value",0) or 0), step=100000)
                deal_dt = st.date_input("Tanggal Deal", value=date.today())
                if st.form_submit_button("Update Nilai Deal", type="primary"):
                    update_project(project_id, {
                        "deal_value": deal_val,
                        "deal_date": str(deal_dt),
                        "status": "deal"
                    }, actor=user["full_name"], action="Nilai deal diupdate", detail=_fmt(deal_val))
                    st.success("Deal diupdate!")

# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE VIEW
# ══════════════════════════════════════════════════════════════════════════════
def render_knowledge_base(user):
    st.title("🧠 Knowledge Base EOL")
    try:
        from modules.db import _get
        rows = _get("project_knowledge_base", {"select":"*","order":"usage_count.desc","limit":"100"})
    except:
        rows = []
    if not rows:
        st.info("Belum ada data knowledge base. Data akan otomatis terisi saat PM menginput replacement product.")
        return
    search = st.text_input("🔍 Cari produk",key="kb_search2")
    if search:
        rows = [r for r in rows if search.lower() in (r.get("original_model","") or "").lower()
                or search.lower() in (r.get("replacement_model","") or "").lower()]
    st.caption(f"{len(rows)} entri knowledge base")
    for r in rows:
        st.markdown(f"""
<div style="background:#130a1e;border:1px solid #2d1a45;border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="display:flex;justify-content:space-between;align-items:center">
<div>
<span style="color:#dc2626;font-weight:600">{r.get('original_brand','')} {r.get('original_model','')}</span>
<span style="color:#4a3060;margin:0 8px">→</span>
<span style="color:#059669;font-weight:600">{r.get('replacement_brand','')} {r.get('replacement_model','')}</span>
</div>
<span style="color:#a855f7;font-size:11px;font-family:monospace">{r.get('usage_count',1)}x dipakai</span>
</div>
{f"<div style='color:#6b4f8a;font-size:11px;margin-top:4px'>{r.get('reason','')}</div>" if r.get('reason') else ''}
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════
def render_notifications(user):
    st.title("🔔 Notifikasi")
    try:
        generate_notifications()
    except Exception:
        pass
    branch = user.get("branch") if user["role"]=="store_leader" else None
    col1,col2 = st.columns([3,1])
    with col1:
        show_all = st.checkbox("Tampilkan yang sudah dibaca juga", value=False, key="notif_show_all")
    with col2:
        if st.button("✅ Tandai semua dibaca", use_container_width=True):
            mark_all_notifications_read(branch=branch)
            st.rerun()

    notifs = get_notifications(unread_only=not show_all, branch=branch, limit=200)
    if not notifs:
        st.success("Tidak ada notifikasi baru. Semua project dalam kondisi terkontrol.")
        return
    st.caption(f"{len(notifs)} notifikasi")
    TYPE_COLOR = {
        "new_request":"#3b82f6","pm_late":"#f97316","supplier_late":"#06b6d4",
        "quotation_late":"#d97706","followup_late":"#dc2626","deadline_near":"#eab308",
        "po_received":"#6366f1","delivered":"#10b981","closed":"#059669",
    }
    for n in notifs:
        color = TYPE_COLOR.get(n.get("notif_type",""),"#94a3b8")
        label = NOTIF_RULES_LABEL.get(n.get("notif_type",""), n.get("notif_type",""))
        ts = (n.get("created_at","") or "")[:16].replace("T"," ")
        read_badge = " (dibaca)" if n.get("is_read") else ""
        col1,col2 = st.columns([5,1])
        with col1:
            st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-left:3px solid {color};border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="color:{color};font-size:11px;font-weight:700">{label}{read_badge}</div>
<div style="color:#e2e8f0;font-size:13px;margin-top:2px">{n.get('message','')}</div>
<div style="color:#4a3060;font-size:10px;margin-top:2px">{ts}{' | '+BRANCH_FULL.get(n.get('branch',''),n.get('branch','')) if n.get('branch') else ''}</div>
</div>""", unsafe_allow_html=True)
        with col2:
            if not n.get("is_read"):
                if st.button("Selesai", key=f"notif_read_{n['id']}", use_container_width=True):
                    mark_notification_read(n["id"])
                    st.rerun()
            if n.get("project_id"):
                if st.button("Buka", key=f"notif_open_{n['id']}", use_container_width=True):
                    st.session_state["crm_project_id"] = n["project_id"]
                    st.session_state["crm_view"] = "detail"
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# CALENDAR VIEW
# ══════════════════════════════════════════════════════════════════════════════
def render_calendar(user):
    st.title("📅 Calendar View")
    st.caption("Jadwal deadline project dan reminder follow up.")
    projects = get_my_projects(user)
    if not projects:
        st.info("Belum ada project.")
        return

    today = date.today()
    c1,c2 = st.columns(2)
    with c1:
        year = st.selectbox("Tahun", list(range(today.year-1, today.year+2)), index=1, key="cal_year")
    with c2:
        month = st.selectbox("Bulan", list(range(1,13)), index=today.month-1,
                              format_func=lambda m: ["Januari","Februari","Maret","April","Mei","Juni",
                                                      "Juli","Agustus","September","Oktober","November","Desember"][m-1],
                              key="cal_month")

    # Kumpulkan event: deadline project & reminder follow up berikutnya
    events = {}  # day(int) -> list of (label, color, text)
    for p in projects:
        dl = p.get("deadline")
        if dl:
            try:
                d = datetime.fromisoformat(dl).date()
                if d.year==year and d.month==month:
                    events.setdefault(d.day, []).append(("Deadline", "#eab308", f"{p.get('project_number','')} — {p.get('customer_name','')}"))
            except: pass
        try:
            fus = get_followups(p["id"])
        except:
            fus = []
        for f in fus:
            nxt = f.get("next_followup")
            if nxt:
                try:
                    d = datetime.fromisoformat(nxt).date()
                    if d.year==year and d.month==month:
                        events.setdefault(d.day, []).append(("Follow Up", "#a855f7", f"{p.get('project_number','')} — {p.get('customer_name','')}"))
                except: pass

    import calendar as _cal
    cal_matrix = _cal.Calendar(firstweekday=0).monthdayscalendar(year, month)
    day_names = ["Sen","Sel","Rab","Kam","Jum","Sab","Min"]

    rows_html = ""
    for week in cal_matrix:
        cells = ""
        for d in week:
            if d == 0:
                cells += '<div class="cal-cell cal-empty"></div>'
            else:
                is_today = (d==today.day and month==today.month and year==today.year)
                evs = events.get(d, [])
                ev_html = "".join(f'<div class="cal-ev" style="background:{c}22;color:{c};border:1px solid {c}44">{lbl}: {txt}</div>' for lbl,c,txt in evs[:3])
                more = f'<div class="cal-more">+{len(evs)-3} lagi</div>' if len(evs)>3 else ""
                cells += f'<div class="cal-cell{" cal-today" if is_today else ""}"><div class="cal-daynum">{d}</div>{ev_html}{more}</div>'
        rows_html += f'<div class="cal-row">{cells}</div>'

    head_html = "".join(f'<div class="cal-head">{dn}</div>' for dn in day_names)

    html = f"""
<style>
body,html {{ margin:0; background:transparent; font-family:-apple-system,Segoe UI,Roboto,sans-serif; }}
.cal-grid {{ display:flex; flex-direction:column; gap:4px; }}
.cal-row {{ display:grid; grid-template-columns:repeat(7,1fr); gap:4px; }}
.cal-head {{ color:#6b4f8a; font-size:11px; font-weight:700; text-align:center; padding:4px 0; }}
.cal-cell {{ background:#130a1e; border:1px solid #2d1a45; border-radius:6px; min-height:70px; padding:4px; font-size:10px; }}
.cal-empty {{ background:transparent; border:none; }}
.cal-today {{ border-color:#a855f7; box-shadow:0 0 0 1px #a855f7; }}
.cal-daynum {{ color:#9d7fba; font-weight:700; font-size:11px; margin-bottom:2px; }}
.cal-ev {{ border-radius:4px; padding:1px 4px; margin-bottom:2px; font-size:9px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.cal-more {{ color:#4a3060; font-size:9px; }}
</style>
<div class="cal-grid">
<div class="cal-row">{head_html}</div>
{rows_html}
</div>
"""
    import streamlit.components.v1 as components
    components.html(html, height=520, scrolling=True)
    st.caption("🟡 Deadline project · 🟣 Reminder follow up")

# ══════════════════════════════════════════════════════════════════════════════
# TIMELINE VIEW (Gantt-ish, cross-project)
# ══════════════════════════════════════════════════════════════════════════════
def render_timeline_view(user):
    st.title("📈 Timeline View")
    st.caption("Durasi tiap project dari dibuat hingga status terkini/selesai.")
    projects = get_my_projects(user)
    if not projects:
        st.info("Belum ada project.")
        return

    active_only = st.checkbox("Hanya project yang masih berjalan", value=True, key="tlv_active_only")
    if active_only:
        projects = [p for p in projects if p.get("status") not in ("deal","lost")]
    if not projects:
        st.info("Tidak ada project untuk ditampilkan.")
        return

    def _parse(dt_str):
        try: return datetime.fromisoformat((dt_str or "").replace("Z",""))
        except: return None

    rows = []
    now = datetime.utcnow()
    for p in projects:
        start = _parse(p.get("created_at")) or now
        end = _parse(p.get("deal_date")) or _parse(p.get("lost_date")) or now
        if end < start: end = start
        rows.append((p, start, end))

    if not rows:
        st.info("Tidak ada data.")
        return

    min_start = min(r[1] for r in rows)
    max_end = max(r[2] for r in rows)
    total_span = max((max_end - min_start).total_seconds(), 3600)

    bars_html = ""
    for p, start, end in sorted(rows, key=lambda r: r[1]):
        label, color = STATUS_MAP.get(p.get("status",""), ("", "#94a3b8"))
        left_pct = (start - min_start).total_seconds() / total_span * 100
        width_pct = max((end - start).total_seconds() / total_span * 100, 0.8)
        cname = (p.get("customer_name","") or "")
        bars_html += f"""
<div class="tl-row">
<div class="tl-label">{p.get('project_number','')} — {cname[:22]}</div>
<div class="tl-track"><div class="tl-bar" style="left:{left_pct:.2f}%;width:{width_pct:.2f}%;background:{color}"><span class="tl-bar-label">{label}</span></div></div>
</div>"""

    html = f"""
<style>
body,html {{ margin:0; background:transparent; font-family:-apple-system,Segoe UI,Roboto,sans-serif; }}
.tl-row {{ display:flex; align-items:center; gap:8px; margin-bottom:6px; }}
.tl-label {{ width:220px; flex-shrink:0; color:#c4b5d4; font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.tl-track {{ position:relative; flex:1; height:22px; background:#130a1e; border:1px solid #2d1a45; border-radius:6px; }}
.tl-bar {{ position:absolute; top:2px; bottom:2px; border-radius:4px; display:flex; align-items:center; padding:0 6px; overflow:hidden; }}
.tl-bar-label {{ color:white; font-size:9px; font-weight:700; white-space:nowrap; }}
</style>
<div>{bars_html}</div>
"""
    import streamlit.components.v1 as components
    components.html(html, height=min(40*len(rows)+40, 650), scrolling=True)
