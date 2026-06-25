"""
drw_generate_v4.py
---
在 v3 基础上升级：
1) 第 6 步「创建剖视图」改为调用 section_helper.create_section_in_active_drawing(sw, drw)。
2) 视图坐标按 drawing_standard_v2.md 第 9 节「加工件出图标准坐标」给出的 mm 数值布置；
   解析失败时退回 v3 硬编码坐标作 fallback。
3) Note 字高改为 3.5 mm —— model.SetUserPreferenceDoubleValue(89, 0.0035)。
4) 产物文件名带 _v4 后缀，避免覆盖 v3。
5) 仍保留：13 项标题栏属性同步（含 MassProperties.重量）、4 个标准视图、自动尺寸 RunCommand(826)、
   技术要求 / Ra Note / 基准 A Note 兜底。
6) 保留 try/except 鲁棒性 + sys.stdout.reconfigure(line_buffering=True) + log()。
"""
import os, re, sys, time, json, math, traceback
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

sys.path.insert(0, os.path.dirname(__file__))
from section_helper import create_section_in_active_drawing

sys.stdout.reconfigure(line_buffering=True)
def log(*a, **kw): print(*a, **kw, flush=True)

ROOT = r"c:\Users\Vision\Desktop\SW 相关"
DEFAULT_PART = os.path.join(ROOT, r"3D转2D测试图纸\LB26001-A-04-001.SLDPRT")
OUT_DIR = os.path.join(ROOT, "drw_output")
STANDARD_MD = os.path.join(os.path.dirname(__file__), "drawing_standard_v2.md")

CANDIDATE_SCALES = [(5,1),(3,1),(2,1),(1,1),(1,2),(1,3),(1,4),(1,5)]
PROP_KEYS = ["SWFormatSize","机型","品名","图号","类别","数量",
             "材质","表面处理","设计","日期",
             "UNIT_OF_MEASURE","Material","重量"]

TECH_NOTES = (
    "技术要求：\n"
    "1. 未注圆角 R0.5；\n"
    "2. 未注公差按 GB/T 1804-m；\n"
    "3. 未注角度公差 ±0.5°；\n"
    "4. 加工后去毛刺、锐边倒钝 0.2x45°；\n"
    "5. 表面不得有划伤、磕碰等明显缺陷。"
)

# v3 fallback (mm)
FALLBACK_COORDS_MM = {
    "front":     (0.297*0.28*1000, 0.21*0.55*1000),
    "top":       (0.297*0.28*1000, 0.21*0.82*1000),
    "right":     (0.297*0.55*1000, 0.21*0.55*1000),
    "iso":       (0.297*0.80*1000, 0.21*0.80*1000),
    "section":   (0.297*0.28*1000, 0.21*0.20*1000),
    "tech":      (0.297*0.62*1000, 0.21*0.30*1000),
    "ra":        (0.297*0.55*1000, 0.21*0.42*1000),
    "datum":     (0.297*0.18*1000, 0.21*0.40*1000),
}


def parse_standard_coords(md_path):
    """解析 drawing_standard_v2.md 第 9 节的「加工件出图标准坐标」。
    返回 dict: key in {front, top, right, iso, section, tech, ra, datum}
    每个值为 (x_mm, y_mm)。解析失败返回 {} 由调用方走 fallback。
    """
    coords = {}
    if not os.path.exists(md_path):
        return coords
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return coords

    # 锚定第 9 节
    sec_idx = text.find("加工件出图标准坐标")
    if sec_idx < 0:
        return coords
    section_text = text[sec_idx:sec_idx + 4000]

    label_map = [
        (r"前视图",                       "front"),
        (r"上视图",                       "top"),
        (r"右视图",                       "right"),
        (r"等轴测",                       "iso"),
        (r"剖视图\s*A-?A?\s*[（(]?\s*横切",  "section"),
        (r"技术要求\s*Note",              "tech"),
        (r"Ra\s*Note",                    "ra"),
        (r"基准\s*A",                     "datum"),
    ]
    # 表格行格式: | 元素 | **x** | **y** | ... |
    num_pat = re.compile(r"\*?\*?(\d+(?:\.\d+)?)\*?\*?")
    for label_re, key in label_map:
        m = re.search(
            r"\|\s*" + label_re + r"[^|]*\|\s*([^|]+)\|\s*([^|]+)\|",
            section_text)
        if not m:
            continue
        x_cell, y_cell = m.group(1), m.group(2)
        x_match = num_pat.search(x_cell)
        y_match = num_pat.search(y_cell)
        if not x_match or not y_match:
            continue
        try:
            coords[key] = (float(x_match.group(1)), float(y_match.group(1)))
        except Exception:
            continue
    return coords


