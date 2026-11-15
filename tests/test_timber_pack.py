"""The timber pack: a sawn-lumber beam screened by NDS against declared reference values."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from anvilate.packs.timber import (
    TimberBeam,
    TimberConnection,
    screen_timber_beam,
    screen_timber_connection,
)
from anvilate.scorecard import CheckStatus


def _value(prop: str, magnitude: float, unit: str = "psi") -> dict:
    return {
        "standard": "NDS",
        "edition": "2018",
        "table": "Supplement Table 4A",
        "species": "Douglas Fir-Larch",
        "grade": "No. 2",
        "size_classification": "dimension lumber",
        "property": prop,
        "value": {"magnitude": magnitude, "unit": unit},
    }


# A 2x10 Douglas Fir-Larch No. 2 joist, 12 ft, 80 plf: the worked example in the numbers below.
_JOIST = {
    "name": "joist",
    "width": {"magnitude": 1.5, "unit": "inch"},
    "depth": {"magnitude": 9.25, "unit": "inch"},
    "span": {"magnitude": 12.0, "unit": "ft"},
    "load": {"magnitude": 80.0, "unit": "lbf/ft"},
    "bending": _value("F_b", 900.0),
    "shear": _value("F_v", 180.0),
    "modulus": _value("E", 1_600_000.0),
    "bending_factors": {"C_D": 1.0, "C_F": 1.1},
    "shear_factors": {"C_D": 1.0},
    "deflection_limit": {"magnitude": 0.4, "unit": "inch"},
}


def _screen(**changes: object) -> dict:
    document = copy.deepcopy(_JOIST)
    document.update(changes)
    card = screen_timber_beam(TimberBeam.model_validate(document))
    return {entry.name: entry for entry in card.entries}


def test_a_joist_is_screened_by_hand_worked_nds_numbers() -> None:
    entries = _screen()
    # M = w·L²/8 = 80 x 12²/8 = 1,440 lb·ft = 17,280 lb·in; S = 1.5 x 9.25²/6 = 21.39 in³;
    # f_b = 807.9 psi against F'_b = 900 x 1.1 = 990 psi.
    section_modulus = 1.5 * 9.25**2 / 6
    assert entries["joist bending"].safety_factor == pytest.approx(
        990 / (17_280 / section_modulus), rel=1e-6
    )
    # V = w·L/2 = 480 lb; f_v = 1.5 x 480/(1.5 x 9.25) = 51.9 psi against 180 psi.
    assert entries["joist shear"].safety_factor == pytest.approx(
        180 / (1.5 * 480 / (1.5 * 9.25)), rel=1e-6
    )
    # Δ = 5·w·L⁴/(384·E·I), w = 80/12 lb/in, L = 144 in, I = 1.5 x 9.25³/12.
    deflection = 5 * (80 / 12) * 144**4 / (384 * 1.6e6 * 1.5 * 9.25**3 / 12)
    assert deflection == pytest.approx(0.2358, abs=1e-4)
    assert f"deflection {deflection * 25.4:.3f} mm" in entries["joist deflection"].detail
    assert "short-term" in entries["joist deflection"].detail
    for entry in entries.values():
        assert entry.status is CheckStatus.PASS
        assert "Douglas Fir-Larch No. 2" in entry.detail


def test_creep_multiplies_the_sustained_part_of_the_deflection() -> None:
    """NDS §3.5.2: Δ_T = K_cr·Δ_LT + Δ_ST, so half the load sustained at K_cr = 1.5 is a
    deflection 1.25 times the short-term one, and the check then addresses creep."""
    short = _screen()["joist deflection"]
    creep = _screen(sustained_load={"magnitude": 40.0, "unit": "lbf/ft"}, creep_factor=1.5)[
        "joist deflection"
    ]
    assert creep.addresses == ("timber creep under sustained load",)
    assert short.addresses == ()
    short_mm = float(short.detail.split("deflection ")[1].split(" mm")[0])
    creep_mm = float(creep.detail.split("deflection ")[1].split(" mm")[0])
    assert creep_mm == pytest.approx(1.25 * short_mm, rel=1e-3)
    with pytest.raises(ValidationError, match="declared together"):
        _screen(sustained_load={"magnitude": 40.0, "unit": "lbf/ft"})
    with pytest.raises(ValidationError, match="cannot exceed it"):
        _screen(sustained_load={"magnitude": 90.0, "unit": "lbf/ft"}, creep_factor=1.5)


def test_a_factor_nds_does_not_apply_is_refused_by_the_field_that_carries_it() -> None:
    """C_D on a modulus makes the beam stiffer than the standard allows, on the check that
    usually governs a timber beam."""
    with pytest.raises(ValidationError, match="modulus_factors: NDS Table 4.3.1 does not apply"):
        _screen(modulus_factors={"C_D": 1.15})
    with pytest.raises(ValidationError, match="shear_factors: NDS Table 4.3.1 does not apply"):
        _screen(shear_factors={"C_F": 1.1})
    with pytest.raises(ValidationError, match="bending must be the F_b reference value"):
        _screen(bending=_value("F_v", 180.0))


def test_a_deflection_limit_without_a_modulus_names_it() -> None:
    entries = _screen(modulus=None)
    deflection = entries["joist deflection"]
    assert deflection.status is CheckStatus.NOT_EVALUATED
    assert [need.declaration for need in deflection.needs] == ["element_params.modulus"]


def test_a_failing_beam_is_told_the_depth_that_passes() -> None:
    """screen_timber_beam's depth lever: f_b goes as 1/d², so d·√(1/SF) passes in one step."""
    heavy = {"magnitude": 200.0, "unit": "lbf/ft"}
    document = {**copy.deepcopy(_JOIST), "load": heavy}
    card = screen_timber_beam(TimberBeam.model_validate(document))
    bending = next(entry for entry in card.entries if entry.name == "joist bending")
    assert bending.status is CheckStatus.FAIL
    hint = bending.repair_hint
    assert hint is not None and hint.parameter == "depth"
    repaired = _screen(load=heavy, depth={"magnitude": hint.corrective_value, "unit": "mm"})
    assert repaired["joist bending"].status is CheckStatus.PASS
    assert repaired["joist bending"].safety_factor == pytest.approx(1.0, rel=1e-6)


