"""v1.8 Task 1: 冻结 v1.7 baseline

生成:
  - validation_sets/core_12.json (核心 12 件清单)
  - drw_output/baselines/v1_7_baseline.json (每件样本的完整基线数据)
"""
import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VALIDATION_SETS_DIR = REPO_ROOT / "validation_sets"
BASELINES_DIR = REPO_ROOT / "drw_output" / "baselines"

# 核心 12 件清单
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


def write_core_12_json():
    """生成 validation_sets/core_12.json"""
    VALIDATION_SETS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "version": "v1.7",
        "description": "v1.7 核心验证集 12 件",
        "created_at": "2026-06-19",
        "items": [
            {
                "index": i + 1,
                "part_path": p,
                "base": Path(p).stem,
                "category": "lb26001" if "LB26001" in p else "small_part",
            }
            for i, p in enumerate(CORE_12)
        ],
    }
    out = VALIDATION_SETS_DIR / "core_12.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Task1] 写入 {out}")
    return out


def build_v1_7_baseline():
    """从 v1_7_core_validation.json 构建 baseline"""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    src = REPO_ROOT / "drw_output" / "v1_7_core_validation.json"
    if not src.exists():
        raise FileNotFoundError(f"v1.7 验证结果不存在: {src}")
    v17_data = json.loads(src.read_text(encoding="utf-8"))

    baseline = {
        "version": "v1.7",
        "frozen_at": "2026-06-19",
        "source": "drw_output/v1_7_core_validation.json",
        "summary": {
            "total": v17_data["total"],
            "success": v17_data["success"],
            "warning": v17_data["warning"],
            "failed": v17_data["failed"],
        },
        "items": [],
    }

    for item in v17_data["items"]:
        run_id = item.get("run_id")
        run_dir = REPO_ROOT / "drw_output" / "runs" / run_id if run_id else None

        # 收集产物路径
        qc_json_path = ""
        png_path = ""
        sidecar_used = item.get("has_valid_sidecar_annotation", False)

        if run_dir and run_dir.exists():
            # qc.json
            for qc_file in (run_dir / "qc").glob("*_qc.json"):
                qc_json_path = str(qc_file)
                break
            # png
            for png_file in (run_dir / "drawing").glob("*.PNG"):
                png_path = str(png_file)
                break
            for png_file in (run_dir / "drawing").glob("*.png"):
                png_path = str(png_file)
                break

        # 读取 qc.json 获取 vision_score
        vision_score = None
        if qc_json_path and Path(qc_json_path).exists():
            try:
                qc_data = json.loads(Path(qc_json_path).read_text(encoding="utf-8"))
                vision_score = qc_data.get("checks", {}).get("vision_score", {}).get("score")
            except Exception:
                pass

        baseline_item = {
            "base": item["base"],
            "part_path": item["part_path"],
            "run_id": run_id,
            "grade": item.get("dimension_grade", ""),
            "dim_total": item.get("dim_total", 0),
            "hard_fail": item.get("hard_fail", []),
            "warnings": item.get("warnings", []),
            "part_class": item.get("part_class", ""),
            "sidecar_used": sidecar_used,
            "standard_annotation_present": item.get("standard_annotation_present", False),
            "vision_score": vision_score,
            "drawing_usable_pass": item.get("drawing_usable_pass", False),
            "qc_pass_count": item.get("qc_pass_count", 0),
            "usable_for": item.get("usable_for", []),
            "qc_json": qc_json_path,
            "png_path": png_path,
            "status": item.get("status", ""),
        }
        baseline["items"].append(baseline_item)

    out = BASELINES_DIR / "v1_7_baseline.json"
    out.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Task1] 写入 {out}")
    print(f"[Task1] baseline 包含 {len(baseline['items'])} 件样本")
    return baseline


def verify_baseline(baseline):
    """验证 baseline 完整性"""
    print("\n[Task1] 验证 baseline 完整性:")
    required_fields = [
        "base", "grade", "dim_total", "hard_fail", "warnings",
        "part_class", "sidecar_used", "vision_score", "qc_json", "png_path",
    ]
    all_ok = True
    for item in baseline["items"]:
        missing = [f for f in required_fields if f not in item or (item[f] == "" and f in ("qc_json", "png_path"))]
        if missing:
            print(f"  WARN {item['base']}: 缺失字段 {missing}")
            # png_path 可能为空（如果文件未生成），但 qc_json 必须有
            if "qc_json" in missing:
                all_ok = False
        else:
            print(f"  OK   {item['base']}: grade={item['grade']} dim={item['dim_total']} png={'有' if item['png_path'] else '无'}")
    if all_ok:
        print("\n[Task1] baseline 完整性验证 PASS")
    else:
        print("\n[Task1] baseline 完整性验证 WARN (部分字段缺失)")
    return all_ok


def main():
    print("=" * 60)
    print("v1.8 Task 1: 冻结 v1.7 baseline")
    print("=" * 60)

    # 1. 生成 core_12.json
    write_core_12_json()

    # 2. 构建 v1_7_baseline.json
    baseline = build_v1_7_baseline()

    # 3. 验证
    verify_baseline(baseline)

    print("\n[Task1] 完成")


if __name__ == "__main__":
    main()
