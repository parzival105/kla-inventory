# PRMS — Project Request (multi-produk per request)
# Backend: status engine, history, notifications, master data
from datetime import datetime, date
from modules.db import _get, _post, _patch, _delete

ITEM_STATUSES = [
    ("waiting_product_review",   "🔬 Waiting Product Review",    "#8b5cf6"),
    ("product_found",            "✅ Product Found",             "#10b981"),
    ("replacement_suggested",    "🔁 Replacement Suggested",     "#a855f7"),
    ("unable_to_source",         "🚫 Unable to Source",          "#dc2626"),
    ("store_leader_check",       "🔎 Store Leader Check",        "#f59e0b"),
    ("sales_offer",              "💬 Sales Offer",               "#eab308"),
    ("won",                      "🏆 Won",                       "#22c55e"),
    ("lost",                     "❌ Lost",                      "#ef4444"),
]
ITEM_STATUS_MAP = {k: (label, color) for k, label, color in ITEM_STATUSES}
ITEM_TERMINAL = {"won", "lost", "unable_to_source"}

REQUEST_STATUSES = [
    ("draft",       "📝 Draft",       "#94a3b8"),
    ("submitted",   "📤 Submitted",   "#3b82f6"),
    ("rejected",    "🛑 Rejected",    "#64748b"),
    ("in_progress", "⚙️ In Progress", "#f59e0b"),
    ("completed",   "✅ Completed",   "#22c55e"),
]
REQUEST_STATUS_MAP = {k: (label, color) for k, label, color in REQUEST_STATUSES}

# Alias supaya kode lama/import lain tetap jalan
STATUSES = ITEM_STATUSES
STATUS_MAP = ITEM_STATUS_MAP
URGENCY_COLOR = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#22c55e"}

# ── Nomor request otomatis ───────────────────────────────────────────────────
def generate_request_number():
    try:
        rows = _get("prms_requests", {"select": "request_number", "order": "id.desc", "limit": "1"})
        if rows:
            last = rows[0]["request_number"]
            n = int(last.split("-")[-1]) + 1
        else:
            n = 1
    except Exception:
        n = 1
    return f"PR-{n:06d}"

# ── History / audit trail ────────────────────────────────────────────────────
def log_history(request_id, actor, action, note="", item_id=None):
    try:
        _post("prms_history", {
            "request_id": request_id, "item_id": item_id, "actor": actor, "action": action,
            "note": (note or "")[:500],
            "created_at": datetime.utcnow().isoformat() + "Z"
        })
    except Exception:
        pass

def get_history(request_id):
    try:
        return _get("prms_history", {"request_id": f"eq.{request_id}", "select": "*", "order": "created_at.asc"})
    except Exception:
        return []

# ── Notifikasi ────────────────────────────────────────────────────────────────
def push_notification(request_id, target_role, branch, notif_type, message, item_id=None):
    try:
        _post("prms_notifications", {
            "request_id": request_id, "item_id": item_id, "target_role": target_role, "branch": branch,
            "notif_type": notif_type, "message": message, "is_read": False,
            "created_at": datetime.utcnow().isoformat() + "Z"
        })
    except Exception:
        pass

def get_notifications(role=None, branch=None, sales_id=None, unread_only=True, limit=200):
    params = {"order": "created_at.desc", "limit": str(limit), "select": "*"}
    if unread_only:
        params["is_read"] = "is.false"
    try:
        rows = _get("prms_notifications", params)
    except Exception:
        return []
    out = []
    for n in rows:
        tr = n.get("target_role")
        if tr and role and tr != role:
            continue
        if tr == "store_leader" and branch and n.get("branch") not in (branch, None, ""):
            continue
        out.append(n)
    return out

def mark_notification_read(notif_id):
    try:
        _patch("prms_notifications", {"id": str(notif_id)}, {"is_read": True})
    except Exception:
        pass

def mark_all_notifications_read(role=None, branch=None):
    for n in get_notifications(role=role, branch=branch, unread_only=True, limit=500):
        mark_notification_read(n["id"])

