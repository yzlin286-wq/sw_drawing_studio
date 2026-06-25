# v3.0 EXE Stability Report

Generated: 2026-06-21 22:39:14
EXE: `dist_v3_smoke\sw_drawing_studio.exe`
Overall: PASS
Duration requested: 7200.0 s
Duration observed: 7203.5 s
Samples: 231
Screenshots: 13

## Checks
- duration_met: True
- process_alive_final: True
- samples_written: True
- sample_count: 231
- screenshots_pass: True
- full_cycle_required: True
- all_pages_visited: True
- page_counts: {'Dashboard': 204, 'Single Drawing': 204, 'Job Queue': 204, 'Visual Audit': 204, 'Drawing Review': 204, 'Batch Validation': 204, 'System Health': 204, 'Logs & Diagnostics': 203, 'Settings': 203}
- failure_count: 0

## Failures
- none

## Screenshots
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\001_elapsed_4s_01_dashboard.png` page=Dashboard size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\002_elapsed_607s_03_job_queue.png` page=Job Queue size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\003_elapsed_1208s_04_visual_audit.png` page=Visual Audit size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\004_elapsed_1810s_06_batch_validation.png` page=Batch Validation size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\005_elapsed_2412s_08_logs_diagnostics.png` page=Logs & Diagnostics size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\006_elapsed_3012s_07_system_health.png` page=System Health size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\007_elapsed_3615s_03_job_queue.png` page=Job Queue size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\008_elapsed_4217s_05_drawing_review.png` page=Drawing Review size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\009_elapsed_4819s_04_visual_audit.png` page=Visual Audit size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\010_elapsed_5421s_06_batch_validation.png` page=Batch Validation size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\011_elapsed_6024s_03_job_queue.png` page=Job Queue size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\012_elapsed_6626s_05_drawing_review.png` page=Drawing Review size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_2h_v3_retry1\screenshots\013_final.png` page=System Health size=8341592 pass=True

## Remaining Gates
- This validates EXE navigation stability; staged real CAD validation remains separate.
- Historical visual audit 100 percent coverage remains pending.
