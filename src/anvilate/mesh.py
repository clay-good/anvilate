"""What a tagged face is, after a mesher has been through it.

A load or a support in the FEA tier lands on a face the spec NAMED — ``top``, ``east``,
the face a bolt pattern opens on. The name is the one thing that does not survive the
trip. Anvilate writes STEP, a mesher reads it, and whether a face's name comes through is
unconfirmed at best: Gmsh's maintainer called carrying STEP names "still a little bit
tricky", and after a boolean ``fragment`` it is not clear which face is even which.

So the name is not what is carried across. The SHAPE is. :func:`face_signatures` records,
when the solid is built, what each tagged face *is*: how much area it has, the point it is
centred on, and — where it is flat — the direction it faces. :func:`match_face_signatures`
puts those against the faces that came back.

**The match is verified, never assumed.** A tag that matches nothing, a tag that matches
more than one face, and a face that two tags both claim are each refused by name rather
than resolved by picking. A load applied to the wrong face is not a wrong number a reader
can argue with; it is a different problem solved correctly, and nothing downstream would
say so.

The centroid is the area centroid (``CenterOf.MASS``) and not the parametric centre. On a
cylinder the two are not the same point — the parametric centre of a shaft's outside
surface sits ON the surface, a radius off the axis — and a parametric point is an artefact
of how the face happens to be parameterised, which is exactly what a round trip is free to
change. For the same reason a curved face records no normal: it does not have one, and the
normal at its parametric centre would be recording the artefact again.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from ._models import FrozenMap, Named, StatableModel, each_one
from .refusal import RefusalError, Remedy

__all__ = [
    "FaceSignature",
    "SignatureMatch",
    "face_signatures",
    "match_face_signatures",
    "ROUND_TRIP_AREA_TOLERANCE",
    "ROUND_TRIP_DISTANCE_TOLERANCE_MM",
]

#: How far a face may move and still be the same face. These are the width of floating-point
#: noise through a STEP write and read, not a physical tolerance: a mesher that moves a
#: centroid further than this has not re-read the face, it has changed it, and a match that
#: refuses is the right answer. The value a particular mesher needs is that mesher's to
#: state, which is why both are parameters; these are what they default to until one is
#: wired in and measured.
ROUND_TRIP_AREA_TOLERANCE = 1e-6
ROUND_TRIP_DISTANCE_TOLERANCE_MM = 1e-6

_SOURCE = "the tagged faces of the built solid"


class _MeshInputError(RefusalError, ValueError):
    """A signature or a match that cannot be used as stated."""


def _refuse(message: str, *, subject: str) -> _MeshInputError:
    return _MeshInputError(
        message, remedies=(Remedy(action="correct", subject=subject, source=_SOURCE),)
    )


class FaceSignature(StatableModel):
    """One tagged face, as the shape that identifies it rather than the name it had."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tag: Named
    area_mm2: float = Field(gt=0, allow_inf_nan=False)
    centroid_mm: tuple[float, float, float]
    # Flat faces only. A curved face has no single normal; see this module's docstring.
    normal: tuple[float, float, float] | None = None

    @model_validator(mode="after")
    def _real(self) -> FaceSignature:
        for value in self.centroid_mm:
            if not math.isfinite(value):
                raise _refuse(f"face '{self.tag}' has a centroid at {self.centroid_mm}; "
                              "a centroid is three finite millimetres",
                              subject="centroid_mm")  # fmt: skip
        if self.normal is not None:
            length = math.sqrt(sum(c * c for c in self.normal))
            if not math.isfinite(length) or not math.isclose(length, 1.0, rel_tol=1e-6):
                raise _refuse(f"face '{self.tag}' states a normal of {self.normal}, whose "
                              f"length is {length:.6g}; a normal is a unit direction",
                              subject="normal")  # fmt: skip
        return self

    def __str__(self) -> str:
        where = ", ".join(f"{c:.4g}" for c in self.centroid_mm)
        facing = "" if self.normal is None else (
            " facing " + ", ".join(f"{c:.3g}" for c in self.normal))  # fmt: skip
        return f"{self.tag}: {self.area_mm2:.6g} mm² centred at ({where}) mm{facing}"


