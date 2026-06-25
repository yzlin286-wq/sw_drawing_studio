# sw_drawing_studio Agent Guide

## Project Goal

sw_drawing_studio is intended to become production-grade Windows desktop software for SolidWorks automatic drawing generation and visual quality control.

The product goal is not merely to keep service files in the repository. The product is only acceptable when real users can operate the desktop UI, launch long-running jobs safely, inspect generated drawings, review visual issues, export diagnostics, and verify release artifacts from screenshots and structured logs.

## Updated v3.0 Delivery Goal

The current v3.0 release target is a Chinese-language Windows EXE for Chinese manufacturing users:

- Final executable: `dist/sw_drawing_studio.exe`.
- The app must connect to real SolidWorks, not only mock workers.
- Real `SLDPRT` / `SLDASM` inputs must generate fresh `SLDDRW` / `PDF` / `DXF` / `PNG` artifacts through `JobRuntimeFacade` and QProcess workers.
- Generated 2D drawings must be validated for view completeness, true dimension annotation quality, title block and manufacturing requirements, visual quality, and usability for manufacturing / assembly / procurement.
- Generated drawings must be compared against original reference 2D drawings in `3D转2D测试图纸` when matching references exist.
- The final UI must be Chinese: main navigation, page titles, buttons, statuses, errors, evidence labels, and fix suggestions. Technical identifiers such as `run_id`, `PDF`, `DXF`, `SLDDRW`, and `DisplayDim` may remain English.
- Screenshots must prove Chinese text is readable with no tofu squares; prefer Microsoft YaHei / 微软雅黑 on Windows.
- Historical and newly generated drawing outputs must be covered by Visual Audit.
- Do not claim v3.0 PASS, release-ready, production-ready, or goal complete until every final gate in `docs/final_acceptance_criteria.md` is satisfied.

## v4.1 SolidWorks Exclusivity Goal

The current v4.1 priority is SolidWorks session stability before any further full-batch CAD validation.

- All real SolidWorks COM operations must be globally serialized through `app/services/solidworks_global_lock.py`.
- Two Codex projects or two workers must not control the same `SLDWORKS.exe` at the same time.
- Without the global lock, no code may call `GetActiveObject`, `Dispatch("SldWorks.Application")`, `OpenDoc6`, Add-in Ping, DialogGuard, `SaveAs`, or `CloseDoc`.
- `cad_job_worker.py` and `batch_job_worker.py` are the active CAD lock owners. Other probes must use a short probe lock or an existing CAD job lock.
- System Health may display lock/conflict state and bounded probes, but routine UI refresh must not open documents or mutate the SolidWorks session.
- Visual Audit and application screenshot review must operate on existing PDF/PNG evidence only; they must not trigger SolidWorks.
- If a lock conflict occurs, return `status=blocked_by_solidworks_lock`, include the owner and fix suggestion, and write conflict diagnostics.
- Automatic restart is forbidden unless the current lock owner is this job, no unsaved documents are at risk, the user allows restart, and diagnostics have been written.
- The requested drawings `LB26001-A-04-006/007/008/009/015/022` are not accepted by API metrics alone. Each regenerated drawing must be reviewed through the application UI screenshot workflow, with per-drawing screenshot evidence and manual/visual judgement.

## Development Principles

- The UI thread must never block on SolidWorks COM, OpenDoc6, AddDimension2, OCR, YOLO, PaddleOCR, batch validation, long subprocess calls, or `time.sleep`.
- All long-running work must start through `JobRuntimeFacade`, `JobRunner`, and QProcess-backed workers.
- Every worker must emit JSONL events on stdout, including `job_started`, `progress`, `heartbeat`, `warning`, `recovered`, `job_finished`, and `job_failed` when applicable.
- Any timeout, SolidWorks dialog, OpenDoc6 failure, OCR failure, model failure, or subprocess failure must not freeze the UI.
- Every failure must include a reason. Silent fallback is not allowed.
- Every run artifact must be written into `drw_output/runs/<run_id>/` and summarized by a manifest.
- Visual audit artifacts must be written into `drw_output/visual_audit/`.
- UI acceptance screenshots must be written into `drw_output/ui_acceptance/<timestamp>/`.
- Diagnostics bundles must be written into `drw_output/diagnostics/`.
- Do not pretend Note annotations are real SolidWorks `DisplayDim` objects.
- Do not promote `refdoc_correct` recovery to a hard failure.
- Fastener, spring, and purchased-part drawings may remain C-grade purchase or assembly drawings when that is correct for the part class.
- Never modify original test `SLDPRT` files. Only modify copied files under run directories such as `run_dir/input_work`.
- New UI pages must be scriptable by automation and must produce screenshots for acceptance.
- Do not lower QC thresholds to fabricate a pass.

## Acceptance Rules

- Import success is not functional success.
- File creation is not product completion.
- Service-layer completion is not UI completion.
- UI completion requires simulated human operation and screenshots.
- EXE completion requires smoke validation.
- A release candidate is not production-ready until the documented final acceptance criteria pass.
- Every task completion report must include modified files, key line references, import or AST checks, real or mock run commands, screenshots or JSON artifacts, PASS/WARNING/FAIL, remaining issues, and next recommendations.

## File Conventions

- Run artifacts: `drw_output/runs/<run_id>/`
- Visual audit artifacts: `drw_output/visual_audit/`
- UI screenshots: `drw_output/ui_acceptance/<timestamp>/`
- Diagnostics bundles: `drw_output/diagnostics/`
- Release evidence: `validation_log_v3_0.md`, `ui_acceptance_report_v3_0.md`, `release_log_v3_0.md`, and `visual_audit_report_v3_0.xlsx`
- Human review data: `human_review.json` inside the relevant run or review artifact directory.
- Worker event logs: `job_event_log.jsonl` inside the relevant run or UI acceptance artifact directory.

## Prohibited Work

- Do not call SolidWorks directly from UI code.
- Do not run OCR, YOLO, PaddleOCR, or large model inference directly in UI code.
- Do not delete historical output artifacts.
- Do not modify original test `SLDPRT` files.
- Do not reduce QC thresholds to make validation appear green.
- Do not claim v3.0 PASS before the final acceptance criteria pass.
- Do not mark service files as product-complete without UI, EXE, screenshot, and validation evidence.