# ── CRUD Request (parent) + Items (produk) ────────────────────────────────────
def create_request(parent_data, items, submit=False):
    """items: list of dict (field produk). Membuat 1 request + N item produk."""
    payload = dict(parent_data)
    payload["request_number"] = generate_request_number()
    payload["status"] = "submitted" if submit else "draft"
    payload["created_at"] = datetime.utcnow().isoformat() + "Z"
    payload["updated_at"] = datetime.utcnow().isoformat() + "Z"
    rows = _post("prms_requests", payload)
    req = rows[0] if isinstance(rows, list) and rows else rows

    for it in items:
        item_payload = dict(it)
        item_payload["request_id"] = req["id"]
        item_payload["status"] = "waiting_product_review"
        item_payload["created_at"] = datetime.utcnow().isoformat() + "Z"
        item_payload["updated_at"] = datetime.utcnow().isoformat() + "Z"
        _post("prms_request_items", item_payload)

    log_history(req["id"], payload.get("sales_name", ""), "Request dibuat",
                f"{len(items)} produk — {'langsung disubmit' if submit else 'disimpan sebagai draft'}")
    if submit:
        push_notification(req["id"], "store_leader", payload.get("branch"),
                           "new_request", f"Request baru {req['request_number']} dari {payload.get('customer_name','')} ({len(items)} produk)")
    return req

def submit_request(request_id, actor):
    _patch("prms_requests", {"id": str(request_id)}, {"status": "submitted", "updated_at": datetime.utcnow().isoformat() + "Z"})
    req = get_request(request_id)
    items = get_items(request_id)
    log_history(request_id, actor, "Request disubmit")
    push_notification(request_id, "store_leader", req.get("branch"),
                       "new_request", f"Request baru {req.get('request_number','')} dari {req.get('customer_name','')} ({len(items)} produk)")

def get_request(request_id):
    rows = _get("prms_requests", {"id": f"eq.{request_id}", "select": "*"})
    return rows[0] if rows else None

