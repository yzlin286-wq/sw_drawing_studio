# v3.0 EXE Reality Gate

Generated: 2026-06-22 00:33:12
EXE: `C:\Users\Vision\Desktop\SW 相关\dist\sw_drawing_studio.exe`
Status: **PASS**
Failure bucket: ``

## Command

```powershell
C:\Users\Vision\Desktop\SW 相关\dist\sw_drawing_studio.exe --worker system_health --job-id exe_reality_gate_v3_0 --ensure-solidworks --real-opendoc6-probe --probe-doc-path C:\Users\Vision\Desktop\SW 相关\drw_output\ui_acceptance\exe_reality_gate_v3_0\input_work\-AK-15-AC-27-1-V3-V02.SLDPRT
```

## Required Checks

| Key | Required | Status | Result |
| --- | --- | --- | --- |
| addin_ping | pass | pass | PASS |
| chinese_path_support | pass | pass | PASS |
| dialog_guard | pass | pass | PASS |
| macro_bas | pass | pass | PASS |
| opendoc6_test | pass | pass | PASS |
| output_dir | pass | pass | PASS |
| solidworks | pass | pass | PASS |
| sw_revision | pass | pass | PASS |
| sw_revision_supported | pass | pass | PASS |
| sw_running | pass | pass | PASS |
| template | pass | pass | PASS |
| batch_job_worker.py | recorded_pass_or_warning | pass | PASS |
| cad_job_worker.py | recorded_pass_or_warning | pass | PASS |
| cv2 | recorded_pass_or_warning | pass | PASS |
| document_manager_key | recorded_pass_or_warning | warning | PASS |
| drawing_review_worker.py | recorded_pass_or_warning | pass | PASS |
| fitz | recorded_pass_or_warning | pass | PASS |
| health_check_worker.py | recorded_pass_or_warning | pass | PASS |
| llm_action_worker.py | recorded_pass_or_warning | pass | PASS |
| macro_swp | recorded_pass_or_warning | warning | PASS |
| mock_long_job_worker.py | recorded_pass_or_warning | pass | PASS |
| mock_worker_smoke | recorded_pass_or_warning | pass | PASS |
| ocr | recorded_pass_or_warning | pass | PASS |
| opencv | recorded_pass_or_warning | pass | PASS |
| paddleocr | recorded_pass_or_warning | pass | PASS |
| qc_action_worker.py | recorded_pass_or_warning | pass | PASS |
| ultralytics | recorded_pass_or_warning | pass | PASS |
| ultralytics_import | recorded_pass_or_warning | pass | PASS |
| vision_audit_worker.py | recorded_pass_or_warning | pass | PASS |
| vision_model | recorded_pass_or_warning | warning | PASS |
| sw_pid | positive_integer | pass | PASS |

## Reasons

- No blocking reasons.

## Fix Suggestions

- No fix suggestions.
