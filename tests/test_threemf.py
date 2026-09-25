"""3MF export (target-ap242-e4-exports 2.3), read back by the reference implementation.

Every file here is opened by lib3mf, the 3MF Consortium's own library, in strict mode. That
is what makes a writer written in this repository an "equivalent validated writer": the
claim is not that the XML looks right, it is that the reference reader accepts it, finds the
mesh closed and oriented, and reads the same metadata back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvilate.export.gate import authorize_export
from anvilate.export.threemf import THREEMF_STANDARD, render_mesh_3mf
from anvilate.scorecard import Scorecard, ScorecardEntry

lib3mf = pytest.importorskip("lib3mf")

_REPO = Path(__file__).resolve().parent.parent

# A 10 mm cube, each triangle counter-clockwise seen from outside.
_CUBE_VERTICES = [
    (0, 0, 0),
    (10, 0, 0),
    (10, 10, 0),
    (0, 10, 0),
    (0, 0, 10),
    (10, 0, 10),
    (10, 10, 10),
    (0, 10, 10),
]
_CUBE_TRIANGLES = [
    (0, 2, 1),
    (0, 3, 2),
    (4, 5, 6),
    (4, 6, 7),
    (0, 1, 5),
    (0, 5, 4),
    (1, 2, 6),
    (1, 6, 5),
    (2, 3, 7),
    (2, 7, 6),
    (3, 0, 4),
    (3, 4, 7),
]


def _authorization(*, passing: bool = True):  # type: ignore[no-untyped-def]
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "bending", computed=3.0 if passing else 1.0, required=2.0
            ),
        )
    )
    return authorize_export(card, override=not passing)


def _read(data: bytes):  # type: ignore[no-untyped-def]
    """The file as the reference implementation reads it, strictly."""
    model = lib3mf.get_wrapper().CreateModel()
    reader = model.QueryReader("3mf")
    reader.SetStrictModeActive(True)
    reader.ReadFromBuffer(bytearray(data))
    assert reader.GetWarningCount() == 0, [
        reader.GetWarning(index) for index in range(reader.GetWarningCount())
    ]
    meshes = model.GetMeshObjects()
    assert meshes.MoveNext()
    group = model.GetMetaDataGroup()
    metadata = {
        group.GetMetaData(index).GetName(): group.GetMetaData(index).GetValue()
        for index in range(group.GetMetaDataCount())
    }
    return model, meshes.GetCurrentMeshObject(), metadata


def test_the_reference_reader_accepts_the_file_and_reads_back_what_it_claims():
    data = render_mesh_3mf(
        vertices=_CUBE_VERTICES,
        triangles=_CUBE_TRIANGLES,
        name="cube",
        authorization=_authorization(),
    )
    model, mesh, metadata = _read(data)
    assert (mesh.GetName(), mesh.GetVertexCount(), mesh.GetTriangleCount()) == ("cube", 8, 12)
    assert mesh.IsManifoldAndOriented()
    assert model.GetUnit() == lib3mf.ModelUnit.MilliMeter
    assert metadata["standard"] == THREEMF_STANDARD == "ISO/IEC 25422:2025"
    assert metadata["writer"].startswith("anvilate ")
    assert metadata["ANVILATE_EXPORT_STATUS"] == "VALIDATED"
    assert "ANVILATE_EXPORT_BLOCKING" not in metadata


def test_an_overridden_export_says_so_inside_the_file():
    data = render_mesh_3mf(
        vertices=_CUBE_VERTICES,
        triangles=_CUBE_TRIANGLES,
        name="cube",
        authorization=_authorization(passing=False),
    )
    _model, _mesh, metadata = _read(data)
    assert metadata["ANVILATE_EXPORT_STATUS"] == "UNVALIDATED"
    assert "bending" in metadata["ANVILATE_EXPORT_BLOCKING"]


def test_the_same_mesh_is_the_same_bytes():
    def once() -> bytes:
        return render_mesh_3mf(
            vertices=_CUBE_VERTICES,
            triangles=_CUBE_TRIANGLES,
            name="cube",
            authorization=_authorization(),
        )

    assert once() == once()


@pytest.mark.parametrize(
    ("vertices", "triangles", "match"),
    [
        (_CUBE_VERTICES, _CUBE_TRIANGLES[:-1], "no triangle on its other side"),
        (
            _CUBE_VERTICES,
            [(0, 1, 2), *_CUBE_TRIANGLES[1:]],
            "same way, so one of them faces inward",
        ),
        (_CUBE_VERTICES, [(0, 0, 1), *_CUBE_TRIANGLES[1:]], "repeats a vertex"),
        (_CUBE_VERTICES, [(0, 2, 99), *_CUBE_TRIANGLES[1:]], "must name three of the 8"),
        ([(float("nan"), 0, 0), *_CUBE_VERTICES[1:]], _CUBE_TRIANGLES, "three finite numbers"),
        (_CUBE_VERTICES[:3], _CUBE_TRIANGLES[:3], "at least 4 vertices"),
    ],
)
def test_a_mesh_a_printer_would_have_to_guess_about_is_refused(vertices, triangles, match):
    with pytest.raises(ValueError, match=match):
        render_mesh_3mf(
            vertices=vertices, triangles=triangles, name="cube", authorization=_authorization()
        )


def test_every_audited_part_exports_as_a_closed_mesh_holding_its_volume():
    """The geometry path: each built pattern tessellated, welded, written, and read back.

    The kernel meshes faces separately, so a shared edge's vertices arrive once per face;
    without the weld every part was refused as open. The volume the mesh encloses is held
    to the solid's own, so a tessellation that dropped a bore would be refused, not written.
    """
    pytest.importorskip("build123d")
    from anvilate.geometry import build_spec, render_3mf
    from anvilate.spec import load_spec_yaml

    built_any = 0
    for name in ("base_plate", "cover_plate", "transmission_shaft"):
        spec = load_spec_yaml((_REPO / "examples" / f"{name}.spec.yaml").read_text())
        built = build_spec(spec)
        _model, mesh, metadata = _read(render_3mf(built, authorization=_authorization()))
        assert mesh.IsManifoldAndOriented(), name
        assert mesh.GetName() == built.name
        assert metadata["standard"] == THREEMF_STANDARD
        built_any += 1
    assert built_any == 3
