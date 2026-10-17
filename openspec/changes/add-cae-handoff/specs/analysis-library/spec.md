# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Joint and fitting screens accept imported interface loads

Every joint and fitting screen (bolt group, lug, fitting, weld group, bearing) SHALL accept
its load from an imported interface load case as well as from a declared load. The screen
SHALL carry the import's provenance on its entry. A load imported in a coordinate system
the screen cannot resolve to its own axes SHALL be refused naming the system.

#### Scenario: A bolt group on solver loads

- **WHEN** a four-bolt fitting is screened on an imported interface load case
- **THEN** each bolt's shear and tension come from that case, and the entry names the
  file hash and case identity
