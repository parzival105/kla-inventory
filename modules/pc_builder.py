import re
from modules.config import PC_CATEGORIES, BRANCH_FULL, fmt_rupiah

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
SOCKET_MAP={"i3-12":"LGA1700","i5-12":"LGA1700","i7-12":"LGA1700","i9-12":"LGA1700","i3-13":"LGA1700","i5-13":"LGA1700","i7-13":"LGA1700","i3-14":"LGA1700","i5-14":"LGA1700","i7-14":"LGA1700","ryzen 9000":"AM5","ryzen 8000":"AM5","ryzen 7000":"AM5","ryzen 5000":"AM4","ryzen 3000":"AM4","z790":"LGA1700","b760":"LGA1700","b660":"LGA1700","z690":"LGA1700","b550":"AM4","x570":"AM4","b650":"AM5","x670":"AM5"}
PLATFORM_RAM={"LGA1700":["DDR4","DDR5"],"LGA1200":["DDR4"],"AM5":["DDR5"],"AM4":["DDR4"]}
PSU_MIN={"rtx 4090":850,"rtx 4080":750,"rtx 4070":650,"rtx 4060":550,"rtx 3080":750,"rtx 3070":650,"rtx 3060":550}

def _n(v): return re.sub(r"[^a-z0-9]+", " ", str(v).lower()).strip()

def check_compat(comps):
    names={c["kategori"]:c["nama"] for c in comps}
    cpu=names.get("PROCESSOR","").lower(); mb=names.get("MOTHERBOARD","").lower()
    ram=names.get("RAM LONGDIMM",names.get("RAM SODIMM","")).lower()
    gpu=names.get("GRAPHIC CARD","").lower(); psu=names.get("POWER SUPPLY","").lower()
    notes=[]; warnings=[]
    cpu_s=next((s for k,s in SOCKET_MAP.items() if k in cpu),"")
    mb_s=next((s for k,s in SOCKET_MAP.items() if k in mb),"")
    if cpu_s and mb_s:
        if cpu_s==mb_s: notes.append(f"✅ CPU-MB kompatibel ({cpu_s})")
        else: warnings.append(f"⚠️ CPU {cpu_s} tidak cocok MB {mb_s}")
    rt="DDR5" if "ddr5" in ram else "DDR4" if "ddr4" in ram else ""
    if rt and cpu_s in PLATFORM_RAM:
        if rt in PLATFORM_RAM[cpu_s]: notes.append(f"✅ RAM {rt} kompatibel")
        else: warnings.append(f"⚠️ RAM {rt} tidak cocok — butuh {', '.join(PLATFORM_RAM[cpu_s])}")
    if psu and gpu:
        pw=re.search(r"(\d{3,4})\s*w",psu); min_w=next((w for k,w in PSU_MIN.items() if k in gpu),0)
        if pw and min_w:
            w=int(pw.group(1))
            if w>=min_w: notes.append(f"✅ PSU {w}W cukup")
            else: warnings.append(f"⚠️ PSU {w}W kurang — butuh ≥{min_w}W")
    return notes, warnings

def build_pc(components, build_type, budget, preferred_brand=None):
    profile=BUILD_PROFILES.get(build_type)
    if not profile: return None
    alloc=profile["alloc"]; prio=BUILD_PRIORITY.get(build_type,list(alloc.keys())); needs_gpu=profile["needs_gpu"]
    selected={}; remaining=budget; warnings=[]
    for cat in prio:
        if cat not in alloc or (cat=="GRAPHIC CARD" and not needs_gpu): continue
        comp=_select(components,cat,budget*alloc[cat],remaining,preferred_brand if cat=="PROCESSOR" else None)
        if comp: selected[cat]=comp; remaining-=float(comp["h1"])
        else: warnings.append(f"Tidak ada {PC_CATEGORIES.get(cat,cat)} di budget ini")
    if not selected: return None
    comps=list(selected.values()); notes,warns=check_compat(comps)
    total_hpp=sum(float(c.get("hpp",0)) for c in comps); total_price=sum(float(c["h1"]) for c in comps)
    margin=(total_price-total_hpp)/total_price*100 if total_price>0 else 0
    return {"build_type":build_type,"budget":budget,"total_hpp":total_hpp,"total_price":total_price,"margin_persen":round(margin,2),"is_within_budget":total_price<=budget*1.05,"components":comps,"compat_notes":notes,"compat_warnings":warns,"build_warnings":warnings,"sisa_budget":max(0,budget-total_price)}

def _select(components, cat, target, remaining, brand=None):
    avail=[c for c in components if c.get("kategori","").upper()==cat.upper() and c.get("is_available",True) and float(c.get("h1",0))>0 and float(c.get("h1",0))<=remaining]
    if not avail: return None
    if brand:
        bm=[c for c in avail if brand.lower() in _n(c["nama_barang"])]
        if bm: avail=bm
    within=[c for c in avail if float(c["h1"])<=target]
    return max(within,key=lambda c:float(c["h1"])) if within else min(avail,key=lambda c:float(c["h1"]))

def build_alternatives(components, build_type, budget):
    alts=[]
    for factor in [0.85,1.15]:
        alt=build_pc(components,build_type,budget*factor)
        if alt: alts.append(alt)
    return alts
