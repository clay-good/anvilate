# Change: Typed repair feedback — sensitivities, two-sided bands, governing checks

## Why

2026 research on agent-driven CAD converged on one finding: structured, machine-actionable
validator feedback is what moves success rates. "Self-Improving CAD Generation Agents with
FEA as Feedback" (https://arxiv.org/abs/2605.17448) showed frontier coding agents get zero
strict passes unaided and that typed feedback schemas measurably close the gap;
"Physics-in-the-Loop" (IJCAI 2026, https://arxiv.org/abs/2605.19717) validated checking for
*over-engineering* (safety factor above a target band), not just failure; COSMO-Agent
(https://arxiv.org/abs/2605.20190) frames revision as revise-until-constraints-pass — which
Anvilate's design inverses can turn from a search into a solve.

Anvilate's scorecard today states `{id, status, measured, threshold}`. It does not say
*which parameter to change, in which direction, by how much* — the exact information its
own design-inverse functions can compute deterministically. Nor does it flag a part that
passes everything at SF 9 when the target was 2: silently wasteful is a cousin of silently
green.

## What Changes

- `validation-gauntlet`: scorecard records gain optional repair hints (governing
  parameter, direction, and a corrective value when a design inverse exists); acceptance
  criteria support two-sided bands with an over-margin warning status; the scorecard
  identifies the governing check and reports governing-check changes across revalidations.
- `agent-repair-loop`: the deterministic planner consumes repair hints before any numeric
  search — when an inverse provides the corrective value, repair is a single solve.

## Impact

- Affected specs: `validation-gauntlet` (3 added requirements), `agent-repair-loop`
  (1 added requirement).
- Affected code (when implemented): scorecard record type, analysis design-inverse
  bindings, future planner.
- Backward compatible: hints and bands are optional fields; existing one-sided checks are
  unchanged.
