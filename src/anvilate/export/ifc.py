"""IFC export: a checked structural part as the element a building model holds.

IFC (ISO 16739-1:2018 is IFC4; ISO 16739-1:2024 is IFC 4.3) is how a structural part reaches
a building model. A STEP solid arrives as a lump of faces and loses what it is; an IFC
element arrives as a beam, a column or a plate, with its material, its mass, its part
number and, here, the verdict that was reached on it.

Four positions, each of them a refusal or a record:

* **A part is the class its element maps to, or it is refused.** :data:`IFC_ELEMENT_CLASSES`
  maps an element to an IFC class and predefined type. An element with no mapping is
  refused naming it, never written as an ``IfcBuildingElementProxy``: a proxy is a lump
  with a label, which is the loss this format exists to avoid.
* **A predefined type the declared schema lacks is not invented.** IFC 4.3 added
  ``BASE_PLATE``, ``GUSSET_PLATE`` and ``COVER_PLATE`` to ``IfcPlateTypeEnum``; IFC4 has
  none of them. In IFC4 such a plate is ``USERDEFINED`` with the name in ``ObjectType``,
  which is the schema's own rule for a type it does not enumerate. Both enumerations were
  read from the schemas IfcOpenShell 0.9.0 ships, not recalled.
* **The verdict travels with the element.** The ``Anvilate_Screening`` property set holds
  the part number, material, mass, validation status and card digest, and an unvalidated
  export carries its watermark there and in the file header both.
* **The same parts give the same bytes.** Every ``GlobalId`` is derived from the part's
  identity and the header's timestamp is fixed, so a file's digest identifies its content.

Geometry is a faceted boundary representation (``IfcFacetedBrep``) of the closed, welded,
outward-facing mesh the 3MF writer is held to. A standard profile with an extrusion, for a
member on a rolled section, is the next slice (add-ifc-structural-export 1.2).

IfcOpenShell (LGPL-3.0-or-later) is the optional ``ifc`` extra; nothing else imports it.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from .. import __version__
from ..refusal import RefusalError, Remedy
from .gate import ExportAuthorization

__all__ = [
    "IFC_ELEMENT_CLASSES",
    "IFC_SCHEMAS",
    "IfcElementMeasure",
    "IfcPart",
    "IfcSweptProfile",
    "ifc_class_for",
    "ifc_part",
    "measure_ifc",
    "render_ifc",
]

#: The schemas a file may declare: IFC4 (ISO 16739-1:2018), the default, and IFC 4.3
#: (ISO 16739-1:2024) as IfcOpenShell names its second addendum.
IFC_SCHEMAS = ("IFC4", "IFC4X3_ADD2")
IfcSchema = Literal["IFC4", "IFC4X3_ADD2"]

#: Each element an IFC file can hold, as (IFC class, predefined type). A predefined type
#: that is not in the declared schema's enumeration is written ``USERDEFINED`` with the
#: name in ``ObjectType`` (see :func:`ifc_class_for`).
IFC_ELEMENT_CLASSES: Mapping[str, tuple[str, str]] = {
    "base_plate": ("IfcPlate", "BASE_PLATE"),
    "beam_column_member": ("IfcColumn", "COLUMN"),
    "beam_member": ("IfcBeam", "BEAM"),
    "column_member": ("IfcColumn", "COLUMN"),
    "cover_plate": ("IfcPlate", "COVER_PLATE"),
    "gusset_plate": ("IfcPlate", "GUSSET_PLATE"),
    "shear_plate": ("IfcPlate", "SHEAR_PLATE"),
    "tension_member": ("IfcMember", "MEMBER"),
    "tube": ("IfcMember", "MEMBER"),
}

# The predefined types each schema enumerates for the classes above, as IfcOpenShell
# 0.9.0's schema reports them. A test reads them back from the toolkit, so this cannot
# drift from what the writer is checked against.
_ENUMERATED: Mapping[str, Mapping[str, frozenset[str]]] = {
    "IFC4": {
        "IfcBeam": frozenset({"BEAM", "JOIST", "HOLLOWCORE", "LINTEL", "SPANDREL", "T_BEAM"}),
        "IfcColumn": frozenset({"COLUMN", "PILASTER"}),
        "IfcMember": frozenset(
            {
                "BRACE",
                "CHORD",
                "COLLAR",
                "MEMBER",
                "MULLION",
                "PLATE",
                "POST",
                "PURLIN",
                "RAFTER",
                "STRINGER",
                "STRUT",
                "STUD",
            }
        ),  # fmt: skip
        "IfcPlate": frozenset({"CURTAIN_PANEL", "SHEET"}),
    },
    "IFC4X3_ADD2": {
        "IfcBeam": frozenset(
            {
                "BEAM",
                "CORNICE",
                "DIAPHRAGM",
                "EDGEBEAM",
                "GIRDER_SEGMENT",
                "HATSTONE",
                "HOLLOWCORE",
                "JOIST",
                "LINTEL",
                "PIERCAP",
                "SPANDREL",
                "T_BEAM",
            }
        ),  # fmt: skip
        "IfcColumn": frozenset(
            {"COLUMN", "PIERSTEM", "PIERSTEM_SEGMENT", "PILASTER", "STANDCOLUMN"}
        ),
        "IfcMember": frozenset(
            {
                "ARCH_SEGMENT",
                "BRACE",
                "CHORD",
                "COLLAR",
                "MEMBER",
                "MULLION",
                "PLATE",
                "POST",
                "PURLIN",
                "RAFTER",
                "STAY_CABLE",
                "STIFFENING_RIB",
                "STRINGER",
                "STRUCTURALCABLE",
                "STRUT",
                "STUD",
                "SUSPENDER",
                "SUSPENSION_CABLE",
                "TIEBAR",
            }
        ),  # fmt: skip
        "IfcPlate": frozenset(
            {
                "BASE_PLATE",
                "COVER_PLATE",
                "CURTAIN_PANEL",
                "FLANGE_PLATE",
                "GUSSET_PLATE",
                "SHEET",
                "SPLICE_PLATE",
                "STIFFENER_PLATE",
                "WEB_PLATE",
            }
        ),  # fmt: skip
    },
}

#: The custom property set every element carries. Not ``Pset_``: that prefix is the
#: standard's own and a custom set may not use it.
SCREENING_PSET = "Anvilate_Screening"

_EXPORT_GATE_SOURCE = "the authorization authorize_export issued for this part's scorecard"
_MAPPING_SOURCE = "anvilate.export.ifc.IFC_ELEMENT_CLASSES"
_MESH_SOURCE = "the part's tessellated CAD model (vertices and triangles in mm)"
# 2000-01-01, fixed, so identical content is identical bytes. The header field is the time
# the file was written, and a digest that changed every run would identify nothing.
_TIMESTAMP = "2000-01-01T00:00:00"


class _IfcInputError(RefusalError, ValueError):
    """An IFC export input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str, action: str = "replace") -> _IfcInputError:
    return _IfcInputError(
        message, remedies=(Remedy(action=action, subject=subject, source=source),)
    )


