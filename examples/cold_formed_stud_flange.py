"""Worked example: the cold-formed flange that is only half there.

A cold-formed steel member is thin enough that its wide flat elements buckle
locally, in gentle waves, long before the steel yields. When that happens the
middle of the element stops taking new load and sheds it to the stiff edges, so the
element behaves as if only a reduced *effective* width — clustered at the edges —
were present. The AISI S100 effective-width method (Winter's formula) quantifies
that reduction, and it is the calculation that makes cold-formed design different
from hot-rolled: you cannot use the gross section.

A 100 mm wide flange in 1.5 mm steel (a slenderness w/t of 67) carries stress f up
to the 345 MPa yield of the material. At that stress the plate slenderness is 1.45,
well past the 0.673 limit, and Winter's formula leaves only 59 mm effective — the
flange is barely more than half there, and any section modulus computed on the full
100 mm would badly overstate the member. Thicken the same flange to 3.5 mm and the
slenderness drops below the 0.673 limit: it is fully effective, all 100 mm of it.

The lesson is to compute cold-formed section properties on the effective section,
not the gross one, and that a little more thickness (or a narrower flange, or an
intermediate stiffener) can move an element from partly effective to fully
effective. Anvilate evaluates Winter's formula; the yield strength and modulus are
the caller's. Run it directly (``python examples/cold_formed_stud_flange.py``);
:func:`effective_flange_width` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import aisi_effective_width
from anvilate.units import Quantity

FLANGE_WIDTH = Quantity.parse("100 mm")
YIELD_STRESS = Quantity.parse("345 MPa")  # the edge stress, at yield
MODULUS = Quantity.parse("203000 MPa")  # cold-formed steel


def effective_flange_width(thickness: Quantity) -> Quantity:
    """The AISI effective width of the flange at yield, for a given thickness."""
    return aisi_effective_width(
        flat_width=FLANGE_WIDTH,
        thickness=thickness,
        stress=YIELD_STRESS,
        elastic_modulus=MODULUS,
    )


def main() -> None:
    full = FLANGE_WIDTH.to("mm").magnitude
    for label, t in (("1.5 mm (thin)", "1.5 mm"), ("3.5 mm (thicker)", "3.5 mm")):
        b = effective_flange_width(Quantity.parse(t)).to("mm").magnitude
        print(f"{label}: effective width {b:.1f} mm of {full:.0f} mm ({b / full * 100:.0f}%)")


if __name__ == "__main__":
    main()
