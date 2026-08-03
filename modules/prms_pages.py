# PRMS — Project Request (multi-produk per request) — UI
import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
from modules.prms_db import (
    ITEM_STATUSES, ITEM_STATUS_MAP, ITEM_TERMINAL,
    REQUEST_STATUSES, REQUEST_STATUS_MAP, URGENCY_COLOR,
    create_request, submit_request, get_request, get_requests, get_items, get_item,
    get_history, get_item_queue,
    store_leader_approve, store_leader_reject,
    pm_product_found, pm_replacement, pm_unable_to_source,
    purchasing_ready, store_leader_forward, sales_deal, sales_no_deal,
    get_notifications, mark_notification_read, mark_all_notifications_read,
    get_master, add_master, update_master, delete_master,
    get_dashboard_stats,
)
from modules.config import ALL_BRANCHES, BRANCH_FULL

NODEAL_REASONS_FALLBACK = ["Harga terlalu mahal","Customer batal beli","Customer membeli di tempat lain",
                            "Barang terlalu lama datang","Produk tidak sesuai","Customer tidak jadi rakit",
                            "Budget kurang","Spesifikasi berubah","Lainnya"]

# ── Role helpers ──────────────────────────────────────────────────────────────
def is_sales(u):     return u["role"] in ("sales",)
def is_leader(u):    return u["role"] in ("store_leader","area_manager","super_admin")
def is_pm(u):        return u["role"] in ("product_manager","super_admin")
def is_purchasing(u):return u["role"] in ("admin_purchasing","super_admin")
def is_view_only(u): return u["role"] == "management"
def can_manage_master(u): return u["role"] == "super_admin"

def _my_scope(user):
    if user["role"] == "sales":
        return user.get("branch"), user["id"]
    if user["role"] == "store_leader":
        return user.get("branch"), None
    return None, None

def _item_badge(status):
    label, color = ITEM_STATUS_MAP.get(status, (status, "#94a3b8"))
    return f'<span style="background:{color}22;color:{color};border:1px solid {color}55;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:700">{label}</span>'

def _req_badge(status):
    label, color = REQUEST_STATUS_MAP.get(status, (status, "#94a3b8"))
    return f'<span style="background:{color}22;color:{color};border:1px solid {color}55;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:700">{label}</span>'

def _fmt(n):
    try: return f"Rp {int(n):,}".replace(",", ".")
    except: return "Rp 0"

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def render_dashboard(user):
    st.title("📦 Project Request")
    branch, _ = _my_scope(user)
    stats = get_dashboard_stats(branch=branch)

    cards = [
        ("Total Request", stats["total"], "#a855f7"),
        ("Total Produk", stats["total_items"], "#6366f1"),
        ("Waiting Approval", stats["waiting_approval"], "#3b82f6"),
        ("Waiting PM", stats["waiting_pm"], "#8b5cf6"),
        ("Waiting Purchasing", stats["waiting_purchasing"], "#06b6d4"),
        ("Ready to Offer", stats["ready_to_offer"], "#eab308"),
        ("Deal", stats["deal"], "#22c55e"),
        ("No Deal", stats["no_deal"], "#ef4444"),
        ("Replacement / EOL Product", stats["replacement"], "#f97316"),
    ]
    cols = st.columns(3)
    for i, (label, val, color) in enumerate(cards):
        with cols[i % 3]:
            st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-left:3px solid {color};border-radius:10px;padding:14px 16px;margin-bottom:12px">
