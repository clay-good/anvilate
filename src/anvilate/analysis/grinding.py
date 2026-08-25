"""T1 analytical surface-grinding checks (closed-form).

Grinding removes metal with a wheel of bonded abrasive grits, each grit a tiny cutting edge. It is
the abrasive counterpart to the chip-forming cuts of :mod:`anvilate.analysis.machining`, and it
earns its own module because its process signature is unlike any other cut: the chips are
microscopic and the specific energy — the work spent to remove a unit volume — is an order of
magnitude higher than turning or milling. Almost all of that energy becomes heat at the surface, so
grinding's governing failure mode is not force but *thermal damage*: burn, tempering, and residual
tensile stress if the surface runs too hot.

Three numbers describe a grinding pass. The specific removal rate Q′_w = a_e·v_w is the volume of
metal removed per second per unit width of wheel, from the depth of cut a_e and the workpiece feed
speed v_w — the standard throughput measure a grinding process is dialled in to. The equivalent chip
thickness h_eq = Q′_w/v_s divides that by the wheel speed v_s to give the thickness of the
continuous ribbon the wheel would peel if it never lost contact; it is only microns, and it
correlates directly with grain force, surface finish, and burn. The specific energy u = P/(b·Q′_w)
is the spindle power P spread over the removal rate — the quantity that, multiplied by throughput,
sets how much heat the surface must shed, and the reason grinding is a finishing process, not a
roughing one.

Sources: Kalpakjian & Schmid, *Manufacturing Engineering and Technology* (abrasive machining and
finishing) — the specific removal rate per unit width, the equivalent chip thickness that
indexes wheel behaviour, and the specific energy a grind consumes.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "grinding_equivalent_chip_thickness",
    "grinding_specific_energy",
    "grinding_specific_removal_rate",
]


def grinding_specific_removal_rate(
    *, depth_of_cut: Quantity, workpiece_speed: Quantity
) -> Quantity:
    """The specific material removal rate, Q′_w = a_e·v_w.

    The volume of metal a surface-grinding pass removes per second per unit width of wheel, from the
    ``depth_of_cut`` a_e (the wheel infeed per pass) and the ``workpiece_speed`` v_w (the table
    feed): Q′_w = a_e·v_w. It is the throughput a grinding process is specified by — typically a few
    mm³ per mm of width per second for rough grinding, far less for finish grinding — and it feeds
    both the equivalent chip thickness (:func:`grinding_equivalent_chip_thickness`) and, through the
    specific energy (:func:`grinding_specific_energy`), the heat the surface must shed. Returns Q′_w
    in mm**3/(mm*s), i.e. mm**2/s.
    """
    _check(depth_of_cut, "[length]", "depth_of_cut")
    _check(workpiece_speed, "[length]/[time]", "workpiece_speed")
    a_e = depth_of_cut.to("mm").magnitude
    v_w = workpiece_speed.to("mm/s").magnitude
    if a_e <= 0:
        raise ValueError("depth_of_cut must be positive")
    if v_w <= 0:
        raise ValueError("workpiece_speed must be positive")
    return Quantity(magnitude=a_e * v_w, unit="mm**2/s")


def grinding_equivalent_chip_thickness(
    *, specific_removal_rate: Quantity, wheel_speed: Quantity
) -> Quantity:
    """The equivalent chip thickness, h_eq = Q′_w/v_s.

    The thickness of the continuous ribbon of metal the wheel would peel if it stayed in contact:
    the ``specific_removal_rate`` Q′_w (from :func:`grinding_specific_removal_rate`) divided by the
    ``wheel_speed`` v_s, h_eq = Q′_w/v_s. It collapses depth of cut, feed, and wheel speed into one
    micron-scale number that tracks grain cutting force, surface finish, and the onset of burn — the
    single parameter grinding data is correlated against. Raising wheel speed at fixed throughput
    lowers h_eq, which is why high-speed grinding runs cooler per grain. Returns h_eq in microns.
    """
    _check(specific_removal_rate, "[area]/[time]", "specific_removal_rate")
    _check(wheel_speed, "[length]/[time]", "wheel_speed")
    q = specific_removal_rate.to("mm**2/s").magnitude
    v_s = wheel_speed.to("mm/s").magnitude
    if q <= 0:
        raise ValueError("specific_removal_rate must be positive")
    if v_s <= 0:
        raise ValueError("wheel_speed must be positive")
    return Quantity(magnitude=q / v_s * 1000.0, unit="micrometer")


def grinding_specific_energy(
    *, power: Quantity, specific_removal_rate: Quantity, wheel_width: Quantity
) -> Quantity:
    """The specific grinding energy, u = P/(b·Q′_w).

    The work the spindle spends to remove a unit volume of metal: the grinding ``power`` P spread
    over the total removal rate, u = P/(b·Q′_w), where the total rate is the
    ``specific_removal_rate`` Q′_w (from :func:`grinding_specific_removal_rate`) times the
    ``wheel_width`` b in contact. Grinding specific energy runs tens of J/mm³ — an order of
    magnitude above chip-forming cuts — because the grits rub and plough as well as cut, and most
    becomes heat at the surface. It is the quantity that governs thermal damage: high u at high
    throughput is what burns and re-tempers the workpiece, and the reason grinding finishes rather
    than roughs. Returns u in J/mm**3.
    """
    _check(power, "[power]", "power")
    _check(specific_removal_rate, "[area]/[time]", "specific_removal_rate")
    _check(wheel_width, "[length]", "wheel_width")
    p = power.to("W").magnitude
    q = specific_removal_rate.to("mm**2/s").magnitude
    b = wheel_width.to("mm").magnitude
    if p <= 0:
        raise ValueError("power must be positive")
    if q <= 0:
        raise ValueError("specific_removal_rate must be positive")
    if b <= 0:
        raise ValueError("wheel_width must be positive")
    total_removal_rate = b * q  # mm**3/s
    return Quantity(magnitude=p / total_removal_rate, unit="J/mm**3")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
