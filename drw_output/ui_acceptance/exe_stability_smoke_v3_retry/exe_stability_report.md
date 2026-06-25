# v3.0 EXE Stability Report

Generated: 2026-06-21 20:38:33
EXE: `dist_v3_smoke\sw_drawing_studio.exe`
Overall: PASS
Duration requested: 12.0 s
Duration observed: 13.73 s
Samples: 3
Screenshots: 3

## Checks
- duration_met: True
- process_alive_final: True
- samples_written: True
- sample_count: 3
- screenshots_pass: True
- full_cycle_required: False
- all_pages_visited: True
- page_counts: {'Dashboard': 1, 'Single Drawing': 1, 'Job Queue': 1, 'Visual Audit': 0, 'Drawing Review': 0, 'Batch Validation': 0, 'System Health': 0, 'Logs & Diagnostics': 0, 'Settings': 0}
- failure_count: 0

## Failures
- none

## Screenshots
- `drw_output\ui_acceptance\exe_stability_smoke_v3_retry\screenshots\001_elapsed_4s_01_dashboard.png` page=Dashboard size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_smoke_v3_retry\screenshots\002_elapsed_12s_03_job_queue.png` page=Job Queue size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_smoke_v3_retry\screenshots\003_final.png` page=Job Queue size=8341592 pass=True

## Remaining Gates
- This validates EXE navigation stability; staged real CAD validation remains separate.
- Historical visual audit 100 percent coverage remains pending.
