"""v2.2: 创建 medium_30 验证集

从 129 个零件中选择 30 个非 LB26001、非 core_12 的零件
"""
import json
from pathlib import Path

ROOT = Path(r"c:\Users\Vision\Desktop\SW 相关")
parts_dir = ROOT / "3D转2D测试图纸"

# 读取 core_12 零件列表
with open(ROOT / "validation_sets/core_12.json", "r", encoding="utf-8") as f:
    core12 = json.load(f)
core12_bases = {item["base"] for item in core12["items"]}

# 获取所有 SLDPRT
all_parts = [p for p in parts_dir.glob("*.SLDPRT") if not p.name.startswith("~")]

# 排除 LB26001 和 core_12
medium_parts = []
for p in sorted(all_parts):
    base = p.stem
    if base.startswith("LB26001-A-04-"):
        continue
    if base in core12_bases:
        continue
    medium_parts.append(base)

print(f"Total non-LB26001, non-core_12 parts: {len(medium_parts)}")

# 选择前 30 个作为 medium_30
medium_30 = medium_parts[:30]
print(f"Selected medium_30: {len(medium_30)}")

# 保存
medium_30_data = {
    "version": "v2.2",
    "description": "v2.2 medium_30 验证集 30 件",
    "created_at": "2026-06-20",
    "items": [
        {
            "index": i + 1,
            "part_path": f"3D转2D测试图纸/{base}.SLDPRT",
            "base": base,
            "category": "medium",
        }
        for i, base in enumerate(medium_30)
    ],
}

out_file = ROOT / "validation_sets/medium_30.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(medium_30_data, f, ensure_ascii=False, indent=2)
print(f"Saved: {out_file}")

for item in medium_30_data["items"]:
    print(f"  {item['index']:2d}. {item['base']}")
