import json, requests
from modules.config import SUPABASE_URL, SUPABASE_KEY
BUCKET="kla-inventory"

def _sh(ct="application/octet-stream"):
    return {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":ct}

def upload(data,path,ct="application/octet-stream"):
    url=f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    r=requests.post(url,headers=_sh(ct),data=data,params={"upsert":"true"},timeout=60)
    if r.status_code not in (200,201):
        r2=requests.put(url,headers=_sh(ct),data=data,timeout=60); r2.raise_for_status()

def download(path):
    url=f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    r=requests.get(url,headers=_sh(),timeout=30)
    if r.status_code==404: return None
    r.raise_for_status(); return r.content

def save_analysis(analysis):
    def _j(df):
        if df is None or (hasattr(df,"empty") and df.empty): return "[]"
        try: return df.to_json(orient="records")
        except: return "[]"
    payload={"df":_j(analysis["df"]),"branch_long":_j(analysis.get("branch_long")),"branch_summary":_j(analysis.get("branch_summary")),"transfer":_j(analysis.get("transfer")),"dead_stock":_j(analysis.get("dead_stock")),"stock_columns":analysis.get("stock_columns",{}),"sales_columns":analysis.get("sales_columns",{}),"revenue":analysis.get("revenue",{}),"recommendations":analysis.get("recommendations",[]),"uploaded_at":analysis.get("uploaded_at",""),"filename":analysis.get("filename","")}
    upload(json.dumps(payload,ensure_ascii=False,default=str).encode("utf-8"),"analysis/current.json","application/json")

def load_analysis():
    import pandas as pd
    data=download("analysis/current.json")
    if not data: return None
    try:
        p=json.loads(data.decode("utf-8"))
        def _df(k):
            raw=p.get(k,"[]")
            if not raw or raw=="[]": return pd.DataFrame()
            try: return pd.DataFrame(json.loads(raw))
            except: return pd.DataFrame()
        return {"df":_df("df"),"branch_long":_df("branch_long"),"branch_summary":_df("branch_summary"),"transfer":_df("transfer"),"dead_stock":_df("dead_stock"),"stock_columns":p.get("stock_columns",{}),"sales_columns":p.get("sales_columns",{}),"revenue":p.get("revenue",{}),"recommendations":p.get("recommendations",[]),"uploaded_at":p.get("uploaded_at",""),"filename":p.get("filename","")}
    except: return None

def save_components(comps):
    upload(json.dumps(comps,ensure_ascii=False,default=str).encode("utf-8"),"components/current.json","application/json")

def load_components():
    data=download("components/current.json")
    if not data: return []
    try: return json.loads(data.decode("utf-8"))
    except: return []
