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

from ..units import Quantity

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
        raise ValueError("magnetic_flux_density must be non-negative")
    if ell <= 0:
        raise ValueError("conductor_length must be positive")
    if v < 0:
        raise ValueError("velocity must be non-negative")
    return Quantity(magnitude=b * ell * v, unit="V")


def faraday_induced_emf(
    *, turns: float, flux_change: Quantity, time_interval: Quantity
) -> Quantity:
    """The Faraday induced EMF, EMF = N·ΔΦ/Δt.

    The average voltage a coil of ``turns`` N develops when the magnetic flux through it changes by
    ``flux_change`` ΔΦ over ``time_interval`` Δt: EMF = N·ΔΦ/Δt (magnitude; Lenz's law makes it
    oppose the change). This is how transformers and generators induce voltage. Returns EMF in V.
    """
    _check(flux_change, "[magnetic_flux]", "flux_change")
    _check(time_interval, "[time]", "time_interval")
    dphi = flux_change.to("Wb").magnitude
    dt = time_interval.to("s").magnitude
    if turns <= 0:
        raise ValueError("turns must be positive")
    if dt <= 0:
        raise ValueError("time_interval must be positive")
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
        raise ValueError("inductance must be positive")
    if dt <= 0:
        raise ValueError("time_interval must be positive")
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
        raise ValueError("mutual_inductance must be positive")
    if dt <= 0:
        raise ValueError("time_interval must be positive")
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
        raise ValueError("mutual_inductance must be non-negative")
    if l1 <= 0 or l2 <= 0:
        raise ValueError("primary_inductance and secondary_inductance must be positive")
    k = m / sqrt(l1 * l2)
    if k > 1.0:
        raise ValueError(
            "mutual_inductance cannot exceed sqrt(L1*L2) (coupling coefficient would exceed 1)"
        )
    return k


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
