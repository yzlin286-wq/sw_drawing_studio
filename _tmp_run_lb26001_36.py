"""v2.1 Task 8.5: 批量运行 LB26001_36 中不可交付的零件

对每个零件运行 drw_qc_loop_v6.py（完整 drawing 生成 + QC + 导出）
每个零件之间杀掉 SW 确保稳定性
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
V6_SCRIPT = REPO / ".trae" / "specs" / "build-v6-and-validate-exe-ui" / "drw_qc_loop_v6.py"


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


def run_part(part_path: str, timeout: int = 300) -> dict:
    """运行单个零件的 v6 pipeline"""
    result = {
        "part": Path(part_path).stem,
        "success": False,
        "reason": "",
        "duration": 0,
    }

    start_time = time.time()

    try:
        cmd = [sys.executable, "-X", "utf8", "-u", str(V6_SCRIPT), part_path]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO),
            encoding="utf-8",
            errors="replace",
        )
        result["duration"] = round(time.time() - start_time, 1)
        result["returncode"] = proc.returncode
        result["stdout_tail"] = proc.stdout[-500:] if proc.stdout else ""
        result["stderr_tail"] = proc.stderr[-500:] if proc.stderr else ""

        if proc.returncode == 0:
            result["success"] = True
        else:
            result["reason"] = f"returncode={proc.returncode}"

    except subprocess.TimeoutExpired:
        result["duration"] = round(time.time() - start_time, 1)
        result["reason"] = f"timeout ({timeout}s)"
    except Exception as e:
        result["duration"] = round(time.time() - start_time, 1)
        result["reason"] = str(e)

    return result


def main():
    # 1. 读取 LB26001_36 状态
    status_path = REPO / "drw_output" / "v2_1_lb26001_36_status.json"
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        not_deliverable = status.get("not_deliverable_list", [])
    else:
        print("Status file not found, scanning runs...")
        not_deliverable = []

    # 如果没有状态文件，扫描所有 LB26001 零件
    if not not_deliverable:
        test_dir = REPO / "3D转2D测试图纸"
        all_parts = sorted(test_dir.glob("LB26001-A-04-*.SLDPRT"))
        # 排除 001-009（已可交付）
        deliverable = {"LB26001-A-04-001", "LB26001-A-04-002", "LB26001-A-04-003",
                       "LB26001-A-04-004", "LB26001-A-04-005", "LB26001-A-04-006",
                       "LB26001-A-04-007", "LB26001-A-04-008", "LB26001-A-04-009"}
        not_deliverable = [p.stem for p in all_parts if p.stem not in deliverable]

    print(f"{'='*60}")
    print(f"LB26001_36 批量运行: {len(not_deliverable)} 件")
    print(f"{'='*60}")

    results = {}
    test_dir = REPO / "3D转2D测试图纸"

    for i, base in enumerate(not_deliverable, 1):
        part_path = test_dir / f"{base}.SLDPRT"
        print(f"\n[{i}/{len(not_deliverable)}] {base}")

        if not part_path.exists():
            print(f"  SKIP: {part_path} not found")
            results[base] = {"success": False, "reason": "part not found"}
            continue

        # 杀掉 SW
        kill_sw()

        # 运行 v6 pipeline
        print(f"  Running v6 pipeline...")
        r = run_part(str(part_path), timeout=300)
        results[base] = r
        print(f"  success={r['success']}, duration={r['duration']}s, reason={r.get('reason', '')}")

        # 杀掉 SW
        kill_sw()

        # 增量保存
        out_path = REPO / "drw_output" / "v2_1_lb26001_36_run_results.json"
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 汇总
    success_count = sum(1 for r in results.values() if r.get("success"))
    print(f"\n{'='*60}")
    print(f"=== LB26001_36 批量运行汇总 ===")
    print(f"{'='*60}")
    print(f"Total: {len(results)}")
    print(f"Success: {success_count}")
    print(f"Failed: {len(results) - success_count}")

    out_path = REPO / "drw_output" / "v2_1_lb26001_36_run_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入: {out_path}")


if __name__ == "__main__":
    main()
