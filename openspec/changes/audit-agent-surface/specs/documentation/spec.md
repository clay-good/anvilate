# Documentation Specification (delta)

## ADDED Requirements

### Requirement: A newcomer reaches a first part from the README alone

The README SHALL get a new user from nothing to a checked, drawn, exported part in three
numbered steps (install, connect an agent, ask), state in one short section what comes
back and where it is written, and say plainly what Anvilate is not (a CAD system, a
certification). Everything else SHALL be reached from one index organised by task. A page
that describes behaviour the product no longer has SHALL be removed or corrected in the
change that removed the behaviour, and a gate SHALL fail on a docs page nothing links to.

#### Scenario: Three steps and a result

- **WHEN** a mechanical engineer who has never seen the project follows only the README
- **THEN** they have a part's picture and STEP file without opening another page

#### Scenario: No orphan pages

- **WHEN** a docs page is not reachable from the index
- **THEN** the docs gate fails naming it
