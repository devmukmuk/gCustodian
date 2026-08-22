# Epic SRV — MCP Server Wiring

Scope: `src/gcustodian/server.py`.

## Purpose

The MCP surface itself: registering each service's functions as `@mcp.tool()`
entries and running the server process.

## Current design

- One `MCPServer("gcustodian")` instance; every tool is a thin wrapper that
  calls straight into a `services/*` function — no logic lives here beyond
  argument passthrough and docstrings (which double as the tool descriptions
  Claude sees).
- `main()` calls `mcp.run()` over stdio; registered via
  `claude mcp add gcustodian -- python -m gcustodian.server`.

## Open work

- No resource/prompt definitions yet, only tools.
