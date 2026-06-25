# LB26001-A-04-006 Reference Intent Proof v4.4

- Status: `plan_proof_pass_requires_locked_cad_run`
- PASS: `true`
- Release ready: `false`
- Drawing acceptance evidence: `false`
- API-only acceptance allowed: `false`
- UI screenshot acceptance required: `true`

## Coverage

- DisplayDim target count: `12`
- Required target keys present: `true`
- Right projected view target keys: `projection_view_width, projection_view_height, small_feature_location`
- Required callouts present: `true`
- Absence-checked callouts: `radius_callout, chamfer_callout`

## Checks

- `pass` `plan_file_exists`: reference intent plan artifact exists
- `pass` `plan_schema`: reference intent plan schema is v4.4
- `pass` `plan_base`: reference intent plan is for LB26001-A-04-006
- `pass` `source_reference_exists`: same-name source reference SLDDRW exists
- `pass` `reference_png_exists`: reference PNG used for visual value reading exists
- `pass` `required_dimension_keys`: 006 has exactly the required 12 reference-intent DisplayDim targets
- `pass` `required_dimension_fields`: every DisplayDim target has source_reference, target_view, expected_type, manufacturing flag, fallback policy, and evidence
- `pass` `displaydim_not_note_policy`: all 12 manufacturing targets must be real SolidWorks DisplayDim, not Note or generic AutoDimension acceptance
- `pass` `reference_values`: visual reference values cover total length/width/height, end offsets, hole stations, pitch, and right projection
- `pass` `target_views`: reference-intent targets are assigned to the correct front/top/right view
- `pass` `expected_dimension_types`: reference-intent targets use expected linear/diameter types
- `pass` `right_projected_view_dimensions`: right-side small projected view has width, height, and small-feature location targets
- `pass` `reference_callout_keys`: reference callouts cover M4-6H, surface finish, and radius/chamfer absence checks
- `pass` `reference_callout_fields`: every reference callout has source reference, target view, expected type, manufacturing flag, fallback policy, and evidence
- `pass` `thread_callout_policy`: M4-6H callout is required visual manufacturing evidence and cannot replace DisplayDim
- `pass` `surface_finish_policy`: 3.2 rest surface-finish note is required callout evidence but does not count as DisplayDim
- `pass` `radius_chamfer_absence_policy`: radius/chamfer are recorded as visually absent and must not be fabricated
- `pass` `api_and_ui_policy`: plan requires UI screenshot acceptance and forbids Note substitution
- `pass` `acceptance_trace_requirements`: plan requires selected entity, add method, before/after counts, target coverage, and post-layout persistence trace
- `pass` `contract_file_exists`: reference-intent execution contract exists
- `pass` `contract_schema`: execution contract schema is v4.4
- `pass` `contract_base`: execution contract is for LB26001-A-04-006
- `pass` `contract_lock_policy`: execution contract can only run through the CAD worker while holding the SolidWorks global lock
- `pass` `contract_operations`: execution contract has one locked worker operation for each required DisplayDim target
- `pass` `contract_operation_policy`: each contract operation keeps lock, entrypoint, no-Note, and no-generic-AutoDimension acceptance policy

## Blocking Issues

- None
