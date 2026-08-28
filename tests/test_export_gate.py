"""The export gate: what it refuses, what it stamps, and the ratchet that keeps it there.

``artifact-export`` says export is enabled only when the acceptance checks pass, that a
caller may override, and that an overridden export is watermarked as unvalidated in the
exported file's metadata. Before :mod:`anvilate.export.gate` that sentence was enforced in
no exporter: ``export_plate_dxf`` wrote a cuttable file from a width, a height and a list
of holes, and nothing in the file said whether anything had been checked.

The last two tests here are the ones that keep this from rotting. One reads the source of
every public export entry point and requires an ``authorization`` parameter, so a new
exporter cannot be added ungated. The other holds the MCP tool catalog's declared gates
against what the backing symbol actually requires, so ``export_artifact``'s "the MCP
surface grants no bypass" is a claim that can fail.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from anvilate.attestation import Component, ComponentKind, EnvironmentBOM
from anvilate.bundle import BundleSections
from anvilate.export import dxf as dxf_module
from anvilate.export import gate as gate_module
from anvilate.export import qif as qif_module
from anvilate.export.dxf import (
    Hole,
    export_feature_control_frame_dxf,
    export_gear_blank_dxf,
    export_plate_dxf,
)
from anvilate.export.gate import (
    BLOCKING_KEY,
    NOTICE_KEY,
    SCREENING_NOTICE,
    STATUS_KEY,
    ExportAuthorization,
    ExportRefused,
    authorize_export,
)
from anvilate.export.qif import QIF_NAMESPACE, export_qif_results
from anvilate.gdt import Characteristic, DatumReference, FeatureControlFrame, FeatureType
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity

_NS = {"q": QIF_NAMESPACE}
_REPO = Path(__file__).resolve().parent.parent


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _passing() -> Scorecard:
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("net tension", computed=4.4, required=1.5),
            ScorecardEntry.from_safety_factor("pin bearing", computed=2.0, required=1.5),
        )
    )


def _failing() -> Scorecard:
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("net tension", computed=1.1, required=1.5),
            ScorecardEntry.from_safety_factor("pin bearing", computed=2.0, required=1.5),
        )
    )


def _unrun() -> Scorecard:
    """A card with nothing failing and one check that could not run."""
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("net tension", computed=4.4, required=1.5),
            ScorecardEntry.from_safety_factor("plate tear-out", computed=None, required=1.5),
        )
    )


# --------------------------------------------------------------------------- the decision


def test_a_passing_card_authorizes_a_validated_export():
    authorization = authorize_export(_passing())
    assert authorization.validated
    assert not authorization.overridden
    assert authorization.blocking == ()
    assert authorization.status == "VALIDATED"


def test_a_failing_card_refuses_and_names_the_check():
    with pytest.raises(ExportRefused) as refusal:
        authorize_export(_failing())
    assert refusal.value.blocking == ("net tension",)
    assert "net tension" in str(refusal.value)
    # The message has to tell the caller the door they are allowed to open, or the only
    # way past a refusal they meant is to go around the gate.
    assert "override=True" in str(refusal.value)


def test_a_check_that_could_not_run_blocks_as_hard_as_one_that_failed():
    """No-silent-green at the export gate.

    ``Scorecard.failures()`` is empty for this card — nothing failed. Counting only
    failures here would export a part whose tear-out path nobody dimensioned, which is
    exactly the reading the scorecard's own roll-up refuses.
    """
    assert _unrun().failures() == ()
    with pytest.raises(ExportRefused) as refusal:
        authorize_export(_unrun())
    assert refusal.value.blocking == ("plate tear-out",)


def test_no_card_at_all_is_not_a_pass():
    with pytest.raises(ExportRefused) as refusal:
        authorize_export(None)
    assert refusal.value.blocking == ()
    assert "no checks were run at all" in str(refusal.value)


def test_an_empty_card_is_not_a_pass():
    """A scorecard with no entries rolls up to NOT_EVALUATED, and the gate reads it."""
    empty = Scorecard()
    assert empty.status is CheckStatus.NOT_EVALUATED
    with pytest.raises(ExportRefused):
        authorize_export(empty)


def test_an_over_margin_card_still_exports():
    """Over-margin is a warning, not a blocker — the scorecard says so and the gate agrees."""
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("weld shear", computed=9.1, required=2.0, upper=4.0),
        )
    )
    assert card.status is CheckStatus.OVER_MARGIN
    assert authorize_export(card).validated


def test_the_override_produces_an_unvalidated_authorization_naming_the_blockers():
    authorization = authorize_export(_failing(), override=True)
    assert not authorization.validated
    assert authorization.overridden
    assert authorization.blocking == ("net tension",)
    assert authorization.status == "UNVALIDATED"


def test_an_override_that_overrides_nothing_is_an_error():
    """A no-op override means the caller expected a failing card and did not get one.

    Consuming the argument silently would make ``override=True`` a flag that does nothing
    on the happy path and everything on the unhappy one — a difference no test and no
    reader could see at the call site.
    """
    with pytest.raises(ValueError, match="nothing to override"):
        authorize_export(_passing(), override=True)


# ------------------------------------------------------------------- the watermark itself


def test_every_authorization_carries_the_screening_notice():
    for authorization in (
        authorize_export(_passing()),
        authorize_export(_failing(), override=True),
    ):
        assert authorization.watermark()[0] == SCREENING_NOTICE
        assert dict(authorization.metadata())[NOTICE_KEY] == SCREENING_NOTICE


def test_only_an_overridden_export_carries_the_unvalidated_line():
    clean = authorize_export(_passing())
    dirty = authorize_export(_failing(), override=True)
    assert len(clean.watermark()) == 1
    assert BLOCKING_KEY not in dict(clean.metadata())
    joined = " ".join(dirty.watermark())
    assert "UNVALIDATED EXPORT" in joined
    assert "net tension" in joined
    assert "net tension" in dict(dirty.metadata())[BLOCKING_KEY]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"validated": True, "overridden": True},
        {"validated": True, "blocking": ("net tension",)},
        {"validated": False, "overridden": False},
    ],
)
def test_an_authorization_cannot_disagree_with_itself(kwargs):
    with pytest.raises(ValueError):
        ExportAuthorization(**kwargs)


def test_model_copy_cannot_launder_a_refusal_into_a_pass():
    """``model_copy`` skips ``mode="after"`` validators, so the model overrides it.

    Without the override, one call turns the authorization for a failing part into one
    that reads VALIDATED with the blocking checks still attached — a clean watermark on a
    part that did not pass, which is the single outcome this module exists to prevent.
    """
    overridden = authorize_export(_failing(), override=True)
    with pytest.raises(ValueError):
        overridden.model_copy(update={"validated": True, "overridden": False})


# ------------------------------------------------------------------------- DXF, stamped


def _custom_vars(path):
    ezdxf = pytest.importorskip("ezdxf")
    return dict(ezdxf.readfile(path).header.custom_vars.properties)


def test_a_validated_plate_dxf_says_so_in_its_header(tmp_path):
    pytest.importorskip("ezdxf")
    out = export_plate_dxf(
        width=_q("80 mm"),
        height=_q("120 mm"),
        holes=[Hole(x=_q("40 mm"), y=_q("90 mm"), diameter=_q("25 mm"))],
        path=tmp_path / "lug.dxf",
        authorization=authorize_export(_passing()),
    )
    properties = _custom_vars(out)
    assert properties[STATUS_KEY] == "VALIDATED"
    assert properties[NOTICE_KEY] == SCREENING_NOTICE
    assert BLOCKING_KEY not in properties


def test_an_overridden_plate_dxf_names_the_checks_it_was_exported_past(tmp_path):
    pytest.importorskip("ezdxf")
    out = export_plate_dxf(
        width=_q("80 mm"),
        height=_q("120 mm"),
        holes=[],
        path=tmp_path / "lug.dxf",
        authorization=authorize_export(_failing(), override=True),
    )
    properties = _custom_vars(out)
    assert properties[STATUS_KEY] == "UNVALIDATED"
    assert "net tension" in properties[BLOCKING_KEY]


def test_the_gear_blank_and_the_callout_frame_are_stamped_too(tmp_path):
    """Every DXF entry point, not just the one the requirement's example names."""
    pytest.importorskip("ezdxf")
    blank = export_gear_blank_dxf(
        outside_diameter=_q("104 mm"),
        pitch_diameter=_q("100 mm"),
        root_diameter=_q("95 mm"),
        bore_diameter=_q("30 mm"),
        path=tmp_path / "blank.dxf",
        authorization=authorize_export(_passing()),
    )
    frame = FeatureControlFrame(
        characteristic=Characteristic.POSITION,
        tolerance=_q("0.2 mm"),
        feature_type=FeatureType.FEATURE_OF_SIZE,
        datums=(DatumReference(letter="A"),),
    )
    callout = export_feature_control_frame_dxf(
        frame=frame,
        path=tmp_path / "fcf.dxf",
        authorization=authorize_export(None, override=True),
    )
    assert _custom_vars(blank)[STATUS_KEY] == "VALIDATED"
    assert _custom_vars(callout)[STATUS_KEY] == "UNVALIDATED"
    assert _custom_vars(blank)[NOTICE_KEY] == _custom_vars(callout)[NOTICE_KEY]


