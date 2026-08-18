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

import math

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


# --- Mutation-found gaps: behavior that ran under test and was asserted by nothing ----
#
# Every test below exists because a deliberate mutation of the code it covers left the
# suite green. An 88-mutation pass against the code landed 2026-08-17 left 40 real
# survivors; these are the ones where a wrong edit would change a number a reader
# believes.


def test_pipe_flow_area_is_computed_from_the_bore_not_the_outside_diameter():
    """`flow_area`'s only assertion was `> 0`, so it could be built from the OD and stay
    green — a 25% overstatement feeding every velocity and pressure-drop screen that
    starts from a pipe designation."""
    from anvilate.standards import default_pipe_schedule_table

    pipe = default_pipe_schedule_table().get("4", "40")
    bore = 114.3 - 2 * 6.02
    assert pipe.inside_diameter.to("mm").magnitude == pytest.approx(bore, rel=1e-12)
    assert pipe.flow_area.to("mm**2").magnitude == pytest.approx(math.pi * bore**2 / 4, rel=1e-12)
    # Named so the failure says which mistake was made: the OD area is 10261 mm² and
    # pi*d**2/2 is 16426, against the true 8213.
    assert pipe.flow_area.to("mm**2").magnitude == pytest.approx(8213.0, abs=1.0)
    assert pipe.flow_area.to("mm**2").magnitude < math.pi * 114.3**2 / 4


def test_std_and_xs_diverge_at_the_first_size_where_they_part_not_only_at_the_last():
    """The module's headline claim is that STD and XS are not aliases for 40 and 80. It
    was checked only at NPS 24; the first sizes where they part were free to be
    re-aliased."""
    from anvilate.standards import default_pipe_schedule_table

    table = default_pipe_schedule_table()

    def wall(nps: str, schedule: str) -> float:
        return table.get(nps, schedule).wall_thickness.quantity.to("mm").magnitude

    # NPS 12 is where STD stops tracking Schedule 40, and NPS 10 where XS stops tracking 80.
    assert wall("10", "STD") == pytest.approx(wall("10", "40"), rel=1e-12)
    assert wall("12", "STD") == pytest.approx(9.53, rel=1e-12)
    assert wall("12", "40") == pytest.approx(10.31, rel=1e-12)
    assert wall("12", "STD") < wall("12", "40")

    assert wall("8", "XS") == pytest.approx(wall("8", "80"), rel=1e-12)
    assert wall("10", "XS") == pytest.approx(12.70, rel=1e-12)
    assert wall("10", "80") == pytest.approx(15.09, rel=1e-12)
    assert wall("10", "XS") < wall("10", "80")

    # And the held-flat property itself: past their divergence both stay constant.
    assert len({wall(n, "STD") for n in ("12", "14", "16", "18", "20", "24")}) == 1
    assert len({wall(n, "XS") for n in ("10", "12", "16", "20", "24")}) == 1


def test_the_miter_bend_honours_the_quality_factor_it_accepts():
    """Every call in the suite left E at 1.0, so the term could be dropped entirely. E is
    0.85 for ERW and 0.80 for furnace butt-welded pipe — an 18% unconservative rating."""
    from anvilate.analysis import asme_b313_miter_bend_pressure

    common = {
        "allowable_stress": _q("138 MPa"),
        "wall_thickness": _q("6.02 mm"),
        "mean_radius": _q("54.14 mm"),
        "miter_angle": 22.5,
    }
    seamless = asme_b313_miter_bend_pressure(**common).to("MPa").magnitude
    erw = asme_b313_miter_bend_pressure(quality_factor=0.85, **common).to("MPa").magnitude
    # The whole expression is linear in E, so the ratio is exact.
    assert erw == pytest.approx(seamless * 0.85, rel=1e-12)
    assert asme_b313_miter_bend_pressure(quality_factor=0.8, **common).to(
        "MPa"
    ).magnitude == pytest.approx(seamless * 0.8, rel=1e-12)

    # The steep branch's 1.25 coefficient was the one number in the function nothing
    # asserted — dropping it to 1.0 rates a 45° cut 21% high.
    steep = asme_b313_miter_bend_pressure(**{**common, "miter_angle": 45.0}).to("MPa").magnitude
    base = 138.0 * 6.02 / 54.14
    expected = base / (1.0 + 1.25 * math.tan(math.radians(45.0)) * math.sqrt(54.14 / 6.02))
    assert steep == pytest.approx(expected, rel=1e-9)


