"""Interop: externally computed member forces and section properties, typed at the door.

Anvilate has the cited check library. What it lacked was a doorway for numbers computed
somewhere else — a frame analysis in Pynite or a commercial solver, a cross-section
constant from ``sectionproperties`` — so that the checking layer can sit on top of the
ecosystem instead of competing with it.

The doorway is the whole design. Importing a member force is not a data-format problem,
it is a *convention* problem, and the conventions are where the failures live:

* **Which axis is the strong one.** One tool calls major-axis bending M3, another Mz, a
  third My. Nothing in the number says which, and swapping major for minor on a wide
  flange overstates its capacity by the ratio of the two section moduli — often 6 to 10
  times. So the mapping from the caller's component labels to Anvilate's quantities is
  **declared, never inferred**, and an undeclared import is refused.
* **The component nobody mapped.** An export carrying P, M2, M3, V2, V3 and T bound to a
  mapping that names three of them silently drops the other three, and the check comes
  back green having never seen the minor-axis moment. Every label must be either mapped
  or explicitly ignored by name; a label that is neither is an error.
* **Units.** Every component is a dimension-checked :class:`~anvilate.units.Quantity`, so
  a kip-inch read as a kip-foot cannot get past the door.

Provenance travels with everything: which tool produced the numbers, which version, and
which load case. A check that cites its clause but not the analysis it screened is only
half-traceable, and the report renderer emits both lines.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from .analysis.section import CrossSection
from .units import Quantity

__all__ = [
    "ForceComponent",
    "AxisMapping",
    "ForceStation",
    "MemberForceRecord",
    "MemberDemand",
    "ExternalSectionProperties",
    "bind_demand",
    "from_sectionproperties",
    "provenance_lines",
]

# What each mapped component must be dimensionally. A moment read as a force, or a
# kip-inch read as a kip-foot, dies here rather than three functions downstream.
# The unit every component is compared in when scanning for its governing station. A
# Quantity keeps the magnitude the caller entered, so the scan must convert before it
# compares or a 1000 N*m station beats a 500 kN*m one.
_CANONICAL_UNITS: dict[str, str] = {
    "axial": "N",
    "major_bending": "N*mm",
    "minor_bending": "N*mm",
    "major_shear": "N",
    "minor_shear": "N",
    "torsion": "N*mm",
}

_COMPONENT_DIMENSIONS: dict[str, str] = {
    "axial": "[force]",
    "major_bending": "[force]*[length]",
    "minor_bending": "[force]*[length]",
    "major_shear": "[force]",
    "minor_shear": "[force]",
    "torsion": "[force]*[length]",
}


class ForceComponent(StrEnum):
    """The member-force quantities Anvilate's screens consume.

    Named for what they *do* — major and minor bending, not 2 and 3 or y and z — because
    the numeral conventions are exactly what differs between tools and the point of this
    layer is to make the caller say which is which.
    """

    AXIAL = "axial"
    MAJOR_BENDING = "major_bending"
    MINOR_BENDING = "minor_bending"
    MAJOR_SHEAR = "major_shear"
    MINOR_SHEAR = "minor_shear"
    TORSION = "torsion"


class AxisMapping(BaseModel):
    """Which of the caller's component labels is which Anvilate quantity.

    ``labels`` maps a :class:`ForceComponent` to the label the exporting tool used —
    ``{ForceComponent.MAJOR_BENDING: "M3", ForceComponent.AXIAL: "P"}``. Nothing is
    guessed: an import declares this or it does not import.

    ``ignored`` names the exported labels this study deliberately does not screen. It
    exists so that dropping a component is an act rather than an omission — a mapping
    that names three of six components and silently discards the rest produces a green
    check that never saw the minor-axis moment.

    ``axial_compression_positive`` has **no default**, because the two conventions are
    both ordinary and the failure is not subtle. Most frame solvers report compression as
    negative; Anvilate's beam-column screen takes compression as positive. Import a
    −180 kN column axial without flipping it and the screen reads a 180 kN *tension*,
    which is a different clause entirely — AISC §H1.2 rather than §H1.1 — and the member
    is never checked for buckling at all. Requiring the declaration is what stops the
    question from going unasked.
    """

    model_config = ConfigDict(frozen=True)

    labels: dict[ForceComponent, str]
    axial_compression_positive: bool
    ignored: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _well_formed(self) -> AxisMapping:
        if not self.labels:
            raise ValueError(
                "an axis mapping with no labels declares nothing; name at least the "
                "component the screen will run on"
            )
        used = list(self.labels.values())
        if len(set(used)) != len(used):
            raise ValueError(
                f"one exported label is mapped to two Anvilate components: {sorted(used)}"
            )
        collision = set(used) & set(self.ignored)
        if collision:
            raise ValueError(f"{sorted(collision)} is both mapped and ignored; it cannot be both")
        return self


class ForceStation(BaseModel):
    """One station along a member: where it is, and what the analysis reported there."""

    model_config = ConfigDict(frozen=True)

    position: Quantity
    components: dict[str, Quantity]

    @model_validator(mode="after")
    def _well_formed(self) -> ForceStation:
        if not self.position.has_dimension("[length]"):
            raise ValueError(f"position must be a [length] quantity; got {self.position}")
        if not self.components:
            raise ValueError("a station with no components carries no information")
        return self


class MemberForceRecord(BaseModel):
    """Member forces from an external analysis, with the tool and load case that made them.

    ``tool`` and ``tool_version`` are required, and so is ``load_case``. A demand without
    them is a number with no history: a reviewer cannot tell whether it came from the
    envelope or from one unfactored case, and those differ by more than any safety factor
    in the library.
    """

    model_config = ConfigDict(frozen=True)

    member: str
    tool: str
    tool_version: str
    load_case: str
    stations: tuple[ForceStation, ...]

    @model_validator(mode="after")
    def _well_formed(self) -> MemberForceRecord:
        for value, name in (
            (self.member, "member"),
            (self.tool, "tool"),
            (self.tool_version, "tool_version"),
            (self.load_case, "load_case"),
        ):
            if not value.strip():
                raise ValueError(f"an imported member-force record needs a {name}")
        if not self.stations:
            raise ValueError(f"{self.member}: a record with no stations has nothing to screen")
        first = set(self.stations[0].components)
        for station in self.stations[1:]:
            if set(station.components) != first:
                raise ValueError(
                    f"{self.member}: stations report different components "
                    f"({sorted(first)} against {sorted(station.components)}); a component "
                    f"that appears at some stations and not others would be read as zero "
                    f"at the rest"
                )
        return self

    @property
    def exported_labels(self) -> tuple[str, ...]:
        """Every component label the export carries, in sorted order."""
        return tuple(sorted(self.stations[0].components))


class MemberDemand(BaseModel):
    """The governing demand bound to Anvilate's quantities, and where it came from.

    ``stations`` gives each component its own governing position. Screening the whole
    member at one station is correct only when the same station governs every component,
    which it usually does not.

    ``ignored`` carries the exported labels the mapping deliberately dropped, so the
    report can say what was *not* screened. Without it a reviewer's artifact is identical
    whether a component was consciously excluded or never exported at all, which defeats
    the rule the mapping exists to enforce.
    """

    model_config = ConfigDict(frozen=True)

    member: str
    load_case: str
    tool: str
    tool_version: str
    components: dict[ForceComponent, Quantity]
    stations: dict[ForceComponent, Quantity]
    ignored: tuple[str, ...] = ()

    def get(self, component: ForceComponent) -> Quantity | None:
        """The governing magnitude of one component, or ``None`` if it was not imported."""
        return self.components.get(component)


class ExternalSectionProperties(BaseModel):
    """Cross-section constants computed elsewhere, with the source that computed them.

    Built for the ``sectionproperties``-class case: an arbitrary section meshed and
    integrated by a tool that does that properly, then screened here. ``method`` records
    *how* — "warping analysis, 6-node triangles" is a different provenance from "handbook
    table", and a torsion constant from the first is trustworthy in a way the second is
    not for an open section.

    :meth:`cross_section` converts to the library's :class:`~anvilate.analysis.CrossSection`.
    ``shear_form_factor`` is deliberately optional and defaults to ``None``: the library's
    shear screen reports NOT_EVALUATED without one rather than assuming a rectangle's 1.5,
    and an imported section is exactly the case where guessing it would be wrong.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    source: str
    source_version: str
    method: str
    area: Quantity
    second_moment: Quantity
    extreme_fibre: Quantity
    second_moment_transverse: Quantity | None = None
    torsion_constant: Quantity | None = None
    shear_form_factor: float | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> ExternalSectionProperties:
        for value, name in (
            (self.name, "name"),
            (self.source, "source"),
            (self.source_version, "source_version"),
            (self.method, "method"),
        ):
            if not value.strip():
                raise ValueError(f"imported section properties need a {name}")
        checks: list[tuple[Quantity | None, str, str]] = [
            (self.area, "area", "[length]**2"),
            (self.second_moment, "second_moment", "[length]**4"),
            (self.extreme_fibre, "extreme_fibre", "[length]"),
            (self.second_moment_transverse, "second_moment_transverse", "[length]**4"),
            (self.torsion_constant, "torsion_constant", "[length]**4"),
        ]
        for value, label, dimension in checks:
            if value is None:
                continue
            if not value.has_dimension(dimension):
                raise ValueError(
                    f"{self.name}: {label} must be a {dimension} quantity; got {value}"
                )
            if value.magnitude <= 0:
                raise ValueError(f"{self.name}: {label} must be positive; got {value}")
        if (
            self.second_moment_transverse is not None
            and self.second_moment_transverse.to("mm**4").magnitude
            > self.second_moment.to("mm**4").magnitude
        ):
            raise ValueError(
                f"{self.name}: second_moment_transverse "
                f"({self.second_moment_transverse}) exceeds second_moment "
                f"({self.second_moment}), so the axes are swapped — the major axis is the "
                f"one with the larger I, and screening bending about the minor axis as "
                f"though it were major overstates the capacity"
            )
        return self

    def cross_section(self) -> CrossSection:
        """The library's :class:`~anvilate.analysis.CrossSection` for these constants."""
        return CrossSection(
            area=self.area,
            second_moment=self.second_moment,
            extreme_fibre=self.extreme_fibre,
            second_moment_transverse=self.second_moment_transverse,
            shear_form_factor=self.shear_form_factor,
        )


