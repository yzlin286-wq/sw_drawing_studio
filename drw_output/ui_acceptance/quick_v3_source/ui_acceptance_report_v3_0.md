# UI Acceptance Report v3.0

Generated: 2026-06-21 03:55:06
Mode: source_qt_ui_robot
Overall: WARNING

## Screenshots

| screenshot | size | unique colors | pass |
|---|---:|---:|---|
| `01_dashboard.png` | 14643 | 5 | FAIL |
| `02_single_drawing.png` | 12720 | 7 | FAIL |
| `03_job_queue.png` | 13860 | 5 | FAIL |
| `04_visual_audit.png` | 19789 | 16 | FAIL |
| `06_batch_validation.png` | 14170 | 10 | FAIL |
| `07_system_health.png` | 17054 | 16 | FAIL |
| `08_logs_diagnostics.png` | 21885 | 18 | FAIL |
| `03_job_queue.png` | 17509 | 10 | FAIL |
| `04_visual_audit.png` | 21040 | 17 | FAIL |
| `05_drawing_review.png` | 70892 | 15 | PASS |
| `08_logs_diagnostics.png` | 21690 | 17 | FAIL |
| `09_settings.png` | 7065 | 11 | FAIL |

## Job Operations

- normal_pass_completed: True
- timeout_failed: True
- retry_changed: True
- cancelled_or_failed_after_cancel: True
- normal_job: c790c199
- timeout_job: 794390f5
- cancel_job: 3eaf0205

## Artifacts

- ui_events: `drw_output\ui_acceptance\quick_v3_source\ui_events.jsonl`
- screenshots_dir: `drw_output\ui_acceptance\quick_v3_source\screenshots`
- visual_audit_index: `C:\Users\Vision\Desktop\SW 相关\drw_output\visual_audit_index.json`
- visual_audit_report: ``
- human_review: `drw_output\ui_acceptance\quick_v3_source\drawing_review_fixture\qc\human_review.json`
- diagnostics_zip: `C:\Users\Vision\Desktop\SW 相关\drw_output\diagnostics\diagnostics_a6d1ae861865.zip`
- settings_result: `warning_network_test_deferred`

## Remaining Gates

- This is source-level Qt automation, not Windows-level EXE click automation.
- 20-minute mock stability was not run by the quick suite.
- Real SolidWorks validation and historical visual audit coverage remain pending.