@dataclass(frozen=True)
class IfcSweptProfile:
    """A rolled section swept along a straight axis, as IFC's own profile definitions.

    ``kind`` is ``I`` (``IfcIShapeProfileDef``: ``width``, ``depth``, ``web``, ``flange``,
    ``fillet``), ``rectangle_hollow`` (``IfcRectangleHollowProfileDef``: ``width``,
    ``depth``, ``wall``, ``inner_fillet``, ``outer_fillet``) or ``circle_hollow``
    (``IfcCircleHollowProfileDef``: ``diameter``, ``wall``), every size in millimetres.
    The profile's ``width`` lies along ``across``, and the section is swept ``length`` mm
    along ``axis`` from ``start``, the point on the axis where the member begins.
    """

    kind: Literal["I", "rectangle_hollow", "circle_hollow"]
    designation: str
    dimensions: Mapping[str, float]
    length: float
    axis: tuple[float, float, float]
    across: tuple[float, float, float]
    start: tuple[float, float, float]


@dataclass(frozen=True)
class IfcPart:
    """One part to export: its identity, its mesh in millimetres, and what was found on it.

    ``tag`` identifies the part within the file and seeds its ``GlobalId``. ``vertices`` and
    ``triangles`` are a closed, outward-facing mesh in millimetres in the file's frame.
    ``card_digest`` is the digest of the scorecard the verdict came from, when there is one.
    """

    tag: str
    name: str
    element_type: str
    vertices: Sequence[tuple[float, float, float]]
    triangles: Sequence[tuple[int, int, int]]
    material: str | None = None
    mass_kg: float | None = None
    part_number: str | None = None
    card_digest: str | None = None
    extra: Mapping[str, str] = field(default_factory=dict)
    profile: IfcSweptProfile | None = None


