# Change: Make the derivation-coverage gate exist

## Why

`calculation-report`'s "Derivation metadata is part of the check contract" ends with the
part that gives it teeth: **"CI SHALL report the coverage ratio and fail when a newly added
check ships without metadata"**, and its scenario is a new check merged without one, caught
by name, "unless the check is explicitly registered as tabular-only with a stated reason".

Two of the three halves are built. `Derivation` is a typed, frozen artifact with a symbol
glossary and a citation, and `Report.derivation_coverage()` reports a ratio *for one
report*. The third half does not exist anywhere: there is no repo-wide gate, no
tabular-only registry, and no stated reason attached to any check that lacks metadata.
Grepping for the registry's own vocabulary — `tabular-only`, `TABULAR_ONLY` — returns
nothing in `src/` or `tests/`.

**Measured, not estimated.** Harvesting every `Scorecard` the suite builds and keying each
entry by the clause it cites: **18 of 75 distinct clause references carry a
derivation, and 57 never do** — 24% coverage. That number has
never been reported by anything.

## What Changes

Nothing yet, because two things have to be decided first and neither is a detail.

**1. A check has no identity to fail CI by.** The scenario says CI "fails naming the check".
`ScorecardEntry.name` is per-part prose — `12 mm wall: internal pressure (hoop)`,
`4 m spreader beam rating` — so it names a *result*, not a check. The closest thing to a
stable identity is the clause the entry cites, which is what the measurement above uses; it
is imperfect (two checks can cite one clause, and no-clause entries cite none). Deciding
what a check *is* comes before any gate that names one.

**2. The registry has to distinguish two things the requirement writes as one.**
"Tabular-only with a stated reason" is honest for a check that is a lookup with no formula
to render — a DFM process-capability table, an ASHRAE ventilation rate. It is not honest for
`AISC 360-16 §J4.1`, which is a formula whose derivation simply has not been written. A
registry that files both under "tabular-only" converts a debt into a decision, which is
worse than the silence it replaces. So the registry needs both categories, and seeding it
means reading 57 standards clauses and judging each — that is the work, and it
cannot be done by pattern.

**3. The harvest mechanism.** The measurement came from patching `Scorecard.__init__` for
one suite run. As a shipped gate that means either a session-wide patch in `conftest.py`
(ordering-sensitive: the assertion has to run after every test that builds a card) or a
second suite run in a subprocess (~90s of CI). Neither is obviously right.

## Impact

- Affected specs: `calculation-report`.
- Affected code: a registry and a gate, plus a derivation for each clause classified as a
  debt rather than a lookup.
- Nothing is broken today that this fixes. What it fixes is that the coverage number is
  unknown to CI and can fall without anyone noticing, which is the failure the requirement
  was written to prevent.

## The clauses with no derivation, as measured

- `AISC 360-16 §H1.2`
- `AISC 360-16 §J4.1`
- `AISC 360-22 G3`
- `AISC 360-22 L3`
- `AISC 360-22 §J4.3`
- `AISI S100 Appendix 1 (Direct Strength Method)`
- `ASCE 7-22 §2.3.1`
- `ASCE 7-22 §2.3.6`
- `ASHRAE 62.1 ventilation-rate procedure (Voz)`
- `ASHRAE 90.1 / IECC — lighting power density allowance`
- `ASME B31.3 §304.1.2`
- `ASME BTH-1 §3-1.3 (Design Category)`
- `ASME BTH-1 §3-1.4`
- `ASME BTH-1 §3-1.4 (Service Class)`
- `ASME BTH-1 §3-2`
- `ASME BTH-1 §3-2/§3-3 (allowable stresses)`
- `ASME VIII Div 1 Mandatory Appendix 2 (bolted flange connections)`
- `ASME VIII Div 1 UG-27`
- `ASME VIII Div 1 UG-32`
- `ASME VIII Div 1 UG-37 (reinforcement of openings)`
- `AWS D1.1 fillet weld`
- `Aluminum Design Manual 2020 Part I §B.4/§B.5.4/§E.3/§F.4.2`
- `BS 7910 / R6 Option 1 failure assessment diagram`
- `DFM screening estimates (typical finest achievable tolerances)`
- `Darcy-Weisbach friction + fitting minor losses`
- `EN 15978 life-cycle modules; ISO 14040 cradle-to-gate boundary`
- `EN 1993-1-9`
- `IES Lighting Handbook — recommended task illuminance`
- `ISO 286 H7/g6`
- `ISO 286 H7/g6 clearance fit`
- `ISO 286-1 standard tolerance grades (IT grades)`
- `Infinite-slope limit equilibrium`
- `Kirchhoff plate theory (Bessel eigenvalue)`
- `Kirchhoff plate theory (FD-verified eigenvalue table)`
- `Kirchhoff plate theory (Navier eigenvalue)`
- `Kirchhoff plate theory (Navier series)`
- `Kirchhoff plate theory (axisymmetric closed form)`
- `NDS`
- `NEC 210.19(A)/215.2 informational note — feeder voltage drop`
- `NEC 310.16 — conductor ampacity`
- `NPSH available vs required (cavitation margin)`
- `OSHA 29 CFR 1910.95 / NIOSH REL — 85 dBA criterion, 3 dB exchange rate`
- `OSHA 29 CFR 1910.95 / NIOSH REL — 90 dBA criterion, 5 dB exchange rate`
- `Pump shaft power P = ρgQH/η`
- `Rankine active thrust, base friction resistance`
- `Rankine active thrust, moment balance about the toe`
- `Roark's Formulas, Table 11.4`
- `Rolfe-Novak-Barsom upper-shelf Charpy correlation (an ESTIMATE)`
- `Shigley's Mechanical Engineering Design, Marin surface factor k_a = a·S_u^b (surface-finish table, S_u in MPa); screening estimate, not a measured factor`
- `TMS 402 §8.2.4 allowable axial stress`
- `TMS 402 §8.2.4.2 combined axial + flexure unity`
- `Terzaghi bearing capacity with Vesić shape/depth factors`
- `application minimum air changes per hour`
- `half-sine shock response spectrum`
- `standards effectivity`
- `the plated size is the size that has to fit`
- `α-method pile capacity (shaft friction + end bearing)`
