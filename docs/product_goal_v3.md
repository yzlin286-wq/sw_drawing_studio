# Product Goal v3.0

Generated: 2026-06-21

## Vision

sw_drawing_studio should become a production-ready Windows desktop workbench for SolidWorks automatic 3D-to-2D drawing generation, drawing quality review, visual audit, diagnostics, and release validation.

The target user should be able to:

- Launch the application from an EXE.
- See SolidWorks, worker, visual model, license, and data health at a glance.
- Submit single-part and batch drawing jobs without freezing the UI.
- Observe job progress, heartbeats, warnings, recoveries, failures, and output paths.
- Inspect generated drawings and visual issues with evidence.
- Mark false positives and manual confirmations.
- Export diagnostics and visual audit reports.
- Trust that validation evidence matches real operation.

## Updated Delivery Target

Current status: **WARNING / NOT RELEASE READY**.

The v3.0 product is only acceptable when it is a Chinese-language Windows EXE for Chinese manufacturing teams:

- Final executable: `dist/sw_drawing_studio.exe`.
- Primary users: engineering, process planning, quality inspection, quotation, BOM, and production management staff in Chinese manufacturing companies.
- The application must connect to real SolidWorks and generate real drawings from `SLDPRT` / `SLDASM`; mock workers and safe smoke tests are only partial evidence.
- A fresh real CAD run must produce `SLDDRW`, `PDF`, `DXF`, `PNG`, `manifest.json`, `sw_session.json`, `job_event_log.jsonl`, `qc.json` / `warnings.json`, `vision_qc.json`, and `final_quality.json`.
- The UI must be Chinese. Main navigation must be: 仪表盘, 单件制图, 作业队列, 视觉审计, 图纸复核, 批量验证, 系统健康, 日志诊断, 设置.
- Generated 2D drawings must be validated for view completeness, true `DisplayDim` / CAD annotation quality, title block completeness, manufacturing / assembly / procurement usability, and visual readability.
- Generated drawings must be compared with same-name original 2D reference drawings under `3D转2D测试图纸` when available.
- Historical and new drawing outputs must be covered by Visual Audit, and every vision issue must include `bbox`, `source`, `confidence`, `evidence`, `fix_suggestion`, `auto_fix_available`, and `human_review_status`.
- Final release cannot be marked PASS until EXE UI robot, Chinese screenshot validation, Real CAD Smoke, 2D dimension validation, reference comparison, staged CAD batches, Visual Audit 100%, stability, diagnostics, final reports, and final EXE validation all pass.

## Product Principles

- The UI is an operator console, not a collection of backend buttons.
- Every long action is isolated in a worker process.
- Every job leaves a readable event trail.
- Every generated artifact is discoverable from a run manifest.
- Every visual issue is explainable and reviewable.
- Every release claim is backed by screenshots, JSON logs, Excel reports, diagnostics, and real CAD validation.

## v3.0 Scope

v3.0 focuses on productization:

- Dashboard
- Single Drawing
- Job Queue
- Visual Audit
- Drawing Review
- Batch Validation
- System Health
- Logs & Diagnostics
- Settings
- UI robot acceptance
- EXE smoke
- Real CAD validation sequence
- Historical visual audit coverage

## Non-Goals

- Do not rewrite the whole CAD pipeline before acceptance infrastructure is complete.
- Do not add isolated backend features that are not reachable from the UI.
- Do not treat import checks as product validation.
- Do not optimize EXE size before proving essential release workflows, unless the size itself blocks EXE operation.

## Phase Roadmap

1. Update goal and task documents to the stricter Chinese EXE / real CAD delivery target.
2. Convert the UI to Chinese and verify Microsoft YaHei / readable Chinese screenshots.
3. Align source and EXE UI robots with the Chinese 9-page navigation.
4. Run a real SolidWorks Reality Gate.
5. Run Real CAD Smoke through the UI/runtime, then validate 2D annotations and reference drawing comparison.
6. Execute 024/040, core_12, LB26001_36, medium_30, Historical Visual Audit 100%, full_129, stability gates, final EXE rebuild, final EXE robot, final real CAD job, and release judgment in order.

## Current Product Status

Current product status: WARNING / NOT RELEASE READY.

The project has a capable service layer and promising validation evidence, but it is not yet a complete user-ready desktop product because UI automation, screenshots, EXE workflows, full visual audit, and final staged validation remain incomplete.
