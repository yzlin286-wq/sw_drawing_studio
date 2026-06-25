"""v2.1 隔离运行 002/003/007/009 - 每个目标在独立子进程中运行

每个子进程:
  1. 运行 Add-in generate_dimensions_v3
  2. 杀掉 SW
  3. 运行 Sidecar sheet_sketch_dimension
  4. 杀掉 SW
  5. 保存结果

主进程:
  - 每个目标之间杀掉 SW
  - 收集所有结果
  - 保存到 v2_1_002_003_007_009_result.json
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent


def kill_sw():
    """杀掉所有 SW 进程"""
    for proc_name in ["SLDWORKS.exe", "SLDEXITAPP.exe"]:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc_name, "/T"],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass
    time.sleep(3)


def run_target(target_id):
    """在子进程中运行单个目标"""
    print(f"\n{'='*60}")
    print(f"Running target {target_id}")
    print(f"{'='*60}")

    # 杀掉 SW
    print(f"  [pre] killing SW...")
    kill_sw()

    # 运行单目标脚本
    script = REPO / "_tmp_run_v21_single.py"
    result_file = REPO / "drw_output" / f"v2_1_{target_id}_result.json"

    try:
        proc = subprocess.run(
            [sys.executable, str(script), target_id],
            capture_output=True,
            text=True,
            timeout=600,  # 10 分钟超时
            cwd=str(REPO),
            encoding="utf-8",
            errors="replace",
        )
        # 打印子进程输出
        if proc.stdout:
            for line in proc.stdout.splitlines():
                print(f"  {line}")
        if proc.stderr:
            print(f"  [stderr] {proc.stderr[-1500:]}")
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT! Killing SW...")
        kill_sw()
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        kill_sw()
        return None

    # 读取结果
    if result_file.exists():
        try:
            result = json.loads(result_file.read_text(encoding="utf-8"))
            print(f"  => addin_created_dim_count: {result.get('addin_created_dim_count', 0)}")
            return result
        except Exception as e:
            print(f"  Result parse error: {e}")
            return None
    else:
        print(f"  Result file not found: {result_file}")
        return None


def main():
    targets = ["002", "003", "007", "009"]
    results = {}

    print("=" * 60)
    print("v2.1 隔离运行 002/003/007/009")
    print("=" * 60)

    for target_id in targets:
        result = run_target(target_id)
        if result:
            results[target_id] = result
        else:
            results[target_id] = {
                "target": target_id,
                "success": False,
                "addin_created_dim_count": 0,
                "existing_display_dim_count": 0,
                "reason": "子进程运行失败或超时",
            }

    # 汇总
    print(f"\n{'='*60}")
    print("=== 002/003/007/009 v2.1 汇总 ===")
    print(f"{'='*60}")
    display_dim_positive = 0
    addin_created_positive = 0
    for tid in targets:
        r = results.get(tid, {})
        ddc = r.get("existing_display_dim_count", 0)
        adc = r.get("addin_created_dim_count", 0)
        if ddc > 0:
            display_dim_positive += 1
        if adc > 0:
            addin_created_positive += 1
        print(f"  {tid}: display_dim={ddc}, addin_created={adc}, "
              f"addin_only={r.get('addin_only_dim_count', 0)}, "
              f"sidecar_only={r.get('sidecar_only_dim_count', 0)}")

    print(f"\n  display_dim_positive: {display_dim_positive}/4")
    print(f"  addin_created_dim_positive: {addin_created_positive}/4")

    # 保存
    out_path = REPO / "drw_output" / "v2_1_002_003_007_009_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入: {out_path}")

    return results


if __name__ == "__main__":
    main()