def test_the_documented_limit_constants_are_pinned_at_their_own_seams():
    """Two of the five new limits were tested so far past the seam that the constant
    itself was free: Stokes survived 1.0 -> 20.0, fluidization 20 -> 200."""
    from anvilate.analysis import minimum_fluidization_velocity, stokes_settling_velocity

    water = {
        "particle_density": _q("2650 kg/m**3"),
        "fluid_density": _q("998 kg/m**3"),
        "fluid_viscosity": _q("1e-3 Pa*s"),
    }
    # 0.103 mm quartz sits at Re = 0.98, just inside; 0.105 mm is just outside. Tested
    # at the seam so the constant itself is pinned — 1.0 survived being widened to 20.0
    # when the only inputs sat at Re = 898.
    inside = stokes_settling_velocity(particle_diameter=_q("0.103 mm"), **water)
    assert 0.9 < 998 * inside.to("m/s").magnitude * 0.103e-3 / 1e-3 < 1.0
    with pytest.raises(ValueError, match="Reynolds number"):
        stokes_settling_velocity(particle_diameter=_q("0.105 mm"), **water)

    air = {
        "particle_density": _q("2650 kg/m**3"),
        "fluid_density": _q("1.2 kg/m**3"),
        "fluid_viscosity": _q("1.8e-5 Pa*s"),
        "void_fraction": 0.4,
    }
    # 0.65 mm sand sits at Re_mf = 18.8, just inside; 0.664 mm is just outside. Same
    # reason: 20 survived being widened to 200 when the only input sat at Re_mf = 126.
    ok = minimum_fluidization_velocity(particle_diameter=_q("0.65 mm"), **air)
    assert 18.0 < 1.2 * ok.to("m/s").magnitude * 0.65e-3 / 1.8e-5 < 20.0
    with pytest.raises(ValueError, match="particle Reynolds number"):
        minimum_fluidization_velocity(particle_diameter=_q("0.664 mm"), **air)


def test_a_negative_tolerance_cannot_silently_reject_every_allowable():
    """Without the guard a negative band makes `is_valid_at` unsatisfiable, so every
    B31.3 check downgrades to NOT_EVALUATED — the failure this library exists to prevent,
    arriving as a blanket of not-evaluated greens nobody reads."""
    from anvilate.analysis import AllowableStress

    allowable = AllowableStress(
        value=_q("138 MPa"), temperature=_q("477.6 K"), material="A106-B", source="Table A-1"
    )
    assert allowable.is_valid_at(_q("477.6 K"))
    with pytest.raises(ValueError, match="must not be negative"):
        allowable.is_valid_at(_q("477.6 K"), tolerance=_q("-10 K"))
    # A zero band is legitimate and means "the exact row, nothing else".
    assert allowable.is_valid_at(_q("477.6 K"), tolerance=_q("0 K"))
    assert not allowable.is_valid_at(_q("477.0 K"), tolerance=_q("0 K"))


