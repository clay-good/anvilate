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
    from anvilate.derivation import DerivationAbsence, Underived

    for ratio, inside in ((0.49, True), (0.5, True), (0.51, False), (0.74, False)):
        result = PlateBendingResult(
            max_bending_stress=_q("100 MPa"),
            max_deflection=_q("1 mm"),
            small_deflection_ratio=ratio,
            # Every plate case answers for its work; this probe is about the ratio.
            underived=Underived(kind=DerivationAbsence.NUMERIC_RESULT, reason="a hand-built probe"),
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


# --- Ten defects a second five-agent audit found, all in code written the same day ------


def test_the_governing_station_is_chosen_in_one_unit_not_in_whatever_was_entered():
    """A Quantity keeps the magnitude as entered, so the scan must convert before it compares.

    A member reporting 500 kN·m at one station and 1000 N·m at another handed the 1000
    downstream — a demand **500x too small**, in the unconservative direction, on a number
    nothing further down re-checks. `ExternalSectionProperties` in the same file already
    converted before comparing, which is what made this a slip rather than a design.
    """
    from anvilate.interop import (
        AxisMapping,
        ForceComponent,
        ForceStation,
        MemberForceRecord,
        bind_demand,
    )

    record = MemberForceRecord(
        member="C1",
        tool="Solver",
        tool_version="1",
        load_case="LC1",
        stations=(
            ForceStation(
                position=Quantity(magnitude=0, unit="m"),
                components={"M3": Quantity(magnitude=500.0, unit="kN*m")},
            ),
            ForceStation(
                position=Quantity(magnitude=3, unit="m"),
                components={"M3": Quantity(magnitude=1000.0, unit="N*m")},
            ),
        ),
    )
    demand = bind_demand(
        record,
        AxisMapping(labels={ForceComponent.MAJOR_BENDING: "M3"}, axial_compression_positive=True),
    )
    governing = demand.components[ForceComponent.MAJOR_BENDING]
    assert governing.to("N*mm").magnitude == pytest.approx(500e6, rel=1e-12)
    assert demand.stations[ForceComponent.MAJOR_BENDING].to("m").magnitude == 0.0


def test_an_axial_load_that_reverses_along_the_member_is_refused_not_reduced():
    """+200 kN of tension and -180 kN of compression is two cases, and abs() picks the wrong one.

    Bound by magnitude the member comes out as pure tension, which routes to AISC §H1.2
    and never checks buckling — verbatim the failure the sign declaration exists to
    prevent. Bending and shear are screened on magnitude and their sign carries no
    capacity consequence, so only the axial case is refused.
    """
    from anvilate.interop import (
        AxisMapping,
        ForceComponent,
        ForceStation,
        MemberForceRecord,
        bind_demand,
    )

    def record(*, axial: tuple[float, float], bending: tuple[float, float]):
        return MemberForceRecord(
            member="C2",
            tool="Solver",
            tool_version="1",
            load_case="LC1",
            stations=tuple(
                ForceStation(
                    position=Quantity(magnitude=position, unit="m"),
                    components={
                        "P": Quantity(magnitude=p, unit="kN"),
                        "M3": Quantity(magnitude=m, unit="kN*m"),
                    },
                )
                for position, p, m in ((0.0, axial[0], bending[0]), (3.0, axial[1], bending[1]))
            ),
        )

    mapping = AxisMapping(
        labels={ForceComponent.AXIAL: "P", ForceComponent.MAJOR_BENDING: "M3"},
        axial_compression_positive=False,
    )
    with pytest.raises(ValueError, match="changes sign along the member"):
        bind_demand(record(axial=(200.0, -180.0), bending=(10.0, 10.0)), mapping)
    # A bending moment that reverses is ordinary and still binds by magnitude.
    demand = bind_demand(record(axial=(-200.0, -180.0), bending=(-120.0, 148.0)), mapping)
    assert demand.components[ForceComponent.AXIAL].to("kN").magnitude == pytest.approx(200.0)
    assert demand.components[ForceComponent.MAJOR_BENDING].magnitude == pytest.approx(148.0)


def test_an_ignored_component_reaches_the_report_even_with_no_reason_given():
    """A dropped component no line mentions is indistinguishable from one never exported.

    That defeats the rule the mapping exists to enforce — dropping a component is an act,
    not an omission — and the original test only proved it by hand-passing an unrelated
    `ignored` dict while the mapping's own was empty.
    """
    from anvilate.interop import (
        AxisMapping,
        ForceComponent,
        ForceStation,
        MemberForceRecord,
        bind_demand,
        provenance_lines,
    )

    record = MemberForceRecord(
        member="C3",
        tool="Solver",
        tool_version="1",
        load_case="LC1",
        stations=(
            ForceStation(
                position=Quantity(magnitude=0, unit="m"),
                components={
                    "M3": Quantity(magnitude=500.0, unit="kN*m"),
                    "M2": Quantity(magnitude=41.0, unit="kN*m"),
                },
            ),
        ),
    )
    demand = bind_demand(
        record,
        AxisMapping(
            labels={ForceComponent.MAJOR_BENDING: "M3"},
            ignored=("M2",),
            axial_compression_positive=True,
        ),
    )
    assert demand.ignored == ("M2",)
    lines = "\n".join(provenance_lines(demand=demand))
    assert "not screened: M2" in lines
    # A supplied reason wins over the placeholder.
    with_reason = "\n".join(
        provenance_lines(demand=demand, ignored={"M2": "carried by the slab diaphragm"})
    )
    assert "not screened: M2 — carried by the slab diaphragm" in with_reason


def test_a_failing_check_is_not_verified_by_analysis():
    """A FAIL routed to `analysis_only` printed as `complete` and let the plan roll up green.

    A failing check is not verified by analysis — the analysis is what found it fails —
    and no verification plan over a failing design should read as passed.
    """
    from anvilate.scorecard import Scorecard, ScorecardEntry
    from anvilate.verification import plan_verification

    failing = ScorecardEntry.from_safety_factor(
        "web crippling", computed=0.4, required=1.67
    ).model_copy(update={"reference": "AISC 360-22 G3"})
    plan = plan_verification(Scorecard(entries=(failing,)))
    assert plan.failing_checks == ("web crippling",)
    assert plan.analysis_only == ()
    assert plan.status is CheckStatus.FAIL
    assert "complete" not in plan.matrix()
    assert "FAILED" in plan.matrix()
    assert "1 failing" in plan.summary()
    # A passing check with no archetype is still legitimately analysis-only.
    passing = ScorecardEntry.from_safety_factor(
        "web crippling", computed=2.4, required=1.67
    ).model_copy(update={"reference": "AISC 360-22 G3"})
    clean = plan_verification(Scorecard(entries=(passing,)))
    assert clean.analysis_only == ("web crippling",)
    assert clean.failing_checks == ()


def test_a_recorded_failure_outranks_an_unevaluated_check_in_the_plan_roll_up():
    """One unrelated check that never ran downgraded a proof test that physically cracked.

    `Scorecard` already ranks FAIL above NOT_EVALUATED; the plan checked `unresolved`
    first and inverted it, contradicting its own docstring.
    """
    from datetime import date

    from anvilate.scorecard import Scorecard, ScorecardEntry
    from anvilate.verification import VerificationOutcome, plan_verification, record_outcome

    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("bending", computed=1.2, required=1.0).model_copy(
                update={"reference": "ASME BTH-1 §3-2"}
            ),
            ScorecardEntry(
                name="fatigue",
                status=CheckStatus.NOT_EVALUATED,
                detail="no cycle data",
                reference="ASME BTH-1 §3-1.4",
            ),
        )
    )
    plan = plan_verification(card, parameters={"rated_load": _q("100 kN")})
    assert plan.unresolved  # the fatigue check
    assert plan.status is CheckStatus.NOT_EVALUATED
    cracked = record_outcome(
        plan,
        name="Proof load test",
        outcome=VerificationOutcome(
            passed=False,
            measured="cracked at the bail at 118 kN",
            performed_on=date(2026, 8, 18),
            performed_by="M. Okonkwo",
            instrument="Load cell LC-4471",
        ),
    )
    assert cracked.status is CheckStatus.FAIL


