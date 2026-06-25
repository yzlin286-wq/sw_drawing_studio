"""Test final_quality v2.1 pass_with_manual_review logic"""
import json
import sys
import tempfile
from pathlib import Path

# Setup path
sys.path.insert(0, r"c:\Users\Vision\Desktop\SW 相关")

from app.services.final_quality import compute_final_quality, _load_human_review


class MockCtx:
    def __init__(self):
        self.hard_fail = []
        self.warnings = ["test warning"]
        self.drawing_usable = {"pass": True}
        self.dimension_grade = "B"
        self.usable_for = ["manufacturing"]
        self.drawing_accuracy_score = {"total": 85}


def test_no_manual_review():
    """Test: no human_review.json → pass_with_warning"""
    with tempfile.TemporaryDirectory() as tmp:
        ctx = MockCtx()
        vqc = {"summary": {"critical": 0, "major": 0, "minor": 2, "total": 2}}
        result = compute_final_quality(ctx, vqc, run_dir=tmp)
        assert result["status"] == "pass_with_warning", f"Expected pass_with_warning, got {result['status']}"
        assert result["has_manual_review"] is False
        assert result["deliverable"] is True
        print(f"PASS test_no_manual_review: status={result['status']}, deliverable={result['deliverable']}")


def test_with_manual_review():
    """Test: with human_review.json → pass_with_manual_review"""
    with tempfile.TemporaryDirectory() as tmp:
        # Create human_review.json
        qc_dir = Path(tmp) / "qc"
        qc_dir.mkdir()
        review = {
            "run_id": "test_001",
            "status": "manual_confirmed",
            "reviewer": "operator",
            "timestamp": "2026-06-20 12:00:00",
            "decision": "pass_with_manual_review",
        }
        (qc_dir / "human_review.json").write_text(json.dumps(review), encoding="utf-8")

        ctx = MockCtx()
        vqc = {"summary": {"critical": 0, "major": 0, "minor": 2, "total": 2}}
        result = compute_final_quality(ctx, vqc, run_dir=tmp)
        assert result["status"] == "pass_with_manual_review", f"Expected pass_with_manual_review, got {result['status']}"
        assert result["has_manual_review"] is True
        assert result["deliverable"] is True
        assert result["manual_review"]["reviewer"] == "operator"
        print(f"PASS test_with_manual_review: status={result['status']}, deliverable={result['deliverable']}")


def test_with_manual_review_critical():
    """Test: with manual_review + vision critical → pass_with_manual_review (override need_review)"""
    with tempfile.TemporaryDirectory() as tmp:
        qc_dir = Path(tmp) / "qc"
        qc_dir.mkdir()
        review = {
            "run_id": "test_002",
            "status": "manual_confirmed",
            "reviewer": "operator",
            "timestamp": "2026-06-20 12:00:00",
        }
        (qc_dir / "human_review.json").write_text(json.dumps(review), encoding="utf-8")

        ctx = MockCtx()
        vqc = {"summary": {"critical": 1, "major": 0, "minor": 0, "total": 1}}
        result = compute_final_quality(ctx, vqc, run_dir=tmp)
        assert result["status"] == "pass_with_manual_review", f"Expected pass_with_manual_review, got {result['status']}"
        assert result["conflict"] is True
        assert result["deliverable"] is True
        print(f"PASS test_with_manual_review_critical: status={result['status']}, conflict={result['conflict']}")


def test_hard_fail_no_override():
    """Test: hard_fail cannot be overridden by manual_review"""
    with tempfile.TemporaryDirectory() as tmp:
        qc_dir = Path(tmp) / "qc"
        qc_dir.mkdir()
        review = {"status": "manual_confirmed", "reviewer": "op"}
        (qc_dir / "human_review.json").write_text(json.dumps(review), encoding="utf-8")

        ctx = MockCtx()
        ctx.hard_fail = ["missing_pdf"]
        ctx.drawing_usable = {"pass": False}
        vqc = {"summary": {"critical": 0, "major": 0, "minor": 0, "total": 0}}
        result = compute_final_quality(ctx, vqc, run_dir=tmp)
        assert result["status"] == "fail", f"Expected fail, got {result['status']}"
        assert result["deliverable"] is False
        print(f"PASS test_hard_fail_no_override: status={result['status']}, deliverable={result['deliverable']}")


def test_vqc3_warnings_loaded():
    """Test: vision_qc_v3.json fallback_used loaded as warnings"""
    with tempfile.TemporaryDirectory() as tmp:
        qc_dir = Path(tmp) / "qc"
        qc_dir.mkdir()
        vqc3 = {
            "fallback_used": ["ocr", "yolo_detection"],
            "mode": "fallback",
        }
        (qc_dir / "vision_qc_v3.json").write_text(json.dumps(vqc3), encoding="utf-8")

        ctx = MockCtx()
        vqc = {"summary": {"critical": 0, "major": 0, "minor": 0, "total": 0}}
        result = compute_final_quality(ctx, vqc, run_dir=tmp)
        # Should have vqc3 warnings + initial test warning
        assert result["geo_qc"]["warnings_count"] >= 3, f"Expected >=3 warnings, got {result['geo_qc']['warnings_count']}"
        print(f"PASS test_vqc3_warnings_loaded: warnings_count={result['geo_qc']['warnings_count']}")


if __name__ == "__main__":
    test_no_manual_review()
    test_with_manual_review()
    test_with_manual_review_critical()
    test_hard_fail_no_override()
    test_vqc3_warnings_loaded()
    print("\n=== All final_quality v2.1 tests passed ===")
