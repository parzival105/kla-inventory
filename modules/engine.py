import re, io
import numpy as np
import pandas as pd
from modules.config import (COLUMN_ALIASES, ALL_BRANCHES, AREA_MAP, BRANCH_TO_AREA,
    BRANCH_FULL, CATEGORY_THRESHOLDS, DEAD_STOCK_BUCKETS, PC_CATEGORIES, fmt_rupiah)

EXCL_KW = ["laptop","notebook","pc","aio","tablet","display","bonus","cabutan","service","jasa"]
RUNRATE_MONTHS = 6

def normalize(v): return re.sub(r"[^a-z0-9]+", " ", str(v).lower()).strip()

def detect_col_map(columns):
    lk = {normalize(c): c for c in columns}
    result = {}
    for canon, variants in COLUMN_ALIASES.items():
        for v in variants:
            nv = normalize(v)
            if nv in lk: result[canon] = lk[nv]; break
        if canon in result: continue
        for nk, ok in lk.items():
            for v in variants:
                nv = normalize(v)
                if nv and (nv in nk or nk in nv): result[canon] = ok; break
            if canon in result: break
    return result

def detect_branches(columns):
    sc, sl = {}, {}
    for col in columns:
        col_base = col.replace(".1","").replace(".2","").strip()
        nb = normalize(col_base)
        is_sales = col.endswith(".1") or col.endswith(".2") or any(k in normalize(col) for k in ["terjual","sold","sales","jual"])
        for br in sorted(ALL_BRANCHES, key=len, reverse=True):
            if re.search(rf"(?<![a-z0-9]){br.lower()}(?![a-z0-9])", nb):
                if is_sales: sl.setdefault(br, col)
                else: sc.setdefault(br, col)
                break
    return sc, sl

def categorize_series(rr_series):
    result = pd.Series("Dead Stock", index=rr_series.index)
    for name, lo, hi, _ in reversed(CATEGORY_THRESHOLDS):
        mask = (rr_series >= lo) & (rr_series < hi)
        result[mask] = name
    return result

