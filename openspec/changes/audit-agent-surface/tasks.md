# Tasks: Audit the agent surface

Each audit task ends in a written finding list (kept in `docs/agent-surface-audit.md`) and the fixes
it justifies. A finding that needs a breaking change is proposed, not applied.

## 1. Inventory (no changes yet)

- [x] 1.1 Every MCP tool: purpose, inputs, result shape and size, time, which journeys use it
- [x] 1.2 Every CLI command and flag: purpose, default, overlap with another
- [x] 1.3 Every refusal message on both surfaces, collected into one reviewable list
      (`docs/api/refusal-messages.txt`, from `tools/audit/refusals.py`; finding 21)
- [ ] 1.4 Every docs page: who it is for, whether it is still true, what links to it
- [x] 1.5 Client limits table for Claude Code and Codex, each with source and date

## 2. Tool set

- [x] 2.1 Write the journeys and their maximum call counts
- [ ] 2.2 Propose the workflow-level tool set from the inventory and measurements (own delta)
- [ ] 2.3 Remove tools that cannot return a result (starting with FEA while no solver ships)
- [ ] 2.4 One vocabulary for spec, part, card and file across tools, results and docs
- [x] 2.5 Truthful read-only, destructive and open-world hints on every tool
- [ ] 2.6 Server instructions and the agent skill rewritten for the new set, most important first

## 3. Two clients

- [ ] 3.1 Codex runner for the measurement harness; registration line tested in CI
- [ ] 3.2 Corpus extended: journeys, one task per part family, a combination, a context folder
- [ ] 3.3 Baseline run on both clients; results published per client and version
- [x] 3.4 Gates: description and instruction length, schema constraints, result size, call time
- [ ] 3.5 Release blocked on a completion-rate regression on either client

## 4. Refusals

- [ ] 4.1 Each refusal names the field, the reason and a valid example, within a length limit
- [ ] 4.2 No suggestion less conservative than what was refused; near-match only when unambiguous
- [x] 4.3 Same mistake, same words on CLI and MCP (`tests/test_refusal_parity.py`: twenty
      mistakes through `check`/`run_validation` and `build`/`build_part`; findings 19, 20)

## 5. Install and release

- [ ] 5.1 Publish to the package index; geometry and exchange formats in the default install
- [ ] 5.2 One-line server launch through a package runner; one-line setup per client
- [x] 5.3 CI: install from the built wheel in a clean environment and run the README steps
      (`wheel-install`, every push; `tools/wheel-check/readme_steps.py`)
- [x] 5.4 `doctor` says in plain words what is missing

## 6. CLI

- [ ] 6.1 Review every command, flag and default; remove or merge overlaps; one table
- [x] 6.2 Help text states what each command is for in its first line

## 7. Performance

- [x] 7.1 Responsiveness budget covers every tool and command, cold and warm
- [x] 7.2 Profile the five slowest; improve or justify each (kernel import, first build)
- [x] 7.3 Suite runtime: profile, and cut the slowest tests that add no coverage (findings
      16 to 18: the rasterizer, one redundant 26-body render, and per-view meshing left open)

## 8. Docs

- [x] 8.1 README: three steps to a first part, what comes back, what Anvilate is not
- [x] 8.2 One index by task; orphan-page gate
- [x] 8.3 Remove or correct pages describing the workbench, a web server or a built-in model
- [ ] 8.4 Examples: keep the ones a newcomer needs in the index; the rest stay as tests
