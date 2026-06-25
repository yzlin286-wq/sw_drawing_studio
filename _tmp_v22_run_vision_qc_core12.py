"""v2.2 Task 7.2: 运行 Vision QC v4 on core_12

对 core_12 的 12 个 PDF 运行 vision_qc_v4，生成 vision_qc_v4.json
验收: core_12 12/12 有 bbox/source/confidence/fix_suggestion
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"c:\Users\Vision\Desktop\SW 相关")
sys.path.insert(0, str(ROOT))

from app.services.vision_qc_v4 import run_vision_qc_v4, _detect_mode, _check_dependencies

# 读取 core_12 PDF 路径
with open(ROOT / "_tmp_v22_core12_pdf.json", "r", encoding="utf-8") as f:
    core12_pdfs = json.load(f)

# 输出目录
v22_qc_dir = ROOT / "drw_output/v22_validation/vision_qc_v4"
v22_qc_dir.mkdir(parents=True, exist_ok=True)

print(f"=== Vision QC v4 on core_12 ===")
print(f"mode: {_detect_mode()}")
print(f"deps: {_check_dependencies()}")
print()

results = []
pass_count = 0
for i, item in enumerate(core12_pdfs, 1):
    base = item["base"]
    pdf_path = Path(item["pdf_path"])
    if not pdf_path.exists():
        print(f"[{i}/12] {base}: SKIP (PDF missing)")
        results.append({"base": base, "status": "skip", "reason": "PDF missing"})
        continue

    print(f"[{i}/12] {base}: running vision_qc_v4...")
    t0 = time.time()
    try:
        run_id = f"v22_core12_{base}"
        result = run_vision_qc_v4(
            pdf_path=pdf_path,
            png_path=None,
            qc_json_path=None,
            run_dir=v22_qc_dir,
            run_id=run_id,
        )
        dt = time.time() - t0

        # 检查验收条件: 有 bbox/source/confidence/fix_suggestion
        issues = result.get("issues", [])
        has_bbox = all("bbox" in iss for iss in issues) if issues else True
        has_source = all("source" in iss for iss in issues) if issues else True
        has_confidence = all("confidence" in iss for iss in issues) if issues else True
        has_fix = all("fix_suggestion" in iss for iss in issues) if issues else True

        # 每个issue都需要有这4个字段
        all_fields_ok = True
        for iss in issues:
            for field in ["bbox", "source", "confidence", "fix_suggestion"]:
                if field not in iss:
                    all_fields_ok = False
                    break
            if not all_fields_ok:
                break

        status = "PASS" if all_fields_ok else "FAIL"
        if status == "PASS":
            pass_count += 1

        print(f"  -> {status} ({dt:.1f}s) mode={result.get('mode')} issues={len(issues)} fallback={result.get('fallback_used')}")

        # 保存单个结果
        out_file = v22_qc_dir / f"{base}_vision_qc_v4.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        results.append({
            "base": base,
            "status": status,
            "mode": result.get("mode"),
            "issues_count": len(issues),
            "fallback_used": result.get("fallback_used"),
            "fallback_reasons": result.get("fallback_reasons", []),
            "all_fields_ok": all_fields_ok,
            "output_file": str(out_file),
            "elapsed_s": round(dt, 1),
        })
    except Exception as e:
        dt = time.time() - t0
        print(f"  -> ERROR ({dt:.1f}s): {e}")
        results.append({"base": base, "status": "error", "reason": str(e), "elapsed_s": round(dt, 1)})

print()
print(f"=== 汇总 ===")
print(f"PASS: {pass_count}/12")
print(f"FAIL: {len([r for r in results if r['status'] == 'FAIL'])}/12")
print(f"ERROR: {len([r for r in results if r['status'] == 'error'])}/12")
print(f"SKIP: {len([r for r in results if r['status'] == 'skip'])}/12")

# 保存汇总
summary = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "mode": _detect_mode(),
    "dependencies": _check_dependencies(),
    "total": 12,
    "pass": pass_count,
    "fail": len([r for r in results if r["status"] == "FAIL"]),
    "error": len([r for r in results if r["status"] == "error"]),
    "skip": len([r for r in results if r["status"] == "skip"]),
    "results": results,
}
summary_file = v22_qc_dir / "core_12_summary.json"
with open(summary_file, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f"Summary saved: {summary_file}")
