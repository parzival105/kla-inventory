import hashlib
from datetime import datetime, date, timedelta
from modules.db import _get, _post, _patch, _delete, SUPABASE_URL, SUPABASE_KEY
import requests

# ── Project Number Generator ──────────────────────────────────────────────────
def generate_project_number():
    try:
        rows = _get("project_requests", {"select":"project_number","order":"id.desc","limit":"1"})
        if rows:
            last = rows[0]["project_number"]  # PRJ-000001
            num = int(last.split("-")[1]) + 1
        else:
            num = 1
        return f"PRJ-{num:06d}"
    except:
        import random
        return f"PRJ-{random.randint(1,999999):06d}"

def generate_quotation_number(project_number):
    try:
        rows = _get("project_quotation", {"select":"quotation_number","order":"id.desc","limit":"1"})
        if rows and rows[0].get("quotation_number"):
            last = rows[0]["quotation_number"]
            num = int(last.split("-")[1]) + 1
        else:
            num = 1
        return f"QUO-{num:06d}"
    except:
        return f"QUO-{project_number.split('-')[1]}"

# ── Status Config ─────────────────────────────────────────────────────────────
STATUSES = [
    ("new_request",      "New Request",       "#3b82f6"),
    ("review_pm",        "Review PM",         "#f97316"),
    ("eol_verification", "EOL Verification",  "#eab308"),
    ("replacement",      "Replacement Search","#8b5cf6"),
    ("supplier_sourcing","Supplier Sourcing", "#06b6d4"),
    ("waiting_quotation","Waiting Quotation", "#06b6d4"),
    ("quotation_sent",   "Quotation Sent",    "#06b6d4"),
    ("negotiation",      "Negotiation",       "#f59e0b"),
    ("waiting_po",       "Waiting PO",        "#a855f7"),
    ("ordered",          "Ordered",           "#6366f1"),
    ("delivered",        "Delivered",         "#10b981"),
    ("deal",             "Deal",              "#059669"),
    ("lost",             "Lost",              "#dc2626"),
]
STATUS_MAP = {k: (label, color) for k, label, color in STATUSES}

PRIORITY_COLOR = {"High":"#dc2626","Medium":"#d97706","Low":"#059669"}
MEDIA_OPTS = ["WA","Telepon","Email","Meeting"]
FOLLOWUP_RESULTS = ["Customer menunggu","Minta diskon","Minta revisi","Sudah Deal","Tidak Jadi","Lainnya"]
LOST_REASONS = ["Harga terlalu tinggi","Barang tidak tersedia","Produk EOL",
    "Supplier tidak ada","Lead time terlalu lama","Kompetitor",
    "Customer batal","Budget kurang","Lainnya"]

# ── CRUD Project ──────────────────────────────────────────────────────────────
def create_project(data: dict) -> dict:
    data["project_number"] = generate_project_number()
    data["status"] = "new_request"
    data["created_at"] = datetime.utcnow().isoformat() + "Z"
    data["updated_at"] = datetime.utcnow().isoformat() + "Z"
    result = _post("project_requests", data)
    log_timeline(result["id"], data.get("sales_name","System"), "Project dibuat",
                 f"Customer: {data.get('customer_name','')} | {data.get('customer_company','')}",
                 new_status="new_request")
    return result

def get_projects(branch=None, status=None, sales_id=None, limit=200):
    params = {"order":"updated_at.desc","limit":str(limit),"select":"*"}
    if branch: params["branch"] = f"eq.{branch}"
    if status: params["status"] = f"eq.{status}"
    if sales_id: params["sales_id"] = f"eq.{sales_id}"
    try: return _get("project_requests", params)
    except: return []

def get_project(project_id):
    try:
        rows = _get("project_requests", {"id":f"eq.{project_id}","select":"*"})
        return rows[0] if rows else None
    except: return None

