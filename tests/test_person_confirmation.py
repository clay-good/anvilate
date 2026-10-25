"""Person-only confirmations reach the person, never the agent (add-person-confirmation).

Four decisions are a person's: confirming an agent's reading, writing past a failing gate,
recording a review, consenting to a download. These hold that no tool argument supplies one,
that a client which declared elicitation is asked through an InputRequiredResult (or, on an
older revision, a server request the stdio loop bridges), that a client which did not is told
the shell command and the file form, and that every confirmation carries the channel it came
through into the spec, the card and the bundle.
"""

from __future__ import annotations

import copy
import io
import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from anvilate import mcp
from anvilate.confirmation import (
    PERSON_ONLY_ARGUMENT_NAMES,
    ConfirmationChannel,
    ConfirmationRecord,
    PersonOnlyConfirmation,
    apply_confirmations,
    confirmation_root,
    confirmations_disclosure,
    draft_value_subject,
    find_confirmation,
    record_confirmation,
    unbacked_confirmations,
    was_declined,
)
from anvilate.screening import SOURCE_CONFIRMATION_CHECK
from anvilate.spec import SpecValidationError, load_spec_yaml

_REPO = Path(__file__).resolve().parents[1]
_SHA = "b" * 64
_CLIENT = {"name": "test-client", "version": "9.1"}
_ELICITS = {
    "io.modelcontextprotocol/clientCapabilities": {"elicitation": {}},
    "io.modelcontextprotocol/clientInfo": _CLIENT,
}


def _padeye(**changes) -> dict:
    document = yaml.safe_load((_REPO / "examples" / "padeye.spec.yaml").read_text("utf-8"))
    document.update(changes)
    return document


def _read_width(**extra) -> dict:
    return _padeye(
        sources=[
            {
                "field": "element_params.width",
                "origin": "agent_read",
                "file": "sketch.png",
                "sha256": _SHA,
                "locator": "front view",
                **extra,
            }
        ]
    )


def _call(name: str, arguments: dict, *, meta: dict | None = None, **params) -> dict:
    request_params = {"name": name, "arguments": arguments, **params}
    if meta is not None:
        request_params["_meta"] = meta
    return mcp.handle_request(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": request_params}
    )


def _card(response: dict) -> dict:
    return response["result"]["structuredContent"]["scorecard"]


def _entry_names(card: dict) -> list[str]:
    return [entry["name"] for entry in card["entries"]]


def _spec(document: dict):
    return load_spec_yaml(yaml.safe_dump(document))


# --- the closed list and the catalog gate ---------------------------------------------------


def test_the_list_of_person_only_confirmations_is_closed_at_four():
    assert {member.value for member in PersonOnlyConfirmation} == {
        "draft_value",
        "unvalidated_export",
        "review_record",
        "dataset_consent",
    }


def test_no_tool_input_can_carry_a_person_only_confirmation():
    assert mcp._person_only_argument_issues() == []
    assert mcp.catalog_issues() == []


def test_the_argument_gate_sees_a_confirmation_however_deep_it_is_declared():
    """Attack the gate: a tool that grows `override` two levels down must be caught."""
    (export,) = [tool for tool in mcp.tool_catalog() if tool.name == "export_artifact"]
    schema = copy.deepcopy(export.input_schema)
    schema["properties"]["options"] = {
        "type": "object",
        "properties": {"settings": {"type": "object", "properties": {"override": {}}}},
    }
    tampered = export.model_copy(update={"input_schema": schema})
    issues = mcp._person_only_argument_issues((tampered,))
    assert issues and "export_artifact.options.settings.override" in issues[0]
    assert "override" in PERSON_ONLY_ARGUMENT_NAMES


# --- the source carries its channel ---------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        ({"confirmed_via": "interactive_terminal"}, "names a confirmation channel and no"),
        (
            {
                "confirmed_by": "R. Okafor",
                "confirmed_on": "2026-10-19",
                "confirmed_via": "elicitation",
            },
            "names no client",
        ),
        (
            {"confirmed_by": "R. Okafor", "confirmed_on": "2026-10-19", "confirmed_through": "x 1"},
            "without an elicitation",
        ),
    ],
)
def test_a_channel_is_only_what_it_can_be(extra, reason):
    with pytest.raises(SpecValidationError, match=reason):
        _spec(_read_width(**extra))


