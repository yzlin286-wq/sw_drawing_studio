"""v1.8 Task 8: EXE smoke 测试

验证 EXE 能启动并响应
"""
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
EXE_PATH = REPO_ROOT / "dist" / "sw_drawing_studio.exe"

def main():
    print("=" * 60)
    print("v1.8 Task 8: EXE smoke 测试")
    print("=" * 60)

    if not EXE_PATH.exists():
        print(f"FAIL: EXE 不存在: {EXE_PATH}")
        print("请先运行: pyinstaller build_exe.spec")
        sys.exit(1)

    print(f"EXE 路径: {EXE_PATH}")
    print(f"EXE 大小: {EXE_PATH.stat().st_size / 1024 / 1024:.1f} MB")

    # 启动 EXE
    print("\n启动 EXE...")
    try:
        proc = subprocess.Popen(
            [str(EXE_PATH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        print(f"EXE PID: {proc.pid}")

        # 等待 5 秒
        time.sleep(5)

        # 检查进程是否存活
        if proc.poll() is None:
            print("PASS: EXE 启动后 5 秒仍存活 (alive=True)")
            # 终止
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            print("EXE 已终止")
        else:
            rc = proc.returncode
            print(f"FAIL: EXE 启动后 5 秒已退出 (returncode={rc})")
            stdout, stderr = proc.communicate()
            print(f"stdout: {stdout[:500]}")
            print(f"stderr: {stderr[:500]}")
            sys.exit(1)

    except Exception as e:
        print(f"FAIL: 启动异常: {e}")
        sys.exit(1)

    print("\n=== Smoke 测试结果 ===")
    print("PASS: EXE smoke alive=True")


if __name__ == "__main__":
    main()