@dataclass(frozen=True)
class IfcElementMeasure:
    """An element read back from a file: its class, tag, volume (mm³) and centroid (mm)."""

    ifc_class: str
    tag: str
    predefined_type: str
    object_type: str | None
    volume_mm3: float
    centroid_mm: tuple[float, float, float]
    bounds_mm: tuple[tuple[float, float, float], tuple[float, float, float]]
    representation: str


def ifc_class_for(element_type: str, schema: IfcSchema = "IFC4") -> tuple[str, str, str | None]:
    """``(class, PredefinedType, ObjectType)`` for an element in the declared schema.

    A predefined type the schema enumerates is written as itself; one it does not is
    written ``USERDEFINED`` with the name in ``ObjectType``. An element with no mapping is
    refused naming it.
    """
    if schema not in IFC_SCHEMAS:
        raise _refuse(
            f"schema {schema!r} is not one this writer declares; it writes {list(IFC_SCHEMAS)}",
            subject="schema",
            source="IFC_SCHEMAS",
            action="select",
        )
    if element_type not in IFC_ELEMENT_CLASSES:
        raise _refuse(
            f"the element {element_type!r} has no IFC class here, and is not exported as a "
            f"proxy; the mapped elements are {sorted(IFC_ELEMENT_CLASSES)}",
            subject=f"the {element_type} element",
            source=_MAPPING_SOURCE,
            action="select",
        )
    ifc_class, predefined = IFC_ELEMENT_CLASSES[element_type]
    if predefined in _ENUMERATED[schema][ifc_class]:
        return ifc_class, predefined, None
    return ifc_class, "USERDEFINED", predefined


def _guid(*seed: str) -> str:
    import ifcopenshell.guid

    return ifcopenshell.guid.compress(hashlib.sha256("\x1f".join(seed).encode()).hexdigest()[:32])


def _toolkit() -> Any:
    try:
        import ifcopenshell
    except ImportError as missing:  # pragma: no cover - exercised without the extra
        raise _refuse(
            "IFC export needs IfcOpenShell, the optional 'ifc' extra: pip install 'anvilate[ifc]'",
            subject="the ifc extra",
            source="pyproject.toml [project.optional-dependencies] ifc",
            action="add",
        ) from missing
    return ifcopenshell


def _checked(part: IfcPart) -> None:
    if not isinstance(part, IfcPart):
        raise _refuse(
            f"each part must be an IfcPart; got {part!r}", subject="parts", source=_MESH_SOURCE
        )
    if not part.tag.strip() or not part.name.strip():
        raise _refuse("a part needs a tag and a name", subject="parts", source=_MESH_SOURCE)
    if len(part.vertices) < 4 or len(part.triangles) < 4:
        raise _refuse(
            f"part {part.tag!r} has {len(part.vertices)} vertices and {len(part.triangles)} "
            "triangles; a closed solid needs at least 4 of each",
            subject=f"the {part.tag} mesh",
            source=_MESH_SOURCE,
        )
    for point in part.vertices:
        if len(point) != 3 or not all(math.isfinite(c) for c in point):
            raise _refuse(
                f"part {part.tag!r} has a vertex {point} that is not three finite numbers",
                subject=f"the {part.tag} mesh",
                source=_MESH_SOURCE,
            )
    for face in part.triangles:
        if len(set(face)) != 3 or not all(0 <= v < len(part.vertices) for v in face):
            raise _refuse(
                f"part {part.tag!r} has a triangle {face} that does not name three of its vertices",
                subject=f"the {part.tag} mesh",
                source=_MESH_SOURCE,
            )
    if part.mass_kg is not None and not (math.isfinite(part.mass_kg) and part.mass_kg > 0):
        raise _refuse(
            f"part {part.tag!r} states a mass of {part.mass_kg} kg; a mass is positive",
            subject=f"the {part.tag} mass",
            source=_MESH_SOURCE,
        )


