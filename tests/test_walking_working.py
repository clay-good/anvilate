"""Walking-working surfaces: the clause's own numbers, and the regime that decides which.

Every expected value here is written as 29 CFR 1910 Subpart D writes it — inches and
pounds-force — rather than as the pack stores it, so a transcription error shows up as a
test that disagrees with the regulation rather than as two copies of the same mistake.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.packs.walking_working import (
    DEFLECTED_HEIGHT_FLOOR,
    MIDRAIL_FORCE,
    SUBPART_D_EDITION,
    TOEBOARD_FORCE,
    TOEBOARD_HEIGHT,
    TOP_RAIL_FORCE,
    TOP_RAIL_HEIGHT,
    TOP_RAIL_TOLERANCE,
    GuardrailSystem,
    Regime,
    screen_guardrail,
)
from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity

_Q = Quantity.parse


def _guardrail(**overrides: object) -> GuardrailSystem:
    """A 48.3 x 3.2 CHS guardrail in S355, at 1.8 m post centres."""
    fields: dict[str, object] = {
        "regime": Regime.GENERAL_INDUSTRY,
        "post_height": _Q("1070 mm"),
        "post_spacing": _Q("1800 mm"),
        "post_section_modulus": _Q("4930 mm**3"),
        "post_second_moment": _Q("1.19e5 mm**4"),
        "yield_strength": _Q("355 MPa"),
        "elastic_modulus": _Q("200 GPa"),
        "rail_section_modulus": _Q("4930 mm**3"),
        "midrail_height": _Q("530 mm"),
        "toeboard_height": _Q("100 mm"),
        "toeboard_section_modulus": _Q("1670 mm**3"),
    }
    fields.update(overrides)
    return GuardrailSystem(**fields)  # type: ignore[arg-type]


def _entry(card, name: str):
    return next(entry for entry in card.entries if entry.name == name)


# --- the numbers are the regulation's -------------------------------------------------


def test_every_constant_is_what_the_clause_says_in_the_units_it_says_it_in():
    """Read from the eCFR on 2026-11-15; written here as the text writes them."""
    assert TOP_RAIL_HEIGHT.to("inch").magnitude == 42.0  # 1910.29(b)(1)
    assert TOP_RAIL_TOLERANCE.to("inch").magnitude == 3.0  # 1910.29(b)(1)
    assert TOP_RAIL_FORCE.to("lbf").magnitude == 200.0  # 1910.29(b)(3)
    assert DEFLECTED_HEIGHT_FLOOR.to("inch").magnitude == 39.0  # 1910.29(b)(4)
    assert MIDRAIL_FORCE.to("lbf").magnitude == 150.0  # 1910.29(b)(5)
    assert TOEBOARD_HEIGHT.to("inch").magnitude == 3.5  # 1910.29(k)(1)(ii)
    assert TOEBOARD_FORCE.to("lbf").magnitude == 50.0  # 1910.29(k)(1)(vi)
    # And the SI values the clause prints beside each, which is the other half of the
    # transcription: 200 lbf is 890 N in the text, 150 lbf is 667 N, 50 lbf is 222 N.
    assert TOP_RAIL_FORCE.to("N").magnitude == pytest.approx(890.0, abs=1.0)
    assert MIDRAIL_FORCE.to("N").magnitude == pytest.approx(667.0, abs=1.0)
    assert TOEBOARD_FORCE.to("N").magnitude == pytest.approx(222.0, abs=1.0)
    assert DEFLECTED_HEIGHT_FLOOR.to("cm").magnitude == pytest.approx(99.0, abs=0.5)


def test_every_entry_cites_its_paragraph_and_the_edition_it_was_read_from():
    """A clause with no edition is a number somebody will still read after it changes."""
    card = screen_guardrail(_guardrail())
    assert card.entries
    for entry in card.entries:
        assert entry.reference is not None
        assert "29 CFR 1910." in entry.reference
        assert SUBPART_D_EDITION in entry.reference
    cited = {entry.reference.split(" (")[0] for entry in card.entries}
    assert "29 CFR 1910.29(b)(1)" in cited
    assert "29 CFR 1910.29(b)(3)" in cited
    assert "29 CFR 1910.29(b)(4)" in cited
    assert "29 CFR 1910.29(b)(5)" in cited


# --- the regime -----------------------------------------------------------------------


def test_a_construction_guardrail_is_refused_rather_than_screened_against_1910():
    """A guardrail that passes the wrong regulation is worse than one nobody checked."""
    with pytest.raises(RefusalError, match="1926 Subparts M and X"):
        screen_guardrail(_guardrail(regime=Regime.CONSTRUCTION))


def test_a_user_declared_regime_is_refused_because_there_is_no_bundled_limit():
    with pytest.raises(RefusalError, match="no bundled limit"):
        screen_guardrail(_guardrail(regime=Regime.USER_DECLARED))


def test_the_three_regimes_are_the_three_and_general_industry_is_the_one_that_runs():
    assert {regime.value for regime in Regime} == {
        "us_general_industry",
        "us_construction",
        "user_declared",
    }
    assert screen_guardrail(_guardrail()).entries


# --- the height band --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("inches", "status"),
    [
        (39.0, CheckStatus.PASS),  # the bottom of the band, 42 − 3
        (42.0, CheckStatus.PASS),
        (45.0, CheckStatus.PASS),  # the top of it, 42 + 3
        (38.9, CheckStatus.FAIL),
        (45.1, CheckStatus.WARNING),
    ],
)
def test_the_top_rail_height_band_is_42_plus_or_minus_3(inches, status):
    """Both edges are in the band, and the two neighbours are not — a refusal test on its
    own cannot see which side of the bound it is on."""
    card = screen_guardrail(
        _guardrail(
            post_height=Quantity(magnitude=inches, unit="inch"),
            midrail_height=Quantity(magnitude=inches / 2, unit="inch"),
        )
    )
    assert _entry(card, "guardrail top rail height").status is status


def test_a_rail_above_45_inches_is_a_warning_and_not_a_pass():
    """The clause permits it only if every other criterion of (b) is met — which is the
    verdict this very card is in the middle of reaching."""
    entry = _entry(
        screen_guardrail(_guardrail(post_height=_Q("1300 mm"))),
        "guardrail top rail height",
    )
    assert entry.status is CheckStatus.WARNING
    assert "every other criterion" in entry.detail


# --- strength ---------------------------------------------------------------------------


def test_the_post_carries_the_clauses_force_at_the_rail_height():
    """σ = P·h/Z with the clause's own 200 lbf, worked by hand off the regulation."""
    guardrail = _guardrail()
    entry = _entry(screen_guardrail(guardrail), "guardrail post under the top rail load")

    moment = TOP_RAIL_FORCE.to("N").magnitude * guardrail.post_height.to("m").magnitude
    stress = moment / guardrail.post_section_modulus.to("m**3").magnitude / 1e6
    expected = guardrail.yield_strength.to("MPa").magnitude / stress
    assert entry.safety_factor == pytest.approx(expected, rel=1e-9)
    assert entry.status is CheckStatus.PASS


