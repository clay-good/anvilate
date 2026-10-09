"""Third-party modules: loaded only by name, run confined, marked unverified-origin everywhere.

add-physical-domain-modules 4.1 and 4.2. Each confinement rule is attacked by a module that
breaks it; each refusal is reached by a manifest that earns it; and the marking is followed
from the entry to the CLI, the MCP result, the evidence bundle and the export gate.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from anvilate import thirdparty
from anvilate.scorecard import CheckStatus
from anvilate.thirdparty import ThirdPartyModuleError, enable_module

_REPO = Path(__file__).resolve().parents[1]
_EXAMPLE = _REPO / "examples" / "third_party_module"

_MANIFEST = {
    "id": "acme_widgets",
    "namespace": "acme_widgets",
    "version": "2.1.0",
    "unit_default": "SI",
    "tiers": ["T1_analytical"],
    "screens": ["screen_widget"],
    "covers": ["widget"],
    "summary": "Widgets, for the tests.",
}


def _module(tmp_path: Path, body: str, *, manifest: dict | None = None) -> Path:
    path = tmp_path / "acme.py"
    path.write_text(
        f"MANIFEST = {json.dumps(manifest or _MANIFEST)}\n\n" + textwrap.dedent(body),
        encoding="utf-8",
    )
    return path


_PASSING = """
def screen_widget(params):
    return [{"name": "widget strength", "status": "pass", "detail": "fine"}]
