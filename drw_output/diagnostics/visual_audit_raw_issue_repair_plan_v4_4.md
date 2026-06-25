# Visual Audit Raw Issue Repair Plan v4.4

- Status: `repair_overlay_ready_requires_raw_backfill`
- PASS: `true`
- Release ready: `false`
- Historical artifacts modified: `false`
- Normalized proof is supporting-only: `true`
- Normalized proof cannot replace raw: `true`
- Raw issues: `7004`
- Raw noncompliant issues: `5931`
- Missing normalized replacements: `0`
- Lossy normalized issues needing human review: `5903`

## Top Raw Failure Sources

- `32` `drw_output/v22_validation/vision_qc_v4/LB26001-A-04-001_vision_qc_v4.json`
- `32` `drw_output/v22_validation/vision_qc_v4/LB26001-A-04-002_vision_qc_v4.json`
- `32` `drw_output/v22_validation/vision_qc_v4/LB26001-A-04-004_vision_qc_v4.json`
- `32` `drw_output/v22_validation/vision_qc_v4/LB26001-A-04-005_vision_qc_v4.json`
- `31` `drw_output/v22_validation/vision_qc_v4/-AK-15-AC-25-1-V3-V02_vision_qc_v4.json`
- `31` `drw_output/v22_validation/vision_qc_v4/-AK-15-AC-26-1-V3-V02_vision_qc_v4.json`
- `31` `drw_output/v22_validation/vision_qc_v4/-AK-15-AC-27-1-V3-V02_vision_qc_v4.json`
- `31` `drw_output/v22_validation/vision_qc_v4/-M3x8十字螺丝-1-V3-V02_vision_qc_v4.json`
- `31` `drw_output/v22_validation/vision_qc_v4/-弹簧压棒弹簧-1-V3-V02_vision_qc_v4.json`
- `31` `drw_output/v22_validation/vision_qc_v4/LB26001-A-04-003_vision_qc_v4.json`
- `31` `drw_output/v22_validation/vision_qc_v4/LB26001-A-04-007_vision_qc_v4.json`
- `31` `drw_output/v22_validation/vision_qc_v4/LB26001-A-04-009_vision_qc_v4.json`
- `31` `drw_output/v22_validation/vision_qc_v4/qc/vision_qc_v4.json`
- `25` `drw_output/ui_acceptance/LB26001_ref6_visual_review_manual_20260623/closed_loop_codex_structured_20260624/lb26001_acceptance_gate_v4_2.json`
- `15` `drw_output/ui_acceptance/LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623/closed_loop_strict_final_20260624/lb26001_acceptance_gate_v4_2.json`
- `11` `drw_output/ui_acceptance/LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623/closed_loop_current_v4_2_20260624/lb26001_acceptance_gate_v4_2.json`
- `11` `drw_output/ui_acceptance/LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623/closed_loop_strict_status_detail_20260624/lb26001_acceptance_gate_v4_2.json`
- `11` `drw_output/ui_acceptance/LB26001_006_explicit_displaydim_visible_entities_visual_review_20260623/closed_loop_template_pending_20260624/lb26001_acceptance_gate_v4_2.json`
- `10` `drw_output/runs/0918adfc033b/qc/YAC7-00526-000-JD2U_4_v5_qc.json`
- `10` `drw_output/runs/0bf957d377b5/qc/vision_qc_v2.json`

## Next Required Action

Normalized replacement coverage exists for every raw failure, but it is supporting-only evidence. After the requested UI-gated drawing sequence allows full Visual Audit, back up or regenerate the raw artifacts and rerun raw issue schema validation; records with lossy defaults require human review.
