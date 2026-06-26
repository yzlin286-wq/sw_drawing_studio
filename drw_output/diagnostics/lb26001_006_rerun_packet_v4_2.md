# LB26001-A-04-006 v4.2 rerun packet

- Generated at: `2026-06-26 16:48:05`
- Status: `blocked_by_solidworks_readiness`
- Real CAD allowed now: `False`
- Readiness blockers: `solidworks_unsaved_document_visible`
- Offline missing prerequisites: `none`
- This packet is not acceptance evidence; the application UI screenshot judgement remains the final gate.

## Current UI Verdict

- Status: `manual_visual_checklist_failed`
- Latest manual review: `C:\Users\Vision\Desktop\SW 相关\drw_output\ui_acceptance\LB26001_006_locked_real_rerun_20260625_041353_visual_review\manual_visual_judgement_template.json`
- Failed visual checks: `reference_match, view_layout, display_dimensions, dimension_readability, title_block, manufacturing_notes`
- Comparison image: `drw_output\ui_acceptance\LB26001_006_locked_real_rerun_20260625_041353_visual_review\comparison_images\01_LB26001-A-04-006_reference_vs_generated.png`
- Required correction: 

## Next Gates

1. `no_com_readiness_audit` - ready_to_start_locked_006_cad must be true before real CAD starts.
2. `locked_006_real_cad_rerun` - One 006-only JobRuntimeFacade.start_cad_job / QProcess CAD worker run, protected by the SolidWorks global lock, with a staged summary for the application UI screenshot review.
3. `dimension_validation` - Final persisted/exported real DisplayDim count must be >= 12; Note/OCR/sidecar text is not accepted.
4. `displaydim_lifecycle_audit` - pre-save, post-save/reopen, post-prune, post-layout, and final export must all preserve at least 12 real DisplayDim targets with no sidecar acceptance.
5. `reference_compare_v3` - Same-name reference drawing comparison must pass or pass_with_warning with no strict 006 blockers.
6. `reference_style` - Same-name reference style report must pass: view family, layout centers, DisplayDim floor, and no default template pollution.
7. `strict_reference_compare_v4` - View family/layout, target coverage, title block policy, and post_layout_final coverage must pass.
8. `vision_qc_v6` - vision_qc_v6 must pass with reference visual layout, readable dimensions, title block/template policy, and UI screenshot review requirements satisfied.
9. `drawing_review_application_ui_screenshot` - The Drawing Review application UI must show reference and generated drawing screenshots for visual judgement.
10. `manual_visual_judgement` - Every required checklist item must be true: reference_match, view_layout, display_dimensions, dimension_readability, title_block, manufacturing_notes.
11. `with_ui_closure` - vision_qc_v6_with_ui_review and reference_compare_v4_with_ui_review must both pass.
12. `lb26001_expansion_gate` - Only after 006 passes lifecycle/v3/v4/v6 and application UI screenshot gates may 007/008/009/015/022 proceed.

## Block Policy

Do not run real CAD while readiness or offline prerequisites are blocked.
