# v3.0 EXE Smoke Report

Generated: 2026-06-21 20:01:18
EXE: `dist_v3_smoke\sw_drawing_studio.exe`
Overall: PASS

## Checks

| Check | Result | Detail |
| --- | --- | --- |
| exe_exists | PASS | returncode=None |
| mock_worker | PASS | events=heartbeat,job_finished,job_started,progress |
| llm_pre_analyze_worker | PASS | events=heartbeat,job_finished,job_started,progress,warning |
| llm_tech_text_worker | PASS | events=heartbeat,job_finished,job_started,progress,warning |
| qc_action_worker | PASS | events=heartbeat,job_finished,job_started,progress |
| system_health_worker | PASS | events=heartbeat,job_finished,job_started,progress |
| pipeline_script_info | PASS | C:\Users\Vision\AppData\Local\Temp\_MEI243642\.trae\specs\enforce-drawing-quality\drw_quality_check.py |
| gui_alive | PASS | alive_after_5s=True |
| internal_ui_walkthrough | PASS | pages=9 min_png=5439770 |

## Remaining Gates

- Windows-level EXE click automation remains pending.
- Two-hour UI stability remains pending.
- Real SolidWorks staged validation remains pending.
- Historical visual audit 100 percent coverage remains pending.