def analyze(file_bytes, filename="stock.xlsx"):
    from datetime import datetime

    raw = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl", header=1, dtype_backend='numpy_nullable')
    col_map = detect_col_map(list(raw.columns))
    sc, sl = detect_branches(list(raw.columns))

    if "hpp" not in col_map or "total_stok" not in col_map:
        raise ValueError("Kolom HPP atau Total Stok tidak ditemukan.")

    df = raw.rename(columns={v: k for k, v in col_map.items()}).copy()
    if "nama_barang" not in df.columns:
        df = df.rename(columns={df.columns[0]: "nama_barang"})

    # Filter excluded keywords — vectorized
    name_lower = df["nama_barang"].fillna("").str.lower()
    mask = ~name_lower.apply(lambda x: any(kw in x for kw in EXCL_KW))
    if "kategori_produk" in df.columns:
        kat_lower = df["kategori_produk"].fillna("").str.lower()
        mask &= ~kat_lower.apply(lambda x: any(kw in x for kw in EXCL_KW))
    rows_excl = (~mask).sum()
    df = df[mask].copy().reset_index(drop=True)

    # Numeric conversion — vectorized
    num_cols = ["hpp","hd","h1","h2","total_stok","total_terjual"] + list(sc.values()) + list(sl.values())
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Runrate & category — vectorized
    total_terjual = df.get("total_terjual", pd.Series(0, index=df.index))
    df["runrate_bulanan"] = (total_terjual / RUNRATE_MONTHS).round(2)
    df["kategori"] = categorize_series(df["runrate_bulanan"])

    MULT = {name: m for name, _, _, m in CATEGORY_THRESHOLDS}
    mult_map = df["kategori"].map(MULT).fillna(0)
    df["min_stock"] = (df["runrate_bulanan"] * mult_map).round(0).astype(int)

    # Stock day — vectorized, avoid division by zero
    safe_rr = df["runrate_bulanan"].replace(0, np.nan)
    cov = (df["total_stok"] / safe_rr).clip(upper=999)
    default_cov = pd.Series(np.where(df["total_stok"] > 0, 999, 0), index=df.index, dtype=float)
    df["coverage_month"] = cov.fillna(default_cov).round(2)
    df["stock_day"] = (df["coverage_month"] * 30).round(0)

    df["nilai_inventory"] = df["total_stok"] * df["hpp"]
    df["qty_restock"] = (df["min_stock"] - df["total_stok"]).clip(lower=0)
    df["nilai_restock"] = df["qty_restock"] * df["hpp"]

    # Harga rekomendasi — vectorized
    tier_map = {"Very Fast":"h2","Fast":"h1","Slow":"hd","Dead Stock":"hd"}
    def get_harga(row):
        col = tier_map.get(row["kategori"],"hd")
        v = row.get(col, 0)
        if pd.isna(v) or v <= 0:
            for fb in ["hd","h1","h2"]:
                fv = row.get(fb, 0)
                if fv and fv > 0: return fv
            return row.get("hpp", 0)
        return v
    df["harga_rekomendasi"] = df.apply(get_harga, axis=1)
    df["margin_nominal"] = df["harga_rekomendasi"] - df["hpp"]
    df["margin_persen"] = np.where(df["harga_rekomendasi"] > 0,
        (df["margin_nominal"] / df["harga_rekomendasi"] * 100).round(2), 0.0)
    df["potensi_profit"] = df["margin_nominal"] * df["total_stok"]

    # Branch analysis — vectorized via melt
    bl = _branch_long_fast(df, sc, sl)
    bs = _branch_summary(bl) if not bl.empty else pd.DataFrame()
    bs = _health(bs) if not bs.empty else bs
    tf = _transfers_fast(bl) if not bl.empty else pd.DataFrame()

    # Simpan stok per cabang sebagai dict
    def _make_branch_stock(row):
        d = {}
        for br, col in sc.items():
            if col in row.index:
                try:
                    qty = int(float(row[col] or 0))
                    if qty > 0: d[br] = qty
                except: pass
        return d
    df["branch_stock"] = df.apply(_make_branch_stock, axis=1)

    # Drop hanya kolom sales (.1) bukan kolom stok cabang
    # Kolom stok cabang tetap ada untuk referensi
    sl_cols = list(set(sl.values()))
    df = df.drop(columns=[c for c in sl_cols if c in df.columns])

    dead = _dead(df)
    rev  = _revenue(df, dead, tf)
    recs = _recs(df, dead, tf, bs, rev)
    comp_count, comp_list = _extract_comps(raw, sc)

    return {
        "df": df.reset_index(drop=True),
        "branch_long": bl,
        "branch_summary": bs,
        "transfer": tf,
        "dead_stock": dead,
        "stock_columns": sc,
        "sales_columns": sl,
        "revenue": rev,
        "recommendations": recs,
        "rows_excluded": int(rows_excl),
        "uploaded_at": datetime.now().isoformat(),
        "filename": filename,
        "components": comp_list,
        "component_count": comp_count,
    }

