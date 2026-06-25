"""v1.9 Task 7: EXE smoke 测试

验证 EXE 能启动并响应，并验证 v1.9 新模块（Add-in / DocMgr / PMI）能被导入。
"""
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
EXE_PATH = REPO_ROOT / "dist" / "sw_drawing_studio.exe"


def check_v1_9_modules():
    """验证 v1.9 新模块可被导入（源码层面）"""
    print("\n--- v1.9 模块导入检查 ---")
    modules = [
        "app.services.sw_addin_client",
        "app.services.sw_docmgr_relink",
        "app.services.pmi_probe_service",
    ]
    import importlib

    all_ok = True
    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
            print(f"  PASS: {mod_name}")
        except Exception as e:
            print(f"  FAIL: {mod_name} -> {e}")
            all_ok = False
    return all_ok


def check_exe_alive():
    """启动 EXE 并验证 5 秒后仍存活"""
    print("\n--- EXE 启动 smoke ---")
    if not EXE_PATH.exists():
        print(f"FAIL: EXE 不存在: {EXE_PATH}")
        return False

    print(f"EXE 路径: {EXE_PATH}")
    print(f"EXE 大小: {EXE_PATH.stat().st_size / 1024 / 1024:.1f} MB")

    print("启动 EXE...")
    try:
        proc = subprocess.Popen(
            [str(EXE_PATH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        print(f"EXE PID: {proc.pid}")

        time.sleep(5)

        if proc.poll() is None:
            print("PASS: EXE 启动后 5 秒仍存活 (alive=True)")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            print("EXE 已终止")
            return True
        else:
            rc = proc.returncode
            print(f"FAIL: EXE 启动后 5 秒已退出 (returncode={rc})")
            stdout, stderr = proc.communicate()
            print(f"stdout: {stdout[:500]}")
            print(f"stderr: {stderr[:500]}")
            return False
    except Exception as e:
        print(f"FAIL: 启动异常: {e}")
        return False


def main():
    print("=" * 60)
    print("v1.9 Task 7: EXE smoke 测试")
    print("=" * 60)

    mod_ok = check_v1_9_modules()
    exe_ok = check_exe_alive()

    print("\n=== v1.9 Smoke 测试结果 ===")
    print(f"v1.9 模块导入: {'PASS' if mod_ok else 'FAIL'}")
    print(f"EXE 启动存活:  {'PASS' if exe_ok else 'FAIL'}")

    if mod_ok and exe_ok:
        print("\nPASS: v1.9 EXE smoke 通过")
        sys.exit(0)
    else:
        print("\nFAIL: v1.9 EXE smoke 未通过")
        sys.exit(1)


if __name__ == "__main__":
    main()
