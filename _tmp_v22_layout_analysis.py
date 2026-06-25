"""v2.2 Task 7.5: Layout Solver v2 分析 — titlebar_collision 检查

对 LB26001_36 和 core_12 的图纸进行 titlebar_collision 分析
不修改图纸，只读取视图 outline 并检查碰撞
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"c:\Users\Vision\Desktop\SW 相关")
sys.path.insert(0, str(ROOT))

from app.services.layout_solver_v2 import (
    LayoutSolverV2, LayoutType, FRAME_BOX, TITLEBAR_BOX,
    SCALE_LADDER, LAYOUT_TEMPLATES, SolverResult,
)

# 标题栏区域 (单位: 米)
TITLEBAR_XMIN, TITLEBAR_YMIN, TITLEBAR_XMAX, TITLEBAR_YMAX = TITLEBAR_BOX
FRAME_XMIN, FRAME_YMIN, FRAME_XMAX, FRAME_YMAX = FRAME_BOX


def _get_sw():
    """获取 SW COM 对象"""
    import win32com.client as wc
    try:
        return wc.GetActiveObject("SldWorks.Application")
    except Exception:
        try:
            return wc.Dispatch("SldWorks.Application")
        except Exception as e:
            raise RuntimeError(f"无法连接 SW: {e}")


def _check_titlebar_collision(outlines):
    """检查视图 outline 是否与标题栏碰撞

    Args:
        outlines: {view_name: [xmin, ymin, xmax, ymax]}

    Returns:
        list of collision dicts
    """
    collisions = []
    for name, outline in outlines.items():
        if len(outline) < 4:
            continue
        vxmin, vymin, vxmax, vymax = outline[:4]
        # 检查矩形重叠
        overlap_x = vxmin < TITLEBAR_XMAX and vxmax > TITLEBAR_XMIN
        overlap_y = vymin < TITLEBAR_YMAX and vymax > TITLEBAR_YMIN
        if overlap_x and overlap_y:
            # 计算重叠面积
            ox = min(vxmax, TITLEBAR_XMAX) - max(vxmin, TITLEBAR_XMIN)
            oy = min(vymax, TITLEBAR_YMAX) - max(vymin, TITLEBAR_YMIN)
            collisions.append({
                "view": name,
                "view_outline": list(outline[:4]),
                "titlebar_box": list(TITLEBAR_BOX),
                "overlap_area_m2": round(ox * oy, 6),
            })
    return collisions


def _check_out_of_frame(outlines):
    """检查视图是否超出图框"""
    issues = []
    for name, outline in outlines.items():
        if len(outline) < 4:
            continue
        vxmin, vymin, vxmax, vymax = outline[:4]
        if vxmin < FRAME_XMIN or vymin < FRAME_YMIN or vxmax > FRAME_XMAX or vymax > FRAME_YMAX:
            issues.append({
                "view": name,
                "view_outline": list(outline[:4]),
                "frame_box": list(FRAME_BOX),
            })
    return issues


def _check_view_overlap(outlines):
    """检查视图间重叠"""
    names = list(outlines.keys())
    overlaps = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1, n2 = names[i], names[j]
            o1 = outlines[n1]
            o2 = outlines[n2]
            if len(o1) < 4 or len(o2) < 4:
                continue
            overlap_x = o1[0] < o2[2] and o1[2] > o2[0]
            overlap_y = o1[1] < o2[3] and o1[3] > o2[1]
            if overlap_x and overlap_y:
                ox = min(o1[2], o2[2]) - max(o1[0], o2[0])
                oy = min(o1[3], o2[3]) - max(o1[1], o2[1])
                overlaps.append({
                    "view1": n1,
                    "view2": n2,
                    "overlap_area_m2": round(ox * oy, 6),
                })
    return overlaps


def analyze_drawing(sw, drw_path):
    """分析单个图纸的 layout"""
    import pythoncom
    import win32com.client

    result = {
        "drw_path": str(drw_path),
        "success": False,
        "views": {},
        "titlebar_collisions": [],
        "out_of_frame": [],
        "view_overlaps": [],
        "reason": "",
    }

    try:
        # 打开图纸
        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_DISPATCH, None)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_DISPATCH, None)
        doc = sw.OpenDoc6(str(drw_path), 3, 1, "", errors, warnings)  # 3=Drawing, 1=Open silent
        if doc is None:
            result["reason"] = "OpenDoc6 返回 None"
            return result

        time.sleep(1)  # 等待加载

        # 获取所有视图 outline
        sheet = doc.GetCurrentSheet()
        views = sheet.GetViews()
        if not views:
            result["reason"] = "无视图"
            sw.CloseDoc(doc.GetTitle())
            return result

        outlines = {}
        for view in views:
            try:
                name = view.Name
                out = view.GetOutline
                if out and len(out) >= 4:
                    outlines[name] = [float(out[0]), float(out[1]), float(out[2]), float(out[3])]
            except Exception:
                pass

        result["views"] = outlines

        # 检查
        result["titlebar_collisions"] = _check_titlebar_collision(outlines)
        result["out_of_frame"] = _check_out_of_frame(outlines)
        result["view_overlaps"] = _check_view_overlap(outlines)
        result["success"] = True

        # 关闭文档
        sw.CloseDoc(doc.GetTitle())

    except Exception as e:
        result["reason"] = str(e)

    return result


def main():
    import win32com.client

    v5_dir = ROOT / "drw_output/v5"

    # 选择代表性零件进行 layout 分析
    # core_12 的 7 个 LB26001 + 5 个 small parts
    # LB26001_36 的 024/040（新生成）
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

    print("=== Layout Solver v2 分析 ===")
    print(f"TITLEBAR_BOX: {TITLEBAR_BOX}")
    print(f"FRAME_BOX: {FRAME_BOX}")
    print(f"Sample parts: {len(sample_parts)}")
    print()

    try:
        sw = _get_sw()
        print(f"SW connected: {sw.RevisionNumber}")
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
        total_titlebar_collisions += tc
        total_out_of_frame += of
        total_view_overlaps += vo

        status = "OK" if analysis["success"] and tc == 0 and of == 0 and vo == 0 else "ISSUE"
        print(f"  -> {status} ({dt:.1f}s) views={len(analysis.get('views', {}))} titlebar_col={tc} out_of_frame={of} overlap={vo}")

        results.append({
            "base": base,
            "success": analysis["success"],
            "view_count": len(analysis.get("views", {})),
            "titlebar_collisions": tc,
            "out_of_frame": of,
            "view_overlaps": vo,
            "details": analysis,
        })

    # 汇总
    print(f"\n=== Layout 分析汇总 ===")
    print(f"分析零件数: {len(results)}")
    print(f"titlebar_collision_total: {total_titlebar_collisions}")
    print(f"out_of_frame_total: {total_out_of_frame}")
    print(f"view_overlap_total: {total_view_overlaps}")
    print(f"验收 (all=0): {'PASS' if total_titlebar_collisions == 0 and total_out_of_frame == 0 and total_view_overlaps == 0 else 'FAIL'}")

    # 保存
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