def _branch_long_fast(df, sc, sl):
    if not sc: return pd.DataFrame()
    n = max(len(sc), 1)
    frames = []
    for br, scol in sc.items():
        if scol not in df.columns: continue
        tmp = pd.DataFrame({
            "nama_barang": df["nama_barang"],
            "kategori": df["kategori"],
            "hpp": df["hpp"],
            "branch": br,
            "area": BRANCH_TO_AREA.get(br, ""),
            "stok_cabang": df[scol].fillna(0),
        })
        # Runrate per cabang
        if br in sl and sl[br] in df.columns:
            tmp["runrate_cabang"] = (df[sl[br]].fillna(0) / 6).round(2)
        else:
            tmp["runrate_cabang"] = (df["runrate_bulanan"] / n).round(2)
        MULT = {name: m for name, _, _, m in CATEGORY_THRESHOLDS}
        tmp["min_stock_cabang"] = (tmp["runrate_cabang"] * tmp["kategori"].map(MULT).fillna(0)).round(0).astype(int)
        safe = tmp["runrate_cabang"].replace(0, np.nan)
        cov2 = (tmp["stok_cabang"] / safe).clip(upper=999)
        default_cov2 = pd.Series(np.where(tmp["stok_cabang"] > 0, 999, 0), index=tmp.index, dtype=float)
        tmp["coverage_cabang"] = cov2.fillna(default_cov2).round(2)
        tmp["stock_day_cabang"] = (tmp["coverage_cabang"] * 30).round(0)
        frames.append(tmp)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def _branch_status_vec(df):
    sd = df["stock_day_cabang"]; ms = df["min_stock_cabang"]; stok = df["stok_cabang"]
    ratio = stok / ms.replace(0, np.nan)
    status = pd.Series("Normal", index=df.index)
    status[(ms <= 0) & (stok > 0)] = "Overstock"
    status[(ms > 0) & (ratio > 1.5)] = "Overstock"
    status[(ms > 0) & (ratio < 0.8)] = "Understock"
    status[(sd < 30) & (ms > 0)] = "Critical"
    return status

def _branch_summary(df):
    df = df.copy()
    df["status"] = _branch_status_vec(df)
    df["ni"] = df["stok_cabang"] * df["hpp"]
    dead = df[df["kategori"] == "Dead Stock"]
    grp = df.groupby("branch")
    dead_grp = dead.groupby("branch")
    status_grp = df.groupby(["branch","status"]).size().unstack(fill_value=0)
    bs = grp.agg(
        branch_name=("branch", lambda x: BRANCH_FULL.get(x.iloc[0], x.iloc[0])),
        area=("area", "first"),
        total_sku=("nama_barang", "nunique"),
        total_stok=("stok_cabang", "sum"),
        inventory_value=("ni", "sum"),
        fast_moving_sku=("nama_barang", lambda x: df.loc[x.index][df.loc[x.index,"kategori"].isin(["Very Fast","Fast"])]["nama_barang"].nunique()),
    ).reset_index()
    for col in ["Overstock","Normal","Understock","Critical"]:
        bs[f"{col.lower()}_count"] = bs["branch"].map(status_grp.get(col, pd.Series(dtype=int))).fillna(0).astype(int)
    dead_val = dead.groupby("branch").apply(lambda x: (x["stok_cabang"]*x["hpp"]).sum()) if not dead.empty else pd.Series(dtype=float)
    dead_sku = dead.groupby("branch")["nama_barang"].nunique() if not dead.empty else pd.Series(dtype=int)
    bs["dead_stock_value"] = bs["branch"].map(dead_val).fillna(0)
    bs["dead_stock_sku"] = bs["branch"].map(dead_sku).fillna(0).astype(int)
    return bs