def render_ifc(
    parts: Sequence[IfcPart],
    *,
    name: str,
    authorization: ExportAuthorization,
    schema: IfcSchema = "IFC4",
) -> bytes:
    """``parts`` as the bytes of one IFC file of the declared ``schema``.

    Each part is one element of the class its element maps to (:func:`ifc_class_for`),
    with a faceted B-rep, its material, the schema's common property set and the
    ``Anvilate_Screening`` set, contained in one storey of one building on one site.
    Lengths are millimetres and masses kilograms, declared in the file's unit assignment.
    """
    if not isinstance(authorization, ExportAuthorization):
        raise _refuse(
            f"authorization must be an ExportAuthorization; got {authorization!r}",
            subject="authorization",
            source=_EXPORT_GATE_SOURCE,
        )
    if not isinstance(name, str) or not name.strip():
        raise _refuse("name must label the file's project", subject="name", source=_MESH_SOURCE)
    if not parts:
        raise _refuse("an IFC file holds at least one part", subject="parts", source=_MESH_SOURCE)
    classes = []
    for part in parts:
        _checked(part)
        classes.append(ifc_class_for(part.element_type, schema))
    tags = [part.tag for part in parts]
    repeated = sorted({tag for tag in tags if tags.count(tag) > 1})
    if repeated:
        raise _refuse(
            f"these part tags are used twice: {repeated}; each element is one part",
            subject="parts",
            source=_MESH_SOURCE,
        )

    ifcopenshell = _toolkit()
    f = ifcopenshell.file(schema=schema)
    _header(f, name.strip(), authorization)
    project_name = name.strip()

    def owned(entity: str, seed: str, **attributes: Any) -> Any:
        return f.create_entity(entity, GlobalId=_guid(project_name, entity, seed), **attributes)

    units = f.create_entity(
        "IfcUnitAssignment",
        Units=[
            f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE"),
            f.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
            f.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
            f.create_entity("IfcSIUnit", UnitType="MASSUNIT", Prefix="KILO", Name="GRAM"),
            f.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN"),
        ],
    )
    origin = f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
    world = f.create_entity("IfcAxis2Placement3D", Location=origin)
    context = f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=world,
    )
    body = f.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=context,
        TargetView="MODEL_VIEW",
    )
    project = owned(
        "IfcProject", "", Name=project_name, UnitsInContext=units, RepresentationContexts=[context]
    )
    placement = f.create_entity("IfcLocalPlacement", RelativePlacement=world)
    site = owned("IfcSite", "", Name="Site", ObjectPlacement=placement)
    building = owned("IfcBuilding", "", Name="Building", ObjectPlacement=placement)
    storey = owned("IfcBuildingStorey", "", Name="Storey", ObjectPlacement=placement)
    owned("IfcRelAggregates", "project", RelatingObject=project, RelatedObjects=[site])
    owned("IfcRelAggregates", "site", RelatingObject=site, RelatedObjects=[building])
    owned("IfcRelAggregates", "building", RelatingObject=building, RelatedObjects=[storey])

    elements = []
    materials: dict[str, Any] = {}
    for part, (ifc_class, predefined, object_type) in zip(parts, classes, strict=True):
        if part.profile is not None:
            solid, kind = _swept(f, part.profile), "SweptSolid"
        else:
            solid, kind = _faceted(f, part), "Brep"
        shape = f.create_entity(
            "IfcProductDefinitionShape",
            Representations=[
                f.create_entity(
                    "IfcShapeRepresentation",
                    ContextOfItems=body,
                    RepresentationIdentifier="Body",
                    RepresentationType=kind,
                    Items=[solid],
                )
            ],
        )
        element = owned(
            ifc_class,
            part.tag,
            Name=part.name,
            Tag=part.part_number or part.tag,
            ObjectType=object_type,
            PredefinedType=predefined,
            ObjectPlacement=f.create_entity(
                "IfcLocalPlacement", PlacementRelTo=placement, RelativePlacement=world
            ),
            Representation=shape,
        )
        elements.append(element)
        if part.material:
            if part.material not in materials:
                materials[part.material] = f.create_entity("IfcMaterial", Name=part.material)
        _property_sets(f, owned, element, part, ifc_class, authorization, schema)
    for material_name, material in sorted(materials.items()):
        users = [e for e, p in zip(elements, parts, strict=True) if p.material == material_name]
        owned(
            "IfcRelAssociatesMaterial",
            f"material:{material_name}",
            RelatingMaterial=material,
            RelatedObjects=users,
        )
    owned(
        "IfcRelContainedInSpatialStructure",
        "storey",
        RelatingStructure=storey,
        RelatedElements=elements,
    )
    return f.to_string().encode("utf-8")


