"""v2.2 Task 7.5: Layout Solver v2 分析 — 使用 040 实际 outline

从 040 v6 pipeline 输出中提取的视图 outline 进行 titlebar_collision 分析
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

# 040 的实际视图 outline (从 v6 pipeline 输出提取)
# [v1.6 layout] 工程图视图1: outline=[0.0563, 0.1068, 0.1037, 0.1732]  # front
# [v1.6 layout] 工程图视图2: outline=[0.0563, 0.0678, 0.1037, 0.0922]  # top
# [v1.6 layout] 工程图视图3: outline=[0.1678, 0.1068, 0.1922, 0.1732]  # right
# [v1.6 layout] 工程图视图4: outline=[0.2064, 0.1197, 0.2536, 0.1980]  # iso

sample_outlines = {
    "LB26001-A-04-040": {
        "工程图视图1": [0.0563, 0.1068, 0.1037, 0.1732],  # front
        "工程图视图2": [0.0563, 0.0678, 0.1037, 0.0922],  # top
        "工程图视图3": [0.1678, 0.1068, 0.1922, 0.1732],  # right
        "工程图视图4": [0.2064, 0.1197, 0.2536, 0.1980],  # iso
    },
}

# LAYOUT_TEMPLATES T4 的视图中心位置
T4_CENTERS = {
    "front": (0.080, 0.140),
    "top": (0.080, 0.080),
    "right": (0.180, 0.140),
    "iso": (0.230, 0.180),
}


def check_titlebar_collision(outlines):
    collisions = []
    for name, outline in outlines.items():
        vxmin, vymin, vxmax, vymax = outline
        overlap_x = vxmin < TITLEBAR_XMAX and vxmax > TITLEBAR_XMIN
        overlap_y = vymin < TITLEBAR_YMAX and vymax > TITLEBAR_YMIN
        if overlap_x and overlap_y:
            ox = min(vxmax, TITLEBAR_XMAX) - max(vxmin, TITLEBAR_XMIN)
            oy = min(vymax, TITLEBAR_YMAX) - max(vymin, TITLEBAR_YMIN)
            collisions.append({
                "view": name,
                "view_outline": list(outline),
                "overlap_x_mm": round(ox * 1000, 2),
                "overlap_y_mm": round(oy * 1000, 2),
                "overlap_area_mm2": round(ox * oy * 1000000, 2),
            })
    return collisions


def check_out_of_frame(outlines):
    issues = []
    for name, outline in outlines.items():
        vxmin, vymin, vxmax, vymax = outline
        if vxmin < FRAME_XMIN or vymin < FRAME_YMIN or vxmax > FRAME_XMAX or vymax > FRAME_YMAX:
            issues.append({"view": name, "view_outline": list(outline)})
    return issues


def check_view_overlap(outlines):
    names = list(outlines.keys())
    overlaps = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1, n2 = names[i], names[j]
            o1, o2 = outlines[n1], outlines[n2]
            if o1[0] < o2[2] and o1[2] > o2[0] and o1[1] < o2[3] and o1[3] > o2[1]:
                ox = min(o1[2], o2[2]) - max(o1[0], o2[0])
                oy = min(o1[3], o2[3]) - max(o1[1], o2[1])
                overlaps.append({"view1": n1, "view2": n2, "overlap_area_mm2": round(ox * oy * 1000000, 2)})
    return overlaps


print("=== Layout Solver v2 分析 (040 实际 outline) ===")
print(f"TITLEBAR_BOX: {TITLEBAR_BOX} (180mm × 90mm)")
print(f"FRAME_BOX: {FRAME_BOX} (277mm × 190mm)")
print(f"T4 Centers: {T4_CENTERS}")
print()

results = []
total_tc = 0
total_of = 0
total_vo = 0

for base, outlines in sample_outlines.items():
    print(f"=== {base} ===")
    for name, outline in outlines.items():
        print(f"  {name}: {outline}")

    tc = check_titlebar_collision(outlines)
    of = check_out_of_frame(outlines)
    vo = check_view_overlap(outlines)

    total_tc += len(tc)
    total_of += len(of)
    total_vo += len(vo)

    print(f"  titlebar_collisions: {len(tc)}")
    for c in tc:
        print(f"    {c['view']}: overlap_x={c['overlap_x_mm']}mm overlap_y={c['overlap_y_mm']}mm area={c['overlap_area_mm2']}mm²")
    print(f"  out_of_frame: {len(of)}")
    print(f"  view_overlaps: {len(vo)}")

    results.append({
        "base": base,
        "outlines": outlines,
        "titlebar_collisions": tc,
        "out_of_frame": of,
        "view_overlaps": vo,
    })

print(f"\n=== 汇总 ===")
print(f"titlebar_collision_total: {total_tc}")
print(f"out_of_frame_total: {total_of}")
print(f"view_overlap_total: {total_vo}")

# 分析 titlebar collision 的严重性
if total_tc > 0:
    print(f"\n=== titlebar_collision 分析 ===")
    for r in results:
        for c in r["titlebar_collisions"]:
            if c["overlap_x_mm"] <= 2.0:
                print(f"  {r['base']}/{c['view']}: 边缘碰撞 (≤2mm), 非视觉性问题")
            else:
                print(f"  {r['base']}/{c['view']}: 显著碰撞 (>{c['overlap_x_mm']}mm), 需要调整")

# 保存
v22_dir = ROOT / "drw_output/v22_validation"
v22_dir.mkdir(parents=True, exist_ok=True)
out_file = v22_dir / "layout_solver_v2_analysis.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "titlebar_box": list(TITLEBAR_BOX),
        "frame_box": list(FRAME_BOX),
        "t4_centers": {k: list(v) for k, v in T4_CENTERS.items()},
        "sample_count": len(results),
        "titlebar_collision_total": total_tc,
        "out_of_frame_total": total_of,
        "view_overlap_total": total_vo,
        "results": results,
        "note": "titlebar_collision ≤2mm 为边缘碰撞, 非视觉性问题; layout_solver_v2 集成后可自动避免",
    }, f, ensure_ascii=False, indent=2)
print(f"\nSaved: {out_file}")
