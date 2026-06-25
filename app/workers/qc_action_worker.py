"""QProcess worker for legacy QC page actions.

The legacy QC page still needs PNG rendering, Vision QC v2, and optional LLM
vision scoring, but those actions can touch PDF rendering, image processing, or
network/model calls. Keep them out of the Qt UI process and report through the
same stdout JSONL contract as the other v3 workers.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _emit(event_type: str, job_id: str, data: dict | None = None, message: str = "") -> None:
    event = {
        "event_type": event_type,
        "type": event_type,
        "job_id": job_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "data": data or {},
        "message": message,
    }
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _default_png_for_qc(qc_json_path: Path) -> Path:
    stem = qc_json_path.stem.replace("_qc", "")
    candidates = [
        qc_json_path.with_name(stem + ".PNG"),
        qc_json_path.with_name(stem + ".png"),
        qc_json_path.parent / "drawing" / "preview.PNG",
        qc_json_path.parent.parent / "drawing" / f"{stem}.PNG",
        qc_json_path.parent.parent / "drawing" / f"{stem}.png",
    ]
    return next((p for p in candidates if p.exists()), candidates[0])


def _run_render_png(args: argparse.Namespace) -> dict:
    if not args.slddrw_path:
        raise ValueError("SLDDRW path is required for render_png")
    if not args.png_path:
        raise ValueError("PNG output path is required for render_png")

    from app.services.vision_qc import slddrw_to_png

    ok = bool(slddrw_to_png(args.slddrw_path, args.png_path))
    png = Path(args.png_path)
    if not ok or not png.exists():
        raise RuntimeError("PNG render failed: no PDF/PNG source could be converted")
    return {
        "success": True,
        "action": args.action,
        "slddrw_path": args.slddrw_path,
        "png_path": str(png),
        "size_bytes": png.stat().st_size,
    }


def _run_vision_qc_v2(args: argparse.Namespace) -> dict:
    if not args.qc_json_path:
        raise ValueError("qc_json_path is required for vision_qc_v2")

    from app.services.vision_qc_v2 import run_vision_qc_v2

    qc_path = Path(args.qc_json_path)
    png_path = Path(args.png_path) if args.png_path else _default_png_for_qc(qc_path)
    run_dir = Path(args.run_dir) if args.run_dir else qc_path.parent.parent
    result = run_vision_qc_v2(qc_path, png_path, run_dir)
    if not isinstance(result, dict):
        raise RuntimeError(f"Vision QC v2 returned {type(result).__name__}")
    result.setdefault("success", True)
    result.setdefault("action", args.action)
    result.setdefault("source_qc", str(qc_path))
    result.setdefault("source_png", str(png_path))
    result.setdefault("run_dir", str(run_dir))
    return result


def _run_legacy_vision_score(args: argparse.Namespace) -> dict:
    if not args.slddrw_path:
        raise ValueError("SLDDRW path is required for legacy_vision_score")

    from app.services.llm_client import build_default_client
    from app.services.vision_qc import vision_score

    llm = build_default_client()
    if not getattr(llm, "model", ""):
        raise RuntimeError("LLM model is not configured")
    result = vision_score(args.slddrw_path, args.qc_json_path, llm)
    if not isinstance(result, dict):
        raise RuntimeError(f"vision_score returned {type(result).__name__}")
    result.setdefault("success", True)
    result.setdefault("action", args.action)
    result.setdefault("slddrw_path", args.slddrw_path)
    result.setdefault("qc_json_path", args.qc_json_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Legacy QC action worker")
    parser.add_argument("--job-id", required=True)
    parser.add_argument(
        "--action",
        required=True,
        choices=["render_png", "vision_qc_v2", "legacy_vision_score"],
    )
    parser.add_argument("--slddrw-path", default="")
    parser.add_argument("--qc-json-path", default="")
    parser.add_argument("--png-path", default="")
    parser.add_argument("--run-dir", default="")
    args = parser.parse_args()

    labels = {
        "render_png": "Render PNG",
        "vision_qc_v2": "Vision QC v2",
        "legacy_vision_score": "Legacy Vision Score",
    }
    label = labels[args.action]
    job_id = args.job_id

    _emit(
        "job_started",
        job_id,
        data={
            "job_type": "qc_action",
            "action": args.action,
            "action_name": label,
            "slddrw_path": args.slddrw_path,
            "qc_json_path": args.qc_json_path,
            "png_path": args.png_path,
            "run_dir": args.run_dir,
        },
        message=f"{label} started",
    )

    try:
        _emit("progress", job_id, data={"progress": 0.1, "stage": "validate_inputs"}, message="Validating inputs")
        _emit("heartbeat", job_id, data={"ts": time.time()}, message="qc worker alive")
        _emit("progress", job_id, data={"progress": 0.3, "stage": "run_action"}, message=f"Running {label}")

        if args.action == "render_png":
            result = _run_render_png(args)
        elif args.action == "vision_qc_v2":
            result = _run_vision_qc_v2(args)
        else:
            result = _run_legacy_vision_score(args)

        result.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
        result.setdefault("action_name", label)
        _emit("progress", job_id, data={"progress": 0.9, "stage": "complete"}, message=f"{label} completed")
        _emit(
            "job_finished",
            job_id,
            data={"result": result, "action": args.action, "action_name": label},
            message=f"{label} finished",
        )
        return 0
    except Exception as exc:
        error = {
            "error": str(exc),
            "reason": str(exc),
            "success": False,
            "action": args.action,
            "action_name": label,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "slddrw_path": args.slddrw_path,
            "qc_json_path": args.qc_json_path,
            "png_path": args.png_path,
            "run_dir": args.run_dir,
        }
        _emit("job_failed", job_id, data=error, message=f"{label} failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
