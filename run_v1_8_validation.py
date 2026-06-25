"""v1.8 Task 7: 分阶段验证

阶段 1: core_12 (12 件) - 必须 12/12 不退化
阶段 2: LB26001 36 件 - 目标 PASS/WARNING >=90%
阶段 3: medium_30 - 目标 D 级 <=10%
阶段 4: 129 件全量（视情况）
"""
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from app.services.run_manager import full_pipeline

# 阶段 1: core_12
CORE_12 = [
    "3D转2D测试图纸/LB26001-A-04-001.SLDPRT",
    "3D转2D测试图纸/LB26001-A-04-002.SLDPRT",
    "3D转2D测试图纸/LB26001-A-04-003.SLDPRT",
    "3D转2D测试图纸/LB26001-A-04-004.SLDPRT",
    "3D转2D测试图纸/LB26001-A-04-005.SLDPRT",
    "3D转2D测试图纸/LB26001-A-04-007.SLDPRT",
    "3D转2D测试图纸/LB26001-A-04-009.SLDPRT",
    "3D转2D测试图纸/-M3x8十字螺丝-1-V3-V02.SLDPRT",
    "3D转2D测试图纸/-弹簧压棒弹簧-1-V3-V02.SLDPRT",
    "3D转2D测试图纸/-AK-15-AC-25-1-V3-V02.SLDPRT",
    "3D转2D测试图纸/-AK-15-AC-26-1-V3-V02.SLDPRT",
    "3D转2D测试图纸/-AK-15-AC-27-1-V3-V02.SLDPRT",
]


def run_stage(stage_name, parts, output_file, acceptance=None):
    """运行一个验证阶段"""
    print("=" * 60)
    print(f"阶段: {stage_name}")
    print(f"件数: {len(parts)}")
    print("=" * 60)

    results = {
        "stage": stage_name,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(parts),
        "items": [],
        "summary": {
            "pass": 0,
            "pass_with_warning": 0,
            "need_review": 0,
            "fail": 0,
            "grade_a": 0,
            "grade_b": 0,
            "grade_c": 0,
            "grade_d": 0,
        },
    }

    for i, part_path in enumerate(parts):
        base = Path(part_path).stem
        print(f"\n[{i+1}/{len(parts)}] {base}")

        item = {
            "base": base,
            "part_path": part_path,
            "run_id": None,
            "grade": "",
            "dim_total": 0,
            "hard_fail": [],
            "part_class": "",
            "final_status": "",
            "accuracy_score": 0,
            "drawing_usable_pass": False,
            "has_sidecar": False,
            "error": "",
        }

        try:
            ctx = full_pipeline(part_path, strategy="v6_recommended")
            item["run_id"] = ctx.run_id
            item["grade"] = ctx.dimension_grade
            item["dim_total"] = ctx.dim_total
            item["hard_fail"] = list(ctx.hard_fail or [])
            item["part_class"] = ctx.part_class
            item["final_status"] = ctx.final_quality.get("status", "") if ctx.final_quality else ""
            item["accuracy_score"] = ctx.drawing_accuracy_score.get("total", 0) if ctx.drawing_accuracy_score else 0
            item["drawing_usable_pass"] = bool(ctx.drawing_usable.get("pass") if isinstance(ctx.drawing_usable, dict) else False)
            item["has_sidecar"] = ctx.has_valid_sidecar_annotation

            # 汇总
            fs = item["final_status"]
            if fs == "pass":
                results["summary"]["pass"] += 1
            elif fs == "pass_with_warning":
                results["summary"]["pass_with_warning"] += 1
            elif fs == "need_review":
                results["summary"]["need_review"] += 1
            elif fs == "fail":
                results["summary"]["fail"] += 1

            g = item["grade"]
            if g == "A":
                results["summary"]["grade_a"] += 1
            elif g == "B":
                results["summary"]["grade_b"] += 1
            elif g == "C":
                results["summary"]["grade_c"] += 1
            elif g == "D":
                results["summary"]["grade_d"] += 1

            print(f"  -> grade={g} dim={ctx.dim_total} final={fs} usable={item['drawing_usable_pass']}")

        except Exception as e:
            item["error"] = str(e)
            results["summary"]["fail"] += 1
            print(f"  -> ERROR: {e}")

        results["items"].append(item)

        # 增量保存
        results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        output_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 验收检查
    if acceptance:
        print("\n=== 验收检查 ===")
        for check in acceptance:
            ok, msg = check(results)
            print(f"  {'PASS' if ok else 'FAIL'}: {msg}")

    return results


