"""T1 analytical resistance spot-welding checks (closed-form).

Resistance spot welding joins two sheets by clamping them between copper electrodes and passing a
large current through the stack for a few cycles. The metal's own resistance turns that current into
heat right at the interface, melting a small nugget that solidifies into the weld. It is a distinct
branch of the welding family from the arc heat input of :mod:`anvilate.analysis.welding_heat` and
the joint strength of :mod:`anvilate.analysis.weld`: here the physics is Joule heating, and the
craft is delivering just enough heat, fast enough, to melt a nugget without expelling it.

The heat generated follows Joule's law, Q = I²·R·t — quadratic in the ``weld_current`` I, so the
current is the dominant lever, over the contact resistance R at the faying surfaces for the weld
time t. Inverting it gives the current a weld schedule needs, I = √(Q/(R·t)). But only a fraction of
that heat ends up in the nugget; the rest conducts away into the sheets and the water-cooled
electrodes. The energy the nugget itself demands is a melting balance, E = ρ·V·(c·ΔT + L_f) — its
volume raised to the melting point and then melted — and comparing it to Q reveals the low thermal
efficiency (often only a tenth or so) that forces resistance welding to run at thousands of amperes.

Sources: AWS C1.1M (recommended practices for resistance welding) — the Joule heat Q = I²·R·t a
spot weld generates, the current a target heat needs, and the energy to bring the nugget volume
to melting.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity
from ..units.temperature import temperature_difference_kelvin

__all__ = [
    "spot_weld_current_for_heat",
    "spot_weld_heat_generated",
    "spot_weld_nugget_melting_energy",
]


def spot_weld_heat_generated(
    *, weld_current: Quantity, contact_resistance: Quantity, weld_time: Quantity
) -> Quantity:
    """The Joule heat generated, Q = I²·R·t.

    The heat a resistance spot weld dumps at the interface: Joule's law over the weld, the
    ``weld_current`` I squared times the ``contact_resistance`` R at the faying surfaces and the
    ``weld_time`` t, Q = I²·R·t. Because it is quadratic in current, current is the dominant control
    — a small rise in amperes swamps a change in time — the reason schedules are set in kiloamperes.
    Only part of this heat melts the nugget (:func:`spot_weld_nugget_melting_energy`); the rest is
    lost to the sheets and electrodes. Returns the heat in J.
    """
    _check(weld_current, "[current]", "weld_current")
    _check(contact_resistance, "[resistance]", "contact_resistance")
    _check(weld_time, "[time]", "weld_time")
    i = weld_current.to("A").magnitude
    r = contact_resistance.to("ohm").magnitude
    t = weld_time.to("s").magnitude
    if i <= 0:
        raise ValueError("weld_current must be positive")
    if r <= 0:
        raise ValueError("contact_resistance must be positive")
    if t <= 0:
        raise ValueError("weld_time must be positive")
    return Quantity(magnitude=i * i * r * t, unit="J")


def spot_weld_current_for_heat(
    *, target_heat: Quantity, contact_resistance: Quantity, weld_time: Quantity
) -> Quantity:
    """The weld current for a target heat, I = √(Q/(R·t)).

    Inverting Joule's law (:func:`spot_weld_heat_generated`) for current: the current a schedule
    must pass to deposit a ``target_heat`` Q through the ``contact_resistance`` R in the
    ``weld_time`` t, I = √(Q/(R·t)). Because the heat goes as current squared, cutting the weld time
    in half only raises the required current by √2 — the reason resistance welding trades very short
    times against very large currents. Returns the weld current in kA.
    """
    _check(target_heat, "[energy]", "target_heat")
    _check(contact_resistance, "[resistance]", "contact_resistance")
    _check(weld_time, "[time]", "weld_time")
    q = target_heat.to("J").magnitude
    r = contact_resistance.to("ohm").magnitude
    t = weld_time.to("s").magnitude
    if q <= 0:
        raise ValueError("target_heat must be positive")
    if r <= 0:
        raise ValueError("contact_resistance must be positive")
    if t <= 0:
        raise ValueError("weld_time must be positive")
    i = sqrt(q / (r * t))
    return Quantity(magnitude=i, unit="A").to("kA")


def spot_weld_nugget_melting_energy(
    *,
    nugget_volume: Quantity,
    density: Quantity,
    specific_heat: Quantity,
    temperature_rise: Quantity,
    latent_heat_of_fusion: Quantity,
) -> Quantity:
    """The energy to melt the nugget, E = ρ·V·(c·ΔT + L_f).

    The heat the nugget itself must absorb to form: the mass ρ·V of a nugget of ``nugget_volume`` V
    at the metal's ``density`` ρ, raised from room temperature to melting by the sensible heat c·ΔT
    (the ``specific_heat`` c over the ``temperature_rise`` ΔT) and then melted by the
    ``latent_heat_of_fusion`` L_f, E = ρ·V·(c·ΔT + L_f). It is far less than the Joule heat
    generated (:func:`spot_weld_heat_generated`) — the ratio is the thermal efficiency, often only a
    tenth, since most heat conducts into the sheets and water-cooled electrodes. Returns the energy
    in J.
    """
    _check(nugget_volume, "[volume]", "nugget_volume")
    _check(density, "[mass]/[length]**3", "density")
    _check(specific_heat, "[energy]/([mass]*[temperature])", "specific_heat")
    _check(temperature_rise, "[temperature]", "temperature_rise")
    _check(latent_heat_of_fusion, "[energy]/[mass]", "latent_heat_of_fusion")
    vol = nugget_volume.to("m**3").magnitude
    rho = density.to("kg/m**3").magnitude
    c = specific_heat.to("J/(kg*K)").magnitude
    dt = temperature_difference_kelvin(temperature_rise, name="temperature_rise")
    lf = latent_heat_of_fusion.to("J/kg").magnitude
    if vol <= 0:
        raise ValueError("nugget_volume must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    if c <= 0:
        raise ValueError("specific_heat must be positive")
    if dt <= 0:
        raise ValueError("temperature_rise must be positive")
    if lf < 0:
        raise ValueError("latent_heat_of_fusion must be non-negative")
    return Quantity(magnitude=rho * vol * (c * dt + lf), unit="J")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
