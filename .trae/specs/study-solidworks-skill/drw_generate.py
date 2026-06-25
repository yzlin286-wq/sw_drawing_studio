"""
按公司 2D 工程图对标规范，给一个 SLDPRT 自动生成 SLDDRW + PDF + DXF。

规范要点（来自 drawing_standard.md，由 41 张现有 SLDDRW 自动归纳）：
- A4 横向、第一角投影
- 视图：*前视 / *上视 / *右视 / *等轴测，按零件 bbox 自动选比例
- 13 项中文标题栏自定义属性同步从 SLDPRT 读取并写入 SLDDRW
- 自动导入模型尺寸 (InsertModelAnnotations3)
- 输出三件套：SLDDRW + PDF + DXF
"""
import os, sys, time, math, traceback
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

sys.stdout.reconfigure(line_buffering=True)
def log(*a, **kw): print(*a, **kw, flush=True)

# ---------------- 参数 ----------------
ROOT = r"c:\Users\Vision\Desktop\SW 相关"
PART = os.path.join(ROOT, r"3D转2D测试图纸\LB26001-A-04-001.SLDPRT")
OUT_DIR = os.path.join(ROOT, "drw_output")
os.makedirs(OUT_DIR, exist_ok=True)

CANDIDATE_SCALES = [(5,1), (3,1), (2,1), (1,1), (1,2), (1,3), (1,4), (1,5)]
PROP_KEYS = [
    "SWFormatSize", "机型", "品名", "图号", "类别", "数量",
    "材质", "表面处理", "设计", "日期",
    "UNIT_OF_MEASURE", "Material", "重量",
]

def call(o, n, *a):
    if o is None: return None
    try: m = getattr(o, n)
    except Exception: return None
    try:
        if callable(m): return m(*a)
    except Exception: pass
    return m

def variant_dispatch_none():
    return VARIANT(pythoncom.VT_DISPATCH, None)

# ---------------- 连接 ----------------
log("[..] 连接 SW")
try: sw = wc.GetActiveObject("SldWorks.Application")
except Exception:
    sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

# 关闭所有 "工程图N" 临时文档以及与目标输出目录同名的已保存图纸
def close_temp_drawings(sw, also_target_paths=None):
    closed = []
    paths_to_match = set(os.path.normcase(os.path.abspath(p)) for p in (also_target_paths or []))
    try:
        docs = sw.GetDocuments
        docs = docs() if callable(docs) else docs
        for d in (docs or []):
            try:
                t = d.GetTitle() if callable(getattr(d, "GetTitle", None)) else d.GetTitle
                pn = d.GetPathName() if callable(getattr(d, "GetPathName", None)) else d.GetPathName
                pn_norm = os.path.normcase(os.path.abspath(pn)) if pn else ""
                if str(t).startswith("工程图") or str(t).startswith("Drawing") or pn_norm in paths_to_match:
                    sw.CloseDoc(t)
                    closed.append(f"{t}|{pn}")
            except Exception:
                pass
    except Exception:
        pass
    if closed:
        log(f"  关闭遗留文档: {closed}")
close_temp_drawings(sw, also_target_paths=[
    os.path.join(r"c:\Users\Vision\Desktop\SW 相关\drw_output", "LB26001-A-04-001.SLDDRW")
])

# ---------------- 打开 SLDPRT，读取标题栏属性、bbox ----------------
log(f"[1/6] 打开零件: {os.path.basename(PART)}")
e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
part = sw.OpenDoc6(PART, 1, 1 | 16 | 256, "", e, w)
if part is None:
    raise SystemExit(f"打开零件失败 errors={e.value}")

# 读取自定义属性（仅做透传到工程图）
src_cpm = part.Extension.CustomPropertyManager("")
src_props = {}
for k in PROP_KEYS:
    try:
        rv, value, resolved, was = src_cpm.Get5(k, False)
        src_props[k] = resolved or value or ""
    except Exception:
        src_props[k] = ""
# 兜底图号 = 文件名（无扩展）
if not src_props.get("图号"):
    src_props["图号"] = os.path.splitext(os.path.basename(PART))[0]
log(f"  读到 {sum(1 for v in src_props.values() if v)} / {len(PROP_KEYS)} 项属性")

# 读取零件外形 bbox -> 选比例
Lmax = 0.05
try:
    # 先尝试 IPartDoc.GetPartBox(useUserUnits=False) -> [xmin,ymin,zmin,xmax,ymax,zmax]
    box = part.GetPartBox(True)
    box = list(box) if box else None
    if box and len(box) >= 6:
        Lmax = max(abs(box[3]-box[0]), abs(box[4]-box[1]), abs(box[5]-box[2]))
