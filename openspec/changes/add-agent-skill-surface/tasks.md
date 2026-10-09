# Tasks: Agent skill surface

## 1. Content

- [x] 1.1 Skill covering: compile + confirm, retrieval-not-recall, run gauntlet, read
      scorecard, "not evaluated" != pass, inverse-first repair, export gate + disclaimer —
      six doctrine sections, each anchored by a marker and carried by a runnable example.
      The gauntlet/export half is scoped to the surface that exists: there is no CLI or MCP
      server yet, so the skill teaches the Python API and the evidence bundle's own gate
      (a plan with nothing performed is NOT_EVALUATED; `verified` is false) rather than
      describing an `anvilate export` that nobody can call
- [x] 1.2 Repository-convention instruction file for coding agents — the "Using Anvilate
      correctly" section of AGENTS.md, below the OpenLore managed block, with a CI gate
      that fails if it is written inside the block that gets overwritten
- [x] 1.3 Version + targeted tool-surface version stamped in both — frontmatter `version`
      must equal `anvilate.__version__`, and `tool-surface` must name the manifests the
      drift gate checks against

## 2. Packaging

- [x] 2.1 Ship in the distribution; verify offline availability — the skill lives inside
      the package (`anvilate/skills/anvilate/SKILL.md`), reached through
      `importlib.resources`, and a built wheel was confirmed to carry it
- [x] 2.2 Ensure no capability, gate, or default changes when loaded — the skill is a text
      file with no import side effects and nothing reads it at runtime; `anvilate.skills`
      exposes only a path and a reader

## 3. CI

- [x] 3.1 Validate every referenced tool/argument against published schemas — every
      backticked `anvilate.*` symbol is imported and resolved; a renamed function fails the
      build naming the stale reference
- [x] 3.2 Execute skill examples under the documentation-examples harness — each example
      runs in a fresh namespace and its stdout is compared byte for byte to the output the
      skill claims
- [x] 3.3 Prohibited-guidance check (no gate bypass, no certified-analysis claims) — seven
      patterns, proved to fire against a deliberately offending text. Two are negatable
      because the skill is required to deny them; the five instruction patterns are not,
      since a blanket negation allowance let a stray "not" excuse the very instructions
      they forbid

## 4. Evaluation

- [x] 4.1 Measure the agent-driving funnel with and without the skill loaded; publish the
      delta — measured 2026-10-09 through Claude Code 2.1.295 (`claude-opus-5-5`), with
      `tools/agent-skill-measurement/`, and published in `docs/agent-driving-evals.md`,
      where a test holds the table to the saved results. Completion is 8 of 9 in both
      conditions, so the delta is not completion: with the skill, 5 of 9 answers frame the
      result as a screen rather than a certified analysis (0 of 9 without), in 15 calls
      against 17, for about $0.40 more. The ninth task is the FEA tier, which Claude Code
      cannot start because it declares no tasks extension. It took three runs, and the two
      before found four defects fixed first: tool inputs that took a spec as a bare `$ref`,
      which the model sent as a string every time; a scorer that read 0% errors because
      Claude Code strips the `MCP error -326xx` prefix; server instructions cut at the
      2,048 characters Claude Code keeps, before the element list; and a corpus (now
      1.2.0) with an unanswerable task and a `compile_spec` prelude no correct run needs