def coord_m(coords_mm, key):
    """从 mm dict 取 key，返回 (x_m, y_m)。缺失则用 fallback。"""
    src = coords_mm.get(key) or FALLBACK_COORDS_MM[key]
    return (src[0] / 1000.0, src[1] / 1000.0)


def call(o, n, *a):
    if o is None: return None
    try: m = getattr(o, n)
    except Exception: return None
    try:
        if callable(m): return m(*a)
    except Exception: pass
    return m

def vt_dispatch_none(): return VARIANT(pythoncom.VT_DISPATCH, None)
def empty_callout(): return VARIANT(pythoncom.VT_DISPATCH, None)

def view_outline_box(view):
    out = call(view, "GetOutline")
    if out is None: return None
    o = list(out)
    if len(o) >= 4:
        return (o[0], o[1], o[2], o[3])
    return None

def generate_for(part_path, *, out_dir=OUT_DIR, sw=None):
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(part_path))[0]
    warnings_box = []

    # 解析标准坐标
    std_coords_mm = parse_standard_coords(STANDARD_MD)
    if std_coords_mm:
        log(f"[std] 解析到 {len(std_coords_mm)} 个标准坐标: "
            + ", ".join(f"{k}={v[0]:.1f},{v[1]:.1f}mm" for k,v in std_coords_mm.items()))
    else:
        log("[std] 未解析到标准坐标，全部使用 v3 fallback")
        warnings_box.append({"code":"std_coords_parse_failed",
                             "msg":"drawing_standard_v2.md 第 9 节坐标未解析到，使用 v3 fallback"})

    if sw is None:
        log("[..] 连接 SW")
        try: sw = wc.GetActiveObject("SldWorks.Application")
        except Exception:
            sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

    target_drw = os.path.join(out_dir, f"{base_name}_v4.SLDDRW")
    try:
        docs = sw.GetDocuments
        docs = docs() if callable(docs) else docs
        for d in (docs or []):
            try:
                t = d.GetTitle if not callable(getattr(d,"GetTitle",None)) else d.GetTitle()
                pn = d.GetPathName if not callable(getattr(d,"GetPathName",None)) else d.GetPathName()
                if (str(t).startswith("工程图") or str(t).startswith("Drawing") or
                    (pn and os.path.normcase(os.path.abspath(pn)) == os.path.normcase(os.path.abspath(target_drw)))):
                    sw.CloseDoc(t)
            except Exception: pass
    except Exception: pass
    for ext_ in (".SLDDRW", ".PDF", ".DXF"):
        f = os.path.join(out_dir, base_name + "_v4" + ext_)
        if os.path.exists(f):
            try: os.remove(f)
            except Exception as exc: log(f"  删除旧文件 {f} 失败: {exc}")

    # 1) 打开零件
    log(f"[1/9] 打开 {os.path.basename(part_path)}")
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    part = sw.OpenDoc6(part_path, 1, 1|16|256, "", e, w)
    if part is None:
        raise SystemExit(f"打开零件失败 errors={e.value}")

    # 2) 13 项属性
    log("[2/9] 读 13 项属性 + MassProperties.重量")
    src_props = {}
    src_cpms = []
    try: src_cpms.append(("", part.Extension.CustomPropertyManager("")))
    except Exception: pass
    try:
        cfg_names = part.GetConfigurationNames if not callable(getattr(part, "GetConfigurationNames", None)) else part.GetConfigurationNames()
        for cn in list(cfg_names or []):
            try: src_cpms.append((cn, part.Extension.CustomPropertyManager(cn)))
            except Exception: pass
    except Exception: pass
    src_filled_max = -1
    for cn, cpm in src_cpms:
        cur = {}
        for k in PROP_KEYS:
            try:
                rv, value, resolved, was = cpm.Get5(k, False)
                cur[k] = (resolved or value or "")
            except Exception:
                cur[k] = ""
        f = sum(1 for v in cur.values() if v)
        if f > src_filled_max:
            src_filled_max, src_props = f, cur
    try:
        mp = part.Extension.CreateMassProperty()
        try: mp.UseSystemUnits = True
        except Exception: pass
        mass_kg = call(mp, "Mass")
        if isinstance(mass_kg, (int, float)) and mass_kg > 0:
            src_props["重量"] = f"{round(mass_kg*1000,2)} g"
    except Exception as exc:
        warnings_box.append({"code":"mass_err","msg":str(exc)})
    if not src_props.get("图号"): src_props["图号"] = base_name
    if not src_props.get("数量"): src_props["数量"] = "1"
    if not src_props.get("UNIT_OF_MEASURE"): src_props["UNIT_OF_MEASURE"] = "mm"
    if not src_props.get("SWFormatSize"): src_props["SWFormatSize"] = "210mm*297mm"
    for k in PROP_KEYS:
        if not src_props.get(k):
            warnings_box.append({"code":"prop_missing","key":k,"msg":f"标题栏属性 [{k}] 缺失"})
    log(f"  非空属性 {sum(1 for v in src_props.values() if v)}/{len(PROP_KEYS)}")

    # 3) bbox -> 比例
    Lmax = 0.05
    try:
        box = part.GetPartBox(True)
        box = list(box) if box else None
        if box and len(box) >= 6:
            Lmax = max(abs(box[3]-box[0]),abs(box[4]-box[1]),abs(box[5]-box[2]))
    except Exception: pass
    chosen = (1,1)
    for n_,d_ in CANDIDATE_SCALES:
        if Lmax * (n_/d_) <= 0.10 + 1e-9:
            chosen = (n_, d_); break
    scale_num, scale_den = chosen
    scale_label = f"{scale_num}:{scale_den}"
    log(f"  Lmax={Lmax*1000:.1f}mm 选比例 {scale_label}")

    # 4) 新建工程图
    log("[3/9] 新建 A4 横向 / 第一角 / " + scale_label)
    import glob as _g
    drwtmpl = ""
    for d in [r"C:\ProgramData\SolidWorks\SOLIDWORKS *\templates",
              r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\lang\chinese-simplified",
              r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\lang\english",
              r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified",
              r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english"]:
        for f in _g.glob(os.path.join(d, "*.drwdot")):
            drwtmpl = f; break
        if drwtmpl: break
    drw = sw.NewDocument(drwtmpl or "", 0, 0, 0)
    for _ in range(20):
        if drw is not None: break
        time.sleep(0.25); drw = sw.ActiveDoc
    if drw is None: raise SystemExit("新建工程图失败")
    sheet = call(drw, "GetCurrentSheet")
    sheet_name = call(sheet, "GetName") or "Sheet1"
    try: drw.SetupSheet5(sheet_name, 6, 13, scale_num, scale_den, True, "", 0.297, 0.21, "", True)
    except Exception: pass

    # ★ 文字高度 3.5 mm（替代默认 0.3 mm）
    try:
        ok_tx = drw.SetUserPreferenceDoubleValue(89, 0.0035)
        log(f"  Note 字高设为 3.5mm: SetUserPreferenceDoubleValue(89, 0.0035) -> {ok_tx}")
    except Exception as exc:
        warnings_box.append({"code":"text_height_set_failed","msg":str(exc)})

    # 5) 4 个标准视图（按标准坐标）
    log("[4/9] 4 个标准视图（按 v2 标准坐标）")
    fx, fy = coord_m(std_coords_mm, "front")
    tx, ty = coord_m(std_coords_mm, "top")
    rx, ry = coord_m(std_coords_mm, "right")
    ix, iy = coord_m(std_coords_mm, "iso")
    log(f"  std positions(mm): front=({fx*1000:.1f},{fy*1000:.1f}) "
        f"top=({tx*1000:.1f},{ty*1000:.1f}) right=({rx*1000:.1f},{ry*1000:.1f}) iso=({ix*1000:.1f},{iy*1000:.1f})")
    positions = [
        (("*Front", "*前视"),     (fx, fy)),
        (("*Top",   "*上视"),     (tx, ty)),
        (("*Right", "*右视"),     (rx, ry)),
        (("*Isometric","*等轴测"),(ix, iy)),
    ]
    front_view = None
    for aliases, (x,y) in positions:
        v = None
        for vname in aliases:
            try:
                v = drw.CreateDrawViewFromModelView3(part_path, vname, x, y, 0)
                if v is not None:
                    if vname in ("*Front","*前视"): front_view = v
                    log(f"  + {vname} ok @({x*1000:.1f},{y*1000:.1f})mm")
                    break
            except Exception: pass
        if v is not None:
            try: v.ScaleRatio = (float(scale_num), float(scale_den))
            except Exception: pass

    # 6) 自动尺寸
    log("[5/9] 导入模型尺寸")
    ext = drw.Extension
    imported = False
    try:
        fn = getattr(ext, "InsertModelAnnotations3")
        if callable(fn):
            fn(0, 32, True, True, False, False); imported = True
    except Exception: pass
    if not imported:
        try:
            sw.RunCommand(826, "")
            imported = True
        except Exception as exc:
            warnings_box.append({"code":"dim_import_failed","msg":str(exc)})

    # 7) ★ 剖视图 ★ —— 调 section_helper.create_section_in_active_drawing
    log("[6/9] 创建剖视图（section_helper）")
    section_view = False
    try:
        ok_sec = create_section_in_active_drawing(sw, drw)
        if ok_sec:
            section_view = True
            log("  + 剖视图 A-A OK (section_helper)")
            warnings_box.append({"code":"OK","key":"section_view","msg":"剖视图 A-A 创建成功"})
        else:
            warnings_box.append({"code":"section_helper_failed",
                                 "msg":"create_section_in_active_drawing 返回 False"})
    except Exception as exc:
        warnings_box.append({"code":"section_helper_exc","msg":str(exc)})

    # 8) ★ 真基准 A ★
    log("[7/9] 形位公差基准 A + 表面粗糙度")
    datum_inserted = False
    try:
        if front_view is not None:
            try: front_view.SelectByName(0, "")
            except Exception: pass
            ob = view_outline_box(front_view)
            if ob:
                xmin, ymin, xmax, ymax = ob
                try:
                    drw.Extension.SelectByID2("", "EDGE",
                        (xmin + xmax)/2.0, ymin + 0.0005, 0,
                        False, 0, empty_callout(), 0)
                except Exception: pass
                W, H = 0.297, 0.21
                attempts = [
                    ("ext.InsertDatumTagSymbol2 (5)",
                     lambda: ext.InsertDatumTagSymbol2(W*0.20, ymin - 0.012, 0, 2, "A")),
                    ("ext.InsertDatumTagSymbol3 (5)",
                     lambda: ext.InsertDatumTagSymbol3(W*0.20, ymin - 0.012, 0, 2, "A")),
                    ("ext.InsertDatumTagSymbol (5)",
                     lambda: ext.InsertDatumTagSymbol(W*0.20, ymin - 0.012, 0, "A", 2)),
                ]
                for name, fn in attempts:
                    try:
                        tag = fn()
                        if tag is not None:
                            try: tag.SetLabel("A")
                            except Exception: pass
                            log(f"  + {name} OK")
                            datum_inserted = True
                            break
                    except Exception as exc:
                        warnings_box.append({"code":"datum_exc","fn":name,"msg":str(exc)})
                if not datum_inserted:
                    try:
                        sw.RunCommand(2240, "")
                        log("  + RunCommand(2240) DatumFeature triggered")
                    except Exception: pass
    except Exception as exc:
        warnings_box.append({"code":"datum_outer","msg":str(exc)})
    if not datum_inserted:
        try:
            n = drw.InsertNote("〔A〕")
            if n is not None:
                ann = call(n, "GetAnnotation")
                if ann is not None:
                    dx, dy = coord_m(std_coords_mm, "datum")
                    try: ann.SetPosition2(dx, dy, 0)
                    except Exception: pass
                log(f"  + 兜底 Note 〔A〕 @std datum")
        except Exception: pass

    # 9) ★ 真表面粗糙度 ★
    sf_inserted = False
    try:
        if front_view is not None:
            try: front_view.SelectByName(0, "")
            except Exception: pass
            ob = view_outline_box(front_view)
            if ob:
                xmin, ymin, xmax, ymax = ob
                try:
                    drw.Extension.SelectByID2("", "EDGE",
                        (xmin + xmax)/2.0, ymax - 0.0005, 0,
                        False, 0, empty_callout(), 0)
                except Exception: pass
        rax, ray = coord_m(std_coords_mm, "ra")
        sf_attempts = [
            ("ext.InsertSurfaceFinishSymbol3 (string,string)",
             lambda: ext.InsertSurfaceFinishSymbol3(
                 1, -1, "3.2", "", "", "", 1, "", 0.0,
                 rax, ray, 0.0, 0, 0)),
            ("ext.InsertSurfaceFinishSymbol3 (Lay 0)",
             lambda: ext.InsertSurfaceFinishSymbol3(
                 1, 0, "3.2", "", "", "", 1, "", 0.0,
                 rax, ray, 0.0, 0, 0)),
            ("ext.InsertSurfaceFinishSymbol2",
             lambda: ext.InsertSurfaceFinishSymbol2(
                 1, 0, 3.2, 0.0, "", "", 1, "", 0.0,
                 rax, ray, 0.0)),
        ]
        for name, fn in sf_attempts:
            try:
                sf = fn()
                if sf is not None:
                    log(f"  + {name} Ra 3.2 OK")
                    sf_inserted = True
                    break
            except Exception as exc:
                warnings_box.append({"code":"sf_exc","fn":name,"msg":str(exc)})
    except Exception as exc:
        warnings_box.append({"code":"sf_outer","msg":str(exc)})
    if not sf_inserted:
        try:
            n = drw.InsertNote("Ra 3.2 (其余表面)")
            if n:
                ann = call(n, "GetAnnotation")
                if ann is not None:
                    rax, ray = coord_m(std_coords_mm, "ra")
                    try: ann.SetPosition2(rax, ray, 0)
                    except Exception: pass
                log("  + 兜底 Note Ra 3.2 @std ra")
        except Exception: pass

    # 10) 13 项属性
    log("[8/9] 写 13 项属性")
    write_targets = []
    try: write_targets.append(drw.Extension.CustomPropertyManager(""))
    except Exception: pass
    try:
        cfg_names = drw.GetConfigurationNames if not callable(getattr(drw, "GetConfigurationNames", None)) else drw.GetConfigurationNames()
        for cn in list(cfg_names or []):
            try: write_targets.append(drw.Extension.CustomPropertyManager(cn))
            except Exception: pass
    except Exception: pass
    for cpm in write_targets:
        for k in PROP_KEYS:
            val = src_props.get(k, "") or ""
            try:
                cpm.Add3(k, 30, val, 2)
                if val:
                    try: cpm.Set2(k, val)
                    except Exception: pass
            except Exception as exc:
                warnings_box.append({"code":"prop_write_fail","key":k,"msg":str(exc)})

    # 11) 技术要求 + Ra + 基准 A 兜底 Note
    log("[11/?] 技术要求/表面粗糙度/基准 A Notes")
    try:
        drw.ClearSelection2(True)
        try: drw.ActivateSheet(sheet_name)
        except Exception: pass

        try:
            note = drw.InsertNote(TECH_NOTES)
            if note is not None:
                ann = call(note, "GetAnnotation")
                if ann is not None:
                    tcx, tcy = coord_m(std_coords_mm, "tech")
                    try: ann.SetPosition2(tcx, tcy, 0)
                    except Exception: pass
                log(f"  + 技术要求 Note OK @std tech")
            else:
                warnings_box.append({"code":"tech_note_none","msg":"InsertNote 返回 None"})
        except Exception as exc:
            warnings_box.append({"code":"tech_note_exc","msg":str(exc)})

        if not sf_inserted:
            try:
                drw.ClearSelection2(True)
                n = drw.InsertNote("Ra 3.2  (其余表面)")
                if n is not None:
                    ann = call(n, "GetAnnotation")
                    if ann is not None:
                        rax, ray = coord_m(std_coords_mm, "ra")
                        try: ann.SetPosition2(rax, ray, 0)
                        except Exception: pass
                    log("  + Note Ra 3.2 OK")
            except Exception as exc:
                warnings_box.append({"code":"sf_note_exc","msg":str(exc)})

        if not datum_inserted:
            try:
                drw.ClearSelection2(True)
                n = drw.InsertNote("基准 A")
                if n is not None:
                    ann = call(n, "GetAnnotation")
                    if ann is not None:
                        dx, dy = coord_m(std_coords_mm, "datum")
                        try: ann.SetPosition2(dx, dy, 0)
                        except Exception: pass
                    log("  + Note 基准 A OK")
            except Exception as exc:
                warnings_box.append({"code":"datum_note_exc","msg":str(exc)})
    except Exception as exc:
        warnings_box.append({"code":"notes_outer","msg":str(exc)})

    # 12) 保存（_v4 后缀）
    log("[9/9] 保存 SLDDRW / PDF / DXF（_v4 后缀）")
    slddrw = os.path.join(out_dir, f"{base_name}_v4.SLDDRW")
    pdf    = os.path.join(out_dir, f"{base_name}_v4.PDF")
    dxf    = os.path.join(out_dir, f"{base_name}_v4.DXF")
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    ok1 = drw.Extension.SaveAs(slddrw, 0, 1, vt_dispatch_none(), err, warn)
    log(f"  SLDDRW: {'OK' if ok1 else 'FAIL'}  err={err.value}")
    try:
        pdf_data = sw.GetExportFileData(1)
        sn = drw.GetSheetNames if not callable(getattr(drw,"GetSheetNames",None)) else drw.GetSheetNames()
        sheet_names = list(sn) if sn else []
        if pdf_data and sheet_names:
            try:
                if callable(getattr(pdf_data,"SetSheets",None)):
                    pdf_data.SetSheets(0, sheet_names)
            except Exception: pass
        err.value = 0; warn.value = 0
        ok2 = drw.Extension.SaveAs(pdf, 0, 1, pdf_data, err, warn)
        log(f"  PDF:    {'OK' if ok2 else 'FAIL'}  err={err.value}")
    except Exception as exc:
        log(f"  PDF EXC {exc}")
    try:
        err.value = 0; warn.value = 0
        ok3 = drw.Extension.SaveAs(dxf, 0, 1, vt_dispatch_none(), err, warn)
        log(f"  DXF:    {'OK' if ok3 else 'FAIL'}  err={err.value}")
    except Exception as exc:
        log(f"  DXF EXC {exc}")

    warn_path = os.path.join(out_dir, f"{base_name}_v4_warnings.json")
    with open(warn_path, "w", encoding="utf-8") as f:
        json.dump({"part": part_path, "warnings": warnings_box,
                   "std_coords_mm": std_coords_mm}, f, ensure_ascii=False, indent=2)
    log(f"  Warnings: {len(warnings_box)} 条")

    try: sw.CloseDoc(call(drw, "GetTitle"))
    except Exception: pass
    return {"slddrw": slddrw, "pdf": pdf, "dxf": dxf, "warnings": warn_path,
            "scale": scale_label, "section": bool(section_view),
            "datum": datum_inserted, "surf_finish": sf_inserted,
            "std_coords_mm": std_coords_mm}

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PART
    res = generate_for(target)
    log("\n[DONE] " + json.dumps(res, ensure_ascii=False, default=str))
