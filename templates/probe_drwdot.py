"""探针：验证 gb_a4_landscape.drwdot 是否符合规格

运行：python templates/probe_drwdot.py
要求：SolidWorks 2025 已启动
输出：.trae/specs/craft-gb-drwdot-template/probe_result.json
"""
import sys, json, traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TPL = REPO_ROOT / "templates" / "gb_a4_landscape.drwdot"
OUT = REPO_ROOT / ".trae" / "specs" / "craft-gb-drwdot-template" / "probe_result.json"


def invoke_method(obj, name, *args):
    """通过 IDispatch 调用 method，返回原始结果。"""
    import pythoncom
    iid = obj._oleobj_.GetIDsOfNames(name)
    return obj._oleobj_.Invoke(iid, 0, pythoncom.DISPATCH_METHOD, True, *args)


def main():
    import pythoncom
    import win32com.client

    if not TPL.exists():
        print(f"[ERR] template not found: {TPL}")
        return 2

    sw = win32com.client.GetActiveObject("SldWorks.Application")

    model = sw.NewDocument(str(TPL), 12, 0.297, 0.210)
    if model is None:
        print("[ERR] NewDocument from template returned None"); return 3

    drw = model
    result = {"template": str(TPL), "checks": {}, "summary": {}}

    # 1) sheet 尺寸 — 用 GetProperties2（CDispatch property access 返回 CDispatch）
    try:
        sheet = drw.GetCurrentSheet  # CDispatch property access
        props = invoke_method(sheet, "GetProperties2")
        if props and len(props) >= 7:
            w = float(props[5]); h = float(props[6])
            ok = abs(w - 0.297) < 0.005 and abs(h - 0.210) < 0.005
            result["checks"]["sheet_size_a4"] = {"pass": ok, "w": w, "h": h, "raw": list(props)}
        else:
            result["checks"]["sheet_size_a4"] = {"pass": False, "raw": list(props) if props else None}
    except Exception as e:
        result["checks"]["sheet_size_a4"] = {"pass": False, "error": str(e)}

    # 2) 字高 — 优先 GetUserPreferenceTextFormat(1).CharHeight (Note 默认字高，单位 m)
    try:
        ch = None
        try:
            tf = drw.GetUserPreferenceTextFormat(1)
            if tf is not None:
                ch = float(tf.CharHeight)
        except Exception:
            ch = None
        if ch is None:
            ch = float(drw.GetUserPreferenceDoubleValue(89))
        result["checks"]["text_height_ge_3_5mm"] = {"pass": ch >= 0.0035, "value_m": ch}
    except Exception as e:
        result["checks"]["text_height_ge_3_5mm"] = {"pass": False, "error": str(e)}

    # 3) 图层数
    try:
        lm = drw.GetLayerManager
        cnt = None
        # 试 GetCount method
        try:
            cnt = invoke_method(lm, "GetCount")
        except Exception:
            cnt = None
        # 枚举
        if cnt is None:
            names = []
            try:
                first = lm.GetFirstLayer
                while first is not None:
                    try:
                        n = invoke_method(first, "Name")
                    except Exception:
                        n = None
                    names.append(n or "")
                    try:
                        first = first.GetNext
                    except Exception:
                        first = None
                cnt = len(names)
            except Exception:
                cnt = 0
        result["checks"]["layer_count_ge_5"] = {"pass": int(cnt) >= 5, "count": int(cnt)}
    except Exception as e:
        result["checks"]["layer_count_ge_5"] = {"pass": False, "error": str(e)}

    # 4) NoteBlock + 5) PRP
    ann_cnt = 0
    prp_cnt = 0
    iter_err = None
    try:
        view = drw.GetFirstView
        view_idx = 0
        while view is not None and view_idx < 50:
            view_idx += 1
            try:
                ann = view.GetFirstAnnotation3
                ann_idx = 0
                while ann is not None and ann_idx < 1000:
                    ann_idx += 1
                    try:
                        atype = invoke_method(ann, "GetType")
                    except Exception:
                        atype = None
                    if atype in (2, 6):
                        ann_cnt += 1
                        # 取 Note 文本（GetText 拿展开后字符串；PropertyLinkedText 拿原始 $PRP 链接）
                        try:
                            obj = ann.GetSpecificAnnotation
                            txt = ""
                            try:
                                txt = invoke_method(obj, "GetText") or ""
                            except Exception:
                                txt = ""
                            linked = ""
                            try:
                                linked = obj.PropertyLinkedText or ""
                            except Exception:
                                linked = ""
                            blob = f"{txt}|{linked}"
                            if "$PRP" in blob:
                                prp_cnt += 1
                        except Exception:
                            pass
                    try:
                        ann = ann.GetNext3
                    except Exception:
                        ann = None
            except Exception:
                pass
            try:
                view = view.GetNextView
            except Exception:
                view = None
    except Exception as e:
        iter_err = str(e)

    if iter_err:
        result["checks"]["_iter_err"] = iter_err
    result["checks"]["noteblock_ge_13"] = {"pass": ann_cnt >= 13, "count": ann_cnt}
    result["checks"]["prp_links_ge_3"] = {"pass": prp_cnt >= 3, "count": prp_cnt}

    pass_n = sum(1 for k, v in result["checks"].items()
                 if isinstance(v, dict) and v.get("pass"))
    total = sum(1 for k, v in result["checks"].items() if isinstance(v, dict) and "pass" in v)
    result["summary"] = {"pass_count": pass_n, "total": total, "all_pass": pass_n == total}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    try:
        sw.CloseDoc(drw.GetTitle)
    except Exception:
        pass

    return 0 if result["summary"]["all_pass"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
