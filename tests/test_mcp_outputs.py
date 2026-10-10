"""What the MCP server writes, where, and under which gate (simplify-visual-output).

The server has one output folder, named by the user when it starts. Every file a tool
produces lands there under a name derived from the part; no tool takes a destination; a CAD
file is written only when the part's checks pass; and the bundle and the sheet are written
whatever the verdict, because a document saying a part failed is the one a refusal withholds.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from anvilate import _outputs
from anvilate.mcp import handle_request, tool_catalog

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _call(name: str, arguments: dict) -> dict:
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )


def _spec(name: str) -> dict:
    return yaml.safe_load((_EXAMPLES / f"{name}.spec.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def out(tmp_path, monkeypatch):
    folder = tmp_path / "out"
    monkeypatch.setenv("ANVILATE_OUT", str(folder))
    return folder


def _handles(name: str) -> tuple[str, str]:
    spec = _spec(name)
    built = _call("build_part", {"spec": spec})["result"]["structuredContent"]["subject"]
    screened = _call("run_validation", {"spec": spec})["result"]["structuredContent"]["subject"]
    return built, screened


def test_every_export_of_a_passing_part_is_a_file_in_the_output_folder(out):
    pytest.importorskip("build123d")
    built, screened = _handles("transmission_shaft")
    written = {}
    for artifact, handle in (
        ("step", built),
        ("3mf", built),
        ("part_sheet", screened),
        ("qif", screened),
        ("evidence_bundle", screened),
    ):
        result = _call("export_artifact", {"subject": handle, "format": artifact})["result"]
        file = result["structuredContent"]["file"]
        path = Path(file["path"])
        assert path.parent == out.resolve(), artifact
        data = path.read_bytes()
        assert file["bytes"] == len(data) and file["sha256"] == hashlib.sha256(data).hexdigest()
        # The reply names the file; it never carries a CAD file's contents through the model.
        assert len(json.dumps(result)) < 20_000 or artifact == "evidence_bundle", artifact
        written[artifact] = path.name
    assert written == {
        "step": "drive-shaft.step",
        "3mf": "drive-shaft.3mf",
        "part_sheet": "drive-shaft.html",
        "qif": "drive-shaft.qif",
        "evidence_bundle": "drive-shaft.bundle.json",
    }
    assert (out / "drive-shaft.step").read_text().startswith("ISO-10303-21;")
    assert "<script" not in (out / "drive-shaft.html").read_text(encoding="utf-8")


def test_a_cad_file_is_not_written_for_a_part_whose_checks_do_not_pass(out):
    """The padeye spec with nine times its load fails. Its bundle and sheet are written and
    say so; STEP-class artifacts and QIF are refused in the gate's words, with no override."""
    spec = _spec("padeye")
    spec["element_params"]["load"]["magnitude"] = 900.0
    screened = _call("run_validation", {"spec": spec})["result"]["structuredContent"]["subject"]

    refused = _call("export_artifact", {"subject": screened, "format": "qif"})["error"]
    assert refused["code"] == -32000
    assert "export is gated" in refused["message"] and "no override" in refused["message"]
    for artifact in ("evidence_bundle", "part_sheet"):
        result = _call("export_artifact", {"subject": screened, "format": artifact})["result"]
        assert Path(result["structuredContent"]["file"]["path"]).exists()
    assert sorted(path.name for path in out.iterdir()) == ["padeye.bundle.json", "padeye.html"]
    assert "FAIL" in (out / "padeye.html").read_text(encoding="utf-8")


def test_a_handle_of_the_wrong_kind_is_refused_by_name(out):
    pytest.importorskip("build123d")
    built, screened = _handles("base_plate")
    wrong = _call("export_artifact", {"subject": screened, "format": "step"})["error"]
    assert wrong["code"] == -32602 and "build_part" in wrong["message"]
    wrong = _call("export_artifact", {"subject": built, "format": "part_sheet"})["error"]
    assert wrong["code"] == -32602 and "run_validation" in wrong["message"]


def test_no_tool_takes_a_destination_and_nothing_is_written_without_a_folder(monkeypatch):
    monkeypatch.delenv("ANVILATE_OUT", raising=False)
    _outputs.set_output_folder(None)
    for tool in tool_catalog():
        properties = set(tool.input_schema["properties"])
        assert not properties & {"path", "destination", "output", "out", "file", "directory"}
    screened = _call("run_validation", {"spec": _spec("padeye")})["result"]["structuredContent"]
    bundle = _call("export_artifact", {"subject": screened["subject"], "format": "evidence_bundle"})
    assert "file" not in bundle["result"]["structuredContent"]
    refused = _call("export_artifact", {"subject": screened["subject"], "format": "part_sheet"})
    assert "started without an output folder" in refused["error"]["message"]


