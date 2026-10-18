"""Interface contracts: what each item offers the rest of a product, typed and checked.

An interface is a named, typed offer an item makes: a bolt pattern, a shaft, a bore, a
mounting face. It is declared once on the item (a placeholder or a purchased component),
and a product connects two interfaces by name rather than naming features in mates; the
mate is derived from the pair. The kinds are a closed vocabulary (:data:`KINDS`), each
with the parameters it requires, and :data:`COMPATIBLE` says which kinds may meet, what
must agree between them, and what the pairing checks:

- a bolt pattern meets a bolt pattern or a tapped pattern, on faces, hole by hole, and
  the holes must line up (the combination's own pattern-agreement check);
- a shaft meets a bore, a pin a hole, a keyed shaft a keyed hub, on a shared axis, and
  the shaft must not be larger than the bore;
- a mounting face meets a mounting face, a rail a carriage, a connector envelope a
  connector envelope, face to face.

A pairing the table does not list is refused before any geometry is built, naming both
kinds and what the first may meet. A product accounts for every interface it places:
connected, declared open with a reason, or reported unconnected on its card; a kind that
takes one partner and has two is reported.
"""

from __future__ import annotations

import difflib
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from ._models import EMPTY_MAP, FrozenMap, Named, StatableModel
from .refusal import RefusalError, Remedy
from .units import Quantity

__all__ = [
    "KINDS",
    "COMPATIBLE",
    "InterfaceError",
    "Interface",
    "PartInterface",
    "partners_of",
]

_SOURCE = "the interface vocabulary: each kind, its parameters, and what it may meet"

#: Every interface kind: how it is located (on a ``face``, along an ``axis``), the
#: parameters it requires with their dimensions, and how many partners it takes.
KINDS: dict[str, tuple[Literal["face", "axis"], dict[str, str], int | None]] = {
    "mounting_face": ("face", {}, 1),
    "bolt_pattern": ("face", {}, 1),
    "tapped_pattern": ("face", {}, 1),
    "shaft": ("axis", {"diameter": "[length]"}, 1),
    "bore": ("axis", {"diameter": "[length]"}, 1),
    "pin": ("axis", {"diameter": "[length]"}, 1),
    "hole": ("axis", {"diameter": "[length]"}, 1),
    "keyed_shaft": ("axis", {"diameter": "[length]", "key_width": "[length]"}, 1),
    "keyed_hub": ("axis", {"diameter": "[length]", "key_width": "[length]"}, 1),
    "rail": ("face", {"width": "[length]"}, None),
    "carriage": ("face", {"width": "[length]"}, 1),
    "connector_envelope": (
        "face",
        {"width": "[length]", "height": "[length]", "depth": "[length]"},
        1,
    ),
}

#: The pairings that may connect: (kind, kind) → (parameters that must agree, checks run).
#: Listed once per unordered pair; :func:`partners_of` reads it both ways.
COMPATIBLE: dict[tuple[str, str], tuple[tuple[str, ...], tuple[str, ...]]] = {
    ("bolt_pattern", "bolt_pattern"): ((), ("hole pattern",)),
    ("bolt_pattern", "tapped_pattern"): ((), ("hole pattern",)),
    ("mounting_face", "mounting_face"): ((), ()),
    ("shaft", "bore"): (("diameter",), ("diameter",)),
    ("pin", "hole"): (("diameter",), ("diameter",)),
    ("keyed_shaft", "keyed_hub"): (("diameter", "key_width"), ("diameter", "key_width")),
    ("rail", "carriage"): (("width",), ("width",)),
    ("connector_envelope", "connector_envelope"): (("width", "height", "depth"), ()),
}


def partners_of(kind: str) -> tuple[str, ...]:
    """The kinds ``kind`` may connect to, in the order the table lists them."""
    found: list[str] = []
    for first, second in COMPATIBLE:
        if first == kind and second not in found:
            found.append(second)
        if second == kind and first not in found:
            found.append(first)
    return tuple(found)


class InterfaceError(RefusalError, ValueError):
    """An interface or connection that cannot be used as stated."""


