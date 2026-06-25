# Visual Audit Schema Gap v4.4

- Status: `raw_issue_schema_noncompliant`
- PASS: `false`
- Release ready: `false`
- Normalized schema proof is supporting-only: `true`
- Normalized proof cannot replace raw historical issue compliance: `true`
- Raw noncompliant issues: `4330`
- Final Visual Audit report present: `false`
- Full-scope Visual Audit allowed now: `false`

## Raw Issue Schema

- Status: `fail`
- PASS: `false`
- Issue count: `4538`
- Noncompliant issue count: `4330`
- Failure buckets: `vision_issue_schema_incomplete`

## Checks

- `pass` `raw_issue_schema_report_present`: Raw historical visual issue schema validation report must exist.
- `fail` `raw_issue_schema_pass`: Raw historical visual issues must satisfy the final required issue schema.
- `pass` `normalized_issue_schema_report_present`: Normalized issue schema validation report must exist as supporting evidence.
- `pass` `normalized_issue_schema_pass`: Normalized issue schema proof must pass, but it remains supporting-only evidence.
- `fail` `final_visual_audit_report_present`: Final visual_audit_report_v3_0.xlsx must exist before release evidence can pass.
- `pass` `visual_audit_index_present`: Visual Audit index must exist as full-scope inventory evidence.
- `fail` `visual_audit_full_scope_allowed`: Full-scope Visual Audit must wait until the product gate allows it after the requested six drawings pass.

## Blocking Issues

- `raw_issue_schema_pass`
- `final_visual_audit_report_present`
- `visual_audit_full_scope_allowed`

## Next Required Action

Do not treat normalized issue schema output as release evidence. After 006 and the requested six drawings pass application UI screenshot review, rerun full-scope Visual Audit and raw schema validation so historical visual issues are regenerated or corrected with the required fields.
