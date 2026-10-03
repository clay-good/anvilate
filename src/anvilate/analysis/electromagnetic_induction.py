"""T1 analytical electromagnetic-induction (Faraday) checks (closed-form).

A changing magnetic flux drives a voltage — the effect behind every generator, transformer, and
inductor. Faraday's law sets the voltage a coil sees when the flux through it changes, a conductor
moving through a field develops the same voltage along its length, and a coil resists changes in its
own current with a back-EMF. This is the source side of the magnetic-actuator and magnetic-circuit
relations of :mod:`anvilate.analysis.magnetics` and the energy/time-constant relations of
:mod:`anvilate.analysis.reactive_circuit`.

A conductor of length L moving at speed v across a field B cuts flux lines and develops the motional
EMF = B·L·v — the voltage of a simple generator rod. More generally, a coil of N turns linking a
flux that changes by ΔΦ over a time Δt sees the Faraday EMF = N·ΔΦ/Δt (magnitude; Lenz's law fixes
the sign to oppose the change). A coil also opposes changes in its own current, developing the
self-induced back-EMF = L·ΔI/Δt from its inductance L. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_FIELD_SOURCE = "the magnet design or measured flux density and the conductor geometry"
_COIL_SOURCE = "the coil datasheet or measured inductances and turn count"
_EVENT_SOURCE = "the switching or motion event record (changes, speed, and duration)"


class _ElectromagneticInductionInputError(RefusalError, ValueError):
    """An electromagnetic-induction input that cannot be used without correction."""


def _electromagnetic_induction_refusal(
    message: str, *, subject: str, source: str
) -> _ElectromagneticInductionInputError:
    return _ElectromagneticInductionInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _electromagnetic_induction_input_source(name: str) -> str:
    if name in {"conductor_length", "magnetic_flux_density"}:
        return _FIELD_SOURCE
    if name in {
        "inductance",
        "mutual_inductance",
        "primary_inductance",
        "secondary_inductance",
        "turns",
    }:
        return _COIL_SOURCE
    return _EVENT_SOURCE


__all__ = [
    "coupling_coefficient",
    "faraday_induced_emf",
    "motional_emf",
    "mutual_inductance_emf",
    "self_induced_emf",
]


def motional_emf(
    *, magnetic_flux_density: Quantity, conductor_length: Quantity, velocity: Quantity
) -> Quantity:
    """The motional EMF, EMF = B·L·v.

    The voltage developed along a conductor of ``conductor_length`` L moving at ``velocity`` v
    perpendicular to a field ``magnetic_flux_density`` B: EMF = B·L·v. It is the output of a simple
    generator rod sliding on rails and the basis of a homopolar generator. Returns the EMF in V.
    """
    _check(magnetic_flux_density, "[magnetic_field]", "magnetic_flux_density")
    _check(conductor_length, "[length]", "conductor_length")
    _check(velocity, "[velocity]", "velocity")
    b = magnetic_flux_density.to("T").magnitude
    ell = conductor_length.to("m").magnitude
    v = velocity.to("m/s").magnitude
    if b < 0:
        raise _electromagnetic_induction_refusal(
            "magnetic_flux_density must be non-negative",
            subject="magnetic_flux_density",
            source=_FIELD_SOURCE,
        )
    if ell <= 0:
        raise _electromagnetic_induction_refusal(
            "conductor_length must be positive", subject="conductor_length", source=_FIELD_SOURCE
        )
    if v < 0:
        raise _electromagnetic_induction_refusal(
            "velocity must be non-negative", subject="velocity", source=_EVENT_SOURCE
        )
    return Quantity(magnitude=b * ell * v, unit="V")


def faraday_induced_emf(
    *, turns: float, flux_change: Quantity, time_interval: Quantity
) -> Quantity:
    """The Faraday induced EMF, EMF = N·ΔΦ/Δt.

    The average voltage a coil of ``turns`` N develops when the magnetic flux through it changes by
    ``flux_change`` ΔΦ over ``time_interval`` Δt: EMF = N·ΔΦ/Δt (magnitude; Lenz's law makes it
    oppose the change). This is how transformers and generators induce voltage. Returns EMF in V.
    """
    require_finite(turns, name="turns")
    _check(flux_change, "[magnetic_flux]", "flux_change")
    _check(time_interval, "[time]", "time_interval")
    dphi = flux_change.to("Wb").magnitude
    dt = time_interval.to("s").magnitude
    if turns <= 0:
        raise _electromagnetic_induction_refusal(
            "turns must be positive", subject="turns", source=_COIL_SOURCE
        )
    if dt <= 0:
        raise _electromagnetic_induction_refusal(
            "time_interval must be positive", subject="time_interval", source=_EVENT_SOURCE
        )
    return Quantity(magnitude=abs(turns * dphi / dt), unit="V")


def self_induced_emf(
    *, inductance: Quantity, current_change: Quantity, time_interval: Quantity
) -> Quantity:
    """The self-induced (back-) EMF, EMF = L·ΔI/Δt.

    The voltage a coil of ``inductance`` L develops opposing a change in its own current by
    ``current_change`` ΔI over ``time_interval`` Δt: EMF = L·ΔI/Δt. It is the back-EMF that resists
    switching an inductive load and the source of switch-off voltage spikes. Returns the EMF in V.
    """
    _check(inductance, "[inductance]", "inductance")
    _check(current_change, "[current]", "current_change")
    _check(time_interval, "[time]", "time_interval")
    ell = inductance.to("H").magnitude
    di = current_change.to("A").magnitude
    dt = time_interval.to("s").magnitude
    if ell <= 0:
        raise _electromagnetic_induction_refusal(
            "inductance must be positive", subject="inductance", source=_COIL_SOURCE
        )
    if dt <= 0:
        raise _electromagnetic_induction_refusal(
            "time_interval must be positive", subject="time_interval", source=_EVENT_SOURCE
        )
    return Quantity(magnitude=abs(ell * di / dt), unit="V")


def mutual_inductance_emf(
    *, mutual_inductance: Quantity, current_change: Quantity, time_interval: Quantity
) -> Quantity:
    """The mutually-induced EMF, EMF = M·ΔI/Δt.

    The voltage a changing current in one coil induces in a *second*, magnetically coupled coil: for
    a ``mutual_inductance`` M shared by the pair, a primary current changing by ``current_change``
    ΔI over ``time_interval`` Δt drives EMF = M·ΔI/Δt in the secondary. It is the transformer and
    coupled-inductor principle — the M analogue of the :func:`self_induced_emf` L — and it is what
    lets a signal cross a galvanic barrier or a switching current spike into a neighbouring trace.
    Returns the EMF in V.
    """
    _check(mutual_inductance, "[inductance]", "mutual_inductance")
    _check(current_change, "[current]", "current_change")
    _check(time_interval, "[time]", "time_interval")
    m = mutual_inductance.to("H").magnitude
    di = current_change.to("A").magnitude
    dt = time_interval.to("s").magnitude
    if m <= 0:
        raise _electromagnetic_induction_refusal(
            "mutual_inductance must be positive", subject="mutual_inductance", source=_COIL_SOURCE
        )
    if dt <= 0:
        raise _electromagnetic_induction_refusal(
            "time_interval must be positive", subject="time_interval", source=_EVENT_SOURCE
        )
    return Quantity(magnitude=abs(m * di / dt), unit="V")


def coupling_coefficient(
    *,
    mutual_inductance: Quantity,
    primary_inductance: Quantity,
    secondary_inductance: Quantity,
) -> float:
    """The magnetic coupling coefficient of two coils, k = M/√(L₁·L₂).

    How tightly two coils share their flux: k = M/√(L₁·L₂), from the ``mutual_inductance`` M (see
    :func:`mutual_inductance_emf`) and the two self-inductances ``primary_inductance`` L₁ and
    ``secondary_inductance`` L₂. It runs from 0 (no shared flux, independent coils) to 1 (perfect
    coupling, every field line links both — the ideal-transformer limit). A mains transformer on a
    closed core runs k ≈ 0.98–0.999; a loosely coupled air-cored pair for wireless power or a
    resonant tank may sit at 0.3–0.7, where leakage inductance (1 − k²)·L dominates the behaviour. k
    cannot physically exceed 1, so M ≤ √(L₁·L₂); a value above it signals inconsistent inputs and is
    rejected. Returns the dimensionless coupling coefficient.
    """
    _check(mutual_inductance, "[inductance]", "mutual_inductance")
    _check(primary_inductance, "[inductance]", "primary_inductance")
    _check(secondary_inductance, "[inductance]", "secondary_inductance")
    m = mutual_inductance.to("H").magnitude
    l1 = primary_inductance.to("H").magnitude
    l2 = secondary_inductance.to("H").magnitude
    if m < 0:
        raise _electromagnetic_induction_refusal(
            "mutual_inductance must be non-negative",
            subject="mutual_inductance",
            source=_COIL_SOURCE,
        )
    for subject, magnitude in (("primary_inductance", l1), ("secondary_inductance", l2)):
        if magnitude <= 0:
            raise _electromagnetic_induction_refusal(
                "primary_inductance and secondary_inductance must be positive",
                subject=subject,
                source=_COIL_SOURCE,
            )
    k = m / sqrt(l1 * l2)
    if k > 1.0:
        raise _electromagnetic_induction_refusal(
            "mutual_inductance cannot exceed sqrt(L1*L2) (coupling coefficient would exceed 1)",
            subject="mutual_inductance, primary_inductance, and secondary_inductance",
            source=_COIL_SOURCE,
        )
    return k


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _electromagnetic_induction_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_electromagnetic_induction_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _electromagnetic_induction_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_electromagnetic_induction_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
