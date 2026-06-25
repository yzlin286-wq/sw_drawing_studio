from app.services import persisted_layout_solver as solver


def test_iso_outline_mismatch_is_warning_only() -> None:
    outlines = {
        "Front": [0.01, 0.15, 0.11, 0.16],
        "Top": [0.01, 0.10, 0.11, 0.11],
        "Right": [0.15, 0.15, 0.16, 0.16],
        "Iso": [0.15, 0.08, 0.24, 0.16],
    }
    centers = {
        "front": (0.06, 0.155),
        "top": (0.06, 0.105),
        "right": (0.155, 0.155),
        "iso": (0.195, 0.12),
    }
    target_outlines = {
        "front": [0.01, 0.15, 0.11, 0.16],
        "top": [0.01, 0.10, 0.11, 0.11],
        "right": [0.15, 0.15, 0.16, 0.16],
        "iso": [0.15, 0.08, 0.19, 0.12],
    }

    issues = solver._target_outline_size_issues(outlines, centers, target_outlines, 0.28)
    blocking = solver._blocking_target_outline_issues(issues)
    warnings = [item for item in issues if not item.get("blocking", True)]

    assert blocking == []
    assert [item["slot"] for item in warnings] == ["iso"]
    assert solver._target_outline_scale_direction(blocking) == ""


def test_primary_outline_too_small_requests_larger_scale() -> None:
    outlines = {
        "Front": [0.01, 0.15, 0.08, 0.16],
        "Top": [0.01, 0.10, 0.11, 0.11],
    }
    centers = {
        "front": (0.045, 0.155),
        "top": (0.06, 0.105),
    }
    target_outlines = {
        "front": [0.01, 0.15, 0.14, 0.16],
        "top": [0.01, 0.10, 0.11, 0.11],
    }

    issues = solver._target_outline_size_issues(outlines, centers, target_outlines, 0.28)
    blocking = solver._blocking_target_outline_issues(issues)

    assert len(blocking) == 1
    assert blocking[0]["slot"] == "front"
    assert blocking[0]["dominant_direction"] == "too_small"
    assert solver._target_outline_scale_direction(blocking) == "too_small"


if __name__ == "__main__":
    test_iso_outline_mismatch_is_warning_only()
    test_primary_outline_too_small_requests_larger_scale()
