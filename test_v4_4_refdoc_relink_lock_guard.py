from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services import refdoc_relink_service as svc


def _clear_lock_env(lock_path: Path) -> None:
    os.environ["SW_DRAWING_STUDIO_LOCK_PATH"] = str(lock_path)
    os.environ.pop("SW_DRAWING_STUDIO_LOCK_JOB_ID", None)
    os.environ.pop("JOB_ID", None)


def _assert_blocked(result: dict) -> None:
    assert result["ok"] is False
    assert result["status"] == "blocked_by_solidworks_lock"
    assert result["failure_bucket"] == "solidworks_lock_conflict"
    assert result["lock_conflict"]["ok"] is False


def test_refdoc_relink_private_strategies_require_current_worker_lock() -> None:
    with TemporaryDirectory() as tmp:
        _clear_lock_env(Path(tmp) / "solidworks_global_lock.json")

        _assert_blocked(svc._strategy_pywin32_late("dummy.SLDDRW", "dummy.SLDPRT", ["Drawing View1"]))
        _assert_blocked(svc._strategy_vba_macro("dummy.SLDDRW", "dummy.SLDPRT", ["Drawing View1"]))
        _assert_blocked(svc._strategy_dotnet_sidecar("dummy.SLDDRW", "dummy.SLDPRT", ["Drawing View1"]))

        verify = svc._verify_after_relink("dummy.SLDDRW", "dummy.SLDPRT", ["Drawing View1", "Drawing View2"])
        assert verify["status"] == "blocked_by_solidworks_lock"
        assert verify["failure_bucket"] == "solidworks_lock_conflict"
        assert verify["bad_ref_count"] == 2


def test_refdoc_relink_public_entrypoint_still_blocks_without_lock() -> None:
    with TemporaryDirectory() as tmp:
        _clear_lock_env(Path(tmp) / "solidworks_global_lock.json")

        result = svc.relink_refdoc("dummy.SLDDRW", "dummy.SLDPRT", ["Drawing View1"], strategy="pywin32_late")

        assert result["ok"] is False
        assert result["status"] == "blocked_by_solidworks_lock"
        assert result["failure_bucket"] == "solidworks_lock_conflict"
        assert result["attempts"][0]["message"] == "blocked_by_solidworks_lock"


def test_refdoc_relink_source_guards_every_real_strategy_helper() -> None:
    source = Path("app/services/refdoc_relink_service.py").read_text(encoding="utf-8")
    for marker in [
        'require_current_job_lock("refdoc_relink_service._strategy_pywin32_late")',
        'require_current_job_lock("refdoc_relink_service._strategy_vba_macro")',
        'require_current_job_lock("refdoc_relink_service._strategy_dotnet_sidecar")',
        'require_current_job_lock("refdoc_relink_service._verify_after_relink")',
    ]:
        assert marker in source


if __name__ == "__main__":
    test_refdoc_relink_private_strategies_require_current_worker_lock()
    test_refdoc_relink_public_entrypoint_still_blocks_without_lock()
    test_refdoc_relink_source_guards_every_real_strategy_helper()
    print("PASS test_v4_4_refdoc_relink_lock_guard")
