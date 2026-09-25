"""A product's own EPD, read as a carbon factor (embodied-carbon 3.2).

The declaration below is synthetic: it has openEPD's shape, taken from the reference
implementation's models (cchangelabs/openepd, Apache-2.0), and made-up values. Real
declarations belong to their manufacturers and program operators, and the spec forbids
redistributing them, so none is committed here.
"""

from __future__ import annotations

import json

import pytest

from anvilate.analysis import (
    ModuleScope,
    carbon_contribution,
    carbon_factor_from_openepd,
    embodied_carbon_estimate,
)
from anvilate.units import Quantity

_EPD = {
    "doctype": "openEPD",
    "openepd_version": "0.1.0",
    "id": "ec3synthetic",
    "version": 2,
    "product_name": "Example 6061 extrusion",
    "manufacturer": {"name": "Example Aluminium Co."},
    "declared_unit": {"qty": 1, "unit": "t"},
    "valid_until": "2030-06-30T00:00:00Z",
    "geography": ["US", "CA"],
    "impacts": {"TRACI 2.1": {"gwp": {"A1A2A3": {"mean": 8400.0, "unit": "kgCO2e", "rsd": 0.1}}}},
}


def _with(**changes: object) -> str:
    document = json.loads(json.dumps(_EPD))
    for key, value in changes.items():
        if value is None:
            document.pop(key, None)
        else:
            document[key] = value
    return json.dumps(document)


def test_the_declared_gwp_over_the_mass_of_a_declared_unit_is_the_factor():
    factor = carbon_factor_from_openepd(json.dumps(_EPD), material="AA-6061-T6")
    # 8,400 kgCO2e per tonne is 8.4 kgCO2e per kg, cradle to gate.
    assert factor.value == pytest.approx(8.4, rel=1e-12)
    assert factor.scope is ModuleScope.A1_A3
    # The band is the declaration's own one rsd either side, not a generic table's.
    assert (factor.band_low, factor.band_high) == pytest.approx((0.9, 1.1))
    assert factor.dataset_id == "ec3synthetic" and factor.version == "2"
    assert factor.geography == "US, CA"
    assert factor.source == (
        "openEPD ec3synthetic: Example 6061 extrusion by Example Aluminium Co., "
        "TRACI 2.1 GWP A1A2A3; band ±1 declared rsd (0.1)"
    )


def test_an_estimate_built_on_it_names_the_declaration():
    factor = carbon_factor_from_openepd(json.dumps(_EPD), material="AA-6061-T6")
    line = carbon_contribution(label="frame", mass=Quantity.parse("12 kg"), factor=factor)
    estimate = embodied_carbon_estimate([line])
    assert estimate.total.to("kg").magnitude == pytest.approx(100.8)
    assert "openEPD ec3synthetic" in estimate.dominant.factor.source


def test_a_declared_unit_that_is_not_a_mass_needs_the_mass_per_unit():
    by_volume = {"qty": 1, "unit": "m**3"}
    with pytest.raises(ValueError, match="no kg_per_declared_unit"):
        carbon_factor_from_openepd(_with(declared_unit=by_volume), material="C30 concrete")
    stated = _with(declared_unit=by_volume, kg_per_declared_unit={"qty": 2400, "unit": "kg"})
    factor = carbon_factor_from_openepd(stated, material="C30 concrete")
    assert factor.value == pytest.approx(8400.0 / 2400.0)


def test_no_stated_uncertainty_is_no_band_and_says_so():
    impacts = {"TRACI 2.1": {"gwp": {"A1A2A3": {"mean": 8400.0, "unit": "kgCO2e"}}}}
    factor = carbon_factor_from_openepd(_with(impacts=impacts), material="AA-6061-T6")
    assert (factor.band_low, factor.band_high) == (1.0, 1.0)
    assert factor.source.endswith("no uncertainty declared")


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"doctype": "industryEPD"}, "not 'openEPD'"),
        ({"impacts": None}, "states no impacts"),
        (
            {"impacts": {"TRACI 2.1": {"gwp": {"A1": {"mean": 1.0, "unit": "kgCO2e"}}}}},
            "no A1A2A3",
        ),
        (
            {"impacts": {"TRACI 2.1": {"gwp": {"A1A2A3": {"mean": 8.4, "unit": "tCO2e"}}}}},
            "stated in 'tCO2e'",
        ),
        (
            {"impacts": {"TRACI 2.1": {"gwp": {"A1A2A3": {"mean": -1, "unit": "kgCO2e"}}}}},
            "positive number",
        ),
        ({"id": None, "product_name": None}, "neither an id nor a product"),
    ],
)
def test_what_the_conversion_would_have_to_guess_is_refused(change, match):
    with pytest.raises(ValueError, match=match):
        carbon_factor_from_openepd(_with(**change), material="AA-6061-T6")


