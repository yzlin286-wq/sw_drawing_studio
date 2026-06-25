from __future__ import annotations

import sys
from pathlib import Path

import app.services.resource_paths as resource_paths
from app.main import _print_pipeline_script_info


def test_source_mode_worker_command_uses_python_script() -> None:
    script = Path("app/workers/mock_long_job_worker.py")
    program, args = resource_paths.worker_command("mock", script, ["--job-id", "abc"])
    assert program == sys.executable
    assert args[:2] == [str(script), "--job-id"]
    assert args[-1] == "abc"


def test_source_mode_pipeline_command_uses_script_path() -> None:
    cmd = resource_paths.pipeline_command("drw_qc_loop_v6", ["part.SLDPRT"])
    assert cmd[0] == sys.executable
    assert "-u" in cmd
    assert cmd[-1] == "part.SLDPRT"
    assert cmd[-2].endswith("drw_qc_loop_v6.py")


def test_frozen_worker_and_pipeline_commands(monkeypatch) -> None:
    monkeypatch.setattr(resource_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", "C:/dist/sw_drawing_studio.exe")

    program, args = resource_paths.worker_command("cad", Path("ignored.py"), ["--job-id", "job"])
    assert program == "C:/dist/sw_drawing_studio.exe"
    assert args == ["--worker", "cad", "--job-id", "job"]

    program, args = resource_paths.worker_command("drawing_review", Path("ignored.py"), ["--job-id", "review"])
    assert program == "C:/dist/sw_drawing_studio.exe"
    assert args == ["--worker", "drawing_review", "--job-id", "review"]

    program, args = resource_paths.worker_command("qc_action", Path("ignored.py"), ["--job-id", "qc"])
    assert program == "C:/dist/sw_drawing_studio.exe"
    assert args == ["--worker", "qc_action", "--job-id", "qc"]

    program, args = resource_paths.worker_command("system_health", Path("ignored.py"), ["--job-id", "health"])
    assert program == "C:/dist/sw_drawing_studio.exe"
    assert args == ["--worker", "system_health", "--job-id", "health"]

    program, args = resource_paths.worker_command("solidworks_com_probe", Path("ignored.py"), ["--method", "get_active_object"])
    assert program == "C:/dist/sw_drawing_studio.exe"
    assert args == ["--worker", "solidworks_com_probe", "--method", "get_active_object"]

    program, args = resource_paths.worker_command("llm_action", Path("ignored.py"), ["--job-id", "llm"])
    assert program == "C:/dist/sw_drawing_studio.exe"
    assert args == ["--worker", "llm_action", "--job-id", "llm"]

    cmd = resource_paths.pipeline_command("drw_generate_v6", ["part.SLDPRT"])
    assert cmd == [
        "C:/dist/sw_drawing_studio.exe",
        "--pipeline-script",
        "drw_generate_v6",
        "part.SLDPRT",
    ]


def test_pipeline_script_info_does_not_execute_script() -> None:
    assert _print_pipeline_script_info(["drw_quality_check"]) == 0


if __name__ == "__main__":
    class _RestoreMonkeyPatch:
        def __init__(self) -> None:
            self._items = []

        def setattr(self, obj, name, value) -> None:
            self._items.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

        def undo(self) -> None:
            for obj, name, old_value in reversed(self._items):
                setattr(obj, name, old_value)

    test_source_mode_worker_command_uses_python_script()
    test_source_mode_pipeline_command_uses_script_path()
    test_pipeline_script_info_does_not_execute_script()
    mp = _RestoreMonkeyPatch()
    try:
        test_frozen_worker_and_pipeline_commands(mp)
    finally:
        mp.undo()
    print("v2.3 resource paths verification PASS")
