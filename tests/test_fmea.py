"""Design FMEA rows from the design's own evidence.

The spec's scenarios: a bolted motor bracket's FMEA has rows for fatigue cracking at the
bend, joint loosening and bearing yield, each with its prevention check and detection test
linked; a row with no severity has no priority and names severity as the missing input;
a loaded action-priority matrix is used and named. And the gate: no licensed table ships.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from pathlib import Path

import pytest

import anvilate
from anvilate.failure_modes import (
    DEFAULT_CATALOG,
    Applicability,
    DiscoveryStage,
    FailureMode,
    ModeCatalog,
)
from anvilate.fmea import (
    DETECTION_BANDS,
    DETECTION_SCALE,
    FMEA_COLUMNS,
    OCCURRENCE_BANDS,
    OCCURRENCE_SCALE,
    FmeaDeclaration,
    fmea,
    load_action_priority,
    load_rating_scale,
)
from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity
from anvilate.verification import VerificationOutcome, plan_verification, record_outcome

_BTH1 = "ASME BTH-1 §3-2/§3-3 (allowable stresses)"


_J3 = "AISC 360-22 §J3.10"


def _entry(name: str, factor: float | None, reference: str = _J3) -> ScorecardEntry:
    entry = ScorecardEntry.from_safety_factor(
        name, computed=factor, required=1.0, unavailable="the load is not declared"
    )
    return entry.model_copy(update={"reference": reference})  # fmt: skip


def _mode(mode_id: str, check: str, **applies) -> FailureMode:
    return FailureMode(
        id=mode_id, description=f"{mode_id}, as the team's own mode list states it",
        applicability=Applicability(**applies), stage=DiscoveryStage.QUALIFICATION,
        citation="the team's bracket FMEA mode list, rev C", addressed_by=(check,),
    )  # fmt: skip


#: A team's own modes for its brackets, bound to its own check names.
CATALOG = ModeCatalog(modes=(
    _mode("fatigue cracking at the bend", "upright bending", elements=("angle_bracket",)),
    _mode("joint loosening", "bolt preload", interfaces=("bolted_face",)).model_copy(
        update={"tested_by": ("transverse-vibration",)}),
    _mode("bearing yield at the bolt holes", "bolt bearing", elements=("angle_bracket",)),
))  # fmt: skip

FACTS = {"element": "angle_bracket", "interfaces": ("bolted_face",)}


@pytest.fixture
def card() -> Scorecard:
    return Scorecard(entries=(
        _entry("upright bending", 1.8, _BTH1), _entry("bolt preload", 1.05),
        _entry("bolt bearing", 3.0),
    ))  # fmt: skip


@pytest.fixture
def plan(card):
    return plan_verification(card, parameters={"rated_load": Quantity.parse("100 kN")})


def test_a_brackets_fmea_links_each_mode_to_its_prevention_and_detection(card, plan):
    report = fmea(card, FACTS, item="motor bracket", function="hold the motor to the frame",
                  plan=plan, catalog=CATALOG)  # fmt: skip
    rows = {row.failure_mode: row for row in report.rows}
    assert list(rows) == ["fatigue cracking at the bend", "joint loosening",
                          "bearing yield at the bolt holes"]  # fmt: skip
    bend = rows["fatigue cracking at the bend"]
    proof = plan.items[0]
    assert "upright bending" in proof.driving_checks
    assert bend.prevention_checks == ("upright bending",)
    assert bend.verification_items == (proof.name,)
    assert (bend.occurrence_basis, bend.detection_basis) == ("margin-1.5-to-2", "test-planned")
    loose = rows["joint loosening"]
    assert loose.prevention_checks == ("bolt preload",) and loose.verification_items == ()
    assert loose.detection_basis == "test-named"
    junker = "transverse vibration (Junker) test (named, not on the plan)"
    assert loose.detection_controls == (junker,)
    assert loose.occurrence_basis == "margin-below-1.1" and loose.occurrence == 7
    bearing = rows["bearing yield at the bolt holes"]
    bases = (bearing.occurrence_basis, bearing.detection_basis)
    assert bases == ("margin-2-or-more", "analysis-only")
    assert bearing.prevention == ("bolt bearing (pass)",)


def test_no_severity_no_priority_and_severity_is_named(card, plan):
    rows = fmea(card, FACTS, item="bracket", function="hold", plan=plan, catalog=CATALOG,
                priority_matrix=_matrix()).rows  # fmt: skip
    assert all(row.severity is None and row.priority is None for row in rows)
    assert all("severity" in row.priority_note and "matrix" not in row.priority_note
               for row in rows)  # fmt: skip


def test_without_a_matrix_the_priority_names_the_matrix(card):
    declared = {"joint loosening": FmeaDeclaration(severity=8, effect="motor drops")}
    row = fmea(card, FACTS, item="bracket", function="hold", catalog=CATALOG,
               declared=declared).rows[1]  # fmt: skip
    assert row.priority is None and row.priority_note == (
        "not evaluated — needs an action-priority matrix; none is shipped"
    )
    assert (row.severity, row.effect) == (8, "motor drops")


def _matrix() -> object:
    text = ("severity,occurrence,detection,priority\n9-10,7-10,1-10,H\n9-10,1-6,1-10,M\n"
            "1-8,7-10,8-10,M\n1-8,7-10,1-7,L\n1-8,1-6,1-10,L\n")  # fmt: skip
    return load_action_priority(text, source="ACME DFMEA procedure QP-7.3 rev 4, table 2")


def test_the_users_matrix_computes_priority_and_the_export_names_it(card, plan):
    declared = {
        "joint loosening": FmeaDeclaration(severity=9),
        "fatigue cracking at the bend": FmeaDeclaration(severity=9),
    }
    report = fmea(card, FACTS, item="bracket", function="hold", plan=plan, catalog=CATALOG,
                  declared=declared, priority_matrix=_matrix())  # fmt: skip
    rows = {row.failure_mode: row for row in report.rows}
    assert rows["joint loosening"].priority == "H"  # S9, O7
    assert rows["fatigue cracking at the bend"].priority == "M"  # S9, O3
    assert rows["bearing yield at the bolt holes"].priority is None
    assert "ACME DFMEA procedure QP-7.3 rev 4, table 2" in report.to_csv()


def test_a_recorded_test_is_the_strongest_detection(card, plan):
    done = record_outcome(plan, name=plan.items[0].name, outcome=VerificationOutcome(
        passed=True, measured="held 125 kN", performed_on=date(2026, 11, 21),
        performed_by="J. Rivera", instrument="LC-0042"))  # fmt: skip
    bend = fmea(card, FACTS, item="b", function="f", plan=done, catalog=CATALOG).rows[0]
    assert (bend.detection_basis, bend.detection) == ("test-recorded", 2)


def test_a_failing_check_and_a_check_that_did_not_run():
    card = Scorecard(entries=(_entry("upright bending", 0.8), _entry("bolt preload", None),
                              _entry("bolt bearing", 2.5)))  # fmt: skip
    rows = {r.failure_mode: r for r in fmea(card, FACTS, item="b", function="f",
                                             catalog=CATALOG).rows}  # fmt: skip
    assert rows["fatigue cracking at the bend"].occurrence_basis == "check-fails"
    loose = rows["joint loosening"]  # its only check did not run: it addresses nothing
    assert loose.prevention_checks == () and loose.occurrence_basis == "unaddressed"
    assert loose.occurrence == 10 and loose.detection_basis == "test-named"
    assert card.entries[1].status is CheckStatus.NOT_EVALUATED


def test_the_worst_band_wins_over_several_checks():
    catalog = ModeCatalog(modes=(FailureMode(
        id="bend failure", description="the bend cracks", stage=DiscoveryStage.FIELD,
        applicability=Applicability(elements=("angle_bracket",)), citation="team list",
        addressed_by=("a", "b")),))  # fmt: skip
    card = Scorecard(entries=(_entry("a", 3.0), _entry("b", 1.2)))
    row = fmea(card, FACTS, item="b", function="f", catalog=catalog).rows[0]
    assert row.occurrence_basis == "margin-1.1-to-1.5"


def test_a_users_scale_replaces_the_ranks_and_is_named(card):
    text = "band,rank\n" + "".join(f"{band},{i + 1}\n" for i, band in enumerate(OCCURRENCE_BANDS))
    scale = load_rating_scale(text, kind="occurrence", source="ACME QP-7.3 table 3")
    report = fmea(card, FACTS, item="b", function="f", catalog=CATALOG, occurrence_scale=scale)
    loose = report.rows[1]
    assert loose.occurrence == list(OCCURRENCE_BANDS).index("margin-below-1.1") + 1
    assert report.occurrence_source == "ACME QP-7.3 table 3"


@pytest.mark.parametrize(("text", "said"), [
    ("band,rank\nunaddressed,10\n", "missing"),
    ("band,rank\n" + "".join(f"{b},5\n" for b in OCCURRENCE_BANDS) + "extra,3\n", "unknown"),
    ("band,rank\n" + "".join(f"{b},11\n" for b in OCCURRENCE_BANDS), "1 to 10"),
    ("band,rank\n" + "".join(f"{b},4-5\n" for b in OCCURRENCE_BANDS), "not a range"),
    ("band,rank\nunaddressed,10\nunaddressed,9\n", "twice"),
    ("band,score\nunaddressed,10\n", "header"),
    ("", "empty"),
])  # fmt: skip
def test_a_rating_table_that_leaves_a_band_out_or_off_scale_is_refused(text, said):
    with pytest.raises(RefusalError, match=said):
        load_rating_scale(text, kind="occurrence", source="ACME")


def test_a_table_with_no_source_is_refused():
    with pytest.raises(RefusalError, match="name the document"):
        load_action_priority("severity,occurrence,detection,priority\n1-10,1-10,1-10,L\n",
                             source=" ")  # fmt: skip


@pytest.mark.parametrize(("text", "said"), [
    ("severity,occurrence,detection,priority\n1-9,1-10,1-10,L\n", "have none"),
    ("severity,occurrence,detection,priority\n1-10,1-10,1-10,L\n5,5,5,H\n", "more than one"),
    ("severity,occurrence,detection,priority\n0-10,1-10,1-10,L\n", "within 1 to 10"),
    ("severity,occurrence,detection,priority\nhigh,1-10,1-10,L\n", "a rank 1 to 10"),
    ("severity,occurrence,detection,priority\n1-10,1-10,1-10,\n", "fill each"),
])  # fmt: skip
def test_a_matrix_with_a_gap_or_an_overlap_is_refused(text, said):
    with pytest.raises(RefusalError, match=said):
        load_action_priority(text, source="ACME")


def test_a_declaration_for_a_mode_with_no_row_is_refused(card):
    with pytest.raises(RefusalError, match="not failure modes applying"):
        fmea(card, FACTS, item="b", function="f", catalog=CATALOG,
             declared={"gear tooth surface pitting": FmeaDeclaration(severity=5)})  # fmt: skip


def test_severity_is_a_whole_rank_from_one_to_ten():
    for bad in (0, 11, 5.5, True):
        with pytest.raises(ValueError):
            FmeaDeclaration(severity=bad)


def test_the_csv_and_the_workbook_carry_the_same_rows(card, plan):
    report = fmea(card, FACTS, item="=bracket", function="hold", plan=plan, catalog=CATALOG)
    rows = list(csv.reader(io.StringIO(report.to_csv())))
    assert tuple(rows[0]) == FMEA_COLUMNS
    assert rows[1][0] == "'=bracket"  # a formula lead is written as text
    assert rows[1][FMEA_COLUMNS.index("severity")] == ""
    assert any("never inferred" in r[0] for r in rows if r)
    assert any("floor and never an exhaustive list" in r[0] for r in rows if r)
    with zipfile.ZipFile(io.BytesIO(report.to_xlsx())) as book:
        sheet = book.read("xl/worksheets/sheet1.xml").decode()
        sources = book.read("xl/worksheets/sheet2.xml").decode()
    assert "fatigue cracking at the bend" in sheet and "never inferred" in sources


def test_the_default_catalog_reaches_a_bolted_connection():
    card = Scorecard(entries=(_entry("bolt shear", 2.0),))
    report = fmea(card, {"element": "bolted_connection"}, item="joint", function="clamp")
    loose = next(r for r in report.rows if r.failure_mode == "bolt self-loosening")
    assert loose.detection_basis == "test-named" and loose.occurrence_basis == "unaddressed"
    assert len(report.rows) == len(DEFAULT_CATALOG.applicable({"element": "bolted_connection"}))
    assert "without a severity" in str(report)


def test_the_published_scales_rank_every_band_and_hold_one_back():
    assert set(OCCURRENCE_SCALE.ranks) == set(OCCURRENCE_BANDS)
    assert set(DETECTION_SCALE.ranks) == set(DETECTION_BANDS)
    for scale in (OCCURRENCE_SCALE, DETECTION_SCALE):
        assert 1 not in scale.ranks.values()  # no design record shows a mode cannot occur
        assert "not a reproduction" in scale.source
    order = ["margin-2-or-more", "margin-1.5-to-2", "margin-1.1-to-1.5", "passed-no-margin",
             "margin-below-1.1", "check-fails"]  # fmt: skip
    assert [OCCURRENCE_SCALE.ranks[b] for b in order] == sorted(
        OCCURRENCE_SCALE.ranks[b] for b in order
    )
    detection = ["test-recorded", "test-planned", "inspection-planned", "test-named",
                 "analysis-only", "none"]  # fmt: skip
    assert [DETECTION_SCALE.ranks[b] for b in detection] == sorted(
        DETECTION_SCALE.ranks[b] for b in detection
    )


def test_no_licensed_rating_table_or_priority_matrix_ships():
    """Gate over the bundled data: no action-priority matrix and no handbook table.

    Every file the package carries is read; none may hold a priority matrix's header, and
    none may name the licensed handbooks a matrix or a rating table would be copied from.
    """
    root = Path(anvilate.__file__).parent
    texts = [p for p in root.rglob("*") if p.is_file() and p.suffix in
             {".csv", ".json", ".yaml", ".yml", ".txt", ".toml", ".md"}]  # fmt: skip
    assert len(texts) > 20  # the bundled data is really there to sweep
    for path in texts:
        body = path.read_text(encoding="utf-8", errors="replace").lower()
        assert "severity,occurrence,detection" not in body.replace(" ", ""), path
        for handbook in ("aiag", "vda", "j1739"):
            assert handbook not in body, (path, handbook)
