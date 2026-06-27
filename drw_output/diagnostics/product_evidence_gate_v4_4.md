# Product Evidence Gate v4.4

- Status: `blocked_by_006_regeneration_evidence`
- PASS: `false`
- Release ready: `false`
- Do not run full_129: `true`
- Do not run LB26001_36: `true`
- Do not expand 007/008/009/015/022: `true`

## Allowed Actions

- `locked_006_cad_rerun_allowed_now`: `true`
- `006_application_ui_review_allowed_now`: `false`
- `expand_007_008_009_015_022_allowed`: `false`
- `requested_ref6_complete`: `false`
- `lb26001_36_allowed`: `false`
- `medium_30_allowed`: `false`
- `visual_audit_full_scope_allowed`: `false`
- `full_129_allowed`: `false`
- `release_allowed`: `false`

## Checks

- `pass` `solidworks_stability_gate_pass`: SolidWorks stability gate must pass with no warnings, except a single idle SolidWorks pre-lock process is allowed for the next locked 006 rerun.
- `pass` `ui_thread_direct_risk_zero`: UI/service direct SolidWorks, probe, QThreadPool, OCR/YOLO/batch, and blocking-risk buckets must remain zero.
- `pass` `solidworks_entrypoint_scan_report_pass`: Raw SolidWorks entrypoint scan must prove no UI/service direct COM, probe, QThreadPool, OCR/YOLO/batch, subprocess, or sleep risks.
- `pass` `solidworks_stability_entrypoint_snapshot_current`: SolidWorks stability gate must be generated no earlier than the raw entrypoint scan it summarizes.
- `pass` `solidworks_stability_readiness_snapshot_current`: SolidWorks stability and conflict evidence must be generated no earlier than the 006 readiness report they gate.
- `pass` `solidworks_lock_test_report_pass`: SolidWorks global-lock test report must pass every lock ownership/conflict check.
- `pass` `solidworks_conflict_report_ok`: Current conflict report must be OK, or show exactly one idle SolidWorks process waiting for a worker-owned global lock before the 006 rerun.
- `pass` `solidworks_readiness_for_006`: Readiness must allow exactly one locked 006 CAD rerun before any real CAD action.
- `pass` `solidworks_readiness_title_sampling_guard`: 006 readiness must include multi-sample SolidWorks title evidence and must not observe an unsaved document marker.
- `pass` `lb26001_006_rerun_packet_ready`: 006 rerun packet must have all offline defect-closure prerequisites and source signatures before a locked rerun.
- `pass` `lb26001_006_rerun_packet_readiness_state_current`: 006 rerun packet readiness state must match the current readiness result and be generated no earlier than that readiness result before real CAD can start.
- `pass` `lb26001_006_ui_defect_buckets_ready`: 006 UI screenshot defect buckets must be current and complete before the next locked 006 rerun.
- `pass` `reference_intent_006_proof_pass`: 006 reference-intent plan proof must pass while remaining supporting evidence only.
- `pass` `reference_intent_006_plan_complete`: 006 reference-intent dimension plan must directly define the required manufacturing DisplayDim targets and callout policy.
- `pass` `reference_intent_006_contract_locked_worker_only`: 006 reference-intent execution contract must require SolidWorks global lock, forbid UI-thread execution, and mirror the plan operation-by-operation.
- `fail` `regeneration_006_fresh_evidence_pass`: 006 must have a fresh run evidence gate PASS before UI screenshot review can close acceptance.
- `fail` `application_ui_006_acceptance_pass`: 006 must pass the application Drawing Review UI screenshot and manual visual checklist.
- `fail` `canonical_006_ui_visual_review_pass`: 006 canonical ui_visual_review.json must pass using application Drawing Review UI screenshot evidence.
- `fail` `006_evidence_chain_source_agreement`: 006 regeneration, acceptance proof, and canonical UI visual review must bind to the same run_dir, staged summary, and generated PNG.
- `fail` `006_acceptance_proof_ui_review_freshness`: 006 acceptance proof must be generated at or after the canonical application UI visual review.
- `fail` `requested_ref6_ui_status_pass`: All six requested reference samples must have application UI screenshot PASS plus per-drawing DrawingBlueprint, dimension, reference, vision, and UI visual-review evidence.
- `fail` `requested_ref6_status_snapshot_current`: Requested six-drawing status must be generated no earlier than the canonical 006 UI review and 006 UI defect-bucket evidence it depends on.
- `fail` `staged_batch_sequence_proof_pass`: Staged CAD validation must prove the ordered 024/040 -> core_12 -> LB26001_36 -> medium_30 sequence through locked JobRuntimeFacade and Q-process-backed workers plus application UI screenshot evidence before full-scope Visual Audit or full_129 is allowed.
- `fail` `final_release_artifacts_present`: Final release artifacts must exist before release/full_129 completion can be claimed.
- `fail` `exe_ui_and_stability_proof_pass`: Final EXE/UI evidence must include dist/sw_drawing_studio.exe, EXE-level UI robot PASS, 20-minute mock stability PASS, 2-hour Windows EXE UI stability PASS, and readable Chinese UI text spot-check PASS.
- `fail` `cad_smoke_dimension_reference_proof_pass`: Final CAD/dimension/reference smoke evidence must be semantic PASS: fresh CAD output through JobRuntimeFacade/qprocess, true DisplayDim validation, and reference comparison proof.
- `fail` `visual_audit_schema_proof_pass`: Final Visual Audit must have visual_audit_report_v3_0.xlsx plus raw and normalized issue schema proof plus the v4.4 schema-gap diagnostic; normalized proof alone does not replace raw historical issue compliance.

## Blocking Issues

- `regeneration_006_fresh_evidence_pass`
- `application_ui_006_acceptance_pass`
- `canonical_006_ui_visual_review_pass`
- `006_evidence_chain_source_agreement`
- `006_acceptance_proof_ui_review_freshness`
- `requested_ref6_ui_status_pass`
- `requested_ref6_status_snapshot_current`
- `staged_batch_sequence_proof_pass`
- `final_release_artifacts_present`
- `exe_ui_and_stability_proof_pass`
- `cad_smoke_dimension_reference_proof_pass`
- `visual_audit_schema_proof_pass`

## Next Required Action

Produce a fresh 006 run through the locked CAD worker and pass the regeneration evidence gate.
