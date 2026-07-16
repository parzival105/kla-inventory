import re, io
import numpy as np
import pandas as pd
from modules.config import (COLUMN_ALIASES, ALL_BRANCHES, AREA_MAP, BRANCH_TO_AREA,
    BRANCH_FULL, CATEGORY_THRESHOLDS, DEAD_STOCK_BUCKETS, PC_CATEGORIES, fmt_rupiah)

def normalize(v): return re.sub(r"[^a-z0-9]+", " ", str(v).lower()).strip()
def safe_num(s, fill=0.0): return pd.to_numeric(s, errors="coerce").fillna(fill)
def safe_div(n, d, default=0.0):
    try: return n/d if d!=0 else default
    except: return default

def detect_col_map(columns):
    lk={normalize(c):c for c in columns}; result={}
    for canon, variants in COLUMN_ALIASES.items():
        for v in variants:
            if normalize(v) in lk: result[canon]=lk[normalize(v)]; break
        if canon in result: continue
        for nk,ok in lk.items():
            for v in variants:
                nv=normalize(v)
                if nv and (nv in nk or nk in nv): result[canon]=ok; break
            if canon in result: break
    return result

def detect_branches(columns):
    sc,sl={},{}
    for col in columns:
        n=normalize(col)
        for br in sorted(ALL_BRANCHES,key=len,reverse=True):
            bl=br.lower()
            if re.search(rf"(?<![a-z0-9]){bl}(?![a-z0-9])",n):
                is_sales=any(k in n for k in ["terjual","sold","sales","jual"]) or col.endswith(".1")
                if is_sales: sl.setdefault(br,col)
                else: sc.setdefault(br,col)
                break
    return sc,sl

EXCL_KW=["laptop","notebook","pc","aio","tablet","display","bonus","cabutan","service","jasa"]

def analyze(file_bytes, filename="stock.xlsx"):
    from datetime import datetime
    raw=pd.read_excel(io.BytesIO(file_bytes),engine="openpyxl")
    col_map=detect_col_map(list(raw.columns))
    sc,sl=detect_branches(list(raw.columns))
    if "hpp" not in col_map or "total_stok" not in col_map:
        raise ValueError("Kolom HPP atau Total Stok tidak ditemukan. Cek format file Excel.")
    df=raw.rename(columns={v:k for k,v in col_map.items()}).copy()
    if "nama_barang" not in df.columns: df=df.rename(columns={df.columns[0]:"nama_barang"})
    before=len(df)
    mask=~df["nama_barang"].apply(lambda x: any(kw in normalize(x) for kw in EXCL_KW))
    if "kategori_produk" in df.columns:
        mask&=~df["kategori_produk"].apply(lambda x: any(kw in normalize(x) for kw in EXCL_KW))
    df=df[mask].copy(); rows_excl=before-len(df)
    for col in ["hpp","hd","h1","h2","total_stok","total_terjual"]+list(sc.values())+list(sl.values()):
        if col in df.columns: df[col]=safe_num(df[col])
    df["runrate_bulanan"]=(safe_num(df.get("total_terjual",pd.Series([0]*len(df))))/6).round(2)
    MULT={name:m for name,_,_,m in CATEGORY_THRESHOLDS}
    def _cat(rr):
        for name,lo,hi,_ in CATEGORY_THRESHOLDS:
            if lo<=rr<hi: return name
        return "Dead Stock"
    df["kategori"]=df["runrate_bulanan"].apply(_cat)
    df["min_stock"]=df.apply(lambda r: round(r["runrate_bulanan"]*MULT.get(r["kategori"],0)),axis=1)
    df["coverage_month"]=df.apply(lambda r: round(safe_div(r["total_stok"],r["runrate_bulanan"],999 if r["total_stok"]>0 else 0),2),axis=1)
    df["stock_day"]=(df["coverage_month"]*30).round(0)
    df["nilai_inventory"]=df["total_stok"]*df["hpp"]
    df["qty_restock"]=(df["min_stock"]-df["total_stok"]).clip(lower=0)
    df["nilai_restock"]=df["qty_restock"]*df["hpp"]
    tier={"Very Fast":"h2","Fast":"h1","Slow":"hd","Dead Stock":"hd"}
    def _price(row):
        col=tier.get(row["kategori"],"hd"); v=row.get(col,0)
        if pd.isna(v) or v<=0:
            for fb in ["hd","h1","h2"]:
                fv=row.get(fb,0)
                if fv and fv>0: return fv
            return row.get("hpp",0)
        return v
    df["harga_rekomendasi"]=df.apply(_price,axis=1)
    df["margin_nominal"]=df["harga_rekomendasi"]-df["hpp"]
    df["margin_persen"]=np.where(df["harga_rekomendasi"]>0,(df["margin_nominal"]/df["harga_rekomendasi"]*100).round(2),0.0)
    df["potensi_profit"]=df["margin_nominal"]*df["total_stok"]
    bl=_branch_long(df,sc,sl)
    bs=_branch_summary(bl) if not bl.empty else pd.DataFrame()
    bs=_health(bs) if not bs.empty else bs
    tf=_transfers(bl) if not bl.empty else pd.DataFrame()
    raw_cols=list(set(sc.values())|set(sl.values()))
    df=df.drop(columns=[c for c in raw_cols if c in df.columns])
    dead=_dead(df)
    rev=_revenue(df,dead,tf)
    recs=_recs(df,dead,tf,bs,rev)
    comps,comp_list=_extract_comps(raw,sc)
    return {"df":df.reset_index(drop=True),"branch_long":bl,"branch_summary":bs,"transfer":tf,"dead_stock":dead,"stock_columns":sc,"sales_columns":sl,"revenue":rev,"recommendations":recs,"rows_excluded":rows_excl,"uploaded_at":datetime.now().isoformat(),"filename":filename,"components":comp_list,"component_count":comps}

