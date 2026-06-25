"""v1.9 Task 7: 验证脚本 - 汇总所有 v1.9 结果"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent

# 1. v1.7 baseline
baseline_path = REPO / "drw_output" / "baselines" / "v1_7_baseline.json"
if baseline_path.exists():
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    print("=== v1.7 Baseline ===")
    print("Total:", baseline.get("summary", {}).get("total", "N/A"))
    print("Pass:", baseline.get("summary", {}).get("pass", "N/A"))
    print("Grade A:", baseline.get("summary", {}).get("grade_a", "N/A"))
    print("Grade B:", baseline.get("summary", {}).get("grade_b", "N/A"))
    print("Grade C:", baseline.get("summary", {}).get("grade_c", "N/A"))
    print("Grade D:", baseline.get("summary", {}).get("grade_d", "N/A"))
else:
    print("v1.7 baseline not found")

# 2. Add-in Dimension Results
dim_path = REPO / "drw_output" / "v1_9_addin_test" / "dimension_addin_result.json"
if dim_path.exists():
    dim_result = json.loads(dim_path.read_text(encoding="utf-8"))
    print("\n=== v1.9 Add-in Dimension Results ===")
    print(json.dumps(dim_result.get("summary", {}), ensure_ascii=False, indent=2))
    for t in dim_result.get("targets", []):
        base = t.get("base", "")
        ddc = t.get("display_dim_count", 0)
        success = t.get("success", False)
        print("  " + base + ": display_dim_count=" + str(ddc) + ", success=" + str(success))

# 3. PMI Probe
pmi_path = REPO / "drw_output" / "v1_9_pmi" / "pmi_probe.json"
if pmi_path.exists():
    pmi_result = json.loads(pmi_path.read_text(encoding="utf-8"))
    print("\n=== v1.9 PMI Probe ===")
    print(json.dumps(pmi_result.get("summary", {}), ensure_ascii=False, indent=2))

# 4. Add-in Probe
addin_path = REPO / "drw_output" / "addin_probe_result.json"
if addin_path.exists():
    addin_result = json.loads(addin_path.read_text(encoding="utf-8"))
    print("\n=== v1.9 Add-in Probe ===")
    print("  available:", addin_result.get("available"))
    print("  ping:", addin_result.get("ping_result"))
    print("  method:", addin_result.get("method"))

# 5. DocMgr Probe
docmgr_path = REPO / "drw_output" / "v1_9_docmgr" / "docmgr_relink_result.json"
if docmgr_path.exists():
    docmgr_result = json.loads(docmgr_path.read_text(encoding="utf-8"))
    print("\n=== v1.9 Document Manager Probe ===")
    print(json.dumps(docmgr_result.get("summary", {}), ensure_ascii=False, indent=2))

# 6. Check latest core_12 runs
runs_dir = REPO / "drw_output" / "runs"
if runs_dir.exists():
    print("\n=== Recent Runs ===")
    runs = sorted(runs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    for r in runs:
        manifest = r / "manifest.json"
        if manifest.exists():
            try:
                m = json.loads(manifest.read_text(encoding="utf-8"))
                base = Path(m.get("input_part_path_abs", "")).stem
                grade = m.get("dimension_grade", "")
                usable = m.get("drawing_usable", {})
                print("  " + r.name + ": " + base + " grade=" + grade + " usable=" + str(usable.get("pass", False)))
            except Exception:
                pass
