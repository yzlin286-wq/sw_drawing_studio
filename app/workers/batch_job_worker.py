"""v2.3 Task 1: 批量作业 Worker

在独立子进程中执行批量出图任务（遍历多个零件，逐个运行 v6 流水线）。
通过 stdout 输出 JSONL 事件，供主进程 JobRunner 解析。

CLI:
    python batch_job_worker.py --job-id <id> --parts-json '<json>'
                               --output-dir <dir> --max-rounds <n>

parts_json 格式: ["path/to/part1.SLDPRT", "path/to/part2.SLDPRT", ...]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from app.services.resource_paths import (
    child_process_env,
    pipeline_command,
    pipeline_script_path,
    runtime_path,
)
from app.services.solidworks_global_lock import acquire_lock, heartbeat as lock_heartbeat, release_lock

# 确保 stdout 行缓冲（事件实时传递）
sys.stdout.reconfigure(line_buffering=True)

RUNTIME_ROOT = runtime_path(".")


def _emit(event_type: str, job_id: str, data: dict | None = None, message: str = "") -> None:
    """向 stdout 输出一条 JSONL 事件"""
    event = {
        "event_type": event_type,
        "job_id": job_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "data": data or {},
        "message": message,
    }
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _heartbeat_loop(
    job_id: str,
    stop_event: threading.Event,
    interval: float = 10.0,
    *,
    solidworks_lock: bool = False,
) -> None:
    """后台心跳线程：每 interval 秒发送一次心跳事件"""
    while not stop_event.is_set():
        if solidworks_lock:
            try:
                lock_heartbeat(job_id)
            except Exception:
                pass
        _emit("heartbeat", job_id, data={"ts": time.time()}, message="worker alive")
        stop_event.wait(interval)


def _run_single_part(
    job_id: str,
    part_path: str,
    output_dir: str,
    max_rounds: int,
    timeout_s: float,
    part_index: int,
    total_parts: int,
) -> dict:
    """执行单个零件的出图流程

    Returns:
        包含 ok/error/returncode 的结果字典
    """
    base = Path(part_path).stem
    result: dict = {"ok": False, "part": part_path, "error": "", "returncode": -1}

    # 定位 QC 循环脚本
    v6_script = pipeline_script_path("drw_qc_loop_v6")
    v5_script = pipeline_script_path("drw_qc_loop_v5")
    use_v5 = os.environ.get("USE_V5", "") == "1"
    if v6_script.exists() and not use_v5:
        qc_script_key = "drw_qc_loop_v6"
    elif v5_script.exists():
        qc_script_key = "drw_qc_loop_v5"
    else:
        result["error"] = "QC 循环脚本不存在（v6/v5 均未找到）"
        return result

    env = child_process_env()
    env["V6_SUBPROC_TIMEOUT"] = str(int(timeout_s))
    env["QC_LOOP_MAX_ROUNDS"] = str(max_rounds)
    env["JOB_ID"] = job_id
    env["SW_DRAWING_STUDIO_LOCK_JOB_ID"] = job_id
    if output_dir:
        env["RUN_DIR"] = output_dir

    cmd = pipeline_command(qc_script_key, [part_path])

    _emit("progress", job_id,
          data={
              "progress": round(part_index / total_parts, 3),
              "stage": f"批量 {part_index}/{total_parts}: {base}",
              "current_part": part_path,
          },
          message=f"正在处理: {base} ({part_index}/{total_parts})")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(RUNTIME_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
        assert proc.stdout is not None
        line_count = 0
        for line in proc.stdout:
            line = line.rstrip("\r\n")
            if line:
                line_count += 1
                # 转发子进程日志
                _emit("warning", job_id,
                      data={"source": "subprocess", "part": base, "line": line},
                      message=f"[{base}] {line}")

        proc.wait(timeout=timeout_s)
        result["returncode"] = proc.returncode
        result["ok"] = (proc.returncode == 0)
        if proc.returncode != 0:
            result["error"] = f"子进程退出码: {proc.returncode}"

    except subprocess.TimeoutExpired:
        result["error"] = f"子进程超时 ({timeout_s}s)"
    except Exception as exc:
        result["error"] = str(exc)

    # 检查输出文件
    drw_path = runtime_path("drw_output") / "v5" / f"{base}_v5.SLDDRW"
    if drw_path.exists():
        result["slddrw"] = str(drw_path)
        result["ok"] = True

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch Job Worker")
    parser.add_argument("--job-id", required=True, help="作业 ID")
    parser.add_argument("--parts-json", required=True,
                        help="零件路径列表 JSON 字符串或文件路径")
    parser.add_argument("--output-dir", default="", help="输出目录")
    parser.add_argument("--max-rounds", type=int, default=3, help="最大 QC 迭代轮数")
    parser.add_argument("--timeout-s", type=float, default=600, help="单件超时时间（秒）")
    args = parser.parse_args()

    job_id: str = args.job_id
    output_dir: str = args.output_dir or str(runtime_path("drw_output"))
    max_rounds: int = args.max_rounds
    timeout_s: float = args.timeout_s

    # ── 解析零件列表 ───────────────────────────────────────
    parts_json_str: str = args.parts_json
    parts: list[str] = []
    # 支持直接 JSON 字符串或文件路径
    if Path(parts_json_str).exists():
        try:
            parts = json.loads(Path(parts_json_str).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _emit("job_failed", job_id,
                  data={"error": f"读取零件列表失败: {exc}"},
                  message=f"读取零件列表失败: {exc}")
            return 1
    else:
        try:
            parts = json.loads(parts_json_str)
        except json.JSONDecodeError as exc:
            _emit("job_failed", job_id,
                  data={"error": f"解析 parts-json 失败: {exc}"},
                  message=f"解析 parts-json 失败: {exc}")
            return 1

    if not parts:
        _emit("job_failed", job_id,
              data={"error": "零件列表为空"},
              message="零件列表为空")
        return 1

    total_parts = len(parts)

    # ── 发布 job_started ──────────────────────────────────
    _emit("job_started", job_id,
          data={
              "job_type": "batch",
              "total_parts": total_parts,
              "parts": parts,
              "output_dir": output_dir,
              "max_rounds": max_rounds,
          },
          message=f"批量作业启动: {total_parts} 个零件")

    lock_timeout_s = float(os.environ.get("SW_GLOBAL_LOCK_TIMEOUT_S", "30") or "30")
    solidworks_lock = acquire_lock(
        owner_project=os.environ.get("SW_DRAWING_STUDIO_OWNER_PROJECT", "sw_drawing_studio"),
        owner_workspace=str(runtime_path(".")),
        job_id=job_id,
        operation="batch_job_worker.generate_drawings",
        part_path=f"{total_parts} parts",
        timeout_sec=lock_timeout_s,
        run_id=os.environ.get("RUN_ID", ""),
        allow_restart_sw=os.environ.get("SWDS_ALLOW_RESTART_SW", "0") == "1",
    )
    if not solidworks_lock.get("acquired"):
        _emit(
            "job_failed",
            job_id,
            data={
                "error": "blocked_by_solidworks_lock",
                "status": "blocked_by_solidworks_lock",
                "failure_bucket": "solidworks_lock_conflict",
                "owner": solidworks_lock.get("owner", {}),
                "reason": solidworks_lock.get("reason", ""),
                "fix_suggestion": solidworks_lock.get("fix_suggestion", ""),
                "recoverable": True,
            },
            message="SolidWorks 正被另一个任务使用",
        )
        return 4

    # ── 启动心跳线程 ──────────────────────────────────────
    stop_hb = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(job_id, stop_hb, 10.0),
        kwargs={"solidworks_lock": True},
        daemon=True,
    )
    hb_thread.start()

    # ── 逐个执行零件 ──────────────────────────────────────
    results: list[dict] = []
    ok_count = 0
    fail_count = 0

    for idx, part_path in enumerate(parts, 1):
        _emit("progress", job_id,
              data={
                  "progress": round((idx - 1) / total_parts, 3),
                  "stage": f"批量 {idx}/{total_parts}: {Path(part_path).stem}",
              },
              message=f"开始处理 {idx}/{total_parts}: {Path(part_path).name}")

        part_result = _run_single_part(
            job_id=job_id,
            part_path=part_path,
            output_dir=output_dir,
            max_rounds=max_rounds,
            timeout_s=timeout_s,
            part_index=idx,
            total_parts=total_parts,
        )
        results.append(part_result)
        if part_result.get("ok"):
            ok_count += 1
        else:
            fail_count += 1

    # ── 汇总结果 ───────────────────────────────────────────
    stop_hb.set()

    summary = {
        "total": total_parts,
        "ok": ok_count,
        "failed": fail_count,
        "results": results,
    }

    if fail_count == 0:
        release_lock(job_id, "batch_job_worker_finished")
        _emit("job_finished", job_id,
              data={"result": summary},
              message=f"批量作业完成: {ok_count}/{total_parts} 成功")
        return 0
    elif ok_count > 0:
        release_lock(job_id, "batch_job_worker_finished_partial")
        _emit("job_finished", job_id,
              data={"result": summary},
              message=f"批量作业完成（部分失败）: {ok_count}/{total_parts} 成功, {fail_count} 失败")
        return 0
    else:
        release_lock(job_id, "batch_job_worker_failed")
        _emit("job_failed", job_id,
              data={"error": f"全部 {total_parts} 个零件均失败", "result": summary},
              message=f"批量作业全部失败: {total_parts} 个零件")
        return 1


if __name__ == "__main__":
    sys.exit(main())