<div style="color:#9d7fba;font-size:11px;font-weight:600">{label}</div>
<div style="color:{color};font-size:26px;font-weight:800">{val}</div>
</div>""", unsafe_allow_html=True)

    st.divider()
    st.subheader("📊 Analytics")
    reqs, items = stats["rows"], stats["items"]
    if not reqs:
        st.info("Belum ada data request untuk dianalisis.")
        return
    rdf = pd.DataFrame(reqs)
    rdf["created_at"] = pd.to_datetime(rdf["created_at"], errors="coerce")
    rdf["month"] = rdf["created_at"].dt.strftime("%Y-%m")
    idf = pd.DataFrame(items) if items else pd.DataFrame(columns=["product_name","brand","status"])

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Request per Bulan")
        st.bar_chart(rdf.groupby("month").size())
    with c2:
        st.caption("Produk berdasarkan Status")
        if len(idf):
            labels = idf["status"].map(lambda s: ITEM_STATUS_MAP.get(s, (s, ""))[0])
            st.bar_chart(labels.value_counts())
        else:
            st.caption("Belum ada data")

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Top Requested Product")
        if len(idf): st.bar_chart(idf["product_name"].value_counts().head(10))
        else: st.caption("Belum ada data")
    with c2:
        st.caption("Top Brand")
        if len(idf) and idf["brand"].notna().any():
            st.bar_chart(idf["brand"].value_counts().head(10))
        else:
            st.caption("Belum ada data")

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Request per Cabang")
        st.bar_chart(rdf["branch"].value_counts())
    with c2:
        st.caption("Request per Sales")
        st.bar_chart(rdf["sales_name"].value_counts().head(10))

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Deal Rate", f"{stats['deal_rate']}%")
    with c2: st.metric("No Deal Rate", f"{stats['nodeal_rate']}%")
    with c3:
        closed = rdf[rdf["status"] == "completed"].copy()
        if len(closed):
            avg_days = round((pd.to_datetime(closed["updated_at"], errors="coerce") - closed["created_at"]).dt.total_seconds().mean()/86400, 1)
            st.metric("Avg. Processing Time", f"{avg_days} hari" if avg_days == avg_days else "-")
        else:
            st.metric("Avg. Processing Time", "-")

# ══════════════════════════════════════════════════════════════════════════════
# NEW REQUEST (Sales) — keranjang multi-produk
# ══════════════════════════════════════════════════════════════════════════════
def render_new_request(user):
    st.title("➕ Buat Project Request")
    user_branch = user.get("branch") or ""
    sel_branch = user_branch
    if not user_branch:
        st.info("Akun Bapak tidak terikat ke satu cabang — pilih cabang untuk request ini.")
        sel_branch = st.selectbox("Cabang *", ALL_BRANCHES, format_func=lambda c: f"{c} — {BRANCH_FULL.get(c,c)}", key="pr_branch")

    brands = [b["name"] for b in get_master("brand")]
    cats = [c["name"] for c in get_master("category")]

    if "pr_cart" not in st.session_state:
        st.session_state["pr_cart"] = [{"product_name":"","brand":"","part_number":"","category":"",
                                         "qty":1,"budget_customer":0,"ref_link":"","urgency":"Medium"}]

    st.subheader("Data Customer")
    c1, c2 = st.columns(2)
    with c1:
        cust_name = st.text_input("Nama Customer *", key="pr_cust_name")
        req_date = st.date_input("Tanggal", value=date.today(), key="pr_date")
    with c2:
        note = st.text_area("Catatan Customer (untuk seluruh request)", key="pr_note")

    st.subheader("🛒 Produk Diminta")
    cart = st.session_state["pr_cart"]
    for i, item in enumerate(cart):
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                item["product_name"] = st.text_input(f"Nama Produk * (#{i+1})", value=item["product_name"], key=f"pn_{i}")
                item["brand"] = (st.selectbox("Brand", [""]+brands, index=([""]+brands).index(item["brand"]) if item["brand"] in brands else 0, key=f"br_{i}")
                                  if brands else st.text_input("Brand", value=item["brand"], key=f"br_{i}"))
            with c2:
                item["part_number"] = st.text_input("Part Number", value=item["part_number"], key=f"pnn_{i}")
                item["category"] = (st.selectbox("Kategori", [""]+cats, index=([""]+cats).index(item["category"]) if item["category"] in cats else 0, key=f"ct_{i}")
                                     if cats else st.text_input("Kategori", value=item["category"], key=f"ct_{i}"))
            with c3:
                item["qty"] = st.number_input("Qty", min_value=1, value=int(item["qty"]), step=1, key=f"qt_{i}")
                item["budget_customer"] = st.number_input("Budget Customer (Rp)", min_value=0, value=int(item["budget_customer"]), step=100000, key=f"bg_{i}")
            c1, c2 = st.columns(2)
            with c1: item["ref_link"] = st.text_input("Link Referensi (Opsional)", value=item["ref_link"], key=f"rl_{i}")
            with c2: item["urgency"] = st.selectbox("Tingkat Urgensi", ["Low","Medium","High"],
                                                      index=["Low","Medium","High"].index(item["urgency"]), key=f"ur_{i}")
            if len(cart) > 1:
                if st.button("🗑️ Hapus produk ini", key=f"rm_{i}"):
                    cart.pop(i); st.rerun()

    if st.button("➕ Tambah Produk Lain"):
        cart.append({"product_name":"","brand":"","part_number":"","category":"",
                     "qty":1,"budget_customer":0,"ref_link":"","urgency":"Medium"})
        st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        save_draft = st.button("💾 Simpan Draft", use_container_width=True)
    with c2:
        submit = st.button("📤 Submit ke Store Leader", type="primary", use_container_width=True)

    if save_draft or submit:
        if not cust_name:
            st.error("Nama customer wajib diisi"); return
        if not sel_branch:
            st.error("Cabang wajib dipilih"); return
        valid_items = [it for it in cart if it["product_name"].strip()]
        if not valid_items:
            st.error("Minimal 1 produk dengan nama produk wajib diisi"); return

        items_payload = [{
            "product_name": it["product_name"], "brand": it["brand"] or None,
            "part_number": it["part_number"] or None, "category": it["category"] or None,
            "qty": int(it["qty"]), "budget_customer": float(it["budget_customer"]),
            "ref_link": it["ref_link"] or None, "urgency": it["urgency"],
        } for it in valid_items]

        req = create_request({
            "customer_name": cust_name, "branch": sel_branch, "branch_name": BRANCH_FULL.get(sel_branch,""),
            "sales_id": user["id"], "sales_name": user["full_name"], "request_date": str(req_date),
            "customer_note": note or None,
        }, items_payload, submit=submit)

        st.session_state["pr_cart"] = [{"product_name":"","brand":"","part_number":"","category":"",
                                         "qty":1,"budget_customer":0,"ref_link":"","urgency":"Medium"}]
        if submit:
            st.success(f"Request {req['request_number']} ({len(items_payload)} produk) berhasil disubmit ke Store Leader")
        else:
            st.success(f"Request {req['request_number']} ({len(items_payload)} produk) disimpan sebagai draft")
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# DAFTAR / ANTRIAN
# ══════════════════════════════════════════════════════════════════════════════
QUEUE_ITEM_STATUS = {
    "pm_review":        ["waiting_product_review"],
    "purchasing_queue": ["product_found","replacement_suggested"],
    "leader_check":     ["store_leader_check"],
    "sales_offer":      ["sales_offer"],
}

def render_request_list(user, status_filter=None, title="📋 Daftar Request"):
    """List di level REQUEST (dipakai untuk: Draft Saya, Approval Request, Semua Request)."""
    st.title(title)
    branch, sales_id = _my_scope(user)
    reqs = get_requests(branch=branch, sales_id=sales_id, status=status_filter, limit=2000)

    with st.expander("🔍 Filter", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1: f_branch = st.selectbox("Cabang", ["Semua"]+ALL_BRANCHES, key=f"rf_branch_{title}")
        with c2: f_status = st.selectbox("Status Request", ["Semua"]+[l for _,l,_ in REQUEST_STATUSES], key=f"rf_status_{title}")
        with c3: f_search = st.text_input("Cari (customer/no. request)", key=f"rf_search_{title}")

    if f_branch != "Semua": reqs = [r for r in reqs if r.get("branch")==f_branch]
    if f_status != "Semua":
        rev = {l:k for k,l,_ in REQUEST_STATUSES}
        reqs = [r for r in reqs if r.get("status")==rev.get(f_status)]
    if f_search:
        s = f_search.lower()
        reqs = [r for r in reqs if s in (r.get("customer_name","") or "").lower() or s in (r.get("request_number","") or "").lower()]

    st.caption(f"{len(reqs)} request")
    if not reqs:
        st.info("Tidak ada request."); return

    for r in reqs:
        items = get_items(r["id"])
        c1, c2 = st.columns([5,1])
        with c1:
            item_badges = " ".join(_item_badge(it["status"]) for it in items[:4])
            more = f' <span style="color:#4a3060;font-size:10px">+{len(items)-4} lagi</span>' if len(items)>4 else ""
            st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="color:#6b4f8a;font-size:11px;font-weight:700">{r.get('request_number','')}</span>
{_req_badge(r.get('status',''))}
</div>
<div style="color:#e2e8f0;font-weight:600;font-size:14px;margin-top:2px">{r.get('customer_name','')} — {len(items)} produk</div>
<div style="color:#9d7fba;font-size:12px;margin-top:2px">{r.get('sales_name','')} | {BRANCH_FULL.get(r.get('branch',''),r.get('branch',''))}</div>
<div style="margin-top:6px">{item_badges}{more}</div>
</div>""", unsafe_allow_html=True)
        with c2:
            if st.button("Buka", key=f"open_req_{title}_{r['id']}", use_container_width=True):
                st.session_state["prms_request_id"] = r["id"]
                st.session_state["prms_view"] = "detail"
                st.rerun()

