"""T1 analytical electrical discharge machining (EDM) checks (closed-form).

Electrical discharge machining erodes metal with a rapid train of electrical sparks jumping a small
gap between a shaped electrode and the workpiece, both submerged in a dielectric. Each spark melts
and vaporizes a tiny crater; thousands per second add up to a cut. Like the electrochemical
dissolution of :mod:`anvilate.analysis.ecm`, EDM touches the work with no force and does not care
how hard the metal is — it machines hardened dies and carbide that no cutter will touch. What it
trades on instead is a tension between speed and finish: bigger sparks cut faster but leave rougher
craters
and a wider gap, so the same machine roughs on high energy and finishes on low.

Three numbers describe the spark train. The discharge energy per pulse E = U·I·t_on is the crater
maker — the gap voltage U and peak current I over the pulse-on time t_on — and it sets the surface
roughness and the spark gap. The duty factor τ = t_on/(t_on + t_off) is the fraction of the cycle
actually discharging, the rest spent flushing debris in the off time; it is the efficiency knob. The
material removal rate MRR = k·I·τ ties them to throughput through the metal's erosion coefficient k:
the average current I·τ, times how much volume each ampere-second erodes. Raising I or τ speeds the
cut but coarsens it — the roughing-versus-finishing choice made numerical.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "edm_discharge_energy",
    "edm_duty_factor",
    "edm_material_removal_rate",
]


def edm_discharge_energy(
    *, gap_voltage: Quantity, peak_current: Quantity, pulse_on_time: Quantity
) -> Quantity:
    """The discharge energy per pulse, E = U·I·t_on.

    The energy a single spark dumps into the work: the ``gap_voltage`` U across the discharge, the
    ``peak_current`` I it carries, and the ``pulse_on_time`` t_on it lasts, E = U·I·t_on. It is the
    crater-maker — bigger pulses melt more metal per spark, cutting faster but leaving a rougher
    surface and a wider spark gap (overcut), which is why finishing runs low energy and roughing
    high. Returns the discharge energy in mJ.
    """
    _check(gap_voltage, "[electric_potential]", "gap_voltage")
    _check(peak_current, "[current]", "peak_current")
    _check(pulse_on_time, "[time]", "pulse_on_time")
    u = gap_voltage.to("V").magnitude
    i = peak_current.to("A").magnitude
    t_on = pulse_on_time.to("s").magnitude
    if u <= 0:
        raise ValueError("gap_voltage must be positive")
    if i <= 0:
        raise ValueError("peak_current must be positive")
    if t_on <= 0:
        raise ValueError("pulse_on_time must be positive")
    return Quantity(magnitude=u * i * t_on * 1000.0, unit="mJ")


def edm_duty_factor(*, pulse_on_time: Quantity, pulse_off_time: Quantity) -> float:
    """The duty factor, τ = t_on/(t_on + t_off).

    The fraction of each spark cycle actually discharging: the ``pulse_on_time`` t_on over the full
    period, the on time plus the ``pulse_off_time`` t_off the machine waits to let the dielectric
    de-ionize and flush debris, τ = t_on/(t_on + t_off). A high duty factor spends more of the cycle
    cutting and raises the removal rate (:func:`edm_material_removal_rate`), but too little off time
    fails to clear debris and risks a stable arc that damages the surface. Returns the duty factor
    as a fraction (0 to 1).
    """
    _check(pulse_on_time, "[time]", "pulse_on_time")
    _check(pulse_off_time, "[time]", "pulse_off_time")
    t_on = pulse_on_time.to("s").magnitude
    t_off = pulse_off_time.to("s").magnitude
    if t_on <= 0:
        raise ValueError("pulse_on_time must be positive")
    if t_off < 0:
        raise ValueError("pulse_off_time must be non-negative")
    return t_on / (t_on + t_off)


def edm_material_removal_rate(
    *, erosion_coefficient: Quantity, peak_current: Quantity, duty_factor: float
) -> Quantity:
    """The EDM material removal rate, MRR = k·I·τ.

    The volume of metal eroded per unit time: the metal's ``erosion_coefficient`` k (the volume each
    ampere of average current removes per minute, a material-and-polarity property in mm³/(min·A))
    times the average current — the ``peak_current`` I scaled by the ``duty_factor`` τ (from
    :func:`edm_duty_factor`) — so MRR = k·I·τ. Removal tracks average current, so more current or a
    higher duty factor cuts faster, at the cost of the rougher surface the larger discharge energy
    (:func:`edm_discharge_energy`) brings. Returns the removal rate in mm**3/min.
    """
    _check(erosion_coefficient, "[length]**3/([time]*[current])", "erosion_coefficient")
    _check(peak_current, "[current]", "peak_current")
    _fraction(duty_factor, "duty_factor")
    k = erosion_coefficient.to("mm**3/(min*A)").magnitude
    i = peak_current.to("A").magnitude
    if k <= 0:
        raise ValueError("erosion_coefficient must be positive")
    if i <= 0:
        raise ValueError("peak_current must be positive")
    return Quantity(magnitude=k * i * duty_factor, unit="mm**3/min")


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be a fraction in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
