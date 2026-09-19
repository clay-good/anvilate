"""European hot-rolled I and H profiles by name: ``IPE 200`` to a cited cross-section.

A structural check wants a :class:`~anvilate.analysis.section.CrossSection` — area, second
moments, extreme fibre — and an engineer writes ``IPE 200``. This table bridges the two with
no network call: the five EN 10365 dimensions of each IPE and HEA profile ship with the
package (``data/en_profiles.yaml``), and :meth:`RolledProfile.section` computes the properties
from them, root fillets included, with
:meth:`~anvilate.analysis.section.CrossSection.rolled_i_section`.

The dimensions are recorded as facts read from public tabulations of the standard, and every
one carries that citation. The standard itself is not redistributed. A name the table does
not hold is refused with the entries it nearly named, never approximated.
"""

from __future__ import annotations

import difflib
import re
from functools import cache
from typing import Annotated

import yaml
from pydantic import ConfigDict

from .._models import Named, RevalidatedModel
from ..analysis.section import CrossSection
from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "RolledProfile",
    "ProfileTable",
    "UnknownProfileError",
    "canonical_designation",
    "default_profile_table",
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


def canonical_designation(text: str) -> str | None:
    """``IPE 200`` for any spacing, case or separator of it, ``HEA 200`` for ``HE 200 A``, or
    ``None`` for something else."""
    match = _DESIGNATION.fullmatch(text)
    if match is None:
        return None
    if match.group(3) is not None:
        return f"HEA {int(match.group(3))}"
    return f"{match.group(1).upper()} {int(match.group(2))}"


class RolledProfile(RevalidatedModel):
    """One IPE or HEA profile: its EN 10365 dimensions, each cited."""

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


class UnknownProfileError(KeyError):
    """A requested profile designation has no record in the table."""

    def __init__(self, designation: str, suggestions: list[str]) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(
            f"no record for profile {designation!r}{hint} This table holds the EN 10365 IPE "
            "and HEA series; any other section is declared by its properties"
        )


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
        raise UnknownProfileError(
            designation, difflib.get_close_matches(probe, self._profiles, n=3, cutoff=0.6)
        )

    def __len__(self) -> int:
        return len(self._profiles)


def _load_profiles(text: str) -> dict[str, RolledProfile]:
    doc = yaml.safe_load(text)
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
