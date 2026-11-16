"""Material compliance: what a product's materials are made of, and what they withstand.

Materials are declared in the product's ``screening.materials``, each by the id its items
name (a catalog part's spec material, or a placeholder's or component's ``material``),
with its composition by CAS number and mass fraction, its recycled fraction, and its
attributes, every value with its source.

- :func:`composition_export` gives, for every made part and component, its material, its
  substances, its mass and its recycled fraction, and rolls recycled plastic up the
  product by mass.
- :func:`screen_material_needs` compares each declared need (service temperature,
  sterilization, vacuum outgassing, flammability class, body contact) with the attribute
  its material declares, citing both. A need's limit is the user's, with its source; an
  attribute the material does not declare is not evaluated, naming it.

- :func:`screen_substances` holds every item's composition against the substance lists
  you hold, each loaded with :func:`load_substance_list` from the publisher's own file and
  pinned by its version and SHA-256, and reports each listed substance above its threshold
  with the item, its concentration, the threshold, and the list version and hash. An
  exemption counts only when you declare it with its reference.

Fetching those lists from their publishers, with consent where the terms require it, is
not built: the list is a file you have, and Anvilate ships none.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field, ValidationError, model_validator

from ._models import Named, Provenance, RevalidatedModel, StatableModel, each_one
from .derivation import DerivationAbsence, Underived
from .product import (
    UL94_CLASSES,
    MaterialDeclaration,
    Product,
    _cas_problem,
    _refuse,
    place_product,
)
from .scorecard import CheckStatus, Need, ScorecardEntry, ValueSource

__all__ = [
    "CompositionLine",
    "RecycledRollup",
    "CompositionReport",
    "material_of",
    "composition_export",
    "screen_material_needs",
    "ListedSubstance",
    "SubstanceList",
    "Exemption",
    "load_substance_list",
    "screen_substances",
]

_COMPARED = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="the material's declared attribute against the declared need, as stated",
)


class CompositionLine(StatableModel):
    """One body's material, substances, mass and recycled fraction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    material: str | None
    mass_kg: float | None
    substances: tuple[tuple[str, str, float], ...] = ()
    recycled_fraction: float | None = None
    recycled_source: str | None = None


class RecycledRollup(StatableModel):
    """Recycled plastic content by mass, and the lines it comes from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plastic_kg: float
    recycled_kg: float
    fraction: float | None
    lines: tuple[str, ...] = ()
    undeclared: tuple[str, ...] = ()


class CompositionReport(StatableModel):
    """Every body's composition, and the product's recycled plastic content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lines: tuple[CompositionLine, ...]
    recycled: RecycledRollup


def material_of(
    product: Product, item: str, library: Mapping[str, Product] | None = None
) -> str | None:
    """The material id the instance ``item`` names: its spec's, or its definition's own."""
    definitions = {d.id: d for d in product.definitions}
    instance = next((i for i in product.instances if i.name == item), None)
    if instance is None:
        raise _refuse(f"'{item}' is not an item of '{product.name}'", subject="item")
    definition = definitions[instance.item]
    if definition.spec is not None:
        return str((dict(definition.spec).get("material") or {}).get("ref") or "") or None
    return definition.material


def _declared(product: Product) -> dict[str, MaterialDeclaration]:
    found = product.screening.materials if product.screening is not None else ()
    return {m.material: m for m in found}


def _item(path: str) -> str:
    return path.split("/")[1].split("[")[0]


def composition_export(
    product: Product, *, library: Mapping[str, Product] | None = None, root: Any = None
) -> CompositionReport:
    """Every made part's and component's composition by mass, and recycled plastic content."""
    if not isinstance(product, Product):
        raise _refuse("product must be a Product from parse_product", subject="product")
    placed = place_product(product, library=library, root=root)
    declared = _declared(product)
    lines = []
    plastic = recycled = 0.0
    contributing, undeclared = [], []
    for body in placed.bodies:
        material = material_of(product, _item(body.path))
        record = declared.get(material) if material is not None else None
        substances = (
            tuple((s.cas, s.name, s.fraction) for s in record.composition) if record else ()
        )
        fraction = source = None
        if record is not None and record.recycled_fraction is not None:
            fraction = float(record.recycled_fraction.value)
            source = record.recycled_fraction.source
        lines.append(CompositionLine(path=body.path, material=material, mass_kg=body.mass_kg,
                                     substances=substances, recycled_fraction=fraction,
                                     recycled_source=source))  # fmt: skip
        if record is not None and record.plastic and body.mass_kg is not None:
            plastic += body.mass_kg
            if fraction is None:
                undeclared.append(body.path)
            else:
                recycled += body.mass_kg * fraction
                contributing.append(
                    f"{body.path}: {body.mass_kg:.4g} kg, {fraction:.0%} ({source})"
                )
    rollup = RecycledRollup(
        plastic_kg=plastic, recycled_kg=recycled,
        fraction=recycled / plastic if plastic > 0 and not undeclared else None,
        lines=tuple(contributing), undeclared=tuple(undeclared),
    )  # fmt: skip
    return CompositionReport(lines=tuple(lines), recycled=rollup)


