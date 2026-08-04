"""Worked example: the same column, two rulebooks, two different design demands.

A structure is never designed for one load — it is designed for the worst *combination* of dead,
live, snow, wind, and seismic all weighted by code factors, and ASCE 7 offers two philosophies for
doing the weighting. This example takes one interior column carrying the axial force each load
source delivers — 260 kN dead, 200 kN live, 90 kN snow, 40 kN wind, 110 kN seismic — and runs both.

LRFD (strength design) inflates the loads to a strength level, and here the gravity combination
1.2D + 1.6L + 0.5S governs at ~677 kN. ASD (allowable-stress) keeps the loads near service level
and governs lower, around 535 kN. The tempting mistake is to conclude LRFD is "more conservative"
because its number is bigger — it is not. The demands meet different resistances: the LRFD
677 kN against the column's *factored* strength φPn, the ASD 535 kN against its *allowable* strength
Pn/Ω. Pick one philosophy and stay in it; the raw kN from the two are not comparable. The lesson is
that a load combination is only half of a check — the factored demand and the resistance basis are a
matched pair.

Run it directly (``python examples/column_load_combinations.py``);
:func:`column_demands` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import asce7_asd_factored_load, asce7_lrfd_factored_load
from anvilate.units import Quantity

DEAD = Quantity.parse("260 kN")
LIVE = Quantity.parse("200 kN")
SNOW = Quantity.parse("90 kN")
WIND = Quantity.parse("40 kN")
SEISMIC = Quantity.parse("110 kN")


def column_demands() -> dict[str, float]:
    """Return the governing LRFD and ASD factored axial demands (kN) on the column."""
    loads = {
        "dead": DEAD,
        "live": LIVE,
        "roof_snow_rain": SNOW,
        "wind": WIND,
        "seismic": SEISMIC,
    }
    lrfd = asce7_lrfd_factored_load(**loads).to("kN").magnitude
    asd = asce7_asd_factored_load(**loads).to("kN").magnitude
    return {"lrfd_kn": lrfd, "asd_kn": asd}


def main() -> None:
    d = column_demands()
    print(
        f"LRFD governing demand : {d['lrfd_kn']:.0f} kN  (check against factored strength phi*Pn)"
    )
    print(
        f"ASD  governing demand : {d['asd_kn']:.0f} kN  (check against allowable strength Pn/Omega)"
    )
    print(
        "  -> the bigger LRFD number is not 'more conservative'; the resistance basis differs too"
    )


if __name__ == "__main__":
    main()