@pytest.mark.parametrize("name", ["../escape.step", "sub/part.step", "", "..", "a b.step", "x\x00"])
def test_the_writer_refuses_any_name_that_is_not_a_plain_file_name(out, name):
    with pytest.raises(ValueError, match="plain file name|outside the output folder"):
        _outputs.write_output(name, b"data")
    assert not out.exists() or list(out.iterdir()) == []


def test_a_part_name_cannot_steer_a_file_out_of_the_folder(out):
    """The name comes from the document, so a hostile one is reduced to a safe stem."""
    assert _outputs.safe_stem("../../etc/passwd") == "etc-passwd"
    assert _outputs.safe_stem("  ") == "part"
    spec = _spec("padeye")
    spec["name"] = "../../outside"
    screened = _call("run_validation", {"spec": spec})
    if "error" in screened:  # the spec's own name rule may refuse it first
        return
    handle = screened["result"]["structuredContent"]["subject"]
    file = _call("export_artifact", {"subject": handle, "format": "part_sheet"})["result"]
    assert Path(file["structuredContent"]["file"]["path"]).parent == out.resolve()


def test_a_rebuild_replaces_its_files_and_leaves_no_partials(out):
    screened = _call("run_validation", {"spec": _spec("padeye")})["result"]["structuredContent"]
    for _ in range(3):
        _call("export_artifact", {"subject": screened["subject"], "format": "part_sheet"})
    assert [path.name for path in out.iterdir()] == ["padeye.html"]


def test_the_server_takes_its_folder_at_launch(tmp_path, monkeypatch):
    from anvilate import mcp

    monkeypatch.delenv("ANVILATE_OUT", raising=False)
    monkeypatch.setattr(mcp, "serve_stdio", lambda: None)
    mcp.main(["--out", str(tmp_path / "chosen")])
    assert _outputs.output_folder() == (tmp_path / "chosen").resolve()
    monkeypatch.chdir(tmp_path)
    mcp.main([])
    assert _outputs.output_folder() == (tmp_path / "anvilate-out").resolve()
    _outputs.set_output_folder(None)


def test_every_result_over_the_spec_corpus_fits_the_declared_size_budget(out):
    """A result the client truncates is a result the agent half-reads. Every screening, read
    and bundle over the 147 corpus specs stays inside the budget both target clients allow."""
    from anvilate.mcp import RESULT_BUDGET_CHARS

    corpus = Path(__file__).resolve().parent / "spec_corpus.jsonl"
    largest, calls = 0, 0
    for line in corpus.read_text(encoding="utf-8").splitlines():
        document = json.loads(line)
        screened = _call("run_validation", {"spec": document})
        replies = [screened, _call("compile_spec", {"document": document})]
        if "result" in screened:
            handle = screened["result"]["structuredContent"]["subject"]
            replies.append(_call("read_scorecard", {"subject": handle}))
            replies.append(
                _call("export_artifact", {"subject": handle, "format": "evidence_bundle"})
            )
        for reply in replies:
            calls += 1
            largest = max(largest, len(json.dumps(reply)))
    assert calls >= 400, f"only {calls} results were measured"
    assert largest <= RESULT_BUDGET_CHARS, f"a result reached {largest:,} characters"


def test_the_overview_is_one_picture_with_the_part_its_size_material_and_verdict(out):
    """The view to show first: four views on one image, under a title block read from the
    spec that was built. Its summary line names it, and the file is written as an image."""
    pytest.importorskip("build123d")
    built, _screened = _handles("transmission_shaft")
    result = _call("render_viewport", {"subject": built, "view": "overview"})["result"]
    summary, image = result["content"]
    assert summary["text"].startswith("overview view, 1000x750 px, image/png")
    assert image["mimeType"] == "image/png" and "structuredContent" not in result
    assert (out / "drive-shaft-overview.png").stat().st_size > 2_000

    plain = _call("render_viewport", {"subject": built, "view": "front"})["result"]
    labelled = _call("render_viewport", {"subject": built, "view": "front", "dimensions": True})
    assert labelled["result"]["content"][1]["data"] != plain["content"][1]["data"]
