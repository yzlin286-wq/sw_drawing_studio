"""QProcess worker for LLM-backed UI actions.

AI pre-analysis and technical-text generation can block on network/model calls.
This worker keeps those calls outside the Qt UI process and reports progress via
stdout JSONL, matching the v3 JobRuntime contract.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TECH_BRIEF = (
    "Chinese mechanical drawing technical requirements. Use GB/T 4458.4, "
    "GB/T 1804-m, GB/T 131, GB/T 1182, first-angle projection, readable line "
    "weights, title block conventions, and general manufacturability notes."
)


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


def _parse_json_object(text: str) -> dict:
    if not text:
        return {}
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    candidates = [fenced.group(1)] if fenced else []
    candidates += [text]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except Exception:
            try:
                fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
                value = json.loads(fixed)
                if isinstance(value, dict):
                    return value
            except Exception:
                pass
    return {}


def _parse_json_list(text: str) -> list:
    if not text:
        return []
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text, re.IGNORECASE)
    candidates = [fenced.group(1)] if fenced else []
    candidates += [text]
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, list):
                return value
        except Exception:
            pass
    return []


def _chat(messages: list[dict]) -> tuple[str, bool]:
    mock = os.environ.get("SW_DRAWING_STUDIO_LLM_MOCK_RESPONSE", "")
    if mock:
        return mock, True

    from app.services.llm_client import build_default_client

    client = build_default_client()
    if not getattr(client, "model", ""):
        raise RuntimeError("LLM model is not configured")
    response = client.chat(messages)
    return str((response or {}).get("text") or ""), False


def _run_pre_analyze(args: argparse.Namespace) -> dict:
    if not args.part_path:
        raise ValueError("part_path is required for pre_analyze")
    part = Path(args.part_path)
    size = part.stat().st_size if part.exists() else 0
    messages = [
        {
            "role": "system",
            "content": (
                "You are a mechanical drawing expert. Infer the part category, "
                "front view, and drawing scale from the SolidWorks part file name "
                "and size. Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"File name: {part.name}\nSize bytes: {size}\n"
                "Return JSON with fields category, front_view, scale."
            ),
        },
    ]
    text, mocked = _chat(messages)
    parsed = _parse_json_object(text)
    if not parsed:
        raise RuntimeError("LLM pre-analysis returned no parseable JSON object")
    return {
        "success": True,
        "action": "pre_analyze",
        "part_path": str(part),
        "pre_analysis": parsed,
        "raw_text": text,
        "mock_response_used": mocked,
    }


def _run_tech_text(args: argparse.Namespace) -> dict:
    context = args.context or TECH_BRIEF
    messages = [
        {
            "role": "system",
            "content": (
                "You are a mechanical drawing expert. Generate at least three "
                "Chinese engineering drawing technical requirement notes. Return "
                "a JSON array only."
            ),
        },
        {
            "role": "user",
            "content": context + "\nReturn only a JSON array of strings.",
        },
    ]
    text, mocked = _chat(messages)
    parsed = _parse_json_list(text)
    items = [str(item).strip() for item in parsed if str(item).strip()]
    if not items:
        raise RuntimeError("LLM tech-text generation returned no parseable JSON array")
    return {
        "success": True,
        "action": "tech_text",
        "items": items,
        "raw_text": text,
        "mock_response_used": mocked,
    }


def _run_test_connection(args: argparse.Namespace) -> dict:
    try:
        provider_cfg = json.loads(args.context or "{}")
        if not isinstance(provider_cfg, dict):
            provider_cfg = {}
    except Exception as exc:
        raise ValueError(f"provider config JSON is invalid: {exc}") from exc

    from app.services.llm_client import LLMClient

    client = LLMClient(provider_cfg)
    ok, message, latency_ms = client.test_connection()
    return {
        "success": bool(ok),
        "action": "test_connection",
        "message": str(message),
        "latency_ms": int(latency_ms),
        "model": str(provider_cfg.get("model") or ""),
        "base_url": str(provider_cfg.get("base_url") or ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM action worker")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--action", required=True, choices=["pre_analyze", "tech_text", "test_connection"])
    parser.add_argument("--part-path", default="")
    parser.add_argument("--context", default="")
    parser.add_argument("--run-dir", default="")
    args = parser.parse_args()

    job_id = args.job_id
    _emit(
        "job_started",
        job_id,
        data={
            "job_type": "llm_action",
            "action": args.action,
            "part_path": args.part_path,
            "run_dir": args.run_dir,
        },
        message=f"LLM action started: {args.action}",
    )

    try:
        _emit("progress", job_id, data={"progress": 0.1, "stage": "validate_inputs"}, message="Validating inputs")
        _emit("heartbeat", job_id, data={"ts": time.time()}, message="llm worker alive")
        if os.environ.get("SW_DRAWING_STUDIO_LLM_MOCK_RESPONSE", ""):
            _emit("warning", job_id, data={"key": "mock_response_used"}, message="Using explicit LLM mock response")
        _emit("progress", job_id, data={"progress": 0.35, "stage": "run_llm_action"}, message="Running LLM action")

        if args.action == "pre_analyze":
            result = _run_pre_analyze(args)
        elif args.action == "tech_text":
            result = _run_tech_text(args)
        else:
            result = _run_test_connection(args)

        result.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
        _emit("progress", job_id, data={"progress": 0.9, "stage": "complete"}, message="LLM action completed")
        _emit("job_finished", job_id, data={"result": result, "action": args.action}, message="LLM action finished")
        return 0
    except Exception as exc:
        error = {
            "success": False,
            "action": args.action,
            "part_path": args.part_path,
            "run_dir": args.run_dir,
            "error": str(exc),
            "reason": str(exc),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _emit("job_failed", job_id, data=error, message=f"LLM action failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