def update_project(project_id, data: dict, actor="", action="", detail=""):
    data["updated_at"] = datetime.utcnow().isoformat() + "Z"
    old = get_project(project_id)
    old_status = old.get("status","") if old else ""
    _patch("project_requests", {"id":str(project_id)}, data)
    if action:
        log_timeline(project_id, actor, action, detail,
                     old_status=old_status,
                     new_status=data.get("status", old_status))
    return True

def update_project_status(project_id, new_status, actor="", detail=""):
    old = get_project(project_id)
    old_status = old.get("status","") if old else ""
    _patch("project_requests", {"id":str(project_id)}, {
        "status": new_status,
        "updated_at": datetime.utcnow().isoformat() + "Z"
    })
    log_timeline(project_id, actor, f"Status berubah ke {STATUS_MAP.get(new_status,('',''))[0]}",
                 detail, old_status=old_status, new_status=new_status)

# ── Products ──────────────────────────────────────────────────────────────────
def add_product(project_id, data):
    data["project_id"] = project_id
    data["created_at"] = datetime.utcnow().isoformat() + "Z"
    return _post("project_products", data)

def get_products(project_id):
    try: return _get("project_products", {"project_id":f"eq.{project_id}","select":"*"})
    except: return []

def update_product(product_id, data):
    return _patch("project_products", {"id":str(product_id)}, data)

# ── Supplier ──────────────────────────────────────────────────────────────────
def add_supplier(project_id, data, actor=""):
    data["project_id"] = project_id
    data["created_at"] = datetime.utcnow().isoformat() + "Z"
    result = _post("project_supplier", data)
    log_timeline(project_id, actor, "Supplier ditambahkan", data.get("supplier_name",""))
    return result

def get_suppliers(project_id):
    try: return _get("project_supplier", {"project_id":f"eq.{project_id}","select":"*","order":"created_at.asc"})
    except: return []

def select_supplier(project_id, supplier_id, actor=""):
    # Unselect all first
    for s in get_suppliers(project_id):
        _patch("project_supplier", {"id":str(s["id"])}, {"is_selected":False})
    _patch("project_supplier", {"id":str(supplier_id)}, {"is_selected":True})
    supplier = _get("project_supplier", {"id":f"eq.{supplier_id}","select":"*"})
    name = supplier[0]["supplier_name"] if supplier else ""
    log_timeline(project_id, actor, "Supplier dipilih", name)

# ── Quotation ─────────────────────────────────────────────────────────────────
def create_quotation(project_id, data, actor=""):
    data["project_id"] = project_id
    data["quotation_number"] = generate_quotation_number(
        get_project(project_id).get("project_number","PRJ-000000") if get_project(project_id) else "PRJ-000000")
    data["status"] = "draft"
    data["created_at"] = datetime.utcnow().isoformat() + "Z"
    result = _post("project_quotation", data)
    log_timeline(project_id, actor, "Quotation dibuat", data.get("quotation_number",""))
    return result

def get_quotations(project_id):
    try: return _get("project_quotation", {"project_id":f"eq.{project_id}","select":"*","order":"created_at.desc"})
    except: return []

def update_quotation(quot_id, data, project_id=None, actor=""):
    _patch("project_quotation", {"id":str(quot_id)}, data)
    if project_id and data.get("status"):
        status_label = {"draft":"Draft","sent":"Dikirim ke Customer","revised":"Direvisi","approved":"Disetujui"}
        log_timeline(project_id, actor, "Quotation "+status_label.get(data["status"],"diupdate"), "")

# ── Follow Up ─────────────────────────────────────────────────────────────────
def add_followup(project_id, data, actor=""):
    data["project_id"] = project_id
    data["created_at"] = datetime.utcnow().isoformat() + "Z"
    result = _post("project_followup", data)
    log_timeline(project_id, actor, f"Follow up via {data.get('media','')}",
                 data.get("result","") + " — " + data.get("notes",""))
    return result

def get_followups(project_id):
    try: return _get("project_followup", {"project_id":f"eq.{project_id}","select":"*","order":"created_at.desc"})
    except: return []