"""


def _screened(path: Path, params: dict | None = None) -> list:
    return enable_module(path).screen("widget", params or {})


def test_a_module_runs_and_every_entry_names_where_it_came_from(tmp_path):
    path = _module(tmp_path, _PASSING)
    module = enable_module(path)
    (entry,) = module.screen("widget", {})
    assert (entry.status, entry.name) == (CheckStatus.PASS, "widget strength")
    assert entry.origin == module.origin
    assert (entry.origin.module, entry.origin.version) == ("acme_widgets", "2.1.0")
    assert entry.origin.source == str(path.resolve())
    assert "unverified origin" in str(entry)


@pytest.mark.parametrize(
    ("label", "body", "refused"),
    [
        (
            "network",
            "import socket\ndef screen_widget(p):\n"
            "    socket.create_connection(('127.0.0.1', 9)); return []\n",
            "socket.",
        ),
        (
            "read outside",
            "def screen_widget(p):\n    return [open('/etc/hosts').read()]\n",
            "may not read",
        ),
        (
            "write outside",
            f"def screen_widget(p):\n    open({str(Path.home() / 'anvilate-escape')!r}, 'w')\n",
            "may not write",
        ),
        (
            "process",
            "import subprocess\ndef screen_widget(p):\n    subprocess.run(['true'])\n",
            "subprocess.Popen",
        ),
        (
            "ctypes",
            "def screen_widget(p):\n    import ctypes\n    ctypes.CDLL(None)\n",
            "ctypes",
        ),
        (
            "swallowed",
            "def screen_widget(p):\n    try:\n        open('/etc/hosts').read()\n"
            "    except PermissionError:\n        pass\n"
            "    return [{'name': 'w', 'status': 'pass', 'detail': 'trust me'}]\n",
            "may not read",
        ),
    ],
)
def test_a_module_that_breaks_confinement_is_stopped_and_reported(tmp_path, label, body, refused):
    (entry,) = _screened(_module(tmp_path, body))
    assert entry.status is CheckStatus.NOT_EVALUATED, label
    assert "did not complete" in entry.detail and refused in entry.detail, entry.detail
    assert entry.origin is not None
    assert not (Path.home() / "anvilate-escape").exists()


def test_a_module_that_loads_native_code_on_import_is_refused_when_enabled(tmp_path):
    """Confinement starts before the module is imported, so the refusal comes at enabling."""
    path = _module(tmp_path, "import ctypes\nctypes.CDLL(None)\n" + _PASSING)
    with pytest.raises(ThirdPartyModuleError, match="ctypes"):
        enable_module(path)


def test_a_module_may_use_its_scratch_directory_and_print(tmp_path):
    body = """
    def screen_widget(params):
        print("chatter on stdout")
        with open("work.txt", "w") as scratch:
            scratch.write(str(params["x"] * 2))
        return [{"name": "w", "status": "pass", "detail": open("work.txt").read()}]
    """
    (entry,) = _screened(_module(tmp_path, body), {"x": 21})
    assert (entry.status, entry.detail) == (CheckStatus.PASS, "42")


def test_a_module_that_never_answers_is_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(thirdparty, "_TIMEOUT_SECONDS", 2)
    (entry,) = _screened(
        _module(tmp_path, "def screen_widget(p):\n    while True:\n        pass\n")
    )
    assert entry.status is CheckStatus.NOT_EVALUATED and "no answer within 2 s" in entry.detail


@pytest.mark.parametrize(
    ("returned", "reason"),
    [
        ("[{'name': 'w', 'status': 'great', 'detail': 'd'}]", "status must be one of"),
        ("[{'name': 'w', 'status': 'pass', 'detail': 'd', 'validated': True}]", "does not read"),
        ("[]", "returned no entries"),
        ("{'not': 'a list'}", "returned no entries"),
    ],
)
def test_what_a_module_returns_is_validated_as_input_from_outside(tmp_path, returned, reason):
    (entry,) = _screened(_module(tmp_path, f"def screen_widget(p):\n    return {returned}\n"))
    assert entry.status is CheckStatus.NOT_EVALUATED and reason in entry.detail


def test_a_module_edited_after_it_was_enabled_is_not_run(tmp_path):
    path = _module(tmp_path, _PASSING)
    module = enable_module(path)
    path.write_text(path.read_text() + "\n# changed\n", encoding="utf-8")
    (entry,) = module.screen("widget", {})
    assert (
        entry.status is CheckStatus.NOT_EVALUATED and "changed after it was enabled" in entry.detail
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"namespace": "structural"}, "shipped module 'structural'"),
        ({"namespace": "structural.extra"}, "shipped module 'structural'"),
        ({"id": "machinery"}, "shipped module 'machinery'"),
        ({"covers": ["base_plate"]}, "already screens"),
        ({"screens": ["widget"]}, "no valid MANIFEST"),
    ],
)
def test_a_manifest_that_claims_what_ships_is_refused(tmp_path, change, message):
    with pytest.raises(ThirdPartyModuleError, match=message):
        enable_module(_module(tmp_path, _PASSING, manifest={**_MANIFEST, **change}))


def test_only_a_python_file_with_a_manifest_is_a_module(tmp_path):
    with pytest.raises(ThirdPartyModuleError, match="one .py file"):
        enable_module(tmp_path / "missing.py")
    bare = tmp_path / "bare.py"
    bare.write_text(_PASSING, encoding="utf-8")
    with pytest.raises(ThirdPartyModuleError, match="no valid MANIFEST"):
        enable_module(bare)


def _example_spec():
    from anvilate.spec import load_spec_yaml

    return load_spec_yaml((_EXAMPLE / "hanger_rod.spec.yaml").read_text(encoding="utf-8"))


def test_nothing_is_screened_by_a_module_nobody_named():
    from anvilate.screening import screen_spec

    card = screen_spec(_example_spec())
    assert not any(entry.origin for entry in card.entries)
    assert "is not one of the" in card.entries[0].detail


def test_the_example_module_screens_its_element_and_cannot_export_as_validated():
    from anvilate.export.gate import ExportRefused, authorize_export
    from anvilate.screening import screen_spec

    module = enable_module(_EXAMPLE / "hanger_rod.py")
    card = screen_spec(_example_spec(), modules=[module])
    rod = next(entry for entry in card.entries if entry.name == "hanger rod tension")
    assert rod.status is CheckStatus.PASS and rod.origin == module.origin
    assert "84.3 mm²" in rod.detail  # A_s for M12x1.75, ISO 898-1
    assert card.passed
    with pytest.raises(ExportRefused, match="third-party module") as refused:
        authorize_export(card)
    assert "hanger rod tension" in refused.value.unmet
    watermarked = authorize_export(card, override=True)
    assert watermarked.validated is False


def test_the_cli_names_the_origin_and_the_bundle_records_it():
    from cli_output import run_cli

    spec, module = str(_EXAMPLE / "hanger_rod.spec.yaml"), str(_EXAMPLE / "hanger_rod.py")
    code, out, _err = run_cli("check", spec, "--module", module)
    assert code == 0
    assert "[unverified origin: third-party module example_hanger_rods 0.1.0" in out
    assert "unverified:    1 from third-party modules" in out

    code, raw, _err = run_cli(
        "export", spec, "--artifact", "evidence-bundle", "--module", module, "--format", "json"
    )
    entries = json.loads(raw)["bundles"][0]["bundle"]["scorecard"]["entries"]
    (marked,) = [entry for entry in entries if "origin" in entry]
    assert marked["origin"]["module"] == "example_hanger_rods"
    assert len(marked["origin"]["sha256"]) == 64

    code, _out, err = run_cli("check", spec, "--module", str(_REPO / "README.md"))
    assert code == 3 and "one .py file" in err


def test_the_mcp_server_enables_modules_only_at_launch(monkeypatch):
    import yaml

    from anvilate import mcp

    document = yaml.safe_load((_EXAMPLE / "hanger_rod.spec.yaml").read_text(encoding="utf-8"))

    def validate() -> dict:
        reply = mcp.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "run_validation", "arguments": {"spec": document}},
            }
        )
        return reply["result"]["structuredContent"]["scorecard"]

    assert not any("origin" in entry for entry in validate()["entries"])
    monkeypatch.setattr(mcp, "_MODULES", (enable_module(_EXAMPLE / "hanger_rod.py"),))
    assert any(entry.get("origin") for entry in validate()["entries"])

    with pytest.raises(SystemExit) as stopped:
        mcp.main(["--module", str(_REPO / "README.md")])
    assert stopped.value.code == 2
