"""The galvanic series as MIL-STD-889C prints it, and the rules a separation alone misses.

Every number and every rule here was read from MIL-STD-889C itself — a US Department of
Defense standard approved for public release — and not recalled. The thresholds that
circulate for this calculation (0.15 V, 0.25 V, 0.50 V of "anodic index") are **not in
889C**; secondary sources attribute them to a different standard, and this ships no
threshold at all for that reason.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.refusal import RefusalError
from anvilate.standards.galvanic import (
    GALVANIC_SERIES,
    GALVANIC_SERIES_CITATION,
    LISTED_TWICE,
    WORST_ENVIRONMENT,
    GalvanicCouple,
    GalvanicEnvironment,
    GalvanicVerdict,
    screen_galvanic_couple,
    series_position,
)


def _couple(**overrides) -> GalvanicCouple:
    declared = {
        "first": "Al alloy 6061-T6",
        "second": "Copper 110",
        "environment": GalvanicEnvironment.MARINE_ATMOSPHERE,
        "separation_limit": 10,
        "limit_basis": "the project's corrosion-control plan, rev B",
    }
    return GalvanicCouple(**{**declared, **overrides})


def test_the_series_is_the_table_as_published():
    """93 names, most active first, most noble last — Table II's own order."""
    assert len(GALVANIC_SERIES) == 93
    assert GALVANIC_SERIES[0] == "Magnesium"
    assert GALVANIC_SERIES[-3:] == ("Silver", "Gold", "Graphite")
    assert series_position("Magnesium") == 0
    assert series_position("Graphite") == len(GALVANIC_SERIES) - 1
    # The order is the whole of the data, so a few landmarks are pinned against it.
    assert series_position("Zinc (hot-dip, die cast or plated)") < series_position("Steel 1010")
    assert series_position("Steel 1010") < series_position("Copper 110")
    assert series_position("Copper 110") < series_position("Titanium 75A")
    assert "MIL-STD-889C" in GALVANIC_SERIES_CITATION
    assert "ARS-TR-67-11" in GALVANIC_SERIES_CITATION


def test_a_name_the_table_prints_twice_is_refused_rather_than_resolved():
    """The source has a duplicate, and a name that means two positions is not a position.

    Table II lists "Al alloy 1160-1114" at two different places. Taking the first silently
    would screen the metal against a position nobody chose, so this says so instead.
    """
    assert LISTED_TWICE == frozenset({"Al alloy 1160-1114"})
    assert GALVANIC_SERIES.count("Al alloy 1160-1114") == 2
    with pytest.raises(RefusalError, match="at two different places"):
        series_position("Al alloy 1160-1114")


def test_a_name_the_table_does_not_print_is_refused_with_the_near_ones():
    with pytest.raises(RefusalError, match="did you mean 'Magnesium'"):
        series_position("Magnesiun")
    with pytest.raises(RefusalError, match="did you mean 'Copper 110'"):
        series_position("Copper 11")
    # And a name near nothing gets no suggestion rather than three wrong ones: at the
    # library default cutoff "aluminium" was answered with Uranium, Magnesium and Indium.
    with pytest.raises(RefusalError) as refused:
        series_position("aluminium")
    assert "did you mean" not in str(refused.value)
    with pytest.raises(RefusalError, match="named by the string"):
        series_position(6061)


def test_the_anode_is_the_metal_higher_in_the_series():
    """§5.1.1: the metal higher in the series is the anode and corrodes preferentially."""
    couple = _couple()
    assert couple.anode == "Al alloy 6061-T6"
    assert couple.cathode == "Copper 110"
    # And naming them the other way round does not change which is which.
    swapped = _couple(first="Copper 110", second="Al alloy 6061-T6")
    assert swapped.anode == couple.anode and swapped.cathode == couple.cathode
    assert swapped.separation == couple.separation == 37


def test_the_limit_is_the_callers_because_the_standard_states_none():
    """889C says only that closer is more compatible. The number is declared, with a basis."""
    with pytest.raises(ValidationError):
        GalvanicCouple(
            first="Al alloy 6061-T6",
            second="Copper 110",
            environment=GalvanicEnvironment.SEA_WATER,
            limit_basis="a plan",
        )
    tight = screen_galvanic_couple(_couple(separation_limit=10))
    loose = screen_galvanic_couple(_couple(separation_limit=40))
    assert not tight.acceptable and loose.acceptable
    assert "the project's corrosion-control plan, rev B" in " ".join(tight.reasons)