def render_item_queue(user, queue, title):
    """List di level ITEM (dipakai untuk: Review Produk, Antrian Purchasing, Store Leader Check, Sales Offer)."""
    st.title(title)
    branch, sales_id = _my_scope(user)
    items = get_item_queue(QUEUE_ITEM_STATUS[queue], branch=branch, sales_id=sales_id)

    with st.expander("🔍 Filter", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1: f_branch = st.selectbox("Cabang", ["Semua"]+ALL_BRANCHES, key=f"if_branch_{queue}")
        with c2: f_urgency = st.selectbox("Urgency", ["Semua","Low","Medium","High"], key=f"if_urg_{queue}")
        with c3: f_search = st.text_input("Cari (customer/produk/no. request)", key=f"if_search_{queue}")

    if f_branch != "Semua": items = [i for i in items if i.get("branch")==f_branch]
    if f_urgency != "Semua": items = [i for i in items if i.get("urgency")==f_urgency]
    if f_search:
        s = f_search.lower()
        items = [i for i in items if s in (i.get("customer_name","") or "").lower()
                 or s in (i.get("product_name","") or "").lower()
                 or s in (i.get("request_number","") or "").lower()]

    st.caption(f"{len(items)} produk")
    if not items:
        st.info("Tidak ada produk dalam antrian ini."); return

    for it in items:
        ucolor = URGENCY_COLOR.get(it.get("urgency","Medium"), "#94a3b8")
        c1, c2 = st.columns([5,1])
        with c1:
            st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="color:#6b4f8a;font-size:11px;font-weight:700">{it.get('request_number','')}</span>
{_item_badge(it.get('status',''))}
</div>
<div style="color:#e2e8f0;font-weight:600;font-size:14px;margin-top:2px">{it.get('product_name','')} — {it.get('customer_name','')}</div>
<div style="color:#9d7fba;font-size:12px;margin-top:2px">{it.get('brand') or '-'} | {it.get('sales_name','')} | {BRANCH_FULL.get(it.get('branch',''),it.get('branch',''))}
<span style="color:{ucolor};font-weight:700"> · {it.get('urgency','')}</span></div>
</div>""", unsafe_allow_html=True)
        with c2:
            if st.button("Buka", key=f"open_item_{queue}_{it['id']}", use_container_width=True):
                st.session_state["prms_request_id"] = it["request_id"]
                st.session_state["prms_view"] = "detail"
                st.session_state["prms_focus_item"] = it["id"]
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# DETAIL REQUEST + AKSI PER PRODUK
# ══════════════════════════════════════════════════════════════════════════════
def render_detail(user):
    rid = st.session_state.get("prms_request_id")
    r = get_request(rid) if rid else None
    if not r:
        st.warning("Request tidak ditemukan.")
        return

    if st.button("← Kembali"):
        st.session_state["prms_view"] = "list"
        st.session_state.pop("prms_focus_item", None)
        st.rerun()

    st.title(f"{r.get('request_number','')} — {r.get('customer_name','')}")
    st.markdown(_req_badge(r.get("status","")), unsafe_allow_html=True)
    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Customer**"); st.write(r.get("customer_name","-"))
        st.markdown("**Cabang**"); st.write(BRANCH_FULL.get(r.get("branch",""), r.get("branch","-")))
    with c2:
        st.markdown("**Sales**"); st.write(r.get("sales_name","-"))
        st.markdown("**Tanggal**"); st.write(r.get("request_date","-"))
    with c3:
        items = get_items(rid)
        st.markdown("**Jumlah Produk**"); st.write(len(items))
    if r.get("customer_note"): st.markdown(f"**Catatan Customer:** {r['customer_note']}")

    st.divider()
    status = r.get("status")

    # ── Sales: submit draft (seluruh request) ───────────────────────────────
    if status == "draft" and (is_sales(user) and r.get("sales_id")==user["id"] or user["role"]=="super_admin"):
        st.subheader("📤 Submit Request")
        if st.button("Submit ke Store Leader", type="primary"):
            submit_request(rid, user["full_name"])
            st.success("Request disubmit"); st.rerun()

    # ── Store Leader review (seluruh request, sekali untuk semua produk) ────
    elif status == "submitted" and is_leader(user):
        st.subheader("🔎 Store Leader Review — seluruh request")
        st.caption(f"Menyetujui/menolak berlaku untuk semua {len(items)} produk di request ini.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Approve Semua Produk", type="primary", use_container_width=True):
                store_leader_approve(rid, user["full_name"]); st.success("Disetujui"); st.rerun()
        with c2:
            with st.popover("❌ Reject", use_container_width=True):
                reason = st.text_area("Alasan Reject *", key="reject_reason")
                if st.button("Konfirmasi Reject"):
                    if not reason:
                        st.error("Alasan wajib diisi")
                    else:
                        store_leader_reject(rid, user["full_name"], reason)
                        st.success("Request ditolak"); st.rerun()

    elif status == "rejected":
        st.error(f"Request ini ditolak. Alasan: {r.get('reject_reason','-')}")

    elif status in ("in_progress", "completed"):
        if status == "completed":
            st.success("✅ Semua produk pada request ini sudah selesai diproses.")
        st.subheader(f"🛒 Produk ({len(items)})")

    st.divider()

    # ── Kartu aksi per PRODUK (hanya tampil kalau request sudah in_progress/completed) ──
    if status in ("in_progress", "completed"):
        for it in items:
            with st.expander(f"{it.get('product_name','')}  ·  {ITEM_STATUS_MAP.get(it['status'],(it['status'],''))[0]}", expanded=True):
                _render_item_card(user, it)

    st.divider()
    st.subheader("📜 History")
    hist = get_history(rid)
    if not hist:
        st.caption("Belum ada riwayat.")
    for h in hist:
        ts = (h.get("created_at","") or "")[:16].replace("T"," ")
        st.markdown(f"""
<div style="background:#130a1e;border-left:2px solid #a855f7;border-radius:6px;padding:6px 12px;margin-bottom:4px">
<span style="color:#6b4f8a;font-size:11px">{ts}</span> — <span style="color:#e2e8f0;font-size:13px;font-weight:600">{h.get('actor','')}</span>: <span style="color:#c4b5d4;font-size:13px">{h.get('action','')}</span>
{f'<div style="color:#9d7fba;font-size:12px;margin-top:2px">{h.get("note","")}</div>' if h.get('note') else ''}
</div>""", unsafe_allow_html=True)

def _render_item_card(user, it):
    item_id = it["id"]; status = it["status"]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption(f"Brand: {it.get('brand') or '-'} | Part No: {it.get('part_number') or '-'}")
        st.caption(f"Kategori: {it.get('category') or '-'}")
    with c2:
        st.caption(f"Qty: {it.get('qty','-')}  |  Budget: {_fmt(it.get('budget_customer',0))}")
        uc = URGENCY_COLOR.get(it.get("urgency","Medium"),"#94a3b8")
        st.markdown(f'Urgensi: <span style="color:{uc};font-weight:700">{it.get("urgency","-")}</span>', unsafe_allow_html=True)
    with c3:
        if it.get("ref_link"): st.caption(f"Referensi: {it['ref_link']}")

    # 3. PM review
    if status == "waiting_product_review" and is_pm(user):
        choice = st.radio("Hasil Review", ["Produk Ready","Produk EOL (End Of Life)","Produk Tidak Ditemukan"], key=f"pm_choice_{item_id}")
        if choice == "Produk Ready":
            suppliers = [s["name"] for s in get_master("supplier")]
            with st.form(f"pm_ready_form_{item_id}"):
                supplier = st.selectbox("Supplier", suppliers) if suppliers else st.text_input("Supplier")
                c1, c2 = st.columns(2)
                with c1: cost = st.number_input("Harga Modal (Rp)", min_value=0, step=10000); eta = st.text_input("Estimasi Datang")
                with c2: sell = st.number_input("Harga Jual (Rp)", min_value=0, step=10000); stock = st.text_input("Stock Supplier")
                if st.form_submit_button("✅ Simpan — Product Found", type="primary"):
                    pm_product_found(item_id, user["full_name"], supplier, cost, sell, eta, stock)
                    st.success("Produk ditandai ready"); st.rerun()
        elif choice == "Produk EOL (End Of Life)":
            with st.form(f"pm_eol_form_{item_id}"):
                c1, c2 = st.columns(2)
                with c1:
                    rname = st.text_input("Nama Produk Pengganti *"); rbrand = st.text_input("Brand"); rpn = st.text_input("Part Number")
                with c2:
                    rspec = st.text_area("Spesifikasi"); rreason = st.text_area("Alasan Penggantian")
                c1, c2 = st.columns(2)
                with c1: rprice = st.number_input("Harga (Rp)", min_value=0, step=10000)
                with c2: rdiff = st.number_input("Selisih Harga (Rp)", step=10000)
                if st.form_submit_button("🔁 Simpan — Replacement Suggested", type="primary"):
                    if not rname: st.error("Nama produk pengganti wajib diisi")
                    else:
                        pm_replacement(item_id, user["full_name"], rname, rbrand, rpn, rspec, rreason, rprice, rdiff)
                        st.success("Produk pengganti diusulkan"); st.rerun()
        else:
            with st.form(f"pm_unable_form_{item_id}"):
                reason = st.text_area("Alasan *")
                if st.form_submit_button("🚫 Simpan — Unable to Source", type="primary"):
                    if not reason: st.error("Alasan wajib diisi")
                    else:
                        pm_unable_to_source(item_id, user["full_name"], reason)
                        st.success("Ditandai tidak ditemukan"); st.rerun()

    # 4. Admin Purchasing
    elif status in ("product_found","replacement_suggested") and is_purchasing(user):
        if status == "product_found":
            st.info(f"Supplier PM: {it.get('pm_supplier','-')} | Modal: {_fmt(it.get('pm_cost_price',0))} | Jual: {_fmt(it.get('pm_sell_price',0))}")
        else:
            st.info(f"Produk pengganti: {it.get('repl_product_name','-')} ({it.get('repl_brand','-')})")
        suppliers = [s["name"] for s in get_master("supplier")]
        with st.form(f"purchasing_form_{item_id}"):
            supplier = st.selectbox("Supplier", suppliers) if suppliers else st.text_input("Supplier")
            c1, c2 = st.columns(2)
            with c1: stock = st.text_input("Stock"); price = st.number_input("Harga (Rp)", min_value=0, step=10000)
            with c2: eta = st.text_input("ETA"); po = st.text_input("Nomor PO (Opsional)")
            if st.form_submit_button("📦 Ready for Sales", type="primary"):
                purchasing_ready(item_id, user["full_name"], supplier, stock, eta, price, po)
                st.success("Ditandai siap — menunggu pengecekan Store Leader"); st.rerun()

    # 5. Store Leader check → forward to sales
    elif status == "store_leader_check" and is_leader(user):
        st.info(f"Purchasing — Supplier: {it.get('pur_supplier','-')} | Harga: {_fmt(it.get('pur_price',0))} | ETA: {it.get('pur_eta','-')} | Stock: {it.get('pur_stock','-')}")
        if st.button("➡️ Forward to Sales", type="primary", key=f"fwd_{item_id}"):
            store_leader_forward(item_id, user["full_name"])
            st.success("Diteruskan ke Sales"); st.rerun()

    # 6. Sales offer: Deal / No Deal
    elif status == "sales_offer" and (is_sales(user) or user["role"]=="super_admin"):
        price_ref = it.get("pur_price") or it.get("pm_sell_price") or it.get("repl_price") or 0
        st.info(f"Harga referensi: {_fmt(price_ref)}")
        tab1, tab2 = st.tabs(["✅ Deal","❌ No Deal"])
        with tab1:
            with st.form(f"deal_form_{item_id}"):
                c1, c2, c3 = st.columns(3)
                with c1: dqty = st.number_input("Qty Deal", min_value=1, value=int(it.get("qty") or 1))
                with c2: dprice = st.number_input("Harga Deal (Rp)", min_value=0, value=int(price_ref), step=10000)
                with c3: dclose = st.date_input("Estimasi Closing", value=date.today())
                if st.form_submit_button("🏆 Simpan — Won", type="primary"):
                    sales_deal(item_id, user["full_name"], dqty, dprice, dclose)
                    st.success("Deal! 🎉"); st.rerun()
        with tab2:
            reasons = [x["reason"] for x in get_master("nodeal_reason")] or NODEAL_REASONS_FALLBACK
            with st.form(f"nodeal_form_{item_id}"):
                reason = st.selectbox("Alasan No Deal", reasons)
                note = st.text_area("Keterangan *") if reason == "Lainnya" else ""
                if st.form_submit_button("❌ Simpan — Lost", type="primary"):
                    if reason == "Lainnya" and not note: st.error("Keterangan wajib diisi untuk alasan Lainnya")
                    else:
                        sales_no_deal(item_id, user["full_name"], reason, note)
                        st.warning("Ditandai No Deal"); st.rerun()

    elif status == "won":
        st.success(f"🏆 Won — Qty: {it.get('deal_qty')} | Harga: {_fmt(it.get('deal_price',0))} | Est. Closing: {it.get('deal_est_closing','-')}")
    elif status == "lost":
        st.error(f"❌ Lost — Alasan: {it.get('nodeal_reason','-')}" + (f" — {it.get('nodeal_note')}" if it.get('nodeal_note') else ""))
    elif status == "unable_to_source":
        st.warning(f"🚫 Unable to Source — Alasan: {it.get('unable_reason','-')}")
    else:
        st.caption("Menunggu proses dari pihak terkait — tidak ada aksi untuk role Bapak saat ini pada produk ini.")

# ══════════════════════════════════════════════════════════════════════════════
# NOTIFIKASI
# ══════════════════════════════════════════════════════════════════════════════
def render_notifications(user):
    st.title("🔔 Notifikasi")
    role = user["role"]; branch = user.get("branch")
    c1, c2 = st.columns([3,1])
    with c1: show_all = st.checkbox("Tampilkan yang sudah dibaca", value=False)
    with c2:
        if st.button("✅ Tandai semua dibaca", use_container_width=True):
            mark_all_notifications_read(role=role, branch=branch); st.rerun()

    notifs = get_notifications(role=role, branch=branch, unread_only=not show_all)
    if not notifs:
        st.success("Tidak ada notifikasi baru."); return
    st.caption(f"{len(notifs)} notifikasi")
    for n in notifs:
        ts = (n.get("created_at","") or "")[:16].replace("T"," ")
        c1, c2 = st.columns([5,1])
        with c1:
            st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-left:3px solid #a855f7;border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="color:#e2e8f0;font-size:13px">{n.get('message','')}</div>
<div style="color:#4a3060;font-size:10px;margin-top:2px">{ts}</div>
</div>""", unsafe_allow_html=True)
        with c2:
            if not n.get("is_read"):
                if st.button("Selesai", key=f"prms_notif_{n['id']}", use_container_width=True):
                    mark_notification_read(n["id"]); st.rerun()
            if n.get("request_id"):
                if st.button("Buka", key=f"prms_notif_open_{n['id']}", use_container_width=True):
                    st.session_state["prms_request_id"] = n["request_id"]
                    st.session_state["prms_view"] = "detail"
                    if n.get("item_id"): st.session_state["prms_focus_item"] = n["item_id"]
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MASTER DATA
# ══════════════════════════════════════════════════════════════════════════════
MASTER_LABELS = {"brand":"Brand","category":"Kategori","supplier":"Supplier",
                  "reject_reason":"Alasan Reject","nodeal_reason":"Alasan No Deal"}

