---
name: model-learning
description: Use with BlenderCodex when the user asks to learn from manual Blender/model edits, remember a correction, analyze why they changed a model, turn experience into an executor, promote a lesson into an owning focused skill, improve workflow speed, or make the plugin progressively smarter from feedback, including phrases like "学习", "记住我的修改", "把经验变成执行器", or "让插件越来越聪明".
---

# Model Learning

## Overview

Use this skill to turn verified user model edits into executable BlenderCodex capability. Documentation records evidence, but a repeatable modeling workflow is not learned until it has an owning focused skill, runtime action, parameter schema, fixture, and regression test.

## Coordination

- Also use `blendercodex` for live RPC inspection, scene summaries, save rules, and existing-model preservation.
- Also use `workflow-learning` to validate executable promotion packets and lifecycle requirements.
- Use `internal-structure` too when the learned edit concerns floors, slabs, stairs, openings, cores, or structural interiors.
- Inspect existing `SKILL.md` bodies and relevant references before adding a new rule so duplicate lessons are merged instead of repeated.

## Workflow

1. Gather evidence.
   - Capture the user's stated intent, screenshots, and any before/after descriptions.
   - Inspect the current live or saved scene through RPC when available: file path, touched objects, collections, custom properties, dimensions, materials, modifiers, and UV state.
   - Preserve user edits. Do not regenerate the model or create backup `.blend` files unless explicitly requested.

2. Build a learning packet.
   - Write the observed issue, the user correction, the inferred reason, the proposed future rule, and the confidence level.
   - Classify the lesson as `executable`, `policy`, `model_local`, or `do_not_store`.
   - For `executable`, use `../workflow-learning/references/executor-promotion-schema.md` and produce its JSON packet. Do not use the policy packet as a substitute.
   - Use `references/learning-packet.md` only for `policy`, `model_local`, or `do_not_store` evidence.
   - Separate hard evidence from inference. Say when a reason is inferred from geometry or screenshots rather than directly stated by the user.

3. Choose and implement the promotion target.
   - Put deterministic geometry, validation, and orchestration behavior in the closest owning runtime script.
   - Expose a focused MCP action when doing so removes repeated generated bpy code.
   - Add a representative fixture and regression tests that execute or exercise the promoted action.
   - Put routing instructions in the owning `SKILL.md` and evidence or non-executable limits in a focused reference.
   - Reject repeatable modeling workflows that are promoted only into prose.
   - Put model-local notes in scene or object custom properties only when the current `.blend` needs future edit context.
   - Do not create or update `.memory.md` as the default storage path. Use it only if the user explicitly asks for an audit log rather than a task rule.
   - Do not store secrets, temporary debugging paths, unverified guesses, or one-off artistic choices as global rules.

4. Validate the learning.
   - Add or update the smallest realistic acceptance check when the learning changes a reusable workflow.
   - Run `../workflow-learning/scripts/promote_learning.py` for every executable packet, then run the referenced runtime, MCP, fixture, and regression checks.
   - At minimum, verify frontmatter, runtime behavior, focused MCP routing, fixtures, and regression acceptance checks.
   - If the plugin source changes, update the local plugin cachebuster so future threads can load the new skill package.

5. Report back.
   - Summarize what was learned, why the user likely made the edit, where the knowledge was stored, and what validation ran.
   - Mention any limits, especially if the learning is intentionally narrow or awaits another example before promotion.

## Promotion Rules

- Promote a correction to a default when it fixes a visible class of modeling failure, aligns with established BlenderCodex rules, or the user explicitly says this should become a default.
- Keep a correction out of global defaults when it is only a narrow preference. If it still needs reuse, encode it as a scoped rule with clear trigger conditions and limits.
- Keep it local to the model when it depends on the exact scene, reference image, or user experiment.
- Ask a short clarifying question only when the same evidence supports incompatible future rules.

## Output Pattern

Use this concise pattern in the final response:

- Learned: the durable lesson.
- Why: the reason inferred from the user's edit and scene evidence.
- Stored in: files or scene metadata changed.
- Verified: checks performed.
