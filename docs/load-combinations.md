# Load combinations

Every code check the structural packs cite assumes a *combination* of load cases —
a factored sum under LRFD, a service sum under ASD — not a single case. The
governing combination is often not the obvious one, and a member or connection can
be governed by a different combination than the one next to it. Doing that
bookkeeping by hand is a silent-error class; this module does it explicitly.

## What you get

```python
from anvilate.loads import LoadNature, asce7_lrfd_basic

loads = {
    LoadNature.DEAD: 15.0,
    LoadNature.LIVE: 10.0,
    LoadNature.ROOF_LIVE: 12.0,
    LoadNature.WIND: -40.0,   # a net uplift on a light canopy — the sign is yours to assert
}

combos = asce7_lrfd_basic()
combos.envelope(loads)                     # 47.2 — the largest factored demand
combos.governing(loads)                    # (LRFD 3 (+L) [Lr], 47.2) — sizes the beam
combos.governing(loads, minimize=True)     # (LRFD 5, -26.5) — the uplift that sizes the hold-down
combos.evaluate_all(loads)                 # every combination's demand, in order
```

- **`asce7_lrfd_basic()`** and **`asce7_asd_basic()`** generate the ASCE 7-22 §2.3.1
  strength and §2.4.1 allowable-stress basic combinations, with the roof companion
  "(Lr or S or R)" expanded into one variant per companion.
- **`governing(loads)`** names the largest-demand combination — the strength
  envelope. **`minimize=True`** names the smallest — the counteracting case (0.9D +
  1.0W netting upward) that governs uplift and overturning, and that a gravity-only
  check silently misses.
- **Custom sets**: build a `CombinationSet` of your own `LoadCombination`s with any
  factors and citation.

See [`examples/canopy_beam_load_combinations.py`](../examples/canopy_beam_load_combinations.py)
for a canopy beam whose bending is sized by one combination and whose hold-down by
another.

## Into the scorecard

`combination_scorecard` screens a capacity against the governing combination and
returns a scorecard entry that names which combination controlled — no silent
subsetting to one number:

```python
from anvilate.loads import asce7_lrfd_basic, combination_scorecard

entry = combination_scorecard(
    "beam bending",
    combinations=asce7_lrfd_basic(),
    loads=loads,
    capacity=130.0,
    required=1.5,
)
entry.detail      # "...; demand 47.2 from LRFD 3 (+L) [Lr]: 1.2D + 1L + 1.6Lr"
entry.reference   # "ASCE 7-22 §2.3.1"
```

Pass `minimize=True` to screen a hold-down or overturning check against the
counteracting combination instead.

## From a spec's load cases

A `DesignSpec` load case can declare its `nature` (an ASCE 7 `LoadNature`), and
`DesignSpec.combination_loads()` aggregates the classified cases into the same
`{LoadNature: newtons}` mapping the generators consume — so combinations run from
the spec, not a side spreadsheet:

```python
loads = spec.combination_loads()          # sums each nature's force magnitude, signs kept
combination_scorecard("deck strength", combinations=asce7_lrfd_basic(),
                      loads=loads, capacity=90_000.0, required=1.5)
```

See [`examples/spec_load_combination_check.py`](../examples/spec_load_combination_check.py)
for the full spec-to-scorecard flow.

## What Anvilate does and does not derive

This is **combination factoring, not load derivation**. The generators apply the
published factors to load magnitudes you supply. Deriving those magnitudes — wind,
seismic, snow, rain from maps, site parameters, and building geometry — stays out of
scope; that is the wind-tunnel and hazard-map work a combination table cannot do.

Seismic combinations are available through `asce7_lrfd_seismic(s_ds=..., redundancy=...)`
(§2.3.6) and `asce7_asd_seismic(...)` (§2.4.5). They split the earthquake load E into
its vertical part Ev = 0.2·S_DS·D (folded into the dead-load factor) and its horizontal
part Eh = ρ·Q_E (carried on the seismic load you supply as Q_E). The design spectral
acceleration S_DS and the redundancy factor ρ are typed inputs — the combination is
factored here, the seismic hazard is derived by you. Both horizontal directions (±Eh)
are generated, so the reduced-dead combination surfaces the load reversal that puts a
gravity-compression column into net tension.
