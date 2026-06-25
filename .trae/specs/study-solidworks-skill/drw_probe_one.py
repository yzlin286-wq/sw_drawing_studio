"""
SLDDRW 探针 v3 (单文件最小复现)
- options=0 完整打开
- 直接通过 GetSheetCount/Sheet(i) 路径读取（属性式）
- 视图：GetFirstView 强制 callable
"""
import os, json, time, traceback, pythoncom
import win32com.client as wc
from win32com.client import VARIANT

ROOT = r"c:\Users\Vision\Desktop\SW 相关"
TARGET = os.path.join(ROOT, r"3D转2D测试图纸\LB26001-A-04-001.SLDDRW")
OUT = os.path.join(ROOT, ".trae", "specs", "study-solidworks-skill", "drw_probe_one.json")

def call(obj, name, *args):
    """COM 双态强制调用：先按方法尝试，失败后退回属性。"""
    if obj is None: return None
    try:
        member = getattr(obj, name)
    except Exception:
        return None
    try:
        if callable(member):
            return member(*args)
    except Exception:
        pass
    try:
        return member
    except Exception:
        return None

print("[..] 连接 SW")
try:
    sw = wc.GetActiveObject("SldWorks.Application")
except Exception:
    sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

errs = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
warns = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
drw = sw.OpenDoc6(TARGET, 3, 0, "", errs, warns)
print(f"errors={errs.value} warnings={warns.value}")
if drw is None:
    print("[FAIL]"); raise SystemExit

print("Title :", call(drw, "GetTitle"))
print("Path  :", call(drw, "GetPathName"))

# Sheet
sheet_names = call(drw, "GetSheetNames")
print("Sheet count:", call(drw, "GetSheetCount"))
print("Sheet names:", list(sheet_names) if sheet_names else None)

# 当前 Sheet 属性
sheet = call(drw, "GetCurrentSheet")
print("Sheet obj:", sheet)
if sheet is not None:
    print("  Name        :", call(sheet, "GetName"))
    print("  Properties2 :", list(call(sheet, "GetProperties2") or []))
    print("  Properties  :", list(call(sheet, "GetProperties") or []))
    try:
        sz = sheet.GetSize()
        print("  Size(method):", list(sz) if sz else None)
    except Exception as e:
        print("  Size(method): ERR", e)
    print("  Template    :", call(sheet, "GetTemplateName"))

# 视图
print("\n--- 视图 ---")
v = call(drw, "GetFirstView")
i = 0
while v is not None:
    name = call(v, "GetName2")
    print(f"  [{i}] name={name!r}  type={call(v,'Type')}  scale={list(call(v,'ScaleRatio') or [])}  pos={list(call(v,'Position') or [])}")
    print(f"       outline={list(call(v,'GetOutline') or [])}")
    print(f"       orient ={call(v,'GetOrientationName')}")
    refdoc = call(v, "GetReferencedDocument")
    if refdoc is not None:
        print(f"       refdoc ={call(refdoc, 'GetPathName')}")
    # 尺寸
    a = call(v, "GetFirstAnnotation3")
    cnt = 0
    types = {}
    while a is not None:
        cnt += 1
        t = str(call(a, "GetType"))
        types[t] = types.get(t, 0) + 1
        a = call(a, "GetNext3")
    print(f"       annotations cnt={cnt} types={types}")
    v = call(v, "GetNextView")
    i += 1

# 用户偏好关键码
print("\n--- 用户偏好 ---")
codes = {
    "swUnitsLinear": 5,
    "swDetailingDimensionTextFont": 8,
    "swUnitsDecimalPlaces": 6,
    "swDetailingDualDimension": 94,
    "swDetailingArrowHeight": 0,
    "swDetailingArrowLength": 1,
    "swDetailingArrowWidth": 2,
}
for k, code in codes.items():
    try:
        d = drw.GetUserPreferenceDoubleValue(code)
        print(f"  D[{k}={code}] = {d}")
    except Exception as e:
        print(f"  D[{k}={code}] = {e}")
    try:
        i_ = drw.GetUserPreferenceIntegerValue(code)
        print(f"  I[{k}={code}] = {i_}")
    except Exception as e:
        print(f"  I[{k}={code}] = {e}")

sw.CloseDoc(call(drw, "GetTitle"))
print("[DONE]")