def _branch_long(df,sc,sl):
    if not sc: return pd.DataFrame()
    nc="nama_barang"; n=max(len(sc),1); records=[]
    for _,row in df.iterrows():
        kat=row.get("kategori","Slow"); hpp=row.get("hpp",0); rr=row.get("runrate_bulanan",0)
        MULT={name:m for name,_,_,m in CATEGORY_THRESHOLDS}
        for br,scol in sc.items():
            stok=row.get(scol,0) if scol in row.index else 0
            br_rr=round((row.get(sl[br],0)/6) if br in sl and sl[br] in row.index else rr/n,2)
            min_s=round(br_rr*MULT.get(kat,0)); cov=safe_div(stok,br_rr,999 if stok>0 else 0)
            records.append({"nama_barang":row.get(nc,""),"kategori":kat,"hpp":hpp,"branch":br,"area":BRANCH_TO_AREA.get(br,""),"stok_cabang":stok,"runrate_cabang":br_rr,"min_stock_cabang":min_s,"coverage_cabang":round(cov,2),"stock_day_cabang":round(cov*30)})
    return pd.DataFrame(records)

def _branch_status(row):
    sd=row["stock_day_cabang"]; ms=row["min_stock_cabang"]; stok=row["stok_cabang"]
    if sd<30 and ms>0: return "Critical"
    if ms<=0: return "Normal" if stok==0 else "Overstock"
    ratio=stok/ms
    return "Overstock" if ratio>1.5 else "Understock" if ratio<0.8 else "Normal"

def _branch_summary(df):
    df=df.copy(); df["status"]=df.apply(_branch_status,axis=1); rows=[]
    for br,grp in df.groupby("branch"):
        grp=grp.copy(); grp["ni"]=grp["stok_cabang"]*grp["hpp"]
        dead=grp[grp["kategori"]=="Dead Stock"]; sc=grp["status"].value_counts().to_dict()
        rows.append({"branch":br,"branch_name":BRANCH_FULL.get(br,br),"area":BRANCH_TO_AREA.get(br,""),"total_sku":grp["nama_barang"].nunique(),"total_stok":grp["stok_cabang"].sum(),"inventory_value":grp["ni"].sum(),"dead_stock_value":(dead["stok_cabang"]*dead["hpp"]).sum(),"fast_moving_sku":grp[grp["kategori"].isin(["Very Fast","Fast"])]["nama_barang"].nunique(),"dead_stock_sku":dead["nama_barang"].nunique(),"overstock_count":sc.get("Overstock",0),"normal_count":sc.get("Normal",0),"understock_count":sc.get("Understock",0),"critical_count":sc.get("Critical",0)})
    return pd.DataFrame(rows)