def _joist_spec(material: str) -> str:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "examples" / "timber_joist.spec.yaml").read_text()
    assert "material: {ref: Douglas Fir-Larch No. 2}" in text
    return text.replace("Douglas Fir-Larch No. 2}", f"{material}}}", 1)


def test_a_timber_document_names_its_wood_and_the_records_resolve_it() -> None:
    """No bundled table carries wood, so every timber document failed material resolution
    or named a metal. The element's own NDS records are the material now: the document's
    `material.ref` must be the species and grade they are for."""
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    card = screen_spec(load_spec_yaml(_joist_spec("Douglas Fir-Larch No. 2")))
    assert card.status is CheckStatus.PASS
    resolution = next(e for e in card.entries if e.name == "material resolution")
    assert "from those records rather than the materials database" in resolution.detail
    # A real database identifier is still the wrong material for a wood joist.
    card = screen_spec(load_spec_yaml(_joist_spec("ASTM-A36")))
    resolution = next(e for e in card.entries if e.name == "material resolution")
    assert resolution.status is CheckStatus.FAIL
    assert "'ASTM-A36'" in resolution.detail and "'Douglas Fir-Larch No. 2'" in resolution.detail


def test_compile_spec_resolves_a_timber_material_the_same_way() -> None:
    import yaml

    from anvilate.mcp import handle_request

    def compiled(material: str) -> dict:
        document = yaml.safe_load(_joist_spec(material))
        reply = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "compile_spec", "arguments": {"document": document}},
            }
        )
        return reply["result"]["structuredContent"]

    assert compiled("Douglas Fir-Larch No. 2")["errors"] == []
    refused = compiled("ASTM-A36")
    assert refused["remedies"] == ["write `material.ref` as `Douglas Fir-Larch No. 2`"]


def test_the_records_describe_one_piece_of_wood() -> None:
    other = {**_value("F_v", 180.0), "species": "Southern Pine"}
    with pytest.raises(ValidationError, match="describe one piece of wood"):
        _screen(shear=other)


def test_the_support_bearing_derives_its_own_area_factor() -> None:
    """R = 480 lb over a 1.5 x 1.5 in bearing is 213.3 psi across the grain; C_b =
    (1.5 + 0.375)/1.5 = 1.25 lifts F_c_perp = 625 psi to 781.25 psi."""
    bearing = {
        "bearing_length": {"magnitude": 1.5, "unit": "inch"},
        "compression_perpendicular": _value("F_c_perp", 625.0),
    }
    entry = _screen(**bearing)["joist bearing"]
    assert entry.safety_factor == pytest.approx(781.25 / (480 / 1.5**2), rel=1e-6)
    # Three inches from the member end or nearer, the fibre past the bearing is not there.
    near_end = _screen(**bearing, bearing_end_distance={"magnitude": 2.0, "unit": "inch"})
    assert near_end["joist bearing"].safety_factor == pytest.approx(625 / (480 / 1.5**2))
    with pytest.raises(ValidationError, match="C_b is derived"):
        _screen(**bearing, compression_perpendicular_factors={"C_b": 1.25})
    with pytest.raises(ValidationError, match="declared together"):
        _screen(bearing_length={"magnitude": 1.5, "unit": "inch"})


