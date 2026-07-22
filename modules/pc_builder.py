import re
from modules.config import PC_CATEGORIES, BRANCH_FULL, fmt_rupiah

# Panduan Kompatibilitas dari Kompatible_komponen.xlsx

INTEL_RULES = [
    {"kw":["g1820","g1840","g3220","g3240","g3258","i3 4","i5 4","i7 4"],
     "socket":"LGA1150","chipsets":["H81","B85","H97","Z97"],"ram":"DDR3"},
    {"kw":["i5 5","i7 5","5675","5775"],
     "socket":"LGA1150","chipsets":["H97","Z97"],"ram":"DDR3"},
    {"kw":["g3900","g3920","g4400","g4500","g4520","i3 6","i5 6","i7 6"],
     "socket":"LGA1151","chipsets":["H110","B150","H170","Z170"],"ram":"DDR4"},
    {"kw":["g4560","g4600","g4620","i3 7","i5 7","i7 7"],
     "socket":"LGA1151","chipsets":["H110","B250","H270","Z270"],"ram":"DDR4"},
    {"kw":["g5400","g5500","i3 8","i5 8","i7 8"],
     "socket":"LGA1151-v2","chipsets":["H310","B360","H370","Z370"],"ram":"DDR4"},
    {"kw":["g5420","i3 9","i5 9","i7 9","i9 9"],
     "socket":"LGA1151-v2","chipsets":["H310","B365","Z390"],"ram":"DDR4"},
    {"kw":["g5900","g6400","g6500","i3 10","i5 10","i7 10","i9 10"],
     "socket":"LGA1200","chipsets":["H410","B460","H470","Z490"],"ram":"DDR4"},
    {"kw":["i5 11","i7 11","i9 11"],
     "socket":"LGA1200","chipsets":["H510","B560","Z590"],"ram":"DDR4"},
    {"kw":["i3 12","i5 12","i7 12","i9 12"],
     "socket":"LGA1700","chipsets":["H610","B660","Z690"],"ram":"DDR4/DDR5"},
    {"kw":["i3 13","i5 13","i7 13","i9 13"],
     "socket":"LGA1700","chipsets":["H610","B760","Z790"],"ram":"DDR4/DDR5"},
    {"kw":["i3 14","i5 14","i7 14","i9 14"],
     "socket":"LGA1700","chipsets":["H610","B760","Z790"],"ram":"DDR4/DDR5"},
    {"kw":["ultra 5","ultra 7","ultra 9","245k","265k","285k","250k","270k"],
     "socket":"LGA1851","chipsets":["B860","Z890"],"ram":"DDR5"},
]

AMD_RULES = [
    {"kw":["athlon x2","athlon ii","phenom"],
     "socket":"AM3","chipsets":["760G","880G","970"],"ram":"DDR3"},
    {"kw":["fx-4","fx-6","fx-8","fx-9","fx 4","fx 6","fx 8","fx 9"],
     "socket":"AM3+","chipsets":["970","990X","990FX"],"ram":"DDR3"},
    {"kw":["200ge","220ge","240ge","3000g"],
     "socket":"AM4","chipsets":["A320","B450"],"ram":"DDR4"},
    {"kw":["ryzen 3 1","ryzen 5 1","ryzen 7 1","1200","1300x","1400","1500x","1600","1700","1800x"],
     "socket":"AM4","chipsets":["A320","B350","X370"],"ram":"DDR4"},
    {"kw":["ryzen 3 2","ryzen 5 2","ryzen 7 2","2200g","2400g","2600","2700"],
     "socket":"AM4","chipsets":["B450","X470"],"ram":"DDR4"},
    {"kw":["ryzen 3 3","ryzen 5 3","ryzen 7 3","ryzen 9 3","3100","3300","3500","3600","3700","3800","3900","3950"],
     "socket":"AM4","chipsets":["B450","B550","X570"],"ram":"DDR4"},
    {"kw":["ryzen 5 5","ryzen 7 5","ryzen 9 5","5500","5600","5700","5800","5900","5950"],
     "socket":"AM4","chipsets":["B450","B550","X570"],"ram":"DDR4"},
    {"kw":["ryzen 5 7","ryzen 7 7","ryzen 9 7","7500f","7600","7700","7800","7900","7950"],
     "socket":"AM5","chipsets":["A620","B650","X670"],"ram":"DDR5"},
    {"kw":["8500g","8600g","8700g","ryzen 5 8","ryzen 7 8"],
     "socket":"AM5","chipsets":["A620","B650"],"ram":"DDR5"},
    {"kw":["9600x","9700x","9800x","9900x","9950x","ryzen 5 9","ryzen 7 9","ryzen 9 9"],
     "socket":"AM5","chipsets":["B650","B850","X870"],"ram":"DDR5"},
]