def test_the_watermark_survives_the_file_rather_than_the_call(tmp_path):
    """The claim is about the artifact, so it is read back out of the bytes on disk.

    Asserting on the authorization object would pass even if ``_stamp`` were deleted.
    """
    pytest.importorskip("ezdxf")
    out = export_plate_dxf(
        width=_q("50 mm"),
        height=_q("50 mm"),
        holes=[],
        path=tmp_path / "plate.dxf",
        authorization=authorize_export(_failing(), override=True),
    )
    text = Path(out).read_text(encoding="utf-8", errors="replace")
    assert STATUS_KEY in text
    assert "UNVALIDATED" in text
    assert SCREENING_NOTICE in text


# ------------------------------------------------------------------------- QIF, stamped


def _bom() -> EnvironmentBOM:
    return EnvironmentBOM(
        application=Component(name="anvilate", version="0.0.1", kind=ComponentKind.APPLICATION)
    )


def _qif(card: Scorecard, *, override: bool) -> str:
    return export_qif_results(
        BundleSections(scorecard=card),
        part_name="lug-01",
        spec_digest="sha256:abc123",
        bom=_bom(),
        authorization=authorize_export(card, override=override),
    )


def _scope(document: str) -> str:
    scope = ET.fromstring(document).findtext("./q:Header/q:Scope", namespaces=_NS)
    assert scope is not None
    return scope


