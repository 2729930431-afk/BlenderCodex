# Executable promotion packet

An executable packet is JSON and contains:

- `kind: "executable"`
- `observed_problem`
- `owner_skill`
- `runtime_file`
- `runtime_action`
- `parameter_schema`
- `fixture`
- `acceptance_checks`
- `mcp_tool`
- `tests`

A policy packet uses `kind: "policy"`, `observed_problem`, and `future_rule`. Policy is the only category allowed to end as prose alone. A repeated scene operation is not promoted until its owning runtime and regression evidence exist.

`promote_learning.py` parses the runtime dispatch to verify the action, verifies the exact MCP tool registration, and requires referenced tests to mention the runtime action, MCP route, and every named acceptance check. It is a wiring gate; the packet is complete only after those referenced tests actually run successfully.
