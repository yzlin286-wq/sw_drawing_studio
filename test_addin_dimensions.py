"""v1.9 Task 3: Add-in 尺寸修复测试

对 002/003/007/009 调用 Add-in GenerateAssociativeDimensions
输出 dimension_addin_result.json
"""
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from app.services.sw_addin_client import generate_associative_dimensions

TEST_DIR = REPO_ROOT / "3D转2D测试图纸"
OUTPUT_DIR = REPO_ROOT / "drw_output" / "v1_9_addin_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 002/003/007/009
TARGETS = ["LB26001-A-04-002", "LB26001-A-04-003", "LB26001-A-04-007", "LB26001-A-04-009"]


def close_all_docs():
    """关闭 SW 中所有文档"""
    try:
        import win32com.client as wc
        sw = wc.GetActiveObject("SldWorks.Application")
        sw.CloseAllDocuments(True)
    except Exception:
        pass


def main():
    close_all_docs()
    time.sleep(2)

    results = {
        "version": "v1.9",
        "task": "Task 3 Add-in Dimension Repair",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "targets": [],
        "summary": {
            "total": len(TARGETS),
            "success": 0,
            "display_dim_improved": 0,
            "display_dim_positive": 0,
            "model_annotations_inserted": 0,
        },
    }

    for base in TARGETS:
        part_path = TEST_DIR / f"{base}.SLDPRT"
        drawing_path = TEST_DIR / f"{base}.SLDDRW"

        if not part_path.exists() or not drawing_path.exists():
            results["targets"].append({
                "base": base,
                "success": False,
                "reason": f"文件缺失: part={part_path.exists()}, drw={drawing_path.exists()}",
            })
            continue

        print(f"\n=== {base} ===")

        # 直接使用原文件（Add-in 不修改文件如果 InsertModelAnnotations 返回 0）
        result = generate_associative_dimensions(
            drawing_path=str(drawing_path),
            part_path=str(part_path),
            run_dir=OUTPUT_DIR,
            run_id=f"v1_9_{base}",
        )

        result["base"] = base
        result["part_path"] = str(part_path)
        result["drawing_path"] = str(drawing_path)

        print(f"  display_dim_count: {result.get('display_dim_count', 0)}")
        print(f"  dim_before: {result.get('dim_before', 0)} -> dim_after: {result.get('dim_after', 0)}")
        print(f"  model_annotations: {result.get('model_annotations_count', 0)}")
        print(f"  visible_entities: {result.get('visible_entities_count', 0)}")
        print(f"  success: {result.get('success')}, reason: {result.get('reason', '')}")

        results["targets"].append(result)

        if result.get("success"):
            results["summary"]["success"] += 1
        if result.get("dim_after", 0) > result.get("dim_before", 0):
            results["summary"]["display_dim_improved"] += 1
        if result.get("display_dim_count", 0) > 0:
            results["summary"]["display_dim_positive"] += 1
        results["summary"]["model_annotations_inserted"] += result.get("model_annotations_count", 0)

        # 关闭文档避免锁定
        close_all_docs()
        time.sleep(1)

    # 写入结果
    out_path = OUTPUT_DIR / "dimension_addin_result.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== Summary ===")
    print(json.dumps(results["summary"], ensure_ascii=False, indent=2))
    print(f"\nResult written to: {out_path}")


if __name__ == "__main__":
    main()
