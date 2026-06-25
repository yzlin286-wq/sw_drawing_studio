"""
drw_generate_v2.py
---
按公司 2D 工程图对标规范，给一个 SLDPRT 自动生成 SLDDRW + PDF + DXF。

新增能力（相对 v1）：
- ② 技术要求注释块（未注圆角 R0.5 / 去毛刺 / GB/T 1804-m / 未注角度 ±0.5°）
- ③ 表面粗糙度符号 + 形位公差基准 A 示例
- ④ 标题栏属性同步：从 SLDPRT 读 13 项 -> SLDDRW；MassProperties 自动写"重量"
- ⑤ 缺失属性告警 -> 写入侧文件 *_warnings.json
- 输出：SLDDRW + PDF + DXF + warnings.json
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

# 技术要求文本（按公司常见标注，可按需调整）
TECH_NOTES = (
    "技术要求：\n"
    "1. 未注圆角 R0.5；\n"
    "2. 未注公差按 GB/T 1804-m；\n"
    "3. 未注角度公差 ±0.5°；\n"
    "4. 加工后去毛刺、锐边倒钝 0.2×45°；\n"
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

# ---------------- 主流程 ----------------
def generate_for(part_path, *, out_dir=OUT_DIR, sw=None, do_close_drw=True):
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(part_path))[0]
    warnings_box = []  # 收集缺失告警

    # --- 连接 ---
    if sw is None:
        log("[..] 连接 SW")
        try: sw = wc.GetActiveObject("SldWorks.Application")
        except Exception:
            sw = wc.Dispatch("SldWorks.Application"); sw.Visible = True; time.sleep(2)

    # --- 关掉同名遗留 ---
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

    # --- 打开 SLDPRT ---
    log(f"[1/8] 打开 {os.path.basename(part_path)}")
    e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    part = sw.OpenDoc6(part_path, 1, 1|16|256, "", e, w)
    if part is None:
        raise SystemExit(f"打开零件失败 errors={e.value}")

    # --- 读取 13 项属性 + 缺失告警 ---
    log("[2/8] 读取标题栏 13 项属性 + MassProperties 自动写'重量'")
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
    src_props_source = ""
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
            src_filled_max = f
            src_props = cur
            src_props_source = cn or "(doc)"
    log(f"  属性来源: {src_props_source}; 非空 {src_filled_max}/{len(PROP_KEYS)}")

    # MassProperties: 写"重量"（克）
    try:
        mp = part.Extension.CreateMassProperty()
        try: mp.UseSystemUnits = True
        except Exception: pass
        mass_kg = call(mp, "Mass")
        if isinstance(mass_kg, (int, float)) and mass_kg > 0:
            grams = round(mass_kg * 1000, 2)
            src_props["重量"] = f"{grams} g"
            log(f"  Mass = {mass_kg:.6f} kg -> 重量 = {grams} g")
        else:
            warnings_box.append({"code":"mass_unavailable","msg":"无法读取 Mass，请人工填写重量"})
    except Exception as exc:
        warnings_box.append({"code":"mass_err","msg":str(exc)})

    if not src_props.get("图号"): src_props["图号"] = base_name
    if not src_props.get("数量"): src_props["数量"] = "1"
    if not src_props.get("UNIT_OF_MEASURE"): src_props["UNIT_OF_MEASURE"] = "mm"
    if not src_props.get("SWFormatSize"): src_props["SWFormatSize"] = "210mm*297mm"

    # 缺失告警
    for k in PROP_KEYS:
        if not src_props.get(k):
            warnings_box.append({"code":"prop_missing","key":k,"msg":f"标题栏属性 [{k}] 缺失"})
    log(f"  非空属性: {sum(1 for v in src_props.values() if v)} / {len(PROP_KEYS)}；缺失告警: {sum(1 for x in warnings_box if x['code']=='prop_missing')}")

    # --- bbox -> 选比例 ---
    Lmax = 0.05
    try:
        box = part.GetPartBox(True)
        box = list(box) if box else None
        if box and len(box) >= 6:
            Lmax = max(abs(box[3]-box[0]),abs(box[4]-box[1]),abs(box[5]-box[2]))
    except Exception: pass
    if Lmax <= 0 or Lmax > 10:
        try:
            for b in (part.GetBodies2(0, False) or []):
                bb = b.GetBodyBox if not callable(getattr(b,"GetBodyBox",None)) else b.GetBodyBox()
                bb = list(bb) if bb else None
                if bb and len(bb) >= 6:
                    Lmax = max(Lmax, max(abs(bb[3]-bb[0]),abs(bb[4]-bb[1]),abs(bb[5]-bb[2])))
        except Exception: pass
    log(f"  Lmax = {Lmax*1000:.1f} mm")
    chosen = (1,1)
    EPS = 1e-9
    for n_,d_ in CANDIDATE_SCALES:
        if Lmax * (n_/d_) <= 0.10 + EPS:
            chosen = (n_, d_); break
    scale_num, scale_den = chosen
    scale_label = f"{scale_num}:{scale_den}"

    # --- 新建工程图（A4 横向，第一角投影） ---
    log("[3/8] 新建工程图 A4 横向 第一角 比例 " + scale_label)
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
    try:
        drw.SetupSheet5(sheet_name, 6, 13, scale_num, scale_den, True, "", 0.297, 0.21, "", True)
    except Exception as exc:
        log(f"  SetupSheet5 异常: {exc}")

    # --- 添加视图 ---
    log("[4/8] 创建 4 视图（前/上/右/等轴测）")
    W, H = 0.297, 0.21
    positions = [
        (("*Front",     "*前视"),     (W*0.30, H*0.55)),
        (("*Top",       "*上视"),     (W*0.30, H*0.80)),
        (("*Right",     "*右视"),     (W*0.55, H*0.55)),
        (("*Isometric", "*等轴测"),   (W*0.78, H*0.78)),
    ]
    front_view = None
    for aliases, (x,y) in positions:
        v = None
        for vname in aliases:
            try:
                v = drw.CreateDrawViewFromModelView3(part_path, vname, x, y, 0)
                if v is not None:
                    if vname.endswith("Front") or "前视" in vname:
                        front_view = v
                    log(f"  + {vname} ok")
                    break
            except Exception as exc:
                pass
        if v is not None:
            try: v.ScaleRatio = (float(scale_num), float(scale_den))
            except Exception: pass

    # --- 自动尺寸 ---
    log("[5/8] 自动导入模型尺寸")
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
            log("  OK via RunCommand(826)")
        except Exception as exc:
            warnings_box.append({"code":"dim_import_failed","msg":str(exc)})

    # --- 同步 13 项自定义属性（写到文档级 + 默认配置级，工程图标题栏 $PRP 可解析）---
    log("[6/8] 写 13 项标题栏属性")
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
                # 先尝试 Add3：如果字段不存在就创建
                rc = cpm.Add3(k, 30, val, 2)
                # 如果 rc=0 (Failed) 或 6 (Existing)，再用 Set 覆盖
                try:
                    if val:
                        cpm.Set2(k, val)
                except Exception:
                    pass
            except Exception as exc:
                warnings_box.append({"code":"prop_write_fail","key":k,"msg":str(exc)})

    # --- 技术要求 + 表面粗糙度 + 形位公差基准 ---
    log("[7/8] 技术要求注释 + 表面粗糙度 + 形位公差基准 A")
    # 1) 技术要求 Note：放在右下角（标题栏上方）
    try:
        drw.ClearSelection2(True)
        nx, ny = W*0.62, H*0.30
        note = drw.InsertNote(TECH_NOTES)
        if note is None:
            warnings_box.append({"code":"tech_note_failed","msg":"InsertNote 返回 None"})
        else:
            try:
                ann = note.GetAnnotation if not callable(getattr(note,"GetAnnotation",None)) else note.GetAnnotation()
                if ann is not None:
                    try: ann.SetPosition2(nx, ny, 0)
                    except Exception: pass
                    try: ann.SetTextFormat(0, True, None)
                    except Exception: pass
            except Exception: pass
            try: note.Angle = 0
            except Exception: pass
            log("  + 技术要求 Note OK")
    except Exception as exc:
        warnings_box.append({"code":"tech_note_exc","msg":str(exc)})

    # 2) 表面粗糙度符号：放主视图右下，Ra 3.2 默认
    try:
        if front_view is not None:
            try: front_view.SelectByName(0, "")
            except Exception: pass
        # InsertSurfaceFinishSymbol4 需要先选择实体；这里改为浮动符号 InsertSurfaceFinishSymbol2
        try:
            sf = drw.InsertSurfaceFinishSymbol2(
                4,        # symbol type: 4 = swSFSymType_AnyMethodReqd (任意工艺)
                0.0000032, # Ra 3.2 in m? -> SolidWorks API 用值原意；该参数是 Ra 字段填充字符串时用
                "",       # 其它形参在不同版本差异大
                "", "", "", "", "", "", "", "",
            )
            if sf is not None:
                ann = sf.GetAnnotation if not callable(getattr(sf,"GetAnnotation",None)) else sf.GetAnnotation()
                if ann is not None:
                    try: ann.SetPosition2(W*0.55, H*0.40, 0)
                    except Exception: pass
                log("  + 表面粗糙度 Ra 3.2 OK")
            else:
                warnings_box.append({"code":"sf_failed","msg":"InsertSurfaceFinishSymbol2 返回 None；改用 Note 兜底"})
        except Exception as exc:
            warnings_box.append({"code":"sf_exc","msg":str(exc)})
    except Exception as exc:
        warnings_box.append({"code":"sf_outer","msg":str(exc)})

    # 兜底：用 Note 写一个表面粗糙度提示
    try:
        ra_note = drw.InsertNote("\\sf<MOD-DIAM>Ra 3.2  (其余表面)")
        if ra_note is not None:
            ann = ra_note.GetAnnotation if not callable(getattr(ra_note,"GetAnnotation",None)) else ra_note.GetAnnotation()
            if ann is not None:
                try: ann.SetPosition2(W*0.55, H*0.40, 0)
                except Exception: pass
            log("  + Note 兜底 Ra 3.2 OK")
    except Exception as exc:
        warnings_box.append({"code":"sf_note_fallback","msg":str(exc)})

    # 3) 形位公差基准 A（放在主视图左侧）
    try:
        if front_view is not None:
            try: front_view.SelectByName(0, "")
            except Exception: pass
        # InsertDatumTag2(LeaderCount, ...) 在不同版本差异大；最稳妥用 Note + 文本
        d_note = drw.InsertNote("〔A〕")
        if d_note is not None:
            ann = d_note.GetAnnotation if not callable(getattr(d_note,"GetAnnotation",None)) else d_note.GetAnnotation()
            if ann is not None:
                try: ann.SetPosition2(W*0.18, H*0.55, 0)
                except Exception: pass
            log("  + 基准 A Note OK")
    except Exception as exc:
        warnings_box.append({"code":"datum_exc","msg":str(exc)})

    # --- 保存输出 ---
    log("[8/8] 保存 SLDDRW / 输出 PDF / DXF")
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

    # --- 写 warnings ---
    warn_path = os.path.join(out_dir, f"{base}_warnings.json")
    with open(warn_path, "w", encoding="utf-8") as f:
        json.dump({"part": part_path, "warnings": warnings_box}, f, ensure_ascii=False, indent=2)
    log(f"  Warnings: {len(warnings_box)} 条 -> {warn_path}")

    # 关闭工程图（保留零件）
    if do_close_drw:
        try: sw.CloseDoc(call(drw, "GetTitle"))
        except Exception: pass
    return {"slddrw": slddrw, "pdf": pdf, "dxf": dxf, "warnings": warn_path,
            "scale": scale_label, "props": src_props}

# CLI
if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PART
    res = generate_for(target)
    log("\n[DONE] " + json.dumps({k:v for k,v in res.items() if k!='props'}, ensure_ascii=False))
