# PC Request — UI (Custom PC Build Request)
import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
from modules.pcreq_db import (
    STATUSES, STATUS_MAP, CATEGORIES, NODEAL_REASONS,
    create_request, submit_request, get_request, get_requests, get_extras, update_extra,
    get_history, purchasing_save, store_leader_set_price, store_leader_reject,
    sales_deal, sales_no_deal, get_notifications, mark_notification_read,
    mark_all_notifications_read, get_dashboard_stats,
)
from modules.config import ALL_BRANCHES, BRANCH_FULL

def is_sales(u):      return u["role"] in ("sales",)
def is_leader(u):     return u["role"] in ("store_leader","area_manager","super_admin")
def is_purchasing(u): return u["role"] in ("admin_purchasing","super_admin")

def _my_scope(user):
    if user["role"] == "sales":
        return user.get("branch"), user["id"]
    if user["role"] == "store_leader":
        return user.get("branch"), None
    return None, None

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
    st.title("🖥️ PC Request")
    st.caption("Custom PC build / pemesanan khusus di luar stok")
    branch, _ = _my_scope(user)
    stats = get_dashboard_stats(branch=branch)

    cards = [
        ("Total Request", stats["total"], "#a855f7"),
        ("Waiting Purchasing", stats["submitted"], "#06b6d4"),
        ("Waiting Leader Check", stats["store_leader_check"], "#f59e0b"),
        ("Ready to Offer", stats["sales_offer"], "#eab308"),
        ("Deal", stats["won"], "#22c55e"),
        ("No Deal", stats["lost"], "#ef4444"),
    ]
    cols = st.columns(3)
    for i,(label,val,color) in enumerate(cards):
        with cols[i%3]:
            st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-left:3px solid {color};border-radius:10px;padding:14px 16px;margin-bottom:12px">