def test_a_halton_study_is_provisional_however_many_points_it_took():
    """A continuous sample never visits a grid point, so it never completes the grid.

    Unbudgeted, `count = grid_size` made `provisional` False and the summary say
    "25 of 25 points evaluated (100%, complete)" while touching none of the 25 grid points
    and neither bound on either axis — the one case where the front genuinely is
    provisional.
    """
    from anvilate.explore import (
        Objective,
        Parameter,
        SamplingStrategy,
        Study,
        StudyEvaluation,
        run_study,
    )
    from anvilate.scorecard import Scorecard, ScorecardEntry

    def evaluate(parameters):
        return StudyEvaluation(
            objectives={"f": parameters["x"]},
            scorecard=Scorecard(
                entries=(ScorecardEntry.from_safety_factor("s", computed=2.0, required=1.0),)
            ),
        )

    axes = (
        Parameter(name="x", low=0.0, high=4.0, unit="mm"),
        Parameter(name="y", low=0.0, high=4.0, unit="mm"),
    )
    halton = run_study(
        Study(
            name="h",
            parameters=axes,
            objectives=(Objective(name="f"),),
            strategy=SamplingStrategy.HALTON,
        ),
        evaluate,
    )
    assert halton.provisional is True
    assert "provisional" in halton.summary()
    # It really did miss the grid: the sequence never visits either bound on either axis,
    # so the corners a full-factorial sweep always evaluates are simply not in the set.
    # (On a box whose grid step is dyadic some interior points do coincide, which is why
    # the bounds are the honest test rather than a count of coincidences.)
    for axis in ("x", "y"):
        sampled = {point.parameters[axis] for point in halton.points}
        assert 0.0 not in sampled and 4.0 not in sampled
    # Coverage is a budget ratio for a Halton sweep and is capped rather than reported
    # as 400% when the budget exceeds the grid.
    over = run_study(
        Study(
            name="h",
            parameters=axes,
            objectives=(Objective(name="f"),),
            strategy=SamplingStrategy.HALTON,
            budget=100,
        ),
        evaluate,
    )
    assert over.coverage == pytest.approx(1.0)
    assert over.provisional is True
    # And an untruncated GRID sweep is the only thing that reports complete.
    full = run_study(Study(name="g", parameters=axes, objectives=(Objective(name="f"),)), evaluate)
    assert full.provisional is False
    assert "complete" in full.summary()


def test_a_fragile_point_is_marked_on_the_front():
    """A front sits at the edge of feasibility, which is where fragility lives.

    `best()` returned a design whose governing check falls short under its own declared
    scatter with nothing said about it — the one new roll-up that dropped a signal
    `review.py` and the report renderer both carry.
    """
    from anvilate.explore import (
        Objective,
        Parameter,
        Study,
        StudyEvaluation,
        run_study,
    )
    from anvilate.scorecard import Scorecard, ScorecardEntry
    from anvilate.uncertainty import MarginUncertainty

    def evaluate(parameters):
        entry = ScorecardEntry.from_safety_factor("bending", computed=2.2, required=1.5)
        if parameters["x"] < 1.5:  # the light end of the space is the fragile end
            entry = entry.model_copy(
                update={
                    "uncertainty": MarginUncertainty(
                        samples=20_000,
                        seed=7,
                        required=1.5,
                        mean=2.2,
                        std=1.4,
                        shortfall_probability=0.46,
                        lower=0.5,
                        upper=4.6,
                        coverage=0.90,
                        sensitivities=(),
                    )
                }
            )
        return StudyEvaluation(
            objectives={"mass": parameters["x"]}, scorecard=Scorecard(entries=(entry,))
        )

    result = run_study(
        Study(
            name="fragility",
            parameters=(Parameter(name="x", low=0.0, high=4.0, unit="mm", steps=5),),
            objectives=(Objective(name="mass"),),
        ),
        evaluate,
    )
    lightest = result.best("mass")
    assert lightest.feasible is True
    assert lightest.fragile is True
    assert len(result.fragile) == 2  # x = 0 and 1
    assert "fragile" in result.summary()
    # A point with no distribution attached is never flagged.
    assert all(not p.fragile for p in result.points if p.parameters["x"] >= 1.5)


def test_a_lifter_with_nothing_to_screen_is_refused_rather_than_passed():
    """The identification entry is context and Class 0 fatigue is an exemption.

    With neither members nor pin plates those two were the only entries, so the card rolled
    up PASS having screened nothing — the empty-card silent green `Scorecard` guards
    against, reached through the side door. It also propagated into `run_study`, whose
    feasibility rule is `card.passed`.
    """
    from anvilate.analysis import (
        DesignCategory,
        LifterDevice,
        ServiceClass,
        bth1_allowable_stresses,
        screen_lifter_device,
    )

    device = LifterDevice(
        name="spreader",
        rated_load=_q("100 kN"),
        self_weight=_q("8 kN"),
        category=DesignCategory.B,
        service_class=ServiceClass.CLASS_0,
    )
    allowables = bth1_allowable_stresses(
        yield_strength=_q("250 MPa"),
        ultimate_strength=_q("400 MPa"),
        category=DesignCategory.B,
    )
    with pytest.raises(ValueError, match="nothing would be screened"):
        screen_lifter_device(device, allowables=allowables)


def test_the_stress_block_guard_is_at_the_tension_steel_not_at_twice_the_depth():
    """`a >= 2*d` is where the lever arm changes sign, not where the physics stops.

    `a = beta1*c`, so the boundary is `a >= beta1*d` — the neutral axis reaching the bars,
    past which the steel is not in tension and `A_s*f_y*(d - a/2)` means nothing. The old
    guard waved through the whole band between, and the module's own
    `rc_net_tensile_strain` refused the identical section: same module, same physics, two
    answers.
    """
    from anvilate.analysis import rc_beam_nominal_moment, rc_net_tensile_strain

    over_reinforced = {
        "steel_area": _q("4047.6 mm**2"),
        "steel_yield": _q("420 MPa"),
        "concrete_strength": _q("25 MPa"),
        "beam_width": _q("200 mm"),
        "effective_depth": _q("300 mm"),
    }
    # a = 400 mm on d = 300 mm: c/d = 1.57, the neutral axis 57% below the bars.
    with pytest.raises(ValueError, match="reaches the tension steel"):
        rc_beam_nominal_moment(**over_reinforced)
    # The sibling that always refused it still does, and now they agree.
    with pytest.raises(ValueError, match="neutral axis reaches the steel"):
        rc_net_tensile_strain(
            stress_block_depth=_q("400 mm"),
            effective_depth=_q("300 mm"),
            concrete_strength=_q("25 MPa"),
        )
    # An ordinary under-reinforced section is untouched.
    ordinary = dict(over_reinforced, steel_area=_q("1200 mm**2"))
    assert rc_beam_nominal_moment(**ordinary).to("kN*m").magnitude == pytest.approx(
        121.316, rel=1e-4
    )


def test_a_non_finite_gdt_tolerance_cannot_build_a_frame():
    """`<= 0` is False for NaN, so a NaN tolerance walked past the positivity guard.

    Every downstream comparison then failed safe and silently, which is the quiet version
    of the same problem: a frame that exists and means nothing.
    """
    import pydantic

    from anvilate.gdt import Characteristic, FeatureControlFrame, FeatureType

    for poison in (math.nan, math.inf, -math.inf, 0.0):
        with pytest.raises(pydantic.ValidationError, match="positive, finite"):
            FeatureControlFrame(
                characteristic=Characteristic.FLATNESS,
                tolerance=Quantity(magnitude=poison, unit="mm"),
                feature_type=FeatureType.SURFACE,
            )


def test_every_bth1_limit_state_actually_travels_through_the_device_screen():
    """Only SHEAR ever reached `screen_lifter_device`, so BENDING's routing was unpinned.

    Routing a bending stress to the shear allowable passes it at 1/0.60 = 1.67x the
    margin it earned, and the whole reason `BTH1LimitState` exists is to make that
    impossible. A routing table is only as good as the rows something drives through it.
    """
    from anvilate.analysis import (
        BTH1LimitState,
        DesignCategory,
        LifterDevice,
        LifterMemberStress,
        ServiceClass,
        bth1_allowable_for,
        bth1_allowable_stresses,
        screen_lifter_device,
    )

    allowables = bth1_allowable_stresses(
        yield_strength=_q("300 MPa"),
        ultimate_strength=_q("450 MPa"),
        category=DesignCategory.B,
    )
    device = LifterDevice(
        name="spreader",
        rated_load=_q("100 kN"),
        self_weight=_q("8 kN"),
        category=DesignCategory.B,
        service_class=ServiceClass.CLASS_0,
    )
    stress = _q("40 MPa")
    # Drive EVERY limit state through the screen and check each lands on its own
    # allowable, not merely that the table maps them.
    for state in BTH1LimitState:
        entries = screen_lifter_device(
            device,
            allowables=allowables,
            members=(LifterMemberStress(name=state.value, stress=stress, limit_state=state),),
        )
        entry = next(e for e in entries if e.name == state.value)
        expected = bth1_allowable_for(allowables, state).to("MPa").magnitude
        assert entry.safety_factor == pytest.approx(expected / 40.0, rel=1e-9)
        assert f"{expected:.4g} MPa" in entry.detail
    # And the two that must differ, do: bending is S_y/N_d and shear 0.60 of it, so a
    # bending stress routed to the shear allowable would read 1.67x low.
    bending = bth1_allowable_for(allowables, BTH1LimitState.BENDING).to("MPa").magnitude
    shear = bth1_allowable_for(allowables, BTH1LimitState.SHEAR).to("MPa").magnitude
    assert shear / bending == pytest.approx(0.60, rel=1e-12)