def test_the_pressure_scorecard_boundaries_sit_exactly_where_the_clamp_puts_them():
    """`available_wall` clamps to exactly 0.0, so the scorecard's `available <= 0` branch
    is reached at the boundary and not one step past it."""
    from anvilate.analysis import AllowableStress, asme_b313_pressure_scorecard
    from anvilate.scorecard import CheckStatus

    allowable = AllowableStress(
        value=_q("138 MPa"), temperature=_q("477.6 K"), material="A106-B", source="Table A-1"
    )
    common = {
        "design_temperature": _q("477.6 K"),
        "outside_diameter": _q("114.3 mm"),
        "allowable": allowable,
    }
    # A wall exactly consumed by its allowances: 6.02 * 0.875 = 5.2675 mm.
    exact = asme_b313_pressure_scorecard(
        "line",
        design_pressure=_q("5 MPa"),
        nominal_wall=_q("6.02 mm"),
        corrosion_allowance=_q("5.2675 mm"),
        **common,
    )
    assert exact.status is CheckStatus.NOT_EVALUATED
    assert "whole nominal wall" in exact.detail
    # A hair less allowance leaves a sliver, which rates and fails rather than vanishing.
    sliver = asme_b313_pressure_scorecard(
        "line",
        design_pressure=_q("5 MPa"),
        nominal_wall=_q("6.02 mm"),
        corrosion_allowance=_q("5.26 mm"),
        **common,
    )
    assert sliver.status is CheckStatus.FAIL
    # A zero design pressure is nothing to screen against, not a check that passed.
    assert (
        asme_b313_pressure_scorecard(
            "line", design_pressure=_q("0 MPa"), nominal_wall=_q("6.02 mm"), **common
        ).status
        is CheckStatus.NOT_EVALUATED
    )


def test_the_small_deflection_limit_sits_at_a_half_not_merely_below_five():
    """0.5 -> 5.0 was killed; 0.5 -> 0.75 was not, so the constant was pinned only loosely."""
    from anvilate.analysis.plate import PlateBendingResult

    for ratio, inside in ((0.49, True), (0.5, True), (0.51, False), (0.74, False)):
        result = PlateBendingResult(
            max_bending_stress=_q("100 MPa"),
            max_deflection=_q("1 mm"),
            small_deflection_ratio=ratio,
        )
        assert result.is_small_deflection is inside, ratio


# --- Six defects a five-agent audit found, all silent greens or unenforced limits ------


def test_a_non_finite_load_is_refused_rather_than_dropped_from_the_envelope():
    """A NaN wind load used to remove every wind combination and report PASS on gravity.

    This is the worst shape a silent green can take: the poison does not propagate, it
    *deletes*. `max` and `min` compare with `>` and `<`, both False against NaN, so the
    seven wind combinations of an ASCE 7 LRFD set — including the 0.9D + 1.0W uplift case
    the check exists to catch — were silently discarded and the largest surviving gravity
    demand was returned as governing, at a comfortable safety factor. Whether it read
    PASS or NOT_EVALUATED depended on nothing but the declaration order of the list.
    """
    from anvilate.loads import LoadNature, asce7_lrfd_basic, combination_scorecard

    combinations = asce7_lrfd_basic()
    for poison in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="not a finite number"):
            combination_scorecard(
                "uplift",
                combinations=combinations,
                loads={LoadNature.DEAD: 100.0, LoadNature.WIND: poison},
                capacity=500.0,
                required=1.5,
            )
        with pytest.raises(ValueError, match="not a finite number"):
            combinations.envelope({LoadNature.DEAD: 100.0, LoadNature.WIND: poison})
    # The finite case still finds the uplift combination it is supposed to find.
    entry = combination_scorecard(
        "uplift",
        combinations=combinations,
        loads={LoadNature.DEAD: 100.0, LoadNature.WIND: -420.0},
        capacity=500.0,
        required=1.5,
    )
    assert "0.9D" in entry.detail


def test_a_non_positive_required_safety_factor_is_refused_not_passed():
    """`required=0` made `computed < required` False for every result — every check green.

    The invariant was already enforced in thirteen places on the design-*inverse* side of
    the library and nowhere on the screening side, which is where the silent green
    actually lands: a member five times overstressed came back PASS.
    """
    from anvilate.scorecard import ScorecardEntry

    for bad in (0.0, -1.0):
        with pytest.raises(ValueError, match="required_safety_factor must be positive"):
            ScorecardEntry.from_safety_factor("overstressed", computed=0.2, required=bad)
    with pytest.raises(ValueError, match="upper safety-factor band must be positive"):
        ScorecardEntry.from_safety_factor("x", computed=2.0, required=1.5, upper=0.0)
    # The ordinary case is untouched.
    assert ScorecardEntry.from_safety_factor("x", computed=0.2, required=1.5).status is (
        CheckStatus.FAIL
    )