# ── Replacement ───────────────────────────────────────────────────────────────
def add_replacement(project_id, data, actor=""):
    data["project_id"] = project_id
    data["created_at"] = datetime.utcnow().isoformat() + "Z"
    result = _post("project_replacement", data)
    log_timeline(project_id, actor, "Replacement product ditambahkan",
                 f"{data.get('original_model','')} → {data.get('new_model','')}")
    # Update knowledge base
    try:
        kb_rows = _get("project_knowledge_base", {
            "original_model":f"eq.{data.get('original_model','')}",
            "replacement_model":f"eq.{data.get('new_model','')}","select":"*"})
        if kb_rows:
            _patch("project_knowledge_base", {"id":str(kb_rows[0]["id"])},
                   {"usage_count": kb_rows[0]["usage_count"]+1,
                    "updated_at": datetime.utcnow().isoformat()+"Z"})
        else:
            _post("project_knowledge_base", {
                "original_brand":data.get("original_brand",""),
                "original_model":data.get("original_model",""),
                "replacement_brand":data.get("new_brand",""),
                "replacement_model":data.get("new_model",""),
                "reason":data.get("pm_notes",""),
                "created_at":datetime.utcnow().isoformat()+"Z",
                "updated_at":datetime.utcnow().isoformat()+"Z"})
    except: pass
    return result

def get_replacements(project_id):
    try: return _get("project_replacement", {"project_id":f"eq.{project_id}","select":"*"})
    except: return []

def search_knowledge_base(product_name):
    try:
        name_lower = product_name.lower()
        rows = _get("project_knowledge_base", {"select":"*","order":"usage_count.desc","limit":"20"})
        return [r for r in rows if
                name_lower in (r.get("original_model","") or "").lower() or
                name_lower in (r.get("original_brand","") or "").lower()]
    except: return []

# ── Timeline ──────────────────────────────────────────────────────────────────
def log_timeline(project_id, actor, action, detail="", old_status="", new_status=""):
    try:
        _post("project_timeline", {
            "project_id": project_id,
            "actor": actor,
            "action": action,
            "detail": detail[:500] if detail else "",
            "old_status": old_status,
            "new_status": new_status,
            "created_at": datetime.utcnow().isoformat() + "Z"
        })
    except: pass

def get_timeline(project_id):
    try: return _get("project_timeline", {"project_id":f"eq.{project_id}","select":"*","order":"created_at.asc"})
    except: return []

# ── Dashboard Stats ───────────────────────────────────────────────────────────
def get_dashboard_stats(branch=None):
    projects = get_projects(branch=branch, limit=500)
    if not projects:
        return {"total":0,"deal":0,"lost":0,"in_progress":0,
                "deal_rate":0,"potential_revenue":0,"deal_revenue":0,
                "lost_revenue":0,"by_status":{},"by_priority":{},
                "top_brands":{},"top_lost":{},"top_sales":{}}
    total = len(projects)
    deal = sum(1 for p in projects if p["status"]=="deal")
    lost = sum(1 for p in projects if p["status"]=="lost")
    in_prog = total - deal - lost
    deal_rate = round(deal/(deal+lost)*100,1) if (deal+lost)>0 else 0
    potential = sum(float(p.get("estimated_value",0) or 0) for p in projects if p["status"] not in ["deal","lost"])
    deal_rev = sum(float(p.get("deal_value",0) or 0) for p in projects if p["status"]=="deal")
    lost_rev = sum(float(p.get("estimated_value",0) or 0) for p in projects if p["status"]=="lost")
    by_status = {}
    for p in projects:
        s = p["status"]; by_status[s] = by_status.get(s,0)+1
    by_priority = {}
    for p in projects:
        pr = p.get("priority","Medium"); by_priority[pr] = by_priority.get(pr,0)+1
    top_sales = {}
    for p in projects:
        s = p.get("sales_name","Unknown"); top_sales[s] = top_sales.get(s,0)+1
    return {"total":total,"deal":deal,"lost":lost,"in_progress":in_prog,
            "deal_rate":deal_rate,"potential_revenue":potential,
            "deal_revenue":deal_rev,"lost_revenue":lost_rev,
            "by_status":by_status,"by_priority":by_priority,"top_sales":top_sales}