def test_each_channel_reads_as_what_it_attests():
    confirmed = {"confirmed_by": "R. Okafor", "confirmed_on": "2026-10-19"}
    terminal = _spec(_read_width(**confirmed, confirmed_via="interactive_terminal")).sources[0]
    answered = _spec(
        _read_width(**confirmed, confirmed_via="elicitation", confirmed_through="test-client 9.1")
    ).sources[0]
    filed = _spec(_read_width(**confirmed, confirmed_via="confirmation_file")).sources[0]
    assert str(terminal).endswith("confirmed by R. Okafor on 2026-10-19 at an interactive terminal")
    assert str(answered).endswith(
        "answered through test-client 9.1 on 2026-10-19, naming R. Okafor"
    )
    assert "confirmed by" not in str(answered)
    assert str(filed).endswith("in a confirmation file")


# --- an agent cannot confirm its own reading ------------------------------------------------


def test_a_confirmation_the_agent_wrote_into_the_document_is_refused_by_name():
    document = _read_width(confirmed_by="R. Okafor", confirmed_on="2026-10-19")
    for tool in ("run_validation", "build_part"):
        refused = _call(tool, {"spec": document})
        assert refused["error"]["code"] == mcp.INVALID_PARAMS, tool
        assert (
            "element_params.width carries a confirmation no person" in refused["error"]["message"]
        )
        assert any("anvilate confirm" in remedy for remedy in refused["error"]["data"]["remedies"])
    compiled = _call("compile_spec", {"document": document})["result"]["structuredContent"]
    assert compiled["errors"] and "element_params.width" in compiled["errors"][0]


def test_a_document_confirmation_counts_when_a_persons_record_backs_it():
    spec = _spec(_read_width())
    record_confirmation(
        ConfirmationRecord(
            confirms=PersonOnlyConfirmation.DRAFT_VALUE,
            subject=draft_value_subject(spec, "element_params.width"),
            person="R. Okafor",
            on=date(2026, 10, 19),
            via=ConfirmationChannel.TERMINAL,
        )
    )
    backed = _read_width(confirmed_by="R. Okafor", confirmed_on="2026-10-19")
    assert unbacked_confirmations(_spec(backed)) == ()
    # Someone else's name, or a channel the record did not come through, is not backed.
    assert unbacked_confirmations(
        _spec(_read_width(confirmed_by="A. Agent", confirmed_on="2026-10-19"))
    ) == ("element_params.width",)
    assert unbacked_confirmations(
        _spec(
            _read_width(
                confirmed_by="R. Okafor",
                confirmed_on="2026-10-19",
                confirmed_via="confirmation_file",
            )
        )
    ) == ("element_params.width",)
    card = _card(_call("run_validation", {"spec": backed}))
    assert SOURCE_CONFIRMATION_CHECK not in _entry_names(card)


# --- elicitation over the current revision --------------------------------------------------


def test_a_client_that_declared_no_elicitation_is_not_asked_and_keeps_the_draft():
    card = _card(_call("run_validation", {"spec": _read_width()}))
    (waiting,) = [e for e in card["entries"] if e["name"] == SOURCE_CONFIRMATION_CHECK]
    assert waiting["status"] == "not_evaluated"
    assert "anvilate confirm" in json.dumps(waiting["needs"])


def test_a_client_that_declared_elicitation_is_asked_with_a_form():
    asked = _call("run_validation", {"spec": _read_width()}, meta=_ELICITS)["result"]
    assert asked["resultType"] == "input_required"
    (request,) = asked["inputRequests"].values()
    assert request["method"] == "elicitation/create"
    params = request["params"]
    assert params["mode"] == "form"
    assert "element_params.width as 120.0 mm from sketch.png (front view)" in params["message"]
    assert "test-client 9.1" in params["message"]
    schema = params["requestedSchema"]
    assert schema["type"] == "object" and set(schema["required"]) == {"correct", "name"}
    # A flat object of primitives, which is all form mode allows.
    assert {p["type"] for p in schema["properties"].values()} == {"boolean", "string"}
    assert isinstance(asked["requestState"], str) and asked["requestState"]


def _retry(first: dict, answer: dict) -> dict:
    (key,) = first["inputRequests"]
    return _call(
        "run_validation",
        {"spec": _read_width()},
        meta=_ELICITS,
        inputResponses={key: answer},
        requestState=first["requestState"],
    )