def test_the_centrifuge_enforces_the_creeping_flow_limit_its_docstring_names():
    """Stokes with omega^2*r for g is still Stokes, and past Re ~1 it is 6.7x too fast.

    A 100 um sand grain in water at 3,000 rpm and 150 mm returned 13.57 m/s at an implied
    particle Reynolds number of 1,357; an iterated Schiller-Naumann solve gives 2.01 m/s.
    The settling time goes as 1/v, so a centrifuge sized on it was short on residence time
    by the same 6.7x — in the optimistic direction. `drag.stokes_settling_velocity`
    already refused past this line; the centrifugal form did not.
    """
    from anvilate.analysis import centrifugal_sedimentation_velocity, centrifuge_settling_time

    slurry = {
        "density_particle": Quantity(magnitude=2650, unit="kg/m**3"),
        "density_fluid": Quantity(magnitude=1000, unit="kg/m**3"),
        "viscosity": Quantity(magnitude=1e-3, unit="Pa*s"),
        "rotational_speed": Quantity(magnitude=3000, unit="rpm"),
    }
    coarse = {"particle_diameter": Quantity(magnitude=100, unit="um"), **slurry}
    with pytest.raises(ValueError, match="creeping-flow limit"):
        centrifugal_sedimentation_velocity(radius=_q("0.15 m"), **coarse)
    with pytest.raises(ValueError, match="creeping-flow limit"):
        centrifuge_settling_time(inner_radius=_q("0.05 m"), outer_radius=_q("0.15 m"), **coarse)
    # A 1 um particle is deep in the creeping-flow regime and still answers.
    fine = {"particle_diameter": Quantity(magnitude=1, unit="um"), **slurry}
    velocity = centrifugal_sedimentation_velocity(radius=_q("0.15 m"), **fine)
    assert velocity.to("m/s").magnitude == pytest.approx(0.00135707, rel=1e-4)


def test_the_boundary_layer_forms_refuse_the_regime_they_do_not_model():
    """Eight functions documented a transition limit; every one computed Re and ignored it.

    At Re_x = 1e7 the laminar thickness reads 4.74 mm against the turbulent 44.2 mm, and
    the laminar plate drag coefficient 4.20e-4 against 2.95e-3 — a friction-drag estimate
    7x low and entirely plausible-looking. The library already enforced this same
    transition in `thermal.flat_plate_forced_convection_coefficient`; this module was the
    outlier.
    """
    from anvilate.analysis import (
        laminar_boundary_layer_thickness,
        laminar_plate_drag_coefficient,
        turbulent_boundary_layer_thickness,
        turbulent_plate_drag_coefficient,
    )

    fast = {
        "freestream_velocity": _q("50 m/s"),
        "kinematic_viscosity": Quantity(magnitude=1.5e-5, unit="m**2/s"),
    }
    with pytest.raises(ValueError, match="laminar forms hold below the transition"):
        laminar_boundary_layer_thickness(distance=_q("3 m"), **fast)
    with pytest.raises(ValueError, match="laminar forms hold below the transition"):
        laminar_plate_drag_coefficient(plate_length=_q("3 m"), **fast)
    # The turbulent forms answer there, and they are the ones that were 7-9x apart.
    assert turbulent_boundary_layer_thickness(distance=_q("3 m"), **fast).to(
        "mm"
    ).magnitude == pytest.approx(44.19, rel=1e-3)
    assert turbulent_plate_drag_coefficient(plate_length=_q("3 m"), **fast) == pytest.approx(
        2.946e-3, rel=1e-3
    )
    # And they refuse the laminar side, and past the end of their own 1e7 fit.
    slow = {
        "freestream_velocity": _q("2 m/s"),
        "kinematic_viscosity": Quantity(magnitude=1.5e-5, unit="m**2/s"),
    }
    with pytest.raises(ValueError, match="turbulent forms hold above the transition"):
        turbulent_boundary_layer_thickness(distance=_q("1 m"), **slow)
    with pytest.raises(ValueError, match="past the end of"):
        turbulent_boundary_layer_thickness(distance=_q("100 m"), **fast)


