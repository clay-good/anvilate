# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: Studies run over MCP as cancellable tasks

A declared study (sweep or search) SHALL be runnable through one MCP tool and one CLI
command. A study that can exceed the synchronous tool budget SHALL run as a task with
progress reported as evaluations, solver runs and elapsed time against their budgets. A
cancelled study SHALL return the record so far, labeled provisional, and leave no solver
process running. The tool's result SHALL be a bounded summary (the result, its governing
checks, the front when there is one, the coverage achieved), with the full record written
to the output folder and named by path.

#### Scenario: Cancelling a long search

- **WHEN** an agent cancels a reducer search after 12 of 40 solver runs
- **THEN** the task ends with a provisional result over the points evaluated so far, the
  record is written, and no solver process remains

#### Scenario: The CLI matches the tool

- **WHEN** `anvilate study reducer.study.yaml` runs at the shell
- **THEN** it records the same points and returns the same result the MCP tool does for the
  same study and seed
