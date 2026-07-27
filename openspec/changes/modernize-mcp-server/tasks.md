# Tasks: MCP server on the 2026-07-28 protocol

## 1. Contracts

- [ ] 1.1 Publish the Spec IR and scorecard JSON Schemas as standalone versioned artifacts
- [ ] 1.2 Map pipeline operations to tool definitions with 2020-12 input/output schemas
- [ ] 1.3 Define the task-exposed operation set (FEA-class) vs. synchronous set (T0–T2)

## 2. Implementation (when the server is built)

- [ ] 2.1 Stateless server skeleton on the 2026-07-28 revision
- [ ] 2.2 structuredContent results + preview-image attachments
- [ ] 2.3 Tasks extension: handles, progress, cancellation with subprocess cleanup
- [ ] 2.4 Gate parity tests: sandbox/export gating identical to CLI paths

## 3. Release

- [ ] 3.1 Registry publication automation per release
- [ ] 3.2 Conformance run against the protocol test suite

## 4. Docs

- [ ] 4.1 Agent-integration guide: driving Anvilate from a coding agent, with the
      build-validate-read-scorecard loop
