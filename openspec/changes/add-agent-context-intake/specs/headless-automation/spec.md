# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: File reading over MCP is confined to declared folders

The MCP server SHALL read files only inside context folders named when it starts, SHALL
refuse any path outside them (including through links), and SHALL treat those folders as
read-only. With no context folder named, the file-reading tools SHALL be refused with how
to enable them. File-reading tools SHALL return measured facts and never file contents,
SHALL bound the size of file they accept and of result they return, and SHALL complete
within the tool time limit or refuse, stating the file's size.

#### Scenario: A path outside the context folder

- **WHEN** an agent asks the server to read a file outside every declared context folder
- **THEN** the call is refused, naming the folders it may read

#### Scenario: Reading is not copying

- **WHEN** a proprietary STEP file is read
- **THEN** the result carries its measurements and names, and no part of the file's
  geometry data is returned or written elsewhere
