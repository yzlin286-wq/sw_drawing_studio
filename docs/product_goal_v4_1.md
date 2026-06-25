# sw_drawing_studio v4.1 Product Goal

Status: WARNING / NOT RELEASE READY.

v4.1 prioritizes SolidWorks session stability and truthful visual acceptance before additional full-batch validation.

## Immediate Goal

Before any new real CAD batch, the product must prove that all real SolidWorks COM operations are globally serialized and that conflict diagnostics are visible in System Health.

Required evidence:

- `app/services/solidworks_global_lock.py` exists and can acquire, heartbeat, release, reject competing jobs, and release only stale locks.
- `app/services/solidworks_conflict_monitor.py` writes `drw_output/diagnostics/conflict_report.json`.
- `cad_job_worker.py` and `batch_job_worker.py` acquire the global lock before launching real CAD work, heartbeat while running, and release on success or failure.
- System Health shows the SolidWorks mutex state, owner, heartbeat age, SW process state, waiting jobs, stale-lock state, and fix suggestion.
- `tools/validation/scan_solidworks_entrypoints_v4_1.py` writes `drw_output/diagnostics/unguarded_solidworks_entrypoints.json`.

## Drawing Acceptance

The six user-requested reference drawings are:

- `LB26001-A-04-006.SLDDRW`
- `LB26001-A-04-007.SLDDRW`
- `LB26001-A-04-008.SLDDRW`
- `LB26001-A-04-009.SLDDRW`
- `LB26001-A-04-015.SLDDRW`
- `LB26001-A-04-022.SLDDRW`

API metrics, strict style reports, and DisplayDim counts are supporting evidence only. Final drawing correctness requires application UI screenshot review for every drawing. A drawing is not accepted unless its generated PNG/PDF is shown through the application review workflow and the per-drawing visual judgement passes.

## Recovery Sequence

After the lock and monitor evidence passes, resume real CAD in this order:

1. Global lock unit test.
2. Conflict monitor test.
3. System Health lock/conflict display.
4. Single CAD smoke: `LB26001-A-04-040`.
5. 006 reference-style smoke.
6. 006 dimension validation.
7. 006 reference comparison.
8. 024/040.
9. core_12.
10. LB26001_36.
11. medium_30.
12. full_129.

Do not run `full_129` directly.
