"""Worked example: an enclosure floor that must leave a connector and a service corridor clear.

The floor of an electronics enclosure is a 240 by 160 mm plate. Two volumes around it are
declared as keepouts, each with its reason and the face it moves with:

- the J1 connector's mating envelope, a 24 mm cylinder in front of the east wall ending
  2 mm short of it, with a 1 mm clearance margin;
- the service corridor, an 80 by 60 mm channel beginning 20 mm above the mounting face,
  through which a technician reaches the fuse, with a 0.5 mm margin.

The floor was thickened from 18 mm to 22 mm to stiffen it. The connector still clears by
2 mm, but the floor now reaches 2 mm into the corridor, and the card fails with the
intruded volume, the depth along the corridor's axis and a repair hint: take the floor's
thickness down to 19.5 mm. The repair goes to 19 mm, clear of that exact solve, and the
card passes with the corridor 1 mm clear.

Needs the geometry extra (``pip install anvilate[geometry]``). Run it directly
(``python examples/enclosure_keepouts.py``); :func:`card` and :func:`repaired_card` are also
exercised in the test suite.
"""

from __future__ import annotations

from anvilate.geometry import build_spec
from anvilate.keepouts import screen_keepouts
from anvilate.packs.structural import BasePlate
from anvilate.scorecard import Scorecard
from anvilate.spec import (
    AcceptanceCriteria,
    CylinderKeepout,
    DesignSpec,
    Keepout,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Origin,
    Provenanced,
    SweptProfileKeepout,
    ValidationTier,
)
from anvilate.units import Quantity, UnitSystem

q = Quantity.parse

CONNECTOR = Keepout(
    tag="j1_mating_envelope",
    anchor="east",
    # In front of the east wall, 40 mm out to 2 mm short of the face: the plug's latch
    # sweep, which must not touch the floor's edge.
    rule=CylinderKeepout(diameter=q("24 mm"), height=q("38 mm")),
    offset=q("-40 mm"),
    clearance_margin=q("1 mm"),
    reason="the J1 plug and its latch must seat without touching the floor",
)
CORRIDOR = Keepout(
    tag="service_corridor",
    anchor="bottom",
    # A technician's hand reaches the fuse through a channel 20 mm above the mounting face.
    rule=SweptProfileKeepout(
        profile_width=q("80 mm"), profile_height=q("60 mm"), path_length=q("40 mm")
    ),
    offset=q("20 mm"),
    clearance_margin=q("0.5 mm"),
    reason="a technician's hand reaches the fuse through the service door",
    owner="service engineering",
)


def _spec(floor: str) -> DesignSpec:
    return DesignSpec(
        name="enclosure_floor",
        description="The floor of a sealed electronics enclosure.",
        units=Provenanced(value=UnitSystem.SI, origin=Origin.USER_STATED),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        element_type="base_plate",
        element_params=BasePlate(
            name="enclosure_floor",
            width=q("240 mm"),
            depth=q("160 mm"),
            plate_thickness=q(floor),
            plate_material="ASTM-A36",
            cantilever=q("30 mm"),
            axial_load=q("40 kN"),
            concrete_strength=q("25 MPa"),
        ).model_dump(),
        keepouts=(CONNECTOR, CORRIDOR),
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    )


def _card(floor: str) -> Scorecard:
    spec = _spec(floor)
    entries, _bodies = screen_keepouts(spec, build_spec(spec))
    return Scorecard(entries=entries)


def card() -> Scorecard:
    """The floor as redrawn: thickened to 22 mm to stiffen it, into the service corridor."""
    return _card("22 mm")


def repaired_card() -> Scorecard:
    """The repair: the floor back under the corridor, at the thickness the hint solves."""
    return _card("19 mm")


def main() -> None:
    for label, scorecard in (("as redrawn", card()), ("repaired", repaired_card())):
        print(f"{label}: {scorecard.status.value}")
        for entry in scorecard.entries:
            print(f"  {entry}")


if __name__ == "__main__":
    main()