#: Each check: its label, the need it reads, and the material attribute it reads.
_CHECKS = (
    ("service temperature", "service_temperature", "service_max_temperature"),
    ("sterilization", "sterilization", "service_max_temperature"),
    ("vacuum outgassing", "vacuum", "total_mass_loss"),
    ("flammability", "flammability", "flammability"),
    ("body contact", "body_contact", "biocompatibility"),
)


def _need(declaration: str, takes: str) -> Need:
    return Need(
        declaration=declaration, takes=takes, sources=(ValueSource.USER, ValueSource.DATABASE)
    )


def screen_material_needs(product: Product) -> tuple[ScorecardEntry, ...]:
    """Each declared material need against the attribute each affected item's material states."""
    needs = product.screening.needs if product.screening is not None else None
    if needs is None:
        return ()
    declared = _declared(product)
    items = needs.items or tuple(i.name for i in product.instances)
    entries = []
    for item in items:
        material = material_of(product, item)
        record = declared.get(material) if material is not None else None
        for label, field, attribute in _CHECKS:
            need = getattr(needs, field)
            if need is None:
                continue
            name = f"{item} {label}"
            stated = record.attributes.get(attribute) if record is not None else None
            if stated is None:
                entries.append(ScorecardEntry(
                    name=name, status=CheckStatus.NOT_EVALUATED,
                    detail=f"{item}'s material {material or '(none named)'} declares no "
                    f"{attribute.replace('_', ' ')} to hold against the {label} need",
                    needs=(_need(f"screening.materials[{material}].attributes.{attribute}",
                                 f"the material's {attribute.replace('_', ' ')}, cited"),),
                ))  # fmt: skip
                continue
            entries.append(_compare(name, item, material or "", label, need, attribute, stated))
    return tuple(entries)


def _compare(name: str, item: str, material: str, label: str, need: Any, attribute: str,
             stated: Any) -> ScorecardEntry:  # fmt: skip
    have = stated.value
    if attribute == "service_max_temperature":
        wanted = need.temperature if label == "sterilization" else need.value
        ok = have.to("K").magnitude >= wanted.to("K").magnitude
        if label == "sterilization":
            reaches = f"{need.method} sterilization reaches {wanted} ({need.source})"
        else:
            reaches = f"the need is {wanted} ({need.source})"
        why = f"{material} is declared for service to {have} ({stated.source}); {reaches}"
    elif attribute == "total_mass_loss":
        ok = float(have) <= float(need.value)
        why = (f"{material} loses {float(have):.2%} of its mass in vacuum ({stated.source}), "
               f"against the {float(need.value):.2%} screen ({need.source})")  # fmt: skip
    elif attribute == "flammability":
        for rating in (have, need.value):
            if rating not in UL94_CLASSES:
                raise _refuse(f"{rating!r} is not a UL 94 class ({', '.join(UL94_CLASSES)})",
                              subject="product")  # fmt: skip
        ok = UL94_CLASSES.index(have) >= UL94_CLASSES.index(need.value)
        why = (f"{material} is rated {have} ({stated.source}), against the {need.value} needed "
               f"({need.source})")  # fmt: skip
    else:
        held = {c.strip() for c in str(have).split(",")}
        ok = str(need.value) in held
        why = (f"{material} is declared for {', '.join(sorted(held))} ({stated.source}), and "
               f"the need is {need.value} ({need.source})")  # fmt: skip
    return ScorecardEntry(name=name, status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                          detail=f"{item}: {why}", underived=_COMPARED)  # fmt: skip


# --- substance lists ------------------------------------------------------------------------

