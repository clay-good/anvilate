"""Behaviors that execute under test but nothing asserted — found by mutation testing.

Line coverage of the safety-decision layer here is near total, and misleading with it: a
line can run in every test and have its *result* checked by none. Every test in this file
was written because a deliberate mutation of the code it covers left the suite green.

Two families:

* the ``_PEAK_SHEAR_FACTORS`` table, whose triangular column could be doubled without a
  single failure — and it feeds the reported shear demand of every member in that class;
* the library's signature invariant, that a criterion with nothing to evaluate reports
  ``NOT_EVALUATED`` and never ``PASS``. It was asserted in some packs and not others, so
  replacing an ``else None`` with ``else 1.0`` — "exactly at the limit, PASS" — went
  unnoticed in the pump cavitation margin, the masonry unity check, the ASHRAE 62.1
  outdoor-air check, and the hearing-conservation dose.
"""

from __future__ import annotations

import pytest

from anvilate.analysis import CrossSection
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


# --- the peak-shear table -------------------------------------------------


# V/(load) for a full-span member, per (support, load type). Independently stated here:
# a test that recomputed them from the table would pin nothing.
_EXPECTED_SHEAR_FACTORS = {
    ("cantilever", "point"): 1.0,
    ("simply_supported", "point"): 0.5,
    ("fixed_fixed", "point"): 0.5,
    ("fixed_pinned", "point"): 11.0 / 16.0,
    ("cantilever", "distributed"): 1.0,
    ("simply_supported", "distributed"): 0.5,
    ("fixed_fixed", "distributed"): 0.5,
    ("fixed_pinned", "distributed"): 5.0 / 8.0,
    ("cantilever", "triangular"): 0.5,
    ("simply_supported", "triangular"): 1.0 / 3.0,
    ("fixed_fixed", "triangular"): 7.0 / 20.0,
    ("fixed_pinned", "triangular"): 2.0 / 5.0,
}


@pytest.mark.parametrize(("support", "load_type"), sorted(_EXPECTED_SHEAR_FACTORS))
def test_every_peak_shear_factor_is_pinned_to_its_reported_stress(support, load_type):
    """Each table row must produce the shear stress its coefficient implies.

    The whole triangular column plus the fixed-pinned point row were executed by the
    suite and asserted by none of it: doubling the simply-supported triangular
    coefficient left 2352 tests green while halving every reported shear demand in that
    class. A wrong row here turns a failing web into a PASS.
    """
    from anvilate.packs.structural import BeamMember, LoadType, Support, screen_beam_member

    section = CrossSection.rectangular(width=_q("50 mm"), height=_q("100 mm"))
    span_mm = 3000.0
    load = _q("6 kN") if load_type == "point" else _q("2 N/mm")
    member = BeamMember(
        name="b",
        section=section,
        length=_q("3 m"),
        support=Support(support),
        load=load,
        load_type=LoadType(load_type),
        material="ASTM-A36",
    )
    entry = next(
        e
        for e in screen_beam_member(member, required_safety_factor=1.0).entries
        if "shear" in e.name
    )
    assert entry.status is not CheckStatus.NOT_EVALUATED

    factor = _EXPECTED_SHEAR_FACTORS[(support, load_type)]
    total = 6000.0 if load_type == "point" else 2.0 * span_mm
    # τ = k·V/A with k = 3/2 for a rectangle and A = 5000 mm².
    expected_stress = 1.5 * factor * total / 5000.0
    symbol = next(s for s in entry.derivation.inputs if s.symbol == "V")
    assert symbol.value.to("N").magnitude == pytest.approx(factor * total, rel=1e-9)
    assert entry.derivation.result.value.to("MPa").magnitude == pytest.approx(
        expected_stress, rel=1e-9
    )


# --- "nothing to evaluate" is never a pass --------------------------------


def test_pump_cavitation_margin_with_no_npsh_required_is_not_evaluated():
    from anvilate.packs.hydraulics import PumpDuty, screen_pump_duty

    duty = PumpDuty(
        flow_rate=_q("20 m**3/hour"),
        total_head=_q("30 m"),
        fluid_density=_q("998 kg/m**3"),
        efficiency=0.7,
        motor_rating=_q("5 kW"),
        npsh_available=_q("6 m"),
        npsh_required=_q("0 m"),
    )
    entry = next(e for e in screen_pump_duty(duty).entries if "npsh" in e.name.lower())
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert entry.safety_factor is None


def test_masonry_wall_with_a_zero_unity_ratio_is_not_evaluated():
    from anvilate.packs.masonry import MasonryWall, screen_masonry_wall

    wall = MasonryWall(
        masonry_strength=_q("13.8 MPa"),
        slenderness_ratio=20.0,
        axial_stress=_q("0 MPa"),
        flexural_stress=_q("0 MPa"),
    )
    # By name: this card has two NOT_EVALUATED entries, and picking "the one with no
    # safety factor" would have matched the wrong one and pinned nothing.
    entry = next(
        e for e in screen_masonry_wall(wall).entries if e.name == "combined axial + flexure"
    )
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert entry.safety_factor is None


