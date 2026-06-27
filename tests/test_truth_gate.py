from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tools.truth_gate import evaluate_case


FAKE_PASS_CASE = REPO_ROOT / "tests" / "fixtures" / "fake_pass_case"


def test_truth_gate_rejects_fake_release_pass_case() -> None:
    report = evaluate_case(FAKE_PASS_CASE, profile="release-v3")

    keys = {item["key"] for item in report["hard_failures"]}
    assert report["allowed_to_claim_release_pass"] is False
    assert report["pass"] is False
    assert "sw_session_not_connected" in keys
    assert "drawing_artifact_stale" in keys
    assert "note_dimensions_masquerade_as_displaydims" in keys
    assert "mock_synthetic_or_fallback_claimed_release_pass" in keys
    assert "reference_compare_missing_without_reason" in keys


def test_truth_gate_allows_clean_release_case(tmp_path: Path) -> None:
    case_dir = tmp_path / "clean_case"
    drawing_dir = case_dir / "drawing"
    drawing_dir.mkdir(parents=True)
    artifact = drawing_dir / "clean.PNG"
    artifact.write_bytes(b"clean")
    case_dir.joinpath("sw_session.json").write_text(
        json.dumps({"status": "connected"}, indent=2),
        encoding="utf-8",
    )
    case_dir.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "job_started_at": "2000-01-01T00:00:00Z",
                "release_pass": True,
                "drawing_artifacts": ["drawing/clean.PNG"],
                "part_class": "feature_part",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    case_dir.joinpath("dimension_validation.json").write_text(
        json.dumps(
            {
                "part_class": "feature_part",
                "display_dim_count": 12,
                "note_dim_count": 0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    case_dir.joinpath("reference_compare.json").write_text(
        json.dumps({"pass": True}, indent=2),
        encoding="utf-8",
    )

    report = evaluate_case(case_dir, profile="release-v3")

    assert report["allowed_to_claim_release_pass"] is True
    assert report["hard_failures"] == []


def test_truth_gate_cli_returns_nonzero_for_fake_pass_case() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "tools/truth_gate.py",
            "--fixtures",
            str(FAKE_PASS_CASE),
            "--profile",
            "release-v3",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode != 0
    report = json.loads(proc.stdout)
    assert report["allowed_to_claim_release_pass"] is False
    assert report["hard_fail_count"] >= 5
