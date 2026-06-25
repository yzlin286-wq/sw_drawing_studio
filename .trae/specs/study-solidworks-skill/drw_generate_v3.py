"""
drw_generate_v3.py
---
在 v2 基础上新增：
- ① 自动剖视图：在主视图上画水平剖切线 -> CreateSectionViewAt5
- ② 真形位公差基准 A：InsertDatumTag2
- ③ 真表面粗糙度：InsertSurfaceFinishSymbol3 / 2

仍兼容：
- 13 项标题栏属性同步
- MassProperties 自动写"重量"
- 技术要求 Note
- 缺失告警 *_warnings.json
"""
import os, sys, time, json, math, traceback
import pythoncom
import win32com.client as wc
from win32com.client import VARIANT

sys.stdout.reconfigure(line_buffering=True)
def log(*a, **kw): print(*a, **kw, flush=True)

ROOT = r"c:\Users\Vision\Desktop\SW 相关"
DEFAULT_PART = os.path.join(ROOT, r"3D转2D测试图纸\LB26001-A-04-001.SLDPRT")
OUT_DIR = os.path.join(ROOT, "drw_output")

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

    if sw is None:
        log("[..] 连接 SW")
        try: sw = wc.GetActiveObject("SldWorks.Application")
        except Exception:
            sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

    target_drw = os.path.join(out_dir, f"{base_name}.SLDDRW")
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
        f = os.path.join(out_dir, base_name + ext_)
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

    # 5) 4 个标准视图
    log("[4/9] 4 个标准视图")
    W, H = 0.297, 0.21
    positions = [
        (("*Front", "*前视"),     (W*0.28, H*0.55)),
        (("*Top",   "*上视"),     (W*0.28, H*0.82)),
        (("*Right", "*右视"),     (W*0.55, H*0.55)),
        (("*Isometric","*等轴测"),(W*0.80, H*0.80)),
    ]
    front_view = None
    for aliases, (x,y) in positions:
        v = None
        for vname in aliases:
            try:
                v = drw.CreateDrawViewFromModelView3(part_path, vname, x, y, 0)
                if v is not None:
                    if vname in ("*Front","*前视"): front_view = v
                    log(f"  + {vname} ok")
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

    # 7) ★ 剖视图 ★
    log("[6/9] 创建剖视图")
    section_view = None
    try:
        if front_view is not None:
            ob = view_outline_box(front_view)
            if ob:
                xmin, ymin, xmax, ymax = ob
                cy = (ymin + ymax)/2.0
                pad = 0.005
                drw.ClearSelection2(True)
                line = None
                try:
                    line = drw.SketchManager.CreateLine(xmin - pad, cy, 0, xmax + pad, cy, 0)
                    log(f"  + 剖切线 ({(xmin-pad)*1000:.1f},{cy*1000:.1f})->({(xmax+pad)*1000:.1f},{cy*1000:.1f}) mm")
                except Exception as exc:
                    log(f"  CreateLine 异常: {exc}")
                # Select the line
                selected = False
                try:
                    if line is not None:
                        line.Select4(False, None)
                        selected = True
                except Exception: pass
                if not selected:
                    try:
                        drw.Extension.SelectByID2("Line1", "SKETCHSEGMENT",
                            (xmin + xmax)/2.0, cy, 0, False, 0, empty_callout(), 0)
                        selected = True
                    except Exception: pass

                sx, sy = (W*0.28, H*0.20)
                # 实际上 CreateSectionViewAt5 第 5 参是 swCreateSectionView_e 选项位掩码
                # 0=DefaultOptions, 1=Excluded, 2=AutoStartSectionView, 4=DisplaySurfaceCut
                attempts = [
                    ("CreateSectionViewAt5 (auto)",
                     lambda: drw.CreateSectionViewAt5(sx, sy, 0, "A", 2|4, vt_dispatch_none(), 0)),
                    ("CreateSectionViewAt5 (default)",
                     lambda: drw.CreateSectionViewAt5(sx, sy, 0, "A", 0, vt_dispatch_none(), 0)),
                    # 老接口 CreateSectionView (无 Excluded)
                    ("CreateSectionView",
                     lambda: drw.CreateSectionView(sx, sy, "A")),
                ]
                for name, fn in attempts:
                    try:
                        sv = fn()
                        if sv is not None:
                            section_view = sv
                            try: sv.ScaleRatio = (float(scale_num), float(scale_den))
                            except Exception: pass
                            log(f"  + 剖视图 A-A via {name} OK")
                            break
                    except Exception as exc:
                        warnings_box.append({"code":"section_exc","fn":name,"msg":str(exc)})
                if section_view is None:
                    warnings_box.append({"code":"section_failed","msg":"所有 CreateSectionView 尝试均失败"})
        else:
            warnings_box.append({"code":"no_front_view","msg":"无前视图，跳过剖视图"})
    except Exception as exc:
        warnings_box.append({"code":"section_outer","msg":str(exc)})

    # 8) ★ 真基准 A ★ —— 用 IModelDocExtension.InsertDatumTagSymbol2(x,y,z,leaderType,label)
    log("[7/9] 形位公差基准 A + 表面粗糙度")
    datum_inserted = False
    try:
        if front_view is not None:
            try: front_view.SelectByName(0, "")
            except Exception: pass
            ob = view_outline_box(front_view)
            if ob:
                xmin, ymin, xmax, ymax = ob
                # 选中前视图最下方水平边
                try:
                    drw.Extension.SelectByID2("", "EDGE",
                        (xmin + xmax)/2.0, ymin + 0.0005, 0,
                        False, 0, empty_callout(), 0)
                except Exception: pass
                # 候选写法（很多 SolidWorks 2025 版本下这些方法存在但只在 Extension 而非 DrawingDoc）
                attempts = [
                    ("ext.InsertDatumTagSymbol2 (5)",
                     lambda: ext.InsertDatumTagSymbol2(W*0.20, ymin - 0.012, 0, 2, "A")),
                    ("ext.InsertDatumTagSymbol3 (5)",
                     lambda: ext.InsertDatumTagSymbol3(W*0.20, ymin - 0.012, 0, 2, "A")),
                    # 老版本 4 参
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
                # 兜底：用 RunCommand swCommands_DatumFeature
                if not datum_inserted:
                    try:
                        # swCommands_DatumFeature ≈ 2240
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
                    try: ann.SetPosition2(W*0.18, H*0.40, 0)
                    except Exception: pass
                log("  + 兜底 Note 〔A〕")
        except Exception: pass

    # 9) ★ 真表面粗糙度 ★ —— InsertSurfaceFinishSymbol3 第 4 参 Roughness2 必须 string
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
        # InsertSurfaceFinishSymbol3 在 SolidWorks 2014+ 的标准签名（按官方 API Help）：
        # Symbol(int), Lay(int), Roughness1(string), Roughness2(string),
        # ProductionMethod(string), SamplingLength(string), MaterialRemoval(int),
        # OtherValues(string), Angle(double), X(double), Y(double), Z(double),
        # leaderType(int), attachToFlag(int)
        sf_attempts = [
            ("ext.InsertSurfaceFinishSymbol3 (string,string)",
             lambda: ext.InsertSurfaceFinishSymbol3(
                 1, -1, "3.2", "", "", "", 1, "", 0.0,
                 W*0.55, H*0.42, 0.0, 0, 0)),
            ("ext.InsertSurfaceFinishSymbol3 (Lay 0)",
             lambda: ext.InsertSurfaceFinishSymbol3(
                 1, 0, "3.2", "", "", "", 1, "", 0.0,
                 W*0.55, H*0.42, 0.0, 0, 0)),
            ("ext.InsertSurfaceFinishSymbol2",
             lambda: ext.InsertSurfaceFinishSymbol2(
                 1, 0, 3.2, 0.0, "", "", 1, "", 0.0,
                 W*0.55, H*0.42, 0.0)),
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
        # 兜底命令
        if not sf_inserted:
            try:
                # swCommands_SurfaceFinish ≈ 2240+；直接走 Note
                pass
            except Exception: pass
    except Exception as exc:
        warnings_box.append({"code":"sf_outer","msg":str(exc)})
    if not sf_inserted:
        try:
            n = drw.InsertNote("Ra 3.2 (其余表面)")
            if n:
                ann = call(n, "GetAnnotation")
                if ann is not None:
                    try: ann.SetPosition2(W*0.55, H*0.42, 0)
                    except Exception: pass
                log("  + 兜底 Note Ra 3.2")
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

    # 11) 技术要求 + Ra + 基准 A（合并三段 Note，一次写入更稳）
    log("[11/?] 技术要求/表面粗糙度/基准 A Notes")
    try:
        drw.ClearSelection2(True)
        try: drw.ActivateSheet(sheet_name)
        except Exception: pass

        # 技术要求 Note
        try:
            note = drw.InsertNote(TECH_NOTES)
            if note is not None:
                ann = call(note, "GetAnnotation")
                if ann is not None:
                    try: ann.SetPosition2(W*0.62, H*0.30, 0)
                    except Exception: pass
                log("  + 技术要求 Note OK")
            else:
                warnings_box.append({"code":"tech_note_none","msg":"InsertNote 返回 None"})
        except Exception as exc:
            warnings_box.append({"code":"tech_note_exc","msg":str(exc)})

        # 表面粗糙度兜底 Note
        if not sf_inserted:
            try:
                drw.ClearSelection2(True)
                n = drw.InsertNote("Ra 3.2  (其余表面)")
                if n is not None:
                    ann = call(n, "GetAnnotation")
                    if ann is not None:
                        try: ann.SetPosition2(W*0.55, H*0.42, 0)
                        except Exception: pass
                    log("  + Note Ra 3.2 OK")
            except Exception as exc:
                warnings_box.append({"code":"sf_note_exc","msg":str(exc)})

        # 基准 A 兜底 Note
        if not datum_inserted:
            try:
                drw.ClearSelection2(True)
                n = drw.InsertNote("基准 A")
                if n is not None:
                    ann = call(n, "GetAnnotation")
                    if ann is not None:
                        try: ann.SetPosition2(W*0.18, H*0.40, 0)
                        except Exception: pass
                    log("  + Note 基准 A OK")
            except Exception as exc:
                warnings_box.append({"code":"datum_note_exc","msg":str(exc)})
    except Exception as exc:
        warnings_box.append({"code":"notes_outer","msg":str(exc)})

    # 12) 保存
    log("[9/9] 保存 SLDDRW / PDF / DXF")
    base = src_props.get("图号") or base_name
    slddrw = os.path.join(out_dir, f"{base}.SLDDRW")
    pdf    = os.path.join(out_dir, f"{base}.PDF")
    dxf    = os.path.join(out_dir, f"{base}.DXF")
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

    warn_path = os.path.join(out_dir, f"{base}_warnings.json")
    with open(warn_path, "w", encoding="utf-8") as f:
        json.dump({"part": part_path, "warnings": warnings_box}, f, ensure_ascii=False, indent=2)
    log(f"  Warnings: {len(warnings_box)} 条")

    try: sw.CloseDoc(call(drw, "GetTitle"))
    except Exception: pass
    return {"slddrw": slddrw, "pdf": pdf, "dxf": dxf, "warnings": warn_path,
            "scale": scale_label, "section": section_view is not None,
            "datum": datum_inserted, "surf_finish": sf_inserted}

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PART
    res = generate_for(target)
    log("\n[DONE] " + json.dumps(res, ensure_ascii=False, default=str))
