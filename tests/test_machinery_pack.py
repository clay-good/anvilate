"""Tests for the machinery pack: TransmissionShaft and its three-check Shigley screen."""

from __future__ import annotations

import pytest

from anvilate.analysis import (
    agma_module_for_bending_stress,
    gear_pitch_diameter,
    gear_tangential_load,
    shaft_diameter_de_goodman,
)
from anvilate.packs.machinery import (
    SpurGearMesh,
    TransmissionShaft,
    screen_gear_mesh,
    screen_shaft,
)
from anvilate.scorecard import CheckStatus, Direction
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _shaft(**overrides) -> TransmissionShaft:
    fields = {
        "diameter": _q("40 mm"),
        "bending_moment": _q("250 N*m"),
        "torque": _q("400 N*m"),
        "yield_strength": _q("370 MPa"),
        "length": _q("600 mm"),
        "shear_modulus": _q("79.3 GPa"),
        "allowable_twist": _q("0.5 degree"),
        "endurance_limit": _q("200 MPa"),
        "ultimate_strength": _q("690 MPa"),
    }
    fields.update(overrides)
    return TransmissionShaft(**fields)


def _named(card):
    return {entry.name: entry for entry in card.entries}


def test_the_three_checks_disagree_and_twist_governs_this_shaft():
    """The reason the screen is one card: static, fatigue and twist give three answers.

    A 40 mm shaft at these loads is comfortable on yield (5.4) and on fatigue (3.6) and
    fails on windup (0.72). Sized on the static check alone it would have shipped.
    """
    card = screen_shaft(_shaft())
    assert card.status is CheckStatus.FAIL
    names = _named(card)
    assert set(names) == {
        "combined bending and torsion",
        "torsional twist",
        "rotating-shaft fatigue",
    }
    assert names["combined bending and torsion"].status is CheckStatus.PASS
    assert names["rotating-shaft fatigue"].status is CheckStatus.PASS
    assert names["torsional twist"].status is CheckStatus.FAIL
    assert all(e.reference is not None and "Shigley" in e.reference for e in card.entries)

    # Absolute pins, so a moved constant is caught by more than a verdict. σ' =
    # 32·√(250000² + 0.75·400000²)/(π·40³) = 67.99102 MPa against S_y = 370; θ =
    # 32·400000·600/(π·79300·40⁴) rad = 0.6899551°; the fatigue factor is (40/d₁)³.
    assert names["combined bending and torsion"].safety_factor == pytest.approx(
        5.441895001346463, rel=1e-9
    )
    assert names["torsional twist"].safety_factor == pytest.approx(0.7246848416725796, rel=1e-9)
    assert names["rotating-shaft fatigue"].safety_factor == pytest.approx(
        3.586203507897734, rel=1e-9
    )


def test_a_comfortable_shaft_passes_every_check():
    card = screen_shaft(_shaft(diameter=_q("60 mm")))
    assert card.status is CheckStatus.PASS
    assert card.passed


@pytest.mark.parametrize(
    ("check", "shaft"),
    [
        # Each shaft is built to fail ONE of the three, so every lever is reached: a short
        # stubby shaft fails on stress, a long slender one on windup, and a soft-surfaced
        # one on fatigue while yielding is still comfortable.
        ("combined bending and torsion", _shaft(diameter=_q("22 mm"), length=_q("60 mm"))),
        ("torsional twist", _shaft()),
        (
            "rotating-shaft fatigue",
            _shaft(diameter=_q("32 mm"), length=_q("60 mm"), endurance_limit=_q("90 MPa")),
        ),
    ],
)
def test_screen_shaft_names_the_diameter_that_clears_each_failing_check(check, shaft):
    """The lever's value is re-screened, not just asserted — the base plate's lesson.

    A solved hint that lands exactly on the boundary comes back FAIL when the screen
    recomputes the safety factor down a different arithmetic path, so the only assertion
    worth making about a corrective value is that the part rebuilt at it passes.
    """
    entry = _named(screen_shaft(shaft))[check]
    assert entry.status is CheckStatus.FAIL
    hint = entry.repair_hint
    assert hint is not None
    assert hint.parameter == "diameter"
    assert hint.direction is Direction.INCREASE
    assert hint.unit == "mm"
    assert hint.corrective_value is not None

    repaired = _named(
        screen_shaft(
            shaft.model_copy(
                update={"diameter": Quantity(magnitude=hint.corrective_value, unit="mm")}
            )
        )
    )[check]
    assert repaired.status is CheckStatus.PASS
    # And it is the LEAST such diameter: a hair under it fails. Without this the hint could
    # name any large number and still pass the line above.
    under = _named(
        screen_shaft(
            shaft.model_copy(
                update={"diameter": Quantity(magnitude=hint.corrective_value * 0.999, unit="mm")}
            )
        )
    )[check]
    assert under.status is CheckStatus.FAIL


