"""GB A4 横式 .drwdot 模板构造器

运行：python templates/build_drwdot.py
要求：SolidWorks 2025 已启动
输出：templates/gb_a4_landscape.drwdot
"""
import os, sys, time, traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_OUT = REPO_ROOT / "templates" / "gb_a4_landscape.drwdot"

def main():
    import pythoncom
    import win32com.client
    from win32com.client import VARIANT

    # 连 SW
    try:
        sw = win32com.client.GetActiveObject("SldWorks.Application")
    except Exception:
        sw = win32com.client.Dispatch("SldWorks.Application")
        sw.Visible = True
    try:
        rev = sw.RevisionNumber() if callable(getattr(sw, "RevisionNumber", None)) else sw.RevisionNumber
    except Exception:
        rev = "?"
    print(f"[sw] rev={rev}")

    # 关掉视图箭头/等等
    try: sw.SetUserPreferenceToggle(195, False)
    except Exception: pass

    # 设字高 5 mm（应用级，确保后续 NewDocument 继承）
    try:
        sw.SetUserPreferenceDoubleValue(89, 0.005)
    except Exception: pass

    # NewDocument 用 SW 内置空白 drawing 模板（type=3 swDocDRAWING；用 paper_size=12 swDwgPaperA4size 横式）
    # NewDocument 签名: (template_path, paper_size, width, height) → 返回 IModelDoc2
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

    # 找到默认 drawing 模板
    default_drwdot = None
    candidates = []
    try:
        tpl_dir = sw.GetUserPreferenceStringValue(8)
        if tpl_dir:
            for d in str(tpl_dir).split(";"):
                d = d.strip()
                if d:
                    candidates += [Path(d) / "drawing.drwdot", Path(d) / "Drawing.drwdot",
                                    Path(d) / "gb_a4.drwdot", Path(d) / "gb.drwdot"]
    except Exception:
        pass
    # 已知 SW 2025 模板位置兜底
    candidates += [
        Path(r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb_a4.drwdot"),
        Path(r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb.drwdot"),
        Path(r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\data\templates\gb.drwdot"),
        Path(r"C:\Program Files\SOLIDWORKS Corp25\SOLIDWORKS\data\templates\drawing.drwdot"),
    ]
    for cand in candidates:
        try:
            if cand.exists():
                default_drwdot = str(cand); break
        except Exception:
            pass
    if not default_drwdot:
        default_drwdot = ""
    print(f"[template] base={default_drwdot or '(builtin)'}")

    # paper_size_e: 12 = swDwgPaperA4size_横式 (宽 297 高 210)
    # NewDocument(templateName, paperSize, width, height)
    model = sw.NewDocument(default_drwdot, 12, 0.297, 0.210)
    if model is None:
        print("[ERR] NewDocument returned None"); return 2
    drw = model
    print("[doc] new drawing")

    # 强制 paper size：当前 sheet 的 SetProperties2
    try:
        sheet = drw.GetCurrentSheet()
        # SetProperties2 签名 (paperSize, templateIn, scale1, scale2, firstAngle, templateName, width, height, propertyViewName, zoneIDs)
        # 或 SetProperties(paperSize, templateIn, scale1, scale2, firstAngle, templateName, width, height)
        try:
            sheet.SetProperties2(12, 1, 1, 1, True, "", 0.297, 0.210, "", 0)  # firstAngle=True
        except Exception:
            try: sheet.SetProperties(12, 1, 1, 1, True, "", 0.297, 0.210)
            except Exception: pass
    except Exception as e:
        print(f"[sheet] SetProperties failed: {e}")

    # 字高再设一次（通过 TextFormat 强制文档级字高 5mm）
    try:
        tf = drw.GetUserPreferenceTextFormat(1)
        if tf is not None:
            tf.CharHeight = 0.005
            drw.SetUserPreferenceTextFormat(1, tf)
    except Exception:
        pass
    try:
        drw.SetUserPreferenceDoubleValue(89, 0.005)
    except Exception: pass

    # 5 图层
    try:
        lm = drw.GetLayerManager()
    except Exception:
        lm = None
    if lm is not None:
        layers = [
            ("粗实", "thick solid", 0x000000, 0, 6),     # weight 6 ≈ 0.7mm
            ("细实", "thin solid",  0x000000, 0, 2),
            ("虚线", "dashed",      0x000000, 1, 2),
            ("点划", "center",      0x0000FF, 4, 2),     # BGR 0x0000FF = 红色
            ("中心", "centerline",  0x0000FF, 4, 1),
        ]
        for n, d, c, s, w in layers:
            try:
                lm.AddLayer(n, d, c, s, w)
                print(f"[layer] +{n}")
            except Exception as e:
                print(f"[layer] {n} failed: {e}")

    # 进入 sheet sketch 画图框 + 标题栏
    try: drw.ClearSelection2(True)
    except Exception: pass
    try: drw.EditSheet()
    except Exception: pass
    try: drw.SetEditMode(0)
    except Exception: pass

    sm = model.SketchManager
    try: sm.InsertSketch(True)
    except Exception: pass

    def line(x1,y1,x2,y2):
        try: sm.CreateLine(x1, y1, 0, x2, y2, 0)
        except Exception:
            try: sm.CreateLine2(x1, y1, 0, x2, y2, 0)
            except Exception as e: print(f"[line] {e}")

    # 外框
    line(0.010,0.010, 0.287,0.010)
    line(0.287,0.010, 0.287,0.200)
    line(0.287,0.200, 0.010,0.200)
    line(0.010,0.200, 0.010,0.010)
    # 内框
    line(0.025,0.015, 0.282,0.015)
    line(0.282,0.015, 0.282,0.195)
    line(0.282,0.195, 0.025,0.195)
    line(0.025,0.195, 0.025,0.015)
    # 标题栏外框
    line(0.102,0.015, 0.282,0.015)
    line(0.282,0.015, 0.282,0.055)
    line(0.282,0.055, 0.102,0.055)
    line(0.102,0.055, 0.102,0.015)
    # 横线
    line(0.102,0.028, 0.282,0.028)
    line(0.102,0.041, 0.282,0.041)
    # 竖线
    line(0.137,0.015, 0.137,0.055)
    line(0.182,0.015, 0.182,0.055)
    line(0.227,0.015, 0.227,0.055)
    line(0.252,0.015, 0.252,0.055)

    # 退 sketch
    try: sm.InsertSketch(True)
    except Exception: pass

    # 标题栏 15 个 InsertNote（前 12 中文标签 + 3 PRP）
    cells = [
        (0.104,0.043,"机型"), (0.139,0.043,"品名"), (0.184,0.043,"图号"), (0.229,0.043,"类别"), (0.254,0.043,"数量"),
        (0.104,0.030,"材质"), (0.139,0.030,"表面处理"), (0.184,0.030,"比例"), (0.229,0.030,"重量"), (0.254,0.030,"单位"),
        (0.104,0.017,"设计"), (0.139,0.017,"日期"),
        (0.184,0.017, '$PRP:"图号"'),
        (0.229,0.017, '$PRP:"类别"'),
        (0.254,0.017, '$PRP:"数量"'),
    ]
    try: drw.ClearSelection2(True)
    except Exception: pass
    for x,y,text in cells:
        try:
            note = drw.InsertNote(text)
            if note is not None:
                try:
                    ann = note.GetAnnotation()
                    ann.SetPosition2(x, y, 0)
                except Exception: pass
            try: drw.ClearSelection2(True)
            except Exception: pass
            print(f"[note] +{text}")
        except Exception as e:
            print(f"[note] {text} failed: {e}")

    # 强制重建
    try: drw.ForceRebuild3(True)
    except Exception: pass
    try: drw.GraphicsRedraw2()
    except Exception: pass

    # SaveAs .drwdot (type=swDocTEMPLATE_DRAWING=1 不准；用 SaveAs3 with SaveAsTemplate options)
    TEMPLATE_OUT.parent.mkdir(parents=True, exist_ok=True)
    save_err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    save_warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    target = str(TEMPLATE_OUT)

    # 先尝试 SaveAs3
    saved = False
    try:
        # SaveAs3(filename, version, options, error, warnings)
        # options=1 swSaveAsOptions_Silent
        ok = drw.Extension.SaveAs(target, 0, 1, None, save_err, save_warn)
        saved = bool(ok)
        print(f"[save] Extension.SaveAs ok={ok} err={save_err.value} warn={save_warn.value}")
    except Exception as e:
        print(f"[save] Extension.SaveAs failed: {e}")

    if not saved or not Path(target).exists():
        try:
            ok = drw.SaveAs2(target, 0, True, False)
            saved = bool(ok)
            print(f"[save] SaveAs2 ok={ok}")
        except Exception as e:
            print(f"[save] SaveAs2 failed: {e}")

    # 关闭文档
    try: sw.CloseDoc(model.GetTitle())
    except Exception: pass

    # 验证
    if Path(target).exists():
        size = Path(target).stat().st_size
        print(f"[result] {target} size={size} bytes")
        if size < 50_000:
            print("[WARN] file < 50KB")
            return 3
        return 0
    else:
        print("[ERR] template not saved")
        return 4

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
