"""Parts as code: a finding on the spec's own line, and a baseline that says what changed.

Three rules. A sweep never writes the baseline it is judged against. A baseline entry
whose spec is gone is reported, not dropped. And a pass is not a result, while a warning
is — a caution nobody is shown is the silent green the rest of this library refuses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.cli_output import run_cli

from anvilate.ci import (
    SARIF_RESULT_LIMIT,
    SARIF_SCHEMA,
    SARIF_VERSION,
    Baseline,
    BaselineEntry,
    Change,
    ScreenedSpec,
    SourceMark,
    compare,
    governing_field,
    locate,
    sarif_json,
    screened,
    source_marks,
    summary_table,
    to_junit,
    to_sarif,
)
from anvilate.derivation import DerivationAbsence, Underived
from anvilate.refusal import RefusalError
from anvilate.scorecard import (
    CheckStatus,
    Direction,
    Need,
    RepairHint,
    Scorecard,
    ScorecardEntry,
    ValueSource,
)

_YAML = """\
anvilate_spec: "1.22.0"
name: bracket
description: A bracket with a thickness worth annotating.
units:
  value: SI
  origin: user_stated
material:
  ref: ASTM-A36
manufacturing:
  process: sheet_metal
element_type: plate
element_params:
  plate_thickness: 6.0
  plate_width: 120.0
