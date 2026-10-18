"""Worked example: a formed Z stringer cripples well below yield, and its corners help.

A 1.0 mm aluminium Z stringer with a 40 mm web and two 20 mm flanges has an area of
80 mm². Its flat elements buckle early, but the corners keep carrying load, and Gerard's
two-corner correlation (NACA TN 3784 eq. 61) puts its crippling stress at 142.2 MPa,
0.49 of the 290 MPa compressive yield. The form holds up to 0.52 of yield for a 40
mm web, so the answer is inside it.

Forming work-hardens the corners. Declared at 25% above the flat sheet's yield, the
tabulated β rises from 3.3 to 4.0 and the crippling stress to 172.4 MPa. The
table lists β only at a few corner-yield ratios, and the module takes the row at or below
the declared one, never a value between rows. On a stubbier section, a 30 mm web with
15 mm flanges, the flat-cornered stringer lands past the form's own cutoff and the screen
refuses, naming the local buckling stress (eq. 73) as the answer it does not compute. The
hardened one stays inside, because the cutoff itself rises with β.

The material values here are illustrative, not allowables.

Run it directly (``python examples/z_stringer_crippling.py``);
:func:`z_stringer_crippling` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CripplingSection, gerard_crippling_stress
from anvilate.units import Quantity


def _z(corner_yield_ratio: float):
    return gerard_crippling_stress(
        section=CripplingSection.FORMED_TWO_CORNER,
        thickness=Quantity(magnitude=1.0, unit="mm"),
        area=Quantity(magnitude=80.0, unit="mm**2"),
        compressive_yield=Quantity(magnitude=290.0, unit="MPa"),
        elastic_modulus=Quantity(magnitude=72_400.0, unit="MPa"),
        count=2,
        corner_yield_ratio=corner_yield_ratio,
        web_width=Quantity(magnitude=40.0, unit="mm"),
    )


def z_stringer_crippling() -> dict[str, float]:
    """Return the crippling stress as formed flat and with work-hardened corners."""
    flat, hardened = _z(1.0), _z(1.25)
    return {
        "stress_mpa": flat.stress,
        "ratio": flat.ratio,
        "cutoff": flat.cutoff,
        "stress_hardened_mpa": hardened.stress,
    }


def main() -> None:
    d = z_stringer_crippling()
    print(f"crippling: {d['stress_mpa']:.1f} MPa ({d['ratio']:.2f} of yield)")
    print(f"cutoff: {d['cutoff']:.2f} of yield")
    print(f"with work-hardened corners: {d['stress_hardened_mpa']:.1f} MPa")


if __name__ == "__main__":
    main()