MB_CHIPSET_SOCKET = {
    "h81":"LGA1150","b85":"LGA1150","h97":"LGA1150","z97":"LGA1150",
    "h110":"LGA1151","b150":"LGA1151","h170":"LGA1151","z170":"LGA1151",
    "b250":"LGA1151","h270":"LGA1151","z270":"LGA1151",
    "h310":"LGA1151-v2","b360":"LGA1151-v2","h370":"LGA1151-v2","z370":"LGA1151-v2",
    "b365":"LGA1151-v2","z390":"LGA1151-v2",
    "h410":"LGA1200","b460":"LGA1200","h470":"LGA1200","z490":"LGA1200",
    "h510":"LGA1200","b560":"LGA1200","z590":"LGA1200",
    "h610":"LGA1700","b660":"LGA1700","z690":"LGA1700",
    "b760":"LGA1700","z790":"LGA1700",
    "b860":"LGA1851","z890":"LGA1851",
    "760g":"AM3","880g":"AM3","970":"AM3+","990x":"AM3+","990fx":"AM3+",
    "a320":"AM4","b350":"AM4","x370":"AM4","b450":"AM4","x470":"AM4",
    "b550":"AM4","x570":"AM4",
    "a620":"AM5","b650":"AM5","x670":"AM5","b850":"AM5","x870":"AM5",
}

PSU_MIN = {
    "rtx 4090":850,"rtx 4080":750,"rtx 4070 ti":700,"rtx 4070":650,
    "rtx 4060 ti":600,"rtx 4060":550,
    "rtx 3090":850,"rtx 3080":750,"rtx 3070":650,"rtx 3060":550,
    "rx 7900":750,"rx 7800":650,"rx 7700":600,"rx 7600":550,
}

def _n(v): return re.sub(r"[^a-z0-9]+", " ", str(v).lower()).strip()

def _find_cpu_rule(cpu_name):
    cn = _n(cpu_name)
    for rule in INTEL_RULES:
        if any(kw in cn for kw in rule["kw"]):
            return "intel", rule
    for rule in AMD_RULES:
        if any(kw in cn for kw in rule["kw"]):
            return "amd", rule
    return None, None

def _find_mb_socket(mb_name):
    mn = _n(mb_name)
    for chip, sock in MB_CHIPSET_SOCKET.items():
        if chip in mn:
            return sock, chip.upper()
    return "", ""

def check_compat(comps):
    names = {c.get("kategori",""): c.get("nama_barang", c.get("nama","")) for c in comps}
    cpu_name = names.get("PROCESSOR","")
    mb_name  = names.get("MOTHERBOARD","")
    ram_name = names.get("RAM LONGDIMM", names.get("RAM SODIMM",""))
    gpu_name = names.get("GRAPHIC CARD","")
    psu_name = names.get("POWER SUPPLY","")
    notes=[]; warnings=[]

    brand, rule = _find_cpu_rule(cpu_name)
    mb_sock, mb_chip = _find_mb_socket(mb_name)

    if rule and mb_sock:
        cpu_sock = rule["socket"]
        valid_chips = [c.lower() for c in rule["chipsets"]]
        req_ram = rule["ram"]

        sock_ok = (cpu_sock == mb_sock)
        if sock_ok:
            chip_ok = any(ch in _n(mb_name) for ch in valid_chips)
            if chip_ok:
                notes.append("OK CPU-MB kompatibel (" + cpu_sock + ", chipset sesuai panduan)")
            else:
                warnings.append("PERHATIAN Chipset MB tidak sesuai panduan. Chipset yang cocok: " + ", ".join(rule["chipsets"]))
        else:
            warnings.append("TIDAK COCOK CPU socket " + cpu_sock + " tidak cocok dengan MB socket " + mb_sock + ". Ganti motherboard!")

        if ram_name:
            rn = _n(ram_name)
            ram_type = "DDR5" if "ddr5" in rn else "DDR4" if "ddr4" in rn else "DDR3" if "ddr3" in rn else ""
            if ram_type:
                if ram_type in req_ram:
                    notes.append("OK RAM " + ram_type + " kompatibel")
                else:
                    warnings.append("TIDAK COCOK RAM " + ram_type + " tidak cocok - butuh " + req_ram)
    elif cpu_name and not rule:
        notes.append("INFO CPU tidak ditemukan dalam panduan kompatibilitas")

    if psu_name and gpu_name:
        pn = _n(psu_name); gn = _n(gpu_name)
        pw = re.search(r"(\d{3,4})\s*w", pn)
        min_w = next((w for kw,w in PSU_MIN.items() if kw in gn), 0)
        if pw and min_w:
            watt = int(pw.group(1))
            if watt >= min_w: notes.append("OK PSU " + str(watt) + "W cukup untuk GPU ini")
            else: warnings.append("PERHATIAN PSU " + str(watt) + "W kurang - GPU ini butuh minimal " + str(min_w) + "W")

    return notes, warnings

