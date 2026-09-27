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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from ..units.temperature import temperature_difference_kelvin

_SPOT_WELD_SCHEDULE_SOURCE = "the qualified resistance-welding schedule or calibrated controller"
_SPOT_WELD_GEOMETRY_SOURCE = "the joint drawing or verified weld-nugget geometry"
_SPOT_WELD_MATERIAL_SOURCE = "the sheet material certificate or verified thermal-property record"


class _ResistanceWeldingInputError(RefusalError, ValueError):
    """A resistance-welding input that cannot be used without correction."""


def _resistance_welding_refusal(
    message: str, *, subject: str, source: str
) -> _ResistanceWeldingInputError:
    return _ResistanceWeldingInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _resistance_welding_input_source(name: str) -> str:
    if name == "nugget_volume":
        return _SPOT_WELD_GEOMETRY_SOURCE
    if name in {
        "density",
        "specific_heat",
        "temperature_rise",
        "latent_heat_of_fusion",
    }:
        return _SPOT_WELD_MATERIAL_SOURCE
    return _SPOT_WELD_SCHEDULE_SOURCE


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
        raise _resistance_welding_refusal(
            "weld_current must be positive",
            subject="weld_current",
            source=_SPOT_WELD_SCHEDULE_SOURCE,
        )
    if r <= 0:
        raise _resistance_welding_refusal(
            "contact_resistance must be positive",
            subject="contact_resistance",
            source=_SPOT_WELD_SCHEDULE_SOURCE,
        )
    if t <= 0:
        raise _resistance_welding_refusal(
            "weld_time must be positive",
            subject="weld_time",
            source=_SPOT_WELD_SCHEDULE_SOURCE,
        )
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
        raise _resistance_welding_refusal(
            "target_heat must be positive",
            subject="target_heat",
            source=_SPOT_WELD_SCHEDULE_SOURCE,
        )
    if r <= 0:
        raise _resistance_welding_refusal(
            "contact_resistance must be positive",
            subject="contact_resistance",
            source=_SPOT_WELD_SCHEDULE_SOURCE,
        )
    if t <= 0:
        raise _resistance_welding_refusal(
            "weld_time must be positive",
            subject="weld_time",
            source=_SPOT_WELD_SCHEDULE_SOURCE,
        )
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
        raise _resistance_welding_refusal(
            "nugget_volume must be positive",
            subject="nugget_volume",
            source=_SPOT_WELD_GEOMETRY_SOURCE,
        )
    if rho <= 0:
        raise _resistance_welding_refusal(
            "density must be positive", subject="density", source=_SPOT_WELD_MATERIAL_SOURCE
        )
    if c <= 0:
        raise _resistance_welding_refusal(
            "specific_heat must be positive",
            subject="specific_heat",
            source=_SPOT_WELD_MATERIAL_SOURCE,
        )
    if dt <= 0:
        raise _resistance_welding_refusal(
            "temperature_rise must be positive",
            subject="temperature_rise",
            source=_SPOT_WELD_MATERIAL_SOURCE,
        )
    if lf < 0:
        raise _resistance_welding_refusal(
            "latent_heat_of_fusion must be non-negative",
            subject="latent_heat_of_fusion",
            source=_SPOT_WELD_MATERIAL_SOURCE,
        )
    return Quantity(magnitude=rho * vol * (c * dt + lf), unit="J")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _resistance_welding_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_resistance_welding_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _resistance_welding_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_resistance_welding_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
