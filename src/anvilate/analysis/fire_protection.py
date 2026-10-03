"""T1 analytical fire-sprinkler hydraulic checks (NFPA K-factor, closed-form).

A fire sprinkler discharges water at a rate set by its orifice and the pressure behind it, captured
by the sprinkler's K-factor: the flow is Q = K·√P, so the discharge rises with the square root of
the supply pressure. The K-factor bundles the orifice size and discharge coefficient into one
number a data sheet lists (a standard-response head is K ≈ 5.6 gpm/psi^½, a large-drop head much
higher), and it is the basis of every branch-line and remote-area hydraulic calculation.

Two relations follow. The discharge Q = K·√P gives the flow a head delivers at a known residual
pressure — checked against the density the hazard demands. Inverting it, the pressure a head needs
to deliver a required flow is P = (Q/K)², the value that must be available at the most remote head
and that the demand curve is built up from back toward the supply. The K-factor carries mixed units
by convention (gpm/psi^½ in US practice, L/min/bar^½ in metric); pass it as a consistent
:class:`~anvilate.units.Quantity` and the pressures and flows are dimension-checked.
"""

from __future__ import annotations

from math import sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_SPRINKLER_SOURCE = "the sprinkler's listed K-factor from its data sheet"
_HYDRAULIC_SOURCE = "the sprinkler system's hydraulic calculation (pressure or design flow)"
_FLOW_TEST_SOURCE = "the hydrant flow-test record (outlet diameter, coefficient, and pitot reading)"


class _FireProtectionInputError(RefusalError, ValueError):
    """A fire-sprinkler hydraulic input that cannot be used without correction."""


def _fire_protection_refusal(
    message: str, *, subject: str, source: str
) -> _FireProtectionInputError:
    return _FireProtectionInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _fire_protection_input_source(name: str) -> str:
    if name == "k_factor":
        return _SPRINKLER_SOURCE
    if name in {"discharge_coefficient", "outlet_diameter", "pitot_pressure"}:
        return _FLOW_TEST_SOURCE
    return _HYDRAULIC_SOURCE


_K_DIMENSION = "[volume] / [time] / [pressure]**0.5"

__all__ = [
    "hydrant_flow_test",
    "sprinkler_discharge",
    "sprinkler_pressure_for_flow",
]


def sprinkler_discharge(*, k_factor: Quantity, pressure: Quantity) -> Quantity:
    """The flow a sprinkler discharges, Q = K·√P.

    The water a fire sprinkler delivers at a residual ``pressure`` P behind its orifice: Q = K·√P,
    from the head's ``k_factor`` K (its orifice-and-discharge-coefficient constant, e.g.
    5.6 gpm/psi^½ for a standard-response head). Because the flow follows the square root of
    pressure, doubling the flow takes four times the pressure — the reason a hydraulically remote
    head governs a system's demand. ``k_factor`` must carry the flow-over-root-pressure dimension
    and ``pressure`` be a positive pressure. Returns the discharge in gallons per minute.
    """
    if not isinstance(k_factor, Quantity):
        raise _fire_protection_refusal(
            f"k_factor must be a {_K_DIMENSION} quantity; got {k_factor!r}",
            subject="k_factor",
            source=_SPRINKLER_SOURCE,
        )
    if not k_factor.has_dimension(_K_DIMENSION):
        raise _fire_protection_refusal(
            f"k_factor must be a {_K_DIMENSION} quantity; got "
            f"{k_factor.dimensionality} ({k_factor})",
            subject="k_factor",
            source=_SPRINKLER_SOURCE,
        )
    _check(pressure, "[pressure]", "pressure")
    k = k_factor.to("gallon/minute/psi**0.5").magnitude
    p = pressure.to("psi").magnitude
    if k <= 0:
        raise _fire_protection_refusal(
            "k_factor must be positive", subject="k_factor", source=_SPRINKLER_SOURCE
        )
    if p < 0:
        raise _fire_protection_refusal(
            "pressure must be non-negative", subject="pressure", source=_HYDRAULIC_SOURCE
        )
    return Quantity(magnitude=k * sqrt(p), unit="gallon/minute")


