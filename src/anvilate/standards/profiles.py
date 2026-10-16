"""Hot-rolled I and H profiles by name: ``IPE 200`` to a cited cross-section.

A structural check wants a :class:`~anvilate.analysis.section.CrossSection` — area, second
moments, extreme fibre — and an engineer writes ``IPE 200``. This table bridges the two with
no network call: the five EN 10365 dimensions of each IPE and HEA profile ship with the
package (``data/en_profiles.yaml``), and :meth:`RolledProfile.section` computes the properties
from them, root fillets included, with
:meth:`~anvilate.analysis.section.CrossSection.rolled_i_section`.

The dimensions are recorded as facts read from public tabulations of the standard, and every
one carries that citation. The standard itself is not redistributed. AISC W-shape geometry
is likewise computed, but only after the user explicitly fetches the publisher's verified,
non-redistributable workbook into the local cache. A name no table holds is refused with the
entries it nearly named, never approximated.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Annotated
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pydantic import ConfigDict

from .._models import Named, RevalidatedModel, _reason, parse_yaml
from ..analysis.section import CrossSection
from ..fetch import DatasetRecipe, FetchProvenance, cached_dataset, fetch_dataset
from ..refusal import RefusalError, Remedy
from ..units import Quantity
from .records import PropertyCitation, QuantityProperty, dimensioned

_DESIGNATION_SOURCE = "the structural drawing's member schedule designation"
_AISC_SOURCE = "the pinned AISC Shapes Database v16.0 workbook, fetched with consent"


class _ProfileInputError(RefusalError, ValueError):
    """A rolled-profile input that cannot be used without correction."""


def _profile_refusal(message: str, *, subject: str, source: str) -> _ProfileInputError:
    return _ProfileInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


__all__ = [
    "RolledProfile",
    "ProfileTable",
    "AiscProfileDataRequired",
    "AiscProfileTable",
    "AISC_SHAPES_V16",
    "UnknownProfileError",
    "canonical_aisc_designation",
    "canonical_designation",
    "cached_aisc_profile_table",
    "default_profile_table",
    "fetch_aisc_profile_table",
    "resolve_profile",
]


Length = Annotated[QuantityProperty, dimensioned("[length]", "profile dimension")]

# A designation as people write it: the series, a separator or none, the nominal depth —
# and EN 10365's own spelling of the H series, ``HE 200 A``. Bounded on every count, because
# a spec field is a free string.
_SEP = r"[\s_-]{0,8}"
_DESIGNATION = re.compile(
    rf"\s{{0,8}}(?:(IPE|HEA){_SEP}(\d{{2,4}})|HE{_SEP}(\d{{2,4}}){_SEP}A)\s{{0,8}}",
    re.IGNORECASE,
)
_AISC_DESIGNATION = re.compile(
    r"\s{0,8}W\s{0,8}(\d{1,2}(?:\.\d+)?)\s{0,8}[xX×]\s{0,8}"
    r"(\d{1,3}(?:\.\d+)?)\s{0,8}",
    re.IGNORECASE,
)

AISC_SHAPES_V16 = DatasetRecipe(
    name="aisc-shapes-database-v16.0.xlsx",
    url="https://cloud.aisc.org/biggie_bin/aisc-shapes-database-v160-2.xlsx",
    sha256="82d0ceb96a0d938ae1a6bd9637cb10a1e269225b5d668dce5b0bdc8d86013496",
    license="LicenseRef-AISC-Terms",
    source="AISC Shapes Database v16.0, August 2023",
    redistributable=False,
)


def canonical_designation(text: str) -> str | None:
    """``IPE 200`` for any spacing, case or separator of it, ``HEA 200`` for ``HE 200 A``, or
    ``None`` for something else."""
    match = _DESIGNATION.fullmatch(text)
    if match is None:
        return None
    if match.group(3) is not None:
        return f"HEA {int(match.group(3))}"
    return f"{match.group(1).upper()} {int(match.group(2))}"


def canonical_aisc_designation(text: str) -> str | None:
    """Return AISC's compact spelling (for example ``W12X26``), or ``None``."""
    match = _AISC_DESIGNATION.fullmatch(text)
    if match is None:
        return None

    def _number(token: str) -> str:
        value = float(token)
        return str(int(value)) if value.is_integer() else f"{value:g}"

    return f"W{_number(match.group(1))}X{_number(match.group(2))}"


