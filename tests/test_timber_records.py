"""Tests for NDS reference design values as records.

The number is the least of what a reference design value is. What is being pinned here is
the **factor chain**: NDS Table 4.3.1 says which adjustment applies to which value, and the
library's own docstring has always said the caller "simply omits" the ones that do not —
a rule stated in prose and enforced by nobody until this record.

The two absences that catch people are C_D on compression perpendicular to grain and on
either modulus, and C_F on shear and on either modulus. Neither is a conservative extra:
applying C_D to a modulus at a snow load makes the beam 15% stiffer than the standard
allows, on exactly the deflection check that usually governs a timber beam.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.standards.timber import (
    NDS_APPLICABLE_FACTORS,
    SizeClassification,
    TimberDesignValue,
    TimberProperty,
)
from anvilate.units import Quantity

Q = Quantity.parse


def _value(**kwargs) -> TimberDesignValue:
    defaults = {
        "standard": "NDS",
        "edition": "2018",
        "table": "Table 4A",
        "species": "Douglas Fir-Larch",
        "grade": "No. 2",
        "size_classification": SizeClassification.DIMENSION_LUMBER,
        "property": TimberProperty.BENDING,
        "value": Q("900 psi"),
    }
    return TimberDesignValue(**{**defaults, **kwargs})


@pytest.mark.parametrize("field", ["standard", "edition", "table", "species", "grade"])
def test_a_design_value_cannot_be_a_bare_number(field):
    with pytest.raises(ValidationError, match=f"must state its {field}"):
        _value(**{field: "  "})


def test_a_design_value_is_a_positive_finite_stress():
    with pytest.raises(ValidationError, match="stress or a modulus"):
        _value(value=Q("900 N"))
    with pytest.raises(ValidationError, match="positive and finite"):
        _value(value=Q("0 psi"))
    with pytest.raises(ValidationError, match="positive and finite"):
        _value(value=Q("nan psi"))


# --- NDS Table 4.3.1, enforced ----------------------------------------------------------


def test_the_load_duration_factor_is_refused_on_the_values_it_does_not_apply_to():
    """C_D scales strength for how long a load acts. Stiffness does not work that way, and
    neither does bearing perpendicular to grain."""
    for prop in (
        TimberProperty.MODULUS,
        TimberProperty.MODULUS_MIN,
        TimberProperty.COMPRESSION_PERPENDICULAR,
    ):
        record = _value(property=prop, value=Q("1600000 psi"))
        with pytest.raises(ValueError, match="does not apply"):
            record.adjusted({"C_D": 1.15})
        assert record.adjusted({"C_M": 0.9}).magnitude == pytest.approx(0.9 * 1_600_000)


def test_the_size_factor_is_refused_on_shear_and_on_the_moduli():
    for prop in (TimberProperty.SHEAR, TimberProperty.MODULUS, TimberProperty.MODULUS_MIN):
        with pytest.raises(ValueError, match=r"C_F"):
            _value(property=prop, value=Q("180 psi")).adjusted({"C_F": 1.1})


def test_the_factors_a_value_does_take_are_applied():
    bending = _value()
    assert bending.adjusted({"C_D": 1.15, "C_F": 1.1}).magnitude == pytest.approx(900 * 1.15 * 1.1)
    # Every factor Table 4.3.1 lists for bending is accepted together.
    everything = dict.fromkeys(NDS_APPLICABLE_FACTORS[TimberProperty.BENDING], 1.0)
    assert bending.adjusted(everything).magnitude == pytest.approx(900.0)


def test_the_applicability_table_is_the_published_one_and_not_an_empty_set():
    """A gate on the gate: a table that had lost its entries would accept every factor on
    every property and every refusal test above would still pass — because they assert a
    *refusal*, and an empty allowed-set refuses everything."""
    assert set(NDS_APPLICABLE_FACTORS) == set(TimberProperty)
    assert all(NDS_APPLICABLE_FACTORS.values()), "a property with no factors accepts nothing"
    # The three shapes the table actually has.
    assert "C_D" in NDS_APPLICABLE_FACTORS[TimberProperty.BENDING]
    assert "C_D" not in NDS_APPLICABLE_FACTORS[TimberProperty.MODULUS]
    assert "C_P" in NDS_APPLICABLE_FACTORS[TimberProperty.COMPRESSION_PARALLEL]
    assert "C_L" in NDS_APPLICABLE_FACTORS[TimberProperty.BENDING]
    assert "C_b" in NDS_APPLICABLE_FACTORS[TimberProperty.COMPRESSION_PERPENDICULAR]
    assert "C_T" in NDS_APPLICABLE_FACTORS[TimberProperty.MODULUS_MIN]
    # C_L is the beam stability factor and belongs to bending alone.
    holders = {p for p, f in NDS_APPLICABLE_FACTORS.items() if "C_L" in f}
    assert holders == {TimberProperty.BENDING}
    holders = {p for p, f in NDS_APPLICABLE_FACTORS.items() if "C_P" in f}
    assert holders == {TimberProperty.COMPRESSION_PARALLEL}


def test_a_non_positive_or_non_finite_factor_is_refused():
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="positive and finite"):
            _value().adjusted({"C_D": bad})


def test_what_applying_the_duration_factor_to_a_modulus_would_have_cost():
    """The size of the mistake, stated rather than asserted in the abstract."""
    modulus = _value(property=TimberProperty.MODULUS, value=Q("1600000 psi"))
    correct = modulus.adjusted({"C_M": 1.0}).magnitude
    wrong = correct * 1.15  # the snow-load C_D, applied where the table does not list it
    assert wrong / correct == pytest.approx(1.15)
    with pytest.raises(ValueError):
        modulus.adjusted({"C_M": 1.0, "C_D": 1.15})


def test_the_record_says_which_kind_of_number_it_carries():
    """A stress and a modulus are both [pressure], which is exactly why the property has to
    be declared rather than inferred from the unit."""
    stress = _value()
    modulus = _value(property=TimberProperty.MODULUS, value=Q("1600000 psi"))
    assert stress.value.has_dimension("[pressure]")
    assert modulus.value.has_dimension("[pressure]")
    assert "stress" in str(stress) and "modulus" in str(modulus)
    assert stress.property is not modulus.property
