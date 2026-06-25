"""v1.7 Task 6: 核心验证集 12 件

运行 12 件核心验证集，收集结果用于 validation_log_v1_7.md
"""
import sys
import os
import json
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
os.environ['PYTHONPATH'] = str(REPO_ROOT)

from app.services.run_manager import full_pipeline

# 12 件核心验证集
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


def run_validation():
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    results = []
    total = len(CORE_12)
    success = 0
    warning = 0
    failed = 0

    for i, part_path in enumerate(CORE_12, 1):
        base = Path(part_path).stem
        print(f"\n{'='*60}")
        print(f"[{i}/{total}] {base}")
        print(f"{'='*60}")

        item = {
            "base": base,
            "part_path": part_path,
            "run_id": None,
            "hard_fail": [],
            "warnings": [],
            "dim_total": 0,
            "dimension_grade": "",
            "usable_for": [],
            "part_class": "",
            "standard_annotation_present": False,
            "has_valid_sidecar_annotation": False,
            "drawing_usable_pass": False,
            "qc_pass_count": 0,
            "fallback_used": False,
            "status": "failed",
            "error": "",
        }

        try:
            ctx = full_pipeline(part_path, strategy="v6_recommended")
            item["run_id"] = ctx.run_id
            item["hard_fail"] = list(ctx.hard_fail or [])
            item["warnings"] = list(ctx.warnings or [])
            item["dim_total"] = ctx.dim_total
            item["dimension_grade"] = ctx.dimension_grade
            item["usable_for"] = ctx.usable_for
            item["part_class"] = ctx.part_class
            item["standard_annotation_present"] = ctx.standard_annotation_present
            item["has_valid_sidecar_annotation"] = ctx.has_valid_sidecar_annotation
            item["qc_pass_count"] = ctx.qc_pass_count
            item["fallback_used"] = ctx.fallback_used
            if isinstance(ctx.drawing_usable, dict):
                item["drawing_usable_pass"] = bool(ctx.drawing_usable.get("pass"))

            if item["drawing_usable_pass"]:
                item["status"] = "success" if not item["warnings"] else "warning"
            elif item["dimension_grade"] in ("A", "B", "C"):
                item["status"] = "warning"
            else:
                item["status"] = "failed"

            # 读取 sidecar 结果
            sidecar_path = ctx.run_dir / "qc" / "dimension_sidecar_result.json"
            if sidecar_path.exists():
                try:
                    item["sidecar"] = json.loads(sidecar_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

        except Exception as e:
            item["status"] = "failed"
            item["error"] = f"{type(e).__name__}: {e}"

        if item["status"] == "success":
            success += 1
        elif item["status"] == "warning":
            warning += 1
        else:
            failed += 1

        results.append(item)
        print(f"  status={item['status']} grade={item['dimension_grade']} dim_total={item['dim_total']} part_class={item['part_class']}")

        # 增量写结果
        _write_results(results, started_at, success, warning, failed, total)

    finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
    summary = {
        "version": "v1.7",
        "started_at": started_at,
        "finished_at": finished_at,
        "total": total,
        "success": success,
        "warning": warning,
        "failed": failed,
        "items": results,
    }
    out_path = REPO_ROOT / "drw_output" / "v1_7_core_validation.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"Validation complete: {success}/{total} success, {warning}/{total} warning, {failed}/{total} failed")
    print(f"Results: {out_path}")
    return summary


def _write_results(results, started_at, success, warning, failed, total):
    """增量写结果"""
    summary = {
        "version": "v1.7",
        "started_at": started_at,
        "finished_at": "",
        "total": total,
        "success": success,
        "warning": warning,
        "failed": failed,
        "items": results,
    }
    out_path = REPO_ROOT / "drw_output" / "v1_7_core_validation.json"
    try:
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    run_validation()