def bind_demand(record: MemberForceRecord, mapping: AxisMapping) -> MemberDemand:
    """Bind an imported member-force record to Anvilate's quantities, station by station.

    Every exported label must be either mapped or listed in ``mapping.ignored``. A label
    that is neither raises: the alternative is a check that runs on three of six
    components and reports a margin it did not earn.

    Each component's governing value is the largest magnitude across the stations, taken
    independently — the station that governs bending is rarely the station that governs
    shear, and collapsing the member to one station would screen both at whichever one
    happened to win.

    The axial sign is converted to Anvilate's convention (compression positive) using the
    mapping's ``axial_compression_positive`` declaration. Nothing else is re-signed:
    bending and shear are screened on magnitude, so their sign carries no capacity
    consequence, while the axial sign selects between two different clauses.
    """
    exported = set(record.exported_labels)
    mapped = set(mapping.labels.values())
    missing = sorted(mapped - exported)
    if missing:
        raise ValueError(
            f"{record.member}: the mapping names {missing}, which {record.tool} did not "
            f"export; it carries {sorted(exported)}"
        )
    unaccounted = sorted(exported - mapped - set(mapping.ignored))
    if unaccounted:
        raise ValueError(
            f"{record.member}: {unaccounted} was exported but is neither mapped nor "
            f"ignored. Dropping a component silently is how a member gets screened "
            f"without its minor-axis moment; name it in the mapping or in `ignored`"
        )
    components: dict[ForceComponent, Quantity] = {}
    stations: dict[ForceComponent, Quantity] = {}
    reversals: list[str] = []
    for component, label in mapping.labels.items():
        expected = _COMPONENT_DIMENSIONS[component.value]
        canonical = _CANONICAL_UNITS[component.value]
        governing_station = None
        governing_value = None
        governing_canonical = None
        signs = set()
        for station in record.stations:
            value = station.components[label]
            if not value.has_dimension(expected):
                raise ValueError(
                    f"{record.member}: {label} is mapped to {component.value}, which must "
                    f"be {expected}; got {value.dimensionality} ({value})"
                )
            # Compare in ONE unit. A Quantity keeps the magnitude as entered, and stations
            # are only validated to share component NAMES — so a member reporting 500 kN*m
            # at one station and 1000 N*m at another would hand the 1000 downstream if the
            # scan compared raw magnitudes. That is 500x low, in the unconservative
            # direction, on a demand nothing downstream re-checks.
            in_canonical = value.to(canonical).magnitude
            if component is ForceComponent.AXIAL and in_canonical != 0.0:
                signs.add(in_canonical > 0.0)
            if governing_canonical is None or abs(in_canonical) > abs(governing_canonical):
                governing_canonical = in_canonical
                governing_value = value
                governing_station = station.position
        assert governing_value is not None and governing_station is not None
        if len(signs) > 1:
            reversals.append(label)
        if component is ForceComponent.AXIAL and not mapping.axial_compression_positive:
            governing_value = Quantity(
                magnitude=-governing_value.magnitude, unit=governing_value.unit
            )
        components[component] = governing_value
        stations[component] = governing_station
    # An AXIAL load that changes sign along the member has two governing cases, not one,
    # and the larger magnitude is not the worse one: a column with +200 kN of tension and
    # -180 kN of compression binds to the tension, which routes to AISC §H1.2 and never
    # checks buckling at all. Bending and shear are screened on magnitude and their sign
    # carries no capacity consequence, so only the axial case is refused — and it is
    # refused rather than resolved, because which sense governs is the caller's judgement.
    if reversals:
        raise ValueError(
            f"{record.member}: the axial load ({reversals[0]}) changes sign along the "
            f"member, so it has two governing cases and not one — and the larger "
            f"magnitude is not necessarily the worse, since a member bound as pure "
            f"tension is never screened for buckling. Split the record into the stations "
            f"for each sense and bind them separately"
        )
    return MemberDemand(
        member=record.member,
        load_case=record.load_case,
        tool=record.tool,
        tool_version=record.tool_version,
        components=components,
        stations=stations,
        ignored=tuple(sorted(set(mapping.ignored) & exported)),
    )