_LISTED = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="the material's declared composition matched by CAS number against the list held",
)


class ListedSubstance(RevalidatedModel):
    """One substance on a list: its CAS number, its name, and the concentration above
    which it is reported, as a mass fraction (RoHS Annex II's lead is 0.001, its cadmium
    0.0001; a REACH candidate substance in an article is 0.001)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cas: str
    name: Named
    threshold: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _a_real_number(self) -> ListedSubstance:
        problem = _cas_problem(self.cas)
        if problem:
            raise _refuse(f"listed substance {self.name}'s CAS number {self.cas} {problem}",
                          subject="substances")  # fmt: skip
        return self


class SubstanceList(RevalidatedModel):
    """A substance list as you hold it: which list, which version, the SHA-256 of the file
    it was read from, and what its thresholds are a fraction of.

    ``basis`` is what a threshold is measured against. RoHS Annex II limits a substance in
    each **homogeneous material**; REACH Article 33 counts a candidate substance in each
    **article**. ``source`` is where the file came from, as a citation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    version: Named
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    basis: Literal["homogeneous material", "article"]
    substances: tuple[ListedSubstance, ...] = Field(min_length=1, max_length=20000)
    source: Provenance

    @model_validator(mode="after")
    def _each_once(self) -> SubstanceList:
        numbers = [s.cas for s in self.substances]
        twice = sorted({n for n in numbers if numbers.count(n) > 1})
        if twice:
            raise _refuse(f"list {self.name} {self.version} names {twice} more than once; "
                          "one threshold per substance", subject="substances")  # fmt: skip
        return self


