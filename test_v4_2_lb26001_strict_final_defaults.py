from pathlib import Path

from tools.validation.lb26001_006_acceptance_proof_v4_2 import (
    DEFAULT_ACCEPTANCE_GATE as PROOF_ACCEPTANCE_GATE,
    DEFAULT_UI_GATE as PROOF_UI_GATE,
)
from tools.validation.lb26001_006_regression_readiness_v4_2 import (
    DEFAULT_EXPANSION_GATE as READINESS_EXPANSION_GATE,
    DEFAULT_UI_GATE as READINESS_UI_GATE,
)
from tools.validation.lb26001_requested_drawings_status_v4_2 import (
    DEFAULT_ACCEPTANCE_GATE as REQUESTED_STATUS_ACCEPTANCE_GATE,
)


STRICT_FINAL_DIR = "closed_loop_strict_final_20260624"
LEGACY_DEFAULT_DIR = "closed_loop_" + "20260624"


def test_lb26001_active_defaults_use_strict_final_ui_evidence() -> None:
    defaults = [
        READINESS_UI_GATE,
        READINESS_EXPANSION_GATE,
        PROOF_UI_GATE,
        PROOF_ACCEPTANCE_GATE,
        REQUESTED_STATUS_ACCEPTANCE_GATE,
    ]

    for path in defaults:
        text = str(path)
        assert STRICT_FINAL_DIR in text
        assert LEGACY_DEFAULT_DIR not in text


def test_lb26001_validation_sources_do_not_reintroduce_legacy_default_gate() -> None:
    repo_root = Path(__file__).resolve().parent
    active_roots = [
        repo_root / "tools" / "validation",
        repo_root / "app",
    ]
    offenders: list[str] = []

    for root in active_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if LEGACY_DEFAULT_DIR in text:
                offenders.append(str(path.relative_to(repo_root)))

    assert offenders == []


if __name__ == "__main__":
    test_lb26001_active_defaults_use_strict_final_ui_evidence()
    test_lb26001_validation_sources_do_not_reintroduce_legacy_default_gate()
    print("PASS test_v4_2_lb26001_strict_final_defaults")