def render_master_data(user):
    st.title("🗄️ Master Data")
    if not can_manage_master(user):
        st.warning("Hanya Super Admin yang dapat mengelola master data.")
        return
    kind = st.selectbox("Pilih Master Data", list(MASTER_LABELS.keys()), format_func=lambda k: MASTER_LABELS[k])
    field = "reason" if kind in ("reject_reason","nodeal_reason") else "name"

    items = get_master(kind, active_only=False)
    st.caption(f"{len(items)} data")
    for it in items:
        c1, c2, c3 = st.columns([4,1,1])
        with c1:
            active = "🟢" if it.get("is_active", True) else "⚪"
            extra = f" — {it.get('contact')}" if kind=="supplier" and it.get("contact") else ""
            st.write(f"{active} {it.get(field,'')}{extra}")
        with c2:
            if st.button("Nonaktifkan" if it.get("is_active",True) else "Aktifkan", key=f"tgl_{kind}_{it['id']}", use_container_width=True):
                update_master(kind, it["id"], {"is_active": not it.get("is_active", True)}); st.rerun()
        with c3:
            if st.button("🗑️", key=f"del_{kind}_{it['id']}", use_container_width=True):
                delete_master(kind, it["id"]); st.rerun()

    with st.expander(f"➕ Tambah {MASTER_LABELS[kind]}"):
        with st.form(f"add_{kind}"):
            val = st.text_input(MASTER_LABELS[kind])
            contact = st.text_input("Kontak") if kind == "supplier" else None
            if st.form_submit_button("Tambah", type="primary"):
                if val:
                    payload = {field: val, "is_active": True}
                    if kind == "supplier": payload["contact"] = contact
                    add_master(kind, payload); st.success("Berhasil ditambahkan"); st.rerun()
                else:
                    st.warning("Isi datanya dulu")