@pytest.mark.parametrize(
    "changes,subject,source",
    (
        (
            {"width": {"magnitude": 1.5, "unit": "MPa"}},
            "width",
            "the timber member drawing or verified section dimensions",
        ),
        (
            {"load": {"magnitude": 80.0, "unit": "MPa"}},
            "load",
            "the governing load combination and timber member demand analysis",
        ),
        (
            {"bending": _value("F_v", 180.0)},
            "bending",
            "the beam's cited NDS reference-value records",
        ),
        (
            {"modulus_factors": {"C_D": 1.15}},
            "modulus_factors",
            "the governing NDS edition and selected design conditions",
        ),
        (
            {"modulus": None, "modulus_factors": {"C_M": 1.0}},
            "modulus_factors",
            "the timber beam declaration and supporting design records",
        ),
    ),
)
def test_timber_pack_refusals_carry_structured_remedies(changes, subject, source):
    from anvilate.refusal import RefusalError

    with pytest.raises(ValidationError) as refused:
        _screen(**changes)

    error = refused.value.errors()[0]["ctx"]["error"]
    assert isinstance(error, RefusalError)
    assert error.remedies[0].model_dump() == {
        "action": "replace",
        "subject": subject,
        "source": source,
    }


def test_every_timber_pack_refusal_site_is_structured():
    import ast
    import pathlib

    from conftest import parsed_source

    path = pathlib.Path(__file__).parents[1] / "src/anvilate/packs/timber.py"
    structured = []
    unstructured = []
    for node in ast.walk(parsed_source(path)):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "_timber_pack_refusal":
            structured.append(node.exc)
        if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "ValueError":
            unstructured.append(node.exc)

    assert len(structured) == 21
    assert unstructured == []
    for call in structured:
        assert {"subject", "source"} <= {keyword.arg for keyword in call.keywords}, call.lineno


# --- The dowel-connection screen ------------------------------------------------------
#
# A 1/2 in bolt in single shear with a 0.6 in main member and a 2 in side member. The
# geometry is chosen, not typical: it is the case where the mode with the smallest
# unreduced value P is NOT the mode with the smallest design value Z, because the
# reduction terms differ (4.0 for the bearing modes, 3.2 for the hinge ones).

_THIN_MAIN = {
    "diameter": {"magnitude": 0.5, "unit": "inch"},
    "bending_yield_strength": {"magnitude": 45000.0, "unit": "psi"},
    "main_bearing_length": {"magnitude": 0.6, "unit": "inch"},
    "side_bearing_length": {"magnitude": 2.0, "unit": "inch"},
    "main_bearing_strength": {"magnitude": 5600.0, "unit": "psi"},
    "side_bearing_strength": {"magnitude": 5600.0, "unit": "psi"},
}
#: NDS Table 12.3.1B at an angle to grain of zero, which the caller cites.
_REDUCTION_TERMS = {"Im": 4.0, "Is": 4.0, "II": 3.6, "IIIm": 3.2, "IIIs": 3.2, "IV": 3.2}


def _connection(**kwargs) -> TimberConnection:
    defaults = {
        "name": "chord splice",
        "edition": "2018",
        "connection": copy.deepcopy(_THIN_MAIN),
        "reduction_terms": dict(_REDUCTION_TERMS),
        "demand": {"magnitude": 1000.0, "unit": "lbf"},
    }
    return TimberConnection.model_validate({**defaults, **kwargs})


def test_the_design_value_governs_on_a_different_mode_than_the_unreduced_one():
    """The reason the screen divides every mode and not just the smallest.

    P and Z do not rank the modes the same way, because NDS gives the bearing modes a
    reduction term of 4.0 and the hinge modes 3.2. Here mode IIIm has the smallest P and
    mode Im the smallest Z, so `P_governing / R_d_governing` returns 506 lbf where the
    reference design value is 420 — a fifth too much, from a step that looks right.
    """
    from anvilate.analysis import dowel_yield_capacity
    from anvilate.analysis.dowel_yield import DowelConnection

    yielded = dowel_yield_capacity(DowelConnection.model_validate(_THIN_MAIN))
    assert yielded.governing.mode.value == "IIIm"
    reduced = {
        entry.mode.value: entry.capacity.to("lbf").magnitude / _REDUCTION_TERMS[entry.mode.value]
        for entry in yielded.modes
        if entry.capacity is not None
    }
    assert min(reduced, key=lambda mode: reduced[mode]) == "Im"
    assert reduced["Im"] == pytest.approx(420.0, abs=1.0)
    # The wrong step, kept here so the number the screen must not return is written down.
    assert reduced["IIIm"] == pytest.approx(506.0, abs=1.0)

    entry = screen_timber_connection(_connection()).entries[0]
    assert "governs on mode Im" in entry.detail
    assert "mode IIIm governs the unreduced value" in entry.detail
    assert entry.safety_factor == pytest.approx(420.0 / 1000.0, rel=1e-3)