<div style="color:#9d7fba;font-size:11px;font-weight:600">{label}</div>
<div style="color:{color};font-size:26px;font-weight:800">{val}</div>
</div>""", unsafe_allow_html=True)

    st.divider()
    reqs = stats["rows"]
    if not reqs:
        st.info("Belum ada PC Request."); return
    df = pd.DataFrame(reqs)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["month"] = df["created_at"].dt.strftime("%Y-%m")
    c1,c2 = st.columns(2)
    with c1:
        st.caption("Request per Bulan"); st.bar_chart(df.groupby("month").size())
    with c2:
        st.caption("Request per Cabang"); st.bar_chart(df["branch"].value_counts())
    st.metric("Deal Rate", f"{stats['deal_rate']}%")

# ══════════════════════════════════════════════════════════════════════════════
# NEW REQUEST (Sales / Store Leader)
# ══════════════════════════════════════════════════════════════════════════════
def render_new_request(user):
    st.title("➕ Buat PC Request")
    user_branch = user.get("branch") or ""
    sel_branch = user_branch
    if not user_branch:
        st.info("Akun Bapak tidak terikat ke satu cabang — pilih cabang untuk request ini.")
        sel_branch = st.selectbox("Cabang *", ALL_BRANCHES, format_func=lambda c: f"{c} — {BRANCH_FULL.get(c,c)}", key="pcr_branch")

    if "pcr_extras" not in st.session_state:
        st.session_state["pcr_extras"] = []

    st.subheader("Data Customer")
    c1,c2 = st.columns(2)
    with c1:
        cust_name = st.text_input("Nama Customer *", key="pcr_cust")
        req_date = st.date_input("Tanggal", value=date.today(), key="pcr_date")
    with c2:
        note = st.text_area("Catatan Customer", key="pcr_note")

    st.subheader("🧩 Spesifikasi yang Diminta")
    spec_vals = {}
    for cat, label in CATEGORIES:
        spec_vals[cat] = st.text_input(label, key=f"pcr_spec_{cat}",
                                        placeholder="Kosongkan kalau tidak diperlukan/pakai yang lama")

    st.subheader("🛒 Lain-lain (Opsional)")
    st.caption("Contoh: Monitor, Mouse, Keyboard, Speaker, dll")
    extras = st.session_state["pcr_extras"]
    for i, ex in enumerate(extras):
        with st.container(border=True):
            c1,c2,c3 = st.columns([2,3,1])
            with c1: ex["label"] = st.text_input(f"Nama Item (#{i+1})", value=ex["label"], key=f"exl_{i}")
            with c2: ex["spec"] = st.text_input("Spesifikasi", value=ex["spec"], key=f"exs_{i}")
            with c3: ex["qty"] = st.number_input("Qty", min_value=1, value=int(ex["qty"]), step=1, key=f"exq_{i}")
            if st.button("🗑️ Hapus", key=f"exr_{i}"):
                extras.pop(i); st.rerun()
    if st.button("➕ Tambah Item Lain-lain"):
        extras.append({"label":"","spec":"","qty":1}); st.rerun()

    st.divider()
    c1,c2 = st.columns(2)
    with c1: save_draft = st.button("💾 Simpan Draft", use_container_width=True)
    with c2: submit = st.button("📤 Submit ke Admin Purchasing", type="primary", use_container_width=True)

    if save_draft or submit:
        if not cust_name:
            st.error("Nama customer wajib diisi"); return
        if not sel_branch:
            st.error("Cabang wajib dipilih"); return
        if not any(spec_vals.values()) and not any(e["label"].strip() for e in extras):
            st.error("Isi minimal 1 spesifikasi komponen atau 1 item lain-lain"); return

        payload = {"customer_name":cust_name,"branch":sel_branch,"branch_name":BRANCH_FULL.get(sel_branch,""),
                   "sales_id":user["id"],"sales_name":user["full_name"],"request_date":str(req_date),
                   "customer_note":note or None}
        for cat,_ in CATEGORIES:
            payload[f"{cat}_spec"] = spec_vals[cat] or None
        extras_payload = [{"label":e["label"],"spec":e["spec"] or None,"qty":int(e["qty"])}
                           for e in extras if e["label"].strip()]

        req = create_request(payload, extras_payload, submit=submit)
        st.session_state["pcr_extras"] = []
        if submit: st.success(f"PC Request {req['request_number']} berhasil disubmit")
        else: st.success(f"PC Request {req['request_number']} disimpan sebagai draft")
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# LIST / ANTRIAN (request-level)
# ══════════════════════════════════════════════════════════════════════════════
def render_list(user, status_filter=None, title="📋 Daftar PC Request"):
    st.title(title)
    branch, sales_id = _my_scope(user)
    reqs = get_requests(branch=branch, sales_id=sales_id, status=status_filter, limit=2000)

    with st.expander("🔍 Filter", expanded=False):
        c1,c2,c3 = st.columns(3)
        with c1: f_branch = st.selectbox("Cabang", ["Semua"]+ALL_BRANCHES, key=f"pf_branch_{title}")
        with c2: f_status = st.selectbox("Status", ["Semua"]+[l for _,l,_ in STATUSES], key=f"pf_status_{title}")
        with c3: f_search = st.text_input("Cari (customer/no. request)", key=f"pf_search_{title}")
    if f_branch != "Semua": reqs = [r for r in reqs if r.get("branch")==f_branch]
    if f_status != "Semua":
        rev = {l:k for k,l,_ in STATUSES}
        reqs = [r for r in reqs if r.get("status")==rev.get(f_status)]
    if f_search:
        s = f_search.lower()
        reqs = [r for r in reqs if s in (r.get("customer_name","") or "").lower() or s in (r.get("request_number","") or "").lower()]

    st.caption(f"{len(reqs)} request")
    if not reqs:
        st.info("Tidak ada PC Request."); return

    for r in reqs:
        c1,c2 = st.columns([5,1])
        with c1:
            st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="color:#6b4f8a;font-size:11px;font-weight:700">{r.get('request_number','')}</span>
{_badge(r.get('status',''))}
</div>
<div style="color:#e2e8f0;font-weight:600;font-size:14px;margin-top:2px">{r.get('customer_name','')}</div>
<div style="color:#9d7fba;font-size:12px;margin-top:2px">{r.get('sales_name','')} | {BRANCH_FULL.get(r.get('branch',''),r.get('branch',''))}</div>
</div>""", unsafe_allow_html=True)
        with c2:
            if st.button("Buka", key=f"pcr_open_{title}_{r['id']}", use_container_width=True):
                st.session_state["pcreq_id"] = r["id"]
                st.session_state["pcreq_view"] = "detail"
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# DETAIL + AKSI WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════
def render_detail(user):
    rid = st.session_state.get("pcreq_id")
    r = get_request(rid) if rid else None
    if not r:
        st.warning("Request tidak ditemukan."); return
    if st.button("← Kembali"):
        st.session_state["pcreq_view"] = "list"; st.rerun()

    st.title(f"{r.get('request_number','')} — {r.get('customer_name','')}")
    st.markdown(_badge(r.get("status","")), unsafe_allow_html=True)
    st.divider()

    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Customer**"); st.write(r.get("customer_name","-"))
        st.markdown("**Cabang**"); st.write(BRANCH_FULL.get(r.get("branch",""), r.get("branch","-")))
    with c2:
        st.markdown("**Sales**"); st.write(r.get("sales_name","-"))
        st.markdown("**Tanggal**"); st.write(r.get("request_date","-"))
    if r.get("customer_note"): st.markdown(f"**Catatan Customer:** {r['customer_note']}")

    extras = get_extras(rid)

    st.divider()
    st.subheader("🧩 Spesifikasi Komponen")
    has_admin_result = any(r.get(f"{cat}_found") for cat,_ in CATEGORIES)
    for cat, label in CATEGORIES:
        spec = r.get(f"{cat}_spec")
        found = r.get(f"{cat}_found")
        price = r.get(f"{cat}_price")
        if not spec and not found: continue
        c1,c2,c3 = st.columns([2,3,2])
        with c1: st.caption(label)
        with c2: st.write(spec or "-")
        with c3:
            if found: st.write(f"✅ {found} — {_fmt(price or 0)}")
            elif has_admin_result: st.write("⚪ -")
    if extras:
        st.caption("Lain-lain")
        for ex in extras:
            c1,c2,c3 = st.columns([2,3,2])
            with c1: st.caption(f"{ex.get('label','')} (x{ex.get('qty',1)})")
            with c2: st.write(ex.get("spec") or "-")
            with c3:
                if ex.get("found"): st.write(f"✅ {ex['found']} — {_fmt(ex.get('price',0))}")

    status = r.get("status")
    st.divider()

    # ── Sales: submit draft ─────────────────────────────────────────────────
    if status == "draft" and ((is_sales(user) or user["role"]=="store_leader") and r.get("sales_id")==user["id"] or user["role"]=="super_admin"):
        st.subheader("📤 Submit Request")
        if st.button("Submit ke Admin Purchasing", type="primary"):
            submit_request(rid, user["full_name"]); st.success("Request disubmit"); st.rerun()

    # ── Admin Purchasing: cari komponen ─────────────────────────────────────
    elif status == "submitted" and is_purchasing(user):
        st.subheader("🔎 Admin Purchasing — Cari Komponen")
        cat_results = {}
        with st.form("purchasing_form"):
            for cat, label in CATEGORIES:
                spec = r.get(f"{cat}_spec")
                if not spec:
                    continue
                st.markdown(f"**{label}** — diminta: _{spec}_")
                c1,c2 = st.columns(2)
                with c1: found = st.text_input("Produk/Spek Final", key=f"pf_found_{cat}")
                with c2: price = st.number_input("Harga (Rp)", min_value=0, step=10000, key=f"pf_price_{cat}")
                cat_results[cat] = {"found": found, "price": price}
            extras_results = {}
            for ex in extras:
                st.markdown(f"**{ex.get('label','')}** (x{ex.get('qty',1)}) — diminta: _{ex.get('spec') or '-'}_")
                c1,c2 = st.columns(2)
                with c1: efound = st.text_input("Produk/Spek Final", key=f"pf_efound_{ex['id']}")
                with c2: eprice = st.number_input("Harga (Rp)", min_value=0, step=10000, key=f"pf_eprice_{ex['id']}")
                extras_results[ex["id"]] = {"found": efound, "price": eprice}
            note = st.text_area("Catatan Purchasing (opsional)")
            if st.form_submit_button("✅ Simpan — Kirim ke Store Leader", type="primary"):
                purchasing_save(rid, user["full_name"], cat_results, extras_results, note)
                st.success("Komponen tersimpan — menunggu cek Store Leader"); st.rerun()

    # ── Store Leader: cek & tetapkan harga ──────────────────────────────────
    elif status == "store_leader_check" and is_leader(user):
        st.subheader("🔎 Store Leader Check")
        total_hpp = sum(float(r.get(f"{cat}_price") or 0) for cat,_ in CATEGORIES) + sum(float(e.get("price") or 0) for e in extras)
        st.info(f"Total harga komponen dari Purchasing: {_fmt(total_hpp)}")
        c1,c2 = st.columns(2)
        with c1:
            with st.form("sl_price_form"):
                sell_price = st.number_input("Harga Jual ke Customer (Rp)", min_value=0, value=int(total_hpp), step=10000)
                slnote = st.text_area("Catatan (opsional)")
                if st.form_submit_button("✅ Tetapkan Harga & Kirim ke Sales", type="primary"):
                    store_leader_set_price(rid, user["full_name"], sell_price, slnote)
                    st.success("Harga ditetapkan — sales bisa langsung menawarkan"); st.rerun()
        with c2:
            with st.popover("❌ Reject", use_container_width=True):
                reason = st.text_area("Alasan Reject *", key="pcr_reject_reason")
                if st.button("Konfirmasi Reject"):
                    if not reason: st.error("Alasan wajib diisi")
                    else:
                        store_leader_reject(rid, user["full_name"], reason)
                        st.success("Request ditolak"); st.rerun()

    elif status == "rejected":
        st.error(f"Request ini ditolak. Alasan: {r.get('reject_reason','-')}")

    # ── Sales offer: Deal / No Deal ─────────────────────────────────────────
    elif status == "sales_offer" and (is_sales(user) or user["role"] in ("store_leader","super_admin")):
        st.subheader("💬 Sales Offer")
        st.info(f"Harga jual: {_fmt(r.get('sl_price',0))}" + (f"  |  Catatan: {r['sl_note']}" if r.get("sl_note") else ""))
        tab1,tab2 = st.tabs(["✅ Deal","❌ No Deal"])
        with tab1:
            with st.form("deal_form"):
                dprice = st.number_input("Harga Deal (Rp)", min_value=0, value=int(r.get("sl_price") or 0), step=10000)
                dclose = st.date_input("Estimasi Closing", value=date.today())
                if st.form_submit_button("🏆 Simpan — Won", type="primary"):
                    sales_deal(rid, user["full_name"], dprice, dclose)
                    st.success("Deal! 🎉"); st.rerun()
        with tab2:
            with st.form("nodeal_form"):
                reason = st.selectbox("Alasan No Deal", NODEAL_REASONS)
                note = st.text_area("Keterangan *") if reason=="Lainnya" else ""
                if st.form_submit_button("❌ Simpan — Lost", type="primary"):
                    if reason=="Lainnya" and not note: st.error("Keterangan wajib diisi")
                    else:
                        sales_no_deal(rid, user["full_name"], reason, note)
                        st.warning("Ditandai No Deal"); st.rerun()

    elif status == "won":
        st.success(f"🏆 Won — Harga: {_fmt(r.get('deal_price',0))} | Est. Closing: {r.get('deal_est_closing','-')}")
    elif status == "lost":
        st.error(f"❌ Lost — Alasan: {r.get('nodeal_reason','-')}" + (f" — {r.get('nodeal_note')}" if r.get('nodeal_note') else ""))
    elif status in ("submitted","store_leader_check","sales_offer"):
        st.caption("Menunggu proses dari pihak terkait — tidak ada aksi untuk role Bapak saat ini.")

    st.divider()
    st.subheader("📜 History")
    hist = get_history(rid)
    if not hist: st.caption("Belum ada riwayat.")
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
    st.title("🔔 Notifikasi PC Request")
    role = user["role"]; branch = user.get("branch")
    c1,c2 = st.columns([3,1])
    with c1: show_all = st.checkbox("Tampilkan yang sudah dibaca", value=False)
    with c2:
        if st.button("✅ Tandai semua dibaca", use_container_width=True):
            mark_all_notifications_read(role=role, branch=branch); st.rerun()
    notifs = get_notifications(role=role, branch=branch, unread_only=not show_all)
    if not notifs:
        st.success("Tidak ada notifikasi baru."); return
    for n in notifs:
        ts = (n.get("created_at","") or "")[:16].replace("T"," ")
        c1,c2 = st.columns([5,1])
        with c1:
            st.markdown(f"""
<div style="background:#180d28;border:1px solid #2d1a45;border-left:3px solid #a855f7;border-radius:8px;padding:10px 14px;margin-bottom:6px">
<div style="color:#e2e8f0;font-size:13px">{n.get('message','')}</div>
<div style="color:#4a3060;font-size:10px;margin-top:2px">{ts}</div>
</div>""", unsafe_allow_html=True)
        with c2:
            if not n.get("is_read"):
                if st.button("Selesai", key=f"pcn_{n['id']}", use_container_width=True):
                    mark_notification_read(n["id"]); st.rerun()
            if n.get("request_id"):
                if st.button("Buka", key=f"pcn_open_{n['id']}", use_container_width=True):
                    st.session_state["pcreq_id"] = n["request_id"]
                    st.session_state["pcreq_view"] = "detail"; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# LAPORAN
# ══════════════════════════════════════════════════════════════════════════════
def render_reports(user):
    st.title("📑 Laporan PC Request")
    branch, _ = _my_scope(user)
    reqs = get_requests(branch=branch, limit=5000)
    if not reqs:
        st.info("Belum ada data."); return
    df = pd.DataFrame(reqs)
    df["status_label"] = df["status"].map(lambda s: STATUS_MAP.get(s,(s,""))[0])
    st.dataframe(df[["request_number","request_date","branch","sales_name","customer_name","status_label"]],
                 use_container_width=True, hide_index=True)
    c1,c2 = st.columns(2)
    with c1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📄 Download CSV", data=csv, file_name="pc_request_report.csv", mime="text/csv", use_container_width=True)
    with c2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="PC Request", index=False)
        st.download_button("📊 Download Excel", data=buf.getvalue(), file_name="pc_request_report.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
