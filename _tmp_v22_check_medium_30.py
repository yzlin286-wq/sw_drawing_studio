"""v2.2 Task 7.4: 检查 medium_30 验证集

检查 30 个零件的现有输出文件状态
"""
import json
import os
from pathlib import Path

ROOT = Path(r"c:\Users\Vision\Desktop\SW 相关")
v5_dir = ROOT / "drw_output/v5"
runs_dir = ROOT / "drw_output/runs"

with open(ROOT / "validation_sets/medium_30.json", "r", encoding="utf-8") as f:
    medium30 = json.load(f)

results = []
deliverable_count = 0
png_missing = 0
view_overlap_total = 0
view_out_of_frame_total = 0

for item in medium30["items"]:
    base = item["base"]
    v5_slddrw = v5_dir / f"{base}_v5.SLDDRW"
    v5_pdf = v5_dir / f"{base}_v5.PDF"
    v5_dxf = v5_dir / f"{base}_v5.DXF"
    v5_png = v5_dir / f"{base}_v5.PNG"
    v5_qc = v5_dir / f"{base}_v5_qc.json"

    # 检查 runs 目录
    runs_files = {}
    if runs_dir.exists():
        for run_id_dir in runs_dir.iterdir():
            if run_id_dir.is_dir():
                for ext in ["SLDDRW", "PDF", "DXF", "PNG"]:
                    p = run_id_dir / "drawing" / f"{base}_v5.{ext}"
                    if p.exists():
                        runs_files[ext] = p
                qc_p = run_id_dir / "qc" / f"{base}_v5_qc.json"
                if qc_p.exists():
                    runs_files["qc"] = qc_p
                if runs_files:
                    break

    slddrw_ok = v5_slddrw.exists() or "SLDDRW" in runs_files
    pdf_ok = v5_pdf.exists() or "PDF" in runs_files
    dxf_ok = v5_dxf.exists() or "DXF" in runs_files
    png_ok = v5_png.exists() or "PNG" in runs_files

    # 读取 QC 数据
    qc_data = None
    qc_path = None
    if v5_qc.exists():
        qc_path = v5_qc
    elif "qc" in runs_files:
        qc_path = runs_files["qc"]

    if qc_path:
        try:
            with open(qc_path, "r", encoding="utf-8") as f:
                qc_data = json.load(f)
        except Exception:
            pass

    view_overlap = 0
    view_out_of_frame = 0
    qc_pass = False
    qc_score = 0

    if qc_data:
        qc_pass = bool(qc_data.get("pass"))
        qc_score = qc_data.get("score_pass_count", 0)
        checks = qc_data.get("checks", {})
        vo = checks.get("view_overlap", {})
        if isinstance(vo, dict):
            view_overlap = vo.get("count", 0) if not vo.get("pass", True) else 0
        vif = checks.get("view_in_frame", {})
        if isinstance(vif, dict):
            view_out_of_frame = vif.get("count", 0) if not vif.get("pass", True) else 0

    core_ok = all([slddrw_ok, pdf_ok, dxf_ok, png_ok])
    deliverable = core_ok

    if not png_ok:
        png_missing += 1
    view_overlap_total += view_overlap
    view_out_of_frame_total += view_out_of_frame
    if deliverable:
        deliverable_count += 1

    results.append({
        "base": base,
        "deliverable": deliverable,
        "slddrw": slddrw_ok,
        "pdf": pdf_ok,
        "dxf": dxf_ok,
        "png": png_ok,
        "qc_pass": qc_pass,
        "qc_score": qc_score,
        "view_overlap": view_overlap,
        "view_out_of_frame": view_out_of_frame,
    })

total = len(results)
rate = deliverable_count / total * 100 if total > 0 else 0

print(f"=== medium_30 验证汇总 ===")
print(f"总数: {total}")
print(f"可交付: {deliverable_count}/{total} ({rate:.1f}%)")
print(f"png_missing: {png_missing}")
print(f"view_overlap_total: {view_overlap_total}")
print(f"view_out_of_frame_total: {view_out_of_frame_total}")
print()

# 不可交付列表
not_deliverable = [r for r in results if not r["deliverable"]]
if not_deliverable:
    print(f"不可交付 ({len(not_deliverable)}):")
    for r in not_deliverable:
        missing = []
        if not r["slddrw"]: missing.append("slddrw")
        if not r["pdf"]: missing.append("pdf")
        if not r["dxf"]: missing.append("dxf")
        if not r["png"]: missing.append("png")
        print(f"  {r['base']}: missing={missing}")

# 保存结果
v22_dir = ROOT / "drw_output/v22_validation"
out_file = v22_dir / "medium_30_status.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump({
        "total": total,
        "deliverable": deliverable_count,
        "rate": round(rate, 1),
        "png_missing": png_missing,
        "view_overlap_total": view_overlap_total,
        "view_out_of_frame_total": view_out_of_frame_total,
        "results": results,
    }, f, ensure_ascii=False, indent=2)
print(f"\nSaved: {out_file}")
