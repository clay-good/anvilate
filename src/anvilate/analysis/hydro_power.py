"""T1 analytical hydro-turbine power checks (closed-form).

Hydro completes the renewable set with :mod:`anvilate.analysis.solar_pv`,
:mod:`anvilate.analysis.solar_thermal`, and :mod:`anvilate.analysis.wind_power`: where those turn
sun and wind into power, a hydro plant turns *falling water* into it, and the arithmetic is the
plainest of the four — the power is set by how much water falls and how far.

The hydraulic power in a stream is P = ρ·g·Q·H: the weight rate of the flow (ρ·g·Q, from the
``fluid_density`` ρ and the volumetric ``flow_rate`` Q) times the head H it drops through. A real
plant delivers less: friction in the penstock eats part of the drop, so the turbine sees a *net*
head H_net = H_gross − h_loss rather than the full gross head, and the turbine-plus-generator
converts that with an overall efficiency η (~0.7–0.9 for a good small plant). The shaft/electrical
output is then P = ρ·g·Q·H_net·η. Turned around, the flow a target output needs is
Q = P/(ρ·g·H·η) — the sizing inverse that sets the intake and penstock.

Unlike wind's cube law, hydro power is linear in both flow and head, which is why a modest head over
a steady flow is such a dependable resource: the power is there whenever the water is.

Sources: Cengel & Cimbala, *Fluid Mechanics*, and the standard hydro-turbine
specific-speed relations as given in Karassik, *Pump Handbook*.
"""

from __future__ import annotations

from math import sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from ..units.rotation import angular_speed_rad_per_s

_SITE_SOURCE = "the site survey's gross head and the penstock head-loss calculation"
_HYDROLOGY_SOURCE = "the hydrology study's design flow and water density"
_TURBINE_SOURCE = "the turbine manufacturer's performance curve at the duty point"
_TIDAL_SOURCE = "the tidal survey's basin area, tidal range, and tidal period"
_DUTY_SOURCE = "the project design basis's target power output"


class _HydroPowerInputError(RefusalError, ValueError):
    """A hydro-power input that cannot be used without correction."""


def _hydro_power_refusal(message: str, *, subject: str, source: str) -> _HydroPowerInputError:
    return _HydroPowerInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _hydro_power_input_source(name: str) -> str:
    if name in {"density", "flow_rate", "fluid_density", "water_density"}:
        return _HYDROLOGY_SOURCE
    if name in {"overall_efficiency", "power", "rotational_speed"}:
        return _TURBINE_SOURCE
    if name == "target_power":
        return _DUTY_SOURCE
    if name in {"basin_area", "tidal_period", "tidal_range"}:
        return _TIDAL_SOURCE
    return _SITE_SOURCE


_GRAVITY = 9.80665  # m/s^2, standard gravity

__all__ = [
    "hydro_flow_for_power",
    "hydro_net_head",
    "hydro_turbine_power",
    "tidal_average_power",
    "tidal_barrage_energy",
    "turbine_specific_speed",
]


def hydro_net_head(*, gross_head: Quantity, head_loss: Quantity) -> Quantity:
    """The net head a turbine actually sees, H_net = H_gross − h_loss.

    The full vertical drop from intake to turbine is the ``gross_head`` H_gross, but penstock
    friction and fittings burn part of it before the water arrives: the turbine sees only
    H_net = H_gross − h_loss, from the ``head_loss`` h_loss (the friction head from
    :mod:`~anvilate.analysis.pipe_flow`). This is the head to feed :func:`hydro_turbine_power` —
    using the gross head instead overstates the output by the loss fraction. Raises if the loss
    meets or exceeds the gross head (no head left to drive the turbine). Returns the net head as a
    length.
    """
    _check(gross_head, "[length]", "gross_head")
    _check(head_loss, "[length]", "head_loss")
    h_gross = gross_head.to("m").magnitude
    h_loss = head_loss.to("m").magnitude
    if h_gross <= 0:
        raise _hydro_power_refusal(
            "gross_head must be positive", subject="gross_head", source=_SITE_SOURCE
        )
    if h_loss < 0:
        raise _hydro_power_refusal(
            "head_loss must be non-negative", subject="head_loss", source=_SITE_SOURCE
        )
    if h_loss >= h_gross:
        raise _hydro_power_refusal(
            "head_loss must be less than gross_head (no net head to drive the turbine)",
            subject="gross_head and head_loss",
            source=_SITE_SOURCE,
        )
    return Quantity(magnitude=h_gross - h_loss, unit="m")