BUILD_PROFILES = {
    "Office / Kerja":       {"needs_gpu":False,"alloc":{"PROCESSOR":.30,"MOTHERBOARD":.20,"RAM LONGDIMM":.15,"SSD INTERNAL":.13,"CASING PC":.10,"POWER SUPPLY":.09,"INTERNAL COOLER":.03}},
    "Gaming Entry":         {"needs_gpu":True, "alloc":{"PROCESSOR":.18,"MOTHERBOARD":.15,"RAM LONGDIMM":.10,"SSD INTERNAL":.10,"GRAPHIC CARD":.28,"CASING PC":.08,"POWER SUPPLY":.08,"INTERNAL COOLER":.03}},
    "Gaming Mid-range":     {"needs_gpu":True, "alloc":{"PROCESSOR":.17,"MOTHERBOARD":.14,"RAM LONGDIMM":.10,"SSD INTERNAL":.09,"GRAPHIC CARD":.32,"CASING PC":.08,"POWER SUPPLY":.07,"INTERNAL COOLER":.03}},
    "Gaming High-end":      {"needs_gpu":True, "alloc":{"PROCESSOR":.16,"MOTHERBOARD":.13,"RAM LONGDIMM":.10,"SSD INTERNAL":.08,"GRAPHIC CARD":.37,"CASING PC":.07,"POWER SUPPLY":.06,"INTERNAL COOLER":.03}},
    "Desain Grafis":        {"needs_gpu":True, "alloc":{"PROCESSOR":.22,"MOTHERBOARD":.14,"RAM LONGDIMM":.13,"SSD INTERNAL":.10,"GRAPHIC CARD":.25,"CASING PC":.07,"POWER SUPPLY":.06,"INTERNAL COOLER":.03}},
    "Video Editing":        {"needs_gpu":True, "alloc":{"PROCESSOR":.24,"MOTHERBOARD":.13,"RAM LONGDIMM":.15,"SSD INTERNAL":.12,"GRAPHIC CARD":.22,"CASING PC":.07,"POWER SUPPLY":.05,"INTERNAL COOLER":.02}},
    "Coding / Development": {"needs_gpu":False,"alloc":{"PROCESSOR":.28,"MOTHERBOARD":.18,"RAM LONGDIMM":.18,"SSD INTERNAL":.14,"CASING PC":.10,"POWER SUPPLY":.09,"INTERNAL COOLER":.03}},
    "Workstation":          {"needs_gpu":True, "alloc":{"PROCESSOR":.25,"MOTHERBOARD":.15,"RAM LONGDIMM":.18,"SSD INTERNAL":.10,"GRAPHIC CARD":.20,"CASING PC":.06,"POWER SUPPLY":.05,"INTERNAL COOLER":.01}},
}
BUILD_PRIORITY = {
    "Office / Kerja":       ["PROCESSOR","MOTHERBOARD","RAM LONGDIMM","SSD INTERNAL","CASING PC","POWER SUPPLY","INTERNAL COOLER"],
    "Gaming Entry":         ["GRAPHIC CARD","PROCESSOR","RAM LONGDIMM","SSD INTERNAL","MOTHERBOARD","POWER SUPPLY","CASING PC","INTERNAL COOLER"],
    "Gaming Mid-range":     ["GRAPHIC CARD","PROCESSOR","RAM LONGDIMM","SSD INTERNAL","MOTHERBOARD","POWER SUPPLY","CASING PC","INTERNAL COOLER"],
    "Gaming High-end":      ["GRAPHIC CARD","PROCESSOR","RAM LONGDIMM","MOTHERBOARD","SSD INTERNAL","POWER SUPPLY","CASING PC","INTERNAL COOLER"],
    "Desain Grafis":        ["PROCESSOR","RAM LONGDIMM","GRAPHIC CARD","SSD INTERNAL","MOTHERBOARD","POWER SUPPLY","CASING PC","INTERNAL COOLER"],
    "Video Editing":        ["PROCESSOR","RAM LONGDIMM","SSD INTERNAL","GRAPHIC CARD","MOTHERBOARD","POWER SUPPLY","CASING PC","INTERNAL COOLER"],
    "Coding / Development": ["PROCESSOR","RAM LONGDIMM","SSD INTERNAL","MOTHERBOARD","CASING PC","POWER SUPPLY","INTERNAL COOLER"],
    "Workstation":          ["PROCESSOR","RAM LONGDIMM","MOTHERBOARD","GRAPHIC CARD","SSD INTERNAL","POWER SUPPLY","CASING PC","INTERNAL COOLER"],
}

