"""v2.2 Task 7.5: Layout Solver v2 分析 — 从 QC JSON 提取 outline

从现有 QC JSON 中提取视图 outline，检查 titlebar_collision
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
        if not isinstance(outline, list) or len(outline) < 4:
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
        if not isinstance(outline, list) or len(outline) < 4:
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
            if not isinstance(o1, list) or not isinstance(o2, list) or len(o1) < 4 or len(o2) < 4:
                continue
            if o1[0] < o2[2] and o1[2] > o2[0] and o1[1] < o2[3] and o1[3] > o2[1]:
                ox = min(o1[2], o2[2]) - max(o1[0], o2[0])
                oy = min(o1[3], o2[3]) - max(o1[1], o2[1])
                overlaps.append({"view1": n1, "view2": n2, "overlap_area_m2": round(ox * oy, 6)})
    return overlaps


def extract_outlines_from_qc(qc_data):
    """从 QC JSON 中提取视图 outline"""
    outlines = {}
    # QC 数据结构: info -> views -> [view -> outline]
    info = qc_data.get("info", {})
    views = info.get("views", [])
    for view in views:
        name = view.get("name", "")
        outline = view.get("outline", [])
        if name and outline and len(outline) >= 4:
            outlines[name] = [float(outline[0]), float(outline[1]), float(outline[2]), float(outline[3])]
    return outlines


def main():
    v5_dir = ROOT / "drw_output/v5"
    runs_dir = ROOT / "drw_output/runs"

    # 所有 LB26001_36 零件
    lb_parts = []
    for i in range(1, 51):
        base = f"LB26001-A-04-{i:03d}"
        part = ROOT / "3D转2D测试图纸" / f"{base}.SLDPRT"
        if part.exists():
            lb_parts.append(base)

    # core_12 零件
    with open(ROOT / "validation_sets/core_12.json", "r", encoding="utf-8") as f:
        core12 = json.load(f)
    core12_bases = [item["base"] for item in core12["items"]]

    all_parts = lb_parts + [b for b in core12_bases if b not in lb_parts]

    print(f"=== Layout Solver v2 分析 (从 QC JSON) ===")
    print(f"TITLEBAR_BOX: {TITLEBAR_BOX}")
    print(f"FRAME_BOX: {FRAME_BOX}")
    print(f"Total parts: {len(all_parts)}")
    print()

    results = []
    total_titlebar_collisions = 0
    total_out_of_frame = 0
    total_view_overlaps = 0
    analyzed = 0

    for base in all_parts:
        # 查找 QC JSON
        qc_path = v5_dir / f"{base}_v5_qc.json"
        if not qc_path.exists():
            # 搜索 runs 目录
            if runs_dir.exists():
                for run_id_dir in runs_dir.iterdir():
                    if run_id_dir.is_dir():
                        p = run_id_dir / "qc" / f"{base}_v5_qc.json"
                        if p.exists():
                            qc_path = p
                            break
            if not qc_path.exists():
                continue

        try:
            with open(qc_path, "r", encoding="utf-8") as f:
                qc_data = json.load(f)
        except Exception:
            continue

        outlines = extract_outlines_from_qc(qc_data)
        if not outlines:
            continue

        analyzed += 1
        tc = _check_titlebar_collision(outlines)
        of = _check_out_of_frame(outlines)
        vo = _check_view_overlap(outlines)

        total_titlebar_collisions += len(tc)
        total_out_of_frame += len(of)
        total_view_overlaps += len(vo)

        if tc or of or vo:
            print(f"  {base}: views={len(outlines)} titlebar_col={len(tc)} out_of_frame={len(of)} overlap={len(vo)}")
            for vname, vout in outlines.items():
                print(f"    {vname}: {vout}")

        results.append({
            "base": base,
            "view_count": len(outlines),
            "titlebar_collisions": len(tc),
            "out_of_frame": len(of),
            "view_overlaps": len(vo),
            "outlines": outlines,
        })

    print(f"\n=== Layout 分析汇总 ===")
    print(f"分析零件数: {analyzed}")
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
            "analyzed_count": analyzed,
            "titlebar_collision_total": total_titlebar_collisions,
            "out_of_frame_total": total_out_of_frame,
            "view_overlap_total": total_view_overlaps,
            "pass": total_titlebar_collisions == 0 and total_out_of_frame == 0 and total_view_overlaps == 0,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
