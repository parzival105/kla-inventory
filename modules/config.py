import streamlit as st

# Supabase
SUPABASE_URL = st.secrets.get("SUPABASE_URL","")
SUPABASE_KEY = st.secrets.get("SUPABASE_SERVICE_KEY","")
ANTHROPIC_KEY = st.secrets.get("ANTHROPIC_API_KEY","")

ALL_BRANCHES = ["SMG","YK","SLA","TGL","PKL","CRB","KDR","NGL","SKH","MSBY","MJK","BSBY","PWT"]
EXCLUDED_BRANCH_COLS = ["HO","SOLO","TSM"]
AREA_MAP = {
    "Area 1 — Jawa Tengah Barat": ["CRB","PWT","SLA","TGL","PKL"],
    "Area 2 — Jawa Tengah Timur": ["SMG","NGL","YK","SKH"],
    "Area 3 — Jawa Timur":        ["KDR","MJK","MSBY","BSBY"],
}
BRANCH_TO_AREA = {b:a for a,bs in AREA_MAP.items() for b in bs}
BRANCH_FULL = {
    "SMG":"Semarang","YK":"Yogyakarta","SLA":"Slawi","TGL":"Tegal",
    "PKL":"Pekalongan","CRB":"Cirebon","KDR":"Kediri","NGL":"Ngaliyan",
    "SKH":"Sukoharjo","MSBY":"Surabaya Merr","MJK":"Mojokerto",
    "BSBY":"Surabaya Babatan","PWT":"Purwokerto",
}
ROLE_LABELS = {"super_admin":"Super Admin","area_manager":"Area Manager","store_leader":"Store Leader","sales":"Sales"}
CATEGORY_THRESHOLDS = [("Very Fast",25,float("inf"),2.0),("Fast",15,25,1.5),("Slow",4,15,1.0),("Dead Stock",0,4,0.0)]
DEAD_STOCK_BUCKETS = [(3,6,"Turunkan ke HD","Stok 3-6 bulan"),(6,12,"Bundling","Stok 6-12 bulan"),(12,float("inf"),"Clearance","Stok >12 bulan")]
COLUMN_ALIASES = {
    "nama_barang":["nama barang","nama_barang","product name","item","barang"],
    "kategori_produk":["kategori barang","kategori","category","jenis barang"],
    "segment":["segment","segmen","tipe"],"brand":["merek","brand","merk"],
    "hpp":["hpp","harga pokok","cost","modal"],"hd":["hd","h.d.","harga dasar"],
    "h1":["h1","harga 1"],"h2":["h2","harga 2"],
    "total_stok":["total stoks","total stok","total stock","stok total"],
    "total_terjual":["total terjual","total sold","terjual"],
}
PC_CATEGORIES = {
    "PROCESSOR":"Processor","MOTHERBOARD":"Motherboard","RAM SODIMM":"RAM (Laptop)",
    "RAM LONGDIMM":"RAM (Desktop)","SSD INTERNAL":"SSD","HDD INTERNAL":"HDD",
    "GRAPHIC CARD":"Graphic Card","CASING PC":"Casing","POWER SUPPLY":"Power Supply","INTERNAL COOLER":"CPU Cooler",
}
BUILD_TYPES = ["Office / Kerja","Gaming Entry","Gaming Mid-range","Gaming High-end","Desain Grafis","Video Editing","Coding / Development","Workstation"]

def fmt_rupiah(v):
    try:
        v=float(v); s="-" if v<0 else ""; a=abs(v)
        if a>=1e9: return f"{s}Rp {a/1e9:.2f}M"
        if a>=1e6: return f"{s}Rp {a/1e6:.1f}Jt"
        if a>=1e3: return f"{s}Rp {a/1e3:.0f}Rb"
        return f"{s}Rp {a:,.0f}"
    except: return "Rp 0"