def _select(components, cat, target, remaining, brand=None):
    avail = [c for c in components
             if c.get("kategori","").upper()==cat.upper()
             and c.get("is_available",True)
             and float(c.get("h1",0))>0
             and float(c.get("h1",0))<=remaining]
    if not avail: return None
    if brand:
        bm = [c for c in avail if brand.lower() in _n(c.get("nama_barang",""))]
        if bm: avail = bm
    within = [c for c in avail if float(c.get("h1",0))<=target]
    return max(within, key=lambda c: float(c["h1"])) if within else min(avail, key=lambda c: float(c["h1"]))

def _select_compatible_mb(components, cpu_comp, target, remaining):
    all_mb = [c for c in components
              if c.get("kategori","").upper()=="MOTHERBOARD"
              and float(c.get("h1",0))>0
              and float(c.get("h1",0))<=remaining]
    if not all_mb: return None
    cpu_name = cpu_comp.get("nama_barang","") if cpu_comp else ""
    _, rule = _find_cpu_rule(cpu_name)
    if rule:
        valid_chips = [ch.lower() for ch in rule["chipsets"]]
        compat = [mb for mb in all_mb if any(ch in _n(mb.get("nama_barang","")) for ch in valid_chips)]
        if compat:
            within = [mb for mb in compat if float(mb["h1"])<=target]
            return max(within, key=lambda c: float(c["h1"])) if within else min(compat, key=lambda c: float(c["h1"]))
    within = [mb for mb in all_mb if float(mb["h1"])<=target]
    return max(within, key=lambda c: float(c["h1"])) if within else min(all_mb, key=lambda c: float(c["h1"]))

def build_pc(components, build_type, budget, preferred_brand=None):
    profile = BUILD_PROFILES.get(build_type)
    if not profile: return None
    alloc = profile["alloc"]
    prio  = BUILD_PRIORITY.get(build_type, list(alloc.keys()))
    needs_gpu = profile["needs_gpu"]
    selected = {}; remaining = budget; warnings = []
    cpu_comp = None

    for cat in prio:
        if cat not in alloc: continue
        if cat == "GRAPHIC CARD" and not needs_gpu: continue
        target = budget * alloc[cat]
        if cat == "MOTHERBOARD" and cpu_comp:
            comp = _select_compatible_mb(components, cpu_comp, target, remaining)
        else:
            comp = _select(components, cat, target, remaining,
                           preferred_brand if cat=="PROCESSOR" else None)
        if comp:
            c = dict(comp)
            c["kategori"]       = cat
            c["kategori_label"] = PC_CATEGORIES.get(cat, cat)
            c["selling_price"]  = float(c.get("h1",0))
            c.setdefault("nama_barang", c.get("nama",""))
            selected[cat] = c
            remaining -= c["selling_price"]
            if cat == "PROCESSOR": cpu_comp = c
        else:
            warnings.append("Tidak ada " + PC_CATEGORIES.get(cat,cat) + " tersedia di budget ini")

    if not selected: return None
    comps = list(selected.values())
    notes, warns = check_compat(comps)
    total_hpp   = sum(float(c.get("hpp",0)) for c in comps)
    total_price = sum(float(c.get("selling_price",0)) for c in comps)
    margin = (total_price-total_hpp)/total_price*100 if total_price>0 else 0
    return {
        "build_type":build_type,"budget":budget,
        "total_hpp":total_hpp,"total_price":total_price,
        "margin_persen":round(margin,2),
        "is_within_budget":total_price<=budget*1.05,
        "sisa_budget":max(0,budget-total_price),
        "components":comps,"compat_notes":notes,
        "compat_warnings":warns,"build_warnings":warnings,
    }

def build_alternatives(components, build_type, budget):
    return [a for f in [0.85,1.15] if (a:=build_pc(components,build_type,budget*f))]
