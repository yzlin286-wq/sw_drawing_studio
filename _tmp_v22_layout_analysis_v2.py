"""v2.2 Task 7.5: Layout Solver v2 分析 — titlebar_collision 检查 (v2)

修复：使用 ActivateDoc3 激活文档，等待加载
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"c:\Users\Vision\Desktop\SW 相关")
sys.path.insert(0, str(ROOT))

from app.services.layout_solver_v2 import FRAME_BOX, TITLEBAR_BOX

TITLEBAR_XMIN, TITLEBAR_YMIN, TITLEBAR_XMAX, TITLEBAR_YMAX = TITLEBAR_BOX
FRAME_XMIN, FRAME_YMIN, FRAME_XMAX, FRAME_YMAX = FRAME_BOX


def _check_titlebar_collision(outlines):
    collisions = []
    for name, outline in outlines.items():
        if len(outline) < 4:
            continue
        vxmin, vymin, vxmax, vymax = outline[:4]
        overlap_x = vxmin < TITLEBAR_XMAX and vxmax > TITLEBAR_XMIN
        overlap_y = vymin < TITLEBAR_YMAX and vymax > TITLEBAR_YMIN
        if overlap_x and overlap_y:
            ox = min(vxmax, TITLEBAR_XMAX) - max(vxmin, TITLEBAR_XMIN)
            oy = min(vymax, TITLEBAR_YMAX) - max(vymin, TITLEBAR_YMIN)
            collisions.append({
                "view": name,
                "view_outline": list(outline[:4]),
                "overlap_area_m2": round(ox * oy, 6),
            })
    return collisions


def _check_out_of_frame(outlines):
    issues = []
    for name, outline in outlines.items():
        if len(outline) < 4:
            continue
        vxmin, vymin, vxmax, vymax = outline[:4]
        if vxmin < FRAME_XMIN or vymin < FRAME_YMIN or vxmax > FRAME_XMAX or vymax > FRAME_YMAX:
            issues.append({"view": name, "view_outline": list(outline[:4])})
    return issues


def _check_view_overlap(outlines):
    names = list(outlines.keys())
    overlaps = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1, n2 = names[i], names[j]
            o1, o2 = outlines[n1], outlines[n2]
            if len(o1) < 4 or len(o2) < 4:
                continue
            if o1[0] < o2[2] and o1[2] > o2[0] and o1[1] < o2[3] and o1[3] > o2[1]:
                ox = min(o1[2], o2[2]) - max(o1[0], o2[0])
                oy = min(o1[3], o2[3]) - max(o1[1], o2[1])
                overlaps.append({"view1": n1, "view2": n2, "overlap_area_m2": round(ox * oy, 6)})
    return overlaps


def analyze_drawing(sw, drw_path):
    """分析单个图纸的 layout"""
    import pythoncom
    from win32com.client import VARIANT

    result = {
        "drw_path": str(drw_path),
        "success": False,
        "views": {},
        "titlebar_collisions": [],
        "out_of_frame": [],
        "view_overlaps": [],
        "reason": "",
    }

    drw_path = str(Path(drw_path).resolve())
    base_name = Path(drw_path).name

    try:
        # 先关闭所有文档
        try:
            sw.CloseAllDocuments()
        except Exception:
            pass
        time.sleep(0.5)

        # 打开图纸 (使用 VT_I4 类型的 errors/warnings)
        err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        doc = sw.OpenDoc6(drw_path, 3, 257, "", err, warn)
        if doc is None:
            result["reason"] = f"OpenDoc6 返回 None, err={err.value}, warn={warn.value}"
            return result

        # 等待加载
        time.sleep(2)

        # 获取 sheet
        try:
            sheet = doc.GetCurrentSheet()
        except Exception as e:
            result["reason"] = f"GetCurrentSheet failed: {e}"
            try:
                sw.CloseDoc(doc.GetTitle())
            except Exception:
                pass
            return result

        # 获取视图
        try:
            views = sheet.GetViews()
        except Exception as e:
            result["reason"] = f"GetViews failed: {e}"
            try:
                sw.CloseDoc(doc.GetTitle())
            except Exception:
                pass
            return result

        if not views:
            result["reason"] = "GetViews 返回空"
            try:
                sw.CloseDoc(doc.GetTitle())
            except Exception:
                pass
            return result

        # 获取每个视图的 outline
        outlines = {}
        for view in views:
            try:
                name = view.Name
                # GetOutline 是属性，不是方法
                out = view.GetOutline
                if out is not None:
                    o = list(out)
                    if len(o) >= 4:
                        outlines[name] = [float(o[0]), float(o[1]), float(o[2]), float(o[3])]
            except Exception as e:
                outlines[name] = {"error": str(e)}

        result["views"] = outlines

        # 只对有效的 outline 进行检查
        valid_outlines = {k: v for k, v in outlines.items() if isinstance(v, list) and len(v) >= 4}
        result["titlebar_collisions"] = _check_titlebar_collision(valid_outlines)
        result["out_of_frame"] = _check_out_of_frame(valid_outlines)
        result["view_overlaps"] = _check_view_overlap(valid_outlines)
        result["success"] = True

        # 关闭文档
        try:
            sw.CloseDoc(doc.GetTitle())
        except Exception:
            pass
        time.sleep(0.5)

    except Exception as e:
        result["reason"] = str(e)

    return result


def main():
    import win32com.client as wc

    v5_dir = ROOT / "drw_output/v5"

    sample_parts = [
        "LB26001-A-04-001",
        "LB26001-A-04-002",
        "LB26001-A-04-003",
        "LB26001-A-04-004",
        "LB26001-A-04-005",
        "LB26001-A-04-007",
        "LB26001-A-04-009",
        "LB26001-A-04-024",
        "LB26001-A-04-040",
    ]

    print("=== Layout Solver v2 分析 (v2) ===")
    print(f"TITLEBAR_BOX: {TITLEBAR_BOX}")
    print(f"FRAME_BOX: {FRAME_BOX}")
    print(f"Sample parts: {len(sample_parts)}")
    print()

    try:
        sw = wc.GetActiveObject("SldWorks.Application")
        print(f"SW connected: {sw.RevisionNumber}")
    except Exception:
        try:
            sw = wc.Dispatch("SldWorks.Application")
            print(f"SW dispatched: {sw.RevisionNumber}")
        except Exception as e:
            print(f"SW connection failed: {e}")
            return

    results = []
    total_titlebar_collisions = 0
    total_out_of_frame = 0
    total_view_overlaps = 0

    for i, base in enumerate(sample_parts, 1):
        drw_path = v5_dir / f"{base}_v5.SLDDRW"
        if not drw_path.exists():
            print(f"[{i}/{len(sample_parts)}] {base}: SLDDRW not found, skip")
            continue

        print(f"[{i}/{len(sample_parts)}] {base}: analyzing...")
        t0 = time.time()
        analysis = analyze_drawing(sw, drw_path)
        dt = time.time() - t0

        tc = len(analysis.get("titlebar_collisions", []))
        of = len(analysis.get("out_of_frame", []))
        vo = len(analysis.get("view_overlaps", []))
        vc = len(analysis.get("views", {}))
        total_titlebar_collisions += tc
        total_out_of_frame += of
        total_view_overlaps += vo

        if analysis["success"]:
            status = "OK" if tc == 0 and of == 0 and vo == 0 else "ISSUE"
        else:
            status = "FAIL"
        print(f"  -> {status} ({dt:.1f}s) views={vc} titlebar_col={tc} out_of_frame={of} overlap={vo} reason={analysis.get('reason','')}")

        # 打印视图 outline
        for vname, vout in analysis.get("views", {}).items():
            if isinstance(vout, list):
                print(f"    {vname}: {vout}")

        results.append({
            "base": base,
            "success": analysis["success"],
            "view_count": vc,
            "titlebar_collisions": tc,
            "out_of_frame": of,
            "view_overlaps": vo,
            "reason": analysis.get("reason", ""),
            "details": analysis,
        })

    print(f"\n=== Layout 分析汇总 ===")
    print(f"分析零件数: {len(results)}")
    print(f"titlebar_collision_total: {total_titlebar_collisions}")
    print(f"out_of_frame_total: {total_out_of_frame}")
    print(f"view_overlap_total: {total_view_overlaps}")
    print(f"验收 (all=0): {'PASS' if total_titlebar_collisions == 0 and total_out_of_frame == 0 and total_view_overlaps == 0 else 'FAIL'}")

    v22_dir = ROOT / "drw_output/v22_validation"
    v22_dir.mkdir(parents=True, exist_ok=True)
    out_file = v22_dir / "layout_solver_v2_analysis.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "titlebar_box": list(TITLEBAR_BOX),
            "frame_box": list(FRAME_BOX),
            "sample_count": len(results),
            "titlebar_collision_total": total_titlebar_collisions,
            "out_of_frame_total": total_out_of_frame,
            "view_overlap_total": total_view_overlaps,
            "pass": total_titlebar_collisions == 0 and total_out_of_frame == 0 and total_view_overlaps == 0,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
