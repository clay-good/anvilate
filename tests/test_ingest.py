"""Requirements ingestion: the extraction pass, and the gate it feeds."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.ingest import (
    Bound,
    ConfirmationState,
    DraftSpec,
    ExtractedValue,
    SourceLocation,
    UnparsedLine,
    extract_requirements,
)
from anvilate.units import Quantity

SHEET = """# RFQ 2026-114 — lifting lug
Part number:      LUG-4471
Design load:      50 kN
Rated capacity = 5 t
Service temperature: -20 degC
Bore diameter     25 mm
Finish: black oxide
Quantity: 4
"""


def _draft(text: str = SHEET, **kwargs) -> DraftSpec:
    kwargs.setdefault("document", "rfq-2026-114.txt")
    kwargs.setdefault("informational_fields", ("part number",))
    return extract_requirements(text, **kwargs)


def _location() -> SourceLocation:
    return SourceLocation(document="rfq.txt", line_number=3, excerpt="Design load: 50 kN")


# --- the extraction pass ---------------------------------------------------------------


def test_the_pass_reads_colons_equals_signs_and_column_gaps():
    fields = {v.field: v.quantity for v in _draft().values}
    assert fields["design_load"] == Quantity(magnitude=50.0, unit="kN")  # colon
    assert fields["rated_capacity"] == Quantity(magnitude=5.0, unit="t")  # equals sign
    assert fields["bore_diameter"] == Quantity(magnitude=25.0, unit="mm")  # column gap


def test_a_single_space_is_not_a_separator():
    # "design load 50 kN" split at the first space would label the field "design".
    draft = extract_requirements("design load 50 kN\n", document="rfq.txt")
    assert draft.values == ()


def test_an_offset_temperature_unit_survives_the_pass():
    # pint will not *parse* "-20 degC" from text, only construct it — and every real
    # requirement sheet has a service temperature on it.
    (value,) = [v for v in _draft().values if v.field == "service_temperature"]
    assert value.quantity.to("degC").magnitude == pytest.approx(-20.0)


def test_a_bare_number_is_recorded_as_unparsed_rather_than_guessed_at():
    reasons = {u.source.excerpt.strip(): u.reason for u in _draft().unparsed}
    assert "Quantity: 4" in reasons
    assert "Finish: black oxide" in reasons
    assert "Part number:      LUG-4471" in reasons
    # And the pass is auditable by subtraction: everything labelled is either extracted or
    # listed, so a reader can see what was not taken instead of assuming nothing was left.
    assert len(_draft().values) + len(_draft().unparsed) == 7


def test_comments_and_blank_lines_are_skipped_silently():
    draft = extract_requirements("# a heading\n\n  \nLoad: 5 kN\n", document="rfq.txt")
    assert len(draft.values) == 1
    assert draft.unparsed == ()


def test_labels_normalize_to_stable_field_names():
    draft = extract_requirements("Design Load (max): 50 kN\n", document="rfq.txt")
    assert draft.values[0].field == "design_load_max"


def test_a_thousands_separator_does_not_break_the_magnitude():
    draft = extract_requirements("Proof load: 1,250 kN\n", document="rfq.txt")
    assert draft.values[0].quantity.magnitude == pytest.approx(1250.0)


def test_extraction_must_name_its_document():
    with pytest.raises(ValueError, match="name the document"):
        extract_requirements(SHEET, document="  ")


# --- everything is a draft, and a draft is not an input -------------------------------------


def test_every_extracted_value_starts_as_a_draft():
    assert all(v.state is ConfirmationState.DRAFT for v in _draft().values)
    assert all(not v.usable for v in _draft().values)


def test_an_unclassified_value_is_load_bearing_by_default():
    # The safe direction: a value nobody classified blocks the release until somebody looks
    # at it, rather than slipping through as decoration.
    draft = extract_requirements("Mystery figure: 7 kN\n", document="rfq.txt")
    assert draft.values[0].load_bearing is True


def test_named_informational_fields_do_not_block():
    draft = extract_requirements(
        "Revision: 3 dimensionless\nLoad: 5 kN\n",
        document="rfq.txt",
        informational_fields=("revision",),
    )
    outstanding = {v.field for v in draft.unconfirmed_load_bearing()}
    assert outstanding == {"load"}


def test_release_refuses_while_a_load_bearing_value_is_a_draft():
    with pytest.raises(ValueError, match="a draft is not an input"):
        _draft().release()


def test_release_names_exactly_what_is_outstanding_and_does_not_repeat_a_field():
    draft = extract_requirements("Load: 50 kN\nLoad: 50 kN\nSpan: 2 m\n", document="rfq.txt")
    with pytest.raises(ValueError) as caught:
        draft.release()
    assert "['load', 'span']" in str(caught.value)


def test_release_hands_over_the_confirmed_values_once_nothing_is_outstanding():
    draft = extract_requirements("Load: 50 kN\nSpan: 2 m\n", document="rfq.txt")
    for field in ("load", "span"):
        draft = draft.with_confirmation(field, by="A. Engineer, P.E.")
    released = draft.release()
    assert released == {
        "load": Quantity(magnitude=50.0, unit="kN"),
        "span": Quantity(magnitude=2.0, unit="m"),
    }


def test_release_is_all_or_nothing():
    # Releasing the confirmed subset and letting the caller notice the gap is the same
    # failure with more steps.
    draft = extract_requirements("Load: 50 kN\nSpan: 2 m\n", document="rfq.txt")
    draft = draft.with_confirmation("load", by="A. Engineer, P.E.")
    with pytest.raises(ValueError, match="span"):
        draft.release()


def test_a_rejected_value_is_a_decision_and_does_not_block():
    draft = extract_requirements("Load: 50 kN\nStray: 9 kN\n", document="rfq.txt")
    draft = draft.with_confirmation("load", by="A. Engineer, P.E.")
    draft = draft.with_confirmation(
        "stray", by="A. Engineer, P.E.", state=ConfirmationState.REJECTED
    )
    assert set(draft.release()) == {"load"}
    # And it is still in the record: refused is different information from never seen.
    assert any(v.state is ConfirmationState.REJECTED for v in draft.values)


def test_confirming_a_field_the_draft_does_not_carry_is_refused():
    # Confirming a misspelled field name and getting a clean draft back is exactly how an
    # unconfirmed value reaches a check.
    with pytest.raises(ValueError, match="no extracted value for 'desgin_load'"):
        _draft().with_confirmation("desgin_load", by="A. Engineer, P.E.")


def test_a_confirmation_names_a_person():
    with pytest.raises(ValueError, match="names the person"):
        _draft().with_confirmation("design_load", by="   ")


def test_a_confirmed_state_cannot_be_unsigned_and_a_draft_cannot_be_signed():
    with pytest.raises(ValidationError, match="with nobody named"):
        ExtractedValue(
            field="load",
            quantity=Quantity(magnitude=5.0, unit="kN"),
            source=_location(),
            state=ConfirmationState.CONFIRMED,
        )
    with pytest.raises(ValidationError, match="state change, not an annotation"):
        ExtractedValue(
            field="load",
            quantity=Quantity(magnitude=5.0, unit="kN"),
            source=_location(),
            confirmed_by="A. Engineer",
        )


# --- conflicts are surfaced, never resolved ----------------------------------------------


def test_two_disagreeing_values_for_one_field_are_both_kept():
    draft = extract_requirements("Load: 50 kN\nLoad: 45 kN\n", document="rfq.txt")
    (conflict,) = draft.conflicts()
    assert conflict.field == "load"
    assert [v.quantity.magnitude for v in conflict.values] == [50.0, 45.0]
    assert "2 disagreeing values" in str(conflict)


def test_the_same_value_stated_twice_is_not_a_conflict():
    draft = extract_requirements("Load: 50 kN\nLoad: 50000 N\n", document="rfq.txt")
    assert draft.conflicts() == ()


def test_incommensurable_units_for_one_field_always_conflict():
    draft = extract_requirements("Load: 50 kN\nLoad: 50 mm\n", document="rfq.txt")
    assert len(draft.conflicts()) == 1


def test_a_conflict_blocks_the_release_even_when_both_sides_are_confirmed():
    # Two values for one field is not a field, whatever anyone signed.
    draft = extract_requirements("Load: 50 kN\nLoad: 45 kN\n", document="rfq.txt")
    draft = draft.with_confirmation("load", by="A. Engineer, P.E.")
    assert draft.unconfirmed_load_bearing() == ()
    with pytest.raises(ValueError, match="disagreeing values"):
        draft.release()


def test_rejecting_one_side_resolves_the_conflict():
    draft = extract_requirements("Load: 50 kN\nLoad: 45 kN\n", document="rfq.txt")
    corrected = draft.model_copy(
        update={
            "values": (
                draft.values[0].confirmed("A. Engineer, P.E."),
                draft.values[1].rejected("A. Engineer, P.E."),
            )
        }
    )
    assert corrected.conflicts() == ()
    assert corrected.release() == {"load": Quantity(magnitude=50.0, unit="kN")}


# --- the source location is what makes an extraction checkable -------------------------------


def test_every_value_carries_the_line_it_came_from():
    value = next(v for v in _draft().values if v.field == "design_load")
    assert value.source.line_number == 3
    assert "50 kN" in value.source.excerpt
    assert value.source.document == "rfq-2026-114.txt"
    assert "rfq-2026-114.txt:3" in str(value.source)


def test_a_page_number_travels_when_the_reader_knows_one():
    draft = extract_requirements("Load: 5 kN\n", document="rfq.pdf", page=7)
    assert draft.values[0].source.page == 7
    assert "(p. 7)" in str(draft.values[0].source)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("document", "  ", "name its document"),
        ("line_number", 0, "line numbers start at 1"),
        ("excerpt", "   ", "carry the text it read"),
        ("page", 0, "page numbers start at 1"),
    ],
)
def test_a_source_location_has_to_actually_locate_something(field, value, match):
    fields = {"document": "rfq.txt", "line_number": 1, "excerpt": "Load: 5 kN"}
    fields[field] = value
    with pytest.raises(ValidationError, match=match):
        SourceLocation(**fields)


def test_the_summary_says_what_was_read_and_what_blocks():
    summary = _draft().summary()
    assert "4 values from 1 document(s)" in summary
    assert "0 confirmed" in summary
    assert "blocked:" in summary


# --- what an adversarial review found the hour this shipped ---------------------------------
#
# Nine findings, three of them severe, and all three were the same failure: the pass
# produced a confident WRONG number instead of declining. A value it declines is visible in
# `unparsed` and costs somebody a minute. A value it gets wrong is a load.


@pytest.mark.parametrize(
    ("line", "was"),
    [
        ("Design load: 45–50 kN", "2250 kN — the en dash Word autocorrects a hyphen into"),
        ("Design load: 45—50 kN", "an em-dash range"),
        ("Bore: 25 ±0.1 mm", "2.5 mm — the tolerance multiplied in"),
        ("Bore: 25 ± 0.1 mm", "the spaced tolerance"),
        ("Load: 10 to 20 kN", "a written range"),
        ("Load: ~50 kN", "an approximate value"),
    ],
)
def test_a_range_or_a_tolerance_is_declined_rather_than_multiplied_out(line, was):
    draft = extract_requirements(line + "\n", document="rfq.txt")
    assert draft.values == (), f"took {was}"
    assert len(draft.unparsed) == 1


def test_the_general_net_catches_any_unit_half_carrying_its_own_number():
    """The specific spellings above are a list; this is the property underneath them.

    If the parsed magnitude is not the magnitude the line stated, pint multiplied something
    in from the "unit" half — whatever the punctuation was.
    """
    draft = extract_requirements("Load: 45 50 kN\n", document="rfq.txt")
    assert draft.values == ()
    assert "carries a number of its own" in draft.unparsed[0].reason


def test_a_decimal_comma_is_refused_rather_than_read_as_a_thousands_separator():
    # "1,5 m" is one and a half metres in most of Europe — the sheets this module targets —
    # and stripping the comma made it 15 m, a tenfold error.
    draft = extract_requirements("Span: 1,5 m\n", document="rfq.txt")
    assert draft.values == ()
    assert "ambiguous" in draft.unparsed[0].reason
    # Unambiguous thousands grouping still works.
    grouped = extract_requirements("Proof load: 1,250,000 N\n", document="rfq.txt")
    assert grouped.values[0].quantity.magnitude == pytest.approx(1_250_000.0)


@pytest.mark.parametrize(
    ("line", "was"),
    [
        ("Temp: 20 C", "20 coulomb"),
        ("Temp: 20 F", "20 farad"),
        ("Grade: 8.8 min", "8.8 minutes, for a bolt grade"),
        ("Pressure: 5 bar g", "bar*gram"),
        ("Torque: 40 N*m nom", "the nom qualifier read as a unit"),
    ],
)
def test_a_unit_pint_accepts_but_nobody_meant_is_declined(line, was):
    draft = extract_requirements(line + "\n", document="rfq.txt")
    assert draft.values == (), f"took {was}"
    assert len(draft.unparsed) == 1


def test_a_labelled_line_never_vanishes_without_a_trace():
    # An 81-character label matched no separator at all and disappeared — no value, no
    # unparsed record — which defeats the auditable-by-subtraction property outright.
    long_label = "L" * 200
    draft = extract_requirements(f"{long_label}: 50 kN\n", document="rfq.txt")
    assert len(draft.values) == 1
    assert draft.values[0].field == long_label.lower()
    # And a label that normalizes away to nothing is recorded rather than skipped.
    punctuation = extract_requirements("***: 50 kN\n", document="rfq.txt")
    assert punctuation.values == ()
    assert "empty field name" in punctuation.unparsed[0].reason


def test_a_colon_beats_a_column_gap_so_an_aligned_label_keeps_its_value():
    # The stated use case is a flattened fixed-width table, which routinely has runs of
    # spaces inside the label. Splitting on the gap first threw the value away.
    draft = extract_requirements("Design load   (max):   50 kN\n", document="rfq.txt")
    assert draft.values[0].field == "design_load_max"
    assert draft.values[0].quantity.magnitude == pytest.approx(50.0)
    spaced = extract_requirements("DESIGN  LOAD: 50 kN\n", document="rfq.txt")
    assert spaced.values[0].field == "design_load"
    # And a table with no punctuation at all still splits on the gap.
    table = extract_requirements("Bore diameter        25 mm\n", document="rfq.txt")
    assert table.values[0].field == "bore_diameter"


def test_a_value_cannot_be_confirmed_by_nobody_through_the_public_api():
    """`model_copy` does not re-run validators, and these two methods are public.

    `v.confirmed("   ")` produced exactly the state the constructor refuses — CONFIRMED
    with nobody named — and `DraftSpec.model_copy`, the idiom the shipped example uses to
    resolve a conflict, carried it straight into `release()`.
    """
    draft = extract_requirements("Load: 50 kN\n", document="rfq.txt")
    value = draft.values[0]
    for blank in ("", "   ", "\t"):
        with pytest.raises(ValueError, match="names the person"):
            value.confirmed(blank)
        with pytest.raises(ValueError, match="names the person"):
            value.rejected(blank)
    # And the name is stored stripped, so a stray space is not a different person.
    assert value.confirmed("  A. Engineer  ").confirmed_by == "A. Engineer"


def test_reversing_a_decision_has_to_be_deliberate():
    # The membership test included rejected values, so a second confirmation flipped a
    # REJECTED value to CONFIRMED and released it — overwriting the refusal in place, with
    # nothing left to show it had ever been made.
    draft = extract_requirements("Load: 50 kN\n", document="rfq.txt")
    refused = draft.with_confirmation("load", by="A. Engineer", state=ConfirmationState.REJECTED)
    with pytest.raises(ValueError, match="Reversing a decision is a new decision"):
        refused.with_confirmation("load", by="B. Engineer")
    reconsidered = refused.with_confirmation("load", by="B. Engineer", reconsider=True)
    assert reconsidered.release() == {"load": Quantity(magnitude=50.0, unit="kN")}


def test_agreement_is_relative_so_it_means_the_same_thing_at_every_scale():
    # `round(..., 9)` was an absolute tolerance in whatever unit the first value used: at
    # gigametres it swallowed a 0.4 m disagreement.
    far = extract_requirements("Baseline: 1 Gm\nBaseline: 1.0000000004 Gm\n", document="rfq.txt")
    assert len(far.conflicts()) == 1
    # And a conversion's own float error is not a conflict.
    same = extract_requirements("Load: 50 kN\nLoad: 50000 N\n", document="rfq.txt")
    assert same.conflicts() == ()
    # A real disagreement at any scale is one.
    near = extract_requirements("Load: 50 kN\nLoad: 50.04 kN\n", document="rfq.txt")
    assert len(near.conflicts()) == 1


def test_releasing_nothing_is_not_releasing():
    # Every value rejected: both gates pass, and handing the pipeline `{}` makes "there is
    # nothing here" indistinguishable from "everything checked out".
    draft = extract_requirements("Load: 50 kN\n", document="rfq.txt")
    emptied = draft.with_confirmation("load", by="A. Engineer", state=ConfirmationState.REJECTED)
    assert emptied.unconfirmed_load_bearing() == ()
    assert emptied.conflicts() == ()
    with pytest.raises(ValueError, match="nothing to release"):
        emptied.release()


# --- and what a mutation run left standing -----------------------------------------------


def test_a_hand_built_value_is_load_bearing_unless_it_says_otherwise():
    # `extract_requirements` always passes the flag explicitly, so the default itself —
    # the "safe direction" the docstring claims — was pinned by nothing.
    value = ExtractedValue(
        field="load", quantity=Quantity(magnitude=5.0, unit="kN"), source=_location()
    )
    assert value.load_bearing is True
    assert value.state is ConfirmationState.DRAFT


def test_informational_fields_are_named_in_human_form():
    # The documented behaviour is that you name them as they appear on the sheet; the
    # normalization that makes that work was untested.
    draft = extract_requirements(
        "Part Number: 4471 dimensionless\nLoad: 5 kN\n",
        document="rfq.txt",
        informational_fields=("Part Number",),
    )
    assert {v.field for v in draft.unconfirmed_load_bearing()} == {"load"}


def test_a_dimensionless_value_is_declined_because_parse_is_tried_first():
    # `Quantity.parse` refuses a bare or dimensionless number; the direct-construction
    # fallback does not. Dropping the parse call entirely left every test green while
    # quietly admitting "12 %", "30 deg", and "3 dimensionless" as physical quantities.
    for line in ("Utilisation: 12 %", "Fill: 3 dimensionless"):
        draft = extract_requirements(line + "\n", document="rfq.txt")
        assert draft.values == (), line


def test_scientific_notation_survives_the_pass():
    draft = extract_requirements("Modulus: 2.05e5 MPa\n", document="rfq.txt")
    assert draft.values[0].quantity.magnitude == pytest.approx(205000.0)


def test_the_document_name_is_stored_stripped():
    draft = extract_requirements("Load: 5 kN\n", document="  rfq.txt  ")
    assert draft.documents == ("rfq.txt",)


def test_the_summary_counts_conflicts_as_well_as_drafts():
    draft = extract_requirements("Load: 50 kN\nLoad: 45 kN\n", document="rfq.txt")
    assert "1 conflicting" in draft.summary()
    agreed = extract_requirements("Load: 50 kN\nLoad: 50 kN\n", document="rfq.txt")
    assert "0 conflicting" in agreed.summary()


# --- the confirmation checklist -----------------------------------------------------------
#
# `input-ingestion` requires that extracted values "appear as a confirmation checklist, each
# linked to its page location". `summary()` counts them — "2 unconfirmed" — which is the one
# thing the confirmer already knows. Every value carried a SourceLocation the whole time and
# nothing rendered it.


def _located(field, quantity, *, line, page=None, excerpt=None, load_bearing=True):
    return ExtractedValue(
        field=field,
        quantity=Quantity.parse(quantity),
        load_bearing=load_bearing,
        source=SourceLocation(
            document="rfq.pdf",
            page=page,
            line_number=line,
            excerpt=excerpt or f"{field}: {quantity}",
        ),
    )


def _mixed_draft():
    return DraftSpec(
        values=(
            _located("design_load", "50 kN", line=14, page=2),
            _located("design_load", "60 kN", line=3, page=5),
            _located("finish_area", "0.5 m**2", line=2, page=4, load_bearing=False),
            _located("material_yield", "250 MPa", line=9, page=1).confirmed("A. Engineer"),
        ),
        unparsed=(
            UnparsedLine(
                source=SourceLocation(
                    document="rfq.pdf", page=6, line_number=22, excerpt="approx 3/8 in stock"
                ),
                reason="no parseable quantity",
            ),
        ),
        documents=("rfq.pdf",),
    )


def test_every_extracted_value_appears_with_where_it_came_from():
    """Derived from the draft, not compared against a fixture: a value whose location the
    renderer drops fails here, and so does one the renderer forgets entirely."""
    draft = _mixed_draft()
    checklist = draft.checklist()
    for value in draft.values:
        assert value.field in checklist
        assert str(value.source) in checklist, f"{value.field} is listed without its location"
        assert value.source.excerpt in checklist, "the excerpt is what makes it checkable"
        assert str(value.source.line_number) in checklist
    for line in draft.unparsed:
        assert line.reason in checklist
        assert str(line.source) in checklist


def test_the_checklist_separates_what_blocks_release_from_what_does_not():
    """A confirmer works the blocking list first, so "2 unconfirmed" is not enough — and a
    non-load-bearing draft value is still a draft, so it cannot be silently dropped."""
    checklist = _mixed_draft().checklist()
    blocking = checklist.index("TO CONFIRM — load-bearing")
    advisory = checklist.index("TO CONFIRM — not load-bearing")
    confirmed = checklist.index("CONFIRMED")
    assert blocking < advisory < confirmed
    load_bearing_block = checklist[blocking:advisory]
    assert "design_load" in load_bearing_block
    assert "finish_area" not in load_bearing_block
    assert "finish_area" in checklist[advisory:confirmed]
    assert "confirmed by A. Engineer" in checklist


def test_a_conflict_shows_both_readings_rather_than_naming_the_field():
    """The one case where a reader needs both excerpts side by side to decide which line is
    right. Naming the field tells them there is a problem and nothing about it."""
    checklist = _mixed_draft().checklist()
    section = checklist[checklist.index("CONFLICTS") :]
    assert "design_load disagrees" in section
    assert "50.0 kN" in section and "60.0 kN" in section
    # Both excerpts, not just both magnitudes: the excerpt is the line the reader goes back to.
    assert "design_load: 50 kN" in section and "design_load: 60 kN" in section


def test_every_heading_is_present_even_when_its_section_is_empty():
    """The calculation report's rule, one layer over: a draft with no conflicts and one
    whose conflicts nobody looked for must not render the same document."""
    clean = DraftSpec(
        values=(_located("bore", "25 mm", line=6).confirmed("A. Engineer"),),
        documents=("rfq.pdf",),
    )
    checklist = clean.checklist()
    for heading in ("TO CONFIRM", "CONFIRMED", "CONFLICTS", "NOT EXTRACTED"):
        assert heading in checklist
    assert checklist.count("none") >= 3


def test_the_checklist_of_a_real_extraction_lists_what_the_extractor_found():
    """Against the extractor rather than a hand-built draft, so the two cannot drift."""
    draft = extract_requirements(SHEET, document="rfq.txt")
    checklist = draft.checklist()
    assert draft.values, "the extractor found nothing, so this checked nothing"
    for value in draft.values:
        assert str(value.source) in checklist
    # No page in a text document, and it must not print as "p. None".
    assert "p. None" not in checklist


def _documented_draft() -> DraftSpec:
    """The draft the docs page walks through, as inputs rather than as rendered output."""
    return DraftSpec(
        values=(
            _located("design_load", "50 kN", line=14, page=2, excerpt="Design load: 50 kN"),
            _located("plate_thickness", "12 mm", line=7, page=3, excerpt="Plate 12 mm"),
            _located("design_load", "60 kN", line=3, page=5, excerpt="Load shall be 60 kN"),
            _located(
                "finish_area",
                "0.5 m**2",
                line=2,
                page=4,
                excerpt="Painted area 0.5 m2",
                load_bearing=False,
            ),
            _located("material_yield", "250 MPa", line=9, page=1, excerpt="A36").confirmed(
                "A. Engineer"
            ),
        ),
        unparsed=(
            UnparsedLine(
                source=SourceLocation(
                    document="rfq.pdf", page=6, line_number=22, excerpt="approx 3/8 in stock"
                ),
                reason="no parseable quantity",
            ),
        ),
        documents=("rfq.pdf",),
    )


def test_the_checklist_on_the_docs_page_is_the_one_the_library_renders():
    """The page shows a worked checklist, so the page's block is the library's own output.

    The first version of this read the *values* back out of the rendered block and rebuilt
    the draft from them — which is a test whose expected output comes from the thing under
    test. Changing `50.0 kN` to `55.0 kN` on the page passed, because the page was feeding
    itself. The inputs are stated here and the rendering is compared; a drifting page and a
    drifting renderer each fail.
    """
    import re
    from pathlib import Path

    page = (
        Path(__file__).resolve().parent.parent / "docs" / "requirements-ingestion.md"
    ).read_text(encoding="utf-8")
    block = re.search(r"```text\n(\d+ values from(?:.|\n)*?)```", page)
    assert block is not None, "the worked checklist on requirements-ingestion.md has moved"
    assert _documented_draft().checklist() == block.group(1), (
        f"the page shows:\n{block.group(1)}\n"
        f"the library renders:\n{_documented_draft().checklist()}"
    )


# --- Which end of the range a requirement states ---------------------------------------


@pytest.mark.parametrize(
    ("line", "bound"),
    [
        ("Design load: 50 kN max", Bound.MAXIMUM),
        ("Design load: 50 kN maximum", Bound.MAXIMUM),
        ("Design load: 50 kN max.", Bound.MAXIMUM),
        ("Design load: 50 kN min", Bound.MINIMUM),
        ("Design load: 50 kN minimum", Bound.MINIMUM),
    ],
)
def test_a_directional_qualifier_is_taken_with_its_bound_rather_than_declined(line, bound):
    """`max` is a qualifier, and refusing the qualifier used to refuse the quantity with it.

    "Design load: 50 kN max" is on every requirement sheet there is and the pass took
    nothing from it. The value is the same value; what the qualifier adds is the direction.
    """
    draft = extract_requirements(line + "\n", document="rfq.txt")
    assert draft.unparsed == (), draft.unparsed
    (value,) = draft.values
    assert value.field == "design_load"
    assert value.quantity.magnitude == pytest.approx(50.0)
    assert value.quantity.unit == "kN"
    assert value.bound is bound


@pytest.mark.parametrize(
    ("line", "bound"),
    [
        ("Maximum operating pressure: 5 bar", Bound.MAXIMUM),
        ("Max operating pressure: 5 bar", Bound.MAXIMUM),
        ("Operating pressure (max): 5 bar", Bound.MAXIMUM),
        ("Pressure not to exceed: 5 bar", Bound.MAXIMUM),
        ("Pressure no more than: 5 bar", Bound.MAXIMUM),
        ("Pressure at most: 5 bar", Bound.MAXIMUM),
        ("Minimum yield: 250 MPa", Bound.MINIMUM),
        ("Yield at least: 250 MPa", Bound.MINIMUM),
        ("Yield no less than: 250 MPa", Bound.MINIMUM),
        # The trap this is guarded against: "min" is a substring of "nominal", and a
        # nominal dimension read as a floor is a confident wrong answer. Whole tokens only.
        ("Nominal bore: 25 mm", Bound.UNSTATED),
        ("Maximal bore: 25 mm", Bound.UNSTATED),
        ("Bore: 25 mm", Bound.UNSTATED),
    ],
)
def test_the_label_states_the_bound_by_whole_words_not_by_substring(line, bound):
    draft = extract_requirements(line + "\n", document="rfq.txt")
    assert draft.unparsed == (), draft.unparsed
    (value,) = draft.values
    assert value.bound is bound


def test_the_field_name_is_not_rewritten_when_the_label_states_a_bound():
    """Renaming `maximum_operating_pressure` to `operating_pressure` merges two fields.

    The bound is recorded *in addition to* the name the document used, because a rename is
    a decision that two lines are about one thing, and this pass does not make those.
    """
    draft = extract_requirements("Maximum operating pressure: 5 bar\n", document="rfq.txt")
    (value,) = draft.values
    assert value.field == "maximum_operating_pressure"
    assert value.bound is Bound.MAXIMUM


def test_a_line_stating_both_ends_is_declined_naming_both():
    both_halves = extract_requirements("Minimum bore: 30 mm max\n", document="rfq.txt")
    assert both_halves.values == ()
    assert "states a minimum and the value states a maximum" in both_halves.unparsed[0].reason
    one_label = extract_requirements("Minimum and maximum bore: 30 mm\n", document="rfq.txt")
    assert one_label.values == ()
    assert "both a maximum and a minimum" in one_label.unparsed[0].reason


def test_a_bare_number_stays_declined_however_it_was_qualified():
    """Stripping the qualifier must not manufacture a quantity out of what is left.

    "Grade: 8.8 min" is a bolt grade, not 8.8 of anything, and the whole "a bare number is
    not a quantity" position rests on the qualifier strip not being an escape hatch.

    The *reason* is asserted, not just the refusal. Stripping the qualifier with nothing
    left behind still declines the line — a bare number is refused further down — but it
    declines it with a parse error instead of the sentence that tells the author to write
    `minute` if they meant the time unit. That mutation survived a count-only assertion.
    """
    draft = extract_requirements("Grade: 8.8 min\n", document="rfq.txt")
    assert draft.values == ()
    assert len(draft.unparsed) == 1
    assert "usually 'minimum'" in draft.unparsed[0].reason


def test_two_bounds_on_one_field_are_a_range_not_a_conflict():
    """Reporting them as disagreeing sends somebody to reject a requirement the sheet meant.

    They still cannot both be released — one slot per field — so the refusal moves to the
    gate, where it names the field rather than accusing the document of contradicting
    itself.
    """
    draft = extract_requirements(
        "Design load: 50 kN max\nDesign load: 20 kN min\n", document="rfq.txt"
    )
    assert len(draft.values) == 2
    assert draft.conflicts() == ()
    confirmed = draft.with_confirmation("design_load", by="A. Engineer")
    assert confirmed.split_bounds() == ("design_load",)
    # The summary must not read "releasable" over a draft the gate refuses: the reader
    # believes the cheap answer.
    assert "releasable" not in confirmed.summary()
    assert "1 split across two bounds" in confirmed.summary()
    with pytest.raises(ValueError, match="one slot per field"):
        confirmed.release()
    # And the resolution this module already has: reject the end the check does not take.
    resolved = confirmed.with_confirmation(
        "design_load", by="A. Engineer", state=ConfirmationState.REJECTED, reconsider=True
    )
    assert resolved.split_bounds() == ()


def test_two_values_for_one_field_and_one_bound_are_still_a_conflict():
    """The bound narrows the grouping; it must not dissolve it."""
    draft = extract_requirements(
        "Design load: 50 kN max\nDesign load: 60 kN max\n", document="rfq.txt"
    )
    (conflict,) = draft.conflicts()
    assert conflict.field == "design_load"
    assert len(conflict.values) == 2


def test_the_checklist_shows_the_bound_next_to_the_number():
    """A confirmer decides whether the sheet says 50 *and* whether 50 is a ceiling."""
    draft = extract_requirements("Design load: 50 kN max\nBore: 25 mm\n", document="rfq.txt")
    checklist = draft.checklist()
    assert "design_load = 50.0 kN (a maximum)" in checklist
    # An unstated bound renders as nothing rather than as a third word nobody can act on.
    assert "bore = 25.00 mm    " in checklist


def test_every_bound_says_itself_in_a_sentence():
    """Looped over the enum, not a representative: an unphrased member raises at render."""
    phrases = {member: member.phrase() for member in Bound}
    assert all(phrase.strip() for phrase in phrases.values())
    # Distinct, because a phrase shared by two members is a rendering that cannot tell
    # a ceiling from a floor — which is the whole point of carrying the bound.
    assert len(set(phrases.values())) == len(Bound)


def test_a_lowercase_c_is_declined_rather_than_read_as_the_speed_of_light():
    """ "Temp: 20 c" was **taken**, as twenty times the speed of light.

    The ambiguity list that catches `C` and `F` is keyed on the exact token, so it held the
    capitals and nothing else. Lowercase `c` is a unit pint knows — it is *c* — so
    `Quantity.parse` succeeded; the magnitude matched what the line stated, so the
    range-and-tolerance net below caught nothing either; and a temperature requirement
    entered the checklist with a dimensionality of `[length]/[time]`.

    Asserted at the public entry point on purpose. The private helper had a list of its own
    and the pass walked past it, which is how the two disagreed in the first place.
    """
    for line, reads_as in (("Temp: 20 c", "speed of light"), ("Temp: 20 f", "farad")):
        draft = extract_requirements(line + "\n", document="rfq.txt")
        assert draft.values == (), (
            f"{line!r} was taken as "
            f"{[(str(v.quantity), str(v.quantity.dimensionality)) for v in draft.values]}"
        )
        (declined,) = draft.unparsed
        assert reads_as in declined.reason, declined.reason
        assert "deg" in declined.reason, "the refusal does not say what to write instead"
    # The capitals were already held one layer up, and still are.
    assert extract_requirements("Temp: 20 C\n", document="rfq.txt").values == ()


def test_a_temperature_written_in_words_is_taken_rather_than_declined_on_its_capital():
    """ "Temp: 20 Celsius" was declined with a raw `1 validation error for Quantity`.

    The offset-temperature list matched on `unit.lower()` and then handed pint the
    document's own spelling, which pint does not know with a capital C. A spelling the list
    claims to handle was refused, and refused for the wrong reason — not "this is not a
    unit" but "we said we handled this".
    """
    draft = extract_requirements("Temp: 20 Celsius\n", document="rfq.txt")
    assert draft.unparsed == (), [u.reason for u in draft.unparsed]
    (value,) = draft.values
    assert str(value.quantity.dimensionality) == "[temperature]"
    assert value.quantity.to("K").magnitude == pytest.approx(293.15)


def test_the_offset_units_are_declined_or_taken_but_never_read_as_another_dimension():
    """The property under all of it: a temperature spelling is either taken as a temperature
    or declined by name. What it must never be is taken as something else."""
    from anvilate.ingest import _quantity

    for token, other in (("C", "coulomb"), ("c", "speed of light"), ("F", "farad")):
        with pytest.raises(ValueError) as refused:
            _quantity("5", token)
        message = str(refused.value)
        assert other in message, message
        assert "deg" in message, "the refusal does not say what to write instead"

    # The unambiguous spellings all still work, including the degree sign, which strips to
    # the same letter and must not be swept into the refusal.
    for magnitude, unit, expected in (
        ("-20", "degC", "[temperature]"),
        ("-20", "°C", "[temperature]"),
        ("20", "°F", "[temperature]"),
        ("300", "K", "[temperature]"),
    ):
        assert str(_quantity(magnitude, unit).dimensionality) == expected, unit
    # And the electrical quantities are still reachable by their full names, which is what
    # the refusal tells an author to write.
    assert str(_quantity("5", "coulomb").dimensionality) == "[current] * [time]"


def test_the_offset_temperature_list_constructs_what_it_claims_to_handle():
    """The membership test was case-insensitive and the construction was not.

    `"20 Celsius"` matched the list on `unit.lower()` and was then handed to pint with its
    capital C, which pint does not know — so the line was declined, and declined for the
    wrong reason: not "this is not a unit" but "we said we handled this". Every spelling the
    list claims is now constructed through pint's own name for it.
    """
    from anvilate.ingest import _OFFSET_TEMPERATURE_UNITS, _quantity

    assert _OFFSET_TEMPERATURE_UNITS, "the offset-temperature list is empty"
    for written, canonical in _OFFSET_TEMPERATURE_UNITS.items():
        for spelling in (written, written.upper(), written.capitalize(), f"°{written}"):
            try:
                quantity = _quantity("20", spelling)
            except ValueError as refused:
                # Only the bare-letter tokens may be refused, and only for ambiguity.
                assert spelling.strip("°").lower() in {"c", "f"}, (spelling, refused)
                assert "not a temperature" in str(refused), spelling
                continue
            assert str(quantity.dimensionality) == "[temperature]", spelling
            assert str(quantity.to("K").unit) == "K"
            assert canonical in {"degC", "degF"}


def test_every_line_the_docs_table_says_is_declined_really_is():
    """A page whose whole subject is what the pass refuses, held against the pass.

    Six rows, and one of them was **false**: `Temp: 20 C` was documented as "declined; write
    `degC`" and was read as twenty coulombs. Nothing was holding the table, so the page and
    the code disagreed about the one behaviour the page exists to describe.

    The lines are read off the page rather than restated, so a row added to the table has to
    be true, and the *reason* is not asserted — only that the value is not taken, which is
    the claim every row makes.
    """
    import re
    from pathlib import Path

    page = (
        Path(__file__).resolve().parent.parent / "docs" / "requirements-ingestion.md"
    ).read_text(encoding="utf-8")
    table = re.search(r"\| Line \| Would have been \| Now \|\n\|[^\n]*\n((?:\|[^\n]*\n)+)", page)
    assert table is not None, "the declined-lines table on requirements-ingestion.md has moved"

    rows = [row for row in table.group(1).splitlines() if row.strip()]
    assert len(rows) >= 6, f"the table has shrunk to {len(rows)} rows"
    for row in rows:
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        line = cells[0].strip("`")
        draft = extract_requirements(line + "\n", document="rfq.txt")
        assert draft.values == (), (
            f"the page says {line!r} is declined, and the pass took "
            f"{[str(v.quantity) for v in draft.values]} from it"
        )
        assert draft.unparsed, f"{line!r} was neither taken nor recorded as unparsed"
        assert draft.unparsed[0].reason.strip(), f"{line!r} is declined with no reason given"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("design load: 1e400 kN", "overflows to inf"),
        ("design load: -1e400 kN", "overflows to -inf"),
        ("bore diameter: 1e-400 mm", "underflows to zero"),
    ],
)
def test_a_number_a_float_cannot_hold_is_not_extracted(line, expected):
    """`inf kN` is refused by the value pattern; `1e400 kN` walked straight past it.

    `float` overflows both to the same infinity, and the general net in `_quantity` compares
    the parsed magnitude against `float(magnitude)` — inf == inf — so the pass released an
    infinite, load-bearing, confirmable draft value. The mirror case is quieter and worse: a
    dimension the author wrote as a positive number, extracted as exactly zero.
    """
    draft = extract_requirements(line, document="rfq.txt")
    assert not draft.values, f"{line} was extracted as {[str(v) for v in draft.values]}"
    assert len(draft.unparsed) == 1
    assert expected in str(draft.unparsed[0])


def test_a_zero_the_document_actually_states_is_still_extracted():
    """The underflow refusal must not swallow an honest zero — a clearance of 0 mm is a
    requirement somebody writes on purpose."""
    draft = extract_requirements("gap: 0 mm\nlash: 0.0 mm", document="rfq.txt")
    assert [v.field for v in draft.values] == ["gap", "lash"]
    assert all(v.quantity.magnitude == 0.0 for v in draft.values)


def test_a_certificate_says_when_the_calibration_was_performed():
    """The identifier can actively mislead about it.

    `PTB-2026-04711` reads as a 2026 measurement, and the certificate carrying it may record
    a performance date years earlier — which is what decides whether the value is still inside
    its calibration interval. The rendering carried the issue date and dropped the
    performance one.
    """
    from anvilate.ingest import CertificateProvenance, SignatureStatus

    def certificate(**dates):
        return CertificateProvenance(
            identifier="PTB-2026-04711",
            laboratory="PTB",
            signature_status=SignatureStatus.ABSENT,
            **dates,
        )

    assert "measured 2019-03-14" in str(certificate(performance_end_date="2019-03-14"))
    both = str(certificate(issue_date="2026-01-05", performance_end_date="2019-03-14"))
    assert "issued 2026-01-05, measured 2019-03-14" in both
    # The same date twice is one fact, not two: a certificate issued the day it was measured
    # renders as it did.
    same = str(certificate(issue_date="2026-01-05", performance_end_date="2026-01-05"))
    assert same == str(certificate(issue_date="2026-01-05"))


def test_a_refused_bare_number_is_quoted_the_way_the_line_wrote_it():
    """The refusal is right and it misquoted the line it was refusing.

    `_VALUE`'s unit group is mandatory and its magnitude group is not anchored to the end,
    so a value that is nothing but a number still matched — by backtracking until the unit
    had a character to take. `2.0` split into a magnitude of `2.` and a unit of `0`, and the
    sentence came back as **`'2. 0' has no unit`** about a line that said `2.0`. `12` became
    `'1 2'`; `0.75` became `'0.7 5'`; `100.5` became `'100. 5'`.

    "A bare number is not a quantity" is this module's doctrine and the verdict was never in
    question. But a refusal that misquotes its own subject reads as a parser fault, and it
    sends a reader looking for a typo they did not make — on the most ordinary line a
    requirements sheet carries, `Minimum safety factor: 2.0`.

    A bare number now takes the same path `2` already took, so one mistake gets one sentence.
    """
    for line in (
        "Minimum safety factor: 2.0",
        "Minimum safety factor: 2",
        "Ratio: 0.75",
        "Count: 12",
        "Factor: 1.05",
        "Scale: 100.5",
    ):
        draft = extract_requirements(line, document="rfq.txt")
        assert draft.values == (), f"{line!r} was extracted as a quantity"
        assert len(draft.unparsed) == 1, line
        reason = draft.unparsed[0].reason
        assert reason == "the value is not a number with a unit", f"{line!r}: {reason!r}"
        # The specific defect: no reassembled, space-injected version of the number.
        written = line.split(":", 1)[1].strip()
        assert written.replace(".", ". ") not in reason
        assert " " not in reason.replace("the value is not a number with a unit", "").strip()


def test_a_unit_that_begins_with_a_digit_still_parses():
    """The narrow escape the fix had to leave open.

    The split is only treated as one number when the unit half is *entirely* digits, commas
    and dots. A unit may legitimately start with a digit — `1/s` is how a requirement sheet
    writes a frequency — and rejecting the whole shape would have traded one wrong refusal
    for another.
    """
    draft = extract_requirements("Frequency: 50 1/s", document="rfq.txt")
    assert draft.unparsed == ()
    assert len(draft.values) == 1
    assert draft.values[0].quantity.to("Hz").magnitude == pytest.approx(50.0)

    # And the shapes the module already documented are untouched.
    for line, fragment in (
        ("Utilisation: 12 %", "has no unit"),
        ("Load: 1e400 kN", "overflows to inf"),
        ("Thickness: 25 +/- 0.1 mm", "range or a tolerance"),
    ):
        refused = extract_requirements(line, document="rfq.txt")
        assert refused.values == (), line
        assert fragment in refused.unparsed[0].reason, (line, refused.unparsed[0].reason)
    for line, unit in (("Temp: -20 degC", "°C"), ("Mass: 1,200 kg", "kg"), ("Load: 60 kN", "kN")):
        taken = extract_requirements(line, document="rfq.txt")
        assert len(taken.values) == 1, line
        assert unit in str(taken.values[0].quantity), line


# --- the line scan, which runs on every line of a document somebody pastes ---------------


def test_splitting_a_line_is_linear_in_the_length_of_the_line():
    """Both separators were built from lazy groups overlapping what followed them.

    So every expansion re-scanned the same whitespace looking for a separator, and the scan
    quadrupled every time the line doubled: a line with a few thousand spaces in it took half
    a second and a longer one took minutes. A long run of spaces is not hostile input — it is
    what a PDF or a spreadsheet export leaves on a row — and `extract_requirements` runs this
    on every line.

    Three shapes, because each was quadratic through a different pair: a line that never
    splits, one that splits and has whitespace after the value, and one whose *label* carries
    the run. Asserted as a ratio over the minimum of several runs, so a loaded machine cannot
    decide it either way, and the patterns' own shape is asserted beside it.
    """
    import time

    from anvilate.ingest import _SEPARATORS, _split

    for pattern in _SEPARATORS:
        assert ".*?" not in pattern.pattern, (
            f"a lazy anything is back in {pattern.pattern!r}; that is the shape that "
            "backtracks against whatever follows it"
        )
        assert not pattern.pattern.endswith(r"\s*$"), pattern.pattern

    shapes = {
        "never splits": lambda n: "a" + " " * n + "b",
        "splits, trailing run": lambda n: "a  b" + " " * n,
        "run inside the label": lambda n: "a" + " " * n + "b: 1",
    }
    for name, build in shapes.items():

        def _fastest(length: int, build=build) -> float:
            line = build(length)
            _split(line)
            best = float("inf")
            for _ in range(5):
                start = time.perf_counter()
                _split(line)
                best = min(best, time.perf_counter() - start)
            return best

        short, long = _fastest(4_000), _fastest(16_000)
        assert long < max(short * 8, 0.05), f"{name}: {short:.4f}s at 4k, {long:.4f}s at 16k"


def test_a_line_whose_label_is_only_whitespace_is_still_reported():
    """The regression the obvious speedup would have caused.

    Stripping both ends of the line — rather than only the right — stops these matching at
    all, and they would then vanish with no line anywhere in the output. They are *reported*:
    they split, the label normalises to an empty field name, and they come back as unparsed
    saying exactly that. Auditing by subtraction is the property the whole pass rests on.
    """
    draft = extract_requirements("\u00a0\t: 25 mm\n", document="rfq.txt")
    assert draft.values == ()
    assert len(draft.unparsed) == 1
    assert "empty field name" in str(draft.unparsed[0])


def test_trailing_whitespace_does_not_change_what_a_line_says():
    """The right-strip, from the other side: a row out of a spreadsheet export carries it and
    must read exactly as the same row without it."""
    from anvilate.ingest import _split

    for line in ("Design load: 50 kN", "Bore diameter     25 mm", "Rated capacity = 5 t"):
        bare = extract_requirements(line + "\n", document="rfq.txt")
        padded = extract_requirements(line + "   \t \n", document="rfq.txt")
        assert [str(v) for v in bare.values] == [str(v) for v in padded.values], line
        assert bare.values, line

        # And the captured value itself, not only what survives `Quantity.parse`. The
        # trailing `\s*$` the patterns used to end with is what kept whitespace out of this
        # group; the right-strip replaced it, and a reader that only checks the parsed
        # quantity cannot tell the difference — `Quantity.parse` tolerates the space.
        padded_match = _split(line + "   \t ")
        assert padded_match is not None, line
        value = padded_match.group("value")
        assert value == value.rstrip(), f"{line!r} captured {value!r}"
        assert value == _split(line).group("value"), line
