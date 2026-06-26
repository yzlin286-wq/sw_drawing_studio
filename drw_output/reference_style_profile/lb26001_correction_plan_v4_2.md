# LB26001 v4.2 UI-first correction plan

- Generated at: `2026-06-26 11:03:23`
- Status: `blocked_by_solidworks_readiness`
- Primary base: `LB26001-A-04-006`
- Readiness blockers: `solidworks_unsaved_document_visible`
- This is not acceptance evidence; application UI screenshot review remains the final gate.

## Preconditions

- SolidWorks must be responsive and unsaved-document risk must be cleared before real CAD rerun.
- Only the 006 pilot may run first, and it must run through JobRuntimeFacade/QProcess with the global SolidWorks lock.
- Original SLDPRT/SLDASM files must not be modified; use run_dir/input_work copies.
- Do not lower QC thresholds and do not count Note/OCR/QC sidecar text as DisplayDim.
- Every accepted drawing needs application Drawing Review UI screenshot evidence and a complete manual visual checklist.

## Correction order

| # | Base | Stage | Views | DisplayDim floor | UI status | Failed visual checks | Allowed now |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | LB26001-A-04-006 | pilot_006_first | 4 views; 4x2, 7x2 | 12 | manual_visual_checklist_failed | reference_match, view_layout, display_dimensions, dimension_readability, title_block, manufacturing_notes | no |
| 2 | LB26001-A-04-007 | gated_after_006_pass | 4 views; 4x2, 7x2 | 8 | visual_fail | reference_match, view_layout, display_dimensions, title_block, manufacturing_notes | no |
| 3 | LB26001-A-04-008 | gated_after_006_pass | 2 views; 4x1, 7x1 | 2 | visual_fail | reference_match, view_layout, display_dimensions, title_block | no |
| 4 | LB26001-A-04-009 | gated_after_006_pass | 3 views; 4x2, 7x1 | 4 | visual_fail | reference_match, view_layout, display_dimensions, title_block | no |
| 5 | LB26001-A-04-015 | gated_after_006_pass | 2 views; 4x1, 7x1 | 14 | visual_fail | reference_match, view_layout, display_dimensions, dimension_readability, title_block | no |
| 6 | LB26001-A-04-022 | gated_after_006_pass | 4 views; 4x2, 7x2 | 25 | visual_fail | reference_match, view_layout, display_dimensions, dimension_readability, title_block | no |

## 006 next action

- `reference_match`: Match the same-name SLDDRW reference composition before considering API metrics sufficient.
- `view_layout`: Use the learned normalized layout slots and avoid default title-block-driven sheet placement.
- `display_dimensions`: Create explicit reference-intent SolidWorks DisplayDim objects for visible manufacturing callouts.
- `dimension_readability`: Arrange dimensions into readable lanes and reject overlap or sparse generic AutoDimension output.
- `title_block`: Remove or suppress the oversized default title block/frame when it conflicts with the reference layout.
- `manufacturing_notes`: Preserve reference-style notes, roughness, warning text, and compact callout regions.

> Run no real CAD correction until readiness is clear. After that, rerun only LB26001-A-04-006 first and close it through strict v4/v6 plus Drawing Review UI screenshot manual judgement.