def test_a_post_too_slender_for_the_clause_fails_and_names_the_section_to_move():
    guardrail = _guardrail(post_section_modulus=_Q("1200 mm**3"))
    entry = _entry(screen_guardrail(guardrail), "guardrail post under the top rail load")

    assert entry.status is CheckStatus.FAIL
    assert entry.repair_hint is not None
    assert entry.repair_hint.parameter == "post_section_modulus"
    # The solved value is exact: the stress is linear in 1/Z.
    repaired = _guardrail(
        post_section_modulus=Quantity(magnitude=entry.repair_hint.corrective_value, unit="mm**3")
    )
    assert (
        _entry(screen_guardrail(repaired), "guardrail post under the top rail load").status
        is CheckStatus.PASS
    )


def test_the_midrail_is_screened_at_150_lbf_and_the_top_rail_at_200():
    card = screen_guardrail(_guardrail())
    top = _entry(card, "guardrail top rail between posts")
    mid = _entry(card, "guardrail midrail")
    # Same span, same section, same steel: the only difference is the clause's force, so
    # the safety factors are in the inverse ratio of 200 to 150.
    assert mid.safety_factor / top.safety_factor == pytest.approx(200.0 / 150.0, rel=1e-9)


def test_the_toeboard_is_screened_at_50_lbf():
    entry = _entry(screen_guardrail(_guardrail()), "guardrail toeboard")
    assert "50 lbf" in entry.detail