def hydro_turbine_power(
    *,
    flow_rate: Quantity,
    net_head: Quantity,
    overall_efficiency: float,
    fluid_density: Quantity,
) -> Quantity:
    """The power a hydro turbine delivers, P = ρ·g·Q·H·η.

    The shaft/electrical output from a volumetric ``flow_rate`` Q of a fluid of ``fluid_density`` ρ
    dropping through a ``net_head`` H (from :func:`hydro_net_head`): P = ρ·g·Q·H·η, where the
    ``overall_efficiency`` η folds together the turbine, drive, and generator (0 to 1, ~0.7–0.9 for
    a good small plant). It is linear in both flow and head — double either and the power doubles —
    so a steady stream over a modest fall is a dependable resource. Returns the power in watts.
    """
    require_finite(overall_efficiency, name="overall_efficiency")
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    _check(net_head, "[length]", "net_head")
    _check(fluid_density, "[mass]/[length]**3", "fluid_density")
    q = flow_rate.to("m**3/s").magnitude
    h = net_head.to("m").magnitude
    rho = fluid_density.to("kg/m**3").magnitude
    for subject, magnitude in (("flow_rate", q), ("net_head", h), ("fluid_density", rho)):
        if magnitude <= 0:
            raise _hydro_power_refusal(
                "flow_rate, net_head, and fluid_density must be positive",
                subject=subject,
                source=_hydro_power_input_source(subject),
            )
    if not 0.0 < overall_efficiency <= 1.0:
        raise _hydro_power_refusal(
            f"overall_efficiency must be in (0, 1]; got {overall_efficiency}",
            subject="overall_efficiency",
            source=_TURBINE_SOURCE,
        )
    return Quantity(magnitude=rho * _GRAVITY * q * h * overall_efficiency, unit="W")


def hydro_flow_for_power(
    *,
    target_power: Quantity,
    net_head: Quantity,
    overall_efficiency: float,
    fluid_density: Quantity,
) -> Quantity:
    """The flow a target output needs, Q = P/(ρ·g·H·η) (the sizing inverse).

    How much water a plant must pass to reach a ``target_power`` P at a given ``net_head`` H:
    Q = P/(ρ·g·H·η), the inverse of :func:`hydro_turbine_power`, from the ``fluid_density`` ρ and
    the ``overall_efficiency`` η. This is the flow the intake and penstock must carry — check it
    against the stream's available flow before committing to a rating. Returns the required
    volumetric flow rate in m³/s.
    """
    require_finite(overall_efficiency, name="overall_efficiency")
    _check(target_power, "[power]", "target_power")
    _check(net_head, "[length]", "net_head")
    _check(fluid_density, "[mass]/[length]**3", "fluid_density")
    p = target_power.to("W").magnitude
    h = net_head.to("m").magnitude
    rho = fluid_density.to("kg/m**3").magnitude
    for subject, magnitude in (("target_power", p), ("net_head", h), ("fluid_density", rho)):
        if magnitude <= 0:
            raise _hydro_power_refusal(
                "target_power, net_head, and fluid_density must be positive",
                subject=subject,
                source=_hydro_power_input_source(subject),
            )
    if not 0.0 < overall_efficiency <= 1.0:
        raise _hydro_power_refusal(
            f"overall_efficiency must be in (0, 1]; got {overall_efficiency}",
            subject="overall_efficiency",
            source=_TURBINE_SOURCE,
        )
    q = p / (rho * _GRAVITY * h * overall_efficiency)
    return Quantity(magnitude=q, unit="m**3/s")


def tidal_barrage_energy(
    *,
    basin_area: Quantity,
    tidal_range: Quantity,
    water_density: Quantity,
) -> Quantity:
    """The tidal-barrage energy per tide, E = ½·ρ·g·A·h².

    The gravitational potential energy captured when a barrage traps a basin of water over one tidal
    cycle: from the ``basin_area`` A, the ``tidal_range`` h (high-water minus low-water level), and
    the ``water_density`` ρ (~1025 kg/m³ for seawater), E = ½·ρ·g·A·h². The trapped water sits on
    average h/2 above the drained level, and its weight ρ·g·A·h gives the ½·ρ·g·A·h² — so the yield
    scales with the *square* of the tidal range, which is why only high-range estuaries are viable.
    Turbine and cycle efficiency (typically ~0.25–0.4 of this ideal) are the caller's to apply.
    Returns the ideal energy per tide in J.
    """
    _check(basin_area, "[length]**2", "basin_area")
    _check(tidal_range, "[length]", "tidal_range")
    _check(water_density, "[mass]/[length]**3", "water_density")
    a = basin_area.to("m**2").magnitude
    h = tidal_range.to("m").magnitude
    rho = water_density.to("kg/m**3").magnitude
    for subject, magnitude in (("basin_area", a), ("tidal_range", h), ("water_density", rho)):
        if magnitude <= 0:
            raise _hydro_power_refusal(
                "basin_area, tidal_range, and water_density must be positive",
                subject=subject,
                source=_hydro_power_input_source(subject),
            )
    return Quantity(magnitude=0.5 * rho * _GRAVITY * a * h * h, unit="J")


