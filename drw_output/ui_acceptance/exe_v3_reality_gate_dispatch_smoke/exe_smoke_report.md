# v3.0 EXE Smoke Report

Generated: 2026-06-22 00:35:04
EXE: `dist\sw_drawing_studio.exe`
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
| pipeline_script_info | PASS | C:\Users\Vision\AppData\Local\Temp\_MEI334562\.trae\specs\enforce-drawing-quality\drw_quality_check.py |
| gui_alive | PASS | alive_after_5s=True |
| internal_ui_walkthrough | PASS | pages=9 min_png=4808831 |

## Remaining Gates

- Windows-level EXE click automation remains pending.
- Two-hour UI stability remains pending.
- Real SolidWorks staged validation remains pending.
- Historical visual audit 100 percent coverage remains pending.