# ── Logs (audit trail internal, terpisah dari timeline yang dilihat customer) ──
def log_system(project_id, actor, event, detail=""):
    try:
        _post("project_logs", {
            "project_id": project_id, "actor": actor, "event": event,
            "detail": (detail or "")[:500],
            "created_at": datetime.utcnow().isoformat() + "Z"
        })
    except: pass

def get_logs(project_id=None, limit=200):
    params = {"order":"created_at.desc","limit":str(limit),"select":"*"}
    if project_id: params["project_id"] = f"eq.{project_id}"
    try: return _get("project_logs", params)
    except: return []

# ── Documents / Lampiran ────────────────────────────────────────────────────────
def add_document(project_id, file_name, file_bytes, content_type, category, uploaded_by):
    from modules.storage import upload
    import re, time
    safe_name = re.sub(r"[^A-Za-z0-9._-]","_", file_name)
    storage_path = f"crm_docs/{project_id}/{int(time.time())}_{safe_name}"
    upload(file_bytes, storage_path, content_type or "application/octet-stream")
    result = _post("project_documents", {
        "project_id": project_id, "file_name": file_name,
        "storage_path": storage_path, "file_size": len(file_bytes or b""),
        "content_type": content_type, "category": category or "Lainnya",
        "uploaded_by": uploaded_by,
        "created_at": datetime.utcnow().isoformat() + "Z"
    })
    log_timeline(project_id, uploaded_by, "Dokumen diupload", f"{file_name} ({category})")
    log_system(project_id, uploaded_by, "document_upload", storage_path)
    return result

def get_documents(project_id):
    try: return _get("project_documents", {"project_id":f"eq.{project_id}","select":"*","order":"created_at.desc"})
    except: return []

def download_document(storage_path):
    from modules.storage import download
    return download(storage_path)

def delete_document(doc_id, project_id, storage_path, actor=""):
    from modules.storage import delete as storage_delete
    storage_delete(storage_path)
    _delete("project_documents", {"id": doc_id})
    log_timeline(project_id, actor, "Dokumen dihapus", storage_path.split("/")[-1])
    log_system(project_id, actor, "document_delete", storage_path)

# ── Notifications ────────────────────────────────────────────────────────────
NOTIF_RULES_LABEL = {
    "new_request":     "🆕 Project baru",
    "pm_late":         "⏰ PM belum review > 1 hari",
    "supplier_late":   "⏰ Supplier belum update > 2 hari",
    "quotation_late":  "⏰ Quotation belum dikirim > 3 hari",
    "followup_late":   "⏰ Tidak ada follow up > 7 hari",
    "deadline_near":   "📅 Project hampir deadline",
    "po_received":     "📦 PO diterima",
    "delivered":       "🚚 Barang datang",
    "closed":          "✅ Project selesai",
}

def _notif_exists_recent(project_id, notif_type):
    try:
        rows = _get("project_notifications", {
            "project_id": f"eq.{project_id}", "notif_type": f"eq.{notif_type}",
            "is_read": "is.false", "select": "id", "limit": "1"
        })
        return bool(rows)
    except: return False

def _push_notif(project_id, notif_type, message, branch=""):
    if _notif_exists_recent(project_id, notif_type):
        return
    try:
        _post("project_notifications", {
            "project_id": project_id, "notif_type": notif_type, "message": message,
            "branch": branch, "is_read": False,
            "created_at": datetime.utcnow().isoformat() + "Z"
        })
    except: pass

