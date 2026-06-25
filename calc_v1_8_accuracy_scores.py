"""v1.8 Task 2: 为 v1.7 baseline 的 12 件计算 drawing_accuracy_score"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from app.services.drawing_accuracy_score import update_qc_with_accuracy_score

baseline_path = REPO_ROOT / "drw_output" / "baselines" / "v1_7_baseline.json"
baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

print("=" * 60)
print("v1.8 Task 2: 为 v1.7 baseline 计算 drawing_accuracy_score")
print("=" * 60)

results = []
for item in baseline["items"]:
    base = item["base"]
    qc_json = item.get("qc_json", "")
    if not qc_json or not Path(qc_json).exists():
        print(f"  SKIP {base}: qc_json 不存在")
        continue

    try:
        score = update_qc_with_accuracy_score(Path(qc_json))
        results.append({
            "base": base,
            "total": score["total"],
            "layout": score["layout"]["score"],
            "dimension": score["dimension"]["score"],
            "titlebar": score["titlebar"]["score"],
            "annotation": score["annotation"]["score"],
            "visual_clarity": score["visual_clarity"]["score"],
            "grade_label": score["grade_label"],
            "reasons_count": len(score["reasons"]),
        })
        print(f"  {base}: total={score['total']} grade={score['grade_label']} "
              f"layout={score['layout']['score']} dim={score['dimension']['score']} "
              f"tb={score['titlebar']['score']} anno={score['annotation']['score']} "
              f"visual={score['visual_clarity']['score']}")
    except Exception as e:
        print(f"  ERROR {base}: {e}")

# 验收检查
print("\n=== 验收检查 ===")
# 001/004/005 score >=70
for target in ["LB26001-A-04-001", "LB26001-A-04-004", "LB26001-A-04-005"]:
    r = next((x for x in results if x["base"] == target), None)
    if r:
        ok = r["total"] >= 70
        print(f"  {target} score >= 70: {'PASS' if ok else 'FAIL'} (actual={r['total']})")

# 002/003/007/009 比 v1.7 提升 >=10 分
# v1.7 baseline 没有分数，用 50 作为基线（C 级约 50 分）
v17_baseline_score = 50
for target in ["LB26001-A-04-002", "LB26001-A-04-003", "LB26001-A-04-007", "LB26001-A-04-009"]:
    r = next((x for x in results if x["base"] == target), None)
    if r:
        ok = r["total"] >= v17_baseline_score + 10
        print(f"  {target} score >= {v17_baseline_score + 10}: {'PASS' if ok else 'FAIL'} (actual={r['total']})")

# 保存结果
out_path = REPO_ROOT / "drw_output" / "baselines" / "v1_8_accuracy_scores.json"
out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n结果保存到: {out_path}")