def test_the_screen_multiplies_by_the_chain_and_the_fastener_count():
    plain = screen_timber_connection(_connection()).entries[0].safety_factor
    with_chain = screen_timber_connection(
        _connection(factors={"C_D": 1.6, "C_g": 0.95}, fasteners=4)
    ).entries[0]
    assert with_chain.safety_factor == pytest.approx(plain * 1.6 * 0.95 * 4, rel=1e-9)
    assert "C_D 1.6, C_g 0.95" in with_chain.detail
    assert "4 fastener(s)" in with_chain.detail
    # And a chain with nothing in it says so rather than printing an empty list.
    assert (
        "no adjustment factors declared"
        in screen_timber_connection(_connection()).entries[0].detail
    )


def test_a_mode_with_no_reduction_term_is_not_evaluated_naming_it():
    """A connection screened on some of its modes has been screened on the wrong one as
    often as not, so a missing term is NOT_EVALUATED rather than a capacity."""
    card = screen_timber_connection(_connection(reduction_terms={"Im": 4.0}))
    entry = card.entries[0]
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "Is, II, IIIm, IIIs, IV" in entry.detail
    assert entry.needs and "reduction_terms" in entry.needs[0].declaration


def test_a_double_shear_connection_needs_no_term_for_the_modes_it_cannot_reach():
    """Modes II and IIIm do not apply in double shear, so their terms are not asked for."""
    card = screen_timber_connection(
        _connection(
            connection={**copy.deepcopy(_THIN_MAIN), "shear_planes": "double"},
            reduction_terms={"Im": 4.0, "Is": 4.0, "IIIs": 3.2, "IV": 3.2},
        )
    )
    assert card.entries[0].status is not CheckStatus.NOT_EVALUATED


def test_the_reduction_term_is_recorded_as_a_factor_inside_the_capacity():
    """The check is judged at 1.0, so the conservatism has to be itemized somewhere."""
    entry = screen_timber_connection(_connection()).entries[0]
    assert entry.applied_factors and entry.applied_factors[0].value == 4.0
    assert "Table 12.3.1B" in str(entry.applied_factors[0].authority)


def test_the_connection_refuses_the_chain_its_table_does_not_list():
    for bad, message in (
        ({"C_F": 1.1}, "does not apply"),
        ({"C_D": 2.0}, "caps C_D at 1.6"),
        ({"C_D": 0.0}, "positive and finite"),
    ):
        with pytest.raises(ValidationError, match=message):
            _connection(factors=bad)


def test_the_connection_refuses_a_reduction_term_that_is_not_a_mode():
    with pytest.raises(ValidationError, match="not yield modes"):
        _connection(reduction_terms={"Im": 4.0, "V": 3.2})
    with pytest.raises(ValidationError, match="positive and finite"):
        _connection(reduction_terms={**_REDUCTION_TERMS, "Im": 0.0})


def test_the_demand_is_a_force_and_a_magnitude():
    with pytest.raises(ValidationError, match=r"a \[force\]"):
        _connection(demand={"magnitude": 1000.0, "unit": "psi"})
    # The negative and the non-finite are the base class's, which guards every field.
    with pytest.raises(ValidationError, match="must not be negative"):
        _connection(demand={"magnitude": -1000.0, "unit": "lbf"})
    with pytest.raises(ValidationError, match="finite"):
        _connection(demand={"magnitude": float("nan"), "unit": "lbf"})
    with pytest.raises(ValidationError, match="at least"):
        _connection(fasteners=0)
    # Zero demand is a check with nothing to screen, not one that passed.
    entry = screen_timber_connection(_connection(demand={"magnitude": 0.0, "unit": "lbf"})).entries[
        0
    ]
    assert entry.status is CheckStatus.NOT_EVALUATED


def test_the_edition_is_cited_and_shows_on_the_card():
    with pytest.raises(ValidationError):
        _connection(edition="  ")
    entry = screen_timber_connection(_connection(edition="2024")).entries[0]
    assert "NDS 2024 §12.3" in str(entry.reference)