def get_requests(branch=None, sales_id=None, status=None, limit=1000):
    params = {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    if branch: params["branch"] = f"eq.{branch}"
    if sales_id: params["sales_id"] = f"eq.{sales_id}"
    if status: params["status"] = f"eq.{status}"
    try:
        return _get("prms_requests", params)
    except Exception:
        return []

def get_items(request_id):
    try:
        return _get("prms_request_items", {"request_id": f"eq.{request_id}", "select": "*", "order": "id.asc"})
    except Exception:
        return []

def get_item(item_id):
    rows = _get("prms_request_items", {"id": f"eq.{item_id}", "select": "*"})
    return rows[0] if rows else None

def _touch_request(request_id, extra):
    extra = dict(extra); extra["updated_at"] = datetime.utcnow().isoformat() + "Z"
    _patch("prms_requests", {"id": str(request_id)}, extra)

def _touch_item(item_id, extra):
    extra = dict(extra); extra["updated_at"] = datetime.utcnow().isoformat() + "Z"
    _patch("prms_request_items", {"id": str(item_id)}, extra)

def recompute_request_status(request_id):
    """Kalau semua item sudah final (won/lost/unable_to_source) → request jadi Completed."""
    items = get_items(request_id)
    if items and all(i.get("status") in ITEM_TERMINAL for i in items):
        req = get_request(request_id)
        if req and req.get("status") not in ("completed", "rejected"):
            _touch_request(request_id, {"status": "completed"})
            log_history(request_id, "System", "Semua produk selesai — request Completed")

# ── 2. Store Leader review (Approve / Reject) — level REQUEST ────────────────
def store_leader_approve(request_id, actor):
    req = get_request(request_id)
    _touch_request(request_id, {"status": "in_progress"})
    log_history(request_id, actor, "Disetujui Store Leader (seluruh request)")
    push_notification(request_id, "sales", req.get("branch"), "approved",
                       f"Request {req.get('request_number','')} disetujui Store Leader")
    push_notification(request_id, "product_manager", req.get("branch"), "new_request",
                       f"Request {req.get('request_number','')} menunggu review produk")

def store_leader_reject(request_id, actor, reason):
    req = get_request(request_id)
    _touch_request(request_id, {"status": "rejected", "reject_reason": reason})
    log_history(request_id, actor, "Ditolak Store Leader (seluruh request)", reason)
    push_notification(request_id, "sales", req.get("branch"), "rejected",
                       f"Request {req.get('request_number','')} ditolak: {reason}")

# ── 3. PM / Super Admin review — level ITEM (per produk) ──────────────────────
def pm_product_found(item_id, actor, supplier, cost_price, sell_price, eta, stock):
    item = get_item(item_id); req = get_request(item["request_id"])
    _touch_item(item_id, {"status": "product_found", "pm_supplier": supplier,
                          "pm_cost_price": cost_price, "pm_sell_price": sell_price,
                          "pm_eta": eta, "pm_supplier_stock": stock})
    log_history(item["request_id"], actor, "Produk ditemukan", f"{item.get('product_name','')} — Supplier: {supplier}", item_id=item_id)
    push_notification(item["request_id"], "sales", req.get("branch"), "product_found",
                       f"Produk '{item.get('product_name','')}' ditemukan ({req.get('request_number','')})", item_id=item_id)
    push_notification(item["request_id"], "admin_purchasing", req.get("branch"), "to_process",
                       f"Produk '{item.get('product_name','')}' siap diproses purchasing ({req.get('request_number','')})", item_id=item_id)

def pm_replacement(item_id, actor, name, brand, part_number, spec, reason, price, price_diff):
    item = get_item(item_id); req = get_request(item["request_id"])
    _touch_item(item_id, {"status": "replacement_suggested", "repl_product_name": name,
                          "repl_brand": brand, "repl_part_number": part_number, "repl_spec": spec,
                          "repl_reason": reason, "repl_price": price, "repl_price_diff": price_diff})
    log_history(item["request_id"], actor, "Produk EOL — pengganti diusulkan", f"{item.get('product_name','')} → {name} ({brand})", item_id=item_id)
    push_notification(item["request_id"], "sales", req.get("branch"), "replacement_suggested",
                       f"Produk pengganti tersedia untuk '{item.get('product_name','')}' ({req.get('request_number','')})", item_id=item_id)
    push_notification(item["request_id"], "admin_purchasing", req.get("branch"), "to_process",
                       f"Produk pengganti '{name}' siap diproses purchasing ({req.get('request_number','')})", item_id=item_id)

def pm_unable_to_source(item_id, actor, reason):
    item = get_item(item_id); req = get_request(item["request_id"])
    _touch_item(item_id, {"status": "unable_to_source", "unable_reason": reason})
    log_history(item["request_id"], actor, "Produk tidak ditemukan", f"{item.get('product_name','')} — {reason}", item_id=item_id)
    push_notification(item["request_id"], "sales", req.get("branch"), "unable_to_source",
                       f"Produk '{item.get('product_name','')}' tidak ditemukan: {reason}", item_id=item_id)
    recompute_request_status(item["request_id"])

# ── 4. Admin Purchasing — level ITEM ──────────────────────────────────────────
def purchasing_ready(item_id, actor, supplier, stock, eta, price, po_number=""):
    item = get_item(item_id); req = get_request(item["request_id"])
    _touch_item(item_id, {"status": "store_leader_check", "pur_supplier": supplier,
                          "pur_stock": stock, "pur_eta": eta, "pur_price": price, "pur_po_number": po_number})
    log_history(item["request_id"], actor, "Ready for Sales (Purchasing)", f"{item.get('product_name','')} — Supplier: {supplier}, ETA: {eta}", item_id=item_id)
    push_notification(item["request_id"], "store_leader", req.get("branch"), "ready_to_check",
                       f"Produk '{item.get('product_name','')}' siap dicek sebelum ke sales ({req.get('request_number','')})", item_id=item_id)

# ── 5. Store Leader forward to sales — level ITEM ─────────────────────────────
def store_leader_forward(item_id, actor):
    item = get_item(item_id); req = get_request(item["request_id"])
    _touch_item(item_id, {"status": "sales_offer"})
    log_history(item["request_id"], actor, "Forward to Sales", item.get("product_name",""), item_id=item_id)
    push_notification(item["request_id"], "sales", req.get("branch"), "ready_to_offer",
                       f"Produk '{item.get('product_name','')}' siap ditawarkan ({req.get('request_number','')})", item_id=item_id)

# ── 6. Sales offer: Deal / No Deal — level ITEM ───────────────────────────────
def sales_deal(item_id, actor, deal_qty, deal_price, deal_est_closing):
    item = get_item(item_id)
    _touch_item(item_id, {"status": "won", "deal_qty": deal_qty, "deal_price": deal_price,
                          "deal_est_closing": str(deal_est_closing) if deal_est_closing else None})
    log_history(item["request_id"], actor, "Deal", f"{item.get('product_name','')} — Qty {deal_qty} @ {deal_price}", item_id=item_id)
    recompute_request_status(item["request_id"])

def sales_no_deal(item_id, actor, reason, note=""):
    item = get_item(item_id)
    _touch_item(item_id, {"status": "lost", "nodeal_reason": reason, "nodeal_note": note})
    log_history(item["request_id"], actor, "No Deal", f"{item.get('product_name','')} — {reason}" + (f" — {note}" if note else ""), item_id=item_id)
    recompute_request_status(item["request_id"])

# ── Queue: ambil ITEM lintas-request untuk antrian per role ───────────────────
def get_item_queue(item_status_list, branch=None, sales_id=None, request_status="in_progress"):
    """Gabungkan item dari semua request aktif yang statusnya ada di item_status_list.
    Mengembalikan list dict item + info request (request_number, customer_name, branch, sales_name)."""
    reqs = get_requests(branch=branch, sales_id=sales_id, status=request_status, limit=1000)
    out = []
    for req in reqs:
        for it in get_items(req["id"]):
            if it.get("status") in item_status_list:
                merged = dict(it)
                merged["request_number"] = req.get("request_number")
                merged["customer_name"] = req.get("customer_name")
                merged["branch"] = req.get("branch")
                merged["sales_name"] = req.get("sales_name")
                merged["sales_id"] = req.get("sales_id")
                out.append(merged)
    return out

# ── Master data (generic CRUD) ────────────────────────────────────────────────
MASTER_TABLES = {
    "brand": "prms_master_brand", "category": "prms_master_category",
    "supplier": "prms_master_supplier", "reject_reason": "prms_master_reject_reason",
    "nodeal_reason": "prms_master_nodeal_reason",
}

def get_master(kind, active_only=True):
    table = MASTER_TABLES[kind]
    params = {"select": "*", "order": "name.asc" if kind not in ("reject_reason","nodeal_reason") else "reason.asc"}
    if active_only: params["is_active"] = "is.true"
    try:
        return _get(table, params)
    except Exception:
        return []

def add_master(kind, payload):
    table = MASTER_TABLES[kind]
    return _post(table, payload)

def update_master(kind, item_id, payload):
    table = MASTER_TABLES[kind]
    _patch(table, {"id": str(item_id)}, payload)

def delete_master(kind, item_id):
    table = MASTER_TABLES[kind]
    _delete(table, {"id": item_id})

# ── Dashboard & analytics ─────────────────────────────────────────────────────
def get_dashboard_stats(branch=None):
    reqs = get_requests(branch=branch, limit=5000)
    total = len(reqs)
    all_items = []
    for req in reqs:
        for it in get_items(req["id"]):
            it["_branch"] = req.get("branch"); it["_created_at"] = req.get("created_at")
            all_items.append(it)

    def c(*st): return sum(1 for i in all_items if i.get("status") in st)
    waiting_approval = sum(1 for r in reqs if r.get("status") == "submitted")
    total_closing = c("won", "lost")
    deal_rate = round(c("won") / total_closing * 100, 1) if total_closing else 0
    nodeal_rate = round(c("lost") / total_closing * 100, 1) if total_closing else 0
    return {
        "total": total,
        "total_items": len(all_items),
        "waiting_approval": waiting_approval,
        "waiting_pm": c("waiting_product_review"),
        "waiting_purchasing": c("product_found", "replacement_suggested"),
        "ready_to_offer": c("sales_offer", "store_leader_check"),
        "deal": c("won"),
        "no_deal": c("lost"),
        "replacement": sum(1 for i in all_items if i.get("repl_product_name")),
        "eol": sum(1 for i in all_items if i.get("repl_product_name")),
        "deal_rate": deal_rate, "nodeal_rate": nodeal_rate,
        "rows": reqs, "items": all_items,
    }