class RolledProfile(RevalidatedModel):
    """One rolled I or H profile: its source dimensions, each cited."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: Named
    depth: Length
    flange_width: Length
    web_thickness: Length
    flange_thickness: Length
    root_radius: Length

    def section(self) -> CrossSection:
        """The cross-section the structural screens take, bending about the strong axis."""
        return CrossSection.rolled_i_section(
            depth=self.depth.quantity,
            flange_width=self.flange_width.quantity,
            flange_thickness=self.flange_thickness.quantity,
            web_thickness=self.web_thickness.quantity,
            root_radius=self.root_radius.quantity,
        )

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence trail."""
        return {
            field: value.citation
            for field in type(self).model_fields
            if isinstance(value := getattr(self, field), QuantityProperty)
        }

    def __str__(self) -> str:
        dims = ", ".join(
            f"{symbol} {getattr(self, field).quantity.magnitude:g}"
            for symbol, field in (
                ("h", "depth"),
                ("b", "flange_width"),
                ("t_w", "web_thickness"),
                ("t_f", "flange_thickness"),
                ("r", "root_radius"),
            )
        )
        return f"{self.designation} ({dims} mm)"


_HSS_DESIGNATION = re.compile(r"HSS[\d./-]{1,12}(?:X[\d./-]{1,12}){1,2}")

#: AISC's rolled HSS corner, solved out of the Shapes Database's own columns rather than
#: recalled: an outside corner radius of twice the design wall reproduces every tabulated
#: area within 0.4% and second moment within 1%, over all 525 rectangular rows.
_HSS_CORNER_RADIUS_WALLS = 2.0


def canonical_hss_designation(text: str) -> str | None:
    """AISC's spelling of a rolled HSS (``HSS6X4X1/4``, ``HSS6.000X0.250``), or ``None``.

    A rectangular one is its depth, breadth and nominal wall, the wall as AISC writes it,
    a fraction. A round one is its outside diameter and wall to three decimals, so
    ``HSS6x0.25`` is ``HSS6.000X0.250``.
    """
    compact = re.sub(r"\s", "", text[:48]).upper().replace("×", "X")
    if _HSS_DESIGNATION.fullmatch(compact) is None:
        return None
    parts = compact[3:].split("X")
    if len(parts) == 2:
        try:
            return "HSS" + "X".join(f"{float(part):.3f}" for part in parts)
        except ValueError:
            return None
    return compact


class HollowProfile(RevalidatedModel):
    """One rolled HSS: its outside dimensions and design wall, each cited.

    ``depth`` is a round HSS's outside diameter, or a rectangular one's dimension along the
    load, which AISC names first; ``breadth`` is the other and is absent for a round one.
    ``wall_thickness`` is the design wall, which is what the section is computed on.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: Named
    depth: Length
    wall_thickness: Length
    breadth: Length | None = None

    def section(self) -> CrossSection:
        """The cross-section the structural screens take, bending about the strong axis."""
        wall = self.wall_thickness.quantity
        if self.breadth is None:
            outer = self.depth.quantity.to("mm").magnitude
            return CrossSection.hollow_circular(
                outer_diameter=self.depth.quantity,
                inner_diameter=Quantity(magnitude=outer - 2 * wall.to("mm").magnitude, unit="mm"),
            )
        return CrossSection.hollow_rectangular(
            width=self.breadth.quantity,
            height=self.depth.quantity,
            wall_thickness=wall,
            corner_radius=Quantity(
                magnitude=_HSS_CORNER_RADIUS_WALLS * wall.to("mm").magnitude, unit="mm"
            ),
        )

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence trail."""
        return {
            field: value.citation
            for field in type(self).model_fields
            if isinstance(value := getattr(self, field), QuantityProperty)
        }

    def __str__(self) -> str:
        wall = f"t {self.wall_thickness.quantity.magnitude:g}"
        if self.breadth is None:
            return f"{self.designation} (D {self.depth.quantity.magnitude:g}, {wall} mm)"
        return (
            f"{self.designation} (h {self.depth.quantity.magnitude:g}, "
            f"b {self.breadth.quantity.magnitude:g}, {wall} mm)"
        )