def tidal_average_power(
    *,
    basin_area: Quantity,
    tidal_range: Quantity,
    tidal_period: Quantity,
    water_density: Quantity,
) -> Quantity:
    """The average tidal-barrage power, P = E/T = ½·ρ·g·A·h²/T.

    The ideal average power a barrage delivers, spreading one tide's energy
    (:func:`tidal_barrage_energy`) over the ``tidal_period`` T (about 12.42 h for the semidiurnal
    tide): P = ½·ρ·g·A·h²/T, from the ``basin_area`` A, the ``tidal_range`` h, and the
    ``water_density`` ρ. It is the ideal ceiling for a single-basin ebb-generation scheme; the real
    output is a fraction of it after turbine, generator, and cycle losses. Returns the average power
    in W.
    """
    _check(tidal_period, "[time]", "tidal_period")
    period = tidal_period.to("s").magnitude
    if period <= 0:
        raise _hydro_power_refusal(
            "tidal_period must be positive", subject="tidal_period", source=_TIDAL_SOURCE
        )
    energy = tidal_barrage_energy(
        basin_area=basin_area, tidal_range=tidal_range, water_density=water_density
    )
    return Quantity(magnitude=energy.to("J").magnitude / period, unit="W")


def turbine_specific_speed(
    *,
    rotational_speed: Quantity,
    power: Quantity,
    density: Quantity,
    head: Quantity,
) -> float:
    """The dimensionless turbine specific speed, Ω_s = ω·√(P/ρ)/(g·H)^1.25.

    The shape parameter that answers the first question in any hydro scheme: Pelton, Francis, or
    Kaplan? The module sizes head, flow, and power but had no similarity group, so nothing said
    which machine those numbers call for. From the ``rotational_speed`` ω, the ``power`` P, the
    water ``density`` ρ, and the net ``head`` H (of :func:`hydro_net_head`):
    Ω_s = ω·√(P/ρ)/(g·H)^1.25.

    Roughly: below ~0.2 an impulse Pelton wheel (high head, low flow), 0.3-2.5 a reaction Francis
    runner, above ~2.5 an axial Kaplan (low head, high flow). It is deliberately *not* the pump
    group of :func:`anvilate.analysis.pump.pump_specific_speed`, which is built on flow with a 3/4
    exponent — a turbine is specified by the power it must deliver, not the flow it must pass, so
    the group carries √P and an exponent of 5/4 instead. The two are different similarity numbers
    and are not interchangeable. Rotational speed may be given in rpm or rad/s. Returns the
    dimensionless specific speed as a plain float.
    """
    _check(rotational_speed, "1/[time]", "rotational_speed")
    _check(power, "[power]", "power")
    _check(density, "[mass]/[length]**3", "density")
    _check(head, "[length]", "head")
    omega = angular_speed_rad_per_s(rotational_speed, name="rotational_speed")
    p_w = power.to("W").magnitude
    rho = density.to("kg/m**3").magnitude
    h = head.to("m").magnitude
    if omega <= 0:
        raise _hydro_power_refusal(
            "rotational_speed must be positive", subject="rotational_speed", source=_TURBINE_SOURCE
        )
    if p_w <= 0:
        raise _hydro_power_refusal(
            "power must be positive", subject="power", source=_TURBINE_SOURCE
        )
    if rho <= 0:
        raise _hydro_power_refusal(
            "density must be positive", subject="density", source=_HYDROLOGY_SOURCE
        )
    if h <= 0:
        raise _hydro_power_refusal("head must be positive", subject="head", source=_SITE_SOURCE)
    return omega * sqrt(p_w / rho) / (_GRAVITY * h) ** 1.25


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _hydro_power_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_hydro_power_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _hydro_power_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_hydro_power_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