def generate_notifications():
    """Rule engine: scan project aktif dan buat notifikasi jika kondisi terpenuhi.
    Aman dipanggil berulang kali — tidak membuat duplikat notifikasi yang belum dibaca."""
    now = datetime.utcnow()
    try:
        projects = _get("project_requests", {"select":"*","order":"updated_at.desc","limit":"500"})
    except:
        return
    active_ids = [p["id"] for p in projects if p.get("status") not in ("deal","lost")]

    for p in projects:
        pid = p["id"]; branch = p.get("branch","")
        status = p.get("status","")
        created = p.get("created_at","")
        updated = p.get("updated_at","")
        try: created_dt = datetime.fromisoformat(created.replace("Z",""))
        except: created_dt = now
        try: updated_dt = datetime.fromisoformat(updated.replace("Z",""))
        except: updated_dt = now

        if status == "deal" or status == "lost":
            continue

        # Project baru (< 10 menit, belum direview)
        if status == "new_request" and (now - created_dt) < timedelta(minutes=10):
            _push_notif(pid, "new_request", f"Project baru {p.get('project_number','')} dari {p.get('customer_name','')}", branch)

        # PM belum review > 1 hari
        if status == "review_pm" and (now - updated_dt) > timedelta(days=1):
            _push_notif(pid, "pm_late", f"PM belum review project {p.get('project_number','')} sejak {(now-updated_dt).days} hari", branch)

        # Supplier belum update > 2 hari
        if status == "supplier_sourcing" and (now - updated_dt) > timedelta(days=2):
            _push_notif(pid, "supplier_late", f"Supplier belum diupdate untuk {p.get('project_number','')} sejak {(now-updated_dt).days} hari", branch)

        # Quotation belum dikirim > 3 hari
        if status == "waiting_quotation" and (now - updated_dt) > timedelta(days=3):
            _push_notif(pid, "quotation_late", f"Quotation belum dikirim untuk {p.get('project_number','')} sejak {(now-updated_dt).days} hari", branch)

        # Tidak ada follow up > 7 hari (untuk project yang sudah lewat tahap awal)
        if status not in ("new_request","review_pm") :
            try: fus = get_followups(pid)
            except: fus = []
            last_fu_dt = None
            if fus:
                try: last_fu_dt = max(datetime.fromisoformat((f.get("created_at","") or "").replace("Z","")) for f in fus)
                except: last_fu_dt = None
            ref_dt = last_fu_dt or updated_dt
            if (now - ref_dt) > timedelta(days=7):
                _push_notif(pid, "followup_late", f"Tidak ada follow up untuk {p.get('project_number','')} sejak {(now-ref_dt).days} hari", branch)

        # Project hampir deadline (<=3 hari lagi)
        deadline = p.get("deadline")
        if deadline:
            try:
                dl = datetime.fromisoformat(deadline)
                if timedelta(0) <= (dl - now) <= timedelta(days=3):
                    _push_notif(pid, "deadline_near", f"Project {p.get('project_number','')} deadline dalam {(dl-now).days} hari", branch)
            except: pass

        # Status berbasis event tunggal (PO diterima, delivered, closed)
        if status == "ordered":
            _push_notif(pid, "po_received", f"PO diterima untuk {p.get('project_number','')}", branch)
        if status == "delivered":
            _push_notif(pid, "delivered", f"Barang datang untuk {p.get('project_number','')}", branch)

    log_system(None, "System", "notification_run", f"{len(active_ids)} project aktif dicek")

def get_notifications(unread_only=True, branch=None, limit=100):
    params = {"order":"created_at.desc","limit":str(limit),"select":"*"}
    if unread_only: params["is_read"] = "is.false"
    if branch: params["branch"] = f"eq.{branch}"
    try: return _get("project_notifications", params)
    except: return []

def mark_notification_read(notif_id):
    try: _patch("project_notifications", {"id": str(notif_id)}, {"is_read": True})
    except: pass

def mark_all_notifications_read(branch=None):
    try:
        rows = get_notifications(unread_only=True, branch=branch, limit=500)
        for r in rows:
            _patch("project_notifications", {"id": str(r["id"])}, {"is_read": True})
    except: pass
