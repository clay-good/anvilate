"""Worked example: an eccentric bracket load puts the far bolts past their allowables.

A bracket hangs 6 kN on a 50 mm square of four M6 bolts, 100 mm out from the pattern's
centre. Shared equally, each bolt would see 1.5 kN. The eccentricity adds a twist of
600,000 N·mm, and the bolts farthest from the load line take its share at right angles to
their radius: the governing bolt carries 5,408 N, more than three times the even share.

With the full-diameter body in the shear plane, NASA-STD-5020B Eq. 20 gives an interaction
index of 0.79 for that bolt with 2 kN of tension. Put the threads in the shear plane, as
a bolt into a tapped hole does, and Eq. 22's exponents raise it to 1.01, past the limit
of 1. Same load, same bolt; where the shear plane falls decides whether it passes.

The allowables (6.3 kN shear on the body, 5.6 kN on the threads, 9 kN tension) are
illustrative ultimate values for an M6 bolt, not a procurement specification's.

Run it directly (``python examples/eccentric_bolt_pattern.py``);
:func:`eccentric_bolt_pattern` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import GroupFastener, ShearPlane, fastener_group_loads
from anvilate.units import Quantity


def _q(value: float, unit: str) -> Quantity:
    return Quantity(magnitude=value, unit=unit)


def _pattern(plane: ShearPlane) -> list[GroupFastener]:
    shear = 6_300.0 if plane is ShearPlane.BODY else 5_600.0
    return [
        GroupFastener(
            name=name,
            x=_q(x, "mm"),
            y=_q(y, "mm"),
            diameter=_q(6.0, "mm"),
            shear_allowable=_q(shear, "N"),
            tension_allowable=_q(9_000.0, "N"),
            shear_plane=plane,
        )  # fmt: skip
        for name, x, y in (("A", 0, 0), ("B", 50, 0), ("C", 50, 50), ("D", 0, 50))
    ]


def _loads(plane: ShearPlane):
    return fastener_group_loads(
        _pattern(plane), shear_x=_q(0.0, "N"), shear_y=_q(-6_000.0, "N"),
        moment=_q(0.0, "N*mm"), load_x=_q(125.0, "mm"), load_y=_q(25.0, "mm"),
        tension=_q(8_000.0, "N"),
    )  # fmt: skip


def eccentric_bolt_pattern() -> dict[str, float | str]:
    """Return the governing bolt's shear and its interaction, body and threads in shear."""
    body, threads = _loads(ShearPlane.BODY), _loads(ShearPlane.THREADS)
    worst = next(f for f in body.fasteners if f.name == body.governing)
    return {
        "governing": body.governing,
        # the load's moment about the pattern's centroid: 6,000 N at 125 mm
        "twist_nmm": 6_000.0 * (125.0 - body.centroid[0]),
        "shear_n": worst.shear,
        "body_index": body.governing_index,
        "threads_index": threads.governing_index,
    }


def main() -> None:
    d = eccentric_bolt_pattern()
    print(f"bolt {d['governing']} governs at {d['shear_n']:,.0f} N shear")
    print(f"interaction, body in shear: {d['body_index']:.2f}")
    print(f"interaction, threads in shear: {d['threads_index']:.2f}")


if __name__ == "__main__":
    main()
