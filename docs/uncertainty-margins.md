# Uncertainty-aware margins

A safety factor computed from single best-guess inputs is a point estimate. When
the governing input is only known to a band — a load to ±15%, a strength to its
material scatter — that point can sit comfortably above the required factor while a
real fraction of the time the design falls below it. `sample_margin` turns the
input scatter into a distribution of the margin, so that fraction is reported
rather than hidden.

## What you get

```python
from anvilate.uncertainty import Normal, sample_margin

# SF = capacity / load, with the load the dominant unknown.
def safety_factor(v):
    return (v["yield_strength"] * v["area"] / 1000.0) / v["load"]

result = sample_margin(
    safety_factor,
    {
        "load": Normal(mean=29.4, std=0.15 * 29.4),          # 15% CoV
        "yield_strength": Normal(mean=250.0, std=0.05 * 250), # 5% CoV
        "area": Normal(mean=200.0, std=0.0),                  # fixed
    },
    required=1.5,
    seed=20260803,
)

print(result)                       # margin 1.74 ± 0.29, P(below 1.50) = 20.3% over 10000 samples
result.shortfall_probability        # 0.203 — the chance of falling short of 1.5
result.lower, result.upper          # the central 90% band of the safety factor
result.is_fragile(threshold=0.05)   # True — a nominal pass with a material failure chance
result.dominant().name              # "load" — the input driving the scatter
```

- **`response`** maps a name→value mapping to one float — a safety factor,
  utilization, or any margin whose fall below `required` is a failure. The sampler
  is unit-agnostic: the caller's function does the unit bookkeeping, so it wraps any
  analysis function without this module reaching into the analysis layer.
- **Input distributions**: `Normal(mean, std)`, `Uniform(low, high)`, and
  `Symmetric(nominal, half_width, ...)` — the ± vocabulary, where the half-width is
  read as `sigma_level` sigmas (default 3σ, matching the tolerance stack-up).
- **`shortfall_probability`** is the fraction of samples below `required`.
- **`sensitivities`** ranks the inputs by their first-order (Taylor) share of the
  response variance — what to pin down first.

## Reproducible by construction

`seed` is required, and input names are drawn in sorted order, so a run is
byte-identical regardless of the order the input mapping was built in. The same
seed and inputs always give the same statistics.

## What the probability means — and does not

This is **screening, not certified reliability**. The shortfall probability is only
as trustworthy as the ± bands the engineer asserts, and the sensitivity ranking
assumes the response is locally smooth. It answers "given these input spreads, how
often does the margin fall short?" — a design question — not "what is the certified
failure rate of this part?" Full FORM/SORM-class methods stay out of scope.

**A fragile check says so on its own line.** `ScorecardEntry.is_fragile()` has always been
public and the calculation report has always rendered the annotation, but the entry's own
one-line rendering — what `print(entry)` gives you, and the lazy path every caller takes —
printed a check whose margin falls short in one sample in five exactly like one that never
does. It now reads `[PASS] bending: safety factor 2.40 vs required minimum 2.00 — fragile:
21.0% of samples fall short`, and the card summary counts them, because a card of passing
checks with one fragile among them was a clean-looking card.

**The label travels with the number.** A rendered annotation names the sampling method,
the sample count *and* the screening label — the report says
`P(below 2.00) = 3.1% over 4096 samples by monte_carlo` and prints
`Monte Carlo propagation of input distributions; first-order (Taylor) variance
sensitivity. Screening only — not a certified reliability analysis.` beneath it. Both
renderings dropped the method and the label for a release: `MarginUncertainty` carried
them and nothing consumed either, so the one place a reviewer actually meets the
probability — the document they sign — showed it bare. What holds it now is a gate that
replaces the method and the citation with sentinel strings and requires the renderings to
show *those*, because a hardcoded "Monte Carlo, screening only" line satisfies every
naive check and becomes a lie the day a second method exists.

See [`examples/bracket_load_scatter_fragility.py`](../examples/bracket_load_scatter_fragility.py)
for a nominally passing bracket flagged fragile under load scatter.