def sprinkler_pressure_for_flow(*, k_factor: Quantity, flow_rate: Quantity) -> Quantity:
    """The pressure a sprinkler needs for a target flow, P = (Q/K)².

    The design inverse of :func:`sprinkler_discharge`: to deliver a required ``flow_rate`` Q the
    head must see a residual pressure P = (Q/``k_factor`` K)². It is the pressure demanded at the
    most remote sprinkler to meet the hazard's design density, and the starting point a branch-line
    hydraulic calculation accumulates from toward the source. Because it goes as the square of flow,
    pushing more water out of a fixed orifice costs pressure quickly. Returns the required pressure
    in psi.
    """
    if not isinstance(k_factor, Quantity):
        raise _fire_protection_refusal(
            f"k_factor must be a {_K_DIMENSION} quantity; got {k_factor!r}",
            subject="k_factor",
            source=_SPRINKLER_SOURCE,
        )
    if not k_factor.has_dimension(_K_DIMENSION):
        raise _fire_protection_refusal(
            f"k_factor must be a {_K_DIMENSION} quantity; got "
            f"{k_factor.dimensionality} ({k_factor})",
            subject="k_factor",
            source=_SPRINKLER_SOURCE,
        )
    _check(flow_rate, "[volume]/[time]", "flow_rate")
    k = k_factor.to("gallon/minute/psi**0.5").magnitude
    q = flow_rate.to("gallon/minute").magnitude
    if k <= 0:
        raise _fire_protection_refusal(
            "k_factor must be positive", subject="k_factor", source=_SPRINKLER_SOURCE
        )
    if q < 0:
        raise _fire_protection_refusal(
            "flow_rate must be non-negative", subject="flow_rate", source=_HYDRAULIC_SOURCE
        )
    return Quantity(magnitude=(q / k) ** 2, unit="psi")


def hydrant_flow_test(
    *,
    outlet_diameter: Quantity,
    pitot_pressure: Quantity,
    discharge_coefficient: float = 0.9,
) -> Quantity:
    """The flow from a hydrant outlet in a flow test, Q = 29.83·c·d²·√P.

    The standard fire-flow-test relation (NFPA 291): the water leaving a hydrant butt is
    Q = 29.83·c·d²·√P, from the ``outlet_diameter`` d, the ``pitot_pressure`` P read at the outlet
    with a pitot gauge, and the ``discharge_coefficient`` c for the outlet shape (0.90 for a smooth,
    rounded outlet — the default; 0.80 for a square-edged one, 0.70 for one that projects into the
    barrel). The 29.83 constant carries the customary units, so the diameter is taken in inches and
    the pitot pressure in psi and the flow returned in gpm. It converts a field pitot reading into
    the flow a hydrant was delivering, the raw data of a water-supply capacity test. Returns the
    flow in gallons per minute.
    """
    _check(outlet_diameter, "[length]", "outlet_diameter")
    _check(pitot_pressure, "[pressure]", "pitot_pressure")
    if not 0.0 < discharge_coefficient <= 1.0:
        raise _fire_protection_refusal(
            f"discharge_coefficient must be in (0, 1]; got {discharge_coefficient}",
            subject="discharge_coefficient",
            source=_FLOW_TEST_SOURCE,
        )
    d = outlet_diameter.to("inch").magnitude
    p = pitot_pressure.to("psi").magnitude
    if d <= 0:
        raise _fire_protection_refusal(
            "outlet_diameter must be positive", subject="outlet_diameter", source=_FLOW_TEST_SOURCE
        )
    if p < 0:
        raise _fire_protection_refusal(
            "pitot_pressure must be non-negative",
            subject="pitot_pressure",
            source=_FLOW_TEST_SOURCE,
        )
    return Quantity(magnitude=29.83 * discharge_coefficient * d**2 * sqrt(p), unit="gallon/minute")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _fire_protection_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_fire_protection_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _fire_protection_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_fire_protection_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