def test_the_three_levers_do_not_agree_on_one_diameter():
    """One knob, three answers — which is the whole reason a shaft is screened as a card."""
    shaft = _shaft(diameter=_q("20 mm"), length=_q("900 mm"), endurance_limit=_q("110 MPa"))
    values = {
        entry.name: entry.repair_hint.corrective_value
        for entry in screen_shaft(shaft).entries
        if entry.repair_hint is not None
    }
    assert len(values) == 3, values
    assert len({round(v, 6) for v in values.values()}) == 3, values
    # The largest is the shaft. Stated as an ordering rather than three numbers, because
    # the point is that the governing check is not knowable from the loads alone.
    assert max(values, key=values.__getitem__) == "torsional twist"


def test_the_fatigue_factor_is_the_cube_of_the_diameter_ratio():
    """`n_f = (d/d₁)³` is an identity of the DE-Goodman form, so it is checked against it.

    The criterion ships as an inverse only. Turning it into a safety factor relies on the
    whole bracket going as 1/d³, and that claim is worth holding against the inverse itself
    rather than against a number this test copied from the screen.
    """
    shaft = _shaft()
    entry = _named(screen_shaft(shaft))["rotating-shaft fatigue"]
    factor = entry.safety_factor
    assert factor is not None
    solved = shaft_diameter_de_goodman(
        alternating_bending_moment=shaft.bending_moment,
        mean_torque=shaft.torque,
        endurance_limit=shaft.endurance_limit,
        ultimate_strength=shaft.ultimate_strength,
        required_safety_factor=factor,
    )
    assert solved.to("mm").magnitude == pytest.approx(40.0, rel=1e-9)


@pytest.mark.parametrize(
    ("check", "dropped", "missing"),
    [
        ("torsional twist", "length", "length"),
        ("torsional twist", "shear_modulus", "shear_modulus"),
        ("torsional twist", "allowable_twist", "allowable_twist"),
        ("rotating-shaft fatigue", "endurance_limit", "endurance_limit"),
        ("rotating-shaft fatigue", "ultimate_strength", "ultimate_strength"),
    ],
)
def test_a_check_whose_inputs_are_absent_says_so_and_names_them(check, dropped, missing):
    """An undeclared input is NOT_EVALUATED naming the field, never a quiet pass."""
    entry = _named(screen_shaft(_shaft(**{dropped: None})))[check]
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert missing in entry.detail
    assert entry.safety_factor is None


def test_a_shaft_carrying_nothing_is_not_evaluated_rather_than_infinitely_strong():
    card = screen_shaft(_shaft(bending_moment=_q("0 N*m"), torque=_q("0 N*m")))
    for entry in card.entries:
        assert entry.status is CheckStatus.NOT_EVALUATED, entry.name


def test_a_negative_diameter_is_refused_at_the_door():
    with pytest.raises(ValueError, match="must not be negative"):
        _shaft(diameter=_q("-40 mm"))


def test_a_misspelled_field_is_refused_rather_than_ignored():
    """`extra="forbid"`: a shaft declaring `allowable_twist_deg` would otherwise be screened
    with no twist check at all, and the card would still say what it said."""
    with pytest.raises(ValueError):
        _shaft(allowable_twist_deg=0.5)


