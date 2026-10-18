"""Purchased components: the parts you buy, as typed records checked against the product.

A motor, a bearing, a linear guide or a gas spring is not drawn here, and it should not be
written from memory either. It is a record: who makes it and under which number, where to
buy it, the space it takes, the holes it offers a mate, and its ratings, every value with
the datasheet it came from. A product places it as an item (:class:`ComponentRecord` in a
definition's ``component``), and its card compares each rating with what the product asks
of it:

- **Families and their ratings.** :data:`FAMILY_RATINGS` maps each family to the ratings a
  record of it must state and the demands each is checked against. A ball or roller
  bearing's ``dynamic_load_rating`` gives its basic rating life in hours at the declared
  ``equivalent_load`` and ``speed`` (Shigley's L10 = (C/P)^p, the ISO 281 law, through
  :func:`~anvilate.analysis.bearing.bearing_life_hours`), checked against
  ``required_life``. A motor's or coupling's ``rated_torque`` is checked against the
  ``torque`` it must deliver, a linear guide's ``stroke`` and ``dynamic_load_rating``
  against the stroke and load the product asks for, and a gas spring's ``force`` against
  the force it must hold.
- **What the product does not say is not a pass.** A demand the definition does not state
  leaves its check not evaluated, naming the demand to declare.
- **Sourcing.** A record with no supplier part number is unsourced, and its card says so in
  a not-evaluated entry, so a product holding it never exports as validated.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, Provenance, StatableModel, each_one
from .derivation import Derivation, DerivationAbsence, SymbolValue, Underived
from .interfaces import Interface, check_interfaces
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Need, ScorecardEntry, ValueSource
from .units import Quantity

__all__ = [
    "FAMILY_RATINGS",
    "ComponentError",
    "SupplierNumber",
    "Rating",
    "Demand",
    "VendorModel",
    "Price",
    "ComponentRecord",
    "draft_component",
]

_RECORD_SOURCE = "the component record: its datasheet, page by page"

Family = Literal["ball_bearing", "roller_bearing", "motor", "coupling", "linear_guide",
                 "gas_spring", "caster", "other"]  # fmt: skip

#: Each family's ratings (name → dimension) and the demands its checks read
#: (name → dimension). A record must state its family's ratings; a product states the
#: demands, and a check whose demand is missing is not evaluated.
FAMILY_RATINGS: dict[str, tuple[dict[str, str], dict[str, str]]] = {
    "ball_bearing": (
        {"dynamic_load_rating": "[force]"},
        {"equivalent_load": "[force]", "speed": "[frequency]", "required_life": "[time]"},
    ),
    "roller_bearing": (
        {"dynamic_load_rating": "[force]"},
        {"equivalent_load": "[force]", "speed": "[frequency]", "required_life": "[time]"},
    ),
    "motor": ({"rated_torque": "[force] * [length]"}, {"torque": "[force] * [length]"}),
    "coupling": ({"rated_torque": "[force] * [length]"}, {"torque": "[force] * [length]"}),
    "linear_guide": (
        {"stroke": "[length]", "dynamic_load_rating": "[force]"},
        {"stroke": "[length]", "load": "[force]"},
    ),
    "gas_spring": ({"force": "[force]"}, {"force": "[force]"}),
    "caster": ({"load_rating": "[force]"}, {"load": "[force]"}),
    "other": ({}, {}),
}


class ComponentError(RefusalError, ValueError):
    """A component record or demand that cannot be used as stated."""


def _refuse(message: str, *, subject: str) -> ComponentError:
    return ComponentError(
        message, remedies=(Remedy(action="correct", subject=subject, source=_RECORD_SOURCE),)
    )


class SupplierNumber(StatableModel):
    """Where to buy it: a supplier and that supplier's part number."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    supplier: Named
    number: Named


class Rating(StatableModel):
    """One rating the component is sold with, and the datasheet line it was read from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    value: Quantity
    source: Provenance


class Demand(StatableModel):
    """What the product asks of a component, and where that requirement came from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    value: Quantity
    source: Provenance


class VendorModel(StatableModel):
    """The vendor's STEP file for the component: a path in the user's folder, and its hash.

    The file is used where it is, never copied. ``sha256`` is the file's digest when the
    record was written, so a file changed since reads as changed rather than as the model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: Named
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Price(StatableModel):
    """A unit price for screening cost: the amount, its currency, its source and its date.

    It is the user's figure, a quote or a catalog price as of ``date``; a cost roll-up
    sums prices in one currency and converts none.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: float = Field(gt=0, allow_inf_nan=False)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source: Provenance
    date: date


