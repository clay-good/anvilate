"""Worked example: one gear mesh, four checks, three different parameters.

A spur mesh is rated on tooth-root bending, on surface pitting, on its contact ratio and on
the undercut limit, and no single number fixes all four. This example screens an 18/54 mesh
at module 2 that fails both stress checks — and reads back the two *different* modules they
ask for, 3.71 mm and 4.50 mm, because at a fixed pinion torque the tangential load falls as
the module grows and bending goes as 1/m² where pitting goes as 1/m.

Run it directly (``python examples/gear_mesh_scorecard.py``);
:func:`mesh_limits` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.machinery import SpurGearMesh, screen_gear_mesh
from anvilate.units import Quantity


def _mesh(**overrides: object) -> SpurGearMesh:
    """An 18/54 spur reduction carrying 180 N·m on the pinion, with the AGMA charts read."""
    fields: dict[str, object] = {
        "pinion_teeth": 18,
        "gear_teeth": 54,
        "module": Quantity.parse("2 mm"),
        "face_width": Quantity.parse("40 mm"),
        "pressure_angle": 20.0,
        "pinion_torque": Quantity.parse("180 N*m"),
        "bending_geometry_factor": 0.34,
        "contact_geometry_factor": 0.115,
        "allowable_bending_stress": Quantity.parse("250 MPa"),
        "allowable_contact_stress": Quantity.parse("1100 MPa"),
        "pinion_modulus": Quantity.parse("207 GPa"),
        "gear_modulus": Quantity.parse("207 GPa"),
        # None of these is 1.0 on a real drive, and leaving them there is a claim.
        "overload_factor": 1.25,
        "dynamic_factor": 1.3,
        "load_distribution_factor": 1.2,
    }
    fields.update(overrides)
    return SpurGearMesh(**fields)  # type: ignore[arg-type]


def mesh_limits() -> dict[str, object]:
    """The four safety factors, and the parameter each failing check names."""
    card = screen_gear_mesh(_mesh())
    return {
        "status": card.status.value,
        "factors": {e.name: round(e.safety_factor, 2) for e in card.entries},
        "levers": {
            e.name: (e.repair_hint.parameter, e.repair_hint.corrective_value)
            for e in card.entries
            if e.repair_hint is not None
        },
    }


def main() -> None:
    limits = mesh_limits()
    print(f"18/54 mesh at module 2: {str(limits['status']).upper()}")
    for name, factor in limits["factors"].items():  # type: ignore[union-attr]
        print(f"  {name:<20} n = {factor}")
    for name, (parameter, value) in limits["levers"].items():  # type: ignore[union-attr]
        stated = f"{value:.2f}" if value is not None else "lower"
        print(f"  {name:<20} -> {parameter} {stated}")
    print("  -> the two stress checks want two different modules; the module enters twice")


if __name__ == "__main__":
    main()