def _faceted(f: Any, part: IfcPart) -> Any:
    """The part's mesh as a faceted B-rep, one face per triangle on shared points."""
    points = [
        f.create_entity("IfcCartesianPoint", Coordinates=tuple(map(float, v)))
        for v in part.vertices
    ]
    faces = [
        f.create_entity(
            "IfcFace",
            Bounds=[
                f.create_entity(
                    "IfcFaceOuterBound",
                    Bound=f.create_entity("IfcPolyLoop", Polygon=[points[i] for i in tri]),
                    Orientation=True,
                )
            ],
        )
        for tri in part.triangles
    ]
    return f.create_entity(
        "IfcFacetedBrep", Outer=f.create_entity("IfcClosedShell", CfsFaces=faces)
    )


def _swept(f: Any, profile: IfcSweptProfile) -> Any:
    """The profile definition the receiving tool keeps as a section, extruded along its axis."""
    size = profile.dimensions
    centre = f.create_entity(
        "IfcAxis2Placement2D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0)),
    )
    common = {"ProfileType": "AREA", "ProfileName": profile.designation, "Position": centre}
    if profile.kind == "I":
        area = f.create_entity(
            "IfcIShapeProfileDef",
            **common,
            OverallWidth=size["width"],
            OverallDepth=size["depth"],
            WebThickness=size["web"],
            FlangeThickness=size["flange"],
            FilletRadius=size["fillet"] or None,
        )
    elif profile.kind == "rectangle_hollow":
        area = f.create_entity(
            "IfcRectangleHollowProfileDef",
            **common,
            XDim=size["width"],
            YDim=size["depth"],
            WallThickness=size["wall"],
            InnerFilletRadius=size["inner_fillet"] or None,
            OuterFilletRadius=size["outer_fillet"] or None,
        )
    else:
        area = f.create_entity(
            "IfcCircleHollowProfileDef",
            **common,
            Radius=size["diameter"] / 2,
            WallThickness=size["wall"],
        )
    position = f.create_entity(
        "IfcAxis2Placement3D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=tuple(profile.start)),
        Axis=f.create_entity("IfcDirection", DirectionRatios=tuple(profile.axis)),
        RefDirection=f.create_entity("IfcDirection", DirectionRatios=tuple(profile.across)),
    )
    return f.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=area,
        Position=position,
        ExtrudedDirection=f.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
        Depth=float(profile.length),
    )


def _header(f: Any, name: str, authorization: ExportAuthorization) -> None:
    header = f.header
    header.file_description.description = (
        "ViewDefinition [ReferenceView]",
        *authorization.watermark(),
    )
    header.file_name.name = name
    header.file_name.time_stamp = _TIMESTAMP
    header.file_name.preprocessor_version = "IfcOpenShell"
    header.file_name.originating_system = f"anvilate {__version__}"
    header.file_name.authorization = authorization.status


def _property_sets(
    f: Any,
    owned: Any,
    element: Any,
    part: IfcPart,
    ifc_class: str,
    authorization: ExportAuthorization,
    schema: str,
) -> None:
    def single(prop: str, value: Any) -> Any:
        return f.create_entity("IfcPropertySingleValue", Name=prop, NominalValue=value)

    common = [
        single("Reference", f.create_entity("IfcIdentifier", part.part_number or part.tag)),
        single("LoadBearing", f.create_entity("IfcBoolean", True)),
    ]
    common_name = f"Pset_{ifc_class.removeprefix('Ifc')}Common"
    screening = [
        single("ElementType", f.create_entity("IfcLabel", part.element_type)),
        single("ValidationStatus", f.create_entity("IfcLabel", authorization.status)),
    ]
    for key, value in authorization.metadata():
        screening.append(single(key, f.create_entity("IfcText", value)))
    if part.part_number:
        screening.append(single("PartNumber", f.create_entity("IfcIdentifier", part.part_number)))
    if part.material:
        screening.append(single("Material", f.create_entity("IfcLabel", part.material)))
    if part.mass_kg is not None:
        screening.append(single("Mass", f.create_entity("IfcMassMeasure", float(part.mass_kg))))
    if part.card_digest:
        screening.append(single("CardDigest", f.create_entity("IfcIdentifier", part.card_digest)))
    for key, value in sorted(part.extra.items()):
        screening.append(single(key, f.create_entity("IfcText", value)))
    for pset_name, properties in ((common_name, common), (SCREENING_PSET, screening)):
        pset = owned(
            "IfcPropertySet", f"{part.tag}:{pset_name}", Name=pset_name, HasProperties=properties
        )
        owned(
            "IfcRelDefinesByProperties",
            f"{part.tag}:{pset_name}:rel",
            RelatingPropertyDefinition=pset,
            RelatedObjects=[element],
        )
    del schema