def _health(df):
    def _sc(row):
        total=max(row["total_sku"],1)
        fa=safe_div(row["fast_moving_sku"],total)*100; dr=safe_div(row["dead_stock_sku"],total)*100
        cr=safe_div(row["critical_count"],total)*100; or_=safe_div(row["overstock_count"],total)*100
        return round(max(0,min(100,fa*0.25+(100-dr)*0.25+(100-cr)*0.20+(100-or_)*0.15+(100-max(cr,0))*0.15)),1)
    df=df.copy(); df["health_score"]=df.apply(_sc,axis=1)
    df=df.sort_values("health_score",ascending=False).reset_index(drop=True); df["rank"]=df.index+1; return df

def _transfers(df):
    if df.empty: return pd.DataFrame()
    df=df.copy(); df["surplus"]=(df["stok_cabang"]-df["min_stock_cabang"]).clip(lower=0); df["deficit"]=(df["min_stock_cabang"]-df["stok_cabang"]).clip(lower=0)
    records=[]
    for (prod,area),grp in df.groupby(["nama_barang","area"]):
        donors=grp[grp["surplus"]>0].sort_values("surplus",ascending=False); receivers=grp[grp["deficit"]>0].sort_values("deficit",ascending=False)
        if donors.empty or receivers.empty: continue
        pool=donors.set_index("branch")["surplus"].to_dict(); kat=grp["kategori"].iloc[0]; hpp=grp["hpp"].iloc[0]
        for _,recv in receivers.iterrows():
            needed=recv["deficit"]
            for db in list(pool.keys()):
                avail=pool[db]
                if avail<=0 or needed<=0: continue
                qty=min(needed,avail); records.append({"nama_barang":prod,"kategori":kat,"area":area,"dari_cabang":db,"ke_cabang":recv["branch"],"qty_transfer":qty,"hpp":hpp,"nilai_transfer":qty*hpp}); pool[db]-=qty; needed-=qty
    return pd.DataFrame(records) if records else pd.DataFrame()

def _dead(df):
    dead=df[df["kategori"]=="Dead Stock"].copy()
    if dead.empty: return dead
    dead["dead_stock_value"]=dead["total_stok"]*dead["hpp"]
    def _age(row): return round(row["total_stok"]/row["runrate_bulanan"],1) if row["runrate_bulanan"]>0 else (99.0 if row["total_stok"]>0 else 0.0)
    dead["estimasi_bulan"]=dead.apply(_age,axis=1)
    def _act(m):
        for lo,hi,act,rsn in DEAD_STOCK_BUCKETS:
            if lo<=m<hi: return act,rsn
        return "Monitor","Baru masuk dead stock."
    ar=dead["estimasi_bulan"].apply(_act)
    dead["rekomendasi_aksi"]=ar.apply(lambda x:x[0]); dead["alasan"]=ar.apply(lambda x:x[1])
    return dead.sort_values("dead_stock_value",ascending=False).reset_index(drop=True)

def _revenue(df,dead,tf):
    iv=float(df["nilai_inventory"].sum()) if "nilai_inventory" in df.columns else 0
    dv=float(dead["dead_stock_value"].sum()) if not dead.empty else 0
    rv=float(df["nilai_restock"].sum()) if "nilai_restock" in df.columns else 0
    tv=float(tf["nilai_transfer"].sum()) if not tf.empty else 0
    profit=float(df["potensi_profit"].sum()) if "potensi_profit" in df.columns else 0
    revenue=float((df["harga_rekomendasi"]*df["total_stok"]).sum()) if "harga_rekomendasi" in df.columns else 0
    return {"inventory_value":iv,"dead_stock_value":dv,"dead_stock_pct":(dv/iv*100) if iv else 0,"transfer_value":tv,"restock_value":rv,"potential_profit":profit,"potential_revenue":revenue,"total_sku":len(df),"fast_sku":int(df["kategori"].isin(["Very Fast","Fast"]).sum()) if "kategori" in df.columns else 0,"dead_sku":int((df["kategori"]=="Dead Stock").sum()) if "kategori" in df.columns else 0}

