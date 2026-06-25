from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.validation.lb26001_006_reference_intent_proof_v4_4 import (
    DEFAULT_CONTRACT,
    DEFAULT_PLAN,
    build_reference_intent_proof,
)


def _copy_json(source: Path, target: Path) -> dict:
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_006_reference_intent_proof_passes_current_artifacts() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = build_reference_intent_proof(
            plan_path=DEFAULT_PLAN,
            contract_path=DEFAULT_CONTRACT,
            out_json=root / "proof.json",
            out_md=root / "proof.md",
        )

        assert result["pass"] is True
        assert result["status"] == "plan_proof_pass_requires_locked_cad_run"
        assert result["release_ready"] is False
        assert result["report_is_drawing_acceptance_evidence"] is False
        assert result["dimension_summary"]["count"] == 12
        assert set(result["dimension_summary"]["right_projected_view_keys"]) == {
            "projection_view_width",
            "projection_view_height",
            "small_feature_location",
        }
        assert set(result["callout_summary"]["absence_checked_callouts"]) == {
            "radius_callout",
            "chamfer_callout",
        }
        assert (root / "proof.json").exists()
        assert (root / "proof.md").exists()


def test_006_reference_intent_proof_blocks_missing_right_projected_view_target() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan_path = root / "plan.json"
        contract_path = root / "contract.json"
        plan = _copy_json(DEFAULT_PLAN, plan_path)
        contract = _copy_json(DEFAULT_CONTRACT, contract_path)
        plan["dimensions"] = [
            item for item in plan["dimensions"]
            if item.get("key") != "projection_view_height"
        ]
        _write_json(plan_path, plan)
        _write_json(contract_path, contract)

        result = build_reference_intent_proof(
            plan_path=plan_path,
            contract_path=contract_path,
        )

        keys = set(result["blocking_issue_keys"])
        assert result["pass"] is False
        assert "required_dimension_keys" in keys
        assert "right_projected_view_dimensions" in keys
        assert "contract_operations" in keys


def test_006_reference_intent_proof_blocks_note_substitution_and_unlocked_contract() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan_path = root / "plan.json"
        contract_path = root / "contract.json"
        plan = _copy_json(DEFAULT_PLAN, plan_path)
        contract = _copy_json(DEFAULT_CONTRACT, contract_path)
        plan["allow_note_substitution"] = True
        plan["dimensions"][0]["create_as"] = "Note"
        plan["dimensions"][0]["forbid_note_substitution"] = False
        contract["requires_solidworks_lock"] = False
        contract["ui_thread_may_execute"] = True
        contract["allowed_entrypoint"] = "ui_thread"
        contract["direct_com_called"] = True
        contract["operations"][0]["requires_solidworks_lock"] = False
        contract["operations"][0]["forbid_note_substitution"] = False
        _write_json(plan_path, plan)
        _write_json(contract_path, contract)

        result = build_reference_intent_proof(
            plan_path=plan_path,
            contract_path=contract_path,
        )

        keys = set(result["blocking_issue_keys"])
        assert result["pass"] is False
        assert "displaydim_not_note_policy" in keys
        assert "api_and_ui_policy" in keys
        assert "contract_lock_policy" in keys
        assert "contract_operation_policy" in keys


def test_006_reference_intent_proof_blocks_missing_callout_evidence() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan_path = root / "plan.json"
        contract_path = root / "contract.json"
        plan = _copy_json(DEFAULT_PLAN, plan_path)
        _copy_json(DEFAULT_CONTRACT, contract_path)
        plan["reference_callouts"][0]["source_reference"] = ""
        plan["reference_callouts"][0]["source_reference_evidence"] = {}
        _write_json(plan_path, plan)

        result = build_reference_intent_proof(
            plan_path=plan_path,
            contract_path=contract_path,
        )

        keys = set(result["blocking_issue_keys"])
        assert result["pass"] is False
        assert "reference_callout_fields" in keys


def test_006_reference_intent_proof_tool_is_file_only() -> None:
    source = Path("tools/validation/lb26001_006_reference_intent_proof_v4_4.py").read_text(encoding="utf-8")
    forbidden = [
        "win32com",
        "pythoncom",
        "GetActiveObject",
        "Dispatch(",
        "OpenDoc6",
        "subprocess.run",
        "QProcess",
    ]
    for token in forbidden:
        assert token not in source


if __name__ == "__main__":
    test_006_reference_intent_proof_passes_current_artifacts()
    test_006_reference_intent_proof_blocks_missing_right_projected_view_target()
    test_006_reference_intent_proof_blocks_note_substitution_and_unlocked_contract()
    test_006_reference_intent_proof_blocks_missing_callout_evidence()
    test_006_reference_intent_proof_tool_is_file_only()
    print("PASS test_v4_4_lb26001_006_reference_intent_proof")