def measure_ifc(data: bytes) -> list[IfcElementMeasure]:
    """Every element in an IFC file, re-read: its class, tag, volume and centroid.

    The geometry is evaluated by IfcOpenShell's own kernel from the file, not from the mesh
    that wrote it, and the volume and centroid are the mesh integrals of what it returns.
    """
    _toolkit()
    import ifcopenshell
    import ifcopenshell.geom

    model = ifcopenshell.file.from_string(data.decode("utf-8"))
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    measured = []
    for element in model.by_type("IfcElement"):
        nan = (math.nan, math.nan, math.nan)
        bounds = (nan, nan)
        kind = ""
        if element.Representation is None:
            volume, centroid = 0.0, nan
        else:
            kind = element.Representation.Representations[0].RepresentationType
            shape: Any = ifcopenshell.geom.create_shape(settings, element)
            verts, faces = shape.geometry.verts, shape.geometry.faces
            # The kernel works in metres whatever the file declares.
            scale = 1000.0
            points = [
                (verts[i] * scale, verts[i + 1] * scale, verts[i + 2] * scale)
                for i in range(0, len(verts), 3)
            ]
            volume, centroid = _integrals(
                points,
                [(faces[i], faces[i + 1], faces[i + 2]) for i in range(0, len(faces), 3)],
            )
            low = tuple(min(p[axis] for p in points) for axis in range(3))
            high = tuple(max(p[axis] for p in points) for axis in range(3))
            bounds = (low, high)  # type: ignore[assignment]
        measured.append(
            IfcElementMeasure(
                ifc_class=element.is_a(),
                tag=element.Tag,
                predefined_type=element.PredefinedType,
                object_type=element.ObjectType,
                volume_mm3=volume,
                centroid_mm=centroid,
                bounds_mm=bounds,
                representation=kind,
            )
        )
    return measured


def _integrals(
    vertices: Sequence[tuple[float, float, float]], triangles: Sequence[tuple[int, int, int]]
) -> tuple[float, tuple[float, float, float]]:
    """The enclosed volume and its centroid, by the divergence theorem over the triangles."""
    volume = 0.0
    moment = [0.0, 0.0, 0.0]
    for a, b, c in triangles:
        p, q, r = vertices[a], vertices[b], vertices[c]
        signed = (
            p[0] * (q[1] * r[2] - q[2] * r[1])
            - p[1] * (q[0] * r[2] - q[2] * r[0])
            + p[2] * (q[0] * r[1] - q[1] * r[0])
        ) / 6.0
        volume += signed
        for axis in range(3):
            moment[axis] += signed * (p[axis] + q[axis] + r[axis]) / 4.0
    if volume == 0.0:
        return 0.0, (math.nan, math.nan, math.nan)
    return volume, (moment[0] / volume, moment[1] / volume, moment[2] / volume)


def ifc_part(
    spec: Any,
    built: Any,
    card: Any,
    *,
    tag: str | None = None,
    part_number: str | None = None,
) -> IfcPart:
    """The :class:`IfcPart` a built spec exports as: its mesh, identity, mass and verdict.

    A member on a section the bundled table names as a rolled I shape or HSS also carries
    that section as an :class:`IfcSweptProfile`, framed from the built solid, so the file
    holds the profile and its extrusion rather than the faces. ``card`` is the part's
    scorecard; its digest is the one a review of it would cite.
    """
    from .. import __version__ as version
    from ..geometry import _mesh_for_3mf
    from ..review import artifact_digest
    from ..standards.materials import default_materials_db

    vertices, triangles = _mesh_for_3mf(built)
    material = getattr(getattr(spec, "material", None), "ref", None)
    mass = None
    if material:
        try:
            density = default_materials_db().get(str(material)).density.quantity
            mass = float(built.volume_mm3) * density.to("kg/mm**3").magnitude
        except (KeyError, ValueError):
            mass = None
    return IfcPart(
        tag=tag or built.name,
        name=built.name,
        element_type=spec.element_type,
        vertices=vertices,
        triangles=triangles,
        material=str(material) if material else None,
        mass_kg=mass,
        part_number=part_number,
        card_digest="sha256:" + artifact_digest(card, toolchain=f"anvilate {version}"),
        profile=_profile_of(spec, built),
    )