def _health(df):
    def _sc(row):
        total = max(row["total_sku"], 1)
        fa = row["fast_moving_sku"] / total * 100
        dr = row["dead_stock_sku"] / total * 100
        cr = row["critical_count"] / total * 100
        or_ = row["overstock_count"] / total * 100
        return round(max(0, min(100, fa*0.25 + (100-dr)*0.25 + (100-cr)*0.20 + (100-or_)*0.15 + (100-cr)*0.15)), 1)
    df = df.copy()
    df["health_score"] = df.apply(_sc, axis=1)
    df = df.sort_values("health_score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df

def _transfers_fast(df):
    if df.empty: return pd.DataFrame()
    df = df.copy()
    df["surplus"] = (df["stok_cabang"] - df["min_stock_cabang"]).clip(lower=0)
    df["deficit"]  = (df["min_stock_cabang"] - df["stok_cabang"]).clip(lower=0)

    donors    = df[df["surplus"] > 0][["nama_barang","area","branch","surplus","kategori","hpp"]].copy()
    receivers = df[df["deficit"]  > 0][["nama_barang","area","branch","deficit"]].copy()
    if donors.empty or receivers.empty: return pd.DataFrame()

    # Cross-join donors x receivers per (nama_barang, area), exclude same branch
    merged = donors.merge(receivers, on=["nama_barang","area"], suffixes=("_d","_r"))
    merged = merged[merged["branch_d"] != merged["branch_r"]].copy()
    if merged.empty: return pd.DataFrame()

    # Transfer qty = min(surplus, deficit) — take top match per receiver
    merged["qty_transfer"] = merged[["surplus","deficit"]].min(axis=1)
    merged = merged[merged["qty_transfer"] > 0]

    # Deduplicate: each donor can only donate once, pick largest transfer first
    merged = merged.sort_values("qty_transfer", ascending=False)
    merged = merged.drop_duplicates(subset=["nama_barang","area","branch_d"])
    merged = merged.drop_duplicates(subset=["nama_barang","area","branch_r"])

    result = merged.rename(columns={"branch_d":"dari_cabang","branch_r":"ke_cabang"})[
        ["nama_barang","kategori","area","dari_cabang","ke_cabang","qty_transfer","hpp"]].copy()
    result["nilai_transfer"] = result["qty_transfer"] * result["hpp"]
    return result.reset_index(drop=True)

def _dead(df):
    dead = df[df["kategori"] == "Dead Stock"].copy()
    if dead.empty: return dead
    dead["dead_stock_value"] = dead["total_stok"] * dead["hpp"]
    safe = dead["runrate_bulanan"].replace(0, np.nan)
    est = (dead["total_stok"] / safe)
    default_est = pd.Series(np.where(dead["total_stok"] > 0, 99, 0), index=dead.index, dtype=float)
    dead["estimasi_bulan"] = est.fillna(default_est).round(1)
    def _act(m):
        for lo, hi, act, rsn in DEAD_STOCK_BUCKETS:
            if lo <= m < hi: return act, rsn
        return "Monitor", "Baru masuk dead stock."
    ar = dead["estimasi_bulan"].apply(_act)
    dead["rekomendasi_aksi"] = ar.apply(lambda x: x[0])
    dead["alasan"] = ar.apply(lambda x: x[1])
    return dead.sort_values("dead_stock_value", ascending=False).reset_index(drop=True)

def _revenue(df, dead, tf):
    iv = float(df["nilai_inventory"].sum()) if "nilai_inventory" in df.columns else 0
    dv = float(dead["dead_stock_value"].sum()) if not dead.empty else 0
    rv = float(df["nilai_restock"].sum()) if "nilai_restock" in df.columns else 0
    tv = float(tf["nilai_transfer"].sum()) if not tf.empty else 0
    profit = float(df["potensi_profit"].sum()) if "potensi_profit" in df.columns else 0
    revenue = float((df["harga_rekomendasi"] * df["total_stok"]).sum()) if "harga_rekomendasi" in df.columns else 0
    return {"inventory_value":iv,"dead_stock_value":dv,"dead_stock_pct":(dv/iv*100) if iv else 0,
        "transfer_value":tv,"restock_value":rv,"potential_profit":profit,"potential_revenue":revenue,
        "total_sku":len(df),"fast_sku":int(df["kategori"].isin(["Very Fast","Fast"]).sum()),
        "dead_sku":int((df["kategori"]=="Dead Stock").sum())}

def _recs(df, dead, tf, bs, rev):
    recs = []
    rs = df[df["qty_restock"]>0].nlargest(4,"nilai_restock") if "qty_restock" in df.columns else pd.DataFrame()
    for _,r in rs.iterrows():
        recs.append({"category":"Purchasing","priority":"Tinggi","icon":"🛒","text":f"Tambah {r.get('nama_barang','')} — stok {r.get('stock_day',0):.0f} hari, runrate {r.get('runrate_bulanan',0):.0f}/bulan."})
    if not tf.empty:
        for _,r in tf.nlargest(4,"nilai_transfer").iterrows():
            recs.append({"category":"Transfer","priority":"Sedang","icon":"🔄","text":f"Transfer {r['qty_transfer']:.0f}x {r['nama_barang']} {r['dari_cabang']}→{r['ke_cabang']}, hemat {fmt_rupiah(r['nilai_transfer'])}."})
    for _,r in df[df["kategori"]=="Very Fast"].nlargest(3,"runrate_bulanan").iterrows():
        recs.append({"category":"Pricing","priority":"Sedang","icon":"📈","text":f"Naikkan {r.get('nama_barang','')} ke H2 — {r['runrate_bulanan']:.0f}/bulan."})
    if not dead.empty:
        for act,icon in [("Clearance","🚨"),("Bundling","📦"),("Turunkan ke HD","🔽")]:
            for _,r in dead[dead["rekomendasi_aksi"]==act].head(2).iterrows():
                recs.append({"category":"Dead Stock","priority":"Tinggi" if act=="Clearance" else "Sedang","icon":icon,"text":f"{act}: {r.get('nama_barang','')} — {r.get('estimasi_bulan',0):.0f} bulan, modal {fmt_rupiah(r.get('dead_stock_value',0))}."})
    if not bs.empty:
        recs.append({"category":"Branch","priority":"Tinggi","icon":"⚠️","text":f"Cabang {bs.iloc[-1]['branch_name']} Health Score terendah ({bs.iloc[-1]['health_score']:.0f}/100)."})
    dp = rev.get("dead_stock_pct", 0)
    if dp > 30: recs.append({"category":"Revenue","priority":"Tinggi","icon":"🔴","text":f"Dead stock {dp:.1f}% ({fmt_rupiah(rev.get('dead_stock_value',0))}) — kondisi kritis."})
    elif dp > 15: recs.append({"category":"Revenue","priority":"Sedang","icon":"🟡","text":f"Dead stock {dp:.1f}% — waspadai tren kenaikan."})
    if rev.get("transfer_value", 0) > 0:
        recs.append({"category":"Revenue","priority":"Sedang","icon":"💡","text":f"Optimalkan transfer {fmt_rupiah(rev['transfer_value'])} sebelum PO baru."})
    return recs

def _extract_comps(raw_df, sc):
    comps = []
    cat_col = next((c for c in raw_df.columns if any(a in str(c).lower() for a in ["kategori barang","kategori","category"])), None)
    if not cat_col: return 0, []
    for pc_cat in PC_CATEGORIES:
        subset = raw_df[raw_df[cat_col].astype(str).str.upper().str.strip() == pc_cat.upper()].copy()
        for _, row in subset.iterrows():
            nama = str(row.get("Nama Barang", row.get("nama_barang",""))).strip()
            if not nama: continue
            def gv(*keys):
                for k in keys:
                    v = row.get(k)
                    if v is not None and str(v).strip() not in ("","nan"):
                        try: return float(v)
                        except: pass
                return 0.0
            bs = {br: int(float(row.get(col,0) or 0)) for br,col in sc.items() if int(float(row.get(col,0) or 0)) > 0}
            comps.append({"nama_barang":nama,"kategori":pc_cat,"brand":str(row.get("Merek",row.get("brand",""))or""),"hpp":gv("HPP","hpp"),"h1":gv("H1","h1"),"h2":gv("H2","h2"),"total_stok":int(gv("Total Stoks","total_stok")),"branch_stock":bs,"is_available":gv("Total Stoks","total_stok")>0})
    return len(comps), comps

def _branch_status(row):
    sd = row["stock_day_cabang"]; ms = row["min_stock_cabang"]; stok = row["stok_cabang"]
    if sd < 30 and ms > 0: return "Critical"
    if ms <= 0: return "Normal" if stok == 0 else "Overstock"
    ratio = stok / ms
    return "Overstock" if ratio > 1.5 else "Understock" if ratio < 0.8 else "Normal"