def test_the_b313_cyclic_reduction_factor_cannot_inflate_the_allowable():
    """f is a *reduction* factor capped at 1.0, and was unbounded above.

    f = 3.0 on a 138/130 MPa pair returned 615 MPa where the documented ceiling is 205 —
    a 3x-inflated allowable, in the unconservative direction, with nothing downstream to
    notice. Every other dimensionless factor in the module is bounded.
    """
    from anvilate.analysis import asme_b313_allowable_displacement_stress_range

    pair = {"cold_allowable": _q("138 MPa"), "hot_allowable": _q("130 MPa")}
    with pytest.raises(ValueError, match=r"must be in \(0, 1\]"):
        asme_b313_allowable_displacement_stress_range(stress_range_factor=3.0, **pair)
    ceiling = asme_b313_allowable_displacement_stress_range(stress_range_factor=1.0, **pair)
    assert ceiling.to("MPa").magnitude == pytest.approx(1.25 * 138 + 0.25 * 130, rel=1e-12)
    reduced = asme_b313_allowable_displacement_stress_range(stress_range_factor=0.8, **pair)
    assert reduced.to("MPa").magnitude < ceiling.to("MPa").magnitude


def test_a_fragile_nominal_pass_is_not_routine_in_the_reviewer_dossier():
    """A 46% shortfall probability used to headline as "passes" and summarise as routine.

    `review_priority`'s only closeness test was the *nominal* ratio, so a check at 1.6x
    its requirement on paper with a material chance of falling short under its own
    declared input scatter sorted below every other band, stayed out of
    ``attention_first``, and the dossier reported "nothing above routine". The nominal
    margin looking ample is exactly what makes it worth a reviewer's eye.
    """
    from anvilate.review import DecisionOrigin, ReviewPriority, review_priority
    from anvilate.scorecard import ScorecardEntry
    from anvilate.uncertainty import MarginUncertainty

    fragile = ScorecardEntry.from_safety_factor("beam bending", computed=2.4, required=1.5)
    fragile = fragile.model_copy(
        update={
            "uncertainty": MarginUncertainty(
                samples=20_000,
                seed=7,
                required=1.5,
                mean=2.4,
                std=1.4,
                shortfall_probability=0.463,
                lower=0.6,
                upper=4.9,
                coverage=0.90,
                sensitivities=(),
            )
        }
    )
    assert fragile.status is CheckStatus.PASS
    assert fragile.is_fragile() is True
    priority = review_priority(fragile, origin=DecisionOrigin.USER)
    assert priority is ReviewPriority.FRAGILE_MARGIN
    assert priority < ReviewPriority.ROUTINE
    # The same entry without a distribution is genuinely routine — nothing was flagged
    # that was not declared.
    plain = ScorecardEntry.from_safety_factor("beam bending", computed=2.4, required=1.5)
    assert review_priority(plain, origin=DecisionOrigin.USER) is ReviewPriority.ROUTINE


def test_an_empty_citation_list_is_not_a_bundle_that_agrees():
    """`design_basis_scorecard(references=[])` reported PASS on nothing at all.

    Its detail line asserted "all 0 references name an edition", which is true and
    useless. `Scorecard.status` already returns NOT_EVALUATED for an empty entry tuple
    for exactly this reason; the doctrine was not applied here.
    """
    from anvilate.standards.effectivity import DesignBasis, design_basis_scorecard

    basis = DesignBasis(pins={"AISC 360": "16"})
    empty = design_basis_scorecard("design basis", basis=basis, references=[])
    assert empty.status is CheckStatus.NOT_EVALUATED
    assert "no references were supplied" in empty.detail
    populated = design_basis_scorecard(
        "design basis", basis=basis, references=["AISC 360-16 §F2.1"]
    )
    assert populated.status is CheckStatus.PASS