except Exception:
    pass
if Lmax <= 0 or Lmax > 10:
    # 兜底：遍历实体 GetBodyBox
    try:
        bodies = part.GetBodies2(0, False) or []
        for b in bodies:
            bb = b.GetBodyBox() if callable(getattr(b, "GetBodyBox", None)) else b.GetBodyBox
            bb = list(bb) if bb else None
            if bb and len(bb) >= 6:
                d = max(abs(bb[3]-bb[0]), abs(bb[4]-bb[1]), abs(bb[5]-bb[2]))
                Lmax = max(Lmax if Lmax>0 else 0, d)
    except Exception as exc:
        log(f"  读取 bbox 失败: {exc}, 用默认 50mm")
log(f"  零件最大轮廓 Lmax = {Lmax*1000:.1f} mm")

D_LIMIT = 0.10  # 单视图最大 100 mm
chosen = (1, 1)
for n_, d_ in CANDIDATE_SCALES:
    if Lmax * (n_ / d_) <= D_LIMIT:
        chosen = (n_, d_); break
scale_num, scale_den = chosen
scale_label = f"{scale_num}:{scale_den}"
log(f"  自动选择比例 {scale_label}")

# 新建工程图（A4 横向，第一角投影）
log("[2/6] 新建工程图（A4 横向，第一角投影）")
import glob as _g
def find_drwdot():
    cands = []
    for d in [r"C:\ProgramData\SolidWorks\SOLIDWORKS *\templates",
              r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\lang\chinese-simplified",
              r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\lang\english",
              r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified",
              r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english"]:
        for f in _g.glob(os.path.join(d, "*.drwdot")):
            cands.append(f)
    return cands[0] if cands else ""
drwtmpl = find_drwdot()
log(f"  drwdot 模板: {drwtmpl or '(默认)'}")
if drwtmpl:
    drw = sw.NewDocument(drwtmpl, 0, 0, 0)
else:
    drw = sw.NewDocument("", 0, 0, 0)

# 等待 ActiveDoc 切到工程图
for _ in range(20):
    if drw is not None: break
    time.sleep(0.25)
    drw = sw.ActiveDoc
if drw is None:
    raise SystemExit("新建工程图失败")
log(f"  ActiveDoc Title = {call(drw, 'GetTitle')}")

# 标准化纸张/比例/投影
sheet = call(drw, "GetCurrentSheet")
sheet_name = call(sheet, "GetName") if sheet else "Sheet1"
try:
    drw.SetupSheet5(
        sheet_name,
        6,           # paper code: A4 LANDSCAPE
        13,          # template-in
        scale_num, scale_den,
        True,        # firstAngle
        "",          # template path
        0.297, 0.21,
        "", True,
    )
    log("  SetupSheet5 OK -> A4 横向, 第一角, 比例 " + scale_label)
except Exception as exc:
    log(f"  SetupSheet5 异常: {exc}")

# ---------------- 添加视图 ----------------
log("[3/6] 创建 4 个标准视图（前视/上视/右视/等轴测）")
W, H = 0.297, 0.21  # 米
# 主视图 (前视) 居中偏左
positions = [
    (("*Front",     "*前视"),     (W*0.30, H*0.55)),
    (("*Top",       "*上视"),     (W*0.30, H*0.80)),
    (("*Right",     "*右视"),     (W*0.55, H*0.55)),
    (("*Isometric", "*等轴测"),   (W*0.78, H*0.78)),
]
created = []
for aliases, (x, y) in positions:
    v = None
    for vname in aliases:
        try:
            v = drw.CreateDrawViewFromModelView3(PART, vname, x, y, 0)
            if v is not None:
                log(f"  + 视图 [{vname}] @ ({x*1000:.0f}, {y*1000:.0f}) mm")
                break
        except Exception as exc:
            log(f"  视图 {vname} 异常: {exc}")
    if v is None:
        log(f"  视图 {aliases} 创建失败")
        continue
    try: v.ScaleRatio = (float(scale_num), float(scale_den))
    except Exception: pass
    created.append(aliases[0])
log(f"  共创建视图 {len(created)}/4")

# ---------------- 自动导入模型尺寸 ----------------
log("[4/6] 自动导入模型尺寸")
ext = drw.Extension
imported = False
try:
    drw.ClearSelection2(True)
except Exception: pass

# 方案 A：调 InsertModelAnnotations3
try:
    fn = getattr(ext, "InsertModelAnnotations3")
    if callable(fn):
        fn(0, 32, True, True, False, False)
        imported = True
        log("  OK via InsertModelAnnotations3")
except Exception as exc:
    log(f"  InsertModelAnnotations3 异常: {exc}")

# 方案 B：在每张视图里逐个调用 InsertModelAnnotations3
if not imported:
    try:
        v = drw.GetFirstView()
        v = v() if callable(v) else v
        cnt = 0
        # 跳过第 0 个 (sheet 本身)
        v = v.GetNextView() if v is not None else None
        while v is not None:
            try:
                v.SelectByName(0, "")
                ext.InsertModelAnnotations3(0, 32, True, True, False, False)
                cnt += 1
            except Exception:
                pass
            v = v.GetNextView()
        if cnt > 0:
            imported = True
            log(f"  OK via per-view loop (共 {cnt} 个视图)")
    except Exception as exc:
        log(f"  per-view 异常: {exc}")

# 方案 C：调 SolidWorks 命令 ID
if not imported:
    try:
        sw.RunCommand(826, "")  # swCommands_e.swCommands_InsertModelItems = 826
        imported = True
        log("  OK via RunCommand(826) Model Items")
    except Exception as exc:
        log(f"  RunCommand(826) 异常: {exc}")
if not imported:
    log("  自动尺寸导入失败，可在 SolidWorks 内手动用 '模型项目' 命令补尺寸")

# ---------------- 写自定义属性 ----------------
log("[5/6] 同步 13 项标题栏自定义属性")
dst_cpm = drw.Extension.CustomPropertyManager("")
written = 0
for k in PROP_KEYS:
    val = src_props.get(k, "") or ""
    try:
        # Add3: name, type=30(text), value, deleteAndAdd=2
        rv = dst_cpm.Add3(k, 30, val, 2)
        if rv != 0 and rv != 1:
            # 1 = succeeded as new
            pass
        written += 1
    except Exception as exc:
        log(f"  写属性 {k} 失败: {exc}")
log(f"  写入 {written}/{len(PROP_KEYS)} 项")

# ---------------- 保存 + 出 PDF + DXF ----------------
log("[6/6] 保存 SLDDRW / 输出 PDF / DXF")
base = src_props.get("图号") or os.path.splitext(os.path.basename(PART))[0]
slddrw = os.path.join(OUT_DIR, f"{base}.SLDDRW")
pdf    = os.path.join(OUT_DIR, f"{base}.PDF")
dxf    = os.path.join(OUT_DIR, f"{base}.DXF")
# 旧文件先删掉避免 SaveAs 返回 1（文件已存在 / 占用）
for p in (slddrw, pdf, dxf):
    try:
        if os.path.exists(p): os.remove(p)
    except Exception as exc:
        log(f"  删除旧文件 {p} 失败: {exc}")

err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

# 1) SaveAs SLDDRW
ok1 = drw.Extension.SaveAs(slddrw, 0, 1, variant_dispatch_none(), err, warn)
log(f"  SLDDRW: {'OK' if ok1 else 'FAIL'} -> {slddrw}  err={err.value}")

# 2) PDF (with 当前 sheet)
try:
    pdf_data = sw.GetExportFileData(1)  # swExportPDFData
    sheet_names_obj = drw.GetSheetNames if not callable(getattr(drw, "GetSheetNames", None)) else drw.GetSheetNames()
    sheet_names = list(sheet_names_obj) if sheet_names_obj else []
    if pdf_data and sheet_names:
        try:
            ss = pdf_data.SetSheets if not callable(getattr(pdf_data, "SetSheets", None)) else None
            if callable(getattr(pdf_data, "SetSheets", None)):
                pdf_data.SetSheets(0, sheet_names)
        except Exception as exc:
            log(f"  pdf SetSheets 异常: {exc}")
    err.value = 0; warn.value = 0
    ok2 = drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
    log(f"  PDF   : {'OK' if ok2 else 'FAIL'} -> {pdf}  err={err.value}")
except Exception as exc:
    log(f"  PDF   : EXC {exc}")

# 3) DXF
try:
    err.value = 0; warn.value = 0
    ok3 = drw.Extension.SaveAs(dxf, 0, 1, variant_dispatch_none(), err, warn)
    log(f"  DXF   : {'OK' if ok3 else 'FAIL'} -> {dxf}  err={err.value}")
except Exception as exc:
    log(f"  DXF   : EXC {exc}")

# 关闭工程图（保留打开方便人工核查也可注释掉）
try:
    sw.CloseDoc(drw.GetTitle())
except Exception:
    pass

log("\n[DONE]")
