# PRMS — Product Request Management System (UI)
import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
from modules.prms_db import (
    STATUSES, STATUS_MAP, URGENCY_COLOR,
    create_request, submit_request, get_request, get_requests, get_history,
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
def is_view_only(u):  return u["role"] == "management"
def can_manage_master(u): return u["role"] == "super_admin"

def _my_scope(user):
    """(branch, sales_id) filter berdasarkan role — None berarti tidak difilter."""
    if user["role"] == "sales":
        return user.get("branch"), user["id"]
    if user["role"] == "store_leader":
        return user.get("branch"), None
    return None, None  # PM, purchasing, super_admin, area_manager, management → lihat semua

def _badge(status):
    label, color = STATUS_MAP.get(status, (status, "#94a3b8"))
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
        ("Waiting Approval", stats["waiting_approval"], "#3b82f6"),
        ("Waiting PM", stats["waiting_pm"], "#8b5cf6"),
        ("Waiting Purchasing", stats["waiting_purchasing"], "#06b6d4"),
        ("Ready to Offer", stats["ready_to_offer"], "#eab308"),
        ("Deal", stats["deal"], "#22c55e"),
        ("No Deal", stats["no_deal"], "#ef4444"),
        ("Replacement Product", stats["replacement"], "#a855f7"),
        ("EOL Product", stats["eol"], "#f97316"),
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
    rows = stats["rows"]
    if not rows:
        st.info("Belum ada data request untuk dianalisis.")
        return
    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["month"] = df["created_at"].dt.strftime("%Y-%m")

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Request per Bulan")
        st.bar_chart(df.groupby("month").size())
    with c2:
        st.caption("Request berdasarkan Status")
        labels = df["status"].map(lambda s: STATUS_MAP.get(s, (s, ""))[0])
        st.bar_chart(labels.value_counts())

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Top Requested Product")
        st.bar_chart(df["product_name"].value_counts().head(10))
    with c2:
        st.caption("Top Brand")
        if "brand" in df and df["brand"].notna().any():
            st.bar_chart(df["brand"].value_counts().head(10))
        else:
            st.caption("Belum ada data")

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Request per Cabang")
        st.bar_chart(df["branch"].value_counts())
    with c2:
        st.caption("Request per Sales")
        st.bar_chart(df["sales_name"].value_counts().head(10))

    c1, c2, c3 = st.columns(3)
    total_closed = stats["deal"] + stats["no_deal"]
    with c1: st.metric("Deal Rate", f"{stats['deal_rate']}%")
    with c2: st.metric("No Deal Rate", f"{stats['nodeal_rate']}%")
    with c3:
        closed = df[df["status"].isin(["won","lost"])].copy()
        if len(closed):
            closed["dur"] = (closed["created_at"] - df["created_at"].min()).dt.days
            avg_days = round((pd.to_datetime(closed["updated_at"], errors="coerce") - closed["created_at"]).dt.total_seconds().mean()/86400, 1)
            st.metric("Avg. Processing Time", f"{avg_days} hari" if avg_days == avg_days else "-")
        else:
            st.metric("Avg. Processing Time", "-")

# ══════════════════════════════════════════════════════════════════════════════
# NEW REQUEST (Sales)
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

    with st.form("prms_new_request"):
        st.subheader("Data Customer")
        c1, c2 = st.columns(2)
        with c1:
            cust_name = st.text_input("Nama Customer *")
            req_date = st.date_input("Tanggal", value=date.today())
        with c2:
            urgency = st.selectbox("Tingkat Urgensi", ["Low","Medium","High"], index=1)

        st.subheader("Data Produk")
        c1, c2, c3 = st.columns(3)
        with c1:
            product_name = st.text_input("Nama Produk *")
            brand = st.selectbox("Brand", [""] + brands) if brands else st.text_input("Brand")
        with c2:
            part_number = st.text_input("Part Number")
            category = st.selectbox("Kategori", [""] + cats) if cats else st.text_input("Kategori")
        with c3:
            qty = st.number_input("Qty", min_value=1, value=1, step=1)
            budget = st.number_input("Budget Customer (Rp)", min_value=0, value=0, step=100000)

        ref_link = st.text_input("Link Referensi (Opsional)")
        note = st.text_area("Catatan Customer")

        c1, c2 = st.columns(2)
        with c1:
            save_draft = st.form_submit_button("💾 Simpan Draft", use_container_width=True)
        with c2:
            submit = st.form_submit_button("📤 Submit ke Store Leader", type="primary", use_container_width=True)

    if save_draft or submit:
        if not cust_name or not product_name:
            st.error("Nama customer dan nama produk wajib diisi")
            return
        if not sel_branch:
            st.error("Cabang wajib dipilih")
            return
        req = create_request({
            "customer_name": cust_name, "branch": sel_branch, "branch_name": BRANCH_FULL.get(sel_branch,""),
            "sales_id": user["id"], "sales_name": user["full_name"], "request_date": str(req_date),
            "product_name": product_name, "brand": brand or None, "part_number": part_number or None,
            "category": category or None, "qty": int(qty), "budget_customer": float(budget),
            "ref_link": ref_link or None, "customer_note": note or None, "urgency": urgency,
        }, submit=submit)
        if submit:
            st.success(f"Request {req['request_number']} berhasil disubmit ke Store Leader")
        else:
            st.success(f"Request {req['request_number']} disimpan sebagai draft")
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# LIST / INBOX + FILTER
# ══════════════════════════════════════════════════════════════════════════════
QUEUE_STATUS = {
    "sales_draft":     ("draft",),
    "leader_review":   ("submitted",),
    "pm_review":       ("waiting_product_review",),
    "purchasing_queue":("product_found","replacement_suggested"),
    "leader_check":    ("store_leader_check",),
    "sales_offer":     ("sales_offer",),
}

def render_list(user, queue=None, title="📋 Daftar Request"):
    st.title(title)
    branch, sales_id = _my_scope(user)
    reqs = get_requests(branch=branch, sales_id=sales_id, limit=2000)
    if queue:
        allowed = QUEUE_STATUS[queue]
        reqs = [r for r in reqs if r.get("status") in allowed]

    with st.expander("🔍 Filter", expanded=False):
        c1,c2,c3,c4 = st.columns(4)
        with c1:
            f_branch = st.selectbox("Cabang", ["Semua"]+ALL_BRANCHES, key=f"f_branch_{queue}")
        with c2:
            f_status = st.selectbox("Status", ["Semua"]+[l for _,l,_ in STATUSES], key=f"f_status_{queue}")
        with c3:
            f_urgency = st.selectbox("Urgency", ["Semua","Low","Medium","High"], key=f"f_urg_{queue}")
        with c4:
            f_search = st.text_input("Cari (customer/produk/no. request)", key=f"f_search_{queue}")
        c1,c2 = st.columns(2)
        with c1:
            f_brand = st.text_input("Brand", key=f"f_brand_{queue}")
        with c2:
            f_cat = st.text_input("Kategori", key=f"f_cat_{queue}")

    if f_branch != "Semua": reqs = [r for r in reqs if r.get("branch")==f_branch]
    if f_status != "Semua":
        rev = {l:k for k,l,_ in STATUSES}
        reqs = [r for r in reqs if r.get("status")==rev.get(f_status)]
    if f_urgency != "Semua": reqs = [r for r in reqs if r.get("urgency")==f_urgency]
    if f_brand: reqs = [r for r in reqs if f_brand.lower() in (r.get("brand") or "").lower()]
    if f_cat: reqs = [r for r in reqs if f_cat.lower() in (r.get("category") or "").lower()]
    if f_search:
        s = f_search.lower()
        reqs = [r for r in reqs if s in (r.get("customer_name","") or "").lower()
                or s in (r.get("product_name","") or "").lower()
                or s in (r.get("request_number","") or "").lower()]

    st.caption(f"{len(reqs)} request")
    if not reqs:
        st.info("Tidak ada request.")
        return

    for r in reqs:
        ucolor = URGENCY_COLOR.get(r.get("urgency","Medium"), "#94a3b8")
        c1, c2 = st.columns([5,1])
        with c1:
            st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="color:#6b4f8a;font-size:11px;font-weight:700">{r.get('request_number','')}</span>
{_badge(r.get('status',''))}
</div>
<div style="color:#e2e8f0;font-weight:600;font-size:14px;margin-top:2px">{r.get('product_name','')} — {r.get('customer_name','')}</div>
<div style="color:#9d7fba;font-size:12px;margin-top:2px">{r.get('brand') or '-'} | {r.get('sales_name','')} | {BRANCH_FULL.get(r.get('branch',''),r.get('branch',''))}
<span style="color:{ucolor};font-weight:700"> · {r.get('urgency','')}</span></div>
</div>""", unsafe_allow_html=True)
        with c2:
            if st.button("Buka", key=f"open_{queue}_{r['id']}", use_container_width=True):
                st.session_state["prms_request_id"] = r["id"]
                st.session_state["prms_view"] = "detail"
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# DETAIL + AKSI WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════
def render_detail(user):
    rid = st.session_state.get("prms_request_id")
    r = get_request(rid) if rid else None
    if not r:
        st.warning("Request tidak ditemukan.")
        return

    if st.button("← Kembali"):
        st.session_state["prms_view"] = "list"
        st.rerun()

    st.title(f"{r.get('request_number','')} — {r.get('product_name','')}")
    st.markdown(_badge(r.get("status","")), unsafe_allow_html=True)
    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Customer**")
        st.write(r.get("customer_name","-"))
        st.markdown("**Cabang**")
        st.write(BRANCH_FULL.get(r.get("branch",""), r.get("branch","-")))
        st.markdown("**Sales**")
        st.write(r.get("sales_name","-"))
    with c2:
        st.markdown("**Produk**")
        st.write(f"{r.get('product_name','-')}  \nBrand: {r.get('brand') or '-'}  \nPart No: {r.get('part_number') or '-'}")
        st.markdown("**Kategori**")
        st.write(r.get("category") or "-")
    with c3:
        st.markdown("**Qty**"); st.write(r.get("qty","-"))
        st.markdown("**Budget Customer**"); st.write(_fmt(r.get("budget_customer",0)))
        st.markdown("**Urgensi**")
        uc = URGENCY_COLOR.get(r.get("urgency","Medium"),"#94a3b8")
        st.markdown(f'<span style="color:{uc};font-weight:700">{r.get("urgency","-")}</span>', unsafe_allow_html=True)

    if r.get("ref_link"): st.markdown(f"**Link Referensi:** {r['ref_link']}")
    if r.get("customer_note"): st.markdown(f"**Catatan Customer:** {r['customer_note']}")

    st.divider()
    status = r.get("status")

    # ── 1. Sales: submit draft ──────────────────────────────────────────────
    if status == "draft" and (is_sales(user) and r.get("sales_id")==user["id"] or user["role"]=="super_admin"):
        st.subheader("📤 Submit Request")
        if st.button("Submit ke Store Leader", type="primary"):
            submit_request(rid, user["full_name"])
            st.success("Request disubmit"); st.rerun()

    # ── 2. Store Leader review ──────────────────────────────────────────────
    elif status == "submitted" and is_leader(user):
        st.subheader("🔎 Store Leader Review")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Approve", type="primary", use_container_width=True):
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

    # ── 3. PM / Super Admin review ──────────────────────────────────────────
    elif status == "waiting_product_review" and is_pm(user):
        st.subheader("🔬 Product Manager Review")
        choice = st.radio("Hasil Review", ["Produk Ready","Produk EOL (End Of Life)","Produk Tidak Ditemukan"], key="pm_choice")
        if choice == "Produk Ready":
            suppliers = [s["name"] for s in get_master("supplier")]
            with st.form("pm_ready_form"):
                supplier = st.selectbox("Supplier", suppliers) if suppliers else st.text_input("Supplier")
                c1, c2 = st.columns(2)
                with c1:
                    cost = st.number_input("Harga Modal (Rp)", min_value=0, step=10000)
                    eta = st.text_input("Estimasi Datang")
                with c2:
                    sell = st.number_input("Harga Jual (Rp)", min_value=0, step=10000)
                    stock = st.text_input("Stock Supplier")
                if st.form_submit_button("✅ Simpan — Product Found", type="primary"):
                    pm_product_found(rid, user["full_name"], supplier, cost, sell, eta, stock)
                    st.success("Produk ditandai ready"); st.rerun()
        elif choice == "Produk EOL (End Of Life)":
            with st.form("pm_eol_form"):
                st.caption("Produk Pengganti")
                c1, c2 = st.columns(2)
                with c1:
                    rname = st.text_input("Nama Produk Pengganti *")
                    rbrand = st.text_input("Brand")
                    rpn = st.text_input("Part Number")
                with c2:
                    rspec = st.text_area("Spesifikasi")
                    rreason = st.text_area("Alasan Penggantian")
                c1, c2 = st.columns(2)
                with c1: rprice = st.number_input("Harga (Rp)", min_value=0, step=10000)
                with c2: rdiff = st.number_input("Selisih Harga (Rp)", step=10000)
                if st.form_submit_button("🔁 Simpan — Replacement Suggested", type="primary"):
                    if not rname:
                        st.error("Nama produk pengganti wajib diisi")
                    else:
                        pm_replacement(rid, user["full_name"], rname, rbrand, rpn, rspec, rreason, rprice, rdiff)
                        st.success("Produk pengganti diusulkan"); st.rerun()
        else:
            with st.form("pm_unable_form"):
                reason = st.text_area("Alasan *")
                if st.form_submit_button("🚫 Simpan — Unable to Source", type="primary"):
                    if not reason:
                        st.error("Alasan wajib diisi")
                    else:
                        pm_unable_to_source(rid, user["full_name"], reason)
                        st.success("Ditandai tidak ditemukan"); st.rerun()

    # ── 4. Admin Purchasing ─────────────────────────────────────────────────
    elif status in ("product_found","replacement_suggested") and is_purchasing(user):
        st.subheader("📦 Admin Purchasing")
        if status == "product_found":
            st.info(f"Supplier PM: {r.get('pm_supplier','-')} | Modal: {_fmt(r.get('pm_cost_price',0))} | Jual: {_fmt(r.get('pm_sell_price',0))}")
        else:
            st.info(f"Produk pengganti: {r.get('repl_product_name','-')} ({r.get('repl_brand','-')})")
        suppliers = [s["name"] for s in get_master("supplier")]
        with st.form("purchasing_form"):
            supplier = st.selectbox("Supplier", suppliers, index=0 if suppliers else None) if suppliers else st.text_input("Supplier")
            c1, c2 = st.columns(2)
            with c1:
                stock = st.text_input("Stock"); price = st.number_input("Harga (Rp)", min_value=0, step=10000)
            with c2:
                eta = st.text_input("ETA"); po = st.text_input("Nomor PO (Opsional)")
            if st.form_submit_button("📦 Ready for Sales", type="primary"):
                purchasing_ready(rid, user["full_name"], supplier, stock, eta, price, po)
                st.success("Ditandai siap — menunggu pengecekan Store Leader"); st.rerun()

    # ── 5. Store Leader check → forward to sales ────────────────────────────
    elif status == "store_leader_check" and is_leader(user):
        st.subheader("🔎 Store Leader Check")
        st.info(f"Purchasing — Supplier: {r.get('pur_supplier','-')} | Harga: {_fmt(r.get('pur_price',0))} | ETA: {r.get('pur_eta','-')} | Stock: {r.get('pur_stock','-')}")
        if st.button("➡️ Forward to Sales", type="primary"):
            store_leader_forward(rid, user["full_name"])
            st.success("Diteruskan ke Sales"); st.rerun()

    # ── 6. Sales offer: Deal / No Deal ──────────────────────────────────────
    elif status == "sales_offer" and (is_sales(user) or user["role"]=="super_admin"):
        st.subheader("💬 Sales Offer")
        price_ref = r.get("pur_price") or r.get("pm_sell_price") or r.get("repl_price") or 0
        st.info(f"Harga referensi: {_fmt(price_ref)}")
        tab1, tab2 = st.tabs(["✅ Deal","❌ No Deal"])
        with tab1:
            with st.form("deal_form"):
                c1, c2, c3 = st.columns(3)
                with c1: dqty = st.number_input("Qty Deal", min_value=1, value=int(r.get("qty") or 1))
                with c2: dprice = st.number_input("Harga Deal (Rp)", min_value=0, value=int(price_ref), step=10000)
                with c3: dclose = st.date_input("Estimasi Closing", value=date.today())
                if st.form_submit_button("🏆 Simpan — Won", type="primary"):
                    sales_deal(rid, user["full_name"], dqty, dprice, dclose)
                    st.success("Deal! 🎉"); st.rerun()
        with tab2:
            reasons = [x["reason"] for x in get_master("nodeal_reason")] or NODEAL_REASONS_FALLBACK
            with st.form("nodeal_form"):
                reason = st.selectbox("Alasan No Deal", reasons)
                note = ""
                if reason == "Lainnya":
                    note = st.text_area("Keterangan *")
                if st.form_submit_button("❌ Simpan — Lost", type="primary"):
                    if reason == "Lainnya" and not note:
                        st.error("Keterangan wajib diisi untuk alasan Lainnya")
                    else:
                        sales_no_deal(rid, user["full_name"], reason, note)
                        st.warning("Ditandai No Deal"); st.rerun()

    elif status in ("won","lost","rejected","unable_to_source"):
        st.success("Request ini sudah selesai (final).") if status=="won" else st.info("Request ini sudah ditutup.")
        if status=="won":
            st.write(f"Qty: {r.get('deal_qty')} | Harga: {_fmt(r.get('deal_price',0))} | Est. Closing: {r.get('deal_est_closing','-')}")
        elif status=="lost":
            st.write(f"Alasan: {r.get('nodeal_reason','-')}" + (f" — {r.get('nodeal_note')}" if r.get('nodeal_note') else ""))
        elif status=="rejected":
            st.write(f"Alasan: {r.get('reject_reason','-')}")
        elif status=="unable_to_source":
            st.write(f"Alasan: {r.get('unable_reason','-')}")
    else:
        st.caption("Menunggu proses dari pihak terkait — tidak ada aksi untuk role Bapak saat ini.")

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

# ══════════════════════════════════════════════════════════════════════════════
# NOTIFIKASI
# ══════════════════════════════════════════════════════════════════════════════
def render_notifications(user):
    st.title("🔔 Notifikasi")
    role = user["role"]; branch = user.get("branch")
    c1, c2 = st.columns([3,1])
    with c1:
        show_all = st.checkbox("Tampilkan yang sudah dibaca", value=False)
    with c2:
        if st.button("✅ Tandai semua dibaca", use_container_width=True):
            mark_all_notifications_read(role=role, branch=branch); st.rerun()

    notifs = get_notifications(role=role, branch=branch, unread_only=not show_all)
    if not notifs:
        st.success("Tidak ada notifikasi baru.")
        return
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
    is_reason = kind in ("reject_reason","nodeal_reason")
    field = "reason" if is_reason else "name"

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
                update_master(kind, it["id"], {"is_active": not it.get("is_active", True)})
                st.rerun()
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
                    add_master(kind, payload)
                    st.success("Berhasil ditambahkan"); st.rerun()
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
        st.info("Belum ada data.")
        return
    df = pd.DataFrame(reqs)
    df["status_label"] = df["status"].map(lambda s: STATUS_MAP.get(s,(s,""))[0])

    st.subheader("Filter Laporan")
    c1, c2 = st.columns(2)
    with c1: d_from = st.date_input("Dari tanggal", value=None, key="rep_from")
    with c2: d_to = st.date_input("Sampai tanggal", value=None, key="rep_to")
    if d_from: df = df[pd.to_datetime(df["request_date"]) >= pd.to_datetime(str(d_from))]
    if d_to: df = df[pd.to_datetime(df["request_date"]) <= pd.to_datetime(str(d_to))]

    st.dataframe(df[["request_number","request_date","branch","sales_name","customer_name",
                      "product_name","brand","status_label","urgency"]], use_container_width=True, hide_index=True)

    st.subheader("Ringkasan Laporan")
    per_branch = df.groupby("branch").size().rename("Jumlah").reset_index()
    per_sales = df.groupby("sales_name").size().rename("Jumlah").reset_index()
    per_month = df.assign(month=pd.to_datetime(df["request_date"]).dt.strftime("%Y-%m")).groupby("month").size().rename("Jumlah").reset_index()
    deal_vs_nodeal = df[df["status"].isin(["won","lost"])].groupby("status").size().rename("Jumlah").reset_index()
    eol_df = df[df["repl_product_name"].notna()][["request_number","product_name","repl_product_name","repl_brand","repl_reason"]]
    supplier_perf = df[df["pur_supplier"].notna()].groupby("pur_supplier").size().rename("Jumlah Request").reset_index()

    c1, c2 = st.columns(2)
    with c1: st.caption("Request per Cabang"); st.dataframe(per_branch, use_container_width=True, hide_index=True)
    with c2: st.caption("Request per Sales"); st.dataframe(per_sales, use_container_width=True, hide_index=True)

    # Export
    st.subheader("⬇️ Export")
    c1, c2, c3 = st.columns(3)
    with c1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📄 Download CSV", data=csv, file_name="prms_report.csv", mime="text/csv", use_container_width=True)
    with c2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Request", index=False)
            per_branch.to_excel(writer, sheet_name="Per Cabang", index=False)
            per_sales.to_excel(writer, sheet_name="Per Sales", index=False)
            per_month.to_excel(writer, sheet_name="Per Bulan", index=False)
            deal_vs_nodeal.to_excel(writer, sheet_name="Deal vs No Deal", index=False)
            eol_df.to_excel(writer, sheet_name="Produk EOL & Pengganti", index=False)
            supplier_perf.to_excel(writer, sheet_name="Supplier Performance", index=False)
        st.download_button("📊 Download Excel", data=buf.getvalue(), file_name="prms_report.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with c3:
        if st.button("📕 Generate PDF", use_container_width=True):
            pdf = _build_report_pdf(df, user)
            st.download_button("📥 Download PDF", data=pdf, file_name="prms_report.pdf", mime="application/pdf", use_container_width=True)

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
