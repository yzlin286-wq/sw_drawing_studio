"""把 auto_section.bas 部署到 SOLIDWORKS 可调用的位置

策略：直接用 .bas/.swp 都不可靠时，最简单是把 .bas 复制成 .swp 名（SW2025 接受 .swp 路径但内容是 BAS 时无法编译）。
最实际的做法：用户手动在 SW IDE 里打开 .bas 后另存为 .swp。
本脚本仅做"探测：是否已有 .swp"——若无则给出提示让用户手动一次性编译。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BAS = ROOT / "templates" / "macros" / "auto_section.bas"
SWP = ROOT / "templates" / "macros" / "auto_section.swp"

def main():
    if not BAS.exists():
        print(f"[ERR] {BAS} missing")
        return 2
    if SWP.exists():
        print(f"[ok] {SWP} ready ({SWP.stat().st_size} bytes)")
        return 0
    print(f"[hint] .swp not found at {SWP}")
    print("       请打开 SolidWorks → 工具 → 宏 → 编辑 → 选择 auto_section.bas → 另存为 auto_section.swp")
    print(f"       或在 v5 流程中通过 RunMacro2 直接传 .bas 路径（部分 SW 版本可接受）")
    return 1

if __name__ == "__main__":
    sys.exit(main())
