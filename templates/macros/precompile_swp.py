"""尝试用 SOLIDWORKS COM 预编译 auto_section.bas → auto_section.swp

策略：
1) 检查 SW 是否在线
2) 调 sw.RunMacro2(.bas, "auto_section", "main", 1, 0) → SW 内部会编译并运行；
   编译产物 .swp 一般落到与 .bas 同目录
3) 若 SW 仍未生成 .swp，给出手动指引：用户需在 SW VBA IDE 打开 .bas，菜单 文件 → 导出/另存为 .swp
退出码：
  0 = .swp 已存在或 RunMacro2 触发后自动生成
  1 = SW 在线但未生成；给出手动指引
  2 = SW 不在线
"""
import sys, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BAS = ROOT / "templates" / "macros" / "auto_section.bas"
SWP = ROOT / "templates" / "macros" / "auto_section.swp"

def main():
    if not BAS.exists():
        print(f"[ERR] {BAS} not found"); return 2
    if SWP.exists() and SWP.stat().st_size > 1000:
        print(f"[ok] {SWP} already exists ({SWP.stat().st_size} bytes)"); return 0

    try:
        import win32com.client
    except Exception as e:
        print(f"[ERR] pywin32 unavailable: {e}"); return 2

    sw = None
    try:
        sw = win32com.client.GetActiveObject("SldWorks.Application")
    except Exception:
        print("[ERR] SolidWorks 进程未运行；请先启动 SW 后重试。")
        return 2

    print(f"[sw] connected, attempting RunMacro2 on {BAS}")
    try:
        ok = sw.RunMacro2(str(BAS), "auto_section", "main", 1, 0)
        print(f"[sw] RunMacro2 result={ok}")
        time.sleep(2.0)
    except Exception as e:
        print(f"[sw] RunMacro2 failed: {e}")

    if SWP.exists() and SWP.stat().st_size > 1000:
        print(f"[ok] generated {SWP} ({SWP.stat().st_size} bytes)")
        return 0

    print(f"[hint] {SWP} 未自动生成。手动一次性编译指引：")
    print("       1) 打开 SolidWorks → 工具 → 宏 → 编辑")
    print(f"       2) 选择 {BAS}")
    print(f"       3) 在 VBA IDE 内菜单 文件 → 另存为 → 选择 {SWP}（保存为 SOLIDWORKS Macro *.swp）")
    print("       完成后 v6 出图器即可优先调 .swp，不再走 .bas 兜底")
    return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
