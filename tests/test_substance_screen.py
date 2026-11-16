"""Substance screening: each item's declared composition against the lists you hold.

The spec's scenario: a fitting's brass declares 2.5% lead, and RoHS Annex II limits lead
to 0.1% of a homogeneous material. The fitting fails, naming the list version; an
exemption counts only when it is declared with its reference.
"""

from __future__ import annotations

import hashlib

import pytest

from anvilate.compliance import (
    Exemption,
    SubstanceList,
    load_substance_list,
    screen_substances,
)
from anvilate.product import parse_product
from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus

LEAD, CADMIUM, COPPER, ZINC = "7439-92-1", "7440-43-9", "7440-50-8", "7440-66-6"

_ROHS = f"""cas,name,threshold
{LEAD},lead,0.001
{CADMIUM},cadmium,0.0001
"""


def _box(kg: float) -> dict:
    return {"envelope": [{"magnitude": v, "unit": "mm"} for v in (40, 40, 20)],
            "mass": {"magnitude": kg, "unit": "kg"}, "reason": "not yet detailed"}  # fmt: skip


def _seat(part: str, on: str) -> list[dict]:
    return [
        {"id": f"{part}-sit", "kind": "face_to_face", "place": {"part": part, "face": "bottom"},
         "on": {"part": on, "face": "top"}},
        {"id": f"{part}-left", "kind": "edge_flush", "place": {"part": part, "face": "left"},
         "on": {"part": on, "face": "left"}},
        {"id": f"{part}-front", "kind": "edge_flush", "place": {"part": part, "face": "front"},
         "on": {"part": on, "face": "front"}},
    ]  # fmt: skip


def _valve(lead: float = 0.025, plate_composition: bool = True) -> object:
    fitting = {"id": "fitting", "identity": {"description": "fitting", "source": "make"},
               "placeholder": _box(0.2), "material": "CW617N"}  # fmt: skip
    plate = {"id": "plate", "identity": {"description": "plate", "source": "make"},
             "placeholder": _box(1.0), "material": "S235"}  # fmt: skip
    brass = {"material": "CW617N",
             "composition": [{"cas": COPPER, "name": "copper", "fraction": 0.58},
                             {"cas": LEAD, "name": "lead", "fraction": lead},
                             {"cas": ZINC, "name": "zinc", "fraction": 0.395}],
             "composition_source": "mill certificate 4471"}  # fmt: skip
    steel = {"material": "S235"}
    if plate_composition:
        iron = {"cas": "7439-89-6", "name": "iron", "fraction": 0.98}
        steel = {"material": "S235", "composition_source": "EN 10025-2 heat analysis",
                 "composition": [iron]}  # fmt: skip
    return parse_product({
        "name": "valve", "definitions": [plate, fitting],
        "instances": [{"name": "plate", "item": "plate"}, {"name": "fitting", "item": "fitting"}],
        "ground": "plate", "mates": _seat("fitting", "plate"),
        "screening": {"materials": [brass, steel]},
    })  # fmt: skip


@pytest.fixture
def rohs(tmp_path) -> SubstanceList:
    path = tmp_path / "rohs-annex-ii.csv"
    path.write_text(_ROHS)
    return load_substance_list(path, name="RoHS Annex II", version="2015/863",
                               basis="homogeneous material",
                               source="Directive 2011/65/EU Annex II as amended")  # fmt: skip


def _entries(product, lists, **kw) -> dict:
    return {e.name: e for e in screen_substances(product, lists, **kw)}


def test_a_lead_bearing_brass_fails_naming_the_concentration_threshold_and_list(rohs):
    entry = _entries(_valve(), [rohs])["fitting RoHS Annex II"]
    assert entry.status is CheckStatus.FAIL
    assert "lead (CAS 7439-92-1) at 2.5000% of the homogeneous material" in entry.detail
    assert "threshold 0.1000%" in entry.detail
    assert f"RoHS Annex II 2015/863 (sha256 {rohs.sha256[:12]})" in entry.detail
    assert "mill certificate 4471" in entry.detail


