import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from app.workers.cad_job_worker import (
    _prepare_reference_intent_dimension_contract,
    _run_subprocess_streamed,
)
from app.services.dimension_planner import apply_reference_intent_dimension_targets, build_dimension_plan
from app.services.reference_intent_dimension_planner import build_reference_intent_dimension_plan


def test_cad_worker_prepares_006_reference_intent_plan_and_contract_without_com() -> None:
    with TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "run"
        packet_path = Path(tmp) / "lb26001_006_rerun_packet_v4_2.json"
        packet_path.write_text(
            json.dumps(
                {
                    "status": "blocked_by_solidworks_readiness",
                    "packet_build_ready": True,
                    "real_cad_allowed_now": False,
                    "current_006_ui_verdict": {
                        "comparison_image": "006_reference_vs_generated.png",
                        "failed_visual_checklist_items": ["view_layout", "display_dimensions"],
                        "latest_manual_findings": ["006 still fails UI screenshot comparison."],
                        "latest_manual_required_correction": "Repair 006 from UI screenshot evidence.",
                        "ui_screenshot_files": ["006_ui.png"],
                        "generated_png": "006_generated.png",
                        "reference_png": "006_reference.png",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        old_packet = os.environ.get("SWDS_LB26001_006_RERUN_PACKET_PATH")
        try:
            os.environ["SWDS_LB26001_006_RERUN_PACKET_PATH"] = str(packet_path)
            result = _prepare_reference_intent_dimension_contract(
                r"C:\sample\LB26001-A-04-006.SLDPRT",
                str(run_dir),
            )
        finally:
            if old_packet is None:
                os.environ.pop("SWDS_LB26001_006_RERUN_PACKET_PATH", None)
            else:
                os.environ["SWDS_LB26001_006_RERUN_PACKET_PATH"] = old_packet

        assert result["enabled"] is True
        assert result["status"] == "ready"
        assert result["requires_solidworks_lock"] is True
        assert result["ui_thread_may_execute"] is False
        assert result["allowed_entrypoint"] == "cad_job_worker"
        assert result["dimension_target_count"] == 12
        assert result["operation_count"] == 12
        plan_path = Path(result["plan_path"])
        contract_path = Path(result["contract_path"])
        ui_evidence = result["ui_correction_evidence"]
        ui_evidence_path = Path(ui_evidence["path"])
        assert plan_path.exists()
        assert contract_path.exists()
        assert ui_evidence_path.exists()
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        evidence = json.loads(ui_evidence_path.read_text(encoding="utf-8"))
        assert plan["acceptance_trace_requirements"]["final_stage_required"] == "post_layout_final"
        assert plan["acceptance_trace_requirements"]["generic_autodimension_acceptance_allowed"] is False
        assert contract["acceptance_trace_requirements"]["all_dimension_targets_must_persist_after_reopen"] is True
        first_operation = contract["operations"][0]
        assert first_operation["expected_add_method"]
        assert "persisted_after_reopen" in first_operation["trace_required_fields"]
        assert first_operation["functional_role"]
        assert first_operation["placement_lane"]["readability_required"] is True
        assert first_operation["prune_protection_policy"]["protected"] is True
        assert ui_evidence["status"] == "ready"
        assert ui_evidence["failed_visual_check_count"] == 2
        assert ui_evidence["comparison_image"] == "006_reference_vs_generated.png"
        assert evidence["current_006_ui_verdict"]["latest_manual_required_correction"] == (
            "Repair 006 from UI screenshot evidence."
        )


def test_006_reference_intent_plan_uses_right_side_callout_and_projection_quota() -> None:
    reference_profile = {
        "source_reference": r"C:\refs\LB26001-A-04-006.SLDDRW",
        "display_dim_count": 12,
    }
    intent_plan = build_reference_intent_dimension_plan(
        "LB26001-A-04-006",
        reference_profile=reference_profile,
    )
    targets = {item["key"]: item for item in intent_plan["dimensions"]}

    assert targets["overall_width"]["preferred_side"] == "right"
    assert targets["hole_y_location"]["preferred_side"] == "callout_right"
    assert targets["hole_diameter"]["expected_add_method"] == "AddDiameterDimension2"
    assert targets["hole_pitch"]["expected_add_method"] == "AddHorizontalDimension2"
    assert targets["projection_view_height"]["expected_add_method"] == "AddVerticalDimension2"
    assert targets["hole_pitch"]["target_key"] == "hole_pitch"
    assert targets["hole_pitch"]["generic_autodimension_acceptance_allowed"] is False
    assert "selected_entity" in targets["hole_pitch"]["trace_required_fields"]
    assert targets["hole_pitch"]["acceptance_trace"]["must_record_add_method"] == "AddHorizontalDimension2"
    assert targets["hole_pitch"]["reading_group"] == "03_hole_locations"
    assert targets["hole_pitch"]["placement_lane"]["lane_family"] == "outside_top"
    assert targets["hole_pitch"]["prune_protection_policy"]["delete_only_if_target_covered_elsewhere"] is True
    assert all(item["avoid_generic_model_annotation"] for item in targets.values())

    plan = build_dimension_plan(
        part_class="long_thin",
        reference_dimension_profile={"display_dim_count": 12},
        blueprint_context={"view_slots": ["front", "top", "right", "iso"]},
    )
    plan = apply_reference_intent_dimension_targets(
        plan,
        base="LB26001-A-04-006",
        reference_profile=reference_profile,
    )

    assert plan.view_dimension_quotas == {"front": 3, "top": 6, "right": 3}
    assert len(plan.dimension_targets) == 12
    blueprint_targets = {item["key"]: item for item in plan.dimension_targets}
    assert blueprint_targets["hole_diameter"]["expected_add_method"] == "AddDiameterDimension2"
    assert "persisted_after_reopen" in blueprint_targets["hole_diameter"]["trace_required_fields"]
    assert blueprint_targets["hole_diameter"]["allowed_witness_entity"]["preferred"][0] == "circular_edges"
    assert blueprint_targets["projection_view_height"]["placement_lane"]["side"] == "right"


def test_cad_worker_skips_reference_intent_contract_for_other_bases() -> None:
    with TemporaryDirectory() as tmp:
        result = _prepare_reference_intent_dimension_contract(
            r"C:\sample\LB26001-A-04-007.SLDPRT",
            tmp,
        )

        assert result == {
            "enabled": False,
            "status": "not_required",
            "base": "LB26001-A-04-007",
        }


def test_cad_worker_streamed_subprocess_captures_output_without_com() -> None:
    with TemporaryDirectory() as tmp:
        result = _run_subprocess_streamed(
            [sys.executable, "-X", "utf8", "-c", "print('stream-ok', flush=True)"],
            cwd=tmp,
            env=os.environ.copy(),
            timeout_s=5,
            job_id="stream_unit",
        )

        assert result["timeout"] is False
        assert result["returncode"] == 0
        assert result["lines"] == 1
        assert result["subprocess_tail"] == ["stream-ok"]


def test_cad_worker_streamed_subprocess_cleans_orphan_child_without_com() -> None:
    if not sys.platform.startswith("win"):
        return
    code = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-X', 'utf8', '-c', 'import time; time.sleep(30)'])\n"
        "print('spawned-child', flush=True)\n"
    )
    with TemporaryDirectory() as tmp:
        result = _run_subprocess_streamed(
            [sys.executable, "-X", "utf8", "-c", code],
            cwd=tmp,
            env=os.environ.copy(),
            timeout_s=5,
            job_id="orphan_unit",
        )

        assert result["timeout"] is False
        assert result["returncode"] == 0
        assert result["lines"] == 1
        assert result["subprocess_tail"] == ["spawned-child"]
        cleanup = result.get("orphan_descendant_cleanup") or []
        assert cleanup
        assert any(item.get("stopped") is True for item in cleanup)
        assert not any(str(item.get("name", "")).lower() == "sldworks.exe" for item in cleanup)


if __name__ == "__main__":
    test_cad_worker_prepares_006_reference_intent_plan_and_contract_without_com()
    test_006_reference_intent_plan_uses_right_side_callout_and_projection_quota()
    test_cad_worker_skips_reference_intent_contract_for_other_bases()
    test_cad_worker_streamed_subprocess_captures_output_without_com()
    test_cad_worker_streamed_subprocess_cleans_orphan_child_without_com()
    print("OK test_v4_2_reference_intent_dimension_worker")