def main():
    output_dir = REPO_ROOT / "drw_output"
    output_dir.mkdir(exist_ok=True)

    # 阶段 1: core_12
    core_12_out = output_dir / "validation_report_v1_8_core_12.json"
    acceptance_core_12 = [
        lambda r: (r["summary"]["pass"] + r["summary"]["pass_with_warning"] == r["total"],
                   f"core_12 全部通过: {r['summary']['pass'] + r['summary']['pass_with_warning']}/{r['total']}"),
        lambda r: (not any(i["base"] == "LB26001-A-04-001" and i["hard_fail"] for i in r["items"]),
                   "001 不退化 (hard_fail=[])"),
        lambda r: (not any(i["base"] == "LB26001-A-04-004" and ("view_overlap" in i["hard_fail"] or "view_out_of_frame" in i["hard_fail"]) for i in r["items"]),
                   "004 无 view_overlap/out_of_frame"),
        lambda r: (sum(1 for i in r["items"] if i["base"] in ("LB26001-A-04-002", "LB26001-A-04-003", "LB26001-A-04-007", "LB26001-A-04-009") and i["grade"] == "B") >= 2,
                   "002/003/007/009 至少 2 件 C→B"),
        lambda r: (sum(1 for i in r["items"] if i["base"] in ("-M3x8十字螺丝-1-V3-V02", "-弹簧压棒弹簧-1-V3-V02", "-AK-15-AC-25-1-V3-V02", "-AK-15-AC-26-1-V3-V02", "-AK-15-AC-27-1-V3-V02") and i["grade"] == "C") >= 4,
                   "小零件 5 件 >=4 件 C 级"),
        lambda r: (not any("png_missing" in i["hard_fail"] for i in r["items"]),
                   "png_missing=0"),
    ]

    results = run_stage("core_12", CORE_12, core_12_out, acceptance_core_12)

    # 生成 markdown 报告
    md_out = output_dir / "validation_report_v1_8.md"
    with open(md_out, "w", encoding="utf-8") as f:
        f.write("# v1.8 验证报告\n\n")
        f.write(f"**阶段**: {results['stage']}\n")
        f.write(f"**开始**: {results['started_at']}\n")
        f.write(f"**完成**: {results['finished_at']}\n")
        f.write(f"**总计**: {results['total']}\n\n")

        f.write("## 汇总\n\n")
        s = results["summary"]
        f.write(f"- pass: {s['pass']}\n")
        f.write(f"- pass_with_warning: {s['pass_with_warning']}\n")
        f.write(f"- need_review: {s['need_review']}\n")
        f.write(f"- fail: {s['fail']}\n")
        f.write(f"- Grade A: {s['grade_a']}\n")
        f.write(f"- Grade B: {s['grade_b']}\n")
        f.write(f"- Grade C: {s['grade_c']}\n")
        f.write(f"- Grade D: {s['grade_d']}\n\n")

        f.write("## 明细\n\n")
        f.write("| # | 零件 | Grade | dim_total | final_status | hard_fail | part_class | accuracy |\n")
        f.write("|---|------|-------|-----------|--------------|-----------|------------|----------|\n")
        for i, item in enumerate(results["items"]):
            f.write(f"| {i+1} | {item['base']} | {item['grade']} | {item['dim_total']} | {item['final_status']} | {item['hard_fail']} | {item['part_class']} | {item['accuracy_score']} |\n")

    print(f"\n报告保存到: {md_out}")
    print(f"JSON 保存到: {core_12_out}")


if __name__ == "__main__":
    main()
