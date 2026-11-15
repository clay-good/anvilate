# Walking-working surfaces

**The regime is declared, never assumed.** 29 CFR 1926 Subpart M governs construction and
says different numbers for several of the same things, so a document declaring
construction is *refused* here rather than screened against the general-industry ones. A
guardrail that passes the wrong regulation is worse than one nobody checked.

```yaml
element_type: guardrail_system
element_params:
  regime: us_general_industry      # 29 CFR 1910 Subpart D
  post_height: {magnitude: 1070, unit: mm}
  post_spacing: {magnitude: 1800, unit: mm}
  post_section_modulus: {magnitude: 4930, unit: mm ** 3}
  post_second_moment: {magnitude: 119000, unit: mm ** 4}
  yield_strength: {magnitude: 355, unit: MPa}
  elastic_modulus: {magnitude: 200, unit: GPa}
  rail_section_modulus: {magnitude: 4930, unit: mm ** 3}
  midrail_height: {magnitude: 530, unit: mm}
  toeboard_height: {magnitude: 100, unit: mm}
  toeboard_section_modulus: {magnitude: 1670, unit: mm ** 3}
```

| Regime | What happens |
| --- | --- |
| `us_general_industry` | Screened against 29 CFR 1910 Subpart D, the numbers below. |
| `us_construction` | Refused. 1926 Subparts M and X are public domain and not read into this library yet. |
| `user_declared` | Refused. Supply the code's own limits with their source. |

## What a guardrail is checked against

Every number was read off the eCFR text on 2026-11-15 and every entry cites its paragraph
and the edition it came from. Subpart D is a work of the United States government, which
is why — unlike the IBC, ASCE 7 or NDS values this library refuses to bundle — these ship.

| Check | Clause | What it says |
| --- | --- | --- |
| Top rail height | 1910.29(b)(1) | 42 in ± 3 in above the surface. Above 45 in is a **warning**, not a pass: the clause permits it only if every other criterion of (b) is met, which is the verdict this card is in the middle of reaching. |
| Post under the top rail load | 1910.29(b)(3) | 200 lbf downward or outward within 2 in of the top edge, at the top of a post. |
| Top rail between posts | 1910.29(b)(3) | The same 200 lbf at mid-span, where the rail is weakest. |
| Deflected height | 1910.29(b)(4) | Under that 200 lbf the top rail may not drop below 39 in. |
| Midrail | 1910.29(b)(5) | 150 lbf on an intermediate member, any direction, any point. |
| Toeboard height | 1910.29(k)(1)(ii) | At least 3.5 in from its top edge to the surface. |
| Toeboard strength | 1910.29(k)(1)(vi) | 50 lbf in any downward or outward direction. |

**A run with no midrail or toeboard gets no entry for it.** A check that did not apply and
a check that passed are different facts, and the card should not say the second when it
means the first.

**The required factor is 1.0 and that is deliberate.** 1910.29 states a force the system
must withstand *without failure*; it is not a load to be factored. A designer wanting
margin on top of the regulation passes `required_safety_factor` and the card says so.

**The deflection is the post alone.** δ = P·h³/3EI at the top of a post, which is what the
clause's own test measures there. The rail's own sag between posts adds to it, is not in
the number, and the entry says so.

A failing strength check names the section modulus to move and the value that lands the
margin exactly — the stress is linear in 1/Z, so the value is a solve and not a search.

## What a stair is checked against

```yaml
element_type: stair_system
element_params:
  regime: us_general_industry
  kind: standard                  # or `ship`, which has its own paragraph
  angle: {magnitude: 38, unit: degree}
  riser_height: {magnitude: 180, unit: mm}
  tread_depth: {magnitude: 280, unit: mm}
  width: {magnitude: 900, unit: mm}
  headroom: {magnitude: 2100, unit: mm}
  tread_capacity: {magnitude: 6, unit: kN}
  anticipated_live_load: {magnitude: 1.2, unit: kN}
  landing_depth: {magnitude: 900, unit: mm}
```

| Check | Clause | Standard | Ship |
| --- | --- | --- | --- |
| Slope from the horizontal | (c)(1) / (e)(1) | 30 to 50 degrees | 50 to 70 degrees |
| Riser height | (c)(2) / (e)(2) | at most 9.5 in | 6.5 to 12 in between tread surfaces |
| Tread depth | (c)(3) / (e)(3) | at least 9.5 in | at least 4 in |
| Width | (c)(4) / (e)(4) | at least 22 in **between vertical barriers** | at least 18 in **of tread** |
| Headroom above a tread | (b)(2) | at least 6 ft 8 in | same |
| Landing | (b)(4) | at least 30 in deep **and** at least the stair's own width | same |
| Tread load | (b)(6) | five times the declared live load, **and never less than** a 1,000 lb concentrated load | same |

**(b)(6) is two requirements, not one.** The governing half is found and named, and the
card says what the other half asked for. A stair sized on the five-times rule alone can
still fail the 1,000 lb floor, which is the case the floor was written for.

**The width means different things in the two paragraphs.** (c)(4) measures the stair
between its vertical barriers; (e)(4) measures the tread itself. The card says which it
measured, and the first draft of these notes had them confused.

