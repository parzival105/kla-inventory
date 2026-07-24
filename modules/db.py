import hashlib, secrets, requests, streamlit as st
from datetime import datetime, timedelta
from modules.config import SUPABASE_URL, SUPABASE_KEY, ROLE_LABELS, BRANCH_FULL, AREA_MAP, ALL_BRANCHES

def _h():
    return {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json","Prefer":"return=representation"}

def _get(table, params={}):
    r=requests.get(f"{SUPABASE_URL}/rest/v1/{table}",headers=_h(),params=params,timeout=10)
    if r.status_code==401: raise Exception("Supabase 401 — periksa SUPABASE_SERVICE_KEY di Secrets")
    r.raise_for_status(); return r.json()

def _post(table, data):
    r=requests.post(f"{SUPABASE_URL}/rest/v1/{table}",headers=_h(),json=data,timeout=10)
    r.raise_for_status(); res=r.json(); return res[0] if isinstance(res,list) and res else res

def _patch(table, filters, data):
    params={k:f"eq.{v}" for k,v in filters.items()}
    r=requests.patch(f"{SUPABASE_URL}/rest/v1/{table}",headers=_h(),params=params,json=data,timeout=10)
    r.raise_for_status(); return r.json()

def _delete(table, filters):
    params={k:f"eq.{v}" for k,v in filters.items()}
    requests.delete(f"{SUPABASE_URL}/rest/v1/{table}",headers=_h(),params=params,timeout=10)

def hash_pw(pw): return hashlib.sha256(f"kla_salt_{pw}_kla2025".encode()).hexdigest()

def login(username, password):
    rows=_get("users",{"username":f"eq.{username.lower().strip()}","is_active":"is.true","select":"*"})
    if not rows: return False, None
    user=rows[0]
    if hash_pw(password)!=user["password_hash"]: return False, None
    token=secrets.token_urlsafe(32)
    _post("sessions",{"token":token,"user_id":user["id"],"expires_at":(datetime.utcnow()+timedelta(hours=8)).isoformat()+"Z"})
    try: _patch("users",{"id":user["id"]},{"last_login":datetime.utcnow().isoformat()+"Z"})
    except: pass
    return True, user

def validate_token(token):
    if not token: return None
    from datetime import datetime
    try:
        rows = _get("sessions", {"token": f"eq.{token}", "select": "*"})
        if not rows: return None
        session = rows[0]
        exp = session["expires_at"].replace("Z","").replace("+00:00","")
        if datetime.fromisoformat(exp) < datetime.utcnow():
            try: _delete("sessions", {"token": token})
            except: pass
            return None
        users = _get("users", {"id": f"eq.{session['user_id']}", "is_active": "is.true", "select": "*"})
        if not users: return None
        user = users[0]
        from modules.config import ROLE_LABELS, BRANCH_FULL
        user["role_label"] = ROLE_LABELS.get(user.get("role",""), "")
        user["branch_name"] = BRANCH_FULL.get(user.get("branch",""), "")
        return user
    except: return None

def logout(token):
    if not token: return
    try: _delete("sessions", {"token": token})
    except: pass

def get_all_users():
    users=_get("users",{"order":"role.asc,full_name.asc","select":"*"})
    for u in users:
        u["branch_name"]=BRANCH_FULL.get(u.get("branch",""),""); u["role_label"]=ROLE_LABELS.get(u.get("role",""),"")
    return users

def create_user(username,password,full_name,role,branch=None,area=None):
    try:
        _post("users",{"username":username.lower(),"password_hash":hash_pw(password),"full_name":full_name,"role":role,"branch":branch,"area":area,"is_active":True,"created_at":datetime.utcnow().isoformat()+"Z"})
        return True,"User berhasil dibuat."
    except Exception as e:
        msg=str(e); return False,"Username sudah digunakan." if "unique" in msg.lower() else msg

def update_user(uid,full_name,role,branch=None,area=None,is_active=True,new_pw=None):
    try:
        data={"full_name":full_name,"role":role,"branch":branch,"area":area,"is_active":is_active}
        if new_pw: data["password_hash"]=hash_pw(new_pw)
        _patch("users",{"id":uid},data); return True,"User diupdate."
    except Exception as e: return False,str(e)

def deactivate_user(uid):
    try: _patch("users",{"id":uid},{"is_active":False}); return True,"User dinonaktifkan."
    except Exception as e: return False,str(e)

def save_analysis_meta(filename,uploaded_by,sku_count):
    try: _delete("analysis_store",{"id":"1"})
    except: pass
    _post("analysis_store",{"id":1,"filename":filename,"uploaded_by":uploaded_by,"sku_count":sku_count,"uploaded_at":datetime.utcnow().isoformat()+"Z"})

def get_analysis_meta():
    try: rows=_get("analysis_store",{"id":"eq.1","select":"*"}); return rows[0] if rows else None
    except: return None

def save_build_history(user_id,branch,build_name,build_type,budget,total_price,ai_notes):
    import json
    _post("build_history",{"user_id":user_id,"branch":branch,"build_name":build_name,"build_type":build_type,"budget":budget,"total_price":total_price,"ai_notes":ai_notes[:500],"created_at":datetime.utcnow().isoformat()+"Z"})

def log_action(user_id,username,action,detail=""):
    try: _post("audit_log",{"user_id":user_id,"username":username,"action":action,"detail":detail,"created_at":datetime.utcnow().isoformat()+"Z"})
    except: pass

# ── Branch Management ─────────────────────────────────────────────────────────
def get_branches(active_only=True):
    params = {"order": "area.asc,code.asc", "select": "*"}
    if active_only: params["is_active"] = "is.true"
    return _get("branches", params)

def add_branch(code, name, area):
    try:
        _post("branches", {"code": code.upper().strip(), "name": name.strip(), "area": area, "is_active": True})
        return True, f"Cabang {code.upper()} berhasil ditambahkan."
    except Exception as e:
        msg = str(e)
        return False, "Kode cabang sudah ada." if "unique" in msg.lower() else msg

def update_branch(code, name, area, is_active):
    try:
        _patch("branches", {"code": code}, {"name": name.strip(), "area": area, "is_active": is_active})
        return True, "Cabang diupdate."
    except Exception as e: return False, str(e)

def deactivate_branch(code):
    try:
        _patch("branches", {"code": code}, {"is_active": False})
        return True, f"Cabang {code} dinonaktifkan."
    except Exception as e: return False, str(e)

# ── Online Presence ───────────────────────────────────────────────────────────
def update_presence(user):
    """Update last_seen user. Dipanggil tiap render."""
    try:
        from datetime import datetime
        data = {
            "user_id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "branch": user.get("branch",""),
            "last_seen": datetime.utcnow().isoformat() + "Z"
        }
        # Upsert
        import requests as _req
        h = {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}",
             "Content-Type":"application/json","Prefer":"resolution=merge-duplicates"}
        _req.post(f"{SUPABASE_URL}/rest/v1/online_presence",
                  headers=h, json=data, timeout=5)
    except: pass

def get_online_users(minutes=3):
    """Ambil user yang aktif dalam N menit terakhir."""
    try:
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat() + "Z"
        rows = _get("online_presence", {
            "last_seen": f"gte.{cutoff}",
            "order": "last_seen.desc",
            "select": "*"
        })
        return rows
    except: return []

def remove_presence(user_id):
    """Hapus presence saat logout."""
    try: _delete("online_presence", {"user_id": str(user_id)})
    except: pass