class UnknownProfileError(KeyError):
    """A requested profile designation has no record in the table."""

    def __init__(
        self, designation: str, suggestions: list[str], *, detail: str | None = None
    ) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else "."
        super().__init__(
            detail
            or (
                f"no record for profile {designation!r}{hint} This table holds the EN 10365 "
                "IPE and HEA series; any other section is declared by its properties"
            )
        )


def _neighbours(key: str, held: list[str], pattern: str) -> list[str]:
    """The held sizes either side of ``key`` in its own series, or ``[]``.

    ``pattern`` splits a designation into its series and the number that orders it (the
    depth of an IPE, the weight of a W12). For a well-formed name the table does not hold,
    these are what an engineer meant: `IPE 210` nearly names IPE 200 and IPE 220, while
    string similarity offered IPE 270 and IPE 240 ahead of either.
    """
    wanted = re.fullmatch(pattern, key)
    if wanted is None:
        return []
    series, size = wanted.group(1), float(wanted.group(2))
    sizes = sorted(
        (float(match.group(2)), name)
        for name in held
        if (match := re.fullmatch(pattern, name)) is not None and match.group(1) == series
    )
    below = [name for number, name in sizes if number < size][-1:]
    above = [name for number, name in sizes if number > size][:1]
    return below + above


def _profile_key(designation: str) -> tuple[str, int]:
    series, _, size = designation.partition(" ")
    return (series, int(size) if size.isdigit() else 0)


class ProfileTable:
    """IPE and HEA profiles keyed by designation (``IPE 200``, ``HEA 300``)."""

    def __init__(self, profiles: dict[str, RolledProfile]) -> None:
        self._profiles = profiles

    def has_profile(self, designation: str) -> bool:
        return canonical_designation(designation) in self._profiles

    def designations(self) -> list[str]:
        return sorted(self._profiles, key=_profile_key)

    def get(self, designation: str) -> RolledProfile:
        """The profile ``designation`` names, in any spacing or case.

        Raises :class:`UnknownProfileError`, with the entries it nearly named, for a name the
        table does not hold.
        """
        key = canonical_designation(designation)
        if key is not None and key in self._profiles:
            return self._profiles[key]
        probe = key or designation.strip()[:32].upper()
        nearest = _neighbours(probe, list(self._profiles), r"(IPE|HEA) (\d+)")
        raise UnknownProfileError(
            designation,
            nearest or difflib.get_close_matches(probe, self._profiles, n=3, cutoff=0.6),
        )

    def __len__(self) -> int:
        return len(self._profiles)


class AiscProfileDataRequired(LookupError):
    """An AISC shape was named before the non-redistributable AISC workbook was cached."""


class AiscProfileTable:
    """AISC W-shape and HSS geometry parsed from the user's verified local workbook."""

    def __init__(
        self,
        profiles: dict[str, RolledProfile],
        provenance: FetchProvenance,
        hollow: dict[str, HollowProfile] | None = None,
    ) -> None:
        self._profiles = profiles
        self._hollow = hollow or {}
        self.provenance = provenance

    def designations(self) -> list[str]:
        return sorted(self._profiles)

    def hollow_designations(self) -> list[str]:
        return sorted(self._hollow)

    def get(self, designation: str) -> RolledProfile | HollowProfile:
        hss = canonical_hss_designation(designation)
        if hss is not None:
            if hss in self._hollow:
                return self._hollow[hss]
            suggestions = difflib.get_close_matches(hss, self._hollow, n=3, cutoff=0.8)
            hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
            raise UnknownProfileError(
                designation,
                suggestions,
                detail=(
                    f"no AISC HSS record for profile {designation!r}{hint}; a rectangular "
                    "one is written depth, breadth, wall (HSS6X4X1/4) and a round one "
                    "diameter, wall (HSS6.000X0.250). Declare its section properties "
                    "rather than substituting another shape"
                ),
            )
        key = canonical_aisc_designation(designation)
        if key is not None and key in self._profiles:
            return self._profiles[key]
        probe = key or designation.strip()[:32].upper()
        suggestions = _neighbours(
            probe, list(self._profiles), r"(W[\d.]+)X([\d.]+)"
        ) or difflib.get_close_matches(probe, self._profiles, n=3, cutoff=0.6)
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        raise UnknownProfileError(
            designation,
            suggestions,
            detail=(
                f"no AISC W-shape record for profile {designation!r}{hint}; declare its "
                "section properties rather than substituting another shape"
            ),
        )

    def __len__(self) -> int:
        return len(self._profiles)


