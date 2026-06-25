"""v2.3 Task 1: Vision Audit 作业 Worker

在独立子进程中执行视觉审核（优先调用 vision_qc_v5，v4 fallback）。
通过 stdout 输出 JSONL 事件，供主进程 JobRunner 解析。

CLI:
    python vision_audit_worker.py --job-id <id> --pdf-path <path> --png-path <path>
                                  --run-dir <dir>
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from app.services.resource_paths import bundle_root

# 确保 stdout 行缓冲（事件实时传递）
sys.stdout.reconfigure(line_buffering=True)

REPO_ROOT = bundle_root()


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


def _heartbeat_loop(job_id: str, stop_event: threading.Event, interval: float = 10.0) -> None:
    """后台心跳线程：每 interval 秒发送一次心跳事件"""
    while not stop_event.is_set():
        _emit("heartbeat", job_id, data={"ts": time.time()}, message="worker alive")
        stop_event.wait(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Vision Audit Job Worker")
    parser.add_argument("--job-id", required=True, help="作业 ID")
    parser.add_argument("--pdf-path", required=True, help="PDF 文件路径")
    parser.add_argument("--png-path", default="", help="PNG 预览图路径（可选）")
    parser.add_argument("--run-dir", default="", help="运行目录")
    args = parser.parse_args()

    job_id: str = args.job_id
    pdf_path: str = args.pdf_path
    png_path: str = args.png_path
    run_dir: str = args.run_dir

    # ── 校验输入 ───────────────────────────────────────────
    if not Path(pdf_path).exists():
        _emit("job_failed", job_id,
              data={"error": f"PDF 文件不存在: {pdf_path}"},
              message=f"PDF 文件不存在: {pdf_path}")
        return 1

    # ── 发布 job_started ──────────────────────────────────
    _emit("job_started", job_id,
          data={
              "job_type": "vision_audit",
              "pdf_path": pdf_path,
              "png_path": png_path,
              "run_dir": run_dir,
          },
          message=f"视觉审核启动: {Path(pdf_path).name}")

    # ── 启动心跳线程 ──────────────────────────────────────
    stop_hb = threading.Event()
    hb_thread = threading.Thread(target=_heartbeat_loop, args=(job_id, stop_hb, 10.0),
                                 daemon=True)
    hb_thread.start()

    # ── 执行 Vision QC v5 / v4 fallback ─────────────────────
    try:
        _emit("progress", job_id,
              data={"progress": 0.1, "stage": "加载 vision_qc_v5"},
              message="正在加载视觉审核模块...")

        # 确保项目根目录在 sys.path 中
        repo_str = str(REPO_ROOT)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)

        pdf_p = Path(pdf_path)
        png_p = Path(png_path) if png_path else None
        run_dir_p = Path(run_dir) if run_dir else None

        version = "v5"
        try:
            from app.services.vision_qc_v5 import run_vision_qc_v5

            _emit("progress", job_id,
                  data={"progress": 0.2, "stage": "运行 Vision QC v5"},
                  message="正在执行视觉审核...")
            result = run_vision_qc_v5(
                pdf_path=pdf_p,
                png_path=png_p,
                qc_json_path=None,
                run_dir=run_dir_p,
                run_id=job_id,
            )
        except Exception as exc:
            version = "v4"
            _emit("progress", job_id,
                  data={"progress": 0.25, "stage": "Vision QC v4 fallback", "error": str(exc)},
                  message=f"Vision QC v5 不可用，降级 v4: {exc}")
            from app.services.vision_qc_v4 import run_vision_qc_v4

            result = run_vision_qc_v4(
                pdf_path=pdf_p,
                png_path=png_p,
                qc_json_path=None,
                run_dir=run_dir_p,
            )

        _emit("progress", job_id,
              data={"progress": 0.9, "stage": "审核完成"},
              message="视觉审核完成")

        # 提取关键结果
        score = result.get("score")
        pass_status = result.get("pass", False)
        _emit("job_finished", job_id,
              data={
                  "result": {
                      "score": score,
                      "pass": pass_status,
                      "version": version,
                      "mode": result.get("mode", ""),
                      "details": result,
                  },
              },
              message=f"视觉审核完成 (score={score}, pass={pass_status})")
        return 0

    except ImportError as exc:
        _emit("job_failed", job_id,
              data={"error": f"模块导入失败: {exc}"},
              message=f"vision_qc 导入失败: {exc}")
        return 2
    except Exception as exc:
        _emit("job_failed", job_id,
              data={"error": str(exc)},
              message=f"视觉审核异常: {exc}")
        return 3
    finally:
        stop_hb.set()


if __name__ == "__main__":
    sys.exit(main())