# --- deflection ---------------------------------------------------------------------------


def test_the_deflected_rail_must_stay_above_39_inches():
    """1910.29(b)(4), and the cantilever that decides it."""
    guardrail = _guardrail()
    entry = _entry(screen_guardrail(guardrail), "guardrail deflected height")

    deflection = (
        TOP_RAIL_FORCE.to("N").magnitude
        * guardrail.post_height.to("m").magnitude ** 3
        / (
            3
            * guardrail.elastic_modulus.to("Pa").magnitude
            * guardrail.post_second_moment.to("m**4").magnitude
        )
    )
    remaining = guardrail.post_height.to("mm").magnitude - deflection * 1000.0
    assert entry.comparison is not None
    assert entry.comparison.measured.to("mm").magnitude == pytest.approx(remaining, rel=1e-9)
    assert entry.status is CheckStatus.PASS


def test_a_post_that_bends_below_the_floor_fails_the_deflection_clause():
    """A tall, flexible post passes nothing the clause asks and the card says which."""
    card = screen_guardrail(
        _guardrail(post_second_moment=_Q("8000 mm**4"), post_section_modulus=_Q("900 mm**3"))
    )
    deflection = _entry(card, "guardrail deflected height")
    assert deflection.status is CheckStatus.FAIL
    assert card.status is CheckStatus.FAIL


def test_the_deflection_entry_says_what_is_not_in_its_number():
    """The rail's own sag between posts is not in the cantilever, and a reader has to know."""
    entry = _entry(screen_guardrail(_guardrail()), "guardrail deflected height")
    assert "sag between posts is not in this number" in entry.detail


# --- what the card does and does not claim ------------------------------------------------


def test_a_run_with_no_midrail_or_toeboard_gets_no_entry_for_them():
    """A check that did not apply and a check that passed are different facts."""
    card = screen_guardrail(
        _guardrail(midrail_height=None, toeboard_height=None, toeboard_section_modulus=None)
    )
    names = {entry.name for entry in card.entries}
    assert "guardrail midrail" not in names
    assert "guardrail toeboard" not in names
    assert "guardrail toeboard height" not in names
    assert "guardrail top rail height" in names
    assert card.status is CheckStatus.PASS


def test_a_toeboard_section_with_no_toeboard_height_is_refused():
    with pytest.raises(ValidationError, match="no toeboard to screen"):
        _guardrail(toeboard_height=None)


def test_a_midrail_at_or_above_the_top_rail_is_not_an_intermediate_member():
    with pytest.raises(ValidationError, match="not an intermediate member"):
        _guardrail(midrail_height=_Q("1070 mm"))
    with pytest.raises(ValidationError, match="not an intermediate member"):
        _guardrail(midrail_height=_Q("1200 mm"))


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("post_height", _Q("1 kN")),
        ("post_section_modulus", _Q("100 mm**2")),
        ("yield_strength", _Q("355 N")),
        ("post_second_moment", _Q("100 mm**3")),
    ],
)
def test_a_dimension_that_is_not_what_it_says_is_refused(field, wrong):
    with pytest.raises(ValidationError, match=field):
        _guardrail(**{field: wrong})


@pytest.mark.parametrize("field", ["post_height", "post_spacing", "yield_strength"])
def test_a_zero_or_negative_dimension_is_refused(field):
    with pytest.raises(ValidationError, match="is positive"):
        _guardrail(
            **{field: Quantity(magnitude=0.0, unit=_guardrail().__getattribute__(field).unit)}
        )