def test_an_unresolved_check_holds_a_plan_open_even_when_every_test_passed():
    """The plan's own rule 2, unenforced at the roll-up until something drove it.

    No test built a plan with both a non-empty `unresolved` list and fully recorded
    passing outcomes — the exact combination where deleting the unresolved branch lets a
    plan report PASS over a check that was never screened.
    """
    from datetime import date

    from anvilate.scorecard import Scorecard, ScorecardEntry
    from anvilate.verification import VerificationOutcome, plan_verification, record_outcome

    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("bending", computed=1.4, required=1.0).model_copy(
                update={"reference": "ASME BTH-1 §3-2"}
            ),
            ScorecardEntry(
                name="fatigue",
                status=CheckStatus.NOT_EVALUATED,
                detail="no cycle data",
                reference="ASME BTH-1 §3-1.4",
            ),
        )
    )
    plan = plan_verification(card, parameters={"rated_load": _q("100 kN")})
    performed = record_outcome(
        plan,
        name="Proof load test",
        outcome=VerificationOutcome(
            passed=True,
            measured="125.2 kN held, no permanent set",
            performed_on=date(2026, 8, 18),
            performed_by="M. Okonkwo",
            instrument="Load cell LC-4471",
        ),
    )
    # Every planned test performed and passed...
    assert performed.verified == performed.items
    assert all(item.status is CheckStatus.PASS for item in performed.items)
    # ...and the plan is still open, because a check nobody screened is still unscreened.
    assert performed.unresolved
    assert performed.status is CheckStatus.NOT_EVALUATED


def test_a_plan_with_no_items_at_all_is_not_a_passed_plan():
    """A scorecard of purely analysis-verified checks produces zero items.

    An empty plan reporting PASS is the vacuous green the module docstring warns about,
    and it is reachable from an ordinary scorecard rather than a contrived one.
    """
    from anvilate.scorecard import Scorecard, ScorecardEntry
    from anvilate.verification import plan_verification

    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("weld throat", computed=1.4, required=1.0).model_copy(
                update={"reference": "AWS D1.1 fillet weld"}
            ),
        )
    )
    plan = plan_verification(card)
    assert plan.items == ()
    assert plan.analysis_only == ("weld throat",)
    assert plan.unresolved == ()
    assert plan.failing_checks == ()
    assert plan.status is CheckStatus.NOT_EVALUATED
    assert plan.verified == ()


def test_the_governing_station_scan_compares_magnitudes_not_signed_values():
    """A wholly negative series never updated past its first station without the abs().

    A compression axial series or a hogging moment run is entirely negative, so a signed
    `>` comparison keeps the first station forever and `bind_demand` returns it instead of
    the largest — understating the demand, in the unconservative direction.
    """
    from anvilate.interop import (
        AxisMapping,
        ForceComponent,
        ForceStation,
        MemberForceRecord,
        bind_demand,
    )

    record = MemberForceRecord(
        member="C4",
        tool="Solver",
        tool_version="1",
        load_case="LC1",
        stations=tuple(
            ForceStation(
                position=Quantity(magnitude=position, unit="m"),
                components={"M3": Quantity(magnitude=moment, unit="kN*m")},
            )
            # Wholly hogging, and the LAST station governs — the case a signed comparison
            # walks straight past.
            for position, moment in ((0.0, -40.0), (3.0, -95.0), (6.0, -160.0))
        ),
    )
    demand = bind_demand(
        record,
        AxisMapping(labels={ForceComponent.MAJOR_BENDING: "M3"}, axial_compression_positive=True),
    )
    assert demand.components[ForceComponent.MAJOR_BENDING].magnitude == pytest.approx(-160.0)
    assert demand.stations[ForceComponent.MAJOR_BENDING].to("m").magnitude == 6.0
    # A tie keeps the FIRST station it was found at, which is the documented order and the
    # only thing that distinguishes `>` from `>=` here.
    tied = MemberForceRecord(
        member="C5",
        tool="Solver",
        tool_version="1",
        load_case="LC1",
        stations=tuple(
            ForceStation(
                position=Quantity(magnitude=position, unit="m"),
                components={"M3": Quantity(magnitude=-100.0, unit="kN*m")},
            )
            for position in (0.0, 3.0, 6.0)
        ),
    )
    tied_demand = bind_demand(
        tied,
        AxisMapping(labels={ForceComponent.MAJOR_BENDING: "M3"}, axial_compression_positive=True),
    )
    assert tied_demand.stations[ForceComponent.MAJOR_BENDING].to("m").magnitude == 0.0


# --- the NaN family: a poisoned candidate is DROPPED by max()/min(), never propagated ------
#
# `if x <= 0: raise` is a no-op against NaN, because every comparison with NaN is False. On
# its own that would leave a NaN in the answer, which is visible. What makes it a silent
# green is the second half: `max()`/`min()` pick the governing case by comparison too, so
# the poisoned candidate does not contaminate the envelope — it *disappears from it*, and
# the result comes back smaller, complete-looking, and passing.
#
# A five-agent audit found thirteen instances. The fix is one shape: the shared `_require`
# dimension helper in 48 analysis modules now also refuses a non-finite magnitude, and the
# handful of modules with their own validators got the same rule. Each test below is one of
# the thirteen, pinned by the number the old code returned.

_NAN = float("nan")


def _qty(magnitude: float, unit: str) -> Quantity:
    return Quantity(magnitude=magnitude, unit=unit)


def test_a_nan_fastener_coordinate_cannot_return_a_zero_peak_force():
    # The worst of the thirteen: `peak = max(peak, ...)` seeded at 0.0 kept the seed when
    # every candidate went NaN, and a zero peak force is an infinite safety factor.
    from anvilate.analysis.fastener import eccentric_shear_group_peak_force

    positions = [(_qty(-50, "mm"), _qty(0, "mm")), (_qty(50, "mm"), _qty(0, "mm"))]
    good = [*positions, (_qty(0, "mm"), _qty(60, "mm"))]
    poisoned = [*positions, (_qty(_NAN, "mm"), _qty(60, "mm"))]
    kwargs = {"load": _qty(100, "kN"), "eccentricity": _qty(200, "mm")}
    assert eccentric_shear_group_peak_force(positions=good, **kwargs).magnitude == pytest.approx(
        149612, rel=1e-4
    )
    with pytest.raises(ValueError, match="finite"):
        eccentric_shear_group_peak_force(positions=poisoned, **kwargs)


def test_a_nan_weld_endpoint_cannot_return_a_zero_peak_stress():
    from anvilate.analysis.weld import eccentric_weld_group_peak_stress

    first = ((_qty(-100, "mm"), _qty(0, "mm")), (_qty(100, "mm"), _qty(0, "mm")))
    good = [first, ((_qty(100, "mm"), _qty(0, "mm")), (_qty(100, "mm"), _qty(100, "mm")))]
    poisoned = [first, ((_qty(100, "mm"), _qty(0, "mm")), (_qty(_NAN, "mm"), _qty(100, "mm")))]
    kwargs = {"load": _qty(50, "kN"), "eccentricity": _qty(150, "mm"), "leg_size": _qty(8, "mm")}
    assert eccentric_weld_group_peak_stress(segments=good, **kwargs).magnitude == pytest.approx(
        110.213, rel=1e-4
    )
    with pytest.raises(ValueError, match="finite"):
        eccentric_weld_group_peak_stress(segments=poisoned, **kwargs)


def test_a_nan_slenderness_cannot_make_a_buckling_failure_report_as_yielding():
    # The cleanest verdict flip in the set: FAIL at 147.5 MPa became PASS at 241 MPa, with
    # `member_buckling = nan MPa` sitting in the returned object, ignored by min().
    from anvilate.analysis.aluminum import (
        AlloyProperties,
        TemperGroup,
        aluminum_compression_strength,
    )

    props = AlloyProperties(
        name="6061-T6",
        compressive_yield=_qty(241, "MPa"),
        tensile_yield=_qty(241, "MPa"),
        tensile_ultimate=_qty(290, "MPa"),
        elastic_modulus=_qty(70000, "MPa"),
        temper_group=TemperGroup.ARTIFICIALLY_AGED,
        source="ADM 2020 Table A.3.4",
    )
    kwargs = {"flat_width": _qty(50, "mm"), "thickness": _qty(5, "mm")}
    sound = aluminum_compression_strength(properties=props, slenderness=60.0, **kwargs)
    assert sound is not None and sound.nominal.to("MPa").magnitude == pytest.approx(147.5, rel=1e-2)
    with pytest.raises(ValueError, match="finite"):
        aluminum_compression_strength(properties=props, slenderness=_NAN, **kwargs)


def test_a_nan_wind_load_cannot_delete_the_wind_combinations():
    # `max(combinations)` drops every combination containing the poisoned load, and the
    # governing effect is reported from the survivors -- 470 kN became 200 kN.
    from anvilate.analysis.load_combinations import (
        asce7_asd_factored_load,
        asce7_lrfd_factored_load,
    )

    assert asce7_lrfd_factored_load(
        dead=_qty(100, "kN"), live=_qty(50, "kN"), wind=_qty(300, "kN")
    ).magnitude == pytest.approx(470.0)
    with pytest.raises(ValueError, match="finite"):
        asce7_lrfd_factored_load(dead=_qty(100, "kN"), live=_qty(50, "kN"), wind=_qty(_NAN, "kN"))
    with pytest.raises(ValueError, match="finite"):
        asce7_asd_factored_load(dead=_qty(100, "kN"), live=_qty(50, "kN"), seismic=_qty(_NAN, "kN"))


