# LB26001-A-04-006 UI Defect Buckets v4.4

- Status: `blocked_by_solidworks_readiness`
- pass: `False`
- release_ready: `False`
- Active buckets: `dimension_visual_overdense, dimension_lane_wrong, note_missing_or_wrong, titlebar_incomplete, projection_view_style_mismatch`
- SolidWorks readiness: `blocked`

## Required Next Screenshot Checks

- `dimension_visual_overdense`: visible DisplayDim density matches the 12-target reference-intent set
- `dimension_lane_wrong`: dimension text/leaders stay in compact local reference lanes without cross-region clutter
- `note_missing_or_wrong`: manufacturing notes and roughness text match the reference note region
- `titlebar_incomplete`: title/data area uses only the compact reference-like fields
- `projection_view_style_mismatch`: front/top/right/iso view scale and composition match the reference
- `callout_missing`: M4-6H through-thread, 4-3.3 hole callout, Ra3.2 rest roughness, and radius/chamfer absence are explicitly checked

## Bucket Closure Contract

- `dimension_visual_overdense`: manual_visual_judgement must confirm the visible DisplayDim set is compact, readable, and matches the 12 reference-intent manufacturing targets.
- `dimension_lane_wrong`: manual_visual_judgement must confirm leaders and text stay in compact local top/bottom lanes with no cross-region clutter.
- `note_missing_or_wrong`: manual_visual_judgement must confirm manufacturing notes and roughness text match the reference note region.
- `titlebar_incomplete`: manual_visual_judgement must confirm the title/data area uses only the compact reference-like fields.
- `projection_view_style_mismatch`: manual_visual_judgement must confirm front/top/right/iso view scale and composition match the reference.
- `callout_missing`: manual_visual_judgement reference_callout_checklist must prove required callouts are present and radius/chamfer callouts are not fabricated.

## Bucket Evidence

### dimension_visual_overdense

- active: `True`
- severity: `major`
- blocks_006_acceptance: `True`
- fix_action: Keep only the reference-intent manufacturing DisplayDim set after physical DisplayDim de-duplication; reject extra generic AutoDimension survivors before export.

### dimension_lane_wrong

- active: `True`
- severity: `major`
- blocks_006_acceptance: `True`
- fix_action: Place long thin-part dimensions in compact local top/bottom lanes and block diagonal or cross-region leader geometry from surviving final arrange.

### note_missing_or_wrong

- active: `True`
- severity: `major`
- blocks_006_acceptance: `True`
- fix_action: Render the reference-style manufacturing notes/roughness text in the compact reference note region, not as generic default technical-requirement text.

### titlebar_incomplete

- active: `True`
- severity: `major`
- blocks_006_acceptance: `True`
- fix_action: Suppress default template artifacts and fill only the compact fields visible in the reference drawing.

### projection_view_style_mismatch

- active: `True`
- severity: `major`
- blocks_006_acceptance: `True`
- fix_action: Match the reference view family scale and projection composition, especially the small right projection and compact isometric view footprint.

### callout_missing

- active: `False`
- severity: `info`
- blocks_006_acceptance: `False`
- fix_action: On the next UI screenshot pass, explicitly check M4-6H through-thread, 4-3.3 hole callout, and Ra3.2 rest roughness callout.

## Next Allowed Action

Start SolidWorks manually, rerun readiness, then run exactly one locked 006 CAD worker.

## Do Not

- Do not run full_129.
- Do not run LB26001_36.
- Do not expand to 007/008/009/015/022 before 006 passes the application UI screenshot gate.
- Do not use API pass, DisplayDim pass, or reference JSON pass as final acceptance.