A geometry entry's comparison always names **the bound its verdict turned on**. A
two-sided band reported against one end would render a 25-degree stair as "25 deg vs at
most 50 deg" beside a FAIL — a sentence contradicting the verdict above it.

## Fixed ladders and platform edges

| Check | Clause | What it says |
| --- | --- | --- |
| Rung spacing | 1910.23(b)(2) | 10 to 14 in between centrelines |
| Clear width | 1910.23(b)(4) | at least 16 in, before any safety system |
| Clearance behind | 1910.23(d)(2) | at least 7 in to the nearest object |
| Side rail extension | 1910.23(d)(4) | at least 42 in above the landing |
| Clearance each side | 1910.23(d)(13)(i) | at least 15 in, **no cage or well** |
| Clearance climbing side | 1910.23(d)(13)(ii) | at least 30 in, **no cage or well** |
| Ladder fall protection | 1910.28(b)(9) | **more than** 24 ft needs one of four systems |
| Edge fall protection | 1910.28(b)(1)(i) | 4 ft **or more** needs one of three |

**The two triggers differ at their boundary**, and this pack keeps them apart: a ladder
at exactly 24 ft is below its trigger and an edge at exactly 4 ft is at its own. A pack
reading both as the same comparison would be wrong about one of them.

A ladder *below* the trigger still gets an entry saying the rule did not fire. "It does
not apply here" is what a reader of a 23-foot ladder's card most needs to be told, and
silence reads the same as an oversight.

The (d)(13) clearances are written for a ladder **without** a cage or well, so a caged
ladder leaves them unset and gets no entry for them — and declaring them on a caged
ladder is refused rather than screened, because that would be a verdict under a rule
that does not govern.

Which fall-protection system to fit is a person's choice, so the repair hint is a
direction and not a value.

## The post base, and the two anchors a hand pulls out

The guardrail screen checks the post, the rails and the toeboard. It does not check what
holds the post down, and that is where 1910.29(b)(3)'s 200 lbf ends up: as a moment at
the base, and as tension in the anchors.

[`anchor_pattern_demand`](api/analysis-public-surface.txt) takes the pattern and the
clause load and says which bolt lifts first:

```python
from anvilate.analysis import anchor_pattern_demand
from anvilate.analysis.anchorage import AnchorPosition
from anvilate.units import Quantity

Q = Quantity.parse
pattern = tuple(
    AnchorPosition(tag=tag, x=Q(f"{x} mm"), y=Q(f"{y} mm"))
    for tag, x, y in (("fl", -75, -75), ("fr", -75, 75), ("bl", 75, -75), ("br", 75, 75))
)
anchor_pattern_demand(
    anchors=pattern, weight=Q("300 N"), lateral_force=Q("200 lbf"), height=Q("1070 mm")
)
```

A 1,070 mm post on a four-bolt plate at 150 mm centres puts **3,098 N into each of two
anchors**. The post's own weight resists 2.4% of the moment, so the anchors carry
essentially all of it, and **the only lever in the problem is the bolt spacing**: opening
the pattern to 300 mm takes the tension to 1,512 N without changing the post, the rail or
the plate. See
[`examples/guardrail_post_base_anchors.py`](../examples/guardrail_post_base_anchors.py).

**"In any direction" is not along an axis.** The clause applies its force any way, and
`governing_anchor_direction` sweeps for the worst: it is **across the pattern's short
side**, where the lever is least. A 400 x 100 mm pattern takes 4.2 times the tension
across its short dimension that it takes along its long one. On a square the axes are the
worst and the diagonal is the mildest, which is the opposite of how it looks.

Two bolts are where this gets sharp: **along** the load they take double the four-bolt
figure, because only one is ever in tension, and **across** it they are refused — two
anchors on one line resist no moment about that line. A two-bolt base plate works or is a
mechanism depending on which way it is turned, and nothing on the drawing says which.

What this produces is a **demand**. What an anchor can take is a concrete or steel
capacity with its own edition and factors, and this pack does not carry one.

## Worked end to end

[`examples/mezzanine_guardrail.py`](../examples/mezzanine_guardrail.py) answers the
question a designer actually has: *which clause fails this?* For a steel post of ordinary
height, (b)(3) always fails before (b)(4), and the example computes the post diameter at
which the two change places — about 17 mm, which is a rod and not a guardrail. Sizing for
the deflection clause is sizing for the wrong one.

[`examples/ship_stair_access.py`](../examples/ship_stair_access.py) screens one steep
stair twice. Three violations as a standard stair, none as a ship stair — `kind` selects
the paragraph. What the ship paragraph does **not** relax is (b), and the stair fails the
load rule's second half.

## Not in this pack yet

A guardrail run as a combination of real tube posts and rails, with the post bases on
anchors, is recorded in the change's design notes and not built; nor is the grating-span
check against a user-supplied load table. Spiral and alternating-tread stairs are read
and not built — `kind` carries the two this pack screens. The through-ladder extension
clearance of 1910.23(d)(5) and the step-across distances of (d)(12) are read and not
built: both need the ladder's relationship to what it serves, which the element does not
declare yet.

## What this pack does not do

Decide whether fall protection is required as a matter of law. Design a fall arrest
system. Stand in for the competent person 1910.28 names. It screens a declared geometry
and a declared load against clauses it cites, which is where the rest of this library
stops too.