def _mesh(**overrides) -> SpurGearMesh:
    fields = {
        "pinion_teeth": 18,
        "gear_teeth": 54,
        "module": _q("2 mm"),
        "face_width": _q("40 mm"),
        "pressure_angle": 20.0,
        "pinion_torque": _q("180 N*m"),
        "bending_geometry_factor": 0.34,
        "contact_geometry_factor": 0.115,
        "allowable_bending_stress": _q("250 MPa"),
        "allowable_contact_stress": _q("1100 MPa"),
        "pinion_modulus": _q("207 GPa"),
        "gear_modulus": _q("207 GPa"),
        "overload_factor": 1.25,
        "dynamic_factor": 1.3,
        "load_distribution_factor": 1.2,
    }
    fields.update(overrides)
    return SpurGearMesh(**fields)


def test_the_gear_mesh_card_pins_all_four_checks():
    """Absolute pins, each derived here from the published form rather than read back.

    W_t = 2·T/(m·N₁) = 10,000 N; σ = W_t·1.95/(b·m·Y_J); C_p = √(1/(π·2·(1−0.3²)/E)) =
    190.27 √MPa and σ_c = C_p·√(W_t·1.95/(d₁·b·I)); the contact ratio is the base-circle
    form ‹√(r_a1²−r_b1²) + √(r_a2²−r_b2²) − C·sinφ›/(π·m·cosφ).
    """
    names = _named(screen_gear_mesh(_mesh()))
    assert set(names) == {"tooth-root bending", "surface pitting", "contact ratio", "undercut"}
    assert names["tooth-root bending"].safety_factor == pytest.approx(
        0.34871794871794876, rel=1e-12
    )
    assert names["surface pitting"].safety_factor == pytest.approx(0.5327592554581533, rel=1e-12)
    assert names["contact ratio"].safety_factor == pytest.approx(1.3739625044981367, rel=1e-12)
    # 18 teeth is exactly the 20° undercut limit, so the check sits on its own boundary.
    assert names["undercut"].safety_factor == pytest.approx(1.0, rel=1e-12)
    assert names["undercut"].status is CheckStatus.PASS


@pytest.mark.parametrize(
    ("check", "mesh"),
    [
        ("tooth-root bending", _mesh()),
        ("surface pitting", _mesh()),
        ("contact ratio", _mesh(minimum_contact_ratio=1.9)),
        ("undercut", _mesh(pinion_teeth=12)),
    ],
)
def test_screen_gear_mesh_names_a_parameter_that_clears_each_failing_check(check, mesh):
    entry = _named(screen_gear_mesh(mesh))[check]
    assert entry.status is CheckStatus.FAIL
    hint = entry.repair_hint
    assert hint is not None
    if hint.corrective_value is None:
        # A directional hint claims a sign, and the sign is checked by moving that way.
        assert hint.parameter == "pressure_angle"
        assert hint.direction is Direction.DECREASE
        moved = _named(screen_gear_mesh(mesh.model_copy(update={"pressure_angle": 14.5})))[check]
        assert moved.safety_factor > entry.safety_factor
        return
    field = {"module": Quantity(magnitude=hint.corrective_value, unit="mm")}
    if hint.parameter == "pinion_teeth":
        field = {"pinion_teeth": int(hint.corrective_value)}
    repaired = _named(screen_gear_mesh(mesh.model_copy(update=field)))[check]
    assert repaired.status is CheckStatus.PASS
    # And it is the LEAST such value: one step under it still fails.
    if hint.parameter == "pinion_teeth":
        under = {"pinion_teeth": int(hint.corrective_value) - 1}
    else:
        under = {"module": Quantity(magnitude=hint.corrective_value * 0.999, unit="mm")}
    assert _named(screen_gear_mesh(mesh.model_copy(update=under)))[check].status is CheckStatus.FAIL


