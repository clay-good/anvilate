"""Typed MBD callouts: identity, resolution, the diff, and the checks they feed."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from anvilate.callouts import (
    MARIN_SURFACE_CONSTANTS_MPA,
    THREAD_PITCH_DIAMETER_PLATING_MULTIPLIER,
    TYPICAL_ROUGHNESS_UM,
    CalloutSet,
    Coating,
    FreeTextNote,
    HeatTreatment,
    ProcessNote,
    ProductionMethod,
    RoughnessParameter,
    SurfaceFinish,
    callout_diff,
    callout_scorecard,
    heat_treated_material_id,
    marin_surface_factor,
    plated_inner_dimension,
    plated_outer_dimension,
    plated_thread_pitch_diameter_shift,
)
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity

_STEELS = ("AISI-1018-CD", "AISI-4140", "AA-6061-T6")


def _q(magnitude: float, unit: str) -> Quantity:
    return Quantity(magnitude=magnitude, unit=unit)


def _finish(**overrides) -> SurfaceFinish:
    fields = {
        "scope": "shaft_journal",
        "roughness": _q(0.8, "um"),
        "method": ProductionMethod.GROUND,
    }
    fields.update(overrides)
    return SurfaceFinish(**fields)


def _coating(**overrides) -> Coating:
    fields = {
        "scope": "shaft_journal",
        "specification": "ASTM B633 SC1 Type III",
        "minimum_thickness": _q(5, "um"),
        "maximum_thickness": _q(13, "um"),
    }
    fields.update(overrides)
    return Coating(**fields)


# --- persistent characteristic identity ----------------------------------------------


def test_identity_is_the_characteristic_not_its_value():
    # The whole point: revising a finish keeps the identifier, so a diff can call it a
    # change rather than a deletion plus an unrelated addition.
    tight = _finish(roughness=_q(0.4, "um"))
    assert _finish().characteristic_id == tight.characteristic_id
    assert _finish().value_signature() != tight.value_signature()


def test_identity_is_scoped_and_kinded():
    assert _finish().characteristic_id != _finish(scope="bearing_bore").characteristic_id
    assert _finish().characteristic_id != _coating().characteristic_id
    # A whole-part callout has its own identity, distinct from any tag's.
    assert _finish(scope=None).characteristic_id != _finish().characteristic_id


def test_identity_survives_regeneration_because_it_is_derived_not_assigned():
    # No counter, no database: two independently constructed callouts for the same
    # characteristic agree, which is what makes the identifier stable across a rebuild.
    assert _finish().characteristic_id == _finish().characteristic_id
    assert len(_finish().characteristic_id) == 16


def test_a_note_category_is_part_of_the_characteristic():
    deburr = ProcessNote(scope="bore", category="deburr")
    peen = ProcessNote(scope="bore", category="shot_peen")
    assert deburr.characteristic_id != peen.characteristic_id


def test_two_free_text_notes_at_one_scope_are_two_characteristics():
    first = FreeTextNote(scope="bore", text="break all sharp edges", sequence=1)
    second = FreeTextNote(scope="bore", text="do not paint", sequence=2)
    assert first.characteristic_id != second.characteristic_id
    CalloutSet(callouts=(first, second))  # and the set accepts both


# --- the set: resolution and the one-value rule ---------------------------------------


def test_a_scope_that_no_tag_defines_is_refused_by_name():
    callouts = CalloutSet(callouts=(_finish(), _coating(scope="ghost_face")))
    with pytest.raises(ValueError, match="ghost_face"):
        callouts.resolved_against({"shaft_journal", "bearing_bore"})
    # And the same set resolves once the tag exists.
    callouts.resolved_against({"shaft_journal", "ghost_face"})


def test_a_whole_part_callout_resolves_against_any_tag_graph():
    CalloutSet(callouts=(_finish(scope=None),)).resolved_against(set())


def test_one_characteristic_carries_one_value():
    with pytest.raises(ValidationError, match="contradiction, not a refinement"):
        CalloutSet(callouts=(_finish(), _finish(roughness=_q(3.2, "um"))))


def test_free_text_is_stored_distinguished_and_unconsumable():
    note = FreeTextNote(scope="bore", text="finish per shop practice")
    callouts = CalloutSet(callouts=(_finish(), note))
    assert note in callouts.callouts
    assert note not in callouts.consumable()
    # And it produces no scorecard entry, because an entry would imply a check read it.
    card = callout_scorecard(callouts, ultimate_strength=_q(800, "MPa"))
    assert [e.name for e in card.entries] == ["surface finish at shaft_journal"]


def test_a_structured_note_needs_a_category_and_free_text_needs_text():
    with pytest.raises(ValidationError, match="must name its category"):
        ProcessNote(category="  ")
    with pytest.raises(ValidationError, match="is not a note"):
        FreeTextNote(text="   ")


def test_lookups_are_scoped():
    callouts = CalloutSet(callouts=(_finish(), _coating(), _finish(scope="bearing_bore")))
    assert callouts.finish_for("bearing_bore").scope == "bearing_bore"
    assert callouts.coating_for("bearing_bore") is None
    assert callouts.heat_treatment_for("shaft_journal") is None
    assert len(callouts.for_tag("shaft_journal")) == 2


# --- the diff -------------------------------------------------------------------------


def test_a_revised_value_is_a_change_not_a_delete_plus_an_add():
    before = CalloutSet(callouts=(_finish(), _coating()))
    after = CalloutSet(callouts=(_finish(roughness=_q(0.4, "um")), _coating()))
    diff = callout_diff(before, after)
    assert diff.added == () and diff.removed == ()
    assert diff.unchanged_identity is True
    (change,) = diff.changed
    assert change.characteristic_id == _finish().characteristic_id
    assert "0.8" in change.previous and "0.4" in change.current


def test_a_callout_on_a_new_face_mints_a_new_characteristic():
    before = CalloutSet(callouts=(_finish(),))
    after = CalloutSet(callouts=(_finish(), _finish(scope="bearing_bore")))
    diff = callout_diff(before, after)
    assert diff.added == (_finish(scope="bearing_bore").characteristic_id,)
    assert diff.removed == () and diff.changed == ()
    assert diff.unchanged_identity is False


def test_a_removed_callout_is_reported_as_removed():
    diff = callout_diff(
        CalloutSet(callouts=(_finish(), _coating())), CalloutSet(callouts=(_finish(),))
    )
    assert diff.removed == (_coating().characteristic_id,)
    assert "1 removed" in str(diff)


# --- the Marin surface factor ----------------------------------------------------------


def test_the_marin_constants_agree_with_their_own_kpsi_twins():
    """The published table gives both constant sets, and they are not independent.

    k_a is a pure number, so a_kpsi = a_MPa·(MPa per kpsi)^b must hold at every S_u. It
    does, for all four rows, to the table's own rounding — which is the cheapest available
    check that these were transcribed correctly, and it needs no external source.
    """
    mpa_per_kpsi = 6.894757
    published_kpsi = {
        "ground": 1.34,
        "machined": 2.70,
        "hot_rolled": 14.4,
        "as_forged": 39.9,
    }
    for method, (a_mpa, b) in MARIN_SURFACE_CONSTANTS_MPA.items():
        derived = a_mpa * mpa_per_kpsi**b
        assert derived == pytest.approx(published_kpsi[method], rel=3e-3), method


def test_a_polished_surface_takes_the_specimen_factor_exactly():
    polished = _finish(method=ProductionMethod.POLISHED, roughness=_q(0.1, "um"))
    assert marin_surface_factor(polished, ultimate_strength=_q(800, "MPa")) == 1.0


def test_the_surface_factor_falls_with_a_rougher_process_and_a_stronger_steel():
    su = _q(800, "MPa")
    factors = [
        marin_surface_factor(_finish(method=m, roughness=_q(r, "um")), ultimate_strength=su)
        for m, r in (
            (ProductionMethod.GROUND, 0.8),
            (ProductionMethod.MACHINED, 3.2),
            (ProductionMethod.HOT_ROLLED, 12.5),
            (ProductionMethod.AS_FORGED, 25.0),
        )
    ]
    assert factors == sorted(factors, reverse=True)
    assert factors[0] == pytest.approx(0.8951, rel=1e-3)  # ground, 800 MPa
    assert factors[3] == pytest.approx(0.3516, rel=1e-3)  # as-forged, 800 MPa
    # A stronger steel earns a smaller factor from the same process: the surface defects
    # matter more, not less, as the material gets stronger.
    machined = _finish(method=ProductionMethod.MACHINED, roughness=_q(3.2, "um"))
    assert marin_surface_factor(machined, ultimate_strength=_q(1500, "MPa")) < marin_surface_factor(
        machined, ultimate_strength=_q(400, "MPa")
    )


def test_the_surface_factor_is_capped_at_the_polished_specimen():
    # The ground fit crosses 1.0 on a low-strength steel, and no real surface improves on
    # the polished rotating-beam specimen.
    weak = marin_surface_factor(_finish(), ultimate_strength=_q(100, "MPa"))
    assert weak == 1.0


def test_the_surface_factor_needs_a_real_stress():
    with pytest.raises(ValueError, match="\\[pressure\\]"):
        marin_surface_factor(_finish(), ultimate_strength=_q(800, "mm"))
    with pytest.raises(ValueError, match="positive"):
        marin_surface_factor(_finish(), ultimate_strength=_q(-800, "MPa"))


# --- plating and dimensions --------------------------------------------------------------


def test_a_coating_grows_an_outside_dimension_by_twice_its_thickness():
    low, high = plated_outer_dimension(_q(25, "mm"), _coating())
    assert low.to("mm").magnitude == pytest.approx(25.010)
    assert high.to("mm").magnitude == pytest.approx(25.026)


def test_a_coating_shrinks_a_bore_by_twice_its_thickness():
    low, high = plated_inner_dimension(_q(25, "mm"), _coating())
    assert low.to("mm").magnitude == pytest.approx(24.990)
    assert high.to("mm").magnitude == pytest.approx(24.974)


def test_the_thread_pitch_diameter_moves_four_times_the_plating_not_twice():
    """The classic plated-thread interference, and it is derivable rather than folklore.

    The coating is deposited normal to a flank inclined at 30° to the thread axis, so a
    radial thickness t displaces the flank by t/sin(30°) = 2t, and the pitch diameter spans
    two flanks. The multiplier is derived in the module; this asserts the derivation.
    """
    assert THREAD_PITCH_DIAMETER_PLATING_MULTIPLIER == pytest.approx(4.0)
    assert THREAD_PITCH_DIAMETER_PLATING_MULTIPLIER == pytest.approx(
        2.0 / math.sin(math.radians(30.0))
    )
    low, high = plated_thread_pitch_diameter_shift(_coating())
    assert low.to("um").magnitude == pytest.approx(20.0)
    assert high.to("um").magnitude == pytest.approx(52.0)
    # And it is exactly twice what the plain outside-diameter rule would give.
    od_low, _ = plated_outer_dimension(_q(10, "mm"), _coating())
    assert low.to("um").magnitude == pytest.approx(2 * (od_low.to("mm").magnitude - 10.0) * 1000.0)


def test_a_coating_that_closes_the_feature_is_refused():
    thick = _coating(minimum_thickness=_q(1, "mm"), maximum_thickness=_q(2, "mm"))
    with pytest.raises(ValueError, match="closes a"):
        plated_inner_dimension(_q(3, "mm"), thick)


def test_a_backwards_thickness_range_is_refused():
    with pytest.raises(ValidationError, match="runs backwards"):
        _coating(minimum_thickness=_q(13, "um"), maximum_thickness=_q(5, "um"))


def test_a_coating_must_name_its_specification():
    with pytest.raises(ValidationError, match="must name its specification"):
        _coating(specification="  ")


# --- heat treatment and material resolution ------------------------------------------------


def test_a_declared_condition_resolves_to_the_record_that_carries_it():
    treatment = HeatTreatment(specification="AMS 2770", condition="T6")
    assert heat_treated_material_id("AA-6061", treatment, known_materials=_STEELS) == "AA-6061-T6"


def test_a_material_already_in_the_declared_condition_resolves_to_itself():
    treatment = HeatTreatment(specification="cold drawn per ASTM A108", condition="CD")
    assert (
        heat_treated_material_id("AISI-1018-CD", treatment, known_materials=_STEELS)
        == "AISI-1018-CD"
    )


def test_a_condition_no_record_backs_resolves_to_nothing():
    treatment = HeatTreatment(specification="AMS 2759/1", condition="QT", hardness="38-42 HRC")
    assert heat_treated_material_id("AISI-4140", treatment, known_materials=_STEELS) is None


def test_a_heat_treatment_must_name_the_condition_it_produces():
    with pytest.raises(ValidationError, match="must name the condition"):
        HeatTreatment(specification="AMS 2759/1", condition="  ")


# --- consumption and contradiction ------------------------------------------------------------


def test_a_consumed_finish_states_the_value_and_the_effect():
    card = callout_scorecard(CalloutSet(callouts=(_finish(),)), ultimate_strength=_q(800, "MPa"))
    (entry,) = card.entries
    assert entry.status is CheckStatus.PASS
    assert "ground, Ra 0.8 µm" in entry.detail
    assert "k_a = 0.895" in entry.detail
    assert _finish().characteristic_id in entry.detail  # the characteristic, named


def test_a_finish_with_no_strength_to_derive_from_is_not_evaluated():
    card = callout_scorecard(CalloutSet(callouts=(_finish(),)))
    (entry,) = card.entries
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "no ultimate strength" in entry.detail


def test_a_roughness_the_process_cannot_attain_is_a_contradiction_not_an_average():
    impossible = _finish(method=ProductionMethod.AS_FORGED, roughness=_q(0.4, "um"))
    card = callout_scorecard(CalloutSet(callouts=(impossible,)), ultimate_strength=_q(800, "MPa"))
    (entry,) = card.entries
    assert entry.status is CheckStatus.FAIL
    assert "finer than as forged typically attains" in entry.detail
    assert card.status is CheckStatus.FAIL


def test_a_roughness_inside_the_bands_is_never_flagged():
    for method, (low, high) in TYPICAL_ROUGHNESS_UM.items():
        for value in (low, (low + high) / 2, high):
            finish = _finish(method=ProductionMethod(method), roughness=_q(value, "um"))
            card = callout_scorecard(
                CalloutSet(callouts=(finish,)), ultimate_strength=_q(800, "MPa")
            )
            assert card.status is not CheckStatus.FAIL, (method, value)


def test_a_heat_treatment_with_no_record_reports_not_evaluated_naming_the_condition():
    treatment = HeatTreatment(specification="AMS 2759/1", condition="QT", hardness="38-42 HRC")
    card = callout_scorecard(
        CalloutSet(callouts=(treatment,)),
        base_material="AISI-4140",
        known_materials=_STEELS,
    )
    (entry,) = card.entries
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "'QT'" in entry.detail and "AISI-4140" in entry.detail


def test_a_heat_treatment_that_resolves_names_the_record_it_resolved_to():
    treatment = HeatTreatment(specification="AMS 2770", condition="T6")
    card = callout_scorecard(
        CalloutSet(callouts=(treatment,)), base_material="AA-6061", known_materials=_STEELS
    )
    (entry,) = card.entries
    assert entry.status is CheckStatus.PASS
    assert "'AA-6061-T6'" in entry.detail


def test_a_heat_treatment_with_no_base_material_is_not_evaluated():
    treatment = HeatTreatment(specification="AMS 2770", condition="T6")
    (entry,) = callout_scorecard(CalloutSet(callouts=(treatment,))).entries
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "no base material" in entry.detail


def test_a_typed_note_no_check_consumes_says_so_rather_than_passing():
    note = ProcessNote(scope="bore", category="shot_peen", parameters={"intensity": _q(0.3, "mm")})
    (entry,) = callout_scorecard(CalloutSet(callouts=(note,))).entries
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "no check in this library consumes this category yet" in entry.detail


def test_a_coating_entry_states_both_dimensional_effects():
    (entry,) = callout_scorecard(CalloutSet(callouts=(_coating(),))).entries
    assert entry.status is CheckStatus.PASS
    assert "10–26 µm on diameter" in entry.detail
    assert "20–52 µm" in entry.detail  # the 4t thread shift


def test_an_empty_callout_set_produces_an_empty_card_not_a_pass():
    # The scorecard roll-up already treats an empty card as NOT_EVALUATED; this pins that
    # a part with no callouts cannot be read as "callouts checked, all good".
    card = callout_scorecard(CalloutSet())
    assert card.entries == ()
    assert card.status is CheckStatus.NOT_EVALUATED


def test_the_roughness_parameter_travels_with_the_callout():
    rz = _finish(parameter=RoughnessParameter.RZ, roughness=_q(1.6, "um"))
    assert "Rz" in str(rz)
    assert "Rz" in rz.value_signature()