def test_ventilation_zone_needing_no_outdoor_air_is_not_evaluated():
    from anvilate.packs.ventilation import VentilationZone, screen_ventilation

    zone = VentilationZone(
        people_outdoor_rate=_q("2.5 L/s"),
        occupancy=0.0,
        area_outdoor_rate=_q("0.3 L/(s*m**2)"),
        floor_area=_q("0 m**2"),
        zone_air_distribution_effectiveness=1.0,
        provided_outdoor_airflow=_q("100 L/s"),
        room_volume=_q("200 m**3"),
        required_air_changes=4.0,
    )
    entry = next(e for e in screen_ventilation(zone).entries if "outdoor" in e.name.lower())
    assert entry.status is CheckStatus.NOT_EVALUATED


def test_a_zero_noise_dose_is_not_evaluated_rather_than_exactly_at_the_limit():
    from anvilate.packs.noise_exposure import WorkerNoiseExposure, screen_noise_exposure

    # A shift with no exposure time: the dose is zero because nothing was evaluated, not
    # because the worker is exactly at the regulatory limit.
    exposure = WorkerNoiseExposure(machine_levels=(85.0,), exposure_duration=_q("0 hour"))
    entry = next(e for e in screen_noise_exposure(exposure).entries if "dose" in e.name.lower())
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert entry.safety_factor is None


# --- the drainage hint must actually be an improvement --------------------


def test_the_slope_drainage_hint_never_points_at_a_wetter_slope():
    """The `< u` half of "you cannot drain past dry, and it must be an improvement".

    Dropping it left the suite green while the hint pointed at a pore pressure HIGHER than
    the slope already has — drainage advice that says "get wetter". The `0.0 <=` half had
    a test; this half did not.

    It has to be exercised on the helper directly. `_hinted` drops the hint from any
    non-failing entry, and on the failing path the guard is implied: FS is strictly
    decreasing in u, so a check that falls short always sits above its own target. The
    guard earns its place on the path whose result the scorecard discards, which is
    exactly the path a future refactor would move a hint onto.
    """
    from anvilate.packs.geotechnical import InfiniteSlope, _slope_repair_hint, screen_infinite_slope

    # A slope with margin in hand: the pressure that would bring it DOWN to the required
    # 1.5 is above the pressure it has, so drainage is not a repair and must not be named.
    comfortable = InfiniteSlope(
        cohesion=_q("30 kPa"),
        friction_angle=35.0,
        unit_weight=_q("19 kN/m**3"),
        depth=_q("2 m"),
        slope_angle=15.0,
        pore_pressure=_q("2 kPa"),
    )
    hint = _slope_repair_hint(comfortable, 1.5)
    assert hint is not None
    assert hint.parameter != "pore_pressure", (
        "the solved pressure is above the current one, so this is not a repair"
    )

    # And wherever drainage IS offered through the screen, the target is strictly below
    # the current pressure and never negative — swept, so a refactor cannot invert it.
    offered = 0
    for u in (5.0, 20.0, 40.0, 80.0):
        for beta in (10.0, 20.0, 30.0, 40.0):
            slope = InfiniteSlope(
                cohesion=_q("6 kPa"),
                friction_angle=28.0,
                unit_weight=_q("19 kN/m**3"),
                depth=_q("3 m"),
                slope_angle=beta,
                pore_pressure=_q(f"{u} kPa"),
            )
            (screened,) = screen_infinite_slope(slope).entries
            drainage = screened.repair_hint
            if drainage is not None and drainage.parameter == "pore_pressure":
                offered += 1
                assert 0.0 <= drainage.corrective_value < u, (u, beta)
    assert offered, "the sweep never reached the drainage branch, so it pinned nothing"


# --- the rest of the zero-demand family -----------------------------------
#
# A mutation pass ran four of these `else None` sites and all four survived; the rest
# were recorded as suspect rather than assumed clean. These are the rest. Each drives its
# screen to a demand of zero and asserts NOT_EVALUATED — never "exactly at the limit".


def test_lighting_install_with_no_requirement_is_not_evaluated():
    from anvilate.packs.lighting import LightingInstallation, screen_lighting

    # A zero luminaire count is rejected upstream; the branch is reached through a task
    # with no stated illuminance requirement.
    install = LightingInstallation(
        luminaire_count=12,
        lumens_per_luminaire=_q("4000 lumen"),
        input_watts_per_luminaire=_q("30 W"),
        coefficient_of_utilization=0.7,
        light_loss_factor=0.8,
        floor_area=_q("100 m**2"),
        required_illuminance=_q("0 lux"),
        allowable_power_density=_q("8 W/m**2"),
    )
    entry = next(e for e in screen_lighting(install).entries if "illuminance" in e.name.lower())
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert entry.safety_factor is None


