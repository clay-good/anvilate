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


# Two real cases at the same pinned revision, one from each side of the census: a timber
# assembly and a single-part PLA print. Fetched rather than vendored, like the index.
_REAL_CASES = (
    (
        "bookshelf",
        "0959cb0af9d1d269afaa546e06987144522c39e7cb0b07cb7d64d75bd1a7dcc3",
        "an assembly of 44 parts",
    ),
    (
        "vase_teardrop",
        "400cad236d7c5a194e8b42658ac334237103f3f4d60ba00103611acc5df40fda",
        "the material 'PLA' has no record",
    ),
)


@pytest.mark.parametrize("case_id,digest,expected_reason", _REAL_CASES)
def test_the_parser_reads_the_suites_own_prose_not_only_this_files(
    case_id, digest, expected_reason, tmp_path
):
    """The antidote to a fixture agreeing with the parser that was written beside it.

    Every other test here writes its case in the suite's format from memory of the
    format. This one reads two real ones — a timber assembly and a single-part PLA print,
    one from each side of the census — and asserts the verdict each earns. Opt-in and run
    by the scheduled job, like the index check above.
    """
    if not os.environ.get("ANVILATE_ALLOW_NETWORK"):
        pytest.skip("set ANVILATE_ALLOW_NETWORK=1 to fetch real suite cases")

    from anvilate.fetch import DatasetRecipe
    from anvilate.standards import default_materials_db

    recipe = DatasetRecipe(
        name=f"muse-{case_id}.md",
        url=(
            "https://huggingface.co/datasets/dongxiaoyu/MUSE/resolve/"
            f"f8a1dc45d1ea73df4161e8a1caf1d503c5358c30/cases/{case_id}/design_description.md"
        ),
        sha256=digest,
        license="CC-BY-4.0",
        source=f"MUSE case {case_id}",
        redistributable=False,
    )
    path, _provenance = fetch_dataset(
        recipe, retrieved="2026-08-27", consent=True, cache_dir=tmp_path
    )
    case = parse_case_specification(case_id, path.read_text(encoding="utf-8"))
    verdict = scope_verdict(
        case, known_materials=frozenset(default_materials_db().known_materials())
    )
    assert verdict.in_scope is False
    assert expected_reason in verdict.reason


# --- the page that documents this module --------------------------------------------------


def _benchmark_page() -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parent.parent / "docs" / "agent-driving-evals.md").read_text(
        encoding="utf-8"
    )


def test_the_page_quotes_the_reasons_the_module_produces():
    """`anvilate.specbench` shipped and appeared on no page. The three refusals the page
    describes are its own output, so they are read off the page and reproduced."""
    page = _benchmark_page()
    case = parse_case_specification("demo-1", _case())

    material = scope_verdict(case, known_materials=frozenset({"AA-6061-T6"}))
    assert not material.in_scope
    assert material.reason in page, material.reason

    assembly = scope_verdict(
        parse_case_specification("demo-2", _case(quantity="7")),
        known_materials=frozenset({"ASTM-A36"}),
    )
    assert not assembly.in_scope
    assert assembly.reason in page, assembly.reason

    accepted = scope_verdict(case, known_materials=frozenset({"ASTM-A36"}))
    assert accepted.in_scope and accepted.reason == ""


def test_part_count_binds_before_material_as_the_page_says():
    """ "A 44-part PLA bookshelf is not a materials problem" — a case failing both must be
    reported as the assembly, or adding the material would look like the fix."""
    verdict = scope_verdict(
        parse_case_specification("demo-3", _case(quantity="44")),
        known_materials=frozenset({"AA-6061-T6"}),
    )
    assert "assembly" in verdict.reason and "material" not in verdict.reason
    assert "binds before material" in _benchmark_page()


def test_the_accounting_the_page_describes_is_derived_from_the_verdicts():
    page = _benchmark_page()
    assert "suite_accounting" in page
    case = parse_case_specification("demo-1", _case())
    verdicts = [
        scope_verdict(case, known_materials=frozenset({"ASTM-A36"})),
        scope_verdict(case, known_materials=frozenset({"AA-6061-T6"})),
    ]
    accounting = suite_accounting(verdicts)
    assert (accounting.total, accounting.in_scope, accounting.out_of_scope) == (2, 1, 1)
    # `reasons` is a tuple of (reason, count) pairs, not a mapping — an ordered census
    # rather than something a caller can reorder into a different-looking report.
    assert sum(count for _reason, count in accounting.reasons) == accounting.out_of_scope
    assert all(reason.strip() for reason, _count in accounting.reasons)
