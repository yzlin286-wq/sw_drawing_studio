# SolidWorks Conflict Policy

Status: active for v4.1, WARNING / NOT RELEASE READY.

## Lock Rule

Every real SolidWorks COM operation must hold the global lock at:

`C:\Users\Vision\AppData\Local\sw_drawing_studio\solidworks_global_lock.json`

The lock owner must include project, workspace, Codex session, owner PID, worker PID, job ID, run ID, operation, part path, SW PID when known, timestamps, TTL, restart permission, and status.

## Forbidden Without Lock

- `GetActiveObject`
- `Dispatch("SldWorks.Application")`
- `DispatchEx("SldWorks.Application")`
- `OpenDoc6`
- Add-in Ping
- DialogGuard
- `SaveAs`
- `CloseDoc`
- automatic SolidWorks restart

## Conflict Response

If the lock is unavailable, the worker or probe must return:

- `status=blocked_by_solidworks_lock`
- `failure_bucket=solidworks_lock_conflict` when applicable
- owner summary
- reason
- fix suggestion: wait for the current CAD job, or manually confirm stale-lock release

Silent fallback is not allowed.

## Conflict Levels

OK:

- one active owner or no active CAD operation;
- SW responding when present;
- no concurrent CAD workers.

WARNING:

- SW is running but no lock exists;
- stale lock is detected;
- smoke EXE leftovers are detected;
- another workspace is waiting for the lock.

FAIL:

- two active CAD workers;
- SW Responding is false;
- a project attempts COM under another owner's lock;
- DialogGuard is running without the owner lock;
- restart would affect unsaved or non-owned work.

## Visual Validation Boundary

Visual Audit, Drawing Review screenshot review, and manual per-drawing judgement must use existing PDF/PNG artifacts. They must not open SolidWorks or trigger `OpenDoc6`.

The six LB26001 reference drawings must be judged through application UI screenshots. API-only success never proves the drawing is correct.

## Safe Restart Boundary

`app/services/solidworks_safe_restart.py` is the restart preflight service. It must not restart SolidWorks unless all of these are true:

- the current job holds the global lock;
- the lock has `allow_restart_sw=true`;
- the user has confirmed restart;
- unsaved documents have been checked and none are present;
- conflict diagnostics and `restart_report.json` have been written.

The default mode is preflight/report only. Killing any non-owned SolidWorks process is forbidden.
