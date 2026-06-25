"""v2.0 Task 4: SwDocMgrRelink - Document Manager 引用修复工具

使用 Document Manager API 读取 SLDDRW external references 并尝试 ReplaceReference
"""
import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.services.docmgr_service import relink_drawing_references


def main():
    print("=" * 60)
    print("v2.0 Task 4: SwDocMgrRelink - Document Manager 引用修复")
    print("=" * 60)

    if len(sys.argv) < 3:
        print("Usage: python sw_docmgr_relink.py <drawing_path> <part_path>")
        sys.exit(1)

    drawing_path = sys.argv[1]
    part_path = sys.argv[2]

    print(f"\nDrawing: {drawing_path}")
    print(f"Part:    {part_path}")

    result = relink_drawing_references(drawing_path, part_path)
    print("\n--- 结果 ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["success"]:
        print("\nPASS: 引用修复成功")
    elif result["overall_status"] == "warning":
        print(f"\nWARNING: {result['reason']}")
    else:
        print(f"\nFAIL: {result['reason']}")


if __name__ == "__main__":
    main()
