# Staged Batch Sequence Gate v4.4

- Status: `pending`
- PASS: `false`
- Required sequence: `024_040 -> core_12 -> LB26001_36 -> medium_30`
- Observed sequence: `024_040 -> core_12 -> LB26001_36`
- Visual Audit allowed after medium_30: `false`
- full_129 allowed after Visual Audit: `false`

## Stages

- `024_040`: pass=`false`, status=`pass`, summary=`C:\Users\Vision\Desktop\SW 相关\drw_output\staged_validation\024_040\20260622_012550\summary.json`
  - Missing/failed: `solidworks_lock_owned, application_ui_screenshot_evidence, api_only_acceptance_disallowed`
- `core_12`: pass=`false`, status=`pass`, summary=`C:\Users\Vision\Desktop\SW 相关\drw_output\staged_validation\core_12\20260622_014907\summary.json`
  - Missing/failed: `solidworks_lock_owned, application_ui_screenshot_evidence, api_only_acceptance_disallowed`
- `LB26001_36`: pass=`false`, status=`pass_with_warning`, summary=`C:\Users\Vision\Desktop\SW 相关\drw_output\staged_validation\LB26001_36\20260622_035927\summary.json`
  - Missing/failed: `deliverable_target_met, solidworks_lock_owned, application_ui_screenshot_evidence, api_only_acceptance_disallowed`
- `medium_30`: pass=`false`, status=`None`, summary=``
  - Missing/failed: `summary_exists, summary_stage_matches, summary_pass, execution_completed, deliverable_target_met, solidworks_lock_owned, job_runtime_facade_proof, qprocess_worker_proof, application_ui_screenshot_evidence, api_only_acceptance_disallowed, artifact_contract_present, artifact_contract_pass`

## Blocking Issues

- `required_sequence_missing_or_out_of_order`
- `024_040_solidworks_lock_owned`
- `024_040_application_ui_screenshot_evidence`
- `024_040_api_only_acceptance_disallowed`
- `core_12_solidworks_lock_owned`
- `core_12_application_ui_screenshot_evidence`
- `core_12_api_only_acceptance_disallowed`
- `LB26001_36_deliverable_target_met`
- `LB26001_36_solidworks_lock_owned`
- `LB26001_36_application_ui_screenshot_evidence`
- `LB26001_36_api_only_acceptance_disallowed`
- `medium_30_summary_missing`

## Next Required Action

Refresh 024_040 staged evidence with current v4.4 UI screenshot and worker-contract proof: solidworks_lock_owned, application_ui_screenshot_evidence, api_only_acceptance_disallowed.