"""


def _underived() -> Underived:
    return Underived(
        kind=DerivationAbsence.LOOKUP,
        reason="a fixture entry built to be located and reported",
    )


def _entry(
    name: str,
    status: CheckStatus,
    *,
    detail: str = "a detail line",
    reference: str | None = "AISC 360-16 §F2",
    check_id: str | None = None,
    needs: tuple[Need, ...] = (),
    repair: RepairHint | None = None,
) -> ScorecardEntry:
    return ScorecardEntry(
        name=name,
        check_id=check_id,
        status=status,
        detail=detail,
        reference=reference,
        underived=_underived(),
        needs=needs,
        repair_hint=repair,
    )


def _need(declaration: str) -> Need:
    return Need(
        declaration=declaration,
        takes="the number the document should state",
        sources=(ValueSource.USER,),
    )


def _spec(*entries: ScorecardEntry, path: str = "parts/bracket.yaml") -> ScreenedSpec:
    return screened(path, "bracket", Scorecard(entries=entries), _YAML)


# --- source marks -----------------------------------------------------------------


def test_every_field_of_a_document_has_a_position_a_dotted_path_reaches():
    marks = source_marks(_YAML)

    assert marks["element_params.plate_thickness"].line == 13
    assert marks["element_params.plate_thickness"].column == 20
    assert marks["material.ref"].line == 8
    assert marks[""].line == 1
    # The root is named something a reader of a log can make sense of.
    assert marks[""].path == "(document)"


def test_a_sequence_is_indexed_the_way_a_declaration_names_it():
    marks = source_marks("dimensions:\n  - nominal: 10.0\n  - nominal: 20.0\n")
    assert "dimensions[0].nominal" in marks
    assert marks["dimensions[1].nominal"].line == 3


def test_a_document_that_does_not_parse_yields_no_marks_rather_than_raising():
    """The caller is already on its way to a refusal about the YAML; a second exception
    from the annotation layer would replace that message with one about the annotator."""
    assert source_marks("key: [unclosed\n") == {}
    assert source_marks("") == {}


def test_a_mark_counts_from_one_as_an_editor_and_sarif_both_do():
    with pytest.raises(RefusalError, match="counts from one"):
        SourceMark(path="x", line=0, column=1, end_line=1, end_column=1)
    with pytest.raises(RefusalError, match="counts from one"):
        SourceMark(path="x", line=1, column=0, end_line=1, end_column=1)
    with pytest.raises(RefusalError, match="ends on line"):
        SourceMark(path="x", line=5, column=1, end_line=4, end_column=1)


# --- locating a finding -----------------------------------------------------------


def test_a_check_that_did_not_run_is_located_on_the_declaration_it_needed():
    entry = _entry(
        "plate bending",
        CheckStatus.NOT_EVALUATED,
        needs=(_need("element_params.plate_thickness"),),
    )
    assert governing_field(entry) == "element_params.plate_thickness"
    mark = locate(entry, source_marks(_YAML))
    assert mark is not None and mark.line == 13


def test_a_failing_check_is_located_on_the_parameter_that_repairs_it():
    """A repair hint names a bare parameter; the document writes it under a section."""
    entry = _entry(
        "plate bending",
        CheckStatus.FAIL,
        repair=RepairHint(parameter="plate_thickness", direction=Direction.INCREASE),
    )
    assert governing_field(entry) == "plate_thickness"
    mark = locate(entry, source_marks(_YAML))
    assert mark is not None and mark.line == 13


def test_a_check_about_no_single_field_lands_on_the_document():
    entry = _entry("material resolution", CheckStatus.FAIL)
    assert governing_field(entry) is None
    mark = locate(entry, source_marks(_YAML))
    assert mark is not None and mark.line == 1


def test_a_field_the_document_never_declared_lands_on_the_document_too():
    """Which is the not-evaluated case itself: the declaration missing is why it did not
    run, and annotating a line that does not mention it would be confidently wrong."""
    entry = _entry("fatigue", CheckStatus.NOT_EVALUATED, needs=(_need("duty_cycle.life.value"),))
    mark = locate(entry, source_marks(_YAML))
    assert mark is not None and mark.line == 1


# --- SARIF ------------------------------------------------------------------------


def _log(*entries: ScorecardEntry) -> dict:
    return to_sarif([_spec(*entries)], tool_version="0.0.1")


def test_a_pass_is_not_a_result_and_a_warning_is():
    log = _log(
        _entry("passing", CheckStatus.PASS),
        _entry("deferred", CheckStatus.OUT_OF_DEPTH),
        _entry("cautioned", CheckStatus.WARNING),
        _entry("over", CheckStatus.OVER_MARGIN),
        _entry("broken", CheckStatus.FAIL),
        _entry("unrun", CheckStatus.NOT_EVALUATED),
    )
    results = log["runs"][0]["results"]
    levels = {result["ruleId"]: result["level"] for result in results}

    assert levels == {
        "cautioned": "note",
        "over": "note",
        "broken": "error",
        "unrun": "warning",
    }
    assert "passing" not in levels
    assert "deferred" not in levels


def test_the_rule_is_keyed_on_the_check_id_so_a_rename_is_not_a_new_rule():
    log = _log(
        _entry(
            "bracket-7 plate bending",
            CheckStatus.FAIL,
            check_id="structural.steel.plate_bending",
        )
    )
    rules = log["runs"][0]["tool"]["driver"]["rules"]
    assert [rule["id"] for rule in rules] == ["structural.steel.plate_bending"]
    # The display name and the clause both travel, so a reviewer who has never seen the
    # check has the standard before anything else.
    assert rules[0]["name"] == "bracket-7 plate bending"
    assert rules[0]["help"]["text"] == "AISC 360-16 §F2"


def test_one_rule_per_identity_however_many_specs_report_it():
    one = _spec(_entry("bending", CheckStatus.FAIL), path="parts/a.yaml")
    two = _spec(_entry("bending", CheckStatus.FAIL), path="parts/b.yaml")
    log = to_sarif([one, two], tool_version="0.0.1")
    assert len(log["runs"][0]["tool"]["driver"]["rules"]) == 1
    assert len(log["runs"][0]["results"]) == 2


def test_a_finding_on_a_field_spans_it_and_one_on_the_document_is_a_single_line():
    """The root node runs to the end of the file, and an annotation covering every line
    of a spec highlights the whole file in a diff and says nothing."""
    field = _log(
        _entry(
            "bending",
            CheckStatus.FAIL,
            repair=RepairHint(parameter="plate_thickness", direction=Direction.INCREASE),
        )
    )["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
    assert field["startLine"] == 13 and "endLine" in field

    whole = _log(_entry("material resolution", CheckStatus.FAIL))["runs"][0]["results"][0]
    region = whole["locations"][0]["physicalLocation"]["region"]
    assert region == {"startLine": 1, "startColumn": 1}


def test_the_fingerprint_does_not_move_when_the_declaration_does():
    """Which is what a partial fingerprint is for: a de-duplicating consumer should not
    report the same finding twice because somebody added a comment above it."""
    entry = _entry(
        "bending",
        CheckStatus.FAIL,
        repair=RepairHint(parameter="plate_thickness", direction=Direction.INCREASE),
    )
    before = to_sarif([_spec(entry)], tool_version="0.0.1")
    moved = screened(
        "parts/bracket.yaml", "bracket", Scorecard(entries=(entry,)), "# a comment\n" + _YAML
    )
    after = to_sarif([moved], tool_version="0.0.1")

    assert (
        before["runs"][0]["results"][0]["partialFingerprints"]
        == after["runs"][0]["results"][0]["partialFingerprints"]
    )
    assert (
        before["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
        != after["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
    )


def test_the_category_is_the_automation_id_a_code_scanning_upload_reads():
    log = to_sarif([_spec(_entry("x", CheckStatus.FAIL))], tool_version="0.0.1", category="parts")
    assert log["runs"][0]["automationDetails"]["id"] == "parts"
    with pytest.raises(RefusalError, match="overwrite each other"):
        to_sarif([], tool_version="0.0.1", category="  ")


def test_the_log_declares_the_version_and_schema_a_consumer_validates_against():
    log = _log(_entry("x", CheckStatus.FAIL))
    assert log["version"] == SARIF_VERSION == "2.1.0"
    assert log["$schema"] == SARIF_SCHEMA
    assert SARIF_RESULT_LIMIT == 5_000
    # The required properties of the format, read from the schema's own `required` lists.
    assert set(log) >= {"version", "runs"}
    assert set(log["runs"][0]["tool"]["driver"]) >= {"name"}
    for result in log["runs"][0]["results"]:
        assert "message" in result
        assert result["level"] in {"none", "note", "warning", "error"}
    for rule in log["runs"][0]["tool"]["driver"]["rules"]:
        assert "id" in rule


def test_the_same_cards_give_the_same_bytes():
    spec = _spec(_entry("x", CheckStatus.FAIL), _entry("y", CheckStatus.NOT_EVALUATED))
    assert sarif_json([spec], tool_version="0.0.1") == sarif_json([spec], tool_version="0.0.1")
    assert to_junit([spec]) == to_junit([spec])
    # And nothing clock-shaped is in either.
    for text in (sarif_json([spec], tool_version="0.0.1"), to_junit([spec])):
        assert "timestamp" not in text and "time=" not in text


# --- JUnit ------------------------------------------------------------------------


def test_a_check_that_could_not_run_is_skipped_and_never_a_pass():
    xml = to_junit(
        [
            _spec(
                _entry("passing", CheckStatus.PASS),
                _entry("broken", CheckStatus.FAIL, detail="safety factor 0.80 vs 2.00"),
                _entry("unrun", CheckStatus.NOT_EVALUATED, detail="no yield strength"),
                _entry("deferred", CheckStatus.OUT_OF_DEPTH, detail="concept depth"),
            )
        ]
    )
    assert 'tests="4"' in xml and 'failures="1"' in xml and 'skipped="2"' in xml
    assert '<skipped message="no yield strength"/>' in xml
    assert "safety factor 0.80 vs 2.00" in xml
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')


def test_the_failure_body_carries_the_clause_and_the_repair():
    xml = to_junit(
        [
            _spec(
                _entry(
                    "bending",
                    CheckStatus.FAIL,
                    repair=RepairHint(parameter="plate_thickness", direction=Direction.INCREASE),
                )
            )
        ]
    )
    assert "AISC 360-16" in xml
    assert "plate_thickness" in xml


def test_a_name_with_xml_in_it_cannot_break_the_report():
    xml = to_junit(
        [
            _spec(
                _entry(
                    '<bad & "quoted">',
                    CheckStatus.FAIL,
                    detail='a detail with <tags> & "quotes"',
                )
            )
        ]
    )
    import xml.etree.ElementTree as ET

    tree = ET.fromstring(xml)
    case = tree.find("./testsuite/testcase")
    assert case is not None and case.get("name") == '<bad & "quoted">'


def test_an_empty_run_is_a_well_formed_report_and_not_an_empty_file():
    import xml.etree.ElementTree as ET

    tree = ET.fromstring(to_junit([]))
    assert tree.tag == "testsuites" and tree.get("tests") == "0"


# --- the baseline -----------------------------------------------------------------


def _baseline_of(*specs: ScreenedSpec) -> Baseline:
    return Baseline.of(specs)


def test_a_baseline_records_one_entry_per_spec_in_path_order():
    base = _baseline_of(
        _spec(_entry("x", CheckStatus.PASS), path="parts/b.yaml"),
        _spec(_entry("x", CheckStatus.PASS), path="parts/a.yaml"),
    )
    assert [entry.path for entry in base.entries] == ["parts/a.yaml", "parts/b.yaml"]
    assert Baseline.parse(base.to_json()) == base
    assert base.to_json() == base.to_json()


def test_two_recorded_states_for_one_spec_are_refused():
    entry = BaselineEntry(path="parts/a.yaml", digest="d", status=CheckStatus.PASS)
    with pytest.raises(RefusalError, match="more than once"):
        Baseline(entries=(entry, entry))


def test_a_baseline_file_that_is_not_json_says_so():
    with pytest.raises(RefusalError, match="not readable JSON"):
        Baseline.parse("{not json")


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (CheckStatus.PASS, CheckStatus.FAIL, Change.NEWLY_FAILING),
        (CheckStatus.PASS, CheckStatus.NOT_EVALUATED, Change.NEWLY_NOT_EVALUATED),
        (CheckStatus.FAIL, CheckStatus.PASS, Change.NEWLY_PASSING),
        (CheckStatus.NOT_EVALUATED, CheckStatus.PASS, Change.NEWLY_PASSING),
    ],
)
def test_a_changed_verdict_is_classified_by_which_way_it_went(before, after, expected):
    was = Baseline(entries=(BaselineEntry(path="parts/a.yaml", digest="old", status=before),))
    now = _spec(_entry("x", after), path="parts/a.yaml")
    (line,) = compare(was, [now])
    assert line.change is expected
    assert line.before is before and line.after is after


def test_the_same_verdict_from_a_different_card_is_a_change_and_names_the_governing_one():
    now = _spec(
        _entry("bending", CheckStatus.FAIL),
        _entry("bearing", CheckStatus.PASS),
        path="parts/a.yaml",
    )
    was = Baseline(
        entries=(
            BaselineEntry(
                path="parts/a.yaml",
                digest="old",
                status=CheckStatus.FAIL,
                governing="bearing",
            ),
        )
    )
    (line,) = compare(was, [now])
    assert line.change is Change.GOVERNING_CHANGED
    assert "bearing -> bending" in line.detail


def test_an_unchanged_card_is_reported_as_unchanged_and_not_omitted():
    """A table listing only the news cannot tell "nothing changed" from "it did not run"."""
    spec = _spec(_entry("x", CheckStatus.PASS), path="parts/a.yaml")
    (line,) = compare(Baseline.of([spec]), [spec])
    assert line.change is Change.UNCHANGED
    assert not line.change.is_news


def test_a_spec_the_baseline_does_not_know_is_new():
    (line,) = compare(Baseline(), [_spec(_entry("x", CheckStatus.PASS), path="parts/a.yaml")])
    assert line.change is Change.NEW
    assert not line.change.is_news


def test_a_baseline_entry_whose_spec_is_gone_is_reported_and_is_news():
    was = Baseline(
        entries=(BaselineEntry(path="parts/gone.yaml", digest="d", status=CheckStatus.PASS),)
    )
    (line,) = compare(was, [])
    assert line.change is Change.MISSING
    assert line.change.is_news
    assert "did not find it" in line.detail


def test_good_news_is_not_news_a_gate_stops_for():
    """Failing a run because a part started passing is how people learn to ignore runs."""
    assert not Change.NEWLY_PASSING.is_news
    assert Change.NEWLY_FAILING.is_news
    assert Change.NEWLY_NOT_EVALUATED.is_news


def test_the_summary_table_puts_the_news_first_and_counts_the_rest():
    was = Baseline(
        entries=(
            BaselineEntry(path="parts/a.yaml", digest="old", status=CheckStatus.PASS),
            BaselineEntry(path="parts/gone.yaml", digest="d", status=CheckStatus.PASS),
        )
    )
    now = [_spec(_entry("x", CheckStatus.FAIL), path="parts/a.yaml")]
    table = summary_table(compare(was, now))
    rows = [line for line in table.splitlines() if line.startswith("| `")]

    assert len(rows) == 2
    assert "newly_failing" in rows[0] or "missing" in rows[0]
    assert "2 specs:" in table
    assert "2 of them are news" in table


def test_an_empty_sweep_says_so_rather_than_drawing_an_empty_table():
    table = summary_table(())
    assert "no specs screened" in table
    assert "Nothing a gate stops for." in table


def test_one_piece_of_news_reads_in_the_singular():
    was = Baseline(
        entries=(BaselineEntry(path="parts/gone.yaml", digest="d", status=CheckStatus.PASS),)
    )
    assert "1 of them is news" in summary_table(compare(was, []))


# --- through the CLI ---------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    folder = tmp_path / "parts"
    folder.mkdir()
    for name in ("base_plate", "cover_plate"):
        source = Path(__file__).resolve().parent.parent / "examples" / f"{name}.spec.yaml"
        (folder / f"{name}.yaml").write_text(source.read_text(), encoding="utf-8")
    return folder


def test_the_cli_writes_a_baseline_only_when_asked_and_exits_zero(repo, tmp_path):
    baseline = tmp_path / "baseline.json"
    code, _out, err = run_cli("check", str(repo), "--write-baseline", str(baseline))

    assert code == 0
    assert "commit it" in err
    recorded = Baseline.parse(baseline.read_text())
    assert len(recorded.entries) == 2

    # A sweep against it writes nothing.
    before = baseline.read_text()
    run_cli("check", str(repo), "--baseline", str(baseline))
    assert baseline.read_text() == before


def test_the_cli_fails_on_news_even_when_every_card_passes(repo, tmp_path):
    baseline = tmp_path / "baseline.json"
    run_cli("check", str(repo), "--write-baseline", str(baseline))
    # Every card still passes; what changed is that a part the baseline records is gone.
    gone = repo / "cover_plate.yaml"
    text = gone.read_text()
    gone.unlink()

    code, _out, err = run_cli("check", str(repo), "--baseline", str(baseline))
    assert code == 1
    assert "missing" in err

    gone.write_text(text, encoding="utf-8")
    code, _out, err = run_cli("check", str(repo), "--baseline", str(baseline))
    assert code == 0
    assert "missing" not in err


def test_the_cli_writes_both_reports_and_the_summary(repo, tmp_path):
    baseline = tmp_path / "baseline.json"
    run_cli("check", str(repo), "--write-baseline", str(baseline))
    sarif, junit, summary = (
        tmp_path / "out" / "a.sarif",
        tmp_path / "out" / "a.xml",
        tmp_path / "summary.md",
    )
    code, _out, _err = run_cli(
        "check",
        str(repo),
        "--sarif",
        str(sarif),
        "--sarif-category",
        "parts",
        "--junit",
        str(junit),
        "--baseline",
        str(baseline),
        "--summary",
        str(summary),
    )

    assert code == 0
    log = json.loads(sarif.read_text())
    assert log["version"] == "2.1.0"
    assert log["runs"][0]["automationDetails"]["id"] == "parts"
    assert "<testsuites" in junit.read_text()
    assert "| Spec | Change |" in summary.read_text()
    # The summary is appended, as $GITHUB_STEP_SUMMARY is.
    run_cli("check", str(repo), "--baseline", str(baseline), "--summary", str(summary))
    assert summary.read_text().count("| Spec | Change |") == 2


def test_a_summary_with_nothing_to_compare_against_is_a_bad_request(repo, tmp_path):
    code, _out, err = run_cli("check", str(repo), "--summary", str(tmp_path / "s.md"))
    assert code == 3
    assert "needs --baseline" in err


def test_an_unreadable_baseline_is_a_bad_request_and_not_a_crash(repo, tmp_path):
    code, _out, err = run_cli("check", str(repo), "--baseline", str(tmp_path / "nope.json"))
    assert code == 3
    assert "cannot read" in err


def test_the_cli_report_locates_a_finding_on_the_spec_it_came_from(repo, tmp_path):
    """End to end: a real spec, screened, with a real not-evaluated check annotated."""
    broken = repo / "base_plate.yaml"
    broken.write_text(
        broken.read_text().replace("ref: ASTM-A36", "ref: NOT-A-MATERIAL"), encoding="utf-8"
    )
    sarif = tmp_path / "a.sarif"
    code, _out, _err = run_cli("check", str(repo), "--sarif", str(sarif))

    assert code in (1, 2)
    log = json.loads(sarif.read_text())
    results = log["runs"][0]["results"]
    assert results, "a card that did not fully evaluate produced no SARIF result"
    located = {
        result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] for result in results
    }
    assert any(uri.endswith("base_plate.yaml") for uri in located)


def test_the_pre_commit_hook_entry_names_a_command_the_cli_has():
    """The hook file is the least-tested code in most repositories: nothing imports it."""
    import yaml as yaml_module

    from anvilate.cli import _build_parser

    hooks = yaml_module.safe_load(
        (Path(__file__).resolve().parent.parent / ".pre-commit-hooks.yaml").read_text()
    )
    commands = _build_parser()._subparsers._group_actions[0].choices  # noqa: SLF001
    assert hooks, "the hook file declares nothing"
    for hook in hooks:
        words = hook["entry"].split()
        assert words[0] == "anvilate"
        assert words[1] in commands, f"the hook runs `{hook['entry']}` and there is no such command"
        assert hook["id"] and hook["description"]


def test_the_log_validates_against_the_published_sarif_schema():
    """The offline tests above check the shape this writer promises; this one checks the
    format itself, against OASIS's own schema, in the scheduled `interchange-schemas` job.

    Skipped without `ANVILATE_SARIF_SCHEMA`, and that job fails on a skip — a green run
    over a validation that never happened is the outcome it exists to rule out.
    """
    import os

    import jsonschema

    where = os.environ.get("ANVILATE_SARIF_SCHEMA")
    if not where or not Path(where).exists():
        pytest.skip("set ANVILATE_SARIF_SCHEMA to the published sarif-schema-2.1.0.json")

    schema = json.loads(Path(where).read_text(encoding="utf-8"))
    log = to_sarif(
        [
            _spec(
                _entry("passing", CheckStatus.PASS),
                _entry(
                    "bending",
                    CheckStatus.FAIL,
                    check_id="structural.steel.plate_bending",
                    repair=RepairHint(parameter="plate_thickness", direction=Direction.INCREASE),
                ),
                _entry("unrun", CheckStatus.NOT_EVALUATED, needs=(_need("material.ref"),)),
                _entry("cautioned", CheckStatus.WARNING),
            )
        ],
        tool_version="0.0.1",
        category="parts",
    )
    # Draft-04, which is what the published SARIF schema declares.
    validator = jsonschema.validators.validator_for(schema)(schema)
    errors = sorted(validator.iter_errors(log), key=lambda error: list(error.absolute_path))
    assert not errors, "\n".join(
        f"{'/'.join(map(str, error.absolute_path))}: {error.message}" for error in errors[:5]
    )


def test_the_docs_page_quotes_the_limit_and_the_levels_the_code_uses():
    """The page argues from the 5,000-result limit and from the verdict-to-level table;
    both are read back from the code rather than trusted."""
    import re

    page = (Path(__file__).resolve().parent.parent / "docs" / "parts-as-code.md").read_text()

    quoted = re.findall(r"([\d,]{5,}) results", page)
    assert quoted, "the page's result limit has moved"
    for number in quoted:
        assert int(number.replace(",", "")) == SARIF_RESULT_LIMIT

    # Every row of the page's verdict table is what `to_sarif` and `to_junit` actually do.
    rows = re.findall(r"^\| `(\w+)` \| (`\w+`|—) \| (\*\*skipped\*\*[^|]*|\w+) \|$", page, re.M)
    assert len(rows) == len(CheckStatus), f"the page's table lists {len(rows)} verdicts"
    for name, level, junit in rows:
        status = CheckStatus(name)
        log = to_sarif([_spec(_entry("x", status))], tool_version="0.0.1")
        results = log["runs"][0]["results"]
        if level == "—":
            assert not results, f"the page says {name} is not a SARIF result and it is"
        else:
            assert results and results[0]["level"] == level.strip("`"), (
                f"the page says {name} reports at {level}"
            )
        xml = to_junit([_spec(_entry("x", status))])
        wanted = "skipped" if "skipped" in junit else junit.strip()
        assert wanted in {"skipped", "failure", "pass"}, f"the page's JUnit column says {junit!r}"
        assert ("<skipped" in xml) is (wanted == "skipped"), (
            f"the page says {name} is {wanted} in JUnit"
        )
        assert ("<failure" in xml) is (wanted == "failure"), (
            f"the page says {name} is {wanted} in JUnit"
        )


# --- products ----------------------------------------------------------------------


_PRODUCTS = Path(__file__).resolve().parent.parent / "examples" / "products"
_PRODUCT = _PRODUCTS / "gear_reducer.product.yaml"


def test_a_product_node_is_annotated_on_the_definition_it_instantiates():
    """A node has no fields of its own in the file; the definition is what a reader edits."""
    from anvilate.ci import definition_marks

    text = _PRODUCT.read_text()
    marks = definition_marks(text)
    assert marks, "the product document declares definitions and none were found"
    assert all(mark.line > 1 for mark in marks.values())
    assert all(mark.path.startswith("definitions[") for mark in marks.values())


def test_a_document_with_no_definitions_block_yields_no_definition_marks():
    from anvilate.ci import definition_marks

    assert definition_marks("name: x\n") == {}
    assert definition_marks("definitions: not-a-list\n") == {}
    assert definition_marks("[") == {}


def test_the_cli_locates_every_product_node_on_its_own_definition(tmp_path):
    sarif = tmp_path / "p.sarif"
    code, _out, _err = run_cli("check", str(_PRODUCT), "--sarif", str(sarif))

    assert code in (0, 1, 2)
    log = json.loads(sarif.read_text())
    results = log["runs"][0]["results"]
    assert results, "the product screened to no SARIF result"
    lines = {
        result["locations"][0]["physicalLocation"]["region"]["startLine"] for result in results
    }
    # Not all on line one: each node reached a definition of its own.
    assert lines != {1}
    # And a fallback region is one line, never a definition block's whole span.
    for result in results:
        region = result["locations"][0]["physicalLocation"]["region"]
        if "endLine" not in region:
            assert set(region) == {"startLine", "startColumn"}


def test_a_product_baseline_records_one_entry_per_node(tmp_path):
    baseline = tmp_path / "baseline.json"
    code, _out, err = run_cli("check", str(_PRODUCT), "--write-baseline", str(baseline))

    assert code == 0
    assert "nodes" in err
    recorded = Baseline.parse(baseline.read_text())
    assert len(recorded.entries) > 1
    assert all("gear-reducer" in entry.path or entry.path for entry in recorded.entries)

    # A second run against it is unchanged, and writes nothing.
    before = baseline.read_text()
    code, _out, err = run_cli("check", str(_PRODUCT), "--baseline", str(baseline))
    assert baseline.read_text() == before
    assert "missing" not in err


def test_a_mark_and_a_baseline_each_render_what_a_reader_needs():
    """Both are read in a log line, so both have to say what they are about."""
    mark = SourceMark(path="element_params.plate_thickness", line=13, column=20,
                      end_line=13, end_column=23)  # fmt: skip
    assert str(mark) == "element_params.plate_thickness at line 13, column 20"

    base = Baseline.of([_spec(_entry("x", CheckStatus.PASS))])
    assert str(base) == "baseline 1.0: 1 specs"
    assert str(Baseline()) == "baseline 1.0: 0 specs"