def test_a_nan_transverse_second_moment_cannot_hide_the_weak_axis():
    # `least_radius_of_gyration` is documented as governing over both axes; min() dropped
    # the poisoned axis and it returned the STRONG-axis value, 4.5x too large.
    base = {
        "area": _qty(5000, "mm**2"),
        "second_moment": _qty(1e8, "mm**4"),
        "extreme_fibre": _qty(150, "mm"),
    }
    sound = CrossSection(**base, second_moment_transverse=_qty(5e6, "mm**4"))
    assert sound.least_radius_of_gyration.to("mm").magnitude == pytest.approx(31.6228, rel=1e-5)
    with pytest.raises(ValueError, match="finite"):
        CrossSection(**base, second_moment_transverse=_qty(_NAN, "mm**4"))


def test_a_nan_principal_stress_cannot_depend_on_which_slot_it_lands_in():
    # max() - min() dropped a NaN in the middle slot (a clean 150 MPa) and propagated one
    # in the first (nan). The order-dependence was itself the proof it was wrong.
    from anvilate.analysis.stress import tresca_principal

    assert tresca_principal(
        sigma_1=_qty(100, "MPa"), sigma_2=_qty(400, "MPa"), sigma_3=_qty(-50, "MPa")
    ).magnitude == pytest.approx(450.0)
    for slot in ("sigma_1", "sigma_2", "sigma_3"):
        args = {
            "sigma_1": _qty(100, "MPa"),
            "sigma_2": _qty(400, "MPa"),
            "sigma_3": _qty(-50, "MPa"),
        }
        args[slot] = _qty(_NAN, "MPa")
        with pytest.raises(ValueError, match="finite"):
            tresca_principal(**args)


def test_a_nan_net_area_cannot_delete_the_rupture_limit_state():
    from anvilate.analysis.fastener import aisc_tension_member_design_strength

    kwargs = {
        "gross_area": _qty(3000, "mm**2"),
        "yield_strength": _qty(345, "MPa"),
        "ultimate_strength": _qty(450, "MPa"),
    }
    assert aisc_tension_member_design_strength(
        effective_net_area=_qty(1500, "mm**2"), **kwargs
    ).magnitude == pytest.approx(506.25)
    with pytest.raises(ValueError, match="finite"):
        aisc_tension_member_design_strength(effective_net_area=_qty(_NAN, "mm**2"), **kwargs)


def test_a_nan_bolt_diameter_cannot_delete_the_bearing_cap():
    from anvilate.analysis.fastener import bolt_bearing_strength

    kwargs = {
        "clear_distance": _qty(60, "mm"),
        "plate_thickness": _qty(10, "mm"),
        "ultimate_strength": _qty(450, "MPa"),
    }
    assert bolt_bearing_strength(bolt_diameter=_qty(20, "mm"), **kwargs).magnitude == pytest.approx(
        216.0
    )
    with pytest.raises(ValueError, match="finite"):
        bolt_bearing_strength(bolt_diameter=_qty(_NAN, "mm"), **kwargs)


def test_a_nan_thrust_cannot_delete_the_thrust_term_of_the_iso_76_load():
    from anvilate.analysis.bearing import bearing_equivalent_static_load

    kwargs = {"radial_load": _qty(2000, "N"), "radial_factor": 0.6, "axial_factor": 0.5}
    assert bearing_equivalent_static_load(
        axial_load=_qty(8000, "N"), **kwargs
    ).magnitude == pytest.approx(5200.0)
    with pytest.raises(ValueError, match="finite"):
        bearing_equivalent_static_load(axial_load=_qty(_NAN, "N"), **kwargs)


def test_a_nan_pressure_cannot_delete_the_operating_bolt_load():
    from anvilate.analysis.gasket import governing_gasket_bolt_load

    kwargs = {
        "gasket_mean_diameter": _qty(300, "mm"),
        "effective_seating_width": _qty(10, "mm"),
        "seating_stress": _qty(25, "MPa"),
        "gasket_factor": 3.0,
    }
    assert governing_gasket_bolt_load(pressure=_qty(5, "MPa"), **kwargs).magnitude == pytest.approx(
        636173, rel=1e-4
    )
    with pytest.raises(ValueError, match="finite"):
        governing_gasket_bolt_load(pressure=_qty(_NAN, "MPa"), **kwargs)


def test_a_nan_allowable_cannot_leave_a_riveted_joint_with_a_governing_mode():
    from anvilate.analysis.rivet import riveted_joint_efficiency

    kwargs = {
        "pitch": _qty(60, "mm"),
        "rivet_diameter": _qty(20, "mm"),
        "plate_thickness": _qty(10, "mm"),
        "allowable_tension": _qty(100, "MPa"),
        "allowable_bearing": _qty(200, "MPa"),
    }
    sound = riveted_joint_efficiency(allowable_shear=_qty(80, "MPa"), **kwargs)
    assert sound.governing_mode in {"tearing", "shearing", "crushing"}
    with pytest.raises(ValueError, match="finite"):
        riveted_joint_efficiency(allowable_shear=_qty(_NAN, "MPa"), **kwargs)


def test_a_nan_elastic_buckling_load_cannot_leave_the_dsm_nominal_defined():
    # The DSM nominal is the minimum of three modes. With one unknown there is no minimum,
    # and min() reported LOCAL as governing with the distortional mode simply absent.
    from anvilate.analysis.cold_formed_steel import ElasticBuckling

    with pytest.raises(ValueError, match="finite"):
        ElasticBuckling(
            local=_qty(500, "kN"),
            global_=_qty(800, "kN"),
            distortional=_qty(_NAN, "kN"),
            source="CUFSM 5.01",
        )


def test_a_nan_flange_width_cannot_earn_the_unreduced_plastic_moment():
    # Two families in one function: the NaN skipped the "slender flange, F7 not
    # implemented" refusal AND the local-buckling reduction, returning M_p exactly.
    from anvilate.analysis.beam import aisc_rectangular_hss_flexural_strength

    kwargs = {
        "web_flat_height": _qty(280, "mm"),
        "wall_thickness": _qty(6, "mm"),
        "yield_strength": _qty(345, "MPa"),
        "elastic_modulus": _qty(200000, "MPa"),
        "plastic_section_modulus": _qty(8e5, "mm**3"),
        "elastic_section_modulus": _qty(7e5, "mm**3"),
    }
    assert aisc_rectangular_hss_flexural_strength(
        flange_flat_width=_qty(180, "mm"), **kwargs
    ).magnitude == pytest.approx(260.537, rel=1e-4)
    with pytest.raises(ValueError, match="finite"):
        aisc_rectangular_hss_flexural_strength(flange_flat_width=_qty(_NAN, "mm"), **kwargs)


def test_the_shared_dimension_helper_refuses_non_finite_across_the_analysis_layer():
    """The root-cause fix, asserted as one property rather than module by module.

    Forty-eight analysis modules share the same private ``_require`` dimension helper. It
    now refuses a non-finite magnitude, and this is what stops the next instance of this
    family from shipping: a module that copies the helper without the finiteness line
    fails here rather than in an audit six months later.
    """
    import importlib
    import inspect
    import pkgutil

    import anvilate.analysis as analysis_pkg

    unguarded = []
    for module_info in pkgutil.iter_modules(analysis_pkg.__path__):
        module = importlib.import_module(f"anvilate.analysis.{module_info.name}")
        helper = getattr(module, "_require", None)
        if helper is None or not inspect.isfunction(helper):
            continue
        source = inspect.getsource(helper)
        if "require_finite" not in source:
            unguarded.append(module_info.name)
    assert not unguarded, (
        "analysis modules whose _require helper checks dimension but not finiteness — a "
        f"NaN through one of these is dropped by the next max()/min(): {unguarded}"
    )
    # And prove the helper actually refuses, rather than trusting the source scan.
    from anvilate.analysis.fastener import _require

    _require(Quantity(magnitude=1.0, unit="mm"), "[length]", "ok")
    with pytest.raises(ValueError, match="finite"):
        _require(Quantity(magnitude=_NAN, unit="mm"), "[length]", "poisoned")


# --- the guard-the-domain family: a documented limit that nothing enforced ------------------
#
# The highest-yield defect class in this library is not a wrong formula. It is a *correct*
# formula with a validity limit stated in its own docstring and checked nowhere — so the
# function answers confidently outside the range it says it holds in, and every one of these
# answered in the unconservative direction. Each test pins the number the unguarded version
# returned, so the guard cannot be quietly widened back out.


