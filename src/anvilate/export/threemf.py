"""3MF export: a closed triangle mesh as the ISO/IEC 25422 file a printer reads.

3MF (the 3D Manufacturing Format, published as ISO/IEC 25422:2025) is an OPC package: a zip
holding a content-types part, a relationships part and one XML model, whose ``<mesh>`` lists
vertices and the triangles between them. This writer produces exactly that core, in
millimetres, and nothing from the extensions.

Three positions, each of them a refusal or a record:

* **Only a closed, consistently oriented mesh is written.** The core specification requires a
  mesh object to be manifold, and a slicer given one that is not guesses what is inside. Each
  edge must be used by exactly two triangles, once in each direction; an open edge, a
  T-junction or a flipped triangle is refused naming the first one found, rather than written
  and left for the printer to interpret.
* **The file says what it is.** The standard, the writer and its version are written into
  the model's metadata, beside the export watermark every artifact here carries, so the claim
  travels with the file rather than with the email it was attached to.
* **The same mesh gives the same bytes.** Member order, zip timestamps and number spelling are
  fixed, so a file's digest in an evidence bundle identifies its content.

The writer is this module, and its tests read every file back with lib3mf, the 3MF
Consortium's reference implementation. That is the spec's "equivalent validated writer".
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Sequence
from math import isfinite
from xml.sax.saxutils import escape, quoteattr

from .. import __version__
from .gate import ExportAuthorization

__all__ = ["THREEMF_STANDARD", "render_mesh_3mf"]

#: The standard a 3MF file from this module claims, as 3mf.io and ISO's catalogue name it.
THREEMF_STANDARD = "ISO/IEC 25422:2025"

_CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
_ANVILATE = "https://anvilate.dev/3mf"
_MODEL_PART = "3D/3dmodel.model"
# A fixed timestamp for every zip member, so identical content is identical bytes. 1980 is
# the earliest date a zip header can hold.
_EPOCH = (1980, 1, 1, 0, 0, 0)

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="model" '
    'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
    "</Types>\n"
)
_RELATIONSHIPS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    f'<Relationship Target="/{_MODEL_PART}" Id="rel0" '
    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
    "</Relationships>\n"
)


def _number(value: float) -> str:
    """The shortest spelling that reads back as the same float, and never ``-0``."""
    return repr(float(value) + 0.0)


def _closed_and_oriented(triangles: Sequence[tuple[int, int, int]]) -> None:
    """Refuse a mesh whose edges are not each used once in each direction."""
    directed: dict[tuple[int, int], int] = {}
    for index, (a, b, c) in enumerate(triangles):
        for edge in ((a, b), (b, c), (c, a)):
            if edge in directed:
                raise ValueError(
                    f"triangles {directed[edge]} and {index} both run edge {edge[0]}->"
                    f"{edge[1]} the same way, so one of them faces inward or the surface "
                    "folds; a 3MF mesh has to be consistently oriented"
                )
            directed[edge] = index
    for (a, b), index in directed.items():
        if (b, a) not in directed:
            raise ValueError(
                f"edge {a}-{b} of triangle {index} has no triangle on its other side, so the "
                "mesh is open there; a 3MF mesh has to be closed for a printer to know what "
                "is inside it"
            )


def render_mesh_3mf(
    *,
    vertices: Sequence[tuple[float, float, float]],
    triangles: Sequence[tuple[int, int, int]],
    name: str,
    authorization: ExportAuthorization,
) -> bytes:
    """A closed triangle mesh, in millimetres, as the bytes of a 3MF file.

    ``vertices`` are (x, y, z) in millimetres. ``triangles`` index into them, counter-clockwise
    seen from outside, which is the 3MF core's orientation rule. ``name`` labels the object.
    ``authorization`` comes from :func:`~anvilate.export.gate.authorize_export` and is
    written into the model metadata with the standard and the writer. Refuses, with a
    ``ValueError`` naming the first fault, a mesh that is empty, has a non-finite coordinate,
    references a vertex that does not exist, has a degenerate triangle, or is not closed and
    consistently oriented.
    """
    if not isinstance(authorization, ExportAuthorization):
        raise ValueError(f"authorization must be an ExportAuthorization; got {authorization!r}")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must label the object; got an empty name")
    points = [tuple(vertex) for vertex in vertices]
    faces = [tuple(triangle) for triangle in triangles]
    if len(points) < 4 or len(faces) < 4:
        raise ValueError(
            f"a closed mesh needs at least 4 vertices and 4 triangles; got {len(points)} "
            f"and {len(faces)}"
        )
    for index, point in enumerate(points):
        if len(point) != 3 or not all(
            isinstance(c, int | float) and not isinstance(c, bool) and isfinite(c) for c in point
        ):
            raise ValueError(f"vertex {index} must be three finite numbers in mm; got {point}")
    for index, face in enumerate(faces):
        if len(face) != 3 or not all(
            isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(points) for v in face
        ):
            raise ValueError(
                f"triangle {index} must name three of the {len(points)} vertices; got {face}"
            )
        if len(set(face)) != 3:
            raise ValueError(f"triangle {index} repeats a vertex {face}, so it has no area")
    _closed_and_oriented(faces)  # type: ignore[arg-type]

    writer = f"anvilate {__version__} (anvilate.export.threemf)"
    metadata = [
        ("Application", writer),
        ("anvilate:standard", THREEMF_STANDARD),
        ("anvilate:writer", writer),
        *((f"anvilate:{key}", value) for key, value in authorization.metadata()),
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{_CORE}" xmlns:anvilate="{_ANVILATE}">',
        *(f"<metadata name={quoteattr(key)}>{escape(value)}</metadata>" for key, value in metadata),
        "<resources>",
        f'<object id="1" type="model" name={quoteattr(name.strip())}>',
        "<mesh>",
        "<vertices>",
        *(
            f'<vertex x="{_number(x)}" y="{_number(y)}" z="{_number(z)}"/>'
            for x, y, z in points  # type: ignore[misc]
        ),
        "</vertices>",
        "<triangles>",
        *(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces),  # type: ignore[misc]
        "</triangles>",
        "</mesh>",
        "</object>",
        "</resources>",
        '<build><item objectid="1"/></build>',
        "</model>",
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        for part, text in (
            ("[Content_Types].xml", _CONTENT_TYPES),
            ("_rels/.rels", _RELATIONSHIPS),
            (_MODEL_PART, "\n".join(lines) + "\n"),
        ):
            member = zipfile.ZipInfo(part, date_time=_EPOCH)
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o644 << 16
            package.writestr(member, text.encode("utf-8"))
    return buffer.getvalue()