def test_an_isolation_measure_clears_a_separation_and_nothing_else():
    isolated = screen_galvanic_couple(_couple(isolation="a non-absorbing inert gasket, §5.2(b)"))
    assert isolated.acceptable
    assert "isolated by a non-absorbing inert gasket" in " ".join(isolated.reasons)
    assert "§5.1.2" in " ".join(isolated.reasons)
    # It does not clear the area rule, which is about the couple and not the distance.
    still_wrong = screen_galvanic_couple(
        _couple(
            isolation="a non-absorbing inert gasket, §5.2(b)",
            first_area_mm2=100.0,
            second_area_mm2=5000.0,
        )
    )
    assert not still_wrong.acceptable
    assert "the larger area" in " ".join(still_wrong.reasons)


def test_a_controlled_environment_nobody_assured_is_screened_as_the_worst_one():
    """Note (g): humidity control is assured only by a hermetically sealed compartment,
    and where it is not, the contact is treated as if it were in the worst environment."""
    claimed = screen_galvanic_couple(
        _couple(environment=GalvanicEnvironment.CONTROLLED, separation_limit=40)
    )
    assert claimed.declared_environment is GalvanicEnvironment.CONTROLLED
    assert claimed.environment is WORST_ENVIRONMENT is GalvanicEnvironment.SEA_WATER
    assert "note (g)" in " ".join(claimed.reasons)

    assured = screen_galvanic_couple(
        _couple(
            environment=GalvanicEnvironment.CONTROLLED,
            separation_limit=40,
            humidity_assured=True,
        )
    )
    assert assured.environment is GalvanicEnvironment.CONTROLLED
    assert "note (g)" not in " ".join(assured.reasons)
    # The assurance says nothing anywhere else, so declaring it elsewhere is refused.
    with pytest.raises(ValidationError, match="where it says nothing"):
        _couple(environment=GalvanicEnvironment.SEA_WATER, humidity_assured=True)


def test_the_cathode_is_the_smaller_area_and_the_reverse_is_called_out():
    """§5.2(a): stainless bolts in an aluminium sheet, but not the reverse."""
    bolts_in_sheet = screen_galvanic_couple(
        _couple(separation_limit=40, first_area_mm2=5000.0, second_area_mm2=100.0)
    )
    assert bolts_in_sheet.acceptable
    sheet_on_bolts = screen_galvanic_couple(
        _couple(separation_limit=40, first_area_mm2=100.0, second_area_mm2=5000.0)
    )
    assert not sheet_on_bolts.acceptable
    assert "§5.2(a)" in " ".join(sheet_on_bolts.reasons)
    # One area alone says nothing about the ratio, so it is not half-checked.
    half = screen_galvanic_couple(_couple(separation_limit=40, first_area_mm2=100.0))
    assert half.acceptable and "larger area" not in " ".join(half.reasons)


def test_magnesium_takes_the_maximum_protective_system_whatever_else_is_declared():
    """§5.1.6, and the reason a separation limit cannot clear it: the rule is about the
    metal, not the distance."""
    bare = screen_galvanic_couple(_couple(first="Magnesium", separation_limit=99))
    assert not bare.acceptable
    assert "§5.1.6" in " ".join(bare.reasons)
    # Even inside the limit, and even with the areas the right way round.
    sized = screen_galvanic_couple(
        _couple(
            first="Magnesium",
            separation_limit=99,
            first_area_mm2=5000.0,
            second_area_mm2=100.0,
        )
    )
    assert not sized.acceptable
    # A declared measure clears it, and the clause is still named.
    protected = screen_galvanic_couple(
        _couple(
            first="Magnesium",
            separation_limit=99,
            isolation="sealed edges and the maximum protective system, §5.1.6",
        )
    )
    assert protected.acceptable and "§5.1.6" in " ".join(protected.reasons)


def test_a_couple_of_one_metal_is_not_a_couple():
    with pytest.raises(ValidationError, match="two different metals"):
        _couple(first="Copper 110", second="Copper 110")


def test_an_acceptable_couple_still_says_why():
    """A verdict with no reason is a verdict a reader cannot check."""
    verdict = screen_galvanic_couple(_couple(separation_limit=40))
    assert isinstance(verdict, GalvanicVerdict)
    assert verdict.acceptable and verdict.reasons
    assert "within the declared limit of 40" in " ".join(verdict.reasons)
    assert verdict.citation == GALVANIC_SERIES_CITATION
    assert "37 places apart in marine atmosphere, acceptable" in str(verdict)


def test_the_screen_takes_a_couple_and_says_so_otherwise():
    with pytest.raises(RefusalError, match="couple is a GalvanicCouple"):
        screen_galvanic_couple({"first": "Magnesium"})


@pytest.mark.parametrize("field", ["first_area_mm2", "second_area_mm2"])
def test_an_area_is_positive(field):
    with pytest.raises(ValidationError, match="positive area"):
        _couple(**{field: 0.0})


def test_the_separation_limit_is_a_count_and_not_a_voltage():
    with pytest.raises(ValidationError, match="count of places"):
        _couple(separation_limit=-1)