def test_the_thin_wall_forms_refuse_a_wall_they_do_not_describe():
    from anvilate.analysis.pressure_vessel import (
        thick_wall_cylinder,
        thin_wall_cylinder,
        thin_wall_thickness_for_pressure,
    )

    # r/t = 20: comfortably inside the membrane scope.
    assert thin_wall_cylinder(
        pressure=_qty(10, "MPa"), radius=_qty(500, "mm"), wall_thickness=_qty(25, "mm")
    ).hoop_stress.to("MPa").magnitude == pytest.approx(200.0)
    # r/t = 2: the membrane hoop was 20 MPa against the exact 26 MPa at the bore.
    thick = thick_wall_cylinder(
        pressure=_qty(10, "MPa"), radius=_qty(50, "mm"), wall_thickness=_qty(25, "mm")
    )
    assert thick.hoop_stress.to("MPa").magnitude == pytest.approx(26.0, rel=1e-3)
    with pytest.raises(ValueError, match="thin-wall membrane"):
        thin_wall_cylinder(
            pressure=_qty(10, "MPa"), radius=_qty(50, "mm"), wall_thickness=_qty(25, "mm")
        )
    # And the sizing inverse, which is the worse half: it returned a 25 mm wall that runs
    # 30% over the allowable it was sized against.
    with pytest.raises(ValueError, match="thin-wall membrane"):
        thin_wall_thickness_for_pressure(
            pressure=_qty(100, "MPa"), radius=_qty(50, "mm"), allowable_stress=_qty(200, "MPa")
        )


def test_classical_shell_buckling_refuses_a_wall_that_is_not_a_shell():
    from anvilate.analysis.pressure_vessel import (
        cylinder_axial_buckling_stress,
        cylinder_external_pressure_buckling,
        sphere_external_pressure_buckling,
    )

    thin = {"wall_thickness": _qty(5, "mm"), "mean_radius": _qty(500, "mm")}
    stubby = {"wall_thickness": _qty(50, "mm"), "mean_radius": _qty(50, "mm")}
    common = {"elastic_modulus": _qty(200000, "MPa"), "poisson": 0.3}
    assert cylinder_axial_buckling_stress(**thin, **common).to("MPa").magnitude == pytest.approx(
        1210.46, rel=1e-4
    )
    # At t/R = 1 the axial form returned 121046 MPa — 0.6·E, ~350x a structural steel yield.
    for function in (
        cylinder_axial_buckling_stress,
        cylinder_external_pressure_buckling,
        sphere_external_pressure_buckling,
    ):
        with pytest.raises(ValueError, match="thin-shell scope"):
            function(**stubby, **common)


def test_the_masonry_steel_allowable_is_capped_by_the_code_it_cites():
    from anvilate.analysis.masonry import masonry_column_axial_capacity

    kwargs = {
        "masonry_strength": _qty(13.8, "MPa"),
        "net_area": _qty(90000, "mm**2"),
        "slenderness_ratio": 30.0,
        "steel_area": _qty(2000, "mm**2"),
    }
    assert masonry_column_axial_capacity(steel_allowable_stress=_qty(165, "MPa"), **kwargs).to(
        "kN"
    ).magnitude == pytest.approx(500.893, rel=1e-4)
    # 0.6*f_y for Grade 60 is 248 MPa — the natural input, and 21% of phantom capacity.
    with pytest.raises(ValueError, match="TMS 402 cap"):
        masonry_column_axial_capacity(steel_allowable_stress=_qty(248, "MPa"), **kwargs)


def test_tension_field_action_is_refused_where_aisc_does_not_permit_it():
    from anvilate.analysis.beam import aisc_tension_field_shear_strength

    kwargs = {
        "web_area": _qty(12000, "mm**2"),
        "web_depth": _qty(1500, "mm"),
        "web_thickness": _qty(8, "mm"),
        "yield_strength": _qty(345, "MPa"),
        "elastic_modulus": _qty(200000, "MPa"),
    }
    # h/t_w = 187.5, so §G2.2(b) caps a/h at (260/187.5)² = 1.92.
    assert aisc_tension_field_shear_strength(stiffener_spacing=_qty(1500, "mm"), **kwargs).to(
        "kN"
    ).magnitude == pytest.approx(1765.55, rel=1e-4)
    for spacing, ratio in ((4500, 3), (7500, 5), (30000, 20)):
        with pytest.raises(ValueError, match="G2.2"):
            aisc_tension_field_shear_strength(stiffener_spacing=_qty(spacing, "mm"), **kwargs)
        assert ratio > 1.92  # every one of these collected a bonus it was not entitled to


def test_churchill_chu_reports_not_evaluated_past_its_stated_rayleigh_ceiling():
    from anvilate.analysis.thermal import horizontal_cylinder_natural_convection_coefficient

    air = {
        "thermal_conductivity": _qty(0.03, "W/(m*K)"),
        "kinematic_viscosity": _qty(1.6e-5, "m**2/s"),
        "prandtl_number": 0.7,
        "thermal_expansion_coefficient": _qty(1 / 300, "1/K"),
    }
    inside = horizontal_cylinder_natural_convection_coefficient(
        surface_temperature_difference=_qty(20, "K"), diameter=_qty(0.1, "m"), **air
    )
    assert inside is not None
    # Ra_D = 3.35e12, past the stated 1e12: None, matching the forced-convection siblings.
    assert (
        horizontal_cylinder_natural_convection_coefficient(
            surface_temperature_difference=_qty(300, "K"), diameter=_qty(5, "m"), **air
        )
        is None
    )


def test_a_wire_drawing_pass_past_r_max_is_refused_not_priced():
    from anvilate.analysis.wire_drawing import wire_drawing_max_reduction, wire_drawing_stress

    die = {"die_half_angle": 6.0, "friction_coefficient": 0.05}
    assert wire_drawing_max_reduction(**die) == pytest.approx(0.4924, rel=1e-3)
    assert wire_drawing_stress(
        flow_stress=_qty(400, "MPa"),
        initial_area=_qty(100, "mm**2"),
        final_area=_qty(70, "mm**2"),
        **die,
    ).to("MPa").magnitude == pytest.approx(210.54, rel=1e-4)
    # An 80% reduction returned 950 MPa — 2.4x the wire's own flow stress.
    with pytest.raises(ValueError, match="r_max"):
        wire_drawing_stress(
            flow_stress=_qty(400, "MPa"),
            initial_area=_qty(100, "mm**2"),
            final_area=_qty(20, "mm**2"),
            **die,
        )


def test_the_parabolic_cable_forms_hand_off_to_the_catenary_outside_shallow_sag():
    from anvilate.analysis.cable import (
        catenary_max_tension,
        catenary_sag,
        parabolic_cable_max_tension,
        parabolic_cable_sag,
    )

    cable = {"weight_per_length": _qty(10, "N/m"), "span": _qty(100, "m")}
    shallow = {**cable, "horizontal_tension": _qty(1250, "N")}
    # d/L = 0.10: the parabola is within about 1.3% of the exact catenary.
    parabolic = parabolic_cable_sag(**shallow).to("m").magnitude
    exact = catenary_sag(**shallow).to("m").magnitude
    assert parabolic == pytest.approx(10.0)
    assert abs(parabolic - exact) / exact < 0.02
    # d/L = 0.20: sag 5.2% under and T_max 4.3% under, both unconservative, both refused.
    deep = {**cable, "horizontal_tension": _qty(625, "N")}
    for function in (parabolic_cable_sag, parabolic_cable_max_tension):
        with pytest.raises(ValueError, match="shallow-sag"):
            function(**deep)
    assert catenary_sag(**deep).to("m").magnitude == pytest.approx(21.0897, rel=1e-4)
    assert catenary_max_tension(**deep).to("N").magnitude == pytest.approx(835.897, rel=1e-4)


def test_nucleate_boiling_refuses_a_flux_past_the_critical_heat_flux():
    from anvilate.analysis.boiling import (
        critical_heat_flux,
        nucleate_boiling_excess_temperature,
        nucleate_boiling_heat_flux,
    )

    water = {
        "latent_heat": _qty(2257, "kJ/kg"),
        "liquid_density": _qty(957.9, "kg/m**3"),
        "vapor_density": _qty(0.5956, "kg/m**3"),
        "surface_tension": _qty(0.0589, "N/m"),
    }
    rohsenow = {
        "liquid_viscosity": _qty(2.79e-4, "Pa*s"),
        "liquid_specific_heat": _qty(4217, "J/(kg*K)"),
        "surface_fluid_coefficient": 0.0130,
        "prandtl_number": 1.76,
        "fluid_exponent": 1.0,
        **water,
    }
    chf = critical_heat_flux(**water).to("W/m**2").magnitude
    assert chf == pytest.approx(1.2585e6, rel=1e-3)
    assert nucleate_boiling_heat_flux(excess_temperature=_qty(10, "K"), **rohsenow).to(
        "W/m**2"
    ).magnitude == pytest.approx(1.369e5, rel=1e-3)
    # ΔT_e = 100 K returned 1.37e8 W/m², 109x the hydrodynamic maximum.
    with pytest.raises(ValueError, match="critical heat flux"):
        nucleate_boiling_heat_flux(excess_temperature=_qty(100, "K"), **rohsenow)
    # And the inverse: a 5 MW/m² duty is unachievable, and answered with a benign 33 K.
    with pytest.raises(ValueError, match="critical heat flux"):
        nucleate_boiling_excess_temperature(heat_flux=_qty(5e6, "W/m**2"), **rohsenow)