class SignatureMatch(StatableModel):
    """Which face of the imported solid is which tag, and nothing that was guessed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The index into the imported faces, by the tag it carries.
    faces: FrozenMap[str, int]

    def __str__(self) -> str:
        return ", ".join(f"{tag} -> face {index}" for tag, index in sorted(self.faces.items()))


def face_signatures(faces: Mapping[str, Sequence[Any]]) -> tuple[FaceSignature, ...]:
    """The signature of every tagged face of a built solid, in tag order.

    ``faces`` is the ``faces`` mapping of a :class:`~anvilate.geometry.BuiltGeometry`: the
    kernel's faces under the names the pattern gave them. A tag carrying several faces gets
    a signature each, under the same tag, because each has to be found again on its own.
    """
    from build123d import CenterOf, GeomType

    if not isinstance(faces, Mapping) or not faces:
        raise _refuse("faces is the tagged faces of a built solid, and it has none",
                      subject="faces")  # fmt: skip
    signed: list[FaceSignature] = []
    for tag, tagged in faces.items():
        for face in tagged:
            flat = face.geom_type == GeomType.PLANE
            centre = face.center(CenterOf.MASS)
            normal = None
            if flat:
                direction = face.normal_at(face.center())
                normal = tuple(round(float(c), 12) for c in direction)
            signed.append(FaceSignature(
                tag=tag, area_mm2=float(face.area),
                centroid_mm=tuple(float(c) for c in centre), normal=normal,
            ))  # fmt: skip
    return tuple(signed)


def _same(recorded: FaceSignature, found: FaceSignature, area: float, distance: float) -> bool:
    """Whether two signatures describe one face, within the tolerances given."""
    if not math.isclose(recorded.area_mm2, found.area_mm2, rel_tol=area):
        return False
    apart = math.dist(recorded.centroid_mm, found.centroid_mm)
    if apart > distance:
        return False
    if (recorded.normal is None) != (found.normal is None):
        return False
    if recorded.normal is None or found.normal is None:
        return True
    # Direction, not sign-free: a face's outward normal is which way it faces, and two
    # faces of a plate agree on everything else and differ only in this.
    return math.dist(recorded.normal, found.normal) <= 1e-6 + distance


def match_face_signatures(
    recorded: Sequence[FaceSignature],
    found: Sequence[FaceSignature],
    *,
    area_tolerance: float = ROUND_TRIP_AREA_TOLERANCE,
    distance_tolerance_mm: float = ROUND_TRIP_DISTANCE_TOLERANCE_MM,
) -> SignatureMatch:
    """Which imported face is which tag, refusing anything it cannot say for certain.

    Three refusals, and each of them is a setup failure rather than a result: a tag that
    matches no imported face, a tag that matches more than one, and an imported face that
    two tags both claim. None of them is resolved by choosing, because a load applied to
    the wrong face is a different problem solved correctly and nothing downstream says so.

    ``found`` carries whatever tags the importer had — usually none, and they are not read:
    the whole point is that the name did not come through and the shape did.
    """
    recorded = each_one(recorded, FaceSignature, named="recorded")
    found = each_one(found, FaceSignature, named="found")
    if not recorded:
        raise _refuse("recorded is the signatures taken when the solid was built, and it "
                      "is empty", subject="recorded")  # fmt: skip
    if not found:
        raise _refuse("found is the signatures of the imported faces, and it is empty; a "
                      "mesher that returned no face has not read the solid",
                      subject="found")  # fmt: skip
    if area_tolerance <= 0 or distance_tolerance_mm <= 0:
        raise _refuse(f"the tolerances are positive; got {area_tolerance} and "
                      f"{distance_tolerance_mm} mm", subject="area_tolerance")  # fmt: skip
    matched: dict[str, int] = {}
    claimed: dict[int, str] = {}
    for signature in recorded:
        hits = [i for i, candidate in enumerate(found)
                if _same(signature, candidate, area_tolerance, distance_tolerance_mm)]  # fmt: skip
        if not hits:
            raise _refuse(f"no imported face matches {signature}; the solid the mesher read "
                          "is not the solid these signatures were taken from, or the "
                          "tolerances are tighter than its round trip",
                          subject="found")  # fmt: skip
        if len(hits) > 1:
            raise _refuse(f"{len(hits)} imported faces match {signature}, at indices "
                          f"{hits}; a tag that names more than one face cannot be applied "
                          "to one of them by choosing", subject="found")  # fmt: skip
        if signature.tag in matched:
            raise _refuse(f"tag '{signature.tag}' is recorded on more than one face; each "
                          "face of a tag is matched on its own and they cannot share one "
                          "entry", subject="recorded")  # fmt: skip
        taken = claimed.get(hits[0])
        if taken is not None:
            raise _refuse(f"imported face {hits[0]} is claimed by '{taken}' and by "
                          f"'{signature.tag}'; one face carries one tag",
                          subject="recorded")  # fmt: skip
        matched[signature.tag] = hits[0]
        claimed[hits[0]] = signature.tag
    return SignatureMatch(faces=matched)
