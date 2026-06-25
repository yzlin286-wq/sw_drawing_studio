"""QProcess worker for Drawing Review corrective actions.

This keeps Add-in, Document Manager, and Vision QC service calls out of the Qt
UI process while preserving the JSONL job event contract used by JobRunner.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)


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


def _load_dimension_policy(run_dir: str) -> dict:
    if not run_dir:
        return {}
    path = Path(run_dir) / "qc" / "blueprint_decision.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    policy = data.get("dimension_policy", {}) if isinstance(data, dict) else {}
    return {
        "dimension_policy": policy,
        "part_class": data.get("part_class", "") if isinstance(data, dict) else "",
        "required_dims": policy.get("required", []) if isinstance(policy, dict) else [],
        "optional_dims": policy.get("optional", []) if isinstance(policy, dict) else [],
    }


def _run_addin_dimension(args: argparse.Namespace) -> dict:
    from app.services.solidworks_global_lock import acquire_lock, release_lock
    from app.services.sw_addin_client import generate_dimensions_v3

    lock_result = acquire_lock(
        owner_project="sw_drawing_studio",
        owner_workspace=str(Path(__file__).resolve().parent.parent.parent),
        job_id=args.job_id,
        operation="drawing_review.addin_dimension",
        part_path=args.slddrw_path,
        timeout_sec=30,
        run_id=args.run_id,
        ttl_sec=120,
    )
    if not lock_result.get("acquired"):
        return {
            "success": False,
            "status": "blocked_by_solidworks_lock",
            "failure_bucket": "solidworks_lock_conflict",
            "reason": lock_result.get("reason", "blocked_by_solidworks_lock"),
            "owner": lock_result.get("owner", {}),
            "fix_suggestion": lock_result.get("fix_suggestion", "等待当前 CAD job 完成，或手动确认后释放 stale lock"),
        }
    try:
        return generate_dimensions_v3(
            drawing_path=args.slddrw_path,
            part_path=args.sldprt_path,
            run_dir=Path(args.run_dir) if args.run_dir else None,
            run_id=args.run_id,
            policy=_load_dimension_policy(args.run_dir),
        )
    finally:
        release_lock(args.job_id, "drawing_review_addin_dimension_finished")


def _run_docmgr_relink(args: argparse.Namespace) -> dict:
    from app.services.docmgr_service import relink_drawing_references

    return relink_drawing_references(
        drawing_path=args.slddrw_path,
        part_path=args.sldprt_path,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        run_id=args.run_id,
        mode="apply",
    )


def _run_vision_qc_v3(args: argparse.Namespace) -> dict:
    from app.services.vision_qc_v3 import run_vision_qc_v3

    return run_vision_qc_v3(
        pdf_path=Path(args.pdf_path),
        png_path=Path(args.png_path) if args.png_path else None,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        run_id=args.run_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Drawing Review action worker")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--action", required=True, choices=["addin_dimension", "docmgr_relink", "vision_qc_v3"])
    parser.add_argument("--slddrw-path", default="")
    parser.add_argument("--sldprt-path", default="")
    parser.add_argument("--pdf-path", default="")
    parser.add_argument("--png-path", default="")
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()

    action_labels = {
        "addin_dimension": "Add-in Dimension V3",
        "docmgr_relink": "DocMgr Relink",
        "vision_qc_v3": "Vision QC v3",
    }
    action_label = action_labels[args.action]
    job_id = args.job_id

    _emit(
        "job_started",
        job_id,
        data={
            "job_type": "drawing_review",
            "action": args.action,
            "action_name": action_label,
            "run_dir": args.run_dir,
            "run_id": args.run_id,
        },
        message=f"{action_label} started",
    )

    try:
        _emit("progress", job_id, data={"progress": 0.1, "stage": "validate_inputs"}, message="Validating inputs")
        if args.action in {"addin_dimension", "docmgr_relink"}:
            if not args.slddrw_path or not args.sldprt_path:
                raise ValueError("SLDDRW and SLDPRT paths are required")
        if args.action == "vision_qc_v3" and not args.pdf_path:
            raise ValueError("PDF path is required")

        _emit("progress", job_id, data={"progress": 0.3, "stage": "run_service"}, message=f"Running {action_label}")
        if args.action == "addin_dimension":
            result = _run_addin_dimension(args)
        elif args.action == "docmgr_relink":
            result = _run_docmgr_relink(args)
        else:
            result = _run_vision_qc_v3(args)

        if not isinstance(result, dict):
            result = {"success": False, "reason": f"service returned {type(result).__name__}", "raw_result": repr(result)}
        result.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
        result.setdefault("action", args.action)
        result.setdefault("action_name", action_label)
        result.setdefault("run_id", args.run_id)
        result.setdefault("run_dir", args.run_dir)

        _emit("progress", job_id, data={"progress": 0.9, "stage": "complete"}, message=f"{action_label} completed")
        _emit(
            "job_finished",
            job_id,
            data={"result": result, "action": args.action, "action_name": action_label},
            message=f"{action_label} finished",
        )
        return 0
    except Exception as exc:
        error = {
            "error": str(exc),
            "reason": str(exc),
            "success": False,
            "action": args.action,
            "action_name": action_label,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "run_id": args.run_id,
            "run_dir": args.run_dir,
        }
        _emit("job_failed", job_id, data=error, message=f"{action_label} failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
