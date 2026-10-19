# Change: Walking-working surfaces pack — guardrails, stairs, ladders and platforms checked to the regulation that governs them

## Why

Every plant, warehouse, mezzanine, machine platform and equipment skid has them:
guardrails, stair systems, fixed ladders, landings and platforms. They are small,
parametric, prescribed by a public regulation, built constantly, and checked today in a
spreadsheet or not at all. That is the wedge `discipline-packs` describes word for word.

The governing text for US general industry is 29 CFR 1910 Subpart D (walking-working
surfaces), which is a federal regulation and in the public domain, and it prescribes
the numbers a check needs (read from the eCFR on 2026-10-19):

| Item | Requirement | Clause |
| --- | --- | --- |
| Guardrail top rail | Withstand at least 200 lbf (890 N) applied downward or outward within 2 in of the top edge at any point | 1910.29(b)(3) |
| Guardrail deflection | Under the 200 lbf downward load, the top rail must not deflect below 39 in (99 cm) above the surface | 1910.29(b)(4) |
| Midrails and intermediate members | Withstand at least 150 lbf (667 N) downward or outward | 1910.29(b)(5) |
| Stair rails and handrails | Withstand at least 200 lbf (890 N) within 2 in of the top edge | 1910.29(f) |
| Stairs, load | At least five times the normal anticipated live load and never less than a 1,000 lb (454 kg) concentrated load at any point | 1910.25(b)(6) |
| Standard stairs | 30 to 50 degrees; riser at most 9.5 in; tread at least 9.5 in; width at least 22 in | 1910.25(c) |
| Ship stairs; alternating tread | 50 to 70 degrees; their own tread and width minimums | 1910.25(e), (f) |
| Headroom; landings | 6 ft 8 in; at least the stair's width and 30 in deep | 1910.25(b)(2), (b)(4) |
| Fixed ladders | Rung spacing 10 to 14 in; clear width 16 in; 7 in clearance behind rungs; side rails 42 in above the landing; 30 in on the climbing side | 1910.23(b)(2), (b)(4), (d)(2), (d)(4), (d)(13) |
| Fall protection trigger | Unprotected sides and edges 4 ft (1.2 m) or more above a lower level; fixed ladders over 24 ft need a ladder safety or fall arrest system | 1910.28(b)(1), (b)(9) |

Those are load and geometry rules on members, plates and connections Anvilate already
screens: a tube post is a column with a moment at its base, a rail is a beam, a stringer
is a beam, a post base is a bolted connection on anchors. `add-frame-analysis` gives the
run its member forces. What is missing is the element that knows which clause applies,
the geometry rules, and the parts.

Construction (29 CFR 1926 Subpart M) and the building codes (IBC Chapter 10 and its
loads in Chapter 16) have different numbers and are copyrighted in the IBC's case. The
pack declares which regime applies and refuses to apply one to the other.

## What Changes

| Area | Change |
| --- | --- |
| Elements | Guardrail system (posts, top rail, midrail, toeboard), stair system (stringers, treads, landings, stair rail), fixed ladder (rails, rungs, cage or safety-system requirement), platform or mezzanine edge, each as a declared element with its regime. |
| Load rules | The regulation's loads applied as load cases (the 200 lbf top-rail case at the worst point, the 150 lbf midrail case, the stair concentrated and factored live loads); member and connection screens run on them through the existing beam, column, tube, bolt and anchor screens, with frame analysis for a run of posts and rails. |
| Geometry rules | Rail heights, rung spacing and clearances, stair angle, riser, tread, width, headroom and landing depth, each a cited pass/fail against the clause. |
| Deflection | The top-rail deflection rule as a check on the solved deflection under the top-rail load. |
| Regime | General industry (1910) and construction (1926) as declared regimes; a jurisdiction's building code as a user-declared regime with user-supplied loads and citations, never bundled. |
| Grating and decking | Spans screened against the manufacturer's load table the user supplies with its citation; never a bundled table. |
| Drawable | Posts and rails from the existing tube part; stringers from the existing members; a guardrail run as a combination. Treads and grating are not drawn. |

## Impact

- Delta: `discipline-packs` (ADDED). Builds on the structural pack
  (`src/anvilate/packs/structural.py`), the industrial pack, `add-frame-analysis`,
  `add-part-combinations`, `add-equipment-anchorage` (post bases on anchors) and
  `add-standards-effectivity` (the eCFR is dated; the edition is the date read).
- Licensing: 29 CFR is a US federal regulation and in the public domain; each clause is
  cited by paragraph with the date read. The IBC and ASCE 7 are copyrighted; their
  loads are user-supplied with citation.
- Explicitly out:
  - Scaffolds, aerial lifts, dockboards, rope descent systems, and personal fall
    protection equipment (the rest of Subpart D and Subpart I).
  - Egress capacity, occupancy and travel distance (building-code planning).
  - Stair tread slip resistance and nosing design.
  - Any statement of OSHA compliance; the card cites the clause it checked.