def test_an_exemption_counts_only_declared_with_its_reference_and_for_its_items(rohs):
    reference = "RoHS Annex III 6(c), copper alloy up to 4% lead"
    covering = Exemption(list="RoHS Annex II", cas=LEAD, reference=reference)
    entry = _entries(_valve(), [rohs], exemptions=[covering])["fitting RoHS Annex II"]
    assert entry.status is CheckStatus.PASS
    assert f"exempt under {reference}" in entry.detail
    elsewhere = Exemption(list="RoHS Annex II", cas=LEAD, items=("plate",), reference=reference)
    entry = _entries(_valve(), [rohs], exemptions=[elsewhere])["fitting RoHS Annex II"]
    assert entry.status is CheckStatus.FAIL
    other_substance = Exemption(list="RoHS Annex II", cas=CADMIUM, reference=reference)
    entry = _entries(_valve(), [rohs], exemptions=[other_substance])["fitting RoHS Annex II"]
    assert entry.status is CheckStatus.FAIL


def test_the_threshold_itself_passes_and_one_part_in_a_million_above_fails(rohs):
    at = _entries(_valve(lead=0.001), [rohs])["fitting RoHS Annex II"]
    assert at.status is CheckStatus.PASS
    assert "at or below its threshold" in at.detail
    above = _entries(_valve(lead=0.001001), [rohs])["fitting RoHS Annex II"]
    assert above.status is CheckStatus.FAIL


def test_a_material_with_no_composition_is_not_evaluated_naming_it(rohs):
    entry = _entries(_valve(plate_composition=False), [rohs])["plate RoHS Annex II"]
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert entry.needs[0].declaration == "screening.materials[S235].composition"


def test_a_clean_material_passes_saying_how_much_it_was_held_against(rohs):
    entry = _entries(_valve(), [rohs])["plate RoHS Annex II"]
    assert entry.status is CheckStatus.PASS
    assert "none of its 1 declared substances is among the 2 listed" in entry.detail


def test_each_list_is_its_own_entry_with_its_own_basis(rohs, tmp_path):
    path = tmp_path / "candidate.csv"
    path.write_text(f"cas,name,threshold\n{LEAD},lead,0.001\n")
    reach = load_substance_list(path, name="REACH candidate list", version="2026-06-25",
                                basis="article", source="ECHA candidate list")  # fmt: skip
    entries = _entries(_valve(), [rohs, reach])
    assert len(entries) == 4
    assert "of the article" in entries["fitting REACH candidate list"].detail


def test_the_list_hash_is_the_files_own(rohs, tmp_path):
    assert rohs.sha256 == hashlib.sha256(_ROHS.encode()).hexdigest()


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("cas,name\n7439-92-1,lead\n", "no threshold column"),
        ("cas,name,threshold\n7439-92-1,lead,a tenth\n", "line 2: threshold"),
        ("cas,name,threshold\n7439-92-2,lead,0.001\n", "fails its check digit"),
        ("cas,name,threshold\n7439-92-1,lead,0.001\n7439-92-1,lead,0.002\n", "more than once"),
    ],
)
def test_a_malformed_list_is_refused_where_it_is_wrong(tmp_path, text, said):
    path = tmp_path / "list.csv"
    path.write_text(text)
    with pytest.raises(RefusalError, match=said):
        load_substance_list(path, name="x", version="1", basis="article", source="a test")


def test_a_mistyped_cas_number_in_a_composition_is_refused():
    with pytest.raises(RefusalError, match="fails its check digit"):
        parse_product({
            "name": "p", "definitions": [{"id": "a", "identity": {"description": "a",
                                          "source": "make"}, "placeholder": _box(1.0),
                                          "material": "m"}],
            "instances": [{"name": "a", "item": "a"}], "ground": "a",
            "screening": {"materials": [{"material": "m", "composition_source": "a sheet",
                                         "composition": [{"cas": "7439-92-2", "name": "lead",
                                                          "fraction": 0.1}]}]},
        })  # fmt: skip


def test_an_exemption_off_the_lists_or_off_the_product_is_refused(rohs):
    with pytest.raises(RefusalError, match="not among the lists screened"):
        screen_substances(_valve(), [rohs], exemptions=[
            Exemption(list="REACH", cas=LEAD, reference="a ruling")])  # fmt: skip
    with pytest.raises(RefusalError, match="not items of"):
        stray = Exemption(list="RoHS Annex II", cas=LEAD, items=("pump",), reference="a ruling")
        screen_substances(_valve(), [rohs], exemptions=[stray])
    with pytest.raises(RefusalError, match="more than once"):
        screen_substances(_valve(), [rohs, rohs])
    with pytest.raises(RefusalError, match="lists"):
        screen_substances(_valve(), rohs)  # type: ignore[arg-type]
