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
    MAX_CONNECTION_LOAD_DURATION,
    NDS_APPLICABLE_FACTORS,
    NDS_CONNECTION_FACTORS,
    ConnectionDesignValue,
    ConnectionLoad,
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


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        # `standard` and `edition` are provenance fields, refused by the shared rule with
        # their own sentence; the other three by this model's own loop.
        ("standard", "the standard this design value comes from"),
        ("edition", "the edition this design value comes from"),
        ("table", "must state its table"),
        ("species", "must state its species"),
        ("grade", "must state its grade"),
    ],
)
def test_a_design_value_cannot_be_a_bare_number(field, expected):
    with pytest.raises(ValidationError, match=expected):
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


@pytest.mark.parametrize(
    "case,subject,source",
    (
        (
            "record",
            "table",
            "the grade stamp, material certificate, cited NDS Supplement table, or project "
            "specification",
        ),
        (
            "factor",
            "adjustment factor C_D",
            "the governing NDS edition, Table 4.3.1, and selected conditions",
        ),
    ),
)
def test_timber_record_refusals_carry_structured_remedies(case, subject, source):
    from anvilate.refusal import RefusalError

    if case == "record":
        with pytest.raises(ValidationError) as refused:
            _value(table=" ")
        error = refused.value.errors()[0]["ctx"]["error"]
    else:
        with pytest.raises(ValueError) as refused:
            _value().adjusted({"C_D": 0.0})
        error = refused.value

    assert isinstance(error, RefusalError)
    assert error.remedies[0].model_dump() == {
        "action": "replace",
        "subject": subject,
        "source": source,
    }


def test_every_timber_record_refusal_site_is_structured():
    import ast
    import pathlib

    from conftest import parsed_source

    path = pathlib.Path(__file__).parents[1] / "src/anvilate/standards/timber.py"
    structured = []
    unstructured = []
    for node in ast.walk(parsed_source(path)):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "_timber_record_refusal":
            structured.append(node.exc)
        if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "ValueError":
            unstructured.append(node.exc)

    assert len(structured) == 16
    assert unstructured == []
    for call in structured:
        assert {"subject", "source"} <= {keyword.arg for keyword in call.keywords}, call.lineno


# --- NDS Table 11.3.1: the connection row, and the two footnotes under it ---------------


def _connection(**kwargs) -> ConnectionDesignValue:
    defaults = {
        "standard": "NDS",
        "edition": "2018",
        "table": "Table 12.2A",
        "fastener": "1/2 in lag screw in Douglas Fir-Larch",
        "load": ConnectionLoad.WITHDRAWAL,
        "value": Q("437 lbf/inch"),
    }
    return ConnectionDesignValue(**{**defaults, **kwargs})


def test_the_connection_table_covers_every_kind_of_value_it_names():
    """A row added to the enum and not to the table would key-error at the worst moment."""
    assert set(NDS_CONNECTION_FACTORS) == set(ConnectionLoad)
    for load, factors in NDS_CONNECTION_FACTORS.items():
        assert {"C_D", "C_M", "C_t"} <= factors, load


def test_the_group_action_and_geometry_factors_are_not_on_the_withdrawal_row():
    """The absence Table 11.3.1 states and a chain composed by hand loses.

    Both factors describe fasteners sharing a load across a shear plane. A fastener pulled
    straight out has no shear plane, so applying them is not a conservative extra — it
    reduces the value for a mechanism that is not acting.
    """
    lateral = NDS_CONNECTION_FACTORS[ConnectionLoad.LATERAL]
    withdrawal = NDS_CONNECTION_FACTORS[ConnectionLoad.WITHDRAWAL]
    assert {"C_g", "C_Delta", "C_di"} <= lateral
    assert not {"C_g", "C_Delta", "C_di"} & withdrawal
    for factor in ("C_g", "C_Delta", "C_di"):
        with pytest.raises(ValueError, match="does not apply"):
            _connection().adjusted({factor: 0.9})
    # And the lateral row takes all three without complaint.
    assert _connection(load=ConnectionLoad.LATERAL, value=Q("141 lbf"), table="Table 12J").adjusted(
        {"C_g": 0.9, "C_Delta": 0.8, "C_di": 1.1}
    ).to("lbf").magnitude == pytest.approx(141 * 0.9 * 0.8 * 1.1)


