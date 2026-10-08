# -*- coding: utf-8 -*-
"""THUY LOI AI - Unified Reservoir Engine.
Nguồn: CodeZFV2027.xla, gồm curve 2026 và công thức đa thức 2022.
"""
from __future__ import annotations
import json, os, re, unicodedata
from bisect import bisect_right
from typing import Any, Dict, Optional
try:
    from reservoir_q_engine import calculate_spillway_q
except Exception:
    calculate_spillway_q = None

_BASE=os.path.dirname(__file__)
with open(os.path.join(_BASE,"reservoir_curves.json"),"r",encoding="utf-8") as f:
    CURVES: Dict[str,Dict[str,Any]]=json.load(f)
with open(os.path.join(_BASE,"reservoir_legacy_formulas.json"),"r",encoding="utf-8") as f:
    LEGACY: Dict[str,Dict[str,Any]]=json.load(f)

ALIASES={
    "PNinh2026":["phu ninh","phú ninh","ho phu ninh","hồ phú ninh","c24"],
    "ThachBan2026":["thach ban","thạch bàn","ho thach ban","hồ thạch bàn"],
    "TruocDong2026":["truoc dong","trước đông","ho truoc dong","hồ trước đông"],
    "DongTien2026":["dong tien","đồng tiến","ho dong tien","hồ đồng tiến"],
    "DongNghe2026":["dong nghe","đồng nghệ","ho dong nghe","hồ đồng nghệ"],
    "VinhTrinh2026":["vinh trinh","vĩnh trinh","ho vinh trinh","hồ vĩnh trinh"],
    "VietAN2026":["viet an","việt an","ho viet an","hồ việt an"],
    "HocKhe2026":["hoc khe","học khe","ho hoc khe","hồ học khe"],
    "HoCau2026":["ho cau","hồ cầu","ho cau 2026","hồ cầu 2026"],
    "HoaTrung2026":["hoa trung","ho hoa trung","hồ hoa trung"],
}
for rid,meta in LEGACY.items():
    ALIASES.setdefault(rid,[]).extend(meta.get("aliases",[]))

def _norm(s:Any)->str:
    x="" if s is None else str(s)
    x=unicodedata.normalize("NFD",x)
    x="".join(c for c in x if unicodedata.category(c)!="Mn")
    x=x.lower().replace("đ","d")
    return re.sub(r"[^a-z0-9]+"," ",x).strip()

def resolve_reservoir(facility:str)->Optional[str]:
    n=_norm(facility)
    for key,meta in CURVES.items():
        if _norm(meta.get("name"))==n:
            return key
    for key,aliases in ALIASES.items():
        if any(_norm(a) in n for a in aliases):
            # For duplicated 2026 facilities, prefer 2026 curve.
            if key in CURVES: return key
    for key,meta in LEGACY.items():
        if _norm(meta.get("name"))==n:
            return key
    return None

def _linear(x,x1,y1,x2,y2):
    if x2==x1:return y1
    return y1+(x-x1)*(y2-y1)/(x2-x1)

def _interp(x,xs,ys,policy="strict"):
    if not xs or len(xs)!=len(ys): return None,"invalid_curve"
    if x==xs[0]:return ys[0],"exact"
    if x==xs[-1]:return ys[-1],"exact"
    if x<xs[0] or x>xs[-1]:
        if policy=="strict":return None,"out_of_range"
        if policy=="clamp":return (ys[0],"clamped_low") if x<xs[0] else (ys[-1],"clamped_high")
        if x<xs[0]:return _linear(x,xs[0],ys[0],xs[1],ys[1]),"extrapolated_low"
        return _linear(x,xs[-2],ys[-2],xs[-1],ys[-1]),"extrapolated_high"
    i=bisect_right(xs,x)-1
    return _linear(x,xs[i],ys[i],xs[i+1],ys[i+1]),"interpolated"

def _curve_value(meta,z,field):
    return _interp(z,meta["z_m"],meta[field],meta.get("out_of_range","strict"))

def _segment_contains(seg,x):
    lo,hi=seg.get("lo"),seg.get("hi")
    if lo is not None and (x<lo or (x==lo and not seg.get("lo_inc",False))): return False
    if hi is not None and (x>hi or (x==hi and not seg.get("hi_inc",False))): return False
    return True

def _poly(coeff,x):
    y=0.0
    for c in (coeff or []): y=y*x+float(c)
    return y

def _legacy_eval(segments,x):
    for seg in segments:
        if _segment_contains(seg,x):
            coeff=seg.get("coeff_desc")
            if coeff is not None:return _poly(coeff,x),"polynomial"
    return None,"out_of_range"

def _legacy_range(segments):
    vals=[(s.get("lo"),s.get("hi")) for s in segments if s.get("lo") is not None and s.get("hi") is not None]
    return (min(a for a,b in vals),max(b for a,b in vals)) if vals else (None,None)

def _modern_state(meta,z):
    f,fmode=_curve_value(meta,z,"f_m2")
    v,vmode=_curve_value(meta,z,"v_m3")
    return f,fmode,v,vmode,meta["z_m"][0],meta["z_m"][-1]

