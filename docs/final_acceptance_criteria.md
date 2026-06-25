# Final Acceptance Criteria for v3.0

Generated: 2026-06-21

## Product-Level PASS

v3.0 PASS requires every item below:

- Final executable is `dist/sw_drawing_studio.exe`.
- UI is fully Chinese for navigation, page titles, buttons, statuses, errors, evidence labels, and fix suggestions.
- Chinese screenshots show readable Microsoft YaHei / 微软雅黑 text with no tofu squares.
- EXE-level UI robot passes against the Chinese 9-page navigation: 仪表盘, 单件制图, 作业队列, 视觉审计, 图纸复核, 批量验证, 系统健康, 日志诊断, 设置.
- UI runs for 2 hours without freezing.
- Any single job timeout does not freeze the UI.
- All mock worker scenarios pass: pass, pass_with_warning, timeout, failed, recovered, and stuck_then_recovered.
- EXE smoke reports alive=True.
- The 9 Chinese main page screenshots are all larger than 50 KB.
- The 图纸复核 screenshot is larger than 70 KB.
- Real SolidWorks Reality Gate passes with `sw_pid`, revision, Add-in Ping, OpenDoc6 probe status, DialogGuard status, Document Manager status, templates/macros, output directory, and Chinese path support recorded.
- Real CAD Smoke runs through `JobRuntimeFacade.start_cad_job`, not direct UI COM calls.
- Real CAD Smoke generates a fresh `run_id` with artifact mtimes >= `job_started_at`.
- Real CAD Smoke outputs `SLDDRW`, `PDF`, `DXF`, `PNG`, `manifest.json`, `sw_session.json`, `job_event_log.jsonl`, `qc.json` / `warnings.json`, `vision_qc.json`, and `final_quality.json`.
- Smoke drawing 2D annotation validation passes with true source separation for `DisplayDim`, add-in `DisplayDim`, model associative dimensions, drawing sketch dimensions, Note annotations, standard-part notes, and human review.
- Smoke drawing has `dimension_validation_smoke.json`.
- Smoke drawing has `reference_compare_smoke.json` against the matching original 2D example drawing, or a clear no-reference reason.
- 024/040 either recovers automatically or reports clear failure buckets.
- `core_12` is deliverable.
- `LB26001_36` is 100 percent deliverable, or at least 97 percent with explainable failures.
- `medium_30` is 100 percent deliverable, or at least 97 percent with explainable failures.
- `full_129` completes with deliverable rate >= 98%, permanent hang count = 0, timeout recovery >= 90%, D-grade <= 2%, and failure buckets for every failure.
- Historical visual audit coverage is 100 percent for the defined scan scope.
- Every visual issue contains `key`, `severity`, `bbox`, `source`, `confidence`, `evidence`, `fix_suggestion`, `auto_fix_available`, and `human_review_status`.
- Every generated drawing has `dimension_validation`.
- Every generated drawing has `reference_compare` or a clear no-reference reason.
- False positives can be manually confirmed and persisted.
- Diagnostics zip can be generated.
- `visual_audit_report_v3_0.xlsx` can be generated.
- `reference_comparison_report_v3_0.xlsx` can be generated.
- `release_log_v3_0.md` can be generated.
- Original test `SLDPRT` files are not modified.
- QC thresholds are not lowered to fabricate a pass.
- No silent fallback exists in workers or validation paths.
- Note annotations are not counted as real SolidWorks `DisplayDim` objects.
- `refdoc_correct` remains a warning/recovery state, not a hard failure.

## WARNING

A result is WARNING when:

- A workflow works in source mode but not in EXE mode.
- A UI page exists but has no screenshot evidence.
- A service exists but is not reachable through the UI.
- The UI or robot still uses English main navigation.
- Real CAD works only as a single smoke and has not passed staged validation.
- 2D annotation validation or reference comparison exists only for a subset.
- A run is deliverable but has quality warnings such as missing titlebar fields, missing technical notes, missing datum, missing roughness, or incomplete section view strategy.
- Visual audit works on a subset but not on the full historical scope.
- Diagnostics exist but are incomplete.

## FAIL

A result is FAIL when:

- The UI freezes or blocks during long work.
- UI code directly calls SolidWorks COM, OCR, YOLO, PaddleOCR, or long subprocess work.
- A worker exits without a structured reason.
- Required artifacts are missing from `run_dir`.
- A page is blank, crashes, or cannot be automated.
- The EXE cannot launch or cannot locate bundled resources.
- The final UI is not Chinese, Chinese screenshots are unreadable, or screenshots show tofu squares.
- UI robot is source-level only and no EXE-level evidence exists.
- Real CAD is not run through `JobRuntimeFacade` / QProcess workers.
- Generated drawings lack fresh run artifacts or have mtimes older than the job start.
- 2D annotation validation counts Note text as true `DisplayDim`.
- Reference comparison is skipped without a reason.
- Original test CAD files are modified.
- QC thresholds are reduced to fabricate a pass.

## Required Final Artifacts

- `release_log_v3_0.md`
- `validation_log_v3_0.md`
- `ui_acceptance_report_v3_0.md`
- `exe_ui_robot_result_v3_0.json`
- `cad_smoke_v3_0.json`
- `dimension_validation_smoke.json`
- `reference_compare_smoke.json`
- `drw_output/reference_comparison_report_v3_0.xlsx`
- `drw_output/visual_audit_report_v3_0.xlsx`
- `drw_output/visual_audit_index.json`
- `drw_output/ui_acceptance/<timestamp>/screenshots/01_仪表盘.png`
- `drw_output/ui_acceptance/<timestamp>/screenshots/02_单件制图.png`
- `drw_output/ui_acceptance/<timestamp>/screenshots/03_作业队列.png`
- `drw_output/ui_acceptance/<timestamp>/screenshots/04_视觉审计.png`
- `drw_output/ui_acceptance/<timestamp>/screenshots/05_图纸复核.png`
- `drw_output/ui_acceptance/<timestamp>/screenshots/06_批量验证.png`
- `drw_output/ui_acceptance/<timestamp>/screenshots/07_系统健康.png`
- `drw_output/ui_acceptance/<timestamp>/screenshots/08_日志诊断.png`
- `drw_output/ui_acceptance/<timestamp>/screenshots/09_设置.png`
- `stability_20min_mock_v3_0.json`
- `stability_2h_ui_v3_0.json`
- A diagnostics sample zip under `drw_output/diagnostics/`
- `dist/sw_drawing_studio.exe`
- Manifest samples
- `human_review.json` sample
- `job_event_log.jsonl` sample
- `final_quality` samples
- `issue_schema_validation.json`
