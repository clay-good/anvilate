"""The industrial discipline pack: declare a fixture element, get a scorecard.

The industrial pack serves the machine-builder's flat work — covers, fixture
plates, panels, guards — the way :mod:`anvilate.packs.structural` serves
AISC-flavored members. A :class:`CoverPlate` declares a plate's plan shape
(rectangular or circular), edge condition, uniform design pressure, thickness,
and material; :func:`screen_cover_plate` dispatches to the matching closed-form
plate check in :mod:`anvilate.analysis`, screens the peak bending stress
against the material yield and, when a limit is set, the deflection against
it. "No silent green" carries through, and every entry cites the theory the
check implements (the plate checks are handbook theory, not a design code —
the screening label stays with the engineer of record).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from ..analysis import (
    clamped_circular_plate_uniform_load,
    clamped_plate_uniform_load,
    deflection_scorecard,
    simply_supported_circular_plate_uniform_load,
    simply_supported_plate_center_patch_load,
    simply_supported_plate_uniform_load,
    strength_scorecard,
)
from ..scorecard import Scorecard
from ..standards import MaterialsDatabase, default_materials_db
from ..units import Quantity

__all__ = [
    "PlateEdge",
    "CoverPlate",
    "screen_cover_plate",
]


class PlateEdge(StrEnum):
    """How a cover's rim is held: free to rotate (gasketed, clipped) or built in
    (welded all around, or bolted stiffly enough to hold the edge slope)."""

    SIMPLY_SUPPORTED = "simply_supported"
    CLAMPED = "clamped"


# (is_circular, edge) -> the analysis check; each entry also names the theory
# the scorecard cites (handbook theory, not a design-code clause).
_PLATE_CHECKS = {
    (False, PlateEdge.SIMPLY_SUPPORTED): (
        simply_supported_plate_uniform_load,
        "Kirchhoff plate theory (Navier series)",
    ),
    (False, PlateEdge.CLAMPED): (
        clamped_plate_uniform_load,
        "Roark's Formulas, Table 11.4",
    ),
    (True, PlateEdge.SIMPLY_SUPPORTED): (
        simply_supported_circular_plate_uniform_load,
        "Timoshenko plate theory",
    ),
    (True, PlateEdge.CLAMPED): (
        clamped_circular_plate_uniform_load,
        "Timoshenko plate theory",
    ),
}


class CoverPlate(BaseModel):
    """A flat cover or panel under uniform pressure, and what its screen needs.

    Declare the plan geometry one way or the other: ``length`` and ``width``
    for a rectangle, or ``diameter`` for a round blank — exactly one. ``edge``
    picks the rim condition (simply supported by default — a clamped claim
    should be backed by a weld or a stiff bolt circle). ``pressure`` is the
    uniform design pressure, ``material`` a database id (its E and yield drive
    the checks), and an optional ``deflection_limit`` adds the flatness screen.
    Declaring a centred ``patch_length`` × ``patch_width`` footprint (a machine
    foot or pedestal instead of a full-face pressure) restricts ``pressure``
    to that footprint — encoded only for a simply-supported rectangle, the
    one plate with an exact patch solution.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    pressure: Quantity
    thickness: Quantity
    material: str
    edge: PlateEdge = PlateEdge.SIMPLY_SUPPORTED
    length: Quantity | None = None
    width: Quantity | None = None
    diameter: Quantity | None = None
    patch_length: Quantity | None = None  # pressure may act on a centred footprint
    patch_width: Quantity | None = None
    deflection_limit: Quantity | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> CoverPlate:
        if not self.pressure.has_dimension("[pressure]"):
            raise ValueError(f"pressure must be a [pressure] quantity; got {self.pressure}")
        if not self.thickness.has_dimension("[length]"):
            raise ValueError(f"thickness must be a [length] quantity; got {self.thickness}")
        rectangular = self.length is not None or self.width is not None
        if rectangular and self.diameter is not None:
            raise ValueError("declare length/width for a rectangle OR diameter for a circle")
        if rectangular and (self.length is None or self.width is None):
            raise ValueError("a rectangular cover needs both length and width")
        if not rectangular and self.diameter is None:
            raise ValueError("declare the plan geometry: length and width, or diameter")
        for value, name in (
            (self.length, "length"),
            (self.width, "width"),
            (self.diameter, "diameter"),
            (self.patch_length, "patch_length"),
            (self.patch_width, "patch_width"),
            (self.deflection_limit, "deflection_limit"),
        ):
            if value is not None and not value.has_dimension("[length]"):
                raise ValueError(f"{name} must be a [length] quantity; got {value}")
        patched = self.patch_length is not None or self.patch_width is not None
        if patched:
            if self.patch_length is None or self.patch_width is None:
                raise ValueError("a patch footprint needs both patch_length and patch_width")
            if self.diameter is not None or self.edge is not PlateEdge.SIMPLY_SUPPORTED:
                raise ValueError(
                    "a patch footprint is only encoded for a simply-supported "
                    "rectangular cover — the one plate with an exact patch solution"
                )
        return self


def screen_cover_plate(
    plate: CoverPlate,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`CoverPlate` and return its scorecard.

    Dispatches on the cover's shape and edge condition to the matching
    closed-form plate check, screens the peak bending stress against the
    material's yield at ``required_safety_factor``, and — when the cover
    declares a ``deflection_limit`` — the centre deflection against it.
    ``materials`` defaults to the bundled database.
    """
    materials = materials or default_materials_db()
    record = materials.get(plate.material)

    circular = plate.diameter is not None
    check, reference = _PLATE_CHECKS[(circular, plate.edge)]
    common = {
        "pressure": plate.pressure,
        "thickness": plate.thickness,
        "elastic_modulus": record.elastic_modulus.quantity,
    }
    if plate.patch_length is not None:
        result = simply_supported_plate_center_patch_load(
            patch_length=plate.patch_length,
            patch_width=plate.patch_width,
            length=plate.length,
            width=plate.width,
            **common,
        )
    elif circular:
        result = check(diameter=plate.diameter, **common)
    else:
        result = check(length=plate.length, width=plate.width, **common)

    entries = [
        strength_scorecard(
            f"{plate.name} plate bending",
            stress=result.max_bending_stress,
            allowable=record.yield_strength.quantity,
            required=required_safety_factor,
        ).model_copy(update={"reference": reference})
    ]
    if plate.deflection_limit is not None:
        entries.append(
            deflection_scorecard(
                f"{plate.name} flatness",
                deflection=result.max_deflection,
                limit=plate.deflection_limit,
            ).model_copy(update={"reference": reference})
        )
    return Scorecard(entries=tuple(entries))
