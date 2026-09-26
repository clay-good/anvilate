"""The timber pack: a sawn-lumber beam screened by NDS against declared reference values."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from anvilate.packs.timber import TimberBeam, screen_timber_beam
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
