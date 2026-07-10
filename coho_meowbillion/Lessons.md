# Lessons

## 2026-07-09 - Coho baseline

- Issue: Project work had accumulated many implementation decisions without a single local baseline.
- Cause: Work proceeded task-by-task before Coho was activated.
- Fix: Created Coho documentation structure for product, technical design, milestones, lessons, and reusable knowledge.
- Prevention: Before project-related changes under Coho, read the relevant Coho docs and update them when behavior, data model, scope, or test commitments change.
- Affected docs: PRD.md, TechDesign.md, Milestones.md, knowledge.md

## 2026-07-09 - Travel refund sign handling

- Issue: Travel report showed booking and refund transactions as positive spend.
- Cause: The report used `abs(ipay)`, which erased inflow/refund sign.
- Fix: Travel report now converts signed payment into net spend, so refunds reduce trip/category totals.
- Prevention: Add regression tests for sign-sensitive reporting whenever amount logic changes.
- Affected docs: PRD.md, TechDesign.md, Milestones.md

## 2026-07-09 - Reviewed assignment lock

- Issue: Trip/Property assignment could be changed on reviewed transactions.
- Cause: Assignment UI and endpoint did not fully apply the reviewed-lock rule.
- Fix: Disable assignment controls for reviewed transactions and reject assignment-only updates server-side.
- Prevention: Any new editable transaction field must explicitly decide how reviewed lock applies.
- Affected docs: PRD.md, TechDesign.md, Milestones.md
