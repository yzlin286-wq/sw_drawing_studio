# v3.0 EXE Stability Report

Generated: 2026-06-21 20:13:51
EXE: `dist_v3_smoke\sw_drawing_studio.exe`
Overall: PASS
Duration requested: 8.0 s
Duration observed: 8.95 s
Samples: 2
Screenshots: 2

## Checks
- duration_met: True
- process_alive_final: True
- samples_written: True
- sample_count: 2
- screenshots_pass: True
- full_cycle_required: False
- all_pages_visited: True
- page_counts: {'Dashboard': 1, 'Single Drawing': 1, 'Job Queue': 0, 'Visual Audit': 0, 'Drawing Review': 0, 'Batch Validation': 0, 'System Health': 0, 'Logs & Diagnostics': 0, 'Settings': 0}
- failure_count: 0

## Failures
- none

## Screenshots
- `drw_output\ui_acceptance\exe_stability_smoke_v3\screenshots\001_elapsed_4s_01_dashboard.png` page=Dashboard size=8341592 pass=True
- `drw_output\ui_acceptance\exe_stability_smoke_v3\screenshots\002_final.png` page=Single Drawing size=8341592 pass=True

## Remaining Gates
- This validates EXE navigation stability; staged real CAD validation remains separate.
- Historical visual audit 100 percent coverage remains pending.
