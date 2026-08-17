# Aluminum structural screening (ADM 2020)

Aluminum member design is the most persistently spreadsheet-bound structural
discipline: no open-source implementation of the Aluminum Design Manual existed
anywhere, and the commercial coverage is thin add-ons to analysis suites. The
audience — handrails, walkways, platforms, sign structures, curtain wall, marine
superstructures — is steady and unserved.

Two things make aluminum different from steel, and this pack is built around both.

**The buckling curves are straight lines, not one smooth curve.** The ADM fits each
buckling strength with an inelastic straight line that meets the Euler curve at a
slenderness `C`. Aluminum's modulus is about a third of steel's, so that handover
happens at a slenderness a steel designer still thinks of as stocky: `C_c` is 66 for
6061-T6, against about 113 for A992 steel.

**Welding destroys the temper, permanently.** A 6061-T6 extrusion is heat-treated to
a compressive yield of 35 ksi; within about an inch of the arc it is down to 15 ksi
and stays there. Steel has nothing comparable, so the habit does not transfer.

## What you get

```python
from anvilate.analysis import (
    AlloyProperties, EdgeSupport, TemperGroup,
    aluminum_buckling_constants, aluminum_compression_strength,
    aluminum_compression_scorecard,
)
from anvilate.units import Quantity

constants = aluminum_buckling_constants(          # ADM §B.4, from F_cy and E
    compressive_yield=Quantity.parse("35 ksi"),
    elastic_modulus=Quantity.parse("10100 ksi"),
)
# constants.intersection_member == 65.7  (the ADM's tabulated C_c for 6061-T6 is 66)
```

| Function | ADM clause | What it gives |
| --- | --- | --- |
| `aluminum_buckling_constants` | §B.4 (Table B.4.2) | `B_c`, `D_c`, `C_c`, `B_p`, `D_p`, `C_p`, computed from the alloy's own `F_cy` and `E` |
| `aluminum_member_buckling_stress` | §E.3 | The column curve: yielding, inelastic line, then `0.85·π²E/λ²` |
| `aluminum_local_buckling_stress` | §B.5.4 | A flat element by edge support: yielding, inelastic, then postbuckling reserve |
| `aluminum_elastic_local_buckling_stress` | §B.5.6 | `F_e`, the stress at which the element *first* buckles — the §E.4 trigger |
| `aluminum_lateral_torsional_moment` | §F.4.2 | The beam LTB moment, with **no** 0.85 knockdown |
| `aluminum_combined_interaction` | §H.1 | The flat linear sum `P/P_c + M_x/M_cx + M_y/M_cy` |
| `aluminum_tension_stress` | §D.2 | `min(F_ty, F_tu/k_t)` |
| `aluminum_compression_strength` / `_scorecard` | all of the above | The three limit states, the governing one named, parent and weld-affected side by side |

### Buckling constants are computed, never tabulated

The §B.4 formulas are evaluated on the alloy's own properties:

```
B_c = F_cy[1 + (F_cy/2250)^(1/2)]    D_c = (B_c/10)(B_c/E)^(1/2)    C_c = 0.41·B_c/D_c
B_p = F_cy[1 + (F_cy/1500)^(1/3)]    D_p = (B_p/10)(B_p/E)^(1/2)    C_p = 0.41·B_p/D_p
```

No copy of the standard's tables is bundled. That is a correctness matter as well as a
licensing one: a tabulated constant silently stops applying the moment a caller supplies
a tested or certified strength that is not the table's.

The library's test suite anchors all of them against the allowable stresses the ADM
publishes for 6061-T6 in Part VI Table 2-19 — the column curve at four slendernesses
spanning all three branches, the flange and web local-buckling curves, and the
published I 12 × 14.3 lateral-torsional example.

## Welding is first-class

Supply the weld-affected property set on `AlloyProperties.weld_affected` and pass
`welded=True`. The screen runs twice, reports both, and names which governed:

```
unwelded member              pass           SF 1.79
    member buckling governs: 178.5 MPa allowed against a demand of 100 MPa
welded at the connection     fail           SF 0.87
    member buckling governs: 87.38 MPa ...; parent metal 178.5 MPa,
    weld-affected 87.38 MPa, weld-affected governs
welded, no HAZ data supplied not_evaluated  SF   —
    not evaluated — the weld-affected F_cyw for 6061-T6 was not supplied
```

That third row is the point. A member declared welded with no weld-affected properties
does not quietly fall back to parent metal, and it does not pass. See
[`examples/welded_aluminum_platform_beam.py`](../examples/welded_aluminum_platform_beam.py).

## What this pack does not do

- **Non-aged tempers.** Only the artificially aged tempers (-T5 through -T9, ADM
  Table B.4.2) are implemented. An -O, -H, -T1 through -T4 temper takes Table B.4.1,
  whose constants have a different form; declare it with `TemperGroup.NON_AGED` and the
  screen reports `NOT_EVALUATED` rather than evaluating the wrong table.
- **The §E.4 local/member buckling interaction reduction.** When the element buckles
  elastically below the elastic member buckling stress, §E.4 requires the member
  buckling strength to come down. The screen detects that condition
  (`local_member_interaction`), says so in the detail, and downgrades what would have
  been a pass to `NOT_EVALUATED` — but it does not apply the reduction, because §E.4's
  scope depends on the shape in ways a one-element screen cannot see.
- **Alloy properties.** Following the user-supplied-allowables doctrine, `F_cy`, `F_ty`,
  `F_tu`, `E` and the weld-affected set are the caller's, with a `source` recording where
  they came from. `AlloyProperties` refuses a blank one.

ADM 2020 is viewable free on [ICC Digital Codes](https://codes.iccsafe.org/content/AAADM2020P1),
so every cited clause can be checked at no cost.