# Five of the fourteen sites are NOT reachable, and saying so is the point of writing it
# down. `electrical.py`'s drop and ampacity guards, `hydraulics.py`'s motor and pipe-head
# guards, and `lighting.py`'s power-density guard all sit downstream of validators that
# already reject the only inputs that could reach them — `conductor_resistance` refuses a
# zero length, `pump_hydraulic_power` and `reynolds_number` a zero flow, and a luminaire
# count must be positive. Mutating those `else None` branches is EQUIVALENT, not a silent
# green: they are defensive, not load-bearing. That is a different thing from unpinned,
# and the distinction is worth recording so a later audit does not re-file them as
# findings and a later refactor does not delete them as dead.


def test_ventilation_zone_needing_no_air_changes_is_not_evaluated():
    from anvilate.packs.ventilation import VentilationZone, screen_ventilation

    zone = VentilationZone(
        people_outdoor_rate=_q("2.5 L/s"),
        occupancy=4.0,
        area_outdoor_rate=_q("0.3 L/(s*m**2)"),
        floor_area=_q("40 m**2"),
        zone_air_distribution_effectiveness=1.0,
        provided_outdoor_airflow=_q("100 L/s"),
        room_volume=_q("200 m**3"),
        required_air_changes=0.0,
    )
    entry = next(e for e in screen_ventilation(zone).entries if "air change" in e.name.lower())
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert entry.safety_factor is None


def test_an_unloaded_footing_and_an_unloaded_pile_are_not_evaluated():
    from anvilate.packs.geotechnical import (
        DrivenPile,
        ShallowFooting,
        screen_driven_pile,
        screen_shallow_footing,
    )

    (footing,) = screen_shallow_footing(
        ShallowFooting(
            width=_q("2.5 m"),
            length=_q("2.5 m"),
            embedment_depth=_q("1.5 m"),
            applied_load=_q("0 kN"),
            friction_angle=30.0,
            cohesion=_q("25 kPa"),
            unit_weight=_q("18 kN/m**3"),
        )
    ).entries
    assert footing.status is CheckStatus.NOT_EVALUATED
    assert footing.safety_factor is None
    # And no repair hint rides along on a check that was never made.
    assert footing.repair_hint is None

    (pile,) = screen_driven_pile(
        DrivenPile(
            diameter=_q("0.4 m"),
            length=_q("15 m"),
            undrained_shear_strength=_q("75 kPa"),
            adhesion_factor=0.7,
            applied_load=_q("0 kN"),
        )
    ).entries
    assert pile.status is CheckStatus.NOT_EVALUATED
    assert pile.repair_hint is None


@pytest.mark.parametrize(
    "build",
    [
        pytest.param("bolted", id="bolted connection tearout"),
        pytest.param("gusset", id="gusset plate"),
        pytest.param("bearing", id="concrete bearing"),
        pytest.param("shear_plate", id="shear plate yield and rupture"),
    ],
)
def test_unloaded_structural_connections_are_not_evaluated(build):
    """Four more screens whose `else None` was executed by the suite and asserted by none."""
    from anvilate.packs.structural import (
        BoltedConnection,
        ConcreteBearing,
        GussetPlate,
        ShearPlate,
        screen_bolted_connection,
        screen_concrete_bearing,
        screen_gusset_plate,
        screen_shear_plate,
    )

    if build == "bolted":
        card = screen_bolted_connection(
            BoltedConnection(
                name="c",
                bolt_diameter=_q("20 mm"),
                plate_thickness=_q("10 mm"),
                load=_q("0 kN"),
                bolt_material="AISI-4140",
                plate_material="ASTM-A36",
                edge_distance=_q("40 mm"),
            ),
            required_safety_factor=1.5,
        )
    elif build == "gusset":
        card = screen_gusset_plate(
            GussetPlate(
                name="g",
                net_shear_area=_q("3000 mm**2"),
                net_tension_area=_q("2000 mm**2"),
                load=_q("0 kN"),
                material="ASTM-A36",
            ),
            required_safety_factor=1.5,
        )
    elif build == "bearing":
        card = screen_concrete_bearing(
            ConcreteBearing(
                name="b",
                bearing_area=_q("40000 mm**2"),
                support_area=_q("160000 mm**2"),
                concrete_strength=_q("28 MPa"),
                load=_q("0 kN"),
            ),
            required_safety_factor=1.5,
        )
    else:
        card = screen_shear_plate(
            ShearPlate(
                name="s",
                gross_shear_area=_q("3000 mm**2"),
                net_shear_area=_q("2400 mm**2"),
                load=_q("0 kN"),
                material="ASTM-A36",
            ),
            required_safety_factor=1.5,
        )

    assert card.entries, "the screen produced no entries"
    # EVERY entry must be NOT_EVALUATED. "No entry may PASS" is too weak to pin this: with
    # the guard mutated to 1.0 and a 1.5 required factor the entry reads FAIL, which is
    # still a verdict on a check that never ran.
    assert all(e.status is CheckStatus.NOT_EVALUATED for e in card.entries), [
        (e.name, e.status) for e in card.entries
    ]
    assert all(e.safety_factor is None for e in card.entries)