def test_the_required_factor_is_one_by_default_because_the_clause_is_not_a_factored_load():
    """1910.29 states a force the system must withstand without failure."""
    card = screen_guardrail(_guardrail())
    strength = _entry(card, "guardrail post under the top rail load")
    assert strength.required_safety_factor == 1.0
    stricter = screen_guardrail(_guardrail(), required_safety_factor=2.0)
    assert _entry(stricter, "guardrail post under the top rail load").required_safety_factor == 2.0


def test_every_strength_entry_shows_its_work():
    card = screen_guardrail(_guardrail())
    for name in (
        "guardrail post under the top rail load",
        "guardrail top rail between posts",
        "guardrail midrail",
        "guardrail toeboard",
        "guardrail deflected height",
    ):
        entry = _entry(card, name)
        assert entry.derivation is not None, name
        assert entry.derivation.citation


@pytest.mark.parametrize(
    ("check", "parameter", "weaken"),
    [
        ("guardrail top rail between posts", "rail_section_modulus", _Q("400 mm**3")),
        ("guardrail midrail", "rail_section_modulus", _Q("400 mm**3")),
        ("guardrail toeboard", "toeboard_section_modulus", _Q("90 mm**3")),
    ],
)
def test_every_solved_lever_lands_its_check_exactly_at_the_margin(check, parameter, weaken):
    """A lever that merely points the right way is a direction; this one is a value, and
    a value is only worth anything if putting it back in lands the check where it said."""
    failing = _guardrail(**{parameter: weaken})
    entry = _entry(screen_guardrail(failing), check)
    assert entry.status is CheckStatus.FAIL
    assert entry.repair_hint is not None
    assert entry.repair_hint.parameter == parameter

    repaired = _guardrail(
        **{parameter: Quantity(magnitude=entry.repair_hint.corrective_value, unit="mm**3")}
    )
    landed = _entry(screen_guardrail(repaired), check)
    assert landed.status is CheckStatus.PASS
    # Exactly at the margin, not merely past it: the stress is linear in 1/Z.
    assert landed.safety_factor == pytest.approx(landed.required_safety_factor, rel=1e-9)
    # And a hair under it still fails, so the value is the edge and not a guess.
    nearly = _guardrail(
        **{parameter: Quantity(magnitude=entry.repair_hint.corrective_value * 0.999, unit="mm**3")}
    )
    assert _entry(screen_guardrail(nearly), check).status is CheckStatus.FAIL


def test_the_docs_page_quotes_the_clauses_own_numbers():
    """Every figure the page argues from is read back off the constants, and every
    clause it names is one an entry actually cites."""
    import re
    from pathlib import Path

    page = (
        Path(__file__).resolve().parent.parent / "docs" / "walking-working-surfaces.md"
    ).read_text()

    quoted = {
        "42 in ± 3 in": (TOP_RAIL_HEIGHT, TOP_RAIL_TOLERANCE),
        "200 lbf": (TOP_RAIL_FORCE,),
        "150 lbf": (MIDRAIL_FORCE,),
        "50 lbf": (TOEBOARD_FORCE,),
        "39 in": (DEFLECTED_HEIGHT_FLOOR,),
        "3.5 in": (TOEBOARD_HEIGHT,),
    }
    for text, constants in quoted.items():
        assert text in page, f"the page no longer quotes {text}"
        numbers = [float(n) for n in re.findall(r"[\d.]+", text)]
        for number, constant in zip(numbers, constants, strict=True):
            unit = "lbf" if "lbf" in text else "inch"
            assert constant.to(unit).magnitude == pytest.approx(number), text

    # Every clause the page's table names is one the card really cites.
    cited = {entry.reference.split(" (")[0] for entry in screen_guardrail(_guardrail()).entries}
    for clause in re.findall(r"\| (1910\.\d+\([^)]+\)[^|]*?) \|", page):
        assert f"29 CFR {clause.strip()}" in cited, f"the page names {clause} and nothing cites it"
    assert len(cited) >= 5
