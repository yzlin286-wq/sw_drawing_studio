"""检查 LB26001_36 验证状态：36 件 LB26001 零件的可交付情况"""
import json
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parent

# 1. 获取所有 36 件 LB26001 零件
test_dir = REPO / "3D转2D测试图纸"
all_parts = sorted(test_dir.glob("LB26001-A-04-*.SLDPRT"))
print(f"Total LB26001 parts: {len(all_parts)}")

# 2. 扫描所有 runs，找出每个零件的可交付状态
runs_dir = REPO / "drw_output" / "runs"
part_status = {}  # base -> {deliverable: bool, run_dir: str, run_id: str}

if runs_dir.exists():
    runs = sorted(runs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for r in runs:
        manifest = r / "manifest.json"
        if manifest.exists():
            try:
                m = json.loads(manifest.read_text(encoding="utf-8"))
                input_part = m.get("input_part_path_abs", "") or m.get("input_part", "")
                base = Path(input_part).stem if input_part else ""

                # 只关心 LB26001 零件
                if not base.startswith("LB26001-A-04-"):
                    continue

                usable = m.get("drawing_usable", {})
                is_deliverable = usable.get("pass", False)

                # 只记录最新的 run（runs 已按时间倒序）
                if base not in part_status:
                    part_status[base] = {
                        "deliverable": is_deliverable,
                        "run_dir": str(r),
                        "run_id": r.name,
                        "grade": m.get("dimension_grade", ""),
                        "part_class": m.get("part_class", ""),
                    }
            except Exception:
                pass

# 3. 统计
deliverable_count = 0
not_deliverable = []
missing = []

for part_path in all_parts:
    base = part_path.stem
    if base in part_status:
        if part_status[base]["deliverable"]:
            deliverable_count += 1
        else:
            not_deliverable.append(base)
    else:
        missing.append(base)

print(f"\n=== LB26001_36 验证状态 ===")
print(f"Total parts: {len(all_parts)}")
print(f"Deliverable: {deliverable_count}")
print(f"Not deliverable: {len(not_deliverable)}")
print(f"Missing (no run): {len(missing)}")
print(f"Deliverable rate: {deliverable_count}/{len(all_parts)} = {deliverable_count*100//len(all_parts)}%")

if not_deliverable:
    print(f"\nNot deliverable parts:")
    for b in not_deliverable:
        s = part_status.get(b, {})
        print(f"  {b}: grade={s.get('grade','')}, class={s.get('part_class','')}")

if missing:
    print(f"\nMissing parts (no run found):")
    for b in missing:
        print(f"  {b}")

# 4. 保存结果
result = {
    "total_parts": len(all_parts),
    "deliverable": deliverable_count,
    "not_deliverable": len(not_deliverable),
    "missing": len(missing),
    "deliverable_rate": f"{deliverable_count}/{len(all_parts)}",
    "not_deliverable_list": not_deliverable,
    "missing_list": missing,
    "part_status": part_status,
}

out_path = REPO / "drw_output" / "v2_1_lb26001_36_status.json"
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nResult saved: {out_path}")
