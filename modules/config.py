import streamlit as st

# Supabase
SUPABASE_URL = st.secrets.get("SUPABASE_URL","")
SUPABASE_KEY = st.secrets.get("SUPABASE_SERVICE_KEY","")
ANTHROPIC_KEY = st.secrets.get("ANTHROPIC_API_KEY","")

# Default branches (fallback jika Supabase belum setup)
_DEFAULT_BRANCHES = [
    {"code":"SMG","name":"Semarang","area":"Area 2 — Jawa Tengah Timur"},
    {"code":"YK","name":"Yogyakarta","area":"Area 2 — Jawa Tengah Timur"},
    {"code":"SLA","name":"Slawi","area":"Area 1 — Jawa Tengah Barat"},
    {"code":"TGL","name":"Tegal","area":"Area 1 — Jawa Tengah Barat"},
    {"code":"PKL","name":"Pekalongan","area":"Area 1 — Jawa Tengah Barat"},
    {"code":"CRB","name":"Cirebon","area":"Area 1 — Jawa Tengah Barat"},
    {"code":"KDR","name":"Kediri","area":"Area 3 — Jawa Timur"},
    {"code":"NGL","name":"Ngaliyan","area":"Area 2 — Jawa Tengah Timur"},
    {"code":"SKH","name":"Sukoharjo","area":"Area 2 — Jawa Tengah Timur"},
    {"code":"MSBY","name":"Surabaya Merr","area":"Area 3 — Jawa Timur"},
    {"code":"MJK","name":"Mojokerto","area":"Area 3 — Jawa Timur"},
    {"code":"BSBY","name":"Surabaya Babatan","area":"Area 3 — Jawa Timur"},
    {"code":"PWT","name":"Purwokerto","area":"Area 1 — Jawa Tengah Barat"},
]

def get_branch_config():
    """Ambil konfigurasi cabang dari Supabase, fallback ke default."""
    try:
        import requests
        h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        r = requests.get(f"{SUPABASE_URL}/rest/v1/branches?is_active=is.true&order=area.asc,code.asc&select=*", headers=h, timeout=5)
        if r.status_code == 200 and r.json():
            rows = r.json()
            branches = rows
        else:
            branches = _DEFAULT_BRANCHES
    except:
        branches = _DEFAULT_BRANCHES

    all_b = [b["code"] for b in branches]
    full  = {b["code"]: b["name"] for b in branches}
    area_map = {}
    for b in branches:
        area_map.setdefault(b["area"], []).append(b["code"])
    branch_to_area = {b["code"]: b["area"] for b in branches}
    return all_b, full, area_map, branch_to_area

# Load saat startup — cached di module level
_bc = get_branch_config()
ALL_BRANCHES    = _bc[0]
BRANCH_FULL     = _bc[1]
AREA_MAP        = _bc[2]
BRANCH_TO_AREA  = _bc[3]
EXCLUDED_BRANCH_COLS = ["HO"]
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
