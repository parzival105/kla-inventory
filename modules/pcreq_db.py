# PC Request — Custom PC Build Request (rakitan/pemesanan khusus di luar stok)
# Backend: status engine, history, notifications
from datetime import datetime, date
from modules.db import _get, _post, _patch, _delete

STATUSES = [
    ("draft",               "📝 Draft",                "#94a3b8"),
    ("submitted",           "🔎 Waiting Purchasing",   "#8b5cf6"),
    ("store_leader_check",  "🔎 Store Leader Check",   "#f59e0b"),
    ("rejected",            "🛑 Rejected",             "#64748b"),
    ("sales_offer",         "💬 Sales Offer",          "#eab308"),
    ("won",                 "🏆 Won",                  "#22c55e"),
    ("lost",                "❌ Lost",                 "#ef4444"),
]
STATUS_MAP = {k: (label, color) for k, label, color in STATUSES}

CATEGORIES = [
    ("proc",     "🧠 Processor"),
    ("mobo",     "🔌 Motherboard"),
    ("ram",      "💾 RAM"),
    ("gpu",      "🎮 GPU / VGA"),
    ("storage",  "💽 Storage"),
    ("casing",   "🖥️ Casing"),
    ("fan",      "🌀 Fan Processor / Cooling"),
]

NODEAL_REASONS = ["Harga terlalu mahal","Customer batal beli","Customer membeli di tempat lain",
                   "Barang terlalu lama datang","Produk tidak sesuai","Budget kurang",
                   "Spesifikasi berubah","Lainnya"]

def generate_request_number():
    try:
        rows = _get("pc_build_requests", {"select": "request_number", "order": "id.desc", "limit": "1"})
        n = int(rows[0]["request_number"].split("-")[-1]) + 1 if rows else 1
    except Exception:
        n = 1
    return f"PCB-{n:06d}"

# ── History ────────────────────────────────────────────────────────────────
def log_history(request_id, actor, action, note=""):
    try:
        _post("pc_build_logs", {"request_id": request_id, "actor": actor, "action": action,
                                 "note": (note or "")[:500], "created_at": datetime.utcnow().isoformat() + "Z"})
    except Exception: pass

def get_history(request_id):
    try:
        return _get("pc_build_logs", {"request_id": f"eq.{request_id}", "select": "*", "order": "created_at.asc"})
    except Exception: return []

# ── Notifikasi ────────────────────────────────────────────────────────────────
def push_notification(request_id, target_role, branch, notif_type, message):
    try:
        _post("pc_build_notifications", {"request_id": request_id, "target_role": target_role, "branch": branch,
                                          "notif_type": notif_type, "message": message, "is_read": False,
                                          "created_at": datetime.utcnow().isoformat() + "Z"})
    except Exception: pass

def get_notifications(role=None, branch=None, unread_only=True, limit=200):
    params = {"order": "created_at.desc", "limit": str(limit), "select": "*"}
    if unread_only: params["is_read"] = "is.false"
    try: rows = _get("pc_build_notifications", params)
    except Exception: return []
    out = []
    for n in rows:
        tr = n.get("target_role")
        if role == "super_admin":
            out.append(n); continue
        if tr and role and tr != role: continue
        if tr == "store_leader" and branch and n.get("branch") not in (branch, None, ""): continue
        out.append(n)
    return out

def mark_notification_read(notif_id):
    try: _patch("pc_build_notifications", {"id": str(notif_id)}, {"is_read": True})
    except Exception: pass

def mark_all_notifications_read(role=None, branch=None):
    for n in get_notifications(role=role, branch=branch, unread_only=True, limit=500):
        mark_notification_read(n["id"])

# ── CRUD Request + Extras ──────────────────────────────────────────────────────
def create_request(payload, extras_payload, submit=False):
    data = dict(payload)
    data["request_number"] = generate_request_number()
    data["status"] = "submitted" if submit else "draft"
    data["created_at"] = datetime.utcnow().isoformat() + "Z"
    data["updated_at"] = datetime.utcnow().isoformat() + "Z"
    rows = _post("pc_build_requests", data)
    req = rows[0] if isinstance(rows, list) and rows else rows

    for ex in extras_payload:
        ex_data = dict(ex)
        ex_data["request_id"] = req["id"]
        ex_data["created_at"] = datetime.utcnow().isoformat() + "Z"
        _post("pc_build_extras", ex_data)

    log_history(req["id"], data.get("sales_name", ""), "PC Request dibuat",
                f"{'Langsung disubmit' if submit else 'Disimpan sebagai draft'}")
    if submit:
        push_notification(req["id"], "admin_purchasing", data.get("branch"), "new_request",
                           f"PC Request baru {req['request_number']} dari {data.get('customer_name','')}")
    return req

def submit_request(request_id, actor):
    _patch("pc_build_requests", {"id": str(request_id)}, {"status": "submitted", "updated_at": datetime.utcnow().isoformat() + "Z"})
    req = get_request(request_id)
    log_history(request_id, actor, "PC Request disubmit")
    push_notification(request_id, "admin_purchasing", req.get("branch"), "new_request",
                       f"PC Request baru {req.get('request_number','')} dari {req.get('customer_name','')}")

