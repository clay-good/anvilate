# Tasks: Trim the tool set and the command set

Each task waits on the owner's approval of its row in `proposal.md`.

## 1. Tools

- [ ] 1.1 Remove `run_fea_validation`; `run_validation` keeps saying the FEA tier did not run
      — held by the owner, 2026-10-10: it is the only tool the MCP Tasks transport serves, so
      removing it orphans that transport. It stays until a solver or another long-running
      tool settles what the transport is for
- [ ] 1.2 Mark `compile_spec` as going, then remove it one release later
- [ ] 1.3 Decide `measure_geometry` and `read_scorecard` from a measured run on both clients

## 2. Commands

- [x] 2.1 `export --artifact step|3mf`; `build` kept one release as the same thing
      (approved 2026-10-10; one spec, `--output`, the same writer and the same bytes)
- [x] 2.2 `doctor`: *not shipped* for an unbuilt capability, exit 0 when the rest is fine
      (approved 2026-10-10; CLI output 1.61.0)
- [ ] 2.3 `interfaces`: one `--accept KIND` flag (its own change)

## 3. After each

- [ ] 3.1 Catalog, doctor and command-table contracts versioned; instructions and skill updated
