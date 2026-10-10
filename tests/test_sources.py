"""A value can cite the file it came from, and an agent's reading is a draft until confirmed.

add-agent-context-intake, group 1. A spec's `sources` say where a value came from: the file,
its SHA-256, where in it, whether Anvilate measured it or an agent read it, and who confirmed
an agent's reading. These hold the consequences: an unconfirmed reading is used and marked,
it cannot export as validated, a confirmation names a person, and a cited file that has
changed since the value was taken from it fails the check.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from anvilate.scorecard import CheckStatus
from anvilate.screening import CITED_SOURCES_CHECK, SOURCE_CONFIRMATION_CHECK, screen_spec
from anvilate.spec import SpecValidationError, dump_spec_yaml, load_spec_yaml

_REPO = Path(__file__).resolve().parents[1]
_SHA = "a" * 64


def _lug(*sources: dict, **changes) -> dict:
    """The padeye example, citing ``sources``."""
    document = yaml.safe_load((_REPO / "examples" / "padeye.spec.yaml").read_text("utf-8"))
    document["sources"] = [copy.deepcopy(source) for source in sources]
    document.update(changes)
    return document


def _spec(document: dict):
    return load_spec_yaml(yaml.safe_dump(document))


def _read(field: str = "element_params.width", **extra) -> dict:
    return {
        "field": field,
        "origin": "agent_read",
        "file": "sketch.png",
        "sha256": _SHA,
        "locator": "front view, overall width",
        **extra,
    }


_CONFIRMED = {"confirmed_by": "R. Okafor", "confirmed_on": "2026-10-10"}


def test_a_source_says_where_a_value_came_from_and_survives_a_round_trip():
    spec = _spec(_lug(_read(), _read("element_params.thickness", origin="measured_from_file")))
    read, measured = spec.sources
    assert str(read) == (
        "element_params.width: read by an agent from sketch.png, front view, overall width; "
        "unconfirmed"
    )
    assert str(measured).startswith("element_params.thickness: measured from sketch.png")
    assert (read.confirmed, measured.confirmed) == (False, True)
    assert load_spec_yaml(dump_spec_yaml(spec)) == spec
    assert type(spec).model_validate_json(spec.model_dump_json()) == spec
    confirmed = _spec(_lug(_read(**_CONFIRMED))).sources[0]
    assert confirmed.confirmed and "confirmed by R. Okafor on 2026-10-10" in str(confirmed)


@pytest.mark.parametrize(
    ("sources", "reason"),
    [
        ([_read("element_params.depth")], "the document states no such value"),
        ([_read("element_params.width[2]")], "the document states no such value"),
        ([_read("nowhere.at.all")], "the document states no such value"),
        ([_read("element_params..width")], "is not a path to a value"),
        ([_read("element_params.width; rm -rf")], "is not a path to a value"),
        ([_read(), _read()], "more than once"),
        ([_read(confirmed_by="R. Okafor")], "confirmed without confirmed_on"),
        ([_read(confirmed_on="2026-10-10")], "confirmed without confirmed_by"),
        ([_read(confirmed_by="  ", confirmed_on="2026-10-10")], "confirmed_by"),
        ([_read(sha256="abc")], "sha256"),
        ([_read(origin="guessed")], "origin"),
        ([_read(file="")], "file"),
    ],
)
def test_a_source_that_cites_nothing_real_is_refused(sources, reason):
    with pytest.raises(SpecValidationError, match=reason):
        _spec(_lug(*sources))


def test_an_agent_cannot_confirm_its_own_reading_without_naming_a_person():
    """The scenario in the spec: a confirmation with no named person is refused."""
    for attempt in (
        {"confirmed_on": "2026-10-10"},
        {"confirmed_by": "", "confirmed_on": "2026-10-10"},
    ):
        with pytest.raises(SpecValidationError):
            _spec(_lug(_read(**attempt)))


def test_a_value_that_says_it_came_from_a_file_names_the_file():
    factor = {"min_safety_factor": {"value": 2.0, "origin": "agent_read"}}
    with pytest.raises(SpecValidationError, match="no source names the file"):
        _spec(_lug(constraints=factor))
    cited = _spec(_lug(_read("constraints.min_safety_factor"), constraints=factor))
    assert cited.constraints.min_safety_factor.origin.value == "agent_read"
    stated = {"min_safety_factor": {"value": 2.0, "origin": "user_stated"}}
    with pytest.raises(SpecValidationError, match="they are one fact and must agree"):
        _spec(_lug(_read("constraints.min_safety_factor"), constraints=stated))


def test_every_origin_has_a_label_a_reviewer_reads():
    """An origin added after the report was written renders as a KeyError, or as nothing."""
    from anvilate.report.document import _ORIGIN_LABEL
    from anvilate.spec.provenance import Origin

    assert set(_ORIGIN_LABEL) == set(Origin)
    assert _ORIGIN_LABEL[Origin.AGENT_READ] == "read by an agent"
    assert _ORIGIN_LABEL[Origin.MEASURED_FROM_FILE] == "measured from a file"


def test_an_unconfirmed_reading_is_used_and_marked():
    spec = _spec(_lug(_read(), _read("element_params.thickness", locator=None)))
    card = screen_spec(spec)
    tension = next(entry for entry in card.entries if entry.name.endswith("net tension"))
    assert tension.status is CheckStatus.PASS
    assert "rests on 2 unconfirmed readings (width, thickness)" in tension.detail
    waiting = next(entry for entry in card.entries if entry.name == SOURCE_CONFIRMATION_CHECK)
    assert waiting.status is CheckStatus.NOT_EVALUATED
    assert "2 values were read by an agent" in waiting.detail
    assert "element_params.width from sketch.png (front view, overall width)" in waiting.detail
    # A source with no locator is named without the brackets.
    assert "element_params.thickness from sketch.png. The part is drawn" in waiting.detail
    assert [need.declaration for need in waiting.needs] == ["sources[].confirmed_by"]
    assert not card.passed and card.status is CheckStatus.NOT_EVALUATED


def test_one_reading_is_said_in_the_singular():
    card = screen_spec(_spec(_lug(_read())))
    waiting = next(entry for entry in card.entries if entry.name == SOURCE_CONFIRMATION_CHECK)
    assert waiting.detail.startswith("1 value was read by an agent from a file and no person")
    tension = next(entry for entry in card.entries if entry.name.endswith("net tension"))
    assert "rests on 1 unconfirmed reading (width): an agent read it" in tension.detail


def test_a_confirmed_reading_and_a_measurement_ask_for_nothing():
    plain = screen_spec(_spec(_lug()))
    for sources in (
        [_read(**_CONFIRMED)],
        [_read(origin="measured_from_file")],
        [_read(**_CONFIRMED), _read("element_params.thickness", origin="measured_from_file")],
    ):
        card = screen_spec(_spec(_lug(*sources)))
        assert [(e.name, e.status, e.detail) for e in card.entries] == [
            (e.name, e.status, e.detail) for e in plain.entries
        ]
        assert card.passed


def test_a_draft_cannot_export_as_validated():
    from anvilate.export.gate import ExportRefused, authorize_export

    card = screen_spec(_spec(_lug(_read())))
    with pytest.raises(ExportRefused, match=SOURCE_CONFIRMATION_CHECK):
        authorize_export(card)
    marked = authorize_export(card, override=True)
    assert marked.validated is False and SOURCE_CONFIRMATION_CHECK in marked.blocking
    assert authorize_export(screen_spec(_spec(_lug(_read(**_CONFIRMED))))).validated is True


def test_the_needs_report_says_who_has_to_do_what():
    from anvilate.needs import needs_report

    report = needs_report(screen_spec(_spec(_lug(_read()))))
    assert "sources[].confirmed_by" in str(report) and "the name of the person" in str(report)


def test_the_bundle_carries_where_each_value_came_from():
    from cli_output import run_cli

    path = _REPO / "examples" / "context" / "plate_from_drawing.spec.yaml"
    code, raw, _err = run_cli(
        "export", str(path), "--artifact", "evidence-bundle", "--format", "json"
    )
    sources = json.loads(raw)["bundles"][0]["bundle"]["spec"]["sources"]
    assert [source["field"] for source in sources] == [
        "element_params.width",
        "element_params.length",
        "element_params.hole_patterns[0].diameter",
    ]
    assert {source["file"] for source in sources} == {"plate.dxf"} and code in (0, 2)


# --- the cited file -------------------------------------------------------------------


def _beside(tmp_path: Path, content: bytes = b"\x89PNG as it was read") -> tuple[Path, dict]:
    (tmp_path / "sketch.png").write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    document = _lug(_read(sha256=digest, **_CONFIRMED))
    (tmp_path / "lug.yaml").write_text(yaml.safe_dump(document), encoding="utf-8")
    return tmp_path / "lug.yaml", document


def test_a_cited_file_that_still_matches_passes_and_one_that_changed_fails(tmp_path):
    _path, document = _beside(tmp_path)
    spec = _spec(document)
    held = next(
        e
        for e in screen_spec(spec, source_roots=(tmp_path,)).entries
        if e.name == CITED_SOURCES_CHECK
    )
    assert held.status is CheckStatus.PASS and "1 cited file matches" in held.detail
    (tmp_path / "sketch.png").write_bytes(b"\x89PNG redrawn since")
    card = screen_spec(spec, source_roots=(tmp_path,))
    stale = next(e for e in card.entries if e.name == CITED_SOURCES_CHECK)
    assert stale.status is CheckStatus.FAIL and not card.passed
    assert "sketch.png has changed since element_params.width was taken from it" in stale.detail
    assert "Read the file again" in stale.detail


def test_a_file_that_cannot_be_found_is_not_judged(tmp_path):
    _path, document = _beside(tmp_path)
    spec = _spec(document)
    (tmp_path / "sketch.png").unlink()
    for roots in ((), (tmp_path,), (tmp_path / "missing",)):
        names = [entry.name for entry in screen_spec(spec, source_roots=roots).entries]
        assert CITED_SOURCES_CHECK not in names


def test_some_found_and_some_not_says_how_many_of_each(tmp_path):
    _path, document = _beside(tmp_path)
    document["sources"].append(
        _read("element_params.thickness", file="datasheet.pdf", origin="measured_from_file")
    )
    held = next(
        entry
        for entry in screen_spec(_spec(document), source_roots=(tmp_path,)).entries
        if entry.name == CITED_SOURCES_CHECK
    )
    assert held.status is CheckStatus.PASS
    assert "1 cited file matches" in held.detail and "1 could not be found to check" in held.detail


def test_checking_a_spec_looks_for_its_sources_beside_it(tmp_path):
    from cli_output import run_cli

    path, _document = _beside(tmp_path)
    code, out, _err = run_cli("check", str(path))
    assert code == 0 and "cited sources" in out and "1 cited file matches" in out
    (tmp_path / "sketch.png").write_bytes(b"\x89PNG redrawn since")
    code, out, _err = run_cli("check", str(path))
    assert code == 1 and "sketch.png has changed since" in out


def test_the_server_looks_for_sources_in_its_context_folders(tmp_path):
    from anvilate import context
    from anvilate.mcp import handle_request

    _path, document = _beside(tmp_path)

    def names() -> list[str]:
        reply = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "run_validation", "arguments": {"spec": document}},
            }
        )
        return [e["name"] for e in reply["result"]["structuredContent"]["scorecard"]["entries"]]

    assert CITED_SOURCES_CHECK not in names()
    context.set_context_roots([tmp_path])
    assert CITED_SOURCES_CHECK in names()


def test_the_shipped_example_cites_the_drawing_beside_it_and_the_numbers_are_the_drawings():
    """The example is the worked session: its values are what the reader measures from
    plate.dxf, and its digest is that file's."""
    pytest.importorskip("ezdxf")
    from anvilate.context import read_cad_file

    folder = _REPO / "examples" / "context"
    spec = load_spec_yaml((folder / "plate_from_drawing.spec.yaml").read_text("utf-8"))
    facts = read_cad_file(folder / "plate.dxf")
    assert {source.sha256 for source in spec.sources} == {facts.sha256}
    assert all(source.origin == "measured_from_file" for source in spec.sources)
    (plate,) = facts.profiles
    params = spec.element_params
    assert params["width"].to("mm").magnitude == plate.width_mm == 101.6
    assert params["length"].to("mm").magnitude == plate.height_mm == 76.2
    pattern = params["hole_patterns"][0]
    assert (
        {hole.diameter_mm for hole in plate.holes} == {pattern["diameter"]["magnitude"]} == {6.35}
    )
    assert {abs(hole.x_mm) * 2 for hole in plate.holes} == {pattern["pitch_x"]["magnitude"]}
    assert {abs(hole.y_mm) * 2 for hole in plate.holes} == {pattern["pitch_y"]["magnitude"]}
    card = screen_spec(spec, source_roots=(folder,))
    held = next(entry for entry in card.entries if entry.name == CITED_SOURCES_CHECK)
    assert held.status is CheckStatus.PASS and "3 cited files match" in held.detail