def test_luminous_efficiency_cannot_exceed_one():
    from anvilate.analysis.photometry import luminous_efficiency

    assert luminous_efficiency(luminous_efficacy=_qty(683, "lm/W")) == pytest.approx(1.0)
    assert luminous_efficiency(luminous_efficacy=_qty(100, "lm/W")) == pytest.approx(
        0.14641, rel=1e-4
    )
    # 1000 lm/W returned 1.464 — a source 46% better than the physical ideal.
    for efficacy in (700, 1000, 5000):
        with pytest.raises(ValueError, match="physical maximum"):
            luminous_efficiency(luminous_efficacy=_qty(efficacy, "lm/W"))


def test_the_half_power_method_refuses_damping_it_cannot_measure():
    from anvilate.analysis.dynamics import damping_ratio_from_half_power_bandwidth

    # ζ = 0.05: the approximation is good to 0.3%.
    assert damping_ratio_from_half_power_bandwidth(
        resonant_frequency=_qty(100, "Hz"), half_power_bandwidth=_qty(10.025, "Hz")
    ) == pytest.approx(0.0501, rel=1e-2)
    # A true ζ = 0.30 has Δf = 68.235 Hz and returned 0.341 — 14% high, and an overstated
    # damping understates every resonant response computed from it.
    with pytest.raises(ValueError, match="half-power"):
        damping_ratio_from_half_power_bandwidth(
            resonant_frequency=_qty(100, "Hz"), half_power_bandwidth=_qty(68.2354, "Hz")
        )


def test_swt_refuses_the_compressive_mean_it_is_not_a_model_for():
    from anvilate.analysis.fatigue import smith_watson_topper_stress

    # σ_max = σ_a is the fully-reversed edge of the domain: σ_ar = σ_a.
    assert smith_watson_topper_stress(
        max_stress=_qty(100, "MPa"), alternating_stress=_qty(100, "MPa")
    ).to("MPa").magnitude == pytest.approx(100.0)
    # σ_max = 20, σ_a = 100 is a −80 MPa mean, and returned 44.7 MPa: a 2.24x understatement
    # of the stress the caller looks up on an S-N curve.
    with pytest.raises(ValueError, match="compressive"):
        smith_watson_topper_stress(max_stress=_qty(20, "MPa"), alternating_stress=_qty(100, "MPa"))


def test_the_preloaded_bolt_forms_refuse_a_load_past_joint_separation():
    from anvilate.analysis.fastener import (
        bolt_load_in_joint,
        joint_separation_load,
        preloaded_bolt_cyclic_stress,
    )

    joint = {"preload": _qty(20, "kN"), "stiffness_factor": 0.25}
    separation = joint_separation_load(**joint).to("kN").magnitude
    assert separation == pytest.approx(26.667, rel=1e-3)
    assert bolt_load_in_joint(external_load=_qty(20, "kN"), **joint).to(
        "N"
    ).magnitude == pytest.approx(25000.0)
    # 60 kN is 2.25x separation: the bolt load came back 1.71x low, the alternating stress
    # 2.67x low, and Goodman reported n = 0.97 against a true 0.44.
    with pytest.raises(ValueError, match="separation"):
        bolt_load_in_joint(external_load=_qty(60, "kN"), **joint)
    with pytest.raises(ValueError, match="separation"):
        preloaded_bolt_cyclic_stress(
            min_external_load=_qty(0, "kN"),
            max_external_load=_qty(60, "kN"),
            tensile_stress_area=_qty(84.3, "mm**2"),
            **joint,
        )


def test_the_stirrup_spacing_carries_the_aci_cap_it_used_to_delegate():
    from anvilate.analysis.reinforced_concrete import rc_stirrup_spacing_for_shear

    bar = {
        "stirrup_area": _qty(142, "mm**2"),
        "stirrup_yield": _qty(420, "MPa"),
        "effective_depth": _qty(500, "mm"),
    }
    # A light demand: strength alone allowed 1491 mm, where ACI permits d/2 = 250 mm.
    assert rc_stirrup_spacing_for_shear(required_shear_strength=_qty(20, "kN"), **bar).to(
        "mm"
    ).magnitude == pytest.approx(250.0)
    # A heavy demand is strength-governed and the cap does not bind.
    assert rc_stirrup_spacing_for_shear(required_shear_strength=_qty(300, "kN"), **bar).to(
        "mm"
    ).magnitude == pytest.approx(99.4, rel=1e-3)
    # And the 600 mm ceiling binds where d/2 would not.
    assert rc_stirrup_spacing_for_shear(
        required_shear_strength=_qty(20, "kN"),
        stirrup_area=_qty(142, "mm**2"),
        stirrup_yield=_qty(420, "MPa"),
        effective_depth=_qty(2000, "mm"),
    ).to("mm").magnitude == pytest.approx(600.0)


def test_the_road_geometry_rates_refuse_a_percent_where_a_decimal_belongs():
    from anvilate.analysis.road_curve import minimum_curve_radius, stopping_sight_distance

    assert minimum_curve_radius(
        design_speed=_qty(100, "km/hr"), superelevation_rate=0.08, side_friction_factor=0.12
    ).to("m").magnitude == pytest.approx(393.4, rel=1e-3)
    # AASHTO tabulates e as 8%; entering 8.0 returned a 3.93 m minimum radius.
    with pytest.raises(ValueError, match="decimal fraction"):
        minimum_curve_radius(
            design_speed=_qty(100, "km/hr"), superelevation_rate=8.0, side_friction_factor=12.0
        )
    drive = {"speed": _qty(100, "km/hr"), "deceleration": _qty(3.4, "m/s**2")}
    reaction = {"reaction_time": _qty(2.5, "s")}
    assert stopping_sight_distance(grade=0.06, **drive, **reaction).to(
        "m"
    ).magnitude == pytest.approx(166.2, rel=1e-3)
    # The old guard was one-sided: it caught the downgrade and let a 6.0 upgrade through,
    # which is the direction that SHORTENS the answer — 75.6 m against the true 166.2 m.
    with pytest.raises(ValueError, match="decimal fraction"):
        stopping_sight_distance(grade=6.0, **drive, **reaction)


# --- guard bodies nothing had ever executed -------------------------------------------------
#
# A guard-coverage instrument over the whole package found that only 1,649 of 4,045
# `raise ValueError(...)` refusals ever run under the suite. Most of the rest are bare
# positivity checks, but 21 of them hold a real PHYSICAL domain limit — Poisson's ratio
# below 0.5, an angle below 90°, a Compton scattering angle at or under 180° — and every
# one of those constants was widened tenfold in one batched mutation run with the full
# suite still green. The function bodies are exercised; only the refusals are not, so the
# numbers in them were unpinned. These reach them.


@pytest.mark.parametrize(
    ("call", "match"),
    [
        pytest.param(
            lambda: __import__(
                "anvilate.analysis.elastic_constants", fromlist=["x"]
            ).lame_first_parameter(
                elastic_modulus=Quantity(magnitude=200000, unit="MPa"), poisson_ratio=0.5
            ),
            "0.5",
            id="lame-poisson",
        ),
        pytest.param(
            lambda: __import__(
                "anvilate.analysis.acoustics", fromlist=["x"]
            ).coincidence_critical_frequency(
                thickness=Quantity(magnitude=10, unit="mm"),
                youngs_modulus=Quantity(magnitude=70000, unit="MPa"),
                density=Quantity(magnitude=2700, unit="kg/m**3"),
                poissons_ratio=0.5,
                sound_speed=Quantity(magnitude=343, unit="m/s"),
            ),
            "0.5",
            id="acoustics-poisson",
        ),
        pytest.param(
            lambda: __import__("anvilate.analysis.optics", fromlist=["x"]).snell_refraction_angle(
                incident_angle=90.0, incident_index=1.0, refracted_index=1.5
            ),
            "90",
            id="snell-angle",
        ),
        pytest.param(
            lambda: __import__(
                "anvilate.analysis.compton", fromlist=["x"]
            ).compton_scattered_wavelength(
                incident_wavelength=Quantity(magnitude=1, unit="pm"), scattering_angle=181.0
            ),
            "180",
            id="compton-angle",
        ),
        pytest.param(
            lambda: __import__(
                "anvilate.analysis.solar_geometry", fromlist=["x"]
            ).solar_altitude_angle(latitude=45.0, declination=91.0, hour_angle=0.0),
            "90",
            id="declination",
        ),
    ],
)
def test_a_physical_domain_ceiling_actually_refuses(call, match):
    with pytest.raises(ValueError, match=match):
        call()


# --- a second wave, over the modules the first one did not reach -----------------------------
#
# The same lens as above, run again after the first sweep's fixes landed. Six more, all in
# modules the first pass never opened, and every one answered in the flattering direction.


