# v3.0 EXE Job Queue Acceptance

Generated: 2026-06-21 23:08:52
EXE: `dist_v3_smoke\sw_drawing_studio.exe`
Overall: FAIL

## Checks

- normal_pass_completed: True
- timeout_failed: True
- retry_count_changed: True
- retry_final_failed: True
- cancelled: True
- skip_completed: True
- skip_event_logged: False
- open_run_dir_exercised: False
- screenshots_pass: True
- process_alive_before_cleanup: True
- failure_count: 0

## Jobs

- normal_pass: `{"job_id": "534a5997", "part": "mock_normal_pass", "stage": "done", "progress": "100%", "status": "completed", "retry_count": "0", "duration": "1.0", "sw_pid": "33276", "last_event": "", "action": "", "values": ["534a5997", "mock_normal_pass", "done", "100%", "completed", "0", "1.0", "33276"], "run_dir": ""}`
- timeout: `{"job_id": "38136956", "part": "mock_timeout", "stage": "mock_step_8/8", "progress": "100%", "status": "failed", "retry_count": "0", "duration": "1.0", "sw_pid": "27096", "last_event": "", "action": "", "values": ["38136956", "mock_timeout", "mock_step_8/8", "100%", "failed", "0", "1.0", "27096"]}`
- retry_timeout: `{"started": {"job_id": "38136956", "part": "mock_timeout", "stage": "mock_step_8/8", "progress": "100%", "status": "running", "retry_count": "1", "duration": "0", "sw_pid": "27816", "last_event": "", "action": "", "values": ["38136956", "mock_timeout", "mock_step_8/8", "100%", "running", "1", "0", "27816"]}, "final": {"job_id": "38136956", "part": "mock_timeout", "stage": "mock_step_8/8", "progress": "100%", "status": "failed", "retry_count": "1", "duration": "2.0", "sw_pid": "27816", "last_event": "", "action": "", "values": ["38136956", "mock_timeout", "mock_step_8/8", "100%", "failed", "1", "2.0", "27816"]}}`
- cancel: `{"job_id": "75f7c939", "part": "mock_normal_pass", "stage": "mock_step_31/60", "progress": "52%", "status": "cancelled", "retry_count": "0", "duration": "3.0", "sw_pid": "37484", "last_event": "", "action": "", "values": ["75f7c939", "mock_normal_pass", "mock_step_31/60", "52%", "cancelled", "0", "3.0", "37484"]}`
- skip: `{"job_id": "f10bf9a2", "part": "mock_normal_pass", "stage": "mock_step_33/60", "progress": "55%", "status": "completed", "retry_count": "0", "duration": "4.0", "sw_pid": "8140", "last_event": "", "action": "", "values": ["f10bf9a2", "mock_normal_pass", "mock_step_33/60", "55%", "completed", "0", "4.0", "8140"], "run_dir": "", "event_log_has_skipped": false}`

## Screenshots

- `drw_output\ui_acceptance\exe_job_queue_v3\screenshots\01_job_queue_loaded.png` size=8341592 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3\screenshots\02_normal_pass_completed.png` size=8341592 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3\screenshots\03_timeout_failed_ui_responsive.png` size=8341592 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3\screenshots\04_timeout_retry_failed.png` size=8341592 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3\screenshots\05_cancelled.png` size=8341592 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3\screenshots\06_skipped.png` size=8341592 pass=True
- `drw_output\ui_acceptance\exe_job_queue_v3\screenshots\07_final.png` size=8341592 pass=True

## Remaining Gates

- Historical visual audit 100 percent coverage remains pending.
- v3.0 staged real CAD validation remains pending.
- Final dist/sw_drawing_studio.exe remains pending.
- Final release_log_v3_0.md remains pending.