def test_the_qif_scope_carries_the_screening_notice_either_way():
    assert SCREENING_NOTICE in _scope(_qif(_passing(), override=False))
    assert SCREENING_NOTICE in _scope(_qif(_failing(), override=True))


def test_only_the_overridden_qif_scope_says_unvalidated():
    clean = _scope(_qif(_passing(), override=False))
    dirty = _scope(_qif(_failing(), override=True))
    assert "UNVALIDATED EXPORT" not in clean
    assert "UNVALIDATED EXPORT" in dirty
    assert "net tension" in dirty
    # The clause the older document carried is still there — this replaced the sentence,
    # it did not drop it.
    assert "NOT_ANALYZED" in clean


def test_qif_refuses_an_authorization_obtained_from_another_card():
    """The one exporter that can see the card it is exporting checks that it matches.

    ``authorize_export`` is handed a scorecard, and nothing ties the authorization it
    returns to the bundle a caller later passes. For DXF there is nothing to compare
    against; for QIF the card is in the bundle, so a VALIDATED authorization over a
    failing bundle is caught here rather than shipped.
    """
    borrowed = authorize_export(_passing())
    with pytest.raises(ValueError, match="not from another one"):
        export_qif_results(
            BundleSections(scorecard=_failing()),
            part_name="lug-01",
            spec_digest="sha256:abc123",
            bom=_bom(),
            authorization=borrowed,
        )


# ---------------------------------------------------------------------------- the ratchet

# Public functions in `anvilate.export` that write or emit an artifact. Each must take an
# `authorization`. Listing the exemptions rather than the members is deliberate: the scan
# below finds the members itself, so a new exporter is in scope the moment it is written.
_NOT_AN_ARTIFACT_WRITER = {
    # Reads a document rather than emitting one.
    "qif_schema_issues",
    # Maps one declaration to a QIF characteristic definition; returns a value, writes
    # nothing.
    "qif_characteristic_mapping",
}


def _export_entry_points() -> dict[str, object]:
    """Every public callable the export package exposes, by module-qualified name."""
    found: dict[str, object] = {}
    for module in (dxf_module, qif_module, gate_module):
        for name in getattr(module, "__all__", ()):
            value = getattr(module, name)
            if inspect.isfunction(value):
                found[f"{module.__name__.rsplit('.', 1)[-1]}.{name}"] = value
    return found


def _writes_a_file_or_document(function) -> bool:
    """Whether the function's source contains a write or a serialize of an artifact.

    Source reading rather than a hand-kept list: the question is whether *this* function
    emits something, and the answer is in its body.
    """
    source = inspect.getsource(function)
    return "saveas(" in source or "ET.tostring(" in source