def provenance_lines(
    *,
    demand: MemberDemand | None = None,
    section: ExternalSectionProperties | None = None,
    ignored: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """The report lines that say where the externally computed numbers came from.

    A check that cites its clause but not the analysis it screened is only half
    traceable. These lines go beside the citation, and they name the ignored components
    too — a reader has to be able to see what was *not* screened as easily as what was.
    """
    lines: list[str] = []
    if demand is not None:
        lines.append(
            f"member forces: {demand.member}, load case {demand.load_case}, from "
            f"{demand.tool} {demand.tool_version} (external analysis — Anvilate screened "
            f"these numbers, it did not compute them)"
        )
        for component, station in sorted(demand.stations.items(), key=lambda kv: kv[0].value):
            lines.append(
                f"  {component.value}: {demand.components[component]} governing at {station}"
            )
    if section is not None:
        lines.append(
            f"section properties: {section.name}, from {section.source} "
            f"{section.source_version} by {section.method}"
        )
        if section.shear_form_factor is None:
            lines.append(
                "  no shear form factor supplied — a transverse-shear screen reports "
                "NOT_EVALUATED rather than assuming one"
            )
    reasons = dict(ignored or {})
    # Every label the mapping dropped is reported, whether or not the caller supplied a
    # reason — a dropped component that no line mentions is indistinguishable from one
    # that was never exported.
    for label in demand.ignored if demand is not None else ():
        reasons.setdefault(label, "ignored by the axis mapping; no reason recorded")
    for label, reason in sorted(reasons.items()):
        lines.append(f"not screened: {label} — {reason}")
    return tuple(lines)


# --- the sectionproperties adapter -------------------------------------------------------
#
# `sectionproperties` meshes an arbitrary section and integrates it properly, which is
# exactly the case `ExternalSectionProperties` exists for. The adapter is small; the
# interesting part is the three things it refuses to do.
#
# Every getter name and return shape below was read from the package's published API
# reference rather than recalled: `get_area()`, `get_ic()` -> (ixx_c, iyy_c, ixy_c),
# `get_z()` -> (zxx_plus, zxx_minus, zyy_plus, zyy_minus), `get_j()`, `is_composite()`.

# The sentinel `method` string for a section whose warping analysis was never run. It is a
# string a reader sees, not a flag they have to know to look for.
_NO_WARPING = "geometric analysis only (no warping analysis; torsion constant not imported)"


def _positive(value: float, label: str, name: str) -> float:
    if not isfinite(value) or value <= 0:
        raise ValueError(
            f"{name}: sectionproperties returned {label} = {value!r}, which is not a "
            "positive finite number. Screening a section on it would produce a margin "
            "that means nothing"
        )
    return value


def from_sectionproperties(
    section: Any,
    *,
    name: str,
    length_unit: str,
) -> ExternalSectionProperties:
    """A meshed ``sectionproperties`` section as importable constants, with provenance.

    ``length_unit`` is required and not defaulted, because ``sectionproperties`` is
    unit-agnostic: it returns bare floats in whatever units the geometry was drawn in, and
    it has no way to tell you which. A default here would be a guess about somebody else's
    CAD file, and the failure is silent — millimetres read as inches understate a second
    moment by a factor of 4.2 x 10^5 and the screen passes.

    Three refusals, each a wrong number this would otherwise import:

    * **A composite section is refused.** The geometric getters raise on one by design,
      because the meaningful constants for a multi-material section are modulus-weighted;
      reading ``EI`` where ``I`` belongs is a units error no dimension check downstream can
      see, since the library's screens apply their own material.
    * **The extreme fibre comes from the *smaller* section modulus.** ``get_z()`` returns
      the top and bottom fibres separately, and for an asymmetric section they differ. The
      governing fibre is the far one, ``c = I / min(z⁺, z⁻)``; taking the larger modulus
      would put the smaller ``c`` into a bending check and overstate the capacity.
    * **The major axis is the one with the larger second moment**, not the one called x.
      ``sectionproperties`` reports an x and a y; Anvilate screens a major and a minor. For
      a section drawn wider than it is tall those are not the same axis, and mapping ixx to
      major would build a record ``ExternalSectionProperties`` refuses, with a message about
      swapped axes that names the wrong culprit. The extreme fibre follows the same axis.
    * **The shear form factor is left unset**, which is the one worth reading twice.
      ``get_as()`` returns the *Timoshenko shear area*, and ``A / A_s`` is 1.2 for a
      rectangle. :attr:`~anvilate.analysis.CrossSection.shear_form_factor` is the
      *peak-over-average* ratio, which is 1.5 for a rectangle. They are different constants
      that both look like "the shear factor for this shape", and substituting one for the
      other understates the peak shear stress by 25%. Anvilate's shear screen reports
      ``not_evaluated`` without a form factor, which is the honest outcome; supply it
      explicitly if you have it from a source that means the same thing by it.

    The torsion constant is imported only when a warping analysis was run. When it was not,
    it comes back ``None`` and ``method`` says so in words.
    """
    if not length_unit.strip():
        raise ValueError("length_unit is required: sectionproperties returns bare numbers")
    if section.is_composite():
        raise ValueError(
            f"{name}: this section has materials assigned, so sectionproperties reports "
            "modulus-weighted constants (EI, EA). Anvilate's screens apply their own "
            "material to a geometric section, so importing EI as I would be wrong by a "
            "factor of the modulus with nothing downstream able to see it"
        )

    area = _positive(section.get_area(), "area", name)
    ixx_c, iyy_c, _ixy_c = section.get_ic()
    ixx_c = _positive(ixx_c, "ixx_c", name)
    iyy_c = _positive(iyy_c, "iyy_c", name)
    zxx_plus, zxx_minus, zyy_plus, zyy_minus = section.get_z()
    # Anvilate screens a major and a minor axis; sectionproperties reports an x and a y.
    # The major axis is the one with the larger second moment, which for a section drawn
    # wider than it is tall is y — so the mapping is by magnitude, not by name. Fixing
    # ixx to major instead would hand `ExternalSectionProperties` a record its own
    # validator refuses, with a message about swapped axes that names the wrong culprit.
    if ixx_c >= iyy_c:
        major, minor, moduli = ixx_c, iyy_c, (zxx_plus, zxx_minus)
    else:
        major, minor, moduli = iyy_c, ixx_c, (zyy_plus, zyy_minus)
    governing_modulus = _positive(min(moduli), "the elastic section modulus", name)

    method = "sectionproperties finite-element warping analysis"
    torsion_constant: Quantity | None = None
    try:
        j = section.get_j()
    except (RuntimeError, AssertionError, AttributeError):
        # The package raises when the warping analysis has not been run. Anything else is
        # not this condition and is left to propagate.
        method = _NO_WARPING
    else:
        torsion_constant = Quantity(
            magnitude=_positive(j, "the torsion constant", name), unit=f"{length_unit}**4"
        )

    return ExternalSectionProperties(
        name=name,
        source="sectionproperties",
        source_version=_sectionproperties_version(),
        method=method,
        area=Quantity(magnitude=area, unit=f"{length_unit}**2"),
        second_moment=Quantity(magnitude=major, unit=f"{length_unit}**4"),
        extreme_fibre=Quantity(magnitude=major / governing_modulus, unit=length_unit),
        second_moment_transverse=Quantity(magnitude=minor, unit=f"{length_unit}**4"),
        torsion_constant=torsion_constant,
        # Deliberately unset. See the docstring: get_as() means a different constant.
        shear_form_factor=None,
    )


def _sectionproperties_version() -> str:
    """The installed package's version, or an explicit statement that it is unknown.

    A provenance line reading "sectionproperties" with no version is a record that cannot
    be reproduced, so the unknown case says the word rather than leaving the field blank —
    ``ExternalSectionProperties`` refuses a blank one anyway.
    """
    try:
        from importlib.metadata import version

        return version("sectionproperties")
    except Exception:
        return "unknown (sectionproperties not installed as a distribution)"
