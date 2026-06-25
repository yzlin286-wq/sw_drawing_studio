"""v2.2 检查 core_12 PDF 文件位置"""
import os
import json
from pathlib import Path

ROOT = Path(r"c:\Users\Vision\Desktop\SW 相关")
with open(ROOT / "validation_sets/core_12.json", "r", encoding="utf-8") as f:
    core12 = json.load(f)

v5_dir = ROOT / "drw_output/v5"
runs_dir = ROOT / "drw_output/runs"

print("=== core_12 PDF 检查 ===")
found = 0
results = []
for item in core12["items"]:
    base = item["base"]
    v5_pdf = v5_dir / f"{base}_v5.PDF"
    runs_pdf = None
    if runs_dir.exists():
        for run_id_dir in runs_dir.iterdir():
            if run_id_dir.is_dir():
                p = run_id_dir / "drawing" / f"{base}_v5.PDF"
                if p.exists():
                    runs_pdf = p
                    break
    if v5_pdf.exists():
        status = "v5"
        pdf_path = str(v5_pdf)
    elif runs_pdf:
        status = "runs"
        pdf_path = str(runs_pdf)
    else:
        status = "MISSING"
        pdf_path = ""
    name = os.path.basename(pdf_path) if pdf_path else ""
    print(f"  {base}: {status} {name}")
    results.append({"base": base, "status": status, "pdf_path": pdf_path})
    if pdf_path:
        found += 1

print(f"Found: {found}/12")

# 保存结果
out = ROOT / "_tmp_v22_core12_pdf.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"Saved: {out}")
