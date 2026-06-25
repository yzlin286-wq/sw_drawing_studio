"""
查看原件 LB26001-A-04-001.SLDDRW 的属性到底放在哪个 manager
"""
import os, time, pythoncom
import win32com.client as wc
from win32com.client import VARIANT

ROOT = r"c:\Users\Vision\Desktop\SW 相关"
ORIG = os.path.join(ROOT, r"3D转2D测试图纸\LB26001-A-04-001.SLDDRW")

def call(o, n, *a):
    if o is None: return None
    try: m = getattr(o, n)
    except Exception: return None
    try:
        if callable(m): return m(*a)
    except Exception: pass
    return m

try: sw = wc.GetActiveObject("SldWorks.Application")
except Exception:
    sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
drw = sw.OpenDoc6(ORIG, 3, 1|16|256, "", e, w)
print("opened:", call(drw, "GetTitle"))

# 文档级
ext = drw.Extension
mgrs = [("(doc)", ext.CustomPropertyManager(""))]
cfgs = call(drw, "GetConfigurationNames") or []
for cn in list(cfgs):
    mgrs.append((cn, ext.CustomPropertyManager(cn)))

# 看每个视图的 Sheet 自己也可能挂属性
sheet_names = call(drw, "GetSheetNames") or []
print("Sheets:", list(sheet_names))

# 看每个视图引用文档的属性
v = call(drw, "GetFirstView")
while v is not None:
    name = call(v, "GetName2")
    refdoc = call(v, "GetReferencedDocument")
    refpath = call(refdoc, "GetPathName") if refdoc else ""
    print(f"\nView {name!r}  ref={refpath}")
    if refdoc:
        rext = refdoc.Extension
        for tag, mgr in [("ref(doc)", rext.CustomPropertyManager(""))] + \
                        [(cn, rext.CustomPropertyManager(cn)) for cn in (call(refdoc, "GetConfigurationNames") or [])]:
            try:
                names = list(call(mgr, "GetNames") or [])
                vals = {}
                for n in names:
                    try:
                        rv, val, resolved, was = mgr.Get5(n, False)
                        vals[n] = (resolved or val or "")
                    except Exception:
                        pass
                if vals:
                    print(f"  [{tag}] {len(names)} keys -> {vals}")
            except Exception:
                pass
    v = call(v, "GetNextView")

# 看图纸自身属性
print("\n---- DRW 自身属性 ----")
for tag, mgr in mgrs:
    names = list(call(mgr, "GetNames") or [])
    if not names: continue
    vals = {}
    for n in names:
        try:
            rv, val, resolved, was = mgr.Get5(n, False)
            vals[n] = resolved or val or ""
        except Exception: pass
    print(f"  [{tag}] {len(names)} keys: {vals}")

sw.CloseDoc(call(drw, "GetTitle"))
print("\n[DONE]")