def test_the_load_duration_factor_is_capped_at_the_connections_own_ceiling():
    """Footnote 1, and the sharpest difference between a member and its connection.

    NDS Table 2.3.2 gives C_D = 2.0 for an impact load, and `nds_load_duration_factor`
    returns it. The connection joining that member takes 1.6. One load case, two factors,
    and the chain a spreadsheet copies across from the member overstates the connection
    by 25%.
    """
    from anvilate.analysis import LoadDuration, nds_load_duration_factor

    member = nds_load_duration_factor(LoadDuration.IMPACT)
    assert member == 2.0 > MAX_CONNECTION_LOAD_DURATION
    with pytest.raises(ValueError, match="caps C_D at 1.6"):
        _connection().adjusted({"C_D": member})
    # The ceiling itself is allowed, which is the bound the refusal turns on.
    assert _connection().adjusted({"C_D": MAX_CONNECTION_LOAD_DURATION}).to(
        "lbf/inch"
    ).magnitude == pytest.approx(437 * 1.6)


def test_the_wet_service_factor_is_refused_on_a_toe_nail_in_withdrawal():
    """Footnote 2, and it turns on a declaration the number cannot carry."""
    plain, toe = _connection(), _connection(toe_nailed=True)
    assert plain.adjusted({"C_M": 0.7}).to("lbf/inch").magnitude == pytest.approx(437 * 0.7)
    with pytest.raises(ValueError, match="footnote 2"):
        toe.adjusted({"C_M": 0.7})
    # The toe-nail factor itself still applies, and so does every other factor on the row.
    assert toe.adjusted({"C_tn": 0.67, "C_D": 1.0}).to("lbf/inch").magnitude == pytest.approx(
        437 * 0.67
    )
    # A lateral toe-nail does take C_M: footnote 2 is about withdrawal only.
    assert _connection(load=ConnectionLoad.LATERAL, value=Q("141 lbf"), toe_nailed=True).adjusted(
        {"C_M": 0.7}
    ).to("lbf").magnitude == pytest.approx(141 * 0.7)


def test_a_withdrawal_value_and_a_lateral_one_cannot_be_swapped():
    """W is per inch of penetration and Z is a force; the number does not say which."""
    with pytest.raises(ValidationError, match=r"\[force\] / \[length\]"):
        _connection(value=Q("437 lbf"))
    with pytest.raises(ValidationError, match=r"a Z value is a \[force\]"):
        _connection(load=ConnectionLoad.LATERAL, value=Q("437 lbf/inch"))


def test_withdrawal_capacity_is_the_adjusted_value_times_the_penetration():
    record = _connection()
    assert record.withdrawal_capacity(Q("4 inch"), {"C_D": 1.6}).to("lbf").magnitude == (
        pytest.approx(437 * 1.6 * 4)
    )
    # It is the one step between a table and a force, and it needs a withdrawal table.
    with pytest.raises(ValueError, match="already a force"):
        _connection(load=ConnectionLoad.LATERAL, value=Q("141 lbf")).withdrawal_capacity(
            Q("4 inch"), {}
        )
    for bad in (Q("4 lbf"), 4.0, Quantity(magnitude=float("nan"), unit="inch"), Q("0 inch")):
        with pytest.raises(ValueError, match="penetration"):
            record.withdrawal_capacity(bad, {})


def test_a_head_pull_through_value_is_not_a_toe_nail():
    with pytest.raises(ValidationError, match="not a toe-nail condition"):
        _connection(load=ConnectionLoad.PULL_THROUGH, value=Q("150 lbf"), toe_nailed=True)


def test_a_connection_record_says_which_fastener_and_which_table():
    for field in ("table", "fastener"):
        with pytest.raises(ValidationError, match=f"must state its {field}"):
            _connection(**{field: "   "})
    assert "1/2 in lag screw" in str(_connection())
    assert "toe-nailed" in str(_connection(toe_nailed=True))
    assert "toe-nailed" not in str(_connection())


def test_a_connection_factor_is_positive_and_finite():
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="positive and finite"):
            _connection().adjusted({"C_M": bad})