def test_two_impact_methods_are_two_answers_and_the_caller_picks():
    both = {
        "TRACI 2.1": _EPD["impacts"]["TRACI 2.1"],
        "EF 3.0": {"gwp": {"A1A2A3": {"mean": 8600.0, "unit": "kgCO2e"}}},
    }
    with pytest.raises(ValueError, match=r"2 impact methods \(EF 3.0, TRACI 2.1\)"):
        carbon_factor_from_openepd(_with(impacts=both), material="AA-6061-T6")
    chosen = carbon_factor_from_openepd(_with(impacts=both), material="x", method="EF 3.0")
    assert chosen.value == pytest.approx(8.6)
    with pytest.raises(ValueError, match="no GWP under 'CML'"):
        carbon_factor_from_openepd(_with(impacts=both), material="x", method="CML")


def test_an_expired_declaration_is_refused_only_against_a_stated_date():
    carbon_factor_from_openepd(json.dumps(_EPD), material="x")  # nothing reads the clock
    carbon_factor_from_openepd(json.dumps(_EPD), material="x", as_of="2030-06-30")
    with pytest.raises(ValueError, match="valid until 2030-06-30, before 2031-01-01"):
        carbon_factor_from_openepd(json.dumps(_EPD), material="x", as_of="2031-01-01")


@pytest.mark.parametrize("document", ["not json", "[1, 2]", b'{"doctype": "openEPD"}', 1.0, "﻿{"])
def test_a_document_that_is_not_an_openepd_object_is_a_value_error(document):
    with pytest.raises(ValueError):
        carbon_factor_from_openepd(document, material="x")


@pytest.mark.parametrize("poison", ["NaN", "Infinity", "-Infinity"])
def test_a_non_finite_number_inside_the_declaration_is_refused(poison):
    # The front-door probes poison the arguments, and every argument here is text, so the
    # numbers they cannot reach are the ones inside it. Python's JSON reader accepts all
    # three spellings.
    gwp = f'{{"A1A2A3": {{"mean": {poison}, "unit": "kgCO2e"}}}}'
    text = json.dumps(_EPD).replace(json.dumps(_EPD["impacts"]["TRACI 2.1"]["gwp"]), gwp)
    assert poison in text
    with pytest.raises(ValueError, match="positive number"):
        carbon_factor_from_openepd(text, material="x")
    mass = json.dumps(_EPD).replace('{"qty": 1, "unit": "t"}', f'{{"qty": {poison}, "unit": "t"}}')
    with pytest.raises(ValueError, match="declared unit must be a finite quantity"):
        carbon_factor_from_openepd(mass, material="x")


def _generic(material: str, value: float):  # type: ignore[no-untyped-def]
    from anvilate.analysis import CarbonFactor

    return CarbonFactor(
        material=material,
        value=value,
        scope=ModuleScope.A1_A3,
        source="a generic table the caller cites",
        band_low=0.8,
        band_high=1.4,
    )


def test_a_declaration_is_bound_over_the_generic_factor_for_its_material():
    from anvilate.analysis import with_declared_factors

    generic = {"AA-6061-T6": _generic("AA-6061-T6", 12.0), "ASTM-A36": _generic("ASTM-A36", 1.9)}
    declared = carbon_factor_from_openepd(json.dumps(_EPD), material="AA-6061-T6")
    concrete = carbon_factor_from_openepd(
        _with(
            declared_unit={"qty": 1, "unit": "m**3"},
            kg_per_declared_unit={"qty": 2400, "unit": "kg"},
        ),
        material="C30 concrete",
    )
    bound = with_declared_factors(generic, [declared, concrete])
    assert bound["AA-6061-T6"] is declared  # the product's own figure wins
    assert bound["ASTM-A36"] is generic["ASTM-A36"]  # untouched where nothing is declared
    assert bound["C30 concrete"] is concrete  # and a material with no generic factor gains one
    assert generic["AA-6061-T6"].value == 12.0 and "C30 concrete" not in generic


def test_two_declarations_for_one_material_are_the_users_choice_not_ours():
    from anvilate.analysis import with_declared_factors

    one = carbon_factor_from_openepd(json.dumps(_EPD), material="AA-6061-T6")
    other = carbon_factor_from_openepd(_with(id="ec3other"), material="AA-6061-T6")
    with pytest.raises(ValueError, match="two declarations are bound to AA-6061-T6"):
        with_declared_factors({}, [one, other])
    with pytest.raises(ValueError, match="names no declaration"):
        with_declared_factors({}, [_generic("AA-6061-T6", 12.0)])