class ComponentRecord(StatableModel):
    """A purchased component: identity, where to buy it, the space it takes, its ratings.

    ``envelope`` is the box it occupies, centred on its own origin, and ``holes`` the
    interfaces it offers a mate, as a placeholder's; ``envelope_source`` and ``mass_source``
    name where they were read. ``ratings`` must include every rating
    :data:`FAMILY_RATINGS` lists for ``family``, each with its source.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    manufacturer: Named
    part_number: Named
    description: Named
    family: Family
    suppliers: tuple[SupplierNumber, ...] = Field(default=(), max_length=16)
    unit_of_measure: Named = "each"
    envelope: tuple[Quantity, Quantity, Quantity]
    envelope_source: Provenance
    mass: Quantity
    mass_source: Provenance
    ratings: tuple[Rating, ...] = Field(default=(), max_length=32)
    holes: tuple[PlaceholderHole, ...] = Field(default=(), max_length=64)
    interfaces: tuple[Interface, ...] = Field(default=(), max_length=32)
    model: VendorModel | None = None
    # A record drafted from a measured vendor STEP (:func:`draft_component`) is used only
    # once a person has checked it: until ``confirmed_by`` names them, its card says so.
    drafted: bool = False
    confirmed_by: Named | None = None
    # The unit price, cited and dated, which the product cost roll-up reads.
    price: Price | None = None

    @model_validator(mode="after")
    def _a_record(self) -> ComponentRecord:
        for index, size in enumerate(self.envelope):
            if not size.has_dimension("[length]") or not size.magnitude > 0:
                raise _refuse(f"component '{self.part_number}' envelope[{index}] is {size}; an "
                              "envelope is three positive lengths", subject="envelope")  # fmt: skip
        if not self.mass.has_dimension("[mass]") or not self.mass.magnitude > 0:
            raise _refuse(f"component '{self.part_number}' mass is {self.mass}; a mass is "
                          "positive", subject="mass")  # fmt: skip
        names = [r.name for r in self.ratings]
        doubled = sorted({n for n in names if names.count(n) > 1})
        if doubled:
            raise _refuse(f"component '{self.part_number}' states {doubled} twice",
                          subject="ratings")  # fmt: skip
        wanted, _demands = FAMILY_RATINGS[self.family]
        stated = {r.name: r for r in self.ratings}
        for name, dimension in wanted.items():
            if name not in stated:
                raise _refuse(f"component '{self.part_number}' is a {self.family} and states "
                              f"no {name}; a {self.family} record states "
                              f"{', '.join(wanted)}", subject="ratings")  # fmt: skip
            value = stated[name].value
            if not value.has_dimension(dimension) or not value.magnitude > 0:
                raise _refuse(f"component '{self.part_number}' rating {name} is {value}; it "
                              f"is a positive {dimension}", subject="ratings")  # fmt: skip
        check_interfaces(self.interfaces, {h.tag for h in self.holes},
                         f"component '{self.part_number}'")  # fmt: skip
        half = [q.to("mm").magnitude / 2 for q in self.envelope]
        for hole in self.holes:
            point = [q.to("mm").magnitude for q in (hole.x, hole.y, hole.z)]
            if any(abs(p) > h + 1e-9 for p, h in zip(point, half, strict=True)):
                raise _refuse(f"component '{self.part_number}' hole '{hole.tag}' at {point} mm "
                              "is outside its envelope", subject="holes")  # fmt: skip
        return self

    @property
    def sourced(self) -> bool:
        """Whether the record names a supplier part number to buy it by."""
        return bool(self.suppliers)

    def rating(self, name: str) -> Rating:
        """The rating called ``name``."""
        return next(r for r in self.ratings if r.name == name)


def _demand_need(name: str, dimension: str) -> Need:
    return Need(
        declaration=f"definitions[].demands[{name}]",
        takes=f"what the product asks of the component: its {name.replace('_', ' ')}",
        dimension=dimension,
        sources=(ValueSource.USER, ValueSource.MEASUREMENT),
    )


_NEEDS_A_SUPPLIER = Need(
    declaration="definitions[].component.suppliers",
    takes="a supplier and that supplier's part number to buy the component by",
    sources=(ValueSource.USER, ValueSource.DATABASE),
)
_NEEDS_A_CONFIRMATION = Need(
    declaration="definitions[].component.confirmed_by",
    takes="the person who checked the drafted record against the vendor's datasheet",
    sources=(ValueSource.USER,),
)
_NEEDS_THE_MODEL = Need(
    declaration="definitions[].component.model",
    takes="the vendor's STEP file in the folder the product is read from, unchanged",
    sources=(ValueSource.USER,),
)
_ENVELOPE_TOLERANCE_MM = 0.5
_BEARING_REFERENCE = "Shigley, rolling-bearing rating life L10 = (C/P)^p"
_RATING_REFERENCE = "the component's datasheet rating against the product's demand"


def _ratio(name: str, rating: Rating, demand: Demand, *, unit: str) -> ScorecardEntry:
    have = rating.value.to(unit).magnitude
    need = demand.value.to(unit).magnitude
    entry = ScorecardEntry.from_safety_factor(
        name,
        computed=have / need if need > 0 else None,
        required=1.0,
        unavailable=f"the {demand.name.replace('_', ' ')} demanded is zero, so there is "
        "nothing to check the rating against; declare the demand",
        needs=(
            _demand_need(
                demand.name,
                "[force]" if unit == "N" else "[length]" if unit == "mm" else "[force] * [length]",
            ),
        ),
    )
    derivation = Derivation(
        symbolic="n = R / D",
        inputs=(
            SymbolValue(symbol="R", description=f"{rating.name} ({rating.source})",
                        value=rating.value, unit=unit),
            SymbolValue(symbol="D", description=f"{demand.name} demanded ({demand.source})",
                        value=demand.value, unit=unit),
        ),
        result=SymbolValue(symbol="n", description="rating over demand",
                           value=have / need if need > 0 else 0.0),
        citation=_RATING_REFERENCE,
    )  # fmt: skip
    detail = (f"{rating.name} {rating.value} ({rating.source}) against {demand.value} "
              f"demanded ({demand.source})")  # fmt: skip
    if entry.status is CheckStatus.NOT_EVALUATED:
        detail = entry.detail
    return entry.model_copy(
        update={"detail": detail, "reference": _RATING_REFERENCE, "derivation": derivation}
    )


def _missing(name: str, wanted: list[str], family: str) -> ScorecardEntry:
    dimensions = FAMILY_RATINGS[family][1]
    return ScorecardEntry(
        name=name,
        status=CheckStatus.NOT_EVALUATED,
        detail=f"the product states no {', '.join(w.replace('_', ' ') for w in wanted)} for "
        "this component, so its rating is not checked; declare it under the definition's "
        "demands",
        reference=_RATING_REFERENCE,
        needs=tuple(_demand_need(w, dimensions[w]) for w in wanted),
    )


def _model_entry(record: ComponentRecord, model: VendorModel, root: Path | None) -> ScorecardEntry:
    """Whether the vendor's file is there, unchanged, and fits the record's envelope."""
    from .context import read_cad_file

    def not_evaluated(why: str) -> ScorecardEntry:
        return ScorecardEntry(name="vendor model", status=CheckStatus.NOT_EVALUATED,
                              detail=f"{model.file}: {why}; its geometry is not evaluated",
                              reference=_RATING_REFERENCE, needs=(_NEEDS_THE_MODEL,))  # fmt: skip

    if root is None:
        return not_evaluated("no folder was given to read it from")
    path = root / model.file
    if not path.is_file():
        return not_evaluated(f"not found in {root}")
    facts = read_cad_file(path)
    if facts.sha256 != model.sha256:
        found, recorded = facts.sha256[:12], model.sha256[:12]
        return not_evaluated(
            f"its SHA-256 is {found}…, not the recorded {recorded}…, so it has changed "
            "since the record"
        )
    stated = [q.to("mm").magnitude for q in record.envelope]
    worst = max(abs(a - b) for a, b in zip(facts.size_mm, stated, strict=True))
    fits = worst <= _ENVELOPE_TOLERANCE_MM
    return ScorecardEntry(
        name="vendor model",
        status=CheckStatus.PASS if fits else CheckStatus.FAIL,
        detail=f"{model.file} matches its recorded hash and measures "
        f"{' × '.join(f'{v:g}' for v in facts.size_mm)} mm against the record's "
        f"{' × '.join(f'{v:g}' for v in stated)} mm "
        f"({'within' if fits else 'off by'} {worst:.3g} mm"
        f"{'' if fits else f', past {_ENVELOPE_TOLERANCE_MM} mm'})",
        reference=_RATING_REFERENCE,
        underived=Underived(kind=DerivationAbsence.LOOKUP,
                            reason="the measured box against the stated one, axis by axis"),
    )  # fmt: skip


def draft_component(
    path: str | Path,
    *,
    manufacturer: str,
    part_number: str,
    description: str,
    family: str,
    mass: Quantity,
    mass_source: str,
    ratings: tuple[Rating, ...] = (),
    suppliers: tuple[SupplierNumber, ...] = (),
) -> ComponentRecord:
    """A draft record measured from the vendor's STEP at ``path``: envelope, holes, model.

    The envelope is the file's measured box, and each through or blind hole whose axis
    runs along x, y or z becomes a hole on the face it opens on, tagged ``h1``, ``h2``…
    in the order the file lists them. Ratings and mass are the datasheet's and are the
    caller's to state. The record is ``drafted``: a product holding it says so until
    ``confirmed_by`` names who checked it.
    """
    from .context import read_cad_file

    ratings = tuple(each_one(ratings, Rating, named="ratings"))
    suppliers = tuple(each_one(suppliers, SupplierNumber, named="suppliers"))
    facts = read_cad_file(path)
    if facts.kind != "step" or len(facts.solids) != 1:
        raise _refuse(f"{facts.file} is not a STEP file of one solid; draft a record from the "
                      "vendor's model of the one component", subject="path")  # fmt: skip
    from build123d import import_step

    solid = facts.solids[0]
    box = import_step(str(path)).bounding_box()
    low = [box.min.X, box.min.Y, box.min.Z]
    high = [box.max.X, box.max.Y, box.max.Z]
    centre = [(lo + hi) / 2 for lo, hi in zip(low, high, strict=True)]
    holes: list[dict[str, object]] = []
    for cylinder in solid.cylinders:
        axis = [abs(a) for a in cylinder.axis]
        along = axis.index(max(axis))
        if cylinder.kind != "hole" or max(axis) < 1 - 1e-6:
            continue
        ends = [cylinder.position_mm[along] + sign * cylinder.depth_mm / 2 for sign in (-1, 1)]
        gaps = [(abs(end - high[along]), end, 1) for end in ends] + [
            (abs(end - low[along]), end, -1) for end in ends
        ]
        _gap, entry, sign = min(gaps)
        point = list(cylinder.position_mm)
        point[along] = entry
        centred = [p - c for p, c in zip(point, centre, strict=True)]
        face = {(0, 1): "right", (0, -1): "left", (1, 1): "back", (1, -1): "front",
                (2, 1): "top", (2, -1): "bottom"}[(along, sign)]  # fmt: skip
        holes.append({"tag": f"h{len(holes) + 1}", "x": _mm(centred[0]), "y": _mm(centred[1]),
                      "z": _mm(centred[2]), "diameter": _mm(cylinder.diameter_mm),
                      "face": face})  # fmt: skip
    where = f"measured from {facts.file} (sha256 {facts.sha256[:12]}…)"
    return ComponentRecord.model_validate({
        "manufacturer": manufacturer, "part_number": part_number, "description": description,
        "family": family, "suppliers": [s.model_dump(mode="json") for s in suppliers],
        "envelope": [_mm(v) for v in solid.size_mm], "envelope_source": where,
        "mass": mass.model_dump(mode="json"), "mass_source": mass_source,
        "ratings": [r.model_dump(mode="json") for r in ratings], "holes": holes,
        "model": {"file": Path(path).name, "sha256": facts.sha256}, "drafted": True,
    })  # fmt: skip


def _mm(value: float) -> dict[str, float | str]:
    return {"magnitude": round(value, 6) + 0.0, "unit": "mm"}


def _rating_entries(
    record: ComponentRecord, demands: tuple[Demand, ...] = (), root: Path | None = None
) -> tuple[ScorecardEntry, ...]:
    """Each of ``record``'s family checks against ``demands``, and its sourcing.

    A check whose demand is not stated is not evaluated, naming it; an unsourced record
    adds a not-evaluated ``sourcing`` entry. Demands the family does not read are refused,
    so a misspelt one cannot leave its check quietly unrun.
    """
    from .analysis.bearing import (
        BALL_BEARING_LIFE_EXPONENT,
        ROLLER_BEARING_LIFE_EXPONENT,
        bearing_life_hours,
    )

    stated = {demand.name: demand for demand in each_one(demands, Demand, named="demands")}
    reads = FAMILY_RATINGS[record.family][1]
    unread = sorted(set(stated) - set(reads))
    if unread:
        raise _refuse(f"component '{record.part_number}' is a {record.family}, which reads "
                      f"{', '.join(reads) or 'no demands'}; {unread} is not one of them",
                      subject="name")  # fmt: skip
    for name, demand in stated.items():
        if not demand.value.has_dimension(reads[name]):
            raise _refuse(f"demand {name} is {demand.value}; it is a {reads[name]}",
                          subject="value")  # fmt: skip
    entries: list[ScorecardEntry] = []
    family = record.family
    if family in ("ball_bearing", "roller_bearing"):
        wanted = ["equivalent_load", "speed", "required_life"]
        absent = [w for w in wanted if w not in stated]
        if absent:
            entries.append(_missing("bearing rating life", absent, family))
        else:
            rating = record.rating("dynamic_load_rating")
            exponent = (BALL_BEARING_LIFE_EXPONENT if family == "ball_bearing"
                        else ROLLER_BEARING_LIFE_EXPONENT)  # fmt: skip
            life = bearing_life_hours(
                dynamic_load_rating=rating.value,
                equivalent_load=stated["equivalent_load"].value,
                speed=stated["speed"].value,
                life_exponent=exponent,
            )
            from .units.rotation import revolutions_per_minute

            rpm = revolutions_per_minute(stated["speed"].value, name="speed")
            required = stated["required_life"].value.to("hour").magnitude
            hours = life.to("hour").magnitude
            entry = ScorecardEntry.from_safety_factor(
                "bearing rating life", computed=hours / required if required > 0 else None,
                required=1.0, unavailable="the required life is zero; declare required_life",
                needs=(_demand_need("required_life", "[time]"),),
            )  # fmt: skip
            derivation = Derivation(
                symbolic="L10h = 10^6 / (60 · n) · (C / P)^p",
                inputs=(
                    SymbolValue(symbol="C", description=f"dynamic load rating ({rating.source})",
                                value=rating.value, unit="N"),
                    SymbolValue(symbol="P", description="equivalent load "
                                f"({stated['equivalent_load'].source})",
                                value=stated["equivalent_load"].value, unit="N"),
                    SymbolValue(symbol="n", description=f"speed in revolutions per minute "
                                f"({stated['speed'].source})", value=rpm),
                    SymbolValue(symbol="p", value=exponent,
                                description=f"life exponent, {family.replace('_', ' ')}"),
                ),
                result=SymbolValue(symbol="L10h", description="basic rating life in hours",
                                   value=hours),
                citation=_BEARING_REFERENCE,
            )  # fmt: skip
            entries.append(entry.model_copy(update={
                "detail": f"L10 life {hours:.4g} h against {required:.4g} h required "
                f"({stated['required_life'].source}); C {rating.value} ({rating.source})",
                "reference": _BEARING_REFERENCE, "derivation": derivation,
            }))  # fmt: skip
    elif family in ("motor", "coupling"):
        if "torque" in stated:
            entries.append(_ratio(f"{family} torque", record.rating("rated_torque"),
                                  stated["torque"], unit="N*m"))  # fmt: skip
        else:
            entries.append(_missing(f"{family} torque", ["torque"], family))
    elif family == "linear_guide":
        if "stroke" in stated:
            entries.append(_ratio("guide stroke", record.rating("stroke"), stated["stroke"],
                                  unit="mm"))  # fmt: skip
        else:
            entries.append(_missing("guide stroke", ["stroke"], family))
        if "load" in stated:
            entries.append(_ratio("guide load", record.rating("dynamic_load_rating"),
                                  stated["load"], unit="N"))  # fmt: skip
        else:
            entries.append(_missing("guide load", ["load"], family))
    elif family == "caster":
        if "load" in stated:
            entries.append(_ratio("caster load", record.rating("load_rating"), stated["load"],
                                  unit="N"))  # fmt: skip
        else:
            entries.append(_missing("caster load", ["load"], family))
    elif family == "gas_spring":
        if "force" in stated:
            entries.append(_ratio("gas spring force", record.rating("force"), stated["force"],
                                  unit="N"))  # fmt: skip
        else:
            entries.append(_missing("gas spring force", ["force"], family))
    if record.model is not None:
        entries.append(_model_entry(record, record.model, root))
    if record.drafted and record.confirmed_by is None:
        entries.append(ScorecardEntry(
            name="drafted record", status=CheckStatus.NOT_EVALUATED, reference=_RATING_REFERENCE,
            detail=f"{record.manufacturer} {record.part_number} was drafted from a measured "
            "vendor model and nobody has confirmed it against the datasheet",
            needs=(_NEEDS_A_CONFIRMATION,),
        ))  # fmt: skip
    if not record.sourced:
        entries.append(ScorecardEntry(
            name="sourcing", status=CheckStatus.NOT_EVALUATED, reference=_RATING_REFERENCE,
            detail=f"{record.manufacturer} {record.part_number} names no supplier part number, "
            "so it cannot be bought from this record and is not released",
            needs=(_NEEDS_A_SUPPLIER,),
        ))  # fmt: skip
    return tuple(entries)


from .product import PlaceholderHole  # noqa: E402  (product imports this module lazily)

ComponentRecord.model_rebuild()