def _profile_of(spec: Any, built: Any) -> IfcSweptProfile | None:
    """The rolled section a member is drawn from, as a swept profile, or ``None``."""
    named = (spec.element_params or {}).get("section")
    if not isinstance(named, str):
        return None
    from ..packs.structural import _hollow_bar, _pipe_record
    from ..standards.profiles import resolve_profile

    kind: Literal["I", "rectangle_hollow", "circle_hollow"]
    # A tube, a box or a pipe named by its dimensions or its schedule needs no table. The
    # box is welded from plates, so its corners are square, as it is drawn.
    hollow = _hollow_bar(named)
    pipe = _pipe_record(named)
    if hollow is not None and len(hollow) == 2:
        kind, dimensions = "circle_hollow", {"diameter": hollow[0], "wall": hollow[1]}
    elif hollow is not None:
        kind = "rectangle_hollow"
        dimensions = {
            "width": hollow[0],
            "depth": hollow[1],
            "wall": hollow[2],
            "inner_fillet": 0.0,
            "outer_fillet": 0.0,
        }
    elif pipe is not None:
        outside, inside = _mm(pipe.outside_diameter), _mm(pipe.inside_diameter)
        kind, dimensions = "circle_hollow", {"diameter": outside, "wall": (outside - inside) / 2}
    else:
        try:
            profile = resolve_profile(named)
        except (KeyError, ValueError):
            return None
        return _rolled(named, profile, built)
    return _framed(named, kind, dimensions, built)


def _mm(value: Any) -> float:
    return float(getattr(value, "quantity", value).to("mm").magnitude)


def _rolled(named: str, profile: Any, built: Any) -> IfcSweptProfile | None:
    """A table profile: a rolled I shape, or an AISC HSS (which needs the fetched table)."""
    from ..standards.profiles import HollowProfile, RolledProfile

    mm = _mm
    kind: Literal["I", "rectangle_hollow", "circle_hollow"]
    if isinstance(profile, RolledProfile):
        kind = "I"
        dimensions = {
            "width": mm(profile.flange_width),
            "depth": mm(profile.depth),
            "web": mm(profile.web_thickness),
            "flange": mm(profile.flange_thickness),
            "fillet": mm(profile.root_radius),
        }
    elif isinstance(profile, HollowProfile) and profile.breadth is not None:
        wall = mm(profile.wall_thickness)
        kind = "rectangle_hollow"
        # AISC's rolled HSS corner: an outside radius of twice the design wall, the rule
        # the section's own properties are computed on.
        dimensions = {
            "width": mm(profile.breadth),
            "depth": mm(profile.depth),
            "wall": wall,
            "inner_fillet": wall,
            "outer_fillet": 2 * wall,
        }
    elif isinstance(profile, HollowProfile):
        kind = "circle_hollow"
        dimensions = {"diameter": mm(profile.depth), "wall": mm(profile.wall_thickness)}
    else:
        return None
    return _framed(named, kind, dimensions, built)


def _framed(
    named: str,
    kind: Literal["I", "rectangle_hollow", "circle_hollow"],
    dimensions: dict[str, float],
    built: Any,
) -> IfcSweptProfile:
    """The profile placed as the built member is: along its length, width across its width."""
    box = built.shape.bounding_box()
    low, high = (box.min.X, box.min.Y, box.min.Z), (box.max.X, box.max.Y, box.max.Z)
    extent = [b - a for a, b in zip(low, high, strict=True)]
    length = float(built.dimensions_mm.get("length", max(extent)))
    along = min(range(3), key=lambda i: abs(extent[i] - length))
    others = [i for i in range(3) if i != along]
    width = dimensions.get("width", dimensions.get("diameter", 0.0))
    side = min(others, key=lambda i: abs(extent[i] - width))
    unit = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    start = [(a + b) / 2 for a, b in zip(low, high, strict=True)]
    start[along] = low[along]
    return IfcSweptProfile(
        kind=kind,
        designation=named,
        dimensions=dimensions,
        length=length,
        axis=unit[along],
        across=unit[side],
        start=(start[0], start[1], start[2]),
    )
