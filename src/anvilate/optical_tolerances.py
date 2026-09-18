"""Optical element tolerances, declared once and rendered as ISO 10110 indications.

An optical drawing states its tolerances in a notation of its own: a code number for the
characteristic and the value in the form ISO 10110 prescribes — ``0/20`` for stress
birefringence in nm/cm, ``3/2(0.5)`` for a surface-form tolerance of two fringes of power and
half a fringe of irregularity, ``4/1'`` for a centring tolerance of one arcminute, ``5/3×0.16``
for three surface imperfections of grade 0.16. The code numbers follow the parts of the
standard: 0/ part 2 (stress birefringence), 1/ part 3 (bubbles and inclusions), 2/ part 4
(inhomogeneity and striae), 3/ part 5 (surface form), 4/ part 6 (centring), 5/ part 7
(surface imperfections).

The tolerances here are the declaration and :meth:`OpticalElementTolerances.indications`
is one consumer of it, so a tightened tolerance reaches the drawing without a second copy of
the number. Two rules:

- A **surface** tolerance names the surface it applies to, and that surface must be one the
  element declares as optical. A surface-form tolerance on a mounting flange is refused, naming
  the characteristic and the feature, before anything renders it.
- A surface-imperfection tolerance may be declared in a **convention other than ISO 10110-7**
  — the scratch-dig of MIL-PRF-13830B — and is then rendered in that convention and named.
  Nothing converts one into the other: the two grade different things, and a converted value
  is a tolerance nobody specified.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, StatableModel
from .units import Quantity

__all__ = [
    "ImperfectionConvention",
    "StressBirefringence",
    "BubblesAndInclusions",
    "Inhomogeneity",
    "SurfaceForm",
    "Centring",
    "SurfaceImperfections",
    "OpticalElementTolerances",
]


def _number(value: float) -> str:
    return f"{value:g}"


class StressBirefringence(StatableModel):
    """ISO 10110-2: the permitted stress birefringence, in nm per cm of path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nanometres_per_centimetre: float = Field(gt=0)

    def indication(self) -> str:
        return f"0/{_number(self.nanometres_per_centimetre)}"


class BubblesAndInclusions(StatableModel):
    """ISO 10110-3: how many bubbles and inclusions, and the grade (edge length in mm)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int = Field(ge=1)
    grade: float = Field(gt=0)

    def indication(self) -> str:
        return f"1/{self.count}×{_number(self.grade)}"


class Inhomogeneity(StatableModel):
    """ISO 10110-4: the inhomogeneity class and the striae class, each 0 to 5."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    inhomogeneity_class: int = Field(ge=0, le=5)
    striae_class: int = Field(ge=0, le=5)

    def indication(self) -> str:
        return f"2/{self.inhomogeneity_class};{self.striae_class}"


class SurfaceForm(StatableModel):
    """ISO 10110-5: sagitta (power) and irregularity, in fringes, on one surface."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: Named
    power_fringes: float = Field(ge=0)
    irregularity_fringes: float = Field(ge=0)
    rotational_irregularity_fringes: float | None = Field(default=None, ge=0)

    def indication(self) -> str:
        inner = _number(self.irregularity_fringes)
        if self.rotational_irregularity_fringes is not None:
            inner += f"/{_number(self.rotational_irregularity_fringes)}"
        return f"3/{_number(self.power_fringes)}({inner})"


class Centring(StatableModel):
    """ISO 10110-6: the permitted surface tilt of one surface, as an angle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: Named
    tilt: Quantity

    @model_validator(mode="after")
    def _an_angle(self) -> Centring:
        if str(self.tilt.unit).strip() not in {"arcmin", "arcminute", "arcsec", "arcsecond"}:
            raise ValueError(
                f"a centring tolerance is written in arcminutes or arcseconds; got {self.tilt}"
            )
        if self.tilt.magnitude <= 0:
            raise ValueError(f"a centring tolerance must be positive; got {self.tilt}")
        return self

    def indication(self) -> str:
        mark = "'" if str(self.tilt.unit).startswith("arcmin") else '"'
        return f"4/{_number(self.tilt.magnitude)}{mark}"


class ImperfectionConvention(StrEnum):
    """How a surface-imperfection tolerance is written. The two are not interchangeable."""

    ISO_10110_7 = "iso_10110_7"
    MIL_PRF_13830B = "mil_prf_13830b"


class SurfaceImperfections(StatableModel):
    """Surface imperfections on one surface, in the convention the author declares.

    Under ISO 10110-7, ``count`` imperfections of grade ``grade`` (the square root of the
    permitted area, in mm). Under MIL-PRF-13830B, a ``scratch`` number and a ``dig`` number.
    The convention is required and each carries only its own fields: nothing here converts
    one into the other.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: Named
    convention: ImperfectionConvention
    count: int | None = Field(default=None, ge=1)
    grade: float | None = Field(default=None, gt=0)
    scratch: int | None = Field(default=None, ge=0)
    dig: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _its_own_fields(self) -> SurfaceImperfections:
        iso = self.count is not None and self.grade is not None
        mil = self.scratch is not None and self.dig is not None
        if self.convention is ImperfectionConvention.ISO_10110_7:
            if not iso or self.scratch is not None or self.dig is not None:
                raise ValueError(
                    "an ISO 10110-7 tolerance states a count and a grade, and no scratch-dig"
                )
        elif not mil or self.count is not None or self.grade is not None:
            raise ValueError(
                "a MIL-PRF-13830B tolerance states a scratch and a dig, and no ISO count or grade"
            )
        return self

    def indication(self) -> str:
        if self.convention is ImperfectionConvention.ISO_10110_7:
            return f"5/{self.count}×{_number(self.grade or 0.0)}"
        return f"{self.scratch}-{self.dig} scratch-dig (MIL-PRF-13830B)"


class OpticalElementTolerances(StatableModel):
    """One optical element's tolerances, and the surfaces of it that are optical."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    element: Named
    optical_surfaces: tuple[Named, ...] = Field(min_length=1)
    birefringence: StressBirefringence | None = None
    bubbles: BubblesAndInclusions | None = None
    inhomogeneity: Inhomogeneity | None = None
    surface_form: tuple[SurfaceForm, ...] = ()
    centring: tuple[Centring, ...] = ()
    imperfections: tuple[SurfaceImperfections, ...] = ()

    @model_validator(mode="after")
    def _on_optical_surfaces(self) -> OpticalElementTolerances:
        for characteristic, tolerances in (
            ("surface form", self.surface_form),
            ("centring", self.centring),
            ("surface imperfections", self.imperfections),
        ):
            for tolerance in tolerances:
                if tolerance.surface not in self.optical_surfaces:
                    raise ValueError(
                        f"a {characteristic} tolerance is attached to '{tolerance.surface}', "
                        f"which {self.element} does not declare as an optical surface; its "
                        f"optical surfaces are {list(self.optical_surfaces)}"
                    )
        return self

    def indications(self) -> tuple[str, ...]:
        """Every indication the drawing carries, the element's first, then each surface's."""
        lines = [
            f"{self.element}: {tolerance.indication()}"
            for tolerance in (self.birefringence, self.bubbles, self.inhomogeneity)
            if tolerance is not None
        ]
        for surface in self.optical_surfaces:
            for tolerance in (*self.surface_form, *self.centring, *self.imperfections):
                if tolerance.surface == surface:
                    lines.append(f"{surface}: {tolerance.indication()}")
        return tuple(lines)

    def __str__(self) -> str:
        return "\n".join(self.indications()) or f"{self.element}: no optical tolerances declared"
