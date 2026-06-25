# Product Evidence Gate v4.4

- Status: `blocked_by_solidworks_readiness`
- PASS: `false`
- Release ready: `false`
- Do not run full_129: `true`
- Do not run LB26001_36: `true`
- Do not expand 007/008/009/015/022: `true`

## Allowed Actions

- `locked_006_cad_rerun_allowed_now`: `false`
- `006_application_ui_review_allowed_now`: `false`
- `expand_007_008_009_015_022_allowed`: `false`
- `requested_ref6_complete`: `false`
- `lb26001_36_allowed`: `false`
- `medium_30_allowed`: `false`
- `visual_audit_full_scope_allowed`: `false`
- `full_129_allowed`: `false`
- `release_allowed`: `false`

## Checks

- `pass` `solidworks_stability_gate_pass`: SolidWorks stability gate must pass with no warnings.
- `pass` `ui_thread_direct_risk_zero`: UI/service direct SolidWorks, probe, QThreadPool, and blocking-risk buckets must remain zero.
- `pass` `solidworks_entrypoint_scan_report_pass`: Raw SolidWorks entrypoint scan must prove no UI/service direct COM, probe, QThreadPool, subprocess, or sleep risks.
- `pass` `solidworks_lock_test_report_pass`: SolidWorks global-lock test report must pass every lock ownership/conflict check.
- `pass` `solidworks_conflict_report_ok`: Current conflict report must be OK with no SolidWorks process, CAD/batch worker, waiting job, smoke leftover, or DialogGuard conflict.
- `fail` `solidworks_readiness_for_006`: Readiness must allow exactly one locked 006 CAD rerun before any real CAD action.
- `pass` `lb26001_006_rerun_packet_ready`: 006 rerun packet must have all offline defect-closure prerequisites and source signatures before a locked rerun.
- `pass` `lb26001_006_rerun_packet_readiness_state_current`: 006 rerun packet readiness state must match the current readiness result before real CAD can start.
- `pass` `reference_intent_006_proof_pass`: 006 reference-intent plan proof must pass while remaining supporting evidence only.
- `pass` `reference_intent_006_plan_complete`: 006 reference-intent dimension plan must directly define the required manufacturing DisplayDim targets and callout policy.
- `pass` `reference_intent_006_contract_locked_worker_only`: 006 reference-intent execution contract must require SolidWorks global lock and forbid UI-thread execution.
- `fail` `regeneration_006_fresh_evidence_pass`: 006 must have a fresh run evidence gate PASS before UI screenshot review can close acceptance.
- `fail` `application_ui_006_acceptance_pass`: 006 must pass the application Drawing Review UI screenshot and manual visual checklist.
- `fail` `canonical_006_ui_visual_review_pass`: 006 canonical ui_visual_review.json must pass using application Drawing Review UI screenshot evidence.
- `fail` `requested_ref6_ui_status_pass`: All six requested reference samples must have application UI screenshot PASS before expansion is complete.
- `fail` `final_release_artifacts_present`: Final release artifacts must exist before release/full_129 completion can be claimed.
- `fail` `exe_ui_and_stability_proof_pass`: Final EXE/UI evidence must include dist/sw_drawing_studio.exe, EXE-level UI robot PASS, 20-minute mock stability PASS, and 2-hour Windows EXE UI stability PASS.
- `fail` `visual_audit_schema_proof_pass`: Final Visual Audit must have visual_audit_report_v3_0.xlsx plus raw and normalized issue schema proof plus the v4.4 schema-gap diagnostic; normalized proof alone does not replace raw historical issue compliance.

## Blocking Issues

- `solidworks_readiness_for_006`
- `regeneration_006_fresh_evidence_pass`
- `application_ui_006_acceptance_pass`
- `canonical_006_ui_visual_review_pass`
- `requested_ref6_ui_status_pass`
- `final_release_artifacts_present`
- `exe_ui_and_stability_proof_pass`
- `visual_audit_schema_proof_pass`

## Next Required Action

Start SolidWorks manually, rerun readiness, then run exactly one locked 006 CAD worker.