def _refuse(message: str, *, subject: str) -> InterfaceError:
    return InterfaceError(
        message, remedies=(Remedy(action="correct", subject=subject, source=_SOURCE),)
    )


class Interface(StatableModel):
    """One interface an item offers: its name, kind, where it is, and its parameters.

    A ``face`` kind names the face it is on (``top``, ``bottom``…); a pattern kind also
    lists the item's ``holes`` it is made of, by tag. An ``axis`` kind names the item's own
    axis it runs along. ``parameters`` are the kind's required values (:data:`KINDS`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    kind: str
    face: Literal["top", "bottom", "left", "right", "front", "back"] | None = None
    axis: Literal["x", "y", "z"] | None = None
    holes: tuple[Named, ...] = Field(default=(), max_length=64)
    parameters: FrozenMap[str, Quantity] = Field(default_factory=lambda: EMPTY_MAP)
    # A catalog part's axial interface is the round feature it is bound to: its axis runs
    # through that feature, not through the part's origin.
    feature: Named | None = None

    @model_validator(mode="after")
    def _a_kind(self) -> Interface:
        if self.kind not in KINDS:
            near = difflib.get_close_matches(self.kind, KINDS, n=3, cutoff=0.4)
            raise _refuse(f"interface '{self.name}' is of kind '{self.kind}', which is not "
                          f"one; nearest: {', '.join(near) or ', '.join(KINDS)}",
                          subject="kind")  # fmt: skip
        located, wanted, _partners = KINDS[self.kind]
        if located == "face" and (self.face is None or self.axis is not None):
            raise _refuse(f"interface '{self.name}' is a {self.kind}, located by the face it "
                          "is on and not an axis; state face", subject="face")  # fmt: skip
        if located == "axis" and (self.axis is None or self.face is not None):
            raise _refuse(f"interface '{self.name}' is a {self.kind}, located by the axis it "
                          "runs along and not a face; state axis", subject="axis")  # fmt: skip
        patterned = self.kind in ("bolt_pattern", "tapped_pattern")
        if patterned != bool(self.holes):
            raise _refuse(f"interface '{self.name}' is a {self.kind}; "
                          + ("a pattern lists the holes it is made of" if patterned
                             else "only a pattern lists holes"), subject="holes")  # fmt: skip
        for name, dimension in wanted.items():
            value = self.parameters.get(name)
            if value is None:
                raise _refuse(f"interface '{self.name}' is a {self.kind} and states no {name}; "
                              f"a {self.kind} needs {name} as a {dimension}, such as mm",
                              subject="parameters")  # fmt: skip
            if not value.has_dimension(dimension) or not value.magnitude > 0:
                raise _refuse(f"interface '{self.name}' {name} is {value}; it is a positive "
                              f"{dimension}", subject="parameters")  # fmt: skip
        unread = sorted(set(self.parameters) - set(wanted))
        if unread:
            takes = ", ".join(wanted) or "none"
            raise _refuse(f"interface '{self.name}' states {unread}, which a {self.kind} does "
                          f"not take ({takes})", subject="parameters")  # fmt: skip
        return self


def check_interfaces(interfaces: tuple[Interface, ...], holes: set[str], owner: str) -> None:
    """Refuse two interfaces with one name, or a pattern naming a hole ``owner`` lacks."""
    names = [i.name for i in interfaces]
    doubled = sorted({n for n in names if names.count(n) > 1})
    if doubled:
        raise _refuse(f"{owner} offers interfaces {doubled} twice; a name is unique within "
                      "its item", subject="name")  # fmt: skip
    for interface in interfaces:
        missing = [tag for tag in interface.holes if tag not in holes]
        if missing:
            raise _refuse(f"{owner} interface '{interface.name}' names holes {missing}, which "
                          f"it does not have ({', '.join(sorted(holes)) or 'none'})",
                          subject="holes")  # fmt: skip


_FROM_AXIS = {(0, 1): "right", (0, -1): "left", (1, 1): "back", (1, -1): "front",
              (2, 1): "top", (2, -1): "bottom"}  # fmt: skip
_ALONG = {"top": 2, "bottom": 2, "right": 0, "left": 0, "back": 1, "front": 1}
#: The kinds a catalog part can offer: the ones its built features fully state.
PART_KINDS = ("mounting_face", "bolt_pattern", "tapped_pattern", "shaft", "bore", "pin", "hole")


class PartInterface(StatableModel):
    """An interface on a catalog part, bound to the part's tagged features.

    Its frame and parameters are read from the built features, never restated: a pattern's
    holes and the face they open on, an axial kind's axis and diameter. A ``mounting_face``
    names its ``face`` and no feature. ``face`` may also name the far face of a pattern of
    through holes, along the same axis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    kind: str
    features: tuple[Named, ...] = Field(default=(), max_length=64)
    face: Literal["top", "bottom", "left", "right", "front", "back"] | None = None

    @model_validator(mode="after")
    def _a_binding(self) -> PartInterface:
        if self.kind not in PART_KINDS:
            near = difflib.get_close_matches(self.kind, KINDS, n=3, cutoff=0.4)
            nearest = ", ".join(near) or ", ".join(KINDS)
            where = ("a part's features do not state its parameters; offer it on a "
                     "placeholder or component" if self.kind in KINDS
                     else f"it is not a kind; nearest: {nearest}")  # fmt: skip
            raise _refuse(f"interface '{self.name}' is a {self.kind} on a part: {where}",
                          subject="kind")  # fmt: skip
        if self.kind == "mounting_face":
            if self.face is None or self.features:
                raise _refuse(f"interface '{self.name}' is a mounting_face: it names its face "
                              "and no feature", subject="face")  # fmt: skip
        elif self.kind in ("bolt_pattern", "tapped_pattern") and len(self.features) < 2:
            raise _refuse(f"interface '{self.name}' is a {self.kind}: it names the two or more "
                          "holes it is made of", subject="features")  # fmt: skip
        elif KINDS[self.kind][0] == "axis" and (len(self.features) != 1 or self.face):
            raise _refuse(f"interface '{self.name}' is a {self.kind}: it names the one round "
                          "feature it runs along, and no face", subject="features")  # fmt: skip
        return self

    def resolve(self, features: dict[str, object], owner: str) -> Interface:
        """This interface as the built part states it, from its features by tag."""
        missing = [tag for tag in self.features if tag not in features]
        if missing:
            raise _refuse(f"{owner} interface '{self.name}' is bound to {missing}, which the "
                          f"built part does not have ({', '.join(sorted(features)) or 'none'})",
                          subject="features")  # fmt: skip
        if self.kind == "mounting_face":
            return Interface(name=self.name, kind=self.kind, face=self.face)
        bound = [features[tag] for tag in self.features]
        axes = []
        for feature in bound:
            axis = tuple(float(v) for v in feature.axis)  # type: ignore[attr-defined]
            index = max(range(3), key=lambda i: abs(axis[i]))
            if abs(abs(axis[index]) - 1) > 1e-6:
                raise _refuse(f"{owner} interface '{self.name}' is bound to "
                              f"'{feature.tag}', whose axis {axis} is not along x, y or z",  # type: ignore[attr-defined]
                              subject="features")  # fmt: skip
            axes.append((index, 1 if axis[index] > 0 else -1))
        if len({index for index, _sign in axes}) != 1:
            raise _refuse(f"{owner} interface '{self.name}' binds holes on different axes",
                          subject="features")  # fmt: skip
        index, sign = axes[0]
        if KINDS[self.kind][0] == "axis":
            diameter = Quantity(magnitude=bound[0].diameter_mm, unit="mm")  # type: ignore[attr-defined]
            return Interface.model_validate({"name": self.name, "kind": self.kind,
                                             "axis": "xyz"[index], "feature": self.features[0],
                                             "parameters": {"diameter": diameter}})  # fmt: skip
        face = self.face or _FROM_AXIS[(index, sign)]
        along = "xyz"[index]
        if _ALONG[face] != index:
            raise _refuse(f"{owner} interface '{self.name}' names the {face} face, which its "
                          f"holes along {along} do not open on", subject="face")  # fmt: skip
        return Interface.model_validate({"name": self.name, "kind": self.kind, "face": face,
                                         "holes": self.features})  # fmt: skip
