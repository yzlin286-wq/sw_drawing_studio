# UI Acceptance Criteria v3.0

Generated: 2026-06-21

## Scope

This document defines the UI acceptance gates for v3.0. Source-level Qt automation is useful
evidence, but final UI acceptance also requires Windows/EXE-level validation.

## Required Pages

The acceptance suite must cover these nine user-facing entries:

1. Dashboard
2. Single Drawing
3. Job Queue
4. Visual Audit
5. Drawing Review
6. Batch Validation
7. System Health
8. Logs & Diagnostics
9. Settings

## Screenshot Gates

- Each of the nine page screenshots must be larger than 50 KB.
- Drawing Review must be larger than 70 KB.
- Screenshots must be readable in Chinese and English mixed text.
- Screenshots must not show blank pages, tofu glyphs, major overlap, or repeated wrong content.
- Main navigation, active page state, and primary actions must be visible.

## Scenario Gates

### First Launch

- Launch the application.
- Wait for the main window.
- Capture Dashboard.
- Verify the window is nonblank and navigation is visible.

### Navigation

- Click every required page entry.
- Wait for the page to render.
- Capture a screenshot for each page.
- Verify page title and content are distinct.

### Job Queue

- Start a mock pass job.
- Start a mock timeout job.
- Retry the timeout job.
- Cancel a running mock job.
- Verify UI responsiveness and structured event logging.

### Visual Audit

- Scan historical outputs.
- Generate `drw_output/visual_audit_index.json`.
- Export an Excel report.
- Verify the table has rows and filters are operable.

### Drawing Review

- Load a run with visual issues.
- Select an issue.
- Show bbox overlay and evidence.
- Toggle layers.
- Mark false positive and confirmed issue.
- Persist `human_review.json`.

### System Health

- Refresh health checks.
- Show SolidWorks, Vision, Data, License, and UI-Worker groups.
- Each item must have pass, warning, or fail plus a message and fix suggestion.

### Logs And Diagnostics

- Select a run.
- Show manifest, logs, QC, vision, and session evidence when available.
- Generate a diagnostics zip within 30 seconds for a small run.
- The zip must contain manifest, logs, QC/vision data, health/version metadata, and relevant screenshots when available.

### Settings

- Show LLM, Vision, and SolidWorks/Add-in related configuration.
- Test connection must produce a clear pass, warning, or fail result.
- Missing API keys must warn without crashing.

## Current Evidence Levels

- `source_qt_ui_robot`: proves source-mode Qt widgets can be automated and rendered offscreen.
- `exe_smoke`: proves the bundled EXE launches and basic worker/resource paths function.
- `exe_ui_robot`: required final evidence for bundled UI operation.
- `long_stability`: required evidence for 20-minute mock and 2-hour UI stability.

## Final UI PASS

UI PASS requires all of the following:

- Source-level UI robot PASS.
- EXE-level UI robot PASS.
- 20-minute mock stability PASS.
- 2-hour UI stability PASS.
- No UI-thread direct call to SolidWorks COM, OCR, YOLO, PaddleOCR, long subprocess work, or blocking sleeps.
- All required screenshots and reports are archived under `drw_output/ui_acceptance/<timestamp>/`.