def test_the_alfven_speed_cannot_exceed_the_speed_of_light():
    from anvilate.analysis.plasma import alfven_speed

    # A fusion plasma: 5 T at 3.3e-7 kg/m³ runs at 7.76e6 m/s, well inside the form.
    assert alfven_speed(
        magnetic_flux_density=_qty(5, "T"), mass_density=_qty(3.3e-7, "kg/m**3")
    ).to("m/s").magnitude == pytest.approx(7.7644e6, rel=1e-3)
    # A pulsar magnetosphere returned 8.9e16 m/s — 3e8 times c — with no complaint.
    with pytest.raises(ValueError, match="speed of light"):
        alfven_speed(magnetic_flux_density=_qty(1e8, "T"), mass_density=_qty(1e-12, "kg/m**3"))


def test_a_compressor_cannot_be_more_than_ideally_efficient():
    from anvilate.analysis.isentropic_efficiency import compressor_isentropic_efficiency

    kwargs = {"inlet_temperature": _qty(300, "K"), "isentropic_outlet_temperature": _qty(450, "K")}
    assert compressor_isentropic_efficiency(
        actual_outlet_temperature=_qty(480, "K"), **kwargs
    ) == pytest.approx(150.0 / 180.0)
    # Swapping the two outlet temperatures — the obvious slip — returned 15.0, then 1.5e6.
    with pytest.raises(ValueError, match="hotter than the ideal"):
        compressor_isentropic_efficiency(actual_outlet_temperature=_qty(310, "K"), **kwargs)


def test_a_solar_cell_cannot_deliver_more_than_it_receives():
    from anvilate.analysis.solar_cell import solar_cell_efficiency

    kwargs = {"irradiance": _qty(1000, "W/m**2"), "cell_area": _qty(100, "cm**2")}
    assert solar_cell_efficiency(max_power=_qty(2.0, "W"), **kwargs) == pytest.approx(0.20)
    # 5 W from 1 cm² returned 50.0 — a 5000% cell, as a bare float a caller reads as a
    # fraction. The plausible-looking version, 123%, is the transcription slip that bites.
    with pytest.raises(ValueError, match="incident power"):
        solar_cell_efficiency(
            max_power=_qty(5, "W"), irradiance=_qty(1000, "W/m**2"), cell_area=_qty(1, "cm**2")
        )


def test_the_de_broglie_wavelength_refuses_a_relativistic_electron():
    from anvilate.analysis.quantum import de_broglie_wavelength

    electron = {"mass": _qty(9.1093837015e-31, "kg")}
    # In nanometres, not metres: at 7e-10 m, approx's default abs=1e-12 swamps any rel=
    # and the tolerance does nothing. The suite has a ratchet that catches exactly this.
    assert de_broglie_wavelength(velocity=_qty(1e6, "m/s"), **electron).to(
        "nm"
    ).magnitude == pytest.approx(0.72742, rel=1e-4)
    # A 200 kV electron microscope sits at 0.695c, where h/(m*v) is 1.39x long — and the
    # docstring's own motivating example. At v >= c it still returned a finite wavelength.
    with pytest.raises(ValueError, match="non-relativistic range"):
        de_broglie_wavelength(velocity=_qty(2.08e8, "m/s"), **electron)
    with pytest.raises(ValueError, match="speed of light"):
        de_broglie_wavelength(velocity=_qty(3e8, "m/s"), **electron)


def test_the_transformer_load_fraction_stays_a_fraction():
    from anvilate.analysis.electrical import transformer_maximum_efficiency_load_fraction

    assert transformer_maximum_efficiency_load_fraction(
        core_loss=_qty(500, "W"), rated_copper_loss=_qty(1000, "W")
    ) == pytest.approx(0.70711, rel=1e-4)
    # A core loss above the rated copper loss returned 1.41 — a load past nameplate.
    with pytest.raises(ValueError, match="past\\s+nameplate"):
        transformer_maximum_efficiency_load_fraction(
            core_loss=_qty(2000, "W"), rated_copper_loss=_qty(1000, "W")
        )


def test_the_fiber_mode_count_refuses_below_its_own_cutoff():
    from anvilate.analysis.fiber_optics import fiber_mode_count

    assert fiber_mode_count(v_number=10.0) == pytest.approx(50.0)
    # V**2/2 returned 2.89 at the 2.405 cutoff (where M is 1) and 0.125 below it — a
    # fraction of a mode, for a fiber that carries exactly one.
    for v in (2.405, 0.5):
        with pytest.raises(ValueError, match="cutoff"):
            fiber_mode_count(v_number=v)


# --- the NaN class, second wave: plain-float parameters -----------------------------------
#
# The first wave wired `units.require_finite` into the Quantity-validating helpers. A deep
# audit replayed 21,901 recorded calls with one argument poisoned and found the class alive
# in every parameter that is a *plain float* — resistance factors, m, X/Y, k_t, S_DS, spec
# limits — where the guard is a bare `if x <= 0: raise` that NaN walks straight past. A
# `min()`/`max()` then deletes the poisoned candidate instead of propagating it, so the
# answer comes back complete-looking, smaller, and green.
#
# Every case below was demonstrated returning a *finite, wrong, unconservative* number.


def test_a_non_finite_resistance_factor_cannot_delete_a_limit_state():
    """`min(yielding, rupture)` dropped the rupture check when its factor was NaN, and the
    capacity came back 53% higher — from a function that already refused 0.0."""
    from anvilate.analysis.fastener import aisc_tension_member_design_strength

    good = {
        "gross_area": Quantity.parse("2000 mm**2"),
        "effective_net_area": Quantity.parse("1200 mm**2"),
        "yield_strength": Quantity.parse("345 MPa"),
        "ultimate_strength": Quantity.parse("450 MPa"),
    }
    baseline = aisc_tension_member_design_strength(**good).to("kN").magnitude
    for factor in ("yield_resistance_factor", "rupture_resistance_factor"):
        with pytest.raises(ValueError, match="finite"):
            aisc_tension_member_design_strength(**good, **{factor: math.nan})
    # The rupture state is the one that governs here, so the guard is not cosmetic.
    assert baseline == pytest.approx(405.0, rel=1e-3)


def test_a_non_finite_aspect_ratio_cannot_delete_a_punching_shear_term():
    """The three-way `min()` lost the 0.17(1+2/beta) term and the capacity rose 45.6% — on a
    brittle failure mode."""
    from anvilate.analysis.reinforced_concrete import rc_two_way_shear_strength

    good = {
        "concrete_strength": Quantity.parse("30 MPa"),
        "critical_perimeter": Quantity.parse("1600 mm"),
        "effective_depth": Quantity.parse("200 mm"),
    }
    with pytest.raises(ValueError, match="finite"):
        rc_two_way_shear_strength(**good, column_aspect_ratio=math.nan)
    # A legitimate ratio still selects the governing term.
    assert (
        rc_two_way_shear_strength(**good, column_aspect_ratio=6.0).to("kN").magnitude
        < rc_two_way_shear_strength(**good, column_aspect_ratio=1.0).to("kN").magnitude
    )


def test_a_non_finite_intersection_slenderness_cannot_switch_the_buckling_branch():
    """`slenderness <= intersection` is False against NaN, so the function silently took the
    elastic branch and returned 2.13x the correct stress — above any aluminum yield."""
    from anvilate.analysis.aluminum import aluminum_buckling_stress

    good = {
        "intercept": Quantity.parse("200 MPa"),
        "slope": Quantity.parse("1 MPa"),
        "elastic_modulus": Quantity.parse("70000 MPa"),
        "slenderness": 60.0,
    }
    with pytest.raises(ValueError, match="finite"):
        aluminum_buckling_stress(**good, intersection_slenderness=math.nan)
    inelastic = aluminum_buckling_stress(**good, intersection_slenderness=80.0)
    assert inelastic.to("MPa").magnitude == pytest.approx(140.0)


def test_a_non_finite_bearing_factor_cannot_reduce_the_equivalent_load_to_the_radial_one():
    """`max(fr, X*fr + Y*fa)` dropped the combined term: 1000 N where the answer is 3100 N,
    a 3.1x understated demand."""
    from anvilate.analysis.bearing import bearing_equivalent_static_load

    good = {"radial_load": Quantity.parse("1000 N"), "axial_load": Quantity.parse("5000 N")}
    for factor in ("radial_factor", "axial_factor"):
        other = "axial_factor" if factor == "radial_factor" else "radial_factor"
        with pytest.raises(ValueError, match="finite"):
            bearing_equivalent_static_load(**good, **{factor: math.nan, other: 0.6})
    assert bearing_equivalent_static_load(**good, radial_factor=0.6, axial_factor=0.5).to(
        "N"
    ).magnitude == pytest.approx(3100.0)


def test_a_non_finite_gasket_factor_cannot_delete_the_operating_load():
    """The operating load honestly returns NaN when m is NaN, and `max` deleted it: 138 kN
    where the answer is 352 kN, on the joint the calculation exists to size."""
    from anvilate.analysis.gasket import governing_gasket_bolt_load

    good = {
        "gasket_mean_diameter": Quantity.parse("300 mm"),
        "effective_seating_width": Quantity.parse("10 mm"),
        "seating_stress": Quantity.parse("11 MPa"),
        "pressure": Quantity.parse("2 MPa"),
    }
    with pytest.raises(ValueError, match="finite"):
        governing_gasket_bolt_load(**good, gasket_factor=math.nan)
    assert governing_gasket_bolt_load(**good, gasket_factor=3.0).to("N").magnitude > 0