def test_an_accepted_form_confirms_the_value_through_the_named_client():
    first = _call("run_validation", {"spec": _read_width()}, meta=_ELICITS)["result"]
    done = _retry(first, {"action": "accept", "content": {"correct": True, "name": "R. Okafor"}})
    assert done["result"].get("resultType", "complete") == "complete"
    card = _card(done)
    assert SOURCE_CONFIRMATION_CHECK not in _entry_names(card)
    record = find_confirmation(
        draft_value_subject(_spec(_read_width()), "element_params.width"),
        PersonOnlyConfirmation.DRAFT_VALUE,
    )
    assert record is not None and record.via is ConfirmationChannel.ELICITATION
    assert record.client == "test-client 9.1" and not record.attests_a_person
    # A later call from a client with no elicitation finds the record and is not asked.
    again = _card(_call("run_validation", {"spec": _read_width()}))
    assert SOURCE_CONFIRMATION_CHECK not in _entry_names(again)
    applied = apply_confirmations(_spec(_read_width())).sources[0]
    assert applied.confirmed_via == "elicitation"
    assert applied.confirmed_through == "test-client 9.1"


@pytest.mark.parametrize(
    "answer",
    [
        {"action": "decline"},
        {"action": "cancel"},
        {"action": "accept", "content": {"correct": False, "name": "R. Okafor"}},
        {"action": "accept", "content": {"correct": True, "name": "   "}},
    ],
)
def test_anything_but_an_accepted_ticked_named_form_is_a_decline_and_is_not_asked_again(answer):
    first = _call("run_validation", {"spec": _read_width()}, meta=_ELICITS)["result"]
    done = _retry(first, answer)
    assert done["result"].get("resultType", "complete") == "complete"
    assert SOURCE_CONFIRMATION_CHECK in _entry_names(_card(done))
    assert was_declined(draft_value_subject(_spec(_read_width()), "element_params.width"))
    not_again = _call("run_validation", {"spec": _read_width()}, meta=_ELICITS)
    assert not_again["result"].get("resultType", "complete") == "complete"


def test_a_tampered_or_foreign_request_state_is_no_answer_and_the_person_is_asked_again():
    first = _call("run_validation", {"spec": _read_width()}, meta=_ELICITS)["result"]
    (key,) = first["inputRequests"]
    accept = {"action": "accept", "content": {"correct": True, "name": "R. Okafor"}}
    body, mac = first["requestState"].split(".")
    for state in (f"{body}.{'0' * len(mac)}", "not-a-state", None):
        asked = _call(
            "run_validation",
            {"spec": _read_width()},
            meta=_ELICITS,
            inputResponses={key: accept},
            requestState=state,
        )
        assert asked["result"]["resultType"] == "input_required"
    # The same state presented to another tool answers nothing either.
    other = _call(
        "build_part",
        {"spec": _read_width()},
        meta=_ELICITS,
        inputResponses={key: accept},
        requestState=first["requestState"],
    )
    assert other["result"]["resultType"] == "input_required"
    assert (
        find_confirmation(
            draft_value_subject(_spec(_read_width()), "element_params.width"),
            PersonOnlyConfirmation.DRAFT_VALUE,
        )
        is None
    )


# --- the terminal and the file --------------------------------------------------------------


def test_a_confirmation_file_confirms_and_is_a_file_whatever_it_claims(tmp_path, monkeypatch):
    folder = tmp_path / "out"
    monkeypatch.setenv("ANVILATE_OUT", str(folder))
    subject = draft_value_subject(_spec(_read_width()), "element_params.width")
    (folder / "confirmations").mkdir(parents=True)
    (folder / "confirmations" / "width.json").write_text(
        json.dumps(
            {
                "confirms": "draft_value",
                "subject": subject,
                "person": "R. Okafor",
                "date": "2026-10-19",
                "via": "interactive_terminal",
            }
        )
    )
    (folder / "confirmations" / "garbage.json").write_text("{not json")
    applied = apply_confirmations(_spec(_read_width())).sources[0]
    assert applied.confirmed_via == "confirmation_file"
    assert SOURCE_CONFIRMATION_CHECK not in _entry_names(
        _card(_call("run_validation", {"spec": _read_width()}))
    )


def test_anvilate_never_records_a_file_itself():
    with pytest.raises(ValueError, match="written by the person"):
        record_confirmation(
            ConfirmationRecord(
                confirms=PersonOnlyConfirmation.DRAFT_VALUE,
                subject="c" * 64,
                person="R. Okafor",
                on=date(2026, 10, 19),
                via=ConfirmationChannel.FILE,
            )
        )


def test_a_confirmation_confirms_one_value_from_one_file():
    subject = draft_value_subject(_spec(_read_width()), "element_params.width")
    wider = _read_width()
    wider["element_params"]["width"]["magnitude"] = 121.0
    assert draft_value_subject(_spec(wider), "element_params.width") != subject
    other_file = _read_width()
    other_file["sources"][0]["sha256"] = "d" * 64
    assert draft_value_subject(_spec(other_file), "element_params.width") != subject


