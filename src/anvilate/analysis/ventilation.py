"""T1 analytical ventilation / indoor-air-quality checks (airflow, closed-form).

Facility and industrial-hygiene engineers size outdoor-air and exhaust rates to keep an occupied
space healthy, and a few relations carry the work.

The ventilation-rate procedure of ASHRAE 62.1 sets the outdoor air a zone needs from two additive
demands — the people in it and the floor it covers: the breathing-zone rate is
V_bz = R_p·P_z + R_a·A_z, where R_p is the per-person rate, P_z the occupancy, R_a the per-area
rate, and A_z the floor area. Divided by the zone air distribution effectiveness E_z (how supply air
actually reaches the breathing zone), it becomes the outdoor airflow the zone must be given.

Air changes per hour, ACH = Q/V, expresses a flow Q against the room volume V as how many times the
air is replaced each hour — the currency of dilution and of many code minimums.

Dilution ventilation controls a contaminant by supplying enough clean air to hold it below a target
concentration: Q = K·G/C, from the generation rate G, the target concentration C, and a mixing
factor K (the ACGIH safety factor for imperfect mixing). Per-person and per-area rates are supplied
standard values; the engineer of record owns the ventilation design.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "air_changes_per_hour",
    "airflow_for_air_changes",
    "breathing_zone_outdoor_airflow",
    "dilution_airflow",
]


def breathing_zone_outdoor_airflow(
    *,
    people_outdoor_rate: Quantity,
    occupancy: float,
    area_outdoor_rate: Quantity,
    floor_area: Quantity,
    zone_air_distribution_effectiveness: float = 1.0,
) -> Quantity:
    """The zone outdoor airflow by ASHRAE 62.1, V_oz = (R_p·P_z + R_a·A_z)/E_z.

    The ventilation-rate procedure adds a people demand and an area demand: the breathing-zone
    outdoor air is V_bz = R_p·P_z + R_a·A_z, from ``people_outdoor_rate`` R_p (airflow per person),
    ``occupancy`` P_z (the number of people), ``area_outdoor_rate`` R_a (airflow per floor area,
    e.g. 0.06 cfm/ft²), and ``floor_area`` A_z. Dividing by
    ``zone_air_distribution_effectiveness`` E_z — 1.0 for good mixing, less when supply air
    short-circuits to the return — gives the outdoor airflow the zone must actually be supplied.
    Returns the zone outdoor airflow in L/s.
    """
    _check(people_outdoor_rate, "[length]**3/[time]", "people_outdoor_rate")
    _check(area_outdoor_rate, "[length]/[time]", "area_outdoor_rate")
    _check(floor_area, "[length]**2", "floor_area")
    if occupancy < 0:
        raise ValueError("occupancy must be non-negative")
    if not 0.0 < zone_air_distribution_effectiveness <= 1.0:
        raise ValueError("zone_air_distribution_effectiveness must be in (0, 1]")
    people = people_outdoor_rate.pint * occupancy
    area = area_outdoor_rate.pint * floor_area.pint
    v_bz = (people + area).to("L/s")
    v_oz = v_bz / zone_air_distribution_effectiveness
    return Quantity(magnitude=float(v_oz.magnitude), unit="L/s")


def air_changes_per_hour(*, airflow: Quantity, room_volume: Quantity) -> float:
    """The air-change rate of a room, ACH = Q/V (volumes of air replaced per hour).

    The supply ``airflow`` Q divided by the ``room_volume`` V, expressed per hour: ACH = Q/V. It is
    how ventilation is most often specified and checked — code minimums, dilution targets, and
    infection-control criteria are all stated in air changes per hour. Returns the dimensionless
    air-change rate (per hour).
    """
    _check(airflow, "[length]**3/[time]", "airflow")
    _check(room_volume, "[length]**3", "room_volume")
    v = room_volume.to("m**3").magnitude
    if v <= 0:
        raise ValueError("room_volume must be positive")
    return (airflow.pint / room_volume.pint).to("1/hour").magnitude


def airflow_for_air_changes(
    *,
    air_changes_per_hour: float,
    room_volume: Quantity,
) -> Quantity:
    """The airflow a target air-change rate needs, Q = ACH·V (the sizing inverse).

    The design direction of :func:`air_changes_per_hour`: a code or infection-control standard sets
    a minimum air-change rate, and this returns the supply airflow that meets it — the
    ``air_changes_per_hour`` ACH times the ``room_volume`` V, Q = ACH·V. A lab wanting 6 air changes
    an hour in a 200 m³ room needs 1,200 m³/h. Returns the required airflow in m³/s.
    """
    _check(room_volume, "[length]**3", "room_volume")
    v = room_volume.to("m**3").magnitude
    if air_changes_per_hour <= 0:
        raise ValueError("air_changes_per_hour must be positive")
    if v <= 0:
        raise ValueError("room_volume must be positive")
    return Quantity(magnitude=air_changes_per_hour * v / 3600.0, unit="m**3/s")


def dilution_airflow(
    *,
    contaminant_generation_rate: Quantity,
    target_concentration: Quantity,
    mixing_factor: float = 1.0,
) -> Quantity:
    """The clean airflow to hold a contaminant below a target, Q = K·G/C (dilution ventilation).

    To keep a steadily generated contaminant under a limit, dilution ventilation supplies
    Q = K·G/C, from the ``contaminant_generation_rate`` G (mass per time), the
    ``target_concentration`` C (mass per volume — the exposure limit), and a ``mixing_factor`` K,
    the ACGIH factor (≥ 1) that pads the ideal rate for incomplete mixing and poor capture. Returns
    the required dilution airflow in L/s.
    """
    _check(contaminant_generation_rate, "[mass]/[time]", "contaminant_generation_rate")
    _check(target_concentration, "[mass]/[length]**3", "target_concentration")
    if mixing_factor < 1.0:
        raise ValueError("mixing_factor must be at least 1")
    c = target_concentration.to("kg/m**3").magnitude
    if c <= 0:
        raise ValueError("target_concentration must be positive")
    q = mixing_factor * contaminant_generation_rate.pint / target_concentration.pint
    return Quantity(magnitude=float(q.to("L/s").magnitude), unit="L/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
