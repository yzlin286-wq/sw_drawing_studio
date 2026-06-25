"""Smoke tests for LLM action worker JSONL contract."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


WORKER = Path("app/workers/llm_action_worker.py")


def _run_worker(args: list[str], mock_response: str) -> tuple[int, list[dict]]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["SW_DRAWING_STUDIO_LLM_MOCK_RESPONSE"] = mock_response
    proc = subprocess.run(
        [sys.executable, str(WORKER), *args],
        cwd=Path(__file__).resolve().parent,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.strip().startswith("{")]
    return proc.returncode, events


def test_pre_analyze_worker_mock_jsonl() -> None:
    fixture = Path("drw_output") / "_llm_action_worker_test" / "sample.SLDPRT"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("fake part", encoding="utf-8")

    rc, events = _run_worker(
        ["--job-id", "llm_pre", "--action", "pre_analyze", "--part-path", str(fixture)],
        '{"category":"shaft","front_view":"Front","scale":"1:1"}',
    )

    assert rc == 0
    types = [event.get("type") for event in events]
    assert "job_started" in types
    assert "progress" in types
    assert "heartbeat" in types
    assert "warning" in types
    assert "job_finished" in types
    finished = next(event for event in events if event.get("type") == "job_finished")
    result = finished["data"]["result"]
    assert result["action"] == "pre_analyze"
    assert result["pre_analysis"]["category"] == "shaft"
    assert result["mock_response_used"] is True


def test_tech_text_worker_mock_jsonl() -> None:
    rc, events = _run_worker(
        ["--job-id", "llm_tech", "--action", "tech_text"],
        '["Deburr all sharp edges.", "Apply general tolerance GB/T 1804-m.", "Surface finish Ra 3.2 unless noted."]',
    )

    assert rc == 0
    types = [event.get("type") for event in events]
    assert "job_started" in types
    assert "progress" in types
    assert "heartbeat" in types
    assert "warning" in types
    assert "job_finished" in types
    finished = next(event for event in events if event.get("type") == "job_finished")
    result = finished["data"]["result"]
    assert result["action"] == "tech_text"
    assert len(result["items"]) == 3
    assert result["mock_response_used"] is True


if __name__ == "__main__":
    test_pre_analyze_worker_mock_jsonl()
    test_tech_text_worker_mock_jsonl()
    print("v2.3 llm action worker smoke PASS")