def _legacy_state(meta,z):
    f,fmode=_legacy_eval(meta.get("f_segments",[]),z)
    v,vmode=_legacy_eval(meta.get("v_segments",[]),z)
    fmin,fmax=_legacy_range(meta.get("f_segments",[]))
    vmin,vmax=_legacy_range(meta.get("v_segments",[]))
    return f,fmode,v,vmode,max(x for x in (fmin,vmin) if x is not None),min(x for x in (fmax,vmax) if x is not None)

def _z_from_volume(meta,volume):
    if meta.get("kind")=="polynomial":
        return _legacy_eval(meta.get("z_segments",[]),volume)
    return _interp(volume,meta["v_m3"],meta["z_m"],meta.get("out_of_range","strict"))

def calculate_state(facility:str,water_level:float,limits:Optional[Dict[str,Any]]=None)->Dict[str,Any]:
    key=resolve_reservoir(facility)
    if not key:
        return {"ok":False,"error":"Chưa có đường quan hệ Z-F-V cho công trình này.","facility":facility}
    z=float(water_level)
    if key in CURVES:
        meta=CURVES[key]; f,fmode,v,vmode,zmin,zmax=_modern_state(meta,z)
    else:
        meta=LEGACY[key]; f,fmode,v,vmode,zmin,zmax=_legacy_state(meta,z)
    q_result = calculate_spillway_q(key, z) if calculate_spillway_q else {"ok":False,"available":False,"q_m3s":None,"reason":"q_engine_unavailable"}
    result={
      "ok":True,"reservoir_id":key,"reservoir":meta.get("name",facility),
      "source_module":meta.get("source_module","CodeZFV2027.xla"),
      "algorithm":meta.get("algorithm","piecewise_polynomial_from_VBA"),
      "out_of_range_policy":meta.get("out_of_range","strict"),
      "water_level_m":z,"area_m2":f,"area_km2":f/1e6 if f is not None else None,
      "volume_m3":v,"volume_million_m3":v/1e6 if v is not None else None,
      "interpolation":{"area":fmode,"volume":vmode},
      "curve_range":{"z_min_m":zmin,"z_max_m":zmax},
      "calculation_engine":"VBA-port-2027",
      "spillway_q": q_result,
      "spillway_state": ("spilling" if q_result.get("q_m3s") is not None and float(q_result.get("q_m3s") or 0) > 0 else ("below_threshold" if q_result.get("available") else "not_configured")),
    }
    limits=limits or {}; mndbt=limits.get("mndbt");mndgc=limits.get("mndgc")
    result["limits"]={"MNDBT":mndbt,"MNDGC":mndgc}
    if mndbt is not None:
        try:
            bt=float(mndbt)
            if key in CURVES:
                fbt,bt_mode=_curve_value(meta,bt,"f_m2");vbt,_=_curve_value(meta,bt,"v_m3")
            else:
                fbt,bt_mode=_legacy_eval(meta.get("f_segments",[]),bt);vbt,_=_legacy_eval(meta.get("v_segments",[]),bt)
            result["mndbt"]={"z_m":bt,"volume_m3":vbt,"volume_million_m3":vbt/1e6 if vbt is not None else None,"area_m2":fbt,"area_km2":fbt/1e6 if fbt is not None else None,"mode":bt_mode}
            if v is not None and vbt is not None:
                result["volume_vs_mndbt_m3"]=v-vbt
                result["fill_percent_vs_mndbt"]=v/vbt*100 if vbt else None
                result["remaining_to_mndbt_m3"]=max(0.0,vbt-v)
        except (TypeError,ValueError): pass
    if mndgc is not None:
        try:
            gc=float(mndgc)
            if key in CURVES:vgc,gc_mode=_curve_value(meta,gc,"v_m3")
            else:vgc,gc_mode=_legacy_eval(meta.get("v_segments",[]),gc)
            result["mndgc"]={"z_m":gc,"volume_m3":vgc,"volume_million_m3":vgc/1e6 if vgc is not None else None,"mode":gc_mode}
            if v is not None and vgc is not None:result["volume_vs_mndgc_m3"]=v-vgc
        except (TypeError,ValueError):pass
    if mndbt is not None and mndgc is not None:
        result["technical_state"]="above_mndgc" if z>float(mndgc) else ("between_mndbt_mndgc" if z>=float(mndbt) else "below_mndbt")
    elif mndbt is not None: result["technical_state"]="at_or_above_mndbt" if z>=float(mndbt) else "below_mndbt"
    else: result["technical_state"]="unknown"
    return result

def calculate_z_from_volume(facility:str,volume_m3:float)->Dict[str,Any]:
    key=resolve_reservoir(facility)
    if not key:return {"ok":False,"error":"Chưa có đường quan hệ V-Z cho công trình này."}
    meta=CURVES.get(key) or LEGACY.get(key)
    z,mode=_z_from_volume(meta,float(volume_m3))
    return {"ok":z is not None,"reservoir_id":key,"reservoir":meta.get("name",facility),"volume_m3":float(volume_m3),"water_level_m":z,"mode":mode,"source_module":meta.get("source_module"),"algorithm":meta.get("algorithm")}

def catalog()->list[dict]:
    out=[]
    for key,meta in CURVES.items():
        out.append({"id":key,"name":meta.get("name",key),"source":meta.get("source_module"),"algorithm":meta.get("algorithm"),"priority":"2026"})
    for key,meta in LEGACY.items():
        out.append({"id":key,"name":meta.get("name",key),"source":meta.get("source_module"),"algorithm":meta.get("algorithm"),"priority":"2022"})
    return out
