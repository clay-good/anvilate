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
| Riser height | (c)(2) | at most 9.5 in | — |
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

## Not in this pack yet

Fixed ladders and platform edges: 1910.23 and 1910.28(b) are read and recorded in the
change's design notes, and the elements are not built. A guardrail run as a combination
of real tube posts and rails, with the post bases on anchors, is likewise recorded and
not built. Spiral and alternating-tread stairs are read and not built; `kind` carries the
two this pack screens.

## What this pack does not do

Decide whether fall protection is required as a matter of law. Design a fall arrest
system. Stand in for the competent person 1910.28 names. It screens a declared geometry
and a declared load against clauses it cites, which is where the rest of this library
stops too.
