"""Test blueprint_decision_service v2.1"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"c:\Users\Vision\Desktop\SW 相关")

from app.services.blueprint_decision_service import generate_blueprint_decision, load_blueprint_decision


def test_feature_part():
    """Test feature_part blueprint decision"""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        # Create part_class.json
        qc_dir = run_dir / "qc"
        qc_dir.mkdir()
        part_class_data = {
            "part_path": "test.SLDPRT",
            "part_name": "test.SLDPRT",
            "part_class": "feature_part",
            "reason": "default",
            "bbox_mm": [100.0, 50.0, 20.0],
            "is_standard": False,
            "has_features": True,
        }
        (qc_dir / "part_class.json").write_text(json.dumps(part_class_data), encoding="utf-8")

        decision = generate_blueprint_decision(run_dir, run_id="test_001")

        assert decision["part_class"] == "feature_part"
        assert decision["blueprint_matched"] is True
        assert decision["blueprint_fallback_used"] is False
        assert decision["dimension_policy"]["policy"] == "full"
        assert "overall_length" in decision["dimension_policy"]["required_dims"]
        assert "hole_diameter" in decision["dimension_policy"]["required_dims"]
        assert decision["dimension_policy"]["min_display_dim_count"] == 3
        assert decision["vision_policy"]["policy"] == "strict"
        assert decision["summary"]["required_dims_count"] >= 3
        print(f"PASS test_feature_part: policy={decision['dimension_policy']['policy']}, required={decision['dimension_policy']['required_dims']}")


def test_fastener():
    """Test fastener blueprint decision"""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        qc_dir = run_dir / "qc"
        qc_dir.mkdir()
        part_class_data = {
            "part_class": "fastener",
            "reason": "filename match: M6x20",
            "is_standard": True,
            "std_no": "GB/T 5783",
            "std_spec": "M6x20",
        }
        (qc_dir / "part_class.json").write_text(json.dumps(part_class_data), encoding="utf-8")

        decision = generate_blueprint_decision(run_dir, run_id="test_002")

        assert decision["part_class"] == "fastener"
        assert decision["dimension_policy"]["policy"] == "standard_annotation"
        assert "thread_spec" in decision["dimension_policy"]["required_dims"]
        assert decision["dimension_policy"]["require_display_dim"] is False
        assert decision["dimension_policy"]["allow_note_annotation"] is True
        assert decision["vision_policy"]["policy"] == "lenient"
        print(f"PASS test_fastener: policy={decision['dimension_policy']['policy']}, required={decision['dimension_policy']['required_dims']}")


def test_long_thin():
    """Test long_thin blueprint decision"""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        qc_dir = run_dir / "qc"
        qc_dir.mkdir()
        part_class_data = {
            "part_class": "long_thin",
            "reason": "long_thin ratio=8.50",
            "bbox_mm": [170.0, 20.0, 20.0],
            "long_thin_ratio": 8.50,
        }
        (qc_dir / "part_class.json").write_text(json.dumps(part_class_data), encoding="utf-8")

        decision = generate_blueprint_decision(run_dir, run_id="test_003")

        assert decision["part_class"] == "long_thin"
        assert decision["dimension_policy"]["policy"] == "length_critical"
        assert "overall_length" in decision["dimension_policy"]["required_dims"]
        assert "overall_diameter" in decision["dimension_policy"]["required_dims"]
        assert decision["dimension_policy"]["min_display_dim_count"] == 2
        print(f"PASS test_long_thin: policy={decision['dimension_policy']['policy']}, required={decision['dimension_policy']['required_dims']}")


def test_fallback_default():
    """Test fallback to default when part_class not in yaml"""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        qc_dir = run_dir / "qc"
        qc_dir.mkdir()
        part_class_data = {
            "part_class": "unknown_class",
            "reason": "test",
        }
        (qc_dir / "part_class.json").write_text(json.dumps(part_class_data), encoding="utf-8")

        decision = generate_blueprint_decision(run_dir, run_id="test_004")

        # unknown_class 不在 yaml，应回退到 default
        assert decision["part_class"] == "unknown_class"
        assert decision["blueprint_matched"] is False
        assert decision["blueprint_fallback_used"] is True
        # 应该使用 default 的 dimension_policy
        assert decision["dimension_policy"]["policy"] == "outline_only"
        print(f"PASS test_fallback_default: policy={decision['dimension_policy']['policy']}, fallback={decision['blueprint_fallback_used']}")


def test_load_existing():
    """Test loading existing blueprint_decision.json"""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        qc_dir = run_dir / "qc"
        qc_dir.mkdir()
        existing = {"version": "v2.1", "part_class": "test", "cached": True}
        (qc_dir / "blueprint_decision.json").write_text(json.dumps(existing), encoding="utf-8")

        loaded = load_blueprint_decision(run_dir)
        assert loaded.get("cached") is True
        print(f"PASS test_load_existing: part_class={loaded.get('part_class')}")


def test_explanation_readable():
    """Test that explanations are human-readable"""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        qc_dir = run_dir / "qc"
        qc_dir.mkdir()
        part_class_data = {
            "part_class": "spring",
            "reason": "filename match: 弹簧",
            "bbox_mm": [50.0, 50.0, 30.0],
        }
        (qc_dir / "part_class.json").write_text(json.dumps(part_class_data), encoding="utf-8")

        decision = generate_blueprint_decision(run_dir, run_id="test_005")

        # 验证解释字段非空且可读
        assert len(decision["part_class_explanation"]) > 10
        assert len(decision["dimension_policy"]["explanation"]) > 10
        assert len(decision["vision_policy"]["explanation"]) > 10
        assert "spring_free_length" in decision["dimension_policy"]["required_dims"]
        assert "spring_outer_diameter" in decision["dimension_policy"]["required_dims"]
        print(f"PASS test_explanation_readable: spring required={decision['dimension_policy']['required_dims']}")


if __name__ == "__main__":
    test_feature_part()
    test_fastener()
    test_long_thin()
    test_fallback_default()
    test_load_existing()
    test_explanation_readable()
    print("\n=== All blueprint_decision_service v2.1 tests passed ===")
