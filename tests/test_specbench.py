"""Reading an external suite's cases, and refusing the ones nothing could compile.

Every case in this file is written here, in the suite's format, rather than taken from
the suite: the data is fetched and not bundled, and a test does not need somebody else's
copyright to prove a parser. The one test that touches the real index is opt-in and run
by the scheduled job.
"""

from __future__ import annotations

import hashlib
import json
import os
import textwrap

import pytest

from anvilate.fetch import fetch_dataset
from anvilate.specbench import (
    MUSE_CASE_INDEX,
    CaseSpecification,
    ScopeVerdict,
    parse_case_specification,
    scope_verdict,
    suite_accounting,
)

_KNOWN = frozenset({"ASTM-A36", "AA-6061-T6"})


def _case(**overrides) -> str:
    fields = {
        "goal": "A lifting padeye.",
        "geometry": "Approx. 80.0 mm x 12.0 mm x 120.0 mm.",
        "material": "ASTM-A36",
        "method": "CNC Milling",
        "joint": "Bolting",
        "condition": "Static lift, 50 kN.",
        "features": "One plate with a pin hole.",
        "requirements": "Keep the hole concentric.",
        "quantity": "1",
        "names": "- padeye",
    }
    fields.update(overrides)
    return textwrap.dedent(
        f"""\
        # Design Specification

        ## Design Goal
        {fields["goal"]}

        ## Geometry and Dimensions
        {fields["geometry"]}

        ## Material
        {fields["material"]}

        ## Manufacturing Method
        {fields["method"]}

        ## Connection Method (Joint Type)
        {fields["joint"]}

        ## Mechanical Condition
        {fields["condition"]}

        ## Structural Features
        {fields["features"]}

        ## Special Requirements
        {fields["requirements"]}

        ## Planned Component Quantity
        {fields["quantity"]}

        ## Component Names
        {fields["names"]}
        """
    )


def test_a_case_reads_into_the_suites_own_vocabulary():
    case = parse_case_specification("padeye", _case())
    assert case.material == "ASTM-A36"
    assert case.manufacturing_method == "CNC Milling"
    assert case.component_count == 1
    assert case.component_names == ("padeye",)
    # The fields are what the case says, not what Anvilate would do with it.
    assert case.mechanical_condition.startswith("Static lift")


def test_a_document_missing_a_heading_the_format_guarantees_is_refused():
    without_material = _case().replace("## Material\nASTM-A36\n\n", "")
    with pytest.raises(ValueError, match=r"missing the heading\(s\) \['Material'\]"):
        parse_case_specification("padeye", without_material)


def test_a_component_quantity_with_no_number_in_it_is_refused():
    with pytest.raises(ValueError, match="no number in it"):
        parse_case_specification("padeye", _case(quantity="several"))


def test_a_quantity_written_with_a_word_beside_it_still_reads():
    # "44 parts" and "1 (single piece)" both occur in the wild; the count is the number.
    assert parse_case_specification("shelf", _case(quantity="44 parts")).component_count == 44


def test_a_case_whose_material_the_database_carries_is_in_scope():
    verdict = scope_verdict(parse_case_specification("padeye", _case()), known_materials=_KNOWN)
    assert verdict.in_scope is True
    assert verdict.reason == ""


def test_an_assembly_is_out_of_scope_by_construction_and_says_so():
    case = parse_case_specification("bookshelf", _case(quantity="44", names="- upright"))
    verdict = scope_verdict(case, known_materials=_KNOWN)
    assert verdict.in_scope is False
    assert "44 parts" in verdict.reason
    assert "one part" in verdict.reason


def test_a_material_with_no_record_is_refused_rather_than_screened_on_a_guess():
    case = parse_case_specification("vase", _case(material="PLA"))
    verdict = scope_verdict(case, known_materials=_KNOWN)
    assert verdict.in_scope is False
    assert "'PLA'" in verdict.reason
    assert "no record" in verdict.reason


def test_the_part_count_binds_before_the_material():
    """Both refusals can apply; the reported one is the structural one.

    A 44-part PLA bookshelf is not "a materials problem" — adding PLA to the database
    would not make it expressible, and an accounting that said so would point the next
    piece of work at the wrong thing.
    """
    case = parse_case_specification("shelf", _case(quantity="44", material="PLA"))
    assert "assembly" in scope_verdict(case, known_materials=_KNOWN).reason


def test_a_refusal_without_a_reason_cannot_be_constructed():
    with pytest.raises(ValueError, match="say what could not be expressed"):
        ScopeVerdict(case_id="x", in_scope=False)
    with pytest.raises(ValueError, match="was not refused"):
        ScopeVerdict(case_id="x", in_scope=True, reason="but here is a reason")


def test_a_case_with_no_parts_at_all_is_not_a_case():
    with pytest.raises(ValueError, match="no parts"):
        CaseSpecification(
            case_id="x",
            design_goal="g",
            geometry="g",
            material="m",
            manufacturing_method="m",
            joint_type="j",
            mechanical_condition="c",
            structural_features="f",
            special_requirements="r",
            component_count=0,
            component_names=(),
        )


def test_the_accounting_is_the_count_and_the_reason():
    verdicts = [
        scope_verdict(parse_case_specification("padeye", _case()), known_materials=_KNOWN),
        scope_verdict(
            parse_case_specification("vase", _case(material="PLA")), known_materials=_KNOWN
        ),
        scope_verdict(
            parse_case_specification("pen_holder", _case(material="PLA")),
            known_materials=_KNOWN,
        ),
        scope_verdict(
            parse_case_specification("shelf", _case(quantity="44")), known_materials=_KNOWN
        ),
    ]
    accounting = suite_accounting(verdicts)
    assert (accounting.total, accounting.in_scope, accounting.out_of_scope) == (4, 1, 3)
    # Ordered by how many cases each reason accounts for, so the binding constraint reads
    # first — which is the whole point of publishing the reason rather than a percentage.
    assert accounting.reasons[0][1] == 2
    assert "'PLA'" in accounting.reasons[0][0]
    assert sum(count for _reason, count in accounting.reasons) == accounting.out_of_scope


def test_the_muse_index_recipe_names_a_pinned_revision_not_a_moving_branch():
    """A benchmark with a leaderboard moves; a published score has to name its version."""
    assert "/resolve/main/" not in MUSE_CASE_INDEX.url
    assert MUSE_CASE_INDEX.redistributable is False
    assert MUSE_CASE_INDEX.license == "CC-BY-4.0"


def test_the_real_index_is_the_106_cases_the_review_counted(tmp_path):
    """The suite itself, opt-in and fetched — the check that the recipe still holds.

    Skipped without the network, run by name in the scheduled job. It is deliberately a
    check of the *index*: the digest proves the bytes, and the count is the number the
    licence review's census was taken over.
    """
    if not os.environ.get("ANVILATE_ALLOW_NETWORK"):
        pytest.skip("set ANVILATE_ALLOW_NETWORK=1 to fetch the real suite index")

    path, provenance = fetch_dataset(
        MUSE_CASE_INDEX, retrieved="2026-08-27", consent=True, cache_dir=tmp_path
    )
    payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == MUSE_CASE_INDEX.sha256
    assert provenance.license == "CC-BY-4.0"

    cases = [json.loads(line) for line in payload.decode().splitlines() if line.strip()]
    assert len(cases) == 106
    assert {"case_id", "design_description", "evaluation_rubric"} <= set(cases[0])
