"""The industrial discipline pack: declare a fixture element, get a scorecard.

The industrial pack serves the machine-builder's flat work — covers, fixture
plates, panels, guards — the way :mod:`anvilate.packs.structural` serves
AISC-flavored members. A :class:`CoverPlate` declares a plate's plan shape
(rectangular or circular), edge condition, uniform design pressure, thickness,
and material; :func:`screen_cover_plate` dispatches to the matching closed-form
plate check in :mod:`anvilate.analysis`, screens the peak bending stress
against the material yield and, when limits are set, the deflection and the
fundamental frequency against them (the plate's mass per area comes from its
material density — one declaration drives every screen). "No silent green"
carries through, and every entry cites the theory the
check implements (the plate checks are handbook theory, not a design code —
the screening label stays with the engineer of record).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import ConfigDict, model_validator

from .._models import Named
from ..analysis import (
    clamped_annular_plate_uniform_load,
    clamped_circular_plate_uniform_load,
    clamped_plate_uniform_load,
    deflection_scorecard,
    frequency_scorecard,
    plate_fundamental_frequency_derivation,
    simply_supported_annular_plate_uniform_load,
    simply_supported_circular_plate_uniform_load,
    simply_supported_plate_center_patch_load,
    simply_supported_plate_uniform_load,
    strength_scorecard,
)
from ..derivation import Derivation, SymbolValue
from ..scorecard import Scorecard
from ..standards import AllowableBasis, MaterialsDatabase, default_materials_db
from ..units import Quantity
from ._guarded import DESIGN_BASIS, GuardedInputs, design_allowable, disclosed

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


class CoverPlate(GuardedInputs):
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
    one plate with an exact patch solution. Declaring a ``min_frequency``
    adds the resonance screen: the fundamental frequency of the bare plate
    (mass per area from the material's density and the thickness — smeared
    attachments are not modeled) against that floor. A circular cover may
    declare a concentric free-edged ``hole_diameter`` (a sight port, a
    gland bore) — the annular closed form replaces the solid one, and the
    resonance screen switches to the annular eigenvalue table (hole up to
    0.8 of the diameter).
    """

    model_config = ConfigDict(frozen=True)

    name: Named
    pressure: Quantity
    thickness: Quantity
    material: str
    edge: PlateEdge = PlateEdge.SIMPLY_SUPPORTED
    length: Quantity | None = None
    width: Quantity | None = None
    diameter: Quantity | None = None
    hole_diameter: Quantity | None = None  # a concentric free-edged hole (circular only)
    patch_length: Quantity | None = None  # pressure may act on a centred footprint
    patch_width: Quantity | None = None
    deflection_limit: Quantity | None = None
    min_frequency: Quantity | None = None  # the resonance floor

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
            (self.hole_diameter, "hole_diameter"),
            (self.patch_length, "patch_length"),
            (self.patch_width, "patch_width"),
            (self.deflection_limit, "deflection_limit"),
        ):
            if value is not None and not value.has_dimension("[length]"):
                raise ValueError(f"{name} must be a [length] quantity; got {value}")
        if self.min_frequency is not None and not self.min_frequency.has_dimension("[frequency]"):
            raise ValueError(
                f"min_frequency must be a [frequency] quantity; got {self.min_frequency}"
            )
        if self.hole_diameter is not None and self.diameter is None:
            raise ValueError("a hole is only encoded for a circular cover — declare a diameter")
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
    required_basis: AllowableBasis = DESIGN_BASIS,
) -> Scorecard:
    """Screen a :class:`CoverPlate` and return its scorecard.

    Dispatches on the cover's shape and edge condition to the matching
    closed-form plate check, screens the peak bending stress against the
    material's yield at ``required_safety_factor``, and — when the cover
    declares them — the centre deflection against ``deflection_limit`` and
    the bare plate's fundamental frequency against ``min_frequency``.
    ``materials`` defaults to the bundled database.
    """
    materials = materials or default_materials_db()
    record = materials.get(plate.material)
    plate_allowable = design_allowable(
        record, "yield_strength", material_id=plate.material, basis=required_basis
    )

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
    elif plate.hole_diameter is not None:
        annular_check = (
            clamped_annular_plate_uniform_load
            if plate.edge is PlateEdge.CLAMPED
            else simply_supported_annular_plate_uniform_load
        )
        result = annular_check(diameter=plate.diameter, hole_diameter=plate.hole_diameter, **common)
        reference = "Kirchhoff plate theory (axisymmetric closed form)"
    elif circular:
        result = check(diameter=plate.diameter, **common)
    else:
        result = check(length=plate.length, width=plate.width, **common)

    # Assembled by the case, not here. This block used to name the symbols itself and only
    # for a round cover, so the clamped rectangle — whose stress and deflection are as
    # closed a form as any circular one, on two coefficients read out of Roark Table 11.4 —
    # rendered a bare table. And the flatness entry below rendered its limit with nothing
    # behind it on every case, including the four whose deflection is one line.
    bending_update: dict = {"reference": reference}
    stress_work = result.stress_derivation(reference)
    if stress_work is not None:
        bending_update["derivation"] = stress_work
    elif plate_allowable.quantity is not None:
        # A bending entry whose stress is a series sum or a radius scan cannot show that
        # stress as a line — but what this entry decides is a quotient, and the quotient
        # is worth showing with the stress declared as an input that says where it came
        # from. Written for these two cases rather than folded into `strength_scorecard`
        # on purpose: a margin line added to every strength check in the library would
        # raise the derivation-coverage ratio without a reviewer learning anything, which
        # is the meter measuring itself. Here the gloss carries the part that is not
        # arithmetic.
        bending_update["derivation"] = Derivation(
            symbolic="n = σ_allow/σ",
            inputs=(
                SymbolValue(
                    symbol="σ_allow",
                    description="allowable stress for the cover material",
                    value=plate_allowable.quantity,
                    unit="MPa",
                ),
                SymbolValue(
                    symbol="σ",
                    description=(
                        f"peak surface bending stress in the cover — {result.underived.reason}"
                    ),
                    value=result.max_bending_stress,
                    unit="MPa",
                ),
            ),
            result=SymbolValue(
                symbol="n",
                description="margin of the allowable over the peak bending stress",
                value=plate_allowable.quantity.to("MPa").magnitude
                / result.max_bending_stress.to("MPa").magnitude,
            ),
            citation=reference,
        )
    entries = [
        strength_scorecard(
            f"{plate.name} plate bending",
            stress=result.max_bending_stress,
            allowable=plate_allowable.quantity,
            required=required_safety_factor,
            unavailable_detail=plate_allowable.note,
        ).model_copy(update=bending_update)
    ]
    if plate.deflection_limit is not None:
        flatness_update: dict = {"reference": reference}
        deflection_work = result.deflection_derivation(reference)
        if deflection_work is not None:
            flatness_update["derivation"] = deflection_work
        else:
            flatness_update["underived"] = result.underived
        entries.append(
            deflection_scorecard(
                f"{plate.name} flatness",
                deflection=result.max_deflection,
                limit=plate.deflection_limit,
            ).model_copy(update=flatness_update)
        )
    if plate.min_frequency is not None:
        mass_per_area = Quantity(
            magnitude=record.density.quantity.to("kg/m**3").magnitude
            * plate.thickness.to("m").magnitude,
            unit="kg/m**2",
        )
        # One call, and it does the dispatching. This block used to hold a second copy of
        # the case table and a third of the theory names, pick a check from one and a
        # citation from the other, and then patch the citation by hand for a holed cover —
        # four places to keep in step for a screen that has one answer. The frequency now
        # comes out of the same record that carries the expression which produced it, so
        # the resonance entry cannot cite a theory it did not use.
        modal_work = plate_fundamental_frequency_derivation(
            mass_per_area=mass_per_area,
            thickness=plate.thickness,
            elastic_modulus=record.elastic_modulus.quantity,
            length=plate.length,
            width=plate.width,
            diameter=plate.diameter,
            hole_diameter=plate.hole_diameter,
            clamped=plate.edge is PlateEdge.CLAMPED,
        )
        entries.append(
            frequency_scorecard(
                f"{plate.name} resonance",
                frequency=modal_work.result.value,
                min_frequency=plate.min_frequency,
            ).model_copy(update={"reference": modal_work.citation, "derivation": modal_work})
        )
    return disclosed(
        Scorecard(entries=tuple(entries)),
        plate_allowable,
    )
