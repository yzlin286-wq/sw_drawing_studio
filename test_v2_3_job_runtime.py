"""Lightweight v2.3 job runtime verification.

This test avoids SolidWorks and validates the QProcess/event/facade contract using
the mock worker. It is intended to catch UI-plumbing regressions before running
real CAD jobs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QProcess, QTimer

from app.services.job_event_bus import JobEventBus
from app.services.job_queue import JobPriority, JobQueue, JobRecord, JobStatus
from app.services.job_runner import JobRunner
from app.services.job_runtime_facade import JobRuntimeFacade


def test_job_record_defaults() -> None:
    record = JobRecord(
        job_id="unit",
        part_name="part",
        part_path="part.SLDPRT",
        job_type="cad",
        priority=JobPriority.NORMAL,
    )
    assert record.status == JobStatus.PENDING


def test_batch_worker_args() -> None:
    queue = JobQueue()
    runner = JobRunner(event_bus=JobEventBus(), job_queue=queue)
    record = JobRecord(
        job_id="batch",
        part_name="batch_2",
        part_path="",
        job_type="batch",
        timeout_s=12,
    )
    record.result["part_paths"] = ["a.SLDPRT", "b.SLDPRT"]
    record.result["output_dir"] = "out"
    record.result["max_rounds"] = 5
    args = runner._build_worker_args(record)
    assert "--parts-json" in args
    parts_json = args[args.index("--parts-json") + 1]
    assert json.loads(parts_json) == ["a.SLDPRT", "b.SLDPRT"]
    assert args[args.index("--output-dir") + 1] == "out"
    assert args[args.index("--max-rounds") + 1] == "5"
    assert args[args.index("--timeout-s") + 1] == "12"


def test_drawing_review_worker_args() -> None:
    queue = JobQueue()
    runner = JobRunner(event_bus=JobEventBus(), job_queue=queue)
    record = JobRecord(
        job_id="review",
        part_name="review_part",
        part_path="fixture.SLDDRW",
        job_type="drawing_review",
        timeout_s=300,
        run_dir="drw_output/runs/review_args",
        run_id="review_run",
    )
    record.result.update({
        "action": "vision_qc_v3",
        "slddrw_path": "fixture.SLDDRW",
        "sldprt_path": "fixture.SLDPRT",
        "pdf_path": "fixture.PDF",
        "png_path": "fixture.PNG",
    })
    args = runner._build_worker_args(record)
    assert args[args.index("--action") + 1] == "vision_qc_v3"
    assert args[args.index("--slddrw-path") + 1] == "fixture.SLDDRW"
    assert args[args.index("--pdf-path") + 1] == "fixture.PDF"
    assert args[args.index("--run-dir") + 1] == "drw_output/runs/review_args"
    assert args[args.index("--run-id") + 1] == "review_run"


def test_system_health_worker_args() -> None:
    queue = JobQueue()
    runner = JobRunner(event_bus=JobEventBus(), job_queue=queue)
    record = JobRecord(
        job_id="health",
        part_name="system_health_check",
        part_path="",
        job_type="system_health",
        timeout_s=30,
    )
    args = runner._build_worker_args(record)
    assert args == ["--job-id", "health"]


def test_qc_action_worker_args() -> None:
    queue = JobQueue()
    runner = JobRunner(event_bus=JobEventBus(), job_queue=queue)
    record = JobRecord(
        job_id="qc",
        part_name="qc_render_fixture",
        part_path="fixture.SLDDRW",
        job_type="qc_action",
        timeout_s=120,
        run_dir="drw_output/runs/qc_args",
    )
    record.result.update({
        "action": "render_png",
        "slddrw_path": "fixture.SLDDRW",
        "qc_json_path": "fixture_qc.json",
        "png_path": "fixture.PNG",
    })
    args = runner._build_worker_args(record)
    assert args[args.index("--action") + 1] == "render_png"
    assert args[args.index("--slddrw-path") + 1] == "fixture.SLDDRW"
    assert args[args.index("--qc-json-path") + 1] == "fixture_qc.json"
    assert args[args.index("--png-path") + 1] == "fixture.PNG"
    assert args[args.index("--run-dir") + 1] == "drw_output/runs/qc_args"


def test_llm_action_worker_args() -> None:
    queue = JobQueue()
    runner = JobRunner(event_bus=JobEventBus(), job_queue=queue)
    record = JobRecord(
        job_id="llm",
        part_name="llm_pre_fixture",
        part_path="fixture.SLDPRT",
        job_type="llm_action",
        timeout_s=120,
        run_dir="drw_output/runs/llm_args",
    )
    record.result.update({
        "action": "pre_analyze",
        "part_path": "fixture.SLDPRT",
        "context": "context text",
    })
    args = runner._build_worker_args(record)
    assert args[args.index("--action") + 1] == "pre_analyze"
    assert args[args.index("--part-path") + 1] == "fixture.SLDPRT"
    assert args[args.index("--context") + 1] == "context text"
    assert args[args.index("--run-dir") + 1] == "drw_output/runs/llm_args"


def test_runner_skip_running_job_kills_process_and_logs_event() -> None:
    class DummyProcess:
        def __init__(self) -> None:
            self.killed = False

        def kill(self) -> None:
            self.killed = True

    run_dir = Path("drw_output/_job_runner_skip_test")
    log_path = run_dir / "job_event_log.jsonl"
    if log_path.exists():
        log_path.unlink()
    queue = JobQueue()
    event_bus = JobEventBus()
    runner = JobRunner(event_bus=event_bus, job_queue=queue)
    record = JobRecord(
        job_id="skip_running",
        part_name="mock_skip",
        part_path="",
        job_type="mock",
        run_dir=str(run_dir),
    )
    queue.add_job(record)
    queue.update_status(record.job_id, JobStatus.RUNNING)
    proc = DummyProcess()
    runner._processes[record.job_id] = proc  # type: ignore[assignment]

    assert runner.skip_job(record.job_id) is True
    status = queue.get_job(record.job_id)
    assert proc.killed is True
    assert status is not None
    assert status.status == JobStatus.COMPLETED
    assert log_path.exists()
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert any(e.get("data", {}).get("action") == "skipped" for e in events)
    bus_events = event_bus.get_events_for_job(record.job_id)
    assert any(e.data.get("process_killed") is True for e in bus_events)


def test_runner_missing_terminal_event_fails_job_and_logs_event() -> None:
    run_dir = Path("drw_output/_job_runner_missing_terminal_test")
    log_path = run_dir / "job_event_log.jsonl"
    if log_path.exists():
        log_path.unlink()
    queue = JobQueue()
    event_bus = JobEventBus()
    runner = JobRunner(event_bus=event_bus, job_queue=queue)
    record = JobRecord(
        job_id="missing_terminal",
        part_name="mock_missing_terminal",
        part_path="",
        job_type="mock",
        run_dir=str(run_dir),
    )
    queue.add_job(record)
    queue.update_status(
        record.job_id,
        JobStatus.RUNNING,
        last_event="warning",
        stage="subprocess",
    )

    runner._on_finished(record.job_id, 0, QProcess.ExitStatus.NormalExit)

    status = queue.get_job(record.job_id)
    assert status is not None
    assert status.status == JobStatus.FAILED
    assert status.error == "worker exited without terminal event"
    assert status.last_event == "job_failed"
    bus_events = event_bus.get_events_for_job(record.job_id)
    failure_events = [e for e in bus_events if e.event_type == "job_failed"]
    assert failure_events
    assert failure_events[-1].data["failure_bucket"] == "missing_terminal_worker_event"
    assert failure_events[-1].data["last_event"] == "warning"
    assert "orphan_descendant_cleanup" in failure_events[-1].data
    assert log_path.exists()
    logged = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert logged[-1]["event_type"] == "job_failed"
    assert logged[-1]["data"]["failure_bucket"] == "missing_terminal_worker_event"


def run_mock_facade_job() -> None:
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    facade = JobRuntimeFacade()
    seen: dict[str, object] = {"finished": False, "failed": False, "progress": 0}

    def on_progress(_job_id: str, data: dict) -> None:
        seen["progress"] = seen.get("progress", 0) + 1

    def on_finished(job_id: str, data: dict) -> None:
        seen["finished"] = True
        seen["job_id"] = job_id
        seen["result"] = data
        app.quit()

    def on_failed(job_id: str, data: dict) -> None:
        seen["failed"] = True
        seen["job_id"] = job_id
        seen["error"] = data
        app.quit()

    facade.job_progress.connect(on_progress)
    facade.job_finished.connect(on_finished)
    facade.job_failed.connect(on_failed)

    job_id = facade.start_mock_job(scenario="normal_pass", duration_s=0.2)
    QTimer.singleShot(5000, app.quit)
    app.exec()

    status = facade.get_job_status(job_id)
    assert seen["finished"] is True, seen
    assert seen["failed"] is False, seen
    assert int(seen["progress"]) >= 1, seen
    assert status is not None
    assert status["status"] == "completed", status


def test_facade_drawing_review_action_record(monkeypatch=None) -> None:
    facade = JobRuntimeFacade()
    facade.initialize()
    started: list[JobRecord] = []

    def fake_start(record: JobRecord) -> bool:
        started.append(record)
        return True

    if monkeypatch is not None:
        monkeypatch.setattr(facade._job_runner, "start_job", fake_start)
    else:
        facade._job_runner.start_job = fake_start  # type: ignore[method-assign]

    job_id = facade.start_drawing_review_action(
        action="docmgr_relink",
        slddrw_path="fixture.SLDDRW",
        sldprt_path="fixture.SLDPRT",
        run_dir="drw_output/runs/review",
        run_id="review",
    )
    status = facade.get_job_status(job_id)
    assert started and started[0].job_type == "drawing_review"
    assert status is not None
    assert status["result"]["action"] == "docmgr_relink"
    assert status["run_dir"] == "drw_output/runs/review"


def test_facade_system_health_record(monkeypatch=None) -> None:
    facade = JobRuntimeFacade()
    facade.initialize()
    started: list[JobRecord] = []

    def fake_start(record: JobRecord) -> bool:
        started.append(record)
        return True

    if monkeypatch is not None:
        monkeypatch.setattr(facade._job_runner, "start_job", fake_start)
    else:
        facade._job_runner.start_job = fake_start  # type: ignore[method-assign]

    job_id = facade.start_system_health_check(timeout_s=12)
    status = facade.get_job_status(job_id)
    assert started and started[0].job_type == "system_health"
    assert started[0].timeout_s == 12
    assert status is not None
    assert status["part_name"] == "system_health_check"
    assert status["result"]["scope"] == "system_health"


def test_facade_qc_action_record(monkeypatch=None) -> None:
    facade = JobRuntimeFacade()
    facade.initialize()
    started: list[JobRecord] = []

    def fake_start(record: JobRecord) -> bool:
        started.append(record)
        return True

    if monkeypatch is not None:
        monkeypatch.setattr(facade._job_runner, "start_job", fake_start)
    else:
        facade._job_runner.start_job = fake_start  # type: ignore[method-assign]

    job_id = facade.start_qc_action(
        action="vision_qc_v2",
        qc_json_path="fixture_qc.json",
        png_path="fixture.PNG",
        run_dir="drw_output/runs/qc",
        timeout_s=33,
    )
    status = facade.get_job_status(job_id)
    assert started and started[0].job_type == "qc_action"
    assert started[0].timeout_s == 33
    assert status is not None
    assert status["result"]["action"] == "vision_qc_v2"
    assert status["result"]["qc_json_path"] == "fixture_qc.json"
    assert status["run_dir"] == "drw_output/runs/qc"


def test_facade_llm_action_record(monkeypatch=None) -> None:
    facade = JobRuntimeFacade()
    facade.initialize()
    started: list[JobRecord] = []

    def fake_start(record: JobRecord) -> bool:
        started.append(record)
        return True

    if monkeypatch is not None:
        monkeypatch.setattr(facade._job_runner, "start_job", fake_start)
    else:
        facade._job_runner.start_job = fake_start  # type: ignore[method-assign]

    job_id = facade.start_llm_action(
        action="pre_analyze",
        part_path="fixture.SLDPRT",
        context="context text",
        timeout_s=44,
    )
    status = facade.get_job_status(job_id)
    assert started and started[0].job_type == "llm_action"
    assert started[0].timeout_s == 44
    assert status is not None
    assert status["result"]["action"] == "pre_analyze"
    assert status["result"]["part_path"] == "fixture.SLDPRT"
    assert status["run_dir"]

def test_mock_worker_exists() -> None:
    assert (Path(__file__).resolve().parent / "app" / "workers" / "mock_long_job_worker.py").exists()
    assert (Path(__file__).resolve().parent / "app" / "workers" / "drawing_review_worker.py").exists()
    assert (Path(__file__).resolve().parent / "app" / "workers" / "health_check_worker.py").exists()
    assert (Path(__file__).resolve().parent / "app" / "workers" / "qc_action_worker.py").exists()
    assert (Path(__file__).resolve().parent / "app" / "workers" / "llm_action_worker.py").exists()


if __name__ == "__main__":
    test_job_record_defaults()
    test_batch_worker_args()
    test_drawing_review_worker_args()
    test_system_health_worker_args()
    test_qc_action_worker_args()
    test_llm_action_worker_args()
    test_runner_skip_running_job_kills_process_and_logs_event()
    test_runner_missing_terminal_event_fails_job_and_logs_event()
    test_mock_worker_exists()
    test_facade_drawing_review_action_record()
    test_facade_system_health_record()
    test_facade_qc_action_record()
    test_facade_llm_action_record()
    run_mock_facade_job()
    print("v2.3 job runtime verification PASS")