def test_every_export_entry_point_that_emits_an_artifact_takes_an_authorization():
    entry_points = _export_entry_points()
    # Attack the gate first: a scan that found nothing would pass this test silently, and
    # so would one whose `_writes_a_file_or_document` stopped matching anything.
    assert len(entry_points) >= 8, f"the scan found only {len(entry_points)} entry points"
    emitters = {
        name: fn
        for name, fn in entry_points.items()
        if name.rsplit(".", 1)[-1] not in _NOT_AN_ARTIFACT_WRITER and _writes_a_file_or_document(fn)
    }
    assert len(emitters) == 4, f"expected the four artifact writers, found {sorted(emitters)}"
    for name, function in sorted(emitters.items()):
        parameters = inspect.signature(function).parameters
        assert "authorization" in parameters, (
            f"{name} emits an artifact and takes no authorization; every export is gated "
            f"on the acceptance checks and every artifact carries the watermark"
        )
        assert parameters["authorization"].default is inspect.Parameter.empty, (
            f"{name} takes an optional authorization. An optional gate is one the caller "
            f"can omit, and the calls that omit it are the ungated ones"
        )


def test_an_exempt_entry_point_is_one_that_really_emits_nothing():
    """The exemption list cannot be used to excuse a writer.

    A name on ``_NOT_AN_ARTIFACT_WRITER`` that starts emitting an artifact fails here, so
    the list is a statement about behavior rather than a way to quiet the test above.
    """
    entry_points = _export_entry_points()
    for name in _NOT_AN_ARTIFACT_WRITER:
        matches = [fn for key, fn in entry_points.items() if key.rsplit(".", 1)[-1] == name]
        assert matches, f"{name} is exempt and no longer exists; strike it off"
        for function in matches:
            assert not _writes_a_file_or_document(function), (
                f"{name} is exempt from the export gate and emits an artifact"
            )


def test_the_mcp_tools_that_emit_artifacts_are_backed_by_something_that_gates():
    """``export_artifact`` declares the validation and watermark gates. This is the parity.

    The MCP surface "grants no bypass" is a sentence in the headless-automation spec and a
    ``_meta`` field in the published tool definition. It becomes a fact here: the symbol
    named in ``backing`` is resolved and required to take a mandatory ``authorization``,
    so a tool cannot declare a gate its implementation does not have.
    """
    from anvilate.mcp import Gate, tool_catalog

    emitting = [tool for tool in tool_catalog() if Gate.WATERMARK in tool.gates]
    assert len(emitting) == 1, f"expected one artifact-emitting tool, found {emitting}"
    for tool in emitting:
        assert Gate.VALIDATION in tool.gates
        assert tool.backing is not None, (
            f"{tool.name} declares the watermark gate and names no implementation, so the "
            f"claim is untestable"
        )
        module_path, _, symbol = tool.backing.partition(":")
        module = __import__(module_path, fromlist=[symbol])
        parameters = inspect.signature(getattr(module, symbol)).parameters
        assert "authorization" in parameters
        assert parameters["authorization"].default is inspect.Parameter.empty


def test_the_sandbox_gate_is_declared_and_undischarged():
    """The honest half of parity: one declared gate has nothing behind it yet.

    ``build_part`` declares the sandbox gate because it executes caller-supplied code, and
    it names no backing symbol — the operation is unbuilt. Asserting that here means the
    day a backing lands, this test fails and someone has to decide what discharges it,
    rather than the tool quietly acquiring an implementation with no sandbox.
    """
    from anvilate.mcp import Gate, tool_catalog

    sandboxed = [tool for tool in tool_catalog() if Gate.SANDBOX in tool.gates]
    assert [tool.name for tool in sandboxed] == ["build_part"]
    assert sandboxed[0].backing is None
    assert not any(
        "sandbox" in path.read_text()
        for path in (_REPO / "src" / "anvilate" / "export").glob("*.py")
    )


def test_no_exporter_module_writes_a_file_outside_a_gated_entry_point():
    """A private helper that calls ``saveas`` would be an export the ratchet cannot see.

    The scan above only reads public ``__all__`` members. This one reads the whole module
    tree and requires every ``saveas`` call to sit inside a function that takes an
    authorization, so the gate cannot be walked around by moving the write one frame down.
    """
    for path in sorted((_REPO / "src" / "anvilate" / "export").glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body = ast.get_source_segment(path.read_text(), node) or ""
            if "saveas(" not in body:
                continue
            names = {argument.arg for argument in node.args.args + node.args.kwonlyargs}
            assert "authorization" in names, (
                f"{path.name}:{node.name} writes a file and takes no authorization"
            )