class Exemption(RevalidatedModel):
    """A listed substance you declare exempt, on one list, with the reference it rests on.

    ``items`` limits it to those items; empty, it covers every item. The reference is
    yours to hold (an Annex III entry and its expiry, say): the screen names it and does
    not judge it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    list: Named
    cas: str
    items: tuple[Named, ...] = ()
    reference: Provenance

    @model_validator(mode="after")
    def _a_real_number(self) -> Exemption:
        problem = _cas_problem(self.cas)
        if problem:
            raise _refuse(f"the exemption's CAS number {self.cas} {problem}",
                          subject="exemptions")  # fmt: skip
        return self


def load_substance_list(
    path: str | Path,
    *,
    name: str,
    version: str,
    basis: Literal["homogeneous material", "article"],
    source: str,
) -> SubstanceList:
    """A substance list read from a CSV file with ``cas``, ``name`` and ``threshold`` columns.

    The threshold is a mass fraction (0.001 for 0.1%). The file's SHA-256 is computed from
    its bytes and carried on the list, so every hit names exactly what it was held against.
    """
    if not isinstance(path, (str, Path)):
        raise _refuse("path must be the path of a CSV file", subject="path")
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as failure:
        raise _refuse(f"{path} is not UTF-8 text", subject="path") from failure
    reader = csv.DictReader(io.StringIO(text))
    missing = sorted({"cas", "name", "threshold"} - set(reader.fieldnames or ()))
    if missing:
        raise _refuse(f"{path} has no {', '.join(missing)} column; its header is "
                      f"{reader.fieldnames}", subject="path")  # fmt: skip
    entries = []
    for row, line in enumerate(reader, start=2):
        try:
            threshold = float((line["threshold"] or "").strip())
        except ValueError as failure:
            raise _refuse(f"{path} line {row}: threshold {line['threshold']!r} is not a "
                          "number", subject="path") from failure  # fmt: skip
        try:
            entries.append(ListedSubstance(cas=(line["cas"] or "").strip(),
                                           name=(line["name"] or "").strip(),
                                           threshold=threshold))  # fmt: skip
        except ValidationError as failure:
            raise _refuse(f"{path} line {row}: {_first(failure)}", subject="path") from failure
    try:
        return SubstanceList(name=name, version=version, sha256=hashlib.sha256(raw).hexdigest(),
                             basis=basis, substances=tuple(entries), source=source)  # fmt: skip
    except ValidationError as failure:
        field = str(failure.errors()[0]["loc"][0]) if failure.errors()[0]["loc"] else ""
        subject = field if field in ("name", "version", "basis", "source") else "path"
        raise _refuse(f"{path}: {_first(failure)}", subject=subject) from failure


def _first(failure: ValidationError) -> str:
    first = failure.errors()[0]
    where = ".".join(str(p) for p in first["loc"])
    message = str(first["msg"]).removeprefix("Value error, ")
    return f"{where} {message}" if where else message


def screen_substances(
    product: Product,
    lists: Sequence[SubstanceList],
    *,
    exemptions: Sequence[Exemption] = (),
) -> tuple[ScorecardEntry, ...]:
    """Every item's declared composition against each substance list, one entry per item
    and list.

    A substance above its threshold fails the item, naming the substance, its
    concentration, the threshold and its basis, and the list's version and hash, unless an
    exemption declared for that list and substance covers the item, which is then named. An
    item whose material declares no composition is not evaluated: nothing is passed
    unread. An item is one material, so its concentration in the article and in its
    homogeneous material are both the material's declared fraction.
    """
    if not isinstance(product, Product):
        raise _refuse("product must be a Product from parse_product", subject="product")
    lists = each_one(lists, SubstanceList, named="lists")
    exemptions = each_one(exemptions, Exemption, named="exemptions")
    names = [x.name for x in lists]
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:
        raise _refuse(f"lists {twice} are given more than once; hold one version of each",
                      subject="lists")  # fmt: skip
    items = {i.name for i in product.instances}
    for exemption in exemptions:
        if exemption.list not in names:
            raise _refuse(f"an exemption is on list {exemption.list!r}, which is not among "
                          f"the lists screened ({', '.join(names)})",
                          subject="exemptions")  # fmt: skip
        stray = sorted(set(exemption.items) - items)
        if stray:
            raise _refuse(f"an exemption names {stray}, which are not items of "
                          f"'{product.name}'", subject="exemptions")  # fmt: skip
    declared = _declared(product)
    definitions = {d.id: d for d in product.definitions}
    entries = []
    for instance in product.instances:
        definition = definitions[instance.item]
        if definition.product is not None or definition.reference is not None:
            # A sub-product is screened item by item in its own declaration, and a
            # reference assembly is not made here.
            continue
        item = instance.name
        material = material_of(product, item)
        record = declared.get(material) if material is not None else None
        for held in lists:
            name = f"{item} {held.name}"
            pinned = f"{held.name} {held.version} (sha256 {held.sha256[:12]})"
            if record is None or not record.composition:
                entries.append(ScorecardEntry(
                    name=name, status=CheckStatus.NOT_EVALUATED,
                    detail=f"{item}'s material {material or '(none named)'} declares no "
                    f"composition to hold against {pinned}",
                    needs=(_need(f"screening.materials[{material}].composition",
                                 "the material's substances by CAS number and mass "
                                 "fraction, cited"),),
                ))  # fmt: skip
                continue
            entries.append(_listed(name, item, record, held, pinned, exemptions))
    return tuple(entries)


def _listed(name: str, item: str, record: MaterialDeclaration, held: SubstanceList,
            pinned: str, exemptions: Sequence[Exemption]) -> ScorecardEntry:  # fmt: skip
    limits = {s.cas: s for s in held.substances}
    over, exempt, under = [], [], []
    for substance in record.composition:
        listed = limits.get(substance.cas)
        if listed is None:
            continue
        said = (f"{listed.name} (CAS {substance.cas}) at {substance.fraction:.4%} of the "
                f"{held.basis}, threshold {listed.threshold:.4%}")  # fmt: skip
        if substance.fraction <= listed.threshold:
            under.append(said)
            continue
        cover = next((e for e in exemptions if e.list == held.name and e.cas == substance.cas
                      and (not e.items or item in e.items)), None)  # fmt: skip
        if cover is not None:
            exempt.append(f"{said}, exempt under {cover.reference}")
        else:
            over.append(said)
    against = (f"{item}'s material {record.material} ({record.composition_source}) against "
               f"{pinned}, from {held.source}")  # fmt: skip
    parts = []
    if over:
        parts.append("above its threshold: " + "; ".join(over))
    if exempt:
        parts.append("declared exempt: " + "; ".join(exempt))
    if under:
        parts.append("listed, at or below its threshold: " + "; ".join(under))
    if not parts:
        parts.append(f"none of its {len(record.composition)} declared substances is among "
                     f"the {len(held.substances)} listed")  # fmt: skip
    return ScorecardEntry(name=name, status=CheckStatus.FAIL if over else CheckStatus.PASS,
                          detail=f"{against}: " + "; ".join(parts),
                          underived=_LISTED)  # fmt: skip
