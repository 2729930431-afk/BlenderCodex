# Learning Packet

Use this template when a user asks BlenderCodex to learn from a manual model edit or a repair trace.

## Required Fields

- `artifact`: `.blend` path, object names, screenshot path, or other evidence source.
- `user_edit`: what the user changed or asked to preserve.
- `observed_problem`: what the previous model got wrong.
- `inferred_reason`: why the edit improves the asset. Mark as inference when the user did not state it directly.
- `future_rule`: the candidate rule for future generation or edits.
- `scope`: `global_default`, `scoped_skill_rule`, `model_local`, or `do_not_store`.
- `storage_target`: exact skill, reference file, or scene custom property.
- `validation`: the check that proves the learning was recorded or applied.
- `limits`: when not to apply this learning.

## Classification Guide

- Use `global_default` when the edit fixes a repeated or clearly general modeling failure.
- Use `scoped_skill_rule` when the edit records a verified preference or past failure that should affect future behavior only under clear trigger conditions.
- Use `model_local` when the edit is only meaningful for the current `.blend`.
- Use `do_not_store` for exploratory changes, temporary debugging, secrets, unverified guesses, or accidental edits.

## Minimal Example

```yaml
artifact: D:/project/house.blend
user_edit: Added triangular panels under both short sides of a gabled roof.
observed_problem: Roof slopes and tiles left a hollow triangular side gap.
inferred_reason: Side gable faces are part of the structural closure of a house roof.
future_rule: Gabled house roofs need short-side triangular gable panels aligned to wall top, eaves, ridge, and roof thickness.
scope: global_default
storage_target: blendercodex/SKILL.md and blendercodex/references/modeling-standards.md
validation: Grep for the new rule and inspect created panels for material and UVs.
limits: Do not apply to open pavilions, exposed-truss designs, or references that clearly show an open roof side.
```
