# Learning Packet

Use this template only for policy, model-local, or do-not-store lessons from a manual model edit or repair trace. A repeated geometry, validation, scene-mutation, or orchestration workflow is executable: use `../../workflow-learning/references/executor-promotion-schema.md` instead and promote it into an owning runtime, MCP action, fixture, and regression tests.

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

- Use the workflow-learning executable packet when the correction describes an operation that can be repeated. Prose-only storage is not completion for executable lessons.
- Use `global_default` when the edit fixes a repeated or clearly general modeling failure.
- Use `scoped_skill_rule` when the edit records a verified preference or past failure that should affect future behavior only under clear trigger conditions.
- Use `model_local` when the edit is only meaningful for the current `.blend`.
- Use `do_not_store` for exploratory changes, temporary debugging, secrets, unverified guesses, or accidental edits.

## Minimal Policy Example

```yaml
artifact: D:/project/house.blend
user_edit: Requested that intentionally open pavilions never receive automatic gable closure panels.
observed_problem: A general house rule was being applied to a building type that intentionally exposes its roof structure.
inferred_reason: Pavilion classification changes the design constraint; there is no deterministic geometry operation to promote from this preference alone.
future_rule: Do not add gable closure panels to a structure classified as an open pavilion unless the user explicitly requests them.
scope: scoped_skill_rule
storage_target: blendercodex/references/modeling-standards.md
validation: Assert the pavilion exception is routed as policy and does not claim a runtime action.
limits: This exception does not apply to enclosed houses with accidentally missing gable panels.
```
