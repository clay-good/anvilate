# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: Every tool and command can return a result

The MCP tool catalog and the command line SHALL offer only operations that can return a
result on a default install. A tool whose only possible answer is that it did not run MUST
NOT be listed; the tier or capability it stood for SHALL be reported as not evaluated by the
operation a user does call. Two operations that write the same kind of output SHALL be one
operation. A diagnostic command SHALL exit successfully when nothing the user can change is
wrong, and SHALL name a capability that is not built as not shipped.

#### Scenario: A tier with no solver is reported, not offered

- **WHEN** an agent lists the tools on an install with no FEA solver
- **THEN** no FEA tool is listed, and a validation run says the FEA tier was not evaluated

#### Scenario: One command writes a part's files

- **WHEN** an engineer wants the STEP file of a checked part
- **THEN** the command that writes the evidence bundle and the DXF profile writes it too

#### Scenario: A healthy install is reported healthy

- **WHEN** `doctor` runs on an install where everything a user can supply is present
- **THEN** it exits 0 and lists the unbuilt solver as not shipped