def test_a_non_finite_seismic_input_cannot_delete_both_diaphragm_bounds():
    """`min(max(proportional, lower), upper)` collapses to the middle term when a bound is
    NaN, so the §12.10.1.1 floor *and* the cap vanished together and the force came back
    37.5% light."""
    from anvilate.analysis.building_loads import seismic_diaphragm_force

    good = {
        "story_forces_above": Quantity.parse("500 kN"),
        "story_weights_above": Quantity.parse("5000 kN"),
        "diaphragm_weight": Quantity.parse("2500 kN"),
    }
    with pytest.raises(ValueError, match="finite"):
        seismic_diaphragm_force(**good, design_spectral_acceleration=math.nan)
    with pytest.raises(ValueError, match="finite"):
        seismic_diaphragm_force(
            **good, design_spectral_acceleration=0.5, importance_factor=math.nan
        )


def test_a_non_finite_tension_coefficient_cannot_delete_net_section_rupture():
    """`min(fty, ftu/k_t)` dropped rupture and returned 240 MPa where the answer is 208 — a
    15.4% overstatement. k_t = 0.5 was already refused; the guard caught the wrong kind of
    bad value."""
    from anvilate.analysis.aluminum import aluminum_tension_stress

    good = {
        "yield_strength": Quantity.parse("240 MPa"),
        "ultimate_strength": Quantity.parse("260 MPa"),
    }
    with pytest.raises(ValueError, match="finite"):
        aluminum_tension_stress(**good, tension_coefficient=math.nan)
    assert aluminum_tension_stress(**good, tension_coefficient=1.25).to(
        "MPa"
    ).magnitude == pytest.approx(208.0)


def test_a_non_finite_specification_limit_cannot_produce_a_capable_process():
    """`min(upper, lower)` deleted the missing arm and returned 1.3333 — the industry
    "capable process" number — computed from a limit nobody supplied."""
    from anvilate.analysis.process_capability import (
        process_capability_index,
        process_capability_ratio,
    )

    with pytest.raises(ValueError, match="finite"):
        process_capability_ratio(
            upper_spec_limit=10.0, lower_spec_limit=math.nan, process_mean=5.0, process_std_dev=1.0
        )
    with pytest.raises(ValueError, match="finite"):
        process_capability_index(
            upper_spec_limit=10.0, lower_spec_limit=math.nan, process_std_dev=1.0
        )
    assert process_capability_ratio(
        upper_spec_limit=10.0, lower_spec_limit=0.0, process_mean=5.0, process_std_dev=1.0
    ) == pytest.approx(5.0 / 3.0)


def test_a_non_finite_involute_value_cannot_return_the_brackets_own_bound():
    """The residual check that exists to stop the solver returning garbage was itself
    NaN-blind — `max(1.0, nan)` is 1.0 and `nan > 1e-9` is False — so it returned 89.99999
    degrees, literally the bracket's upper bound, as a pressure angle."""
    from anvilate.analysis.gear import involute_angle

    with pytest.raises(ValueError, match="finite"):
        involute_angle(involute_value=math.nan)
    assert involute_angle(involute_value=0.014904) == pytest.approx(20.0, rel=1e-3)


@pytest.mark.parametrize(
    "function_name",
    [
        "aisc_minor_axis_flexural_strength",
        "aisc_rectangular_hss_flexural_strength",
        "aisc_round_hss_flexural_strength",
    ],
)
def test_a_non_finite_elastic_modulus_cannot_delete_the_flexural_cap(function_name):
    """These three checked `elastic_section_modulus` with a raw `has_dimension` instead of
    the module's own finite-checking `_require`, so `min(fy*Z, 1.6*fy*S)` deleted the §F6.1
    cap and all three returned the *exact same number* as the all-valid call. S = 0 was
    refused and S = NaN was not — and a NaN plastic modulus propagated correctly, which is
    the asymmetry that gives it away."""
    import anvilate.analysis.beam as beam

    function = getattr(beam, function_name)
    shared = {
        "yield_strength": Quantity.parse("345 MPa"),
        "elastic_modulus": Quantity.parse("200 GPa"),
        "plastic_section_modulus": Quantity.parse("900000 mm**3"),
    }
    geometry = {
        "aisc_minor_axis_flexural_strength": {
            "flange_width": Quantity.parse("200 mm"),
            "flange_thickness": Quantity.parse("12 mm"),
        },
        "aisc_rectangular_hss_flexural_strength": {
            "flange_flat_width": Quantity.parse("180 mm"),
            "web_flat_height": Quantity.parse("280 mm"),
            "wall_thickness": Quantity.parse("10 mm"),
        },
        "aisc_round_hss_flexural_strength": {
            "diameter": Quantity.parse("250 mm"),
            "thickness": Quantity.parse("10 mm"),
        },
    }[function_name]

    with pytest.raises(ValueError, match="finite"):
        function(
            **shared,
            **geometry,
            elastic_section_modulus=Quantity(magnitude=math.nan, unit="mm**3"),
        )
    # And the valid call still works, so the guard is a guard and not a wall.
    assert (
        function(**shared, **geometry, elastic_section_modulus=Quantity.parse("750000 mm**3"))
        .to("kN*m")
        .magnitude
        > 0
    )


def test_the_over_margin_detail_never_reports_an_excess_of_zero():
    """The central rendering of the library, contradicting itself in three places at once.

    `safety factor 2.50 exceeds target band 1.50–2.50 by 0.00 — over-engineered` was what a
    reviewer read for any factor a hair above the band, and OVER_MARGIN is the status the
    repair loop acts on. The precision widens until the excess is visible.
    """
    import re

    from anvilate.scorecard import CheckStatus, ScorecardEntry

    for computed in (2.5005, 2.501, 2.51, 2.6, 4.0):
        entry = ScorecardEntry.from_safety_factor(
            "band", computed=computed, required=1.5, upper=2.5
        )
        assert entry.status is CheckStatus.OVER_MARGIN, computed
        shown = re.search(
            r"factor ([\d.]+) exceeds target band ([\d.]+)–([\d.]+) by ([\d.]+)", entry.detail
        )
        assert shown is not None, entry.detail
        factor, _lower, upper, excess = (float(value) for value in shown.groups())
        assert excess > 0.0, f"{entry.detail!r} claims an excess of zero"
        assert factor > upper, f"{entry.detail!r} shows a factor that does not exceed the band"
        # The three numbers on the page agree with each other, not merely with the truth.
        assert factor - upper == pytest.approx(excess, abs=10 ** -len(shown.group(4).split(".")[1]))


def test_a_refusal_never_prints_two_numbers_that_render_the_same():
    """The family the over-margin detail belongs to: a message asserting an inequality
    between two figures it prints at fixed precision.

    At one decimal place the round-HSS guard read `D/t = 200.0 exceeds the §F8
    applicability limit 0.45E/F_y = 200.0` — a refusal whose own numbers say there is
    nothing to refuse — for any yield strength putting the limit on a rounding boundary.
    The masonry cap read `overstates the column by 1.00x` in the sentence refusing it.
    """
    import re

    from anvilate.analysis.beam import aisc_round_hss_flexural_strength
    from anvilate.analysis.masonry import masonry_column_axial_capacity
    from anvilate.units import Quantity

    # 0.45E/F_y lands exactly on 200.0 here, so a D/t a hair above it is the collision.
    limit = 0.45 * 200000.0 / 450.0
    with pytest.raises(ValueError) as refusal:
        aisc_round_hss_flexural_strength(
            diameter=Quantity(magnitude=100.0, unit="mm"),
            thickness=Quantity(magnitude=100.0 / (limit * 1.0001), unit="mm"),
            yield_strength=Quantity.parse("450 MPa"),
            elastic_modulus=Quantity.parse("200 GPa"),
            plastic_section_modulus=Quantity.parse("1.2e5 mm**3"),
            elastic_section_modulus=Quantity.parse("1e5 mm**3"),
        )
    shown = re.search(r"D/t = ([\d.]+) exceeds .*= ([\d.]+)", str(refusal.value))
    assert shown is not None, refusal.value
    assert float(shown.group(1)) > float(shown.group(2)), str(refusal.value)
    assert shown.group(1) != shown.group(2)

    with pytest.raises(ValueError) as capped:
        masonry_column_axial_capacity(
            masonry_strength=Quantity.parse("10 MPa"),
            net_area=Quantity.parse("50000 mm**2"),
            steel_area=Quantity.parse("600 mm**2"),
            steel_allowable_stress=Quantity.parse("165.1 MPa"),
            slenderness_ratio=20.0,
        )
    overstatement = re.search(r"overstates the column by ([\d.]+)x", str(capped.value))
    assert overstatement is not None, capped.value
    assert float(overstatement.group(1)) > 1.0, str(capped.value)
