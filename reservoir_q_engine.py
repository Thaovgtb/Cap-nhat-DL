# -*- coding: utf-8 -*-
"""Reservoir free-spillway Q engine ported from CodeQtran2027.xla.
Only Q qua tràn tự do is calculated here. Bottom outlets/gates remain separate.
"""
from __future__ import annotations
import json, os
from bisect import bisect_right
from typing import Any, Dict, Optional

_BASE=os.path.dirname(__file__)
with open(os.path.join(_BASE,"reservoir_q.json"),"r",encoding="utf-8") as f:
    DATA=json.load(f)
QCURVES: Dict[str,Dict[str,Any]]=DATA.get("curves",{})
ALIASES: Dict[str,str]=DATA.get("aliases",{})


def _linear(x,x1,y1,x2,y2):
    if x2==x1:return y1
    return y1+(x-x1)*(y2-y1)/(x2-x1)


def _poly(coeff,x):
    y=0.0
    for c in coeff:y=y*x+float(c)
    return y


def _q_power(seg,z):
    h=z-float(seg["threshold"])
    if h<=0:return 0.0
    return float(seg["coefficient"])*(h**1.5)


def _in_seg(seg,z):
    lo=seg.get("lo"); hi=seg.get("hi")
    if lo is not None and z < float(lo): return False
    if hi is not None and z > float(hi): return False
    return True


def _q_table(meta,z):
    xs=meta["z_m"]; ys=meta["q_m3s"]
    if not xs:return None,"invalid_curve"
    if z < xs[0]:
        return 0.0,"below_spillway_threshold"
    if z == xs[0]:
        return ys[0],"exact"
    if z > xs[-1]:
        return _linear(z,xs[-2],ys[-2],xs[-1],ys[-1]),"extrapolated_high"
    i=bisect_right(xs,z)-1
    return _linear(z,xs[i],ys[i],xs[i+1],ys[i+1]),("exact" if z==xs[i] else "interpolated")


def calculate_spillway_q(reservoir_id:str,z:float)->Dict[str,Any]:
    key=reservoir_id
    if key not in QCURVES:
        key=ALIASES.get(key,key)
    meta=QCURVES.get(key)
    if not meta:
        return {"ok":False,"available":False,"q_m3s":None,"reason":"no_q_curve","message":"Chưa có quan hệ Q qua tràn trong CodeQtran2027.xla cho công trình này."}
    z=float(z)
    if meta["kind"]=="table":
        q,mode=_q_table(meta,z)
        return {"ok":True,"available":True,"q_m3s":max(0.0,float(q)),"mode":mode,
                "algorithm":meta.get("algorithm"),"source_module":meta.get("source_module"),
                "curve_range":{"z_min_m":meta["z_m"][0],"z_max_m":meta["z_m"][-1]},
                "spillway_threshold_m":meta["z_m"][0]}
    if meta["kind"]=="power":
        segs=meta.get("segments",[])
        if z<=float(segs[0]["lo"]):
            return {"ok":True,"available":True,"q_m3s":0.0,"mode":"below_spillway_threshold",
                    "algorithm":meta.get("algorithm"),"source_module":meta.get("source_module"),
                    "curve_range":{"z_min_m":segs[0]["lo"],"z_max_m":segs[-1]["hi"]},
                    "spillway_threshold_m":segs[0]["threshold"]}
        for seg in segs:
            if _in_seg(seg,z):
                q=max(0.0,_q_power(seg,z))
                return {"ok":True,"available":True,"q_m3s":q,"mode":"formula",
                        "algorithm":meta.get("algorithm"),"source_module":meta.get("source_module"),
                        "curve_range":{"z_min_m":segs[0]["lo"],"z_max_m":segs[-1]["hi"]},
                        "spillway_threshold_m":segs[0]["threshold"]}
        return {"ok":True,"available":True,"q_m3s":None,"mode":"out_of_range",
                "algorithm":meta.get("algorithm"),"source_module":meta.get("source_module"),
                "curve_range":{"z_min_m":segs[0]["lo"],"z_max_m":segs[-1]["hi"]},
                "spillway_threshold_m":segs[0]["threshold"]}
    if meta["kind"]=="polynomial":
        segs=meta.get("segments",[])
        # Exact-point segments must win, matching the VBA equality branches.
        exact=[s for s in segs if s.get("lo")==s.get("hi") and abs(z-float(s["lo"]))<1e-12]
        if exact:
            q=max(0.0,_poly(exact[-1]["coeff_desc"],z))
            return {"ok":True,"available":True,"q_m3s":q,"mode":"polynomial_exact",
                    "algorithm":meta.get("algorithm"),"source_module":meta.get("source_module"),
                    "curve_range":{"z_min_m":segs[0]["lo"],"z_max_m":segs[-1]["hi"]},
                    "spillway_threshold_m":segs[0]["lo"]}
        for seg in segs:
            if seg.get("lo")==seg.get("hi"): continue
            if _in_seg(seg,z):
                q=max(0.0,_poly(seg["coeff_desc"],z))
                return {"ok":True,"available":True,"q_m3s":q,"mode":"polynomial",
                        "algorithm":meta.get("algorithm"),"source_module":meta.get("source_module"),
                        "curve_range":{"z_min_m":segs[0]["lo"],"z_max_m":segs[-1]["hi"]},
                        "spillway_threshold_m":segs[0]["lo"]}
        return {"ok":True,"available":True,"q_m3s":0.0 if z<segs[0]["lo"] else None,"mode":"out_of_range",
                "algorithm":meta.get("algorithm"),"source_module":meta.get("source_module"),
                "curve_range":{"z_min_m":segs[0]["lo"],"z_max_m":segs[-1]["hi"]},
                "spillway_threshold_m":segs[0]["lo"]}
    return {"ok":False,"available":False,"q_m3s":None,"reason":"unsupported_q_model"}


def q_catalog():
    return [{"id":k,"name":v.get("name",k),"source":v.get("source_module"),"algorithm":v.get("algorithm")} for k,v in QCURVES.items()]
