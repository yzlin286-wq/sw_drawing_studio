"""v2.0 Task 4: SwDocMgrProbe - Document Manager 探测工具

检测 SW_DM_LICENSE_KEY、COM Factory、DLL 路径
"""
import sys
import json
from pathlib import Path

# 添加项目根目录到 path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.services.docmgr_service import probe_docmgr, read_drawing_references


def main():
    print("=" * 60)
    print("v2.0 Task 4: SwDocMgrProbe - Document Manager 探测")
    print("=" * 60)

    print("\n--- 1. 探测 Document Manager ---")
    probe = probe_docmgr()
    print(json.dumps(probe, ensure_ascii=False, indent=2))

    if len(sys.argv) > 1:
        drawing_path = sys.argv[1]
        print(f"\n--- 2. 读取 drawing 引用: {drawing_path} ---")
        refs = read_drawing_references(drawing_path)
        print(json.dumps(refs, ensure_ascii=False, indent=2))

    print("\n--- 探测完成 ---")
    if probe["available"]:
        print("PASS: Document Manager 可用")
    else:
        print(f"WARNING: Document Manager 不可用 - {probe['reason']}")


if __name__ == "__main__":
    main()