def test_a_part_resting_on_a_reading_is_written_marked_unvalidated_over_mcp(tmp_path, monkeypatch):
    pytest.importorskip("build123d")
    from anvilate.mcp import handle_request

    monkeypatch.setenv("ANVILATE_OUT", str(tmp_path / "out"))
    document = yaml.safe_load(
        (_REPO / "examples" / "transmission_shaft.spec.yaml").read_text("utf-8")
    )
    document["sources"] = [_read("element_params.diameter")]

    def call(name: str, arguments: dict) -> dict:
        return handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )

    built = call("build_part", {"spec": document})["result"]["structuredContent"]["subject"]
    body = call("export_artifact", {"subject": built, "format": "step"})["result"][
        "structuredContent"
    ]
    assert body["validated"] is False
    assert (
        "1 value(s) were read by an agent" in body["note"]
        and "element_params.diameter" in body["note"]
    )
    assert "UNVALIDATED" in Path(body["file"]["path"]).read_text(encoding="utf-8", errors="replace")
    # Confirmed, the same part exports as validated and says nothing.
    document["sources"] = [_read("element_params.diameter", **_CONFIRMED)]
    built = call("build_part", {"spec": document})["result"]["structuredContent"]["subject"]
    body = call("export_artifact", {"subject": built, "format": "step"})["result"][
        "structuredContent"
    ]
    assert "validated" not in body


def test_a_failed_check_is_still_refused_whatever_was_read(tmp_path, monkeypatch):
    """Only a draft is written marked unvalidated. A part that fails is refused."""
    pytest.importorskip("build123d")
    from anvilate.mcp import _drawn_and_not_checked
    from anvilate.scorecard import Scorecard, ScorecardEntry

    spec = _spec(_lug(_read()))

    def card(*entries: tuple[str, CheckStatus]) -> Scorecard:
        return Scorecard(
            entries=tuple(ScorecardEntry(name=n, status=s, detail="d") for n, s in entries)
        )

    waiting = (SOURCE_CONFIRMATION_CHECK, CheckStatus.NOT_EVALUATED)
    assert _drawn_and_not_checked(spec, card(("strength", CheckStatus.PASS), waiting))
    assert not _drawn_and_not_checked(spec, card(("strength", CheckStatus.FAIL), waiting))
    # A screened part with a check that could not run is not a draft either.
    assert not _drawn_and_not_checked(spec, card(("strength", CheckStatus.NOT_EVALUATED), waiting))
    assert not _drawn_and_not_checked(spec, card(("strength", CheckStatus.PASS)))
