# sw_drawing_studio v4.2 Product Goal

Status: WARNING. The project has not reached release conditions.

v4.2 prioritizes three gates before any broader real-CAD stage:

1. SolidWorks exclusive session control.
2. Reference-intent drawing for `LB26001-A-04-006`.
3. Application UI screenshot acceptance.

## Current Drawing Scope

The user-requested reference drawings are:

- `LB26001-A-04-006.SLDDRW`
- `LB26001-A-04-007.SLDDRW`
- `LB26001-A-04-008.SLDDRW`
- `LB26001-A-04-009.SLDDRW`
- `LB26001-A-04-015.SLDDRW`
- `LB26001-A-04-022.SLDDRW`

All six are learning/reference samples, but `006` is the required first acceptance target. Do not expand acceptance to `007/008/009/015/022` until `006` passes the application Drawing Review UI screenshot judgement.

## UI Screenshot Rule

API metrics, strict style reports, DisplayDim counts, and reference comparison scores are supporting evidence only.

A drawing is not accepted unless:

- The generated drawing is shown in the application Drawing Review UI.
- A screenshot artifact is written under `drw_output/ui_acceptance/`.
- A manual or visual judgement artifact records accepted UI screenshot evidence.
- `vision_qc_v6` and `reference_compare_v4` consume that UI judgement.

If API evidence is good but the UI screenshot judgement fails, the drawing status is `need_review`.

## 006 Reference-Intent Dimension Rule

`LB26001-A-04-006` must stop relying on generic AutoDimension output as the final drawing style.

The 006 plan must include real DisplayDim targets for:

- Overall envelope: `overall_length`, `overall_width`, `overall_height`
- End offsets: `left_end_offset`, `right_end_offset`
- Hole group: `hole_diameter`, `hole_x_location`, `hole_y_location`, `hole_pitch`
- Small projected view: `projection_view_width`, `projection_view_height`, `small_feature_location`
- Optional proven features: `radius`, `chamfer`, `thread`

Every dimension target must record:

- `source_reference`
- `target_view`
- `expected_type`
- `fallback_policy`

Notes, OCR text, and sidecar text must not replace real SolidWorks DisplayDim objects.

## SolidWorks Boundary

No UI-thread SolidWorks COM access is allowed.

Any real SolidWorks operation must go through the global lock and worker runtime. If the lock is unavailable, return `blocked_by_solidworks_lock` with owner and fix suggestion.

The current offline artifacts are:

- `drw_output/reference_intent_dimension_plan_006.json`
- `drw_output/reference_intent_dimension_contract_006.json`
- `drw_output/reference_intent_worker_probe_006_20260623/summary.json`
- `drw_output/ui_acceptance/LB26001_ref6_visual_review_manual_20260623/manual_visual_judgement.json`
- `drw_output/diagnostics/unguarded_solidworks_entrypoints.json`
- `drw_output/staged_validation/LB26001_006_pid_cache_lock_release_20260623/summary.json`
- `drw_output/staged_validation/LB26001_006_pid_cache_lock_release_20260623/01_LB26001-A-04-006/cad_smoke.json`
- `drw_output/staged_validation/LB26001_006_inprocess_generator_collect_20260623/summary.json`
- `drw_output/runs/e010a07aecb5/`
- `drw_output/ui_acceptance/LB26001_006_inprocess_generator_collect_visual_review_20260623/drawing_visual_review_report.json`
- `drw_output/ui_acceptance/LB26001_006_inprocess_generator_collect_visual_review_20260623/manual_visual_judgement.json`
- `drw_output/ui_acceptance/LB26001_006_inprocess_generator_collect_visual_review_20260623/vision_qc_v6_with_ui_review.json`
- `drw_output/ui_acceptance/LB26001_006_inprocess_generator_collect_visual_review_20260623/reference_compare_v4_with_ui_review.json`

`app/services/solidworks_entrypoint_scanner.py` is the service-level source scanner for SolidWorks COM entrypoints. A warning scan result is a blocker for broad real-CAD validation.

Latest 006 real-CAD attempt status: `need_review`, `deliverable_count=0`. The locked worker now produces fresh `SLDDRW/PDF/DXF/PNG` in `drw_output/runs/e010a07aecb5/`, and structured checks report `cad_pass=true`, `dimension_pass=true`, `reference_pass=true`, `reference_style_pass=true`, and `DisplayDim=12`. The application Drawing Review UI screenshot was captured, but manual visual judgement is still `FAIL`; `vision_qc_v6_with_ui_review.json` records `manual_review_status=fail`, and `reference_compare_v4_with_ui_review.json` remains blocked by `ui_screenshot_visual_acceptance_not_passed`. API and style results remain supporting evidence only.

## Next Sequence

1. Keep production SolidWorks COM entrypoints at `unguarded_or_unknown_count=0`; external sidecars and manual validation tools must still be invoked only by a lock-owning worker/runner.
2. Correct the 006 visible dimension/callout layout against the same-name reference, especially the tilted dense callout stack and the right-side small feature/projection dimension group.
3. Rerun the locked 006 CAD worker and regenerate fresh `SLDDRW/PDF/DXF/PNG`.
4. Run dimension validation, reference comparison, v6 visual QC, and v4 strict comparison.
5. Open the result in the application Drawing Review UI, capture screenshot evidence, and write a manual visual judgement.
6. Only after 006 is visually accepted, repeat the same pattern for `007/008/009/015/022`.
