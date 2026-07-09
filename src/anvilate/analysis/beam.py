"""T1 analytical beam checks (closed-form, no solver).

The T1 validation tier screens a design with handbook closed-form solutions before
any FEA. This module implements the classic Roark / Shigley cases — a cantilever with an
end load, and a simply-supported beam with a central load — reporting the maximum
bending stress and the maximum deflection. Every input and output is a
dimension-checked :class:`~anvilate.units.Quantity`, and the arithmetic runs
through Pint so the units carry through and validate themselves.

These are screening checks, not certified analysis — they assume a prismatic
linear-elastic beam, small deflections, and no stress concentration.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "BeamBendingResult",
    "cantilever_end_load",
    "simply_supported_center_load",
    "rectangular_second_moment",
    "max_transverse_shear_stress",
    "SHEAR_FORM_RECTANGULAR",
    "SHEAR_FORM_CIRCULAR",
]

# Peak-to-average transverse-shear form factors τ_max = k·V/A: 3/2 at the neutral
# axis of a rectangular section, 4/3 for a solid circular one.
SHEAR_FORM_RECTANGULAR = 1.5
SHEAR_FORM_CIRCULAR = 4.0 / 3.0


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _as_quantity(pint_value, unit: str) -> Quantity:
    """Wrap a computed Pint quantity as a :class:`Quantity` in ``unit``."""
    converted = pint_value.to(unit)
    return Quantity(magnitude=float(converted.magnitude), unit=unit)


def rectangular_second_moment(width: Quantity, height: Quantity) -> Quantity:
    """The area second moment I = b·h³/12 of a rectangular section about its
    neutral (bending) axis, ``height`` being the dimension in the load direction."""
    _require(width, "[length]", "width")
    _require(height, "[length]", "height")
    return _as_quantity(width.pint * height.pint**3 / 12, "mm**4")


def max_transverse_shear_stress(
    *,
    shear_force: Quantity,
    area: Quantity,
    form_factor: float = SHEAR_FORM_RECTANGULAR,
) -> Quantity:
    """The peak transverse shear stress τ_max = k·V/A in a beam cross-section.

    The transverse shear peaks above the average V/A at the neutral axis; the
    ``form_factor`` k captures the section shape — :data:`SHEAR_FORM_RECTANGULAR`
    (1.5) or :data:`SHEAR_FORM_CIRCULAR` (4/3). Short, deep beams fail here rather
    than in bending. ``shear_force`` must be a force and ``area`` an area;
    ``form_factor`` must be positive. Returns the shear stress in MPa.
    """
    _require(shear_force, "[force]", "shear_force")
    _require(area, "[length]**2", "area")
    if form_factor <= 0:
        raise ValueError(f"form_factor must be positive; got {form_factor}")
    stress = form_factor * shear_force.pint / area.pint
    return _as_quantity(stress, "MPa")


class BeamBendingResult(BaseModel):
    """The result of a closed-form beam bending check.

    ``max_bending_stress`` is the peak bending stress; ``max_deflection`` is the
    peak deflection (at the free end for a cantilever, at mid-span for a
    simply-supported beam). Both are screening estimates for a prismatic
    linear-elastic beam under small deflections.
    """

    model_config = ConfigDict(frozen=True)

    max_bending_stress: Quantity
    max_deflection: Quantity

    def bending_safety_factor(self, yield_strength: Quantity) -> float:
        """The factor of safety against yielding: yield strength / peak stress.

        ``yield_strength`` must be a stress (pressure), else :class:`ValueError`.
        A value below 1 means the beam yields under this load.
        """
        _require(yield_strength, "[pressure]", "yield_strength")
        sy = yield_strength.to("MPa").magnitude
        sigma = self.max_bending_stress.to("MPa").magnitude
        return sy / sigma

    def __str__(self) -> str:
        return (
            f"beam: sigma_max {self.max_bending_stress.to('MPa')}, "
            f"delta_max {self.max_deflection.to('mm')}"
        )


def cantilever_end_load(
    *,
    force: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The Roark/Shigley cantilever-with-end-load check.

    A prismatic beam of length ``length`` and section second moment
    ``second_moment`` (about the bending axis), fixed at one end and carrying a
    transverse ``force`` at the free end. ``extreme_fibre`` is the distance from
    the neutral axis to the outermost fibre (c, e.g. half the height of a
    rectangular section); ``elastic_modulus`` is the material's Young's modulus.

    Returns the peak bending stress at the fixed end (σ = M·c/I with M = F·L) and
    the free-end deflection (δ = F·L³/(3·E·I)). Every argument is dimension-checked.
    For a rectangular section, :func:`rectangular_second_moment` gives I and c is
    half the height.
    """
    _require(force, "[force]", "force")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = f * length_p
    stress = moment * c / inertia
    deflection = f * length_p**3 / (3 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )


def simply_supported_center_load(
    *,
    force: Quantity,
    length: Quantity,
    second_moment: Quantity,
    extreme_fibre: Quantity,
    elastic_modulus: Quantity,
) -> BeamBendingResult:
    """The Roark/Shigley simply-supported-beam, central-load check.

    A prismatic beam simply supported at both ends over a span ``length``, with a
    transverse ``force`` at mid-span. Arguments match :func:`cantilever_end_load`.

    Returns the peak bending stress at mid-span (σ = M·c/I with M = F·L/4) and the
    mid-span deflection (δ = F·L³/(48·E·I)). Every argument is dimension-checked.
    """
    _require(force, "[force]", "force")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(extreme_fibre, "[length]", "extreme_fibre")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    f = force.pint
    length_p = length.pint
    inertia = second_moment.pint
    c = extreme_fibre.pint
    e = elastic_modulus.pint

    moment = f * length_p / 4
    stress = moment * c / inertia
    deflection = f * length_p**3 / (48 * e * inertia)
    return BeamBendingResult(
        max_bending_stress=_as_quantity(stress, "MPa"),
        max_deflection=_as_quantity(deflection, "mm"),
    )