def test_the_shipped_module_inverse_is_not_the_bending_hint():
    """The reason the hint is solved here rather than delegated.

    `agma_module_for_bending_stress` inverts at a FIXED tangential load. This screen's given
    is the pinion torque, so W_t = 2·T/(m·N₁) falls as the module grows and the module
    enters the stress twice — σ ∝ 1/m², not 1/m. Delegating would name a module a long way
    past the margin, and a hint that is not the least value is a hint a caller cannot use.
    """
    mesh = _mesh()
    hint = _named(screen_gear_mesh(mesh))["tooth-root bending"].repair_hint
    assert hint is not None and hint.corrective_value is not None
    delegated = (
        agma_module_for_bending_stress(
            tangential_load=gear_tangential_load(
                torque=mesh.pinion_torque,
                pitch_diameter=gear_pitch_diameter(module=mesh.module, teeth=mesh.pinion_teeth),
            ),
            face_width=mesh.face_width,
            geometry_factor=mesh.bending_geometry_factor,
            allowable_stress=mesh.allowable_bending_stress,
            overload_factor=mesh.overload_factor,
            dynamic_factor=mesh.dynamic_factor,
            load_distribution_factor=mesh.load_distribution_factor,
        )
        .to("mm")
        .magnitude
    )
    assert delegated > hint.corrective_value * 1.5, (delegated, hint.corrective_value)


def test_the_module_cannot_move_the_contact_ratio_at_all():
    """Which is why its lever is the pressure angle, and why a bigger gear is not the fix.

    Every length in the contact-ratio expression is a multiple of the module, so it divides
    out. A reader who has just been told to increase the module for two of the four checks
    needs this said explicitly.
    """
    ratios = [
        _named(screen_gear_mesh(_mesh(module=_q(f"{size} mm"))))["contact ratio"].safety_factor
        for size in (1.5, 2.0, 6.0, 12.0)
    ]
    # Float noise in the last place only: an eight-fold change in size moves nothing a
    # reader could see, which is the claim.
    assert all(r == pytest.approx(ratios[0], rel=1e-12) for r in ratios), ratios


def test_the_contact_ratio_falls_with_pressure_angle_over_the_declared_range():
    """The sweep behind the directional hint, because a direction is a claim about a domain.

    Every practical mesh, every half-degree from 14.5° to 30°: the contact ratio is strictly
    decreasing. A directional hint that was right only near one point would be a hint that
    sends a caller the wrong way somewhere else.
    """
    for pinion in (12, 18, 25, 40, 60):
        for wheel in (pinion, pinion + 10, 100):
            previous = None
            for step in range(32):
                angle = 14.5 + 0.5 * step
                mesh = _mesh(pinion_teeth=pinion, gear_teeth=wheel, pressure_angle=angle)
                ratio = _named(screen_gear_mesh(mesh))["contact ratio"].safety_factor
                if previous is not None:
                    assert ratio < previous, (pinion, wheel, angle)
                previous = ratio


def test_the_four_gear_checks_are_moved_by_three_different_parameters():
    mesh = _mesh(module=_q("1.5 mm"), pinion_teeth=12, minimum_contact_ratio=1.9)
    card = screen_gear_mesh(mesh)
    assert all(e.status is CheckStatus.FAIL for e in card.entries)
    assert {e.repair_hint.parameter for e in card.entries if e.repair_hint is not None} == {
        "module",
        "pressure_angle",
        "pinion_teeth",
    }


def test_a_geometric_threshold_takes_no_design_margin_on_top():
    """The contact ratio and the undercut limit are judged against their own thresholds.

    Screening them at the stress checks' 1.2 would be demanding a contact ratio of 1.44 and
    22 teeth where the standard asks for 1.2 and 18 — a different threshold, arrived at by
    accident.
    """
    mesh = _mesh()
    strict = screen_gear_mesh(mesh, required_safety_factor=3.0)
    relaxed = screen_gear_mesh(mesh, required_safety_factor=1.0)
    for name in ("contact ratio", "undercut"):
        assert _named(strict)[name].status is _named(relaxed)[name].status
        assert _named(strict)[name].safety_factor == _named(relaxed)[name].safety_factor
