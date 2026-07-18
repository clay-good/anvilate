"""T1 analytical sliding-wear checks (Archard's law, closed-form).

Sliding surfaces wear, and Archard's law is the workhorse estimate for how fast. The volume
of material a sliding contact loses is proportional to the normal load and the sliding
distance and inversely proportional to the surface hardness:

    V = K · F · s / H,

for a normal ``load`` F, ``sliding_distance`` s, ``hardness`` H, and the dimensionless wear
coefficient ``K`` — a material-pair-and-lubrication property read from a table (roughly 1e-3
for unlubricated like-on-like metal, 1e-4–1e-6 boundary-lubricated, 1e-7 or lower well
lubricated). Dividing by the apparent contact area turns load into pressure and volume into a
wear *depth*, h = K · p · s / H, the number a clearance or a liner thickness is checked
against. Inverting it gives the sliding distance a component survives before a wear-depth
limit — its wear life.

Archard's law is an order-of-magnitude screen, not a precise life: K lumps together the whole
tribology of the pair and can move an order of magnitude with load, speed, and film. Use it to
rank designs and size liners, not to certify a life. The wear coefficient K is the caller's
tabulated value; the load, pressure, distance, hardness, and depth are dimension-checked
:class:`~anvilate.units.Quantity` values. (Hardness enters as a stress — a Vickers number HV
is about 9.81·HV in MPa.)
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "archard_wear_volume",
    "archard_wear_depth",
    "sliding_distance_for_wear_depth",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _check_coefficient(wear_coefficient: float) -> float:
    if wear_coefficient <= 0:
        raise ValueError(f"wear_coefficient must be positive; got {wear_coefficient}")
    return wear_coefficient


def _hardness_pa(hardness: Quantity) -> float:
    _require(hardness, "[pressure]", "hardness")
    h = hardness.to("Pa").magnitude
    if h <= 0:
        raise ValueError(f"hardness must be positive; got {hardness}")
    return h


def archard_wear_volume(
    *,
    wear_coefficient: float,
    load: Quantity,
    sliding_distance: Quantity,
    hardness: Quantity,
) -> Quantity:
    """The worn volume V = K·F·s/H of a sliding contact (Archard's law).

    The volume of material lost to sliding wear: ``wear_coefficient`` K (dimensionless,
    tabulated for the pair and lubrication), ``load`` F, ``sliding_distance`` s, and
    ``hardness`` H (as a stress). K, and the positive quantities, must be positive.
    Returns the worn volume in mm³.
    """
    k = _check_coefficient(wear_coefficient)
    _require(load, "[force]", "load")
    _require(sliding_distance, "[length]", "sliding_distance")
    f = load.to("N").magnitude
    s = sliding_distance.to("m").magnitude
    h = _hardness_pa(hardness)
    if f <= 0 or s <= 0:
        raise ValueError("load and sliding_distance must be positive")
    volume_m3 = k * f * s / h
    return Quantity(magnitude=volume_m3 * 1e9, unit="mm**3")


def archard_wear_depth(
    *,
    wear_coefficient: float,
    contact_pressure: Quantity,
    sliding_distance: Quantity,
    hardness: Quantity,
) -> Quantity:
    """The wear depth h = K·p·s/H worn off a sliding surface (Archard's law).

    Archard's law per unit apparent area: the depth a surface recedes under a
    ``contact_pressure`` p (the load over the apparent area) sliding a
    ``sliding_distance`` s, for a ``wear_coefficient`` K and ``hardness`` H. This is the
    number a running clearance, a liner thickness, or a brush length is checked against.
    All positive. Returns the wear depth in mm.
    """
    k = _check_coefficient(wear_coefficient)
    _require(contact_pressure, "[pressure]", "contact_pressure")
    _require(sliding_distance, "[length]", "sliding_distance")
    p = contact_pressure.to("Pa").magnitude
    s = sliding_distance.to("m").magnitude
    h = _hardness_pa(hardness)
    if p <= 0 or s <= 0:
        raise ValueError("contact_pressure and sliding_distance must be positive")
    depth_m = k * p * s / h
    return Quantity(magnitude=depth_m * 1000.0, unit="mm")


def sliding_distance_for_wear_depth(
    *,
    wear_coefficient: float,
    contact_pressure: Quantity,
    hardness: Quantity,
    allowable_depth: Quantity,
) -> Quantity:
    """The sliding distance s = h·H/(K·p) a surface lasts before a wear-depth limit.

    The wear-life inverse of :func:`archard_wear_depth`: the sliding distance at which the
    wear depth reaches ``allowable_depth`` h for a ``contact_pressure`` p,
    ``wear_coefficient`` K, and ``hardness`` H — the distance a bushing, liner, or brush
    runs before it wears past its allowance. Divide by the sliding speed for a time to
    replacement. All positive. Returns the sliding distance in m.
    """
    k = _check_coefficient(wear_coefficient)
    _require(contact_pressure, "[pressure]", "contact_pressure")
    _require(allowable_depth, "[length]", "allowable_depth")
    p = contact_pressure.to("Pa").magnitude
    hardness_pa = _hardness_pa(hardness)
    depth_m = allowable_depth.to("m").magnitude
    if p <= 0 or depth_m <= 0:
        raise ValueError("contact_pressure and allowable_depth must be positive")
    distance_m = depth_m * hardness_pa / (k * p)
    return Quantity(magnitude=distance_m, unit="m")
