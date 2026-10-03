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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_WEAR_TRIBOLOGY_SOURCE = "the material-pair wear test or cited lubrication-condition data"
_WEAR_DUTY_SOURCE = "the governing contact-load and sliding-duty record"
_WEAR_LIMIT_SOURCE = "the component drawing or approved wear-allowance requirement"


class _WearInputError(RefusalError, ValueError):
    """A sliding-wear input that cannot be used without correction."""


def _wear_refusal(message: str, *, subject: str, source: str) -> _WearInputError:
    return _WearInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _wear_input_source(name: str) -> str:
    if name == "hardness":
        return _WEAR_TRIBOLOGY_SOURCE
    if name == "allowable_depth":
        return _WEAR_LIMIT_SOURCE
    return _WEAR_DUTY_SOURCE


__all__ = [
    "archard_wear_volume",
    "archard_wear_depth",
    "sliding_distance_for_wear_depth",
    "sliding_contact_pv",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _wear_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_wear_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _wear_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_wear_input_source(name),
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


def _check_coefficient(wear_coefficient: float) -> float:
    if wear_coefficient <= 0:
        raise _wear_refusal(
            f"wear_coefficient must be positive; got {wear_coefficient}",
            subject="wear_coefficient",
            source=_WEAR_TRIBOLOGY_SOURCE,
        )
    return wear_coefficient


def _hardness_pa(hardness: Quantity) -> float:
    _require(hardness, "[pressure]", "hardness")
    h = hardness.to("Pa").magnitude
    if h <= 0:
        raise _wear_refusal(
            f"hardness must be positive; got {hardness}",
            subject="hardness",
            source=_WEAR_TRIBOLOGY_SOURCE,
        )
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
    require_finite(wear_coefficient, name="wear_coefficient")
    k = _check_coefficient(wear_coefficient)
    _require(load, "[force]", "load")
    _require(sliding_distance, "[length]", "sliding_distance")
    f = load.to("N").magnitude
    s = sliding_distance.to("m").magnitude
    h = _hardness_pa(hardness)
    if f <= 0 or s <= 0:
        raise _wear_refusal(
            "load and sliding_distance must be positive",
            subject="load and sliding_distance",
            source=_WEAR_DUTY_SOURCE,
        )
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
    require_finite(wear_coefficient, name="wear_coefficient")
    k = _check_coefficient(wear_coefficient)
    _require(contact_pressure, "[pressure]", "contact_pressure")
    _require(sliding_distance, "[length]", "sliding_distance")
    p = contact_pressure.to("Pa").magnitude
    s = sliding_distance.to("m").magnitude
    h = _hardness_pa(hardness)
    if p <= 0 or s <= 0:
        raise _wear_refusal(
            "contact_pressure and sliding_distance must be positive",
            subject="contact_pressure and sliding_distance",
            source=_WEAR_DUTY_SOURCE,
        )
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
    require_finite(wear_coefficient, name="wear_coefficient")
    k = _check_coefficient(wear_coefficient)
    _require(contact_pressure, "[pressure]", "contact_pressure")
    _require(allowable_depth, "[length]", "allowable_depth")
    p = contact_pressure.to("Pa").magnitude
    hardness_pa = _hardness_pa(hardness)
    depth_m = allowable_depth.to("m").magnitude
    if p <= 0 or depth_m <= 0:
        raise _wear_refusal(
            "contact_pressure and allowable_depth must be positive",
            subject="contact_pressure and allowable_depth",
            source=_WEAR_LIMIT_SOURCE,
        )
    distance_m = depth_m * hardness_pa / (k * p)
    return Quantity(magnitude=distance_m, unit="m")


def sliding_contact_pv(*, contact_pressure: Quantity, sliding_velocity: Quantity) -> Quantity:
    """The PV factor p·v of a sliding contact, against the material's PV limit.

    The product of the bearing ``contact_pressure`` p and the ``sliding_velocity`` v is
    the frictional power dissipated per unit area, and it is the canonical plain-bearing
    screen alongside wear: every dry or boundary-lubricated bushing material has an
    allowable PV above which it overheats and melts or chars, regardless of how slowly it
    would otherwise wear. Typical limits are roughly 1.75 MPa·m/s for a bronze bushing,
    0.35 for filled PTFE, and 0.10 for nylon. A slow, heavily-loaded bushing is usually
    wear-limited; a fast, lightly-loaded one is PV-limited. Both inputs must be positive.
    Returns the PV factor in MPa·m/s.
    """
    _require(contact_pressure, "[pressure]", "contact_pressure")
    if not isinstance(sliding_velocity, Quantity):
        raise _wear_refusal(
            f"sliding_velocity must be a [length] / [time] quantity; got {sliding_velocity!r}",
            subject="sliding_velocity",
            source=_WEAR_DUTY_SOURCE,
        )
    if not sliding_velocity.has_dimension("[length] / [time]"):
        raise _wear_refusal(
            f"sliding_velocity must be a velocity quantity; got {sliding_velocity.dimensionality}",
            subject="sliding_velocity",
            source=_WEAR_DUTY_SOURCE,
        )
    p = contact_pressure.to("MPa").magnitude
    v = sliding_velocity.to("m/s").magnitude
    if p <= 0 or v <= 0:
        raise _wear_refusal(
            "contact_pressure and sliding_velocity must be positive",
            subject="contact_pressure and sliding_velocity",
            source=_WEAR_DUTY_SOURCE,
        )
    return Quantity(magnitude=p * v, unit="MPa*m/s")
