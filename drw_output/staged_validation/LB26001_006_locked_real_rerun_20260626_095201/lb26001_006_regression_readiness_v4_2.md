# LB26001-A-04-006 Readiness Recovery Checklist v4.2

- Generated at: `2026-06-26 09:52:04`
- Status: `blocked`
- ready_to_start_locked_006_cad: `False`
- Manual recovery required: `True`
- Automatic restart allowed: `False`
- Blocking issue keys: `solidworks_unsaved_document_visible`

## Observed SolidWorks State

- process_present: `True`
- responding: `True`
- pid: `14144`
- main_window_title: `SOLIDWORKS Premium 2025 SP5.0 - [installed_validation_open_a109019f.SLDPRT *]`
- global_lock_present: `False`
- global_lock_stale: `False`

## SolidWorks Lock Details

- lock_file: `C:\Users\Vision\AppData\Local\sw_drawing_studio\solidworks_global_lock.json`
- conflict_reason: ``
- fix_suggestion: ``
- owner_project: ``
- owner_job_id: ``
- owner_run_id: ``
- owner_pid: ``
- owner_worker_pid: ``
- operation: ``
- heartbeat_age_s: ``

## Manual Recovery Steps

1. In SolidWorks, manually save or close the visible unsaved document before any automated CAD job starts.
2. Rerun this no-COM readiness audit after SolidWorks is responsive.
3. Only when readiness is ready, rerun the no-COM 006 rerun packet.
4. Then run exactly one locked LB26001-A-04-006 CAD regression through staged_cad_validation_v3.

## Do Not

- Do not kill or restart SLDWORKS.exe from automation while unsaved work may exist.
- Do not start 007/008/009/015/022 acceptance before 006 passes.
- Do not use API or file creation as a substitute for the Drawing Review UI screenshot judgement.

## Recovery Verification Command

- `python tools\validation\lb26001_006_regression_readiness_v4_2.py --out drw_output\diagnostics\lb26001_006_regression_readiness_v4_2.json --out-md drw_output\diagnostics\lb26001_006_regression_readiness_v4_2.md`

## Next Commands After Readiness Is Safe

- `python tools\validation\staged_cad_validation_v3.py --stage LB26001_006 --timeout-s 900 --max-rounds 1 --out-dir drw_output\staged_validation\LB26001_006_<timestamp>`
- `python tools\ui_robot\drawing_visual_review_suite.py --summary drw_output\staged_validation\LB26001_006_<timestamp>\summary.json --base LB26001-A-04-006 --out-dir drw_output\ui_acceptance\LB26001_006_<timestamp>_visual_review`
- `write manual_visual_judgement.json from the Drawing Review UI screenshot verdict`
- `python tools\validation\apply_ui_visual_review_v4.py --summary <summary.json> --ui-report <drawing_visual_review_report.json> --manual-review <manual_visual_judgement.json> --base LB26001-A-04-006`
- `python tools\validation\lb26001_acceptance_gate_v4_2.py --gate-summary <ui_visual_review_gate_summary.json>`

## Issues

- `solidworks_unsaved_document_visible` severity=`critical` fix=`Manually save or close the unsaved SolidWorks document before any CAD worker attempts the 006 rerun.`
- `previous_006_v6_ui_gate_not_pass` severity=`info` fix=`This is expected for the previous failed run; rerun closure after the next fresh 006 CAD/UI screenshot attempt.`
- `previous_006_v4_ui_gate_not_pass` severity=`info` fix=`This is expected for the previous failed run; next run must resolve strict v4 blockers.`
- `lb26001_expansion_currently_blocked` severity=`info` fix=`This is expected until 006 passes; do not run acceptance on 007/008/009/015/022.`