# ══════════════════════════════════════════════════════════════════════════════
# REPORT / EXPORT
# ══════════════════════════════════════════════════════════════════════════════
def render_reports(user):
    st.title("📑 Laporan")
    branch, _ = _my_scope(user)
    reqs = get_requests(branch=branch, limit=5000)
    if not reqs:
        st.info("Belum ada data."); return

    all_items = []
    for req in reqs:
        for it in get_items(req["id"]):
            row = dict(it)
            row["request_number"] = req.get("request_number"); row["customer_name"] = req.get("customer_name")
            row["branch"] = req.get("branch"); row["sales_name"] = req.get("sales_name")
            row["request_date"] = req.get("request_date")
            all_items.append(row)
    if not all_items:
        st.info("Belum ada produk yang tercatat di request manapun (request masih Draft/belum ada item).")
        return
    idf = pd.DataFrame(all_items)
    idf["status_label"] = idf["status"].map(lambda s: ITEM_STATUS_MAP.get(s,(s,""))[0])

    st.subheader("Filter Laporan")
    c1, c2 = st.columns(2)
    with c1: d_from = st.date_input("Dari tanggal", value=None, key="rep_from")
    with c2: d_to = st.date_input("Sampai tanggal", value=None, key="rep_to")
    if d_from: idf = idf[pd.to_datetime(idf["request_date"]) >= pd.to_datetime(str(d_from))]
    if d_to: idf = idf[pd.to_datetime(idf["request_date"]) <= pd.to_datetime(str(d_to))]

    st.dataframe(idf[["request_number","request_date","branch","sales_name","customer_name",
                       "product_name","brand","status_label","urgency"]], use_container_width=True, hide_index=True)

    st.subheader("Ringkasan Laporan")
    per_branch = idf.groupby("branch").size().rename("Jumlah").reset_index()
    per_sales = idf.groupby("sales_name").size().rename("Jumlah").reset_index()
    per_month = idf.assign(month=pd.to_datetime(idf["request_date"]).dt.strftime("%Y-%m")).groupby("month").size().rename("Jumlah").reset_index()
    deal_vs_nodeal = idf[idf["status"].isin(["won","lost"])].groupby("status").size().rename("Jumlah").reset_index()
    eol_df = idf[idf["repl_product_name"].notna()][["request_number","product_name","repl_product_name","repl_brand","repl_reason"]]
    supplier_perf = idf[idf["pur_supplier"].notna()].groupby("pur_supplier").size().rename("Jumlah Request").reset_index()

    c1, c2 = st.columns(2)
    with c1: st.caption("Request per Cabang"); st.dataframe(per_branch, use_container_width=True, hide_index=True)
    with c2: st.caption("Request per Sales"); st.dataframe(per_sales, use_container_width=True, hide_index=True)

    st.subheader("⬇️ Export")
    c1, c2, c3 = st.columns(3)
    with c1:
        csv = idf.to_csv(index=False).encode("utf-8")
        st.download_button("📄 Download CSV", data=csv, file_name="project_request_report.csv", mime="text/csv", use_container_width=True)
    with c2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            idf.to_excel(writer, sheet_name="Produk", index=False)
            per_branch.to_excel(writer, sheet_name="Per Cabang", index=False)
            per_sales.to_excel(writer, sheet_name="Per Sales", index=False)
            per_month.to_excel(writer, sheet_name="Per Bulan", index=False)
            deal_vs_nodeal.to_excel(writer, sheet_name="Deal vs No Deal", index=False)
            eol_df.to_excel(writer, sheet_name="Produk EOL & Pengganti", index=False)
            supplier_perf.to_excel(writer, sheet_name="Supplier Performance", index=False)
        st.download_button("📊 Download Excel", data=buf.getvalue(), file_name="project_request_report.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with c3:
        if st.button("📕 Generate PDF", use_container_width=True):
            pdf = _build_report_pdf(idf, user)
            st.download_button("📥 Download PDF", data=pdf, file_name="project_request_report.pdf", mime="application/pdf", use_container_width=True)

def _build_report_pdf(df, user):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elems = [Paragraph("Laporan Project Request", styles["Title"]),
             Paragraph(f"Digenerate: {datetime.now().strftime('%d %B %Y %H:%M')} oleh {user['full_name']}", styles["Normal"]),
             Spacer(1, 12)]
    cols = ["request_number","customer_name","product_name","status","branch"]
    data = [["No. Request","Customer","Produk","Status","Cabang"]] + df[cols].astype(str).values.tolist()[:200]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#a855f7")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey),
    ]))
    elems.append(t)
    doc.build(elems)
    return buf.getvalue()
