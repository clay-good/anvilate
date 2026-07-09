"""The materials database: curated, provenance-tagged mechanical properties.

"Retrieval, not recall." Material property values used anywhere in the pipeline
come from this bundled database, never from a model's memory. Every property
carries a citation (source, condition/temper, license, retrieval date) and every
dimensional property is a dimension-checked :class:`Quantity`. A property the
record lacks is *absent*, never substituted — a check that needs it reports
"unavailable" rather than inventing a number.
"""

from __future__ import annotations

import difflib
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from ..units import Quantity
from .records import PropertyCitation, QuantityProperty, ScalarProperty, dimensioned

__all__ = [
    "PropertyCitation",
    "QuantityProperty",
    "ScalarProperty",
    "Material",
    "MaterialsDatabase",
    "UnknownMaterialError",
    "MaterialPropertyUnavailable",
    "default_materials_db",
]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Modulus = Annotated[QuantityProperty, dimensioned("[pressure]", "elastic_modulus")]
Strength = Annotated[QuantityProperty, dimensioned("[pressure]", "strength")]
Density = Annotated[QuantityProperty, dimensioned("[mass] / [length] ** 3", "density")]


class MaterialPropertyUnavailable(KeyError):
    """A required material property is not present in the record.

    Raised instead of substituting an unsourced value, so a check can report
    "not evaluated — property unavailable" and stop.
    """

    def __init__(self, material_id: str, prop: str) -> None:
        self.material_id = material_id
        self.prop = prop
        super().__init__(f"material {material_id!r} has no {prop!r} property")


class Material(_Base):
    """One material record: identity plus provenance-tagged properties.

    The core mechanical properties (modulus, Poisson ratio, density, yield and
    ultimate strength) are required for a bundled record; fatigue and thermal
    properties are optional and absent unless a sourced value exists.
    """

    id: str
    name: str
    category: str  # e.g. "aluminum", "carbon_steel", "stainless_steel"
    bundled: bool = True  # False marks a user- or team-local extension record

    elastic_modulus: Modulus
    poisson_ratio: ScalarProperty
    density: Density
    yield_strength: Strength
    ultimate_strength: Strength
    endurance_limit: Strength | None = None

    _OPTIONAL = ("endurance_limit",)

    def require(self, prop: str) -> QuantityProperty | ScalarProperty:
        """Return a property or raise :class:`MaterialPropertyUnavailable`.

        Use for optional properties a check depends on: a missing value stops
        the check with a named error rather than yielding a silent substitute.
        """
        if prop not in type(self).model_fields:
            raise MaterialPropertyUnavailable(self.id, prop)
        value = getattr(self, prop)
        if value is None:
            raise MaterialPropertyUnavailable(self.id, prop)
        return value

    def shear_modulus(self) -> Quantity:
        """The isotropic shear modulus G = E/(2(1+ν)), derived from the elastic
        modulus and Poisson ratio.

        An exact relation for an isotropic material (not an estimate), so a
        torsion check (:func:`anvilate.analysis.shaft_twist_angle`) can take G
        directly from a database material even though only E and ν are stored.
        """
        nu = self.poisson_ratio.value
        g = self.elastic_modulus.quantity.pint / (2 * (1 + nu))
        return Quantity(magnitude=float(g.to("GPa").magnitude), unit="GPa")

    def citations(self) -> dict[str, PropertyCitation]:
        """Every property's citation, keyed by property name — the evidence trail."""
        out: dict[str, PropertyCitation] = {}
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, QuantityProperty | ScalarProperty):
                out[field] = value.citation
        return out


class UnknownMaterialError(KeyError):
    """A referenced material ID is not in the database."""

    def __init__(self, material_id: str, suggestions: list[str]) -> None:
        self.material_id = material_id
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"unknown material {material_id!r}{hint}")


class MaterialsDatabase:
    """A queryable set of material records, satisfying the material half of the
    spec layer's reference-resolver protocol (:meth:`has_material`,
    :meth:`known_materials`)."""

    def __init__(self, materials: dict[str, Material]) -> None:
        self._materials = materials

    def has_material(self, material_id: str) -> bool:
        return material_id in self._materials

    def known_materials(self) -> list[str]:
        return sorted(self._materials)

    def get(self, material_id: str) -> Material:
        """Return a record or raise :class:`UnknownMaterialError` with near-misses."""
        try:
            return self._materials[material_id]
        except KeyError:
            raise UnknownMaterialError(
                material_id,
                difflib.get_close_matches(material_id, self._materials, n=3),
            ) from None

    def extension_ids(self) -> list[str]:
        """IDs of extension (user/team-local) records — distinguishable in reports."""
        return sorted(mid for mid, m in self._materials.items() if not m.bundled)

    def extended(self, extension_text: str) -> MaterialsDatabase:
        """Return a new database with ``extension_text``'s records overlaid.

        Extension records are marked non-bundled and override any bundled record
        of the same ID, so a team can add or supersede materials without forking
        the bundled data. The bundled database is left unchanged.
        """
        overlay = _load_records(extension_text, bundled=False)
        return MaterialsDatabase({**self._materials, **overlay})

    def __len__(self) -> int:
        return len(self._materials)


def _load_records(text: str, *, bundled: bool) -> dict[str, Material]:
    """Parse a materials YAML document into :class:`Material` records.

    Dataset-level ``license`` and ``retrieved`` fill any citation that omits
    them, so a data file states shared provenance once. ``bundled`` tags the
    records' origin (a bundled dataset vs a user/team extension).
    """
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})
    fallback = {
        "license": dataset.get("license"),
        "retrieved": dataset.get("retrieved"),
    }

    def _fill_citations(node: object) -> None:
        if isinstance(node, dict):
            if "citation" in node and isinstance(node["citation"], dict):
                for key, value in fallback.items():
                    node["citation"].setdefault(key, value)
            for child in node.values():
                _fill_citations(child)

    materials: dict[str, Material] = {}
    for material_id, record in doc["materials"].items():
        _fill_citations(record)
        materials[material_id] = Material.model_validate(
            {"id": material_id, **record, "bundled": bundled}
        )
    return materials


def default_materials_db() -> MaterialsDatabase:
    """The bundled seed materials database."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "materials.yaml").read_text(encoding="utf-8")
    return MaterialsDatabase(_load_records(text, bundled=True))
