---
name: workflow-learning
description: Promote verified Blender corrections and repeated workflows into owning executable modules, focused skills, fixtures, and regression tests. Use with BlenderCodex when the user asks to learn, remember a correction, make the plugin faster, turn experience into an executor, modularize skills, or ensure future tasks reuse proven code instead of documentation alone.
---

# Workflow Learning

Treat documentation as evidence, not as the completed promotion target.

## Promotion workflow

1. Capture the observed failure and verified user correction.
2. Classify the lesson:
   - executable workflow: repeated geometry, scene mutation, validation, or orchestration;
   - policy: a decision or safety constraint with no deterministic operation.
3. For an executable lesson, identify one owning focused skill, add or update its runtime action, define parameters, add a fixture and acceptance checks, expose a high-level MCP tool when it removes repeated generated code, and update the owning Skill route.
4. Run `scripts/promote_learning.py` against the learning packet. A document-only executable lesson must fail promotion.
5. Run pure unit tests, MCP schema/dispatch tests, and Blender background integration tests as applicable.
6. Update the plugin cachebuster only after the implementation stabilizes.

Use [references/executor-promotion-schema.md](references/executor-promotion-schema.md) for packet fields.