def _recs(df,dead,tf,bs,rev):
    recs=[]
    rs=df[df["qty_restock"]>0].sort_values("nilai_restock",ascending=False).head(4) if "qty_restock" in df.columns else pd.DataFrame()
    for _,r in rs.iterrows():
        recs.append({"category":"Purchasing","priority":"Tinggi","icon":"🛒","text":f"Tambah {r.get('nama_barang','')} — stok {r.get('stock_day',0):.0f} hari, runrate {r.get('runrate_bulanan',0):.0f}/bulan."})
    for _,r in (tf.nlargest(4,"nilai_transfer").iterrows() if not tf.empty else []):
        recs.append({"category":"Transfer","priority":"Sedang","icon":"🔄","text":f"Transfer {r['qty_transfer']:.0f}x {r['nama_barang']} {r['dari_cabang']}→{r['ke_cabang']}, hemat {fmt_rupiah(r['nilai_transfer'])}."})
    for _,r in df[df["kategori"]=="Very Fast"].nlargest(3,"runrate_bulanan").iterrows():
        recs.append({"category":"Pricing","priority":"Sedang","icon":"📈","text":f"Naikkan {r.get('nama_barang','')} ke H2 — {r['runrate_bulanan']:.0f}/bulan."})
    if not dead.empty:
        for act,icon in [("Clearance","🚨"),("Bundling","📦"),("Turunkan ke HD","🔽")]:
            for _,r in dead[dead["rekomendasi_aksi"]==act].head(2).iterrows():
                recs.append({"category":"Dead Stock","priority":"Tinggi" if act=="Clearance" else "Sedang","icon":icon,"text":f"{act}: {r.get('nama_barang','')} — {r.get('estimasi_bulan',0):.0f} bulan, modal {fmt_rupiah(r.get('dead_stock_value',0))}."})
    if not bs.empty:
        recs.append({"category":"Branch","priority":"Tinggi","icon":"⚠️","text":f"Cabang {bs.iloc[-1]['branch_name']} Health Score terendah ({bs.iloc[-1]['health_score']:.0f}/100)."})
    dp=rev.get("dead_stock_pct",0)
    if dp>30: recs.append({"category":"Revenue","priority":"Tinggi","icon":"🔴","text":f"Dead stock {dp:.1f}% ({fmt_rupiah(rev.get('dead_stock_value',0))}) — kondisi kritis."})
    elif dp>15: recs.append({"category":"Revenue","priority":"Sedang","icon":"🟡","text":f"Dead stock {dp:.1f}% — waspadai tren kenaikan."})
    return recs

def _extract_comps(raw_df,sc):
    comps=[]; cat_col=next((c for c in raw_df.columns if any(a in str(c).lower() for a in ["kategori barang","kategori","category"])),None)
    if not cat_col: return 0,[]
    for pc_cat in PC_CATEGORIES:
        subset=raw_df[raw_df[cat_col].astype(str).str.upper().str.strip()==pc_cat.upper()].copy()
        for _,row in subset.iterrows():
            nama=str(row.get("Nama Barang",row.get("nama_barang",""))).strip()
            if not nama: continue
            def gv(*keys):
                for k in keys:
                    v=row.get(k)
                    if v is not None and str(v).strip() not in ("","nan"):
                        try: return float(v)
                        except: pass
                return 0.0
            bs={br:int(float(row.get(col,0) or 0)) for br,col in sc.items() if int(float(row.get(col,0) or 0))>0}
            comps.append({"nama_barang":nama,"kategori":pc_cat,"brand":str(row.get("Merek",row.get("brand",""))or""),"hpp":gv("HPP","hpp"),"h1":gv("H1","h1"),"h2":gv("H2","h2"),"total_stok":int(gv("Total Stoks","total_stok")),"branch_stock":bs,"is_available":gv("Total Stoks","total_stok")>0})
    return len(comps),comps
