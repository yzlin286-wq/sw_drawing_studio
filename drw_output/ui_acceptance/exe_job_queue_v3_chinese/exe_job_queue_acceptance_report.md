# v3.0 EXE Job Queue Acceptance

Generated: 2026-06-21 23:49:37
EXE: `dist\sw_drawing_studio.exe`
Overall: PASS

## Checks

- normal_pass_completed: True
- timeout_failed: True
- retry_count_changed: True
- retry_final_failed: True
- cancelled: True
- skip_completed: True
- skip_event_logged: True
- open_run_dir_exercised: True
- screenshots_pass: True
- process_alive_before_cleanup: True
- failure_count: 0

## Jobs

- normal_pass: `{"job_id": "6b15d2d2", "part": "mock_normal_pass", "stage": "done", "progress": "100%", "status": "completed", "retry_count": "0", "duration": "1.0", "sw_pid": "28344", "last_event": "", "action": "", "values": ["6b15d2d2", "mock_normal_pass", "done", "100%", "completed", "0", "1.0", "28344"], "run_dir": "C:\\Users\\Vision\\Desktop\\SW 相关\\dist\\drw_output\\runs\\mock_20260621_234852_6b15d2d2"}`
- timeout: `{"job_id": "21986b32", "part": "mock_timeout", "stage": "mock_step_8/8", "progress": "100%", "status": "failed", "retry_count": "0", "duration": "2.0", "sw_pid": "31484", "last_event": "", "action": "", "values": ["21986b32", "mock_timeout", "mock_step_8/8", "100%", "failed", "0", "2.0", "31484"]}`
- retry_timeout: `{"started": {"job_id": "21986b32", "part": "mock_timeout", "stage": "mock_step_8/8", "progress": "100%", "status": "running", "retry_count": "1", "duration": "0", "sw_pid": "35800", "last_event": "", "action": "", "values": ["21986b32", "mock_timeout", "mock_step_8/8", "100%", "running", "1", "0", "35800"]}, "final": {"job_id": "21986b32", "part": "mock_timeout", "stage": "mock_step_8/8", "progress": "100%", "status": "failed", "retry_count": "1", "duration": "2.0", "sw_pid": "35800", "last_event": "", "action": "", "values": ["21986b32", "mock_timeout", "mock_step_8/8", "100%", "failed", "1", "2.0", "35800"]}}`
- cancel: `{"job_id": "5eeb74e0", "part": "mock_normal_pass", "stage": "mock_step_31/60", "progress": "52%", "status": "cancelled", "retry_count": "0", "duration": "3.0", "sw_pid": "7828", "last_event": "", "action": "", "values": ["5eeb74e0", "mock_normal_pass", "mock_step_31/60", "52%", "cancelled", "0", "3.0", "7828"]}`
- skip: `{"job_id": "b7d877a4", "part": "mock_normal_pass", "stage": "mock_step_32/60", "progress": "53%", "status": "completed", "retry_count": "0", "duration": "4.0", "sw_pid": "27172", "last_event": "", "action": "", "values": ["b7d877a4", "mock_normal_pass", "mock_step_32/60", "53%", "completed", "0", "4.0", "27172"], "run_dir": "C:\\Users\\Vision\\Desktop\\SW 相关\\dist\\drw_output\\runs\\mock_20260621_234932_b7d877a4", "event_log_has_skipped": true}`

## Screenshots

- `drw_output\ui_acceptance\exe_job_queue_v3_chinese\screenshots\01_job_queue_loaded.png` size=8518016 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3_chinese\screenshots\02_normal_pass_completed.png` size=8518016 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3_chinese\screenshots\03_timeout_failed_ui_responsive.png` size=8518016 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3_chinese\screenshots\04_timeout_retry_failed.png` size=8518016 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3_chinese\screenshots\05_cancelled.png` size=8518016 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3_chinese\screenshots\06_skipped.png` size=8518016 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3_chinese\screenshots\07_final.png` size=8518016 pass=True

## Remaining Gates

- Historical visual audit 100 percent coverage remains pending.
- v3.0 staged real CAD validation remains pending.
- Final dist/sw_drawing_studio.exe remains pending.
- Final release_log_v3_0.md remains pending.
