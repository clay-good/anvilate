"""Requirements ingestion: the extraction pass, and the gate it feeds."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.ingest import (
    ConfirmationState,
    DraftSpec,
    ExtractedValue,
    SourceLocation,
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