def _load_profiles(text: str) -> dict[str, RolledProfile]:
    doc = parse_yaml(text)
    dataset = doc["dataset"]

    def _prop(value_mm: float, designation: str, what: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"{designation} {what}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    fields = ("depth", "flange_width", "web_thickness", "flange_thickness", "root_radius")
    profiles: dict[str, RolledProfile] = {}
    for designation, row in doc["profiles"].items():
        if canonical_designation(designation) != designation:
            raise ValueError(f"profile key {designation!r} is not in canonical form")
        if len(row) != len(fields):
            raise ValueError(f"profile {designation} lists {len(row)} dimensions, not 5")
        profiles[designation] = RolledProfile.model_validate(
            {
                "designation": designation,
                **{
                    field: _prop(value, designation, field.replace("_", " "))
                    for field, value in zip(fields, row, strict=True)
                },
            }
        )
    return profiles


@cache
def default_profile_table() -> ProfileTable:
    """The bundled EN 10365 IPE and HEA profile table."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "en_profiles.yaml").read_text(encoding="utf-8")
    return ProfileTable(_load_profiles(text))


_XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_CELL_COLUMN = re.compile(r"[A-Z]+")
_AISC_COLUMNS = {
    "A": "Type",
    "C": "AISC_Manual_Label",
    "G": "d",
    "I": "Ht",
    "K": "OD",
    "L": "bf",
    "N": "B",
    "Q": "tw",
    "T": "tf",
    "X": "tdes",
    "Y": "kdes",
}


def _xlsx_value(cell: ElementTree.Element, shared: list[str]) -> str | None:
    value = cell.find(f"{_XLSX_NS}v")
    if value is None or value.text is None:
        return None
    if cell.get("t") == "s":
        return shared[int(value.text)]
    return value.text


def _aisc_rows(path: Path, kinds: tuple[str, ...] = ("W", "HSS")) -> list[dict[str, str]]:
    """Read the pinned workbook's geometry for ``kinds`` without a spreadsheet dependency.

    ``kinds`` are the workbook's own shape-type codes. The library builds its tables from
    the W and HSS rows; the other types are read only to check a claim about them.
    """
    try:
        with ZipFile(path) as workbook:
            strings = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
            shared = [
                "".join(node.text or "" for node in item.iter(f"{_XLSX_NS}t"))
                for item in strings.findall(f"{_XLSX_NS}si")
            ]
            with workbook.open("xl/worksheets/sheet2.xml") as sheet:
                rows: list[dict[str, str]] = []
                for _event, row in ElementTree.iterparse(sheet, events=("end",)):
                    if row.tag != f"{_XLSX_NS}row":
                        continue
                    values: dict[str, str] = {}
                    for cell in row.findall(f"{_XLSX_NS}c"):
                        reference = cell.get("r", "")
                        match = _CELL_COLUMN.match(reference)
                        if match is None or match.group() not in _AISC_COLUMNS:
                            continue
                        if (value := _xlsx_value(cell, shared)) is not None:
                            values[match.group()] = value
                    rows.append(values)
                    row.clear()
    except (BadZipFile, KeyError, ElementTree.ParseError, ValueError) as invalid:
        raise ValueError(
            f"{path} is not the pinned AISC Shapes Database v16.0 workbook: {invalid}"
        ) from invalid
    if not rows or any(rows[0].get(column) != heading for column, heading in _AISC_COLUMNS.items()):
        raise ValueError(
            f"{path} does not carry the expected AISC v16.0 geometry columns "
            f"{sorted(_AISC_COLUMNS.values())}"
        )
    return [row for row in rows[1:] if row.get("A") in kinds]


@cache
def _load_aisc_profiles(path: str, provenance_json: str) -> AiscProfileTable:
    provenance = FetchProvenance.model_validate_json(provenance_json)

    def _dimension(value_in: float, designation: str, field: str) -> QuantityProperty:
        return QuantityProperty(
            quantity=Quantity(magnitude=value_in * 25.4, unit="mm"),
            citation=PropertyCitation(
                source=provenance.source,
                condition=f"{designation} {field}, AISC database US customary column",
                license=provenance.license,
                retrieved=provenance.retrieved,
            ),
        )

    profiles: dict[str, RolledProfile] = {}
    hollow: dict[str, HollowProfile] = {}
    for row in _aisc_rows(Path(path)):
        is_hss = row.get("A") == "HSS"
        kind = "HSS" if is_hss else "W-shape"
        canonical = canonical_hss_designation if is_hss else canonical_aisc_designation
        try:
            designation = canonical(row["C"])
            if designation is None or designation != row["C"]:
                raise ValueError(f"non-canonical {kind} designation {row['C']!r}")
            if is_hss:
                wall = _dimension(float(row["X"]), designation, "design wall thickness")
                # A cell with no number in it is an en dash, which is how the workbook
                # says a round HSS has no height and a rectangular one no diameter.
                if _is_number(row.get("K")):
                    hollow[designation] = HollowProfile(
                        designation=designation,
                        depth=_dimension(float(row["K"]), designation, "outside diameter"),
                        wall_thickness=wall,
                    )
                else:
                    hollow[designation] = HollowProfile(
                        designation=designation,
                        depth=_dimension(float(row["I"]), designation, "height"),
                        breadth=_dimension(float(row["N"]), designation, "width"),
                        wall_thickness=wall,
                    )
                continue
            flange_thickness = float(row["T"])
            root_radius = float(row["Y"]) - flange_thickness
            profiles[designation] = RolledProfile(
                designation=designation,
                depth=_dimension(float(row["G"]), designation, "depth"),
                flange_width=_dimension(float(row["L"]), designation, "flange width"),
                web_thickness=_dimension(float(row["Q"]), designation, "web thickness"),
                flange_thickness=_dimension(flange_thickness, designation, "flange thickness"),
                root_radius=_dimension(root_radius, designation, "root radius (kdes - tf)"),
            )
        except (KeyError, TypeError, ValueError) as invalid:
            label = row.get("C", "<unnamed>")
            raise ValueError(f"invalid AISC {kind} row {label}: {_reason(invalid)}") from invalid
    if not profiles:
        raise ValueError("the AISC workbook contains no W-shape geometry")
    return AiscProfileTable(profiles, provenance, hollow)


def _is_number(cell: str | None) -> bool:
    try:
        float(cell)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return True


def _table_from_cached(path: Path, provenance: FetchProvenance) -> AiscProfileTable:
    return _load_aisc_profiles(path.as_posix(), provenance.model_dump_json())


def cached_aisc_profile_table(*, cache_dir: str | Path | None = None) -> AiscProfileTable | None:
    """Return the verified local AISC W-shape table, without making a network call."""
    found = cached_dataset(AISC_SHAPES_V16, cache_dir=cache_dir)
    if found is None:
        return None
    return _table_from_cached(*found)


def fetch_aisc_profile_table(
    *,
    retrieved: str,
    consent: bool = False,
    cache_dir: str | Path | None = None,
    opener: Callable[[str], bytes] | None = None,
) -> AiscProfileTable:
    """Fetch the official workbook once with consent, then parse its W-shape geometry."""
    found = fetch_dataset(
        AISC_SHAPES_V16,
        retrieved=retrieved,
        consent=consent,
        cache_dir=cache_dir,
        opener=opener,
    )
    return _table_from_cached(*found)


def resolve_profile(
    designation: str, *, cache_dir: str | Path | None = None
) -> RolledProfile | HollowProfile:
    """Resolve a bundled EN profile or a fetched AISC W-shape or HSS, never fetching implicitly."""
    if canonical_designation(designation) is not None:
        return default_profile_table().get(designation)
    if (
        canonical_aisc_designation(designation) is None
        and canonical_hss_designation(designation) is None
    ):
        return default_profile_table().get(designation)
    table = cached_aisc_profile_table(cache_dir=cache_dir)
    if table is None:
        raise AiscProfileDataRequired(
            f"AISC shape {designation!r} needs the non-redistributable AISC Shapes "
            "Database v16.0. Fetch it once with `anvilate fetch aisc-shapes --consent` (in "
            "Python, `fetch_aisc_profile_table(retrieved=..., consent=True)`), or declare the "
            "section properties from a local source."
        )
    return table.get(designation)