def _confirm(subject: str) -> tuple[int, str, str]:
    from anvilate import cli

    out, err = io.StringIO(), io.StringIO()
    code = cli.run(["confirm", subject], stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_confirm_refuses_to_run_without_a_terminal():
    from anvilate import cli

    published = _call("run_validation", {"spec": _read_width()})["result"]["structuredContent"]
    code, _, err = _confirm(published["subject"])
    assert code == cli.EXIT_BAD_REQUEST
    assert "only at an interactive terminal" in err


def test_confirm_at_a_terminal_records_what_the_person_typed(monkeypatch):
    from anvilate import cli

    published = _call("run_validation", {"spec": _read_width()})["result"]["structuredContent"]
    monkeypatch.setattr(cli, "_at_a_terminal", lambda: True)
    answers = iter(["R. Okafor", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    code, shown, _ = _confirm(published["subject"])
    assert code == cli.EXIT_OK, shown
    assert "element_params.width = 120.0 mm, read from sketch.png, front view" in shown
    applied = apply_confirmations(_spec(_read_width())).sources[0]
    assert str(applied).endswith("at an interactive terminal")
    assert (
        confirmation_root()
        / f"{draft_value_subject(_spec(_read_width()), 'element_params.width')}.json"
    ).is_file()


def test_confirm_leaves_a_value_the_person_did_not_confirm_as_a_draft(monkeypatch):
    from anvilate import cli

    published = _call("run_validation", {"spec": _read_width()})["result"]["structuredContent"]
    monkeypatch.setattr(cli, "_at_a_terminal", lambda: True)
    answers = iter(["R. Okafor", "no"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert _confirm(published["subject"])[0] == cli.EXIT_NOT_EVALUATED
    assert apply_confirmations(_spec(_read_width())).sources[0].confirmed_by is None


# --- writing past a failing gate ------------------------------------------------------------


def _failing_screening() -> str:
    document = _padeye()
    document["element_params"]["load"] = {"magnitude": 900.0, "unit": "kN"}
    result = _call("run_validation", {"spec": document})["result"]["structuredContent"]
    assert result["scorecard"]["status"] == "fail"
    return result["subject"]


@pytest.fixture
def out(tmp_path, monkeypatch):
    folder = tmp_path / "out"
    monkeypatch.setenv("ANVILATE_OUT", str(folder))
    return folder


def test_without_elicitation_a_failing_export_names_the_shell_and_the_file(out):
    refused = _call("export_artifact", {"subject": _failing_screening(), "format": "qif"})
    message = refused["error"]["message"]
    assert refused["error"]["code"] == mcp.TOOL_UNAVAILABLE
    assert "anvilate build --unvalidated" in message
    assert '"confirms": "unvalidated_export"' in message and '"subject": "' in message
    assert not list(out.glob("*.qif"))


def test_with_elicitation_a_failing_export_is_written_only_on_the_persons_answer(out):
    handle = _failing_screening()
    first = _call("export_artifact", {"subject": handle, "format": "qif"}, meta=_ELICITS)
    asked = first["result"]
    assert asked["resultType"] == "input_required"
    (key,) = asked["inputRequests"]
    assert (
        "write_unvalidated" in asked["inputRequests"][key]["params"]["requestedSchema"]["required"]
    )
    done = _call(
        "export_artifact",
        {"subject": handle, "format": "qif"},
        meta=_ELICITS,
        inputResponses={
            key: {"action": "accept", "content": {"write_unvalidated": True, "name": "R. Okafor"}}
        },
        requestState=asked["requestState"],
    )["result"]["structuredContent"]
    assert done["validated"] is False
    assert "answered through test-client 9.1" in done["note"]
    assert Path(done["file"]["path"]).is_file()


def test_a_declined_export_is_refused_and_not_asked_again(out):
    handle = _failing_screening()
    asked = _call("export_artifact", {"subject": handle, "format": "qif"}, meta=_ELICITS)["result"]
    (key,) = asked["inputRequests"]
    declined = _call(
        "export_artifact",
        {"subject": handle, "format": "qif"},
        meta=_ELICITS,
        inputResponses={key: {"action": "decline"}},
        requestState=asked["requestState"],
    )
    assert declined["error"]["code"] == mcp.TOOL_UNAVAILABLE
    assert "declined" in declined["error"]["message"]
    again = _call("export_artifact", {"subject": handle, "format": "qif"}, meta=_ELICITS)
    assert "declined to write it unvalidated through a form earlier" in again["error"]["message"]
    assert '"confirms": "unvalidated_export"' in again["error"]["message"]
    assert not list(out.glob("*.qif"))


# --- an older client, bridged by the stream -------------------------------------------------


def _stream(*messages: dict) -> list[dict]:
    sink = io.StringIO()
    mcp.serve_stdio(io.StringIO("\n".join(json.dumps(m) for m in messages) + "\n"), sink)
    return [json.loads(line) for line in sink.getvalue().splitlines()]


def _initialize(capabilities: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": capabilities,
            "clientInfo": {"name": "old-client", "version": "2.1"},
        },
    }


_VALIDATE = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {"name": "run_validation", "arguments": {"spec": _read_width()}},
}


def test_an_older_client_is_sent_a_server_request_and_answered_once():
    out = _stream(
        _initialize({"elicitation": {}}),
        _VALIDATE,
        # A request the client sends while the form is open is held and served after.
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": "anvilate-input-1",
            "result": {"action": "accept", "content": {"correct": True, "name": "R. Okafor"}},
        },
    )
    initialize, server_request, *rest = out
    assert server_request["method"] == "elicitation/create"
    assert server_request["id"] == "anvilate-input-1"
    assert "old-client 2.1" in server_request["params"]["message"]
    by_id = {message["id"]: message for message in rest}
    assert set(by_id) == {2, 3}
    validated = by_id[2]["result"]
    assert "resultType" not in validated  # shaped for the 2025-11-25 revision
    assert SOURCE_CONFIRMATION_CHECK not in _entry_names(
        validated["structuredContent"]["scorecard"]
    )
    assert [message["id"] for message in rest] == [2, 3]


def test_an_older_client_that_declared_no_elicitation_is_never_sent_a_request():
    out = _stream(_initialize({}), _VALIDATE)
    assert [message.get("method") for message in out] == [None, None]
    card = out[1]["result"]["structuredContent"]["scorecard"]
    assert SOURCE_CONFIRMATION_CHECK in _entry_names(card)


def test_what_arrives_while_the_form_is_open_is_answered_in_its_turn():
    """A line that is not JSON gets a parse error, and `null` is not mistaken for one."""
    sink = io.StringIO()
    lines = [
        json.dumps(_initialize({"elicitation": {}})),
        json.dumps(_VALIDATE),
        "{not json",
        "null",
        json.dumps({"jsonrpc": "2.0", "id": "anvilate-input-1", "result": {"action": "decline"}}),
    ]
    mcp.serve_stdio(io.StringIO("\n".join(lines) + "\n"), sink)
    out = [json.loads(line) for line in sink.getvalue().splitlines()]
    codes = [m.get("error", {}).get("code") for m in out[2:]]
    assert codes == [None, mcp.PARSE_ERROR, mcp.INVALID_REQUEST]
    assert out[2]["id"] == 2


def test_an_older_client_that_errors_on_the_request_has_not_confirmed_anything():
    out = _stream(
        _initialize({"elicitation": {"form": {}}}),
        _VALIDATE,
        {"jsonrpc": "2.0", "id": "anvilate-input-1", "error": {"code": -32602, "message": "no"}},
    )
    card = out[-1]["result"]["structuredContent"]["scorecard"]
    assert SOURCE_CONFIRMATION_CHECK in _entry_names(card)


# --- the bundle says how each confirmation arrived ------------------------------------------


def test_the_bundle_states_each_channel_and_whether_any_attests_a_person():
    confirmed = {"confirmed_by": "R. Okafor", "confirmed_on": "2026-10-19"}
    answered = _spec(
        _read_width(**confirmed, confirmed_via="elicitation", confirmed_through="test-client 9.1")
    )
    lines = confirmations_disclosure(answered)
    assert lines[0] == "person-only confirmations:"
    assert "answered through test-client 9.1" in lines[1]
    assert "no confirmation this bundle rests on is attested to a person" in lines[-1]
    typed = _spec(_read_width(**confirmed, confirmed_via="interactive_terminal"))
    assert "typed at an interactive terminal" in confirmations_disclosure(typed)[-1]
    assert "unconfirmed drafts" in confirmations_disclosure(_spec(_read_width()))[-1]
    assert confirmations_disclosure(_spec(_padeye())) == ()

    from anvilate.bundle import BundleSections
    from anvilate.screening import screen_spec

    document = BundleSections(scorecard=screen_spec(answered), spec=answered).render_document()
    assert "person-only confirmations:" in document
    assert "answered through test-client 9.1" in document