def get_request(request_id):
    rows = _get("pc_build_requests", {"id": f"eq.{request_id}", "select": "*"})
    return rows[0] if rows else None

def get_requests(branch=None, sales_id=None, status=None, limit=1000):
    params = {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    if branch: params["branch"] = f"eq.{branch}"
    if sales_id: params["sales_id"] = f"eq.{sales_id}"
    if status: params["status"] = f"eq.{status}"
    try: return _get("pc_build_requests", params)
    except Exception: return []

def get_extras(request_id):
    try: return _get("pc_build_extras", {"request_id": f"eq.{request_id}", "select": "*", "order": "id.asc"})
    except Exception: return []

def update_extra(extra_id, extra):
    try: _patch("pc_build_extras", {"id": str(extra_id)}, extra)
    except Exception: pass

def _touch(request_id, extra):
    extra = dict(extra); extra["updated_at"] = datetime.utcnow().isoformat() + "Z"
    _patch("pc_build_requests", {"id": str(request_id)}, extra)

# ── Admin Purchasing: cari komponen (semua kategori + extras sekaligus) ──────
def purchasing_save(request_id, actor, cat_results, extras_results, note=""):
    req = get_request(request_id)
    update = {"status": "store_leader_check", "purchasing_note": note or ""}
    for cat, r in cat_results.items():
        if r.get("found"):
            update[f"{cat}_found"] = r["found"]
            update[f"{cat}_price"] = r.get("price", 0)
    _touch(request_id, update)
    for extra_id, r in extras_results.items():
        if r.get("found"):
            update_extra(extra_id, {"found": r["found"], "price": r.get("price", 0)})
    log_history(request_id, actor, "Komponen ditemukan — menunggu cek Store Leader", note)
    push_notification(request_id, "store_leader", req.get("branch"), "ready_to_check",
                       f"PC Request {req.get('request_number','')} siap dicek & ditentukan harga jualnya")

def revert_to_purchasing(request_id, actor, note=""):
    """Kembalikan request dari Store Leader Check ke Admin Purchasing — dipakai kalau
    hasil sourcing sebelumnya belum lengkap/salah kirim (mis. tidak sengaja submit)."""
    req = get_request(request_id)
    _touch(request_id, {"status": "submitted"})
    log_history(request_id, actor, "Dikembalikan ke Purchasing untuk dilengkapi/diedit ulang", note)
    push_notification(request_id, "admin_purchasing", req.get("branch"), "new_request",
                       f"PC Request {req.get('request_number','')} dikembalikan — mohon lengkapi/perbaiki komponen")

# ── Store Leader: cek & tetapkan harga jual, atau reject ──────────────────────
def store_leader_set_price(request_id, actor, sell_price, note=""):
    req = get_request(request_id)
    _touch(request_id, {"status": "sales_offer", "sl_price": sell_price, "sl_note": note})
    log_history(request_id, actor, "Dicek Store Leader — harga jual ditetapkan", f"Harga jual: {sell_price}")
    push_notification(request_id, "sales", req.get("branch"), "ready_to_offer",
                       f"PC Request {req.get('request_number','')} siap ditawarkan ke customer")

def store_leader_reject(request_id, actor, reason):
    req = get_request(request_id)
    _touch(request_id, {"status": "rejected", "reject_reason": reason})
    log_history(request_id, actor, "Ditolak Store Leader", reason)
    push_notification(request_id, "sales", req.get("branch"), "rejected",
                       f"PC Request {req.get('request_number','')} ditolak: {reason}")

# ── Sales offer: Deal / No Deal ───────────────────────────────────────────────
def sales_deal(request_id, actor, deal_price, deal_est_closing):
    _touch(request_id, {"status": "won", "deal_price": deal_price,
                        "deal_est_closing": str(deal_est_closing) if deal_est_closing else None})
    log_history(request_id, actor, "Deal", f"Harga: {deal_price}")

def sales_no_deal(request_id, actor, reason, note=""):
    _touch(request_id, {"status": "lost", "nodeal_reason": reason, "nodeal_note": note})
    log_history(request_id, actor, "No Deal", f"{reason}" + (f" — {note}" if note else ""))

# ── Dashboard & analytics ─────────────────────────────────────────────────────
def get_dashboard_stats(branch=None):
    reqs = get_requests(branch=branch, limit=5000)
    def c(*st): return sum(1 for r in reqs if r.get("status") in st)
    total_closing = c("won", "lost")
    deal_rate = round(c("won") / total_closing * 100, 1) if total_closing else 0
    return {
        "total": len(reqs),
        "submitted": c("submitted"),
        "store_leader_check": c("store_leader_check"),
        "sales_offer": c("sales_offer"),
        "won": c("won"), "lost": c("lost"),
        "deal_rate": deal_rate,
        "rows": reqs,
    }
