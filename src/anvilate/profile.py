"""Profiles: a cited, versioned bundle of declarations, supplied in one action and attributed.

The needs report (:mod:`anvilate.needs`) says what a build is waiting on. Supplying those
declarations one at a time is the other half of the friction: an engineer screening an
outdoor steel bracket needs an environment, a shop practice and a handling case, and each of
those is several values that belong together.

A :class:`Profile` is that set, as a record: an id, a version, the citation it comes from, an
:class:`Applicability` statement bounding where it may be used, and the values it supplies.
Binding one supplies them all at once, and every value it supplied carries where it came
from wherever it appears — a profile-supplied number that governs a verdict must never read
as one the engineer stated.

Three rules make a profile evidence rather than a convenience:

- **Applicability is checked, not documented.** A profile bound to a context outside its own
  stated range is refused naming the value, the bound it exceeds, and the profile — because
  a value used outside its basis is an invented one with a citation attached.
- **Every supplied value is individually overridable**, and an override is recorded as the
  user's own, so the report distinguishes what the profile said from what the engineer did.
- **A profile supplies declarations only.** It does not screen, weaken a refusal, or change a
  verdict; it fills the document the screens then read.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, Provenance, StatableModel
from .units import Quantity

__all__ = [
    "Applicability",
    "SuppliedValue",
    "Profile",
    "ProfileBinding",
    "OutsideApplicability",
]


class OutsideApplicability(ValueError):
    """Raised when a profile is bound to a context its own statement does not cover."""


class Applicability(StatableModel):
    """One bound on where a profile may be used: a context quantity and its range.

    ``context`` names what the range is about — ``ambient temperature``, ``plate thickness``
    — and is matched against the caller's context by that name. At least one of ``minimum``
    and ``maximum`` is stated; a bound with neither is not a bound.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    context: Named
    minimum: Quantity | None = None
    maximum: Quantity | None = None

    @model_validator(mode="after")
    def _a_bound(self) -> Applicability:
        if self.minimum is None and self.maximum is None:
            raise ValueError(
                f"the applicability bound on '{self.context}' states neither a minimum nor a "
                "maximum; a range with no end covers everything and says nothing"
            )
        if self.minimum is not None and self.maximum is not None:
            if self.minimum.pint.dimensionality != self.maximum.pint.dimensionality:
                raise ValueError(
                    f"the applicability bound on '{self.context}' runs from "
                    f"{self.minimum.dimensionality} to {self.maximum.dimensionality}; a range "
                    "has one dimension"
                )
            if self.maximum.to(self.minimum.unit).magnitude < self.minimum.magnitude:
                raise ValueError(
                    f"the applicability bound on '{self.context}' has its maximum "
                    f"({self.maximum}) below its minimum ({self.minimum})"
                )
        return self

    def covers(self, value: Quantity) -> bool:
        """Whether ``value`` is inside this bound. A different dimension is never inside."""
        end = self.minimum if self.minimum is not None else self.maximum
        assert end is not None  # guaranteed above
        if value.pint.dimensionality != end.pint.dimensionality:
            return False
        magnitude = value.to(end.unit).magnitude
        if self.minimum is not None and magnitude < self.minimum.magnitude:
            return False
        return not (self.maximum is not None and magnitude > self.maximum.to(end.unit).magnitude)

    def __str__(self) -> str:
        if self.minimum is None:
            return f"{self.context} at most {self.maximum}"
        if self.maximum is None:
            return f"{self.context} at least {self.minimum}"
        return f"{self.context} from {self.minimum} to {self.maximum}"


class SuppliedValue(StatableModel):
    """One declaration a profile supplies, and who it came from once bound.

    ``overridden`` is the value the user put in the profile's place. The profile's own value
    is kept beside it rather than replaced, so a reader can see what was changed and from
    what — an override that erased the original would leave the report unable to say a
    profile was even involved.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    declaration: Named
    value: Quantity | float | str
    overridden: Quantity | float | str | None = None

    @property
    def effective(self) -> Quantity | float | str:
        """The value in force: the override where there is one, else the profile's."""
        return self.value if self.overridden is None else self.overridden

    def attribution(self, profile: Profile) -> str:
        """Where the value in force came from, in the words every surface should use."""
        if self.overridden is None:
            return f"profile {profile.id} {profile.version} ({profile.citation})"
        return f"user override of profile {profile.id} {profile.version}"

    def __str__(self) -> str:
        if self.overridden is None:
            return f"{self.declaration} = {self.value}"
        return f"{self.declaration} = {self.overridden} (profile said {self.value})"


class Profile(StatableModel):
    """A named, versioned, cited set of declarations, with the range it applies over."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    version: Named
    citation: Provenance
    applicability: tuple[Applicability, ...] = Field(min_length=1)
    supplies: tuple[SuppliedValue, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _well_formed(self) -> Profile:
        contexts = [bound.context for bound in self.applicability]
        if len(set(contexts)) != len(contexts):
            raise ValueError(f"profile {self.id} bounds one context twice: {sorted(contexts)}")
        declarations = [supplied.declaration for supplied in self.supplies]
        if len(set(declarations)) != len(declarations):
            raise ValueError(
                f"profile {self.id} supplies one declaration twice: {sorted(declarations)}"
            )
        if any(supplied.overridden is not None for supplied in self.supplies):
            raise ValueError(
                f"profile {self.id} carries an override in its own record; an override is "
                "something a user does to a binding, not part of the profile that was cited"
            )
        return self

    def bind(self, context: Mapping[str, Quantity]) -> ProfileBinding:
        """Supply every declaration at once, for a context this profile covers.

        ``context`` maps a bound's name to the value the design states for it. A bound this
        profile declares and the context does not state is refused too: an applicability
        nobody checked is an applicability nobody has.
        """
        outside = []
        for bound in self.applicability:
            stated = context.get(bound.context)
            if stated is None:
                outside.append(
                    f"the context states no {bound.context}, and this profile applies for {bound}"
                )
            elif not bound.covers(stated):
                outside.append(f"{bound.context} is {stated}, and this profile applies for {bound}")
        if outside:
            raise OutsideApplicability(
                f"profile {self.id} {self.version} does not apply here — {'; '.join(outside)}. "
                "A value used outside its own basis is an invented value with a citation on it"
            )
        return ProfileBinding(profile=self, values=self.supplies)

    def __str__(self) -> str:
        applies = "; ".join(str(bound) for bound in self.applicability)
        return (
            f"profile {self.id} {self.version} ({self.citation}): "
            f"{len(self.supplies)} declarations, applies for {applies}"
        )


class ProfileBinding(StatableModel):
    """A profile bound to a design: its declarations, and any the user overrode."""

    model_config = ConfigDict(frozen=True)

    profile: Profile
    values: tuple[SuppliedValue, ...]

    def declarations(self) -> dict[str, Quantity | float | str]:
        """Declaration to the value in force, overrides included."""
        return {supplied.declaration: supplied.effective for supplied in self.values}

    def attribution(self) -> dict[str, str]:
        """Declaration to where its value in force came from."""
        return {
            supplied.declaration: supplied.attribution(self.profile) for supplied in self.values
        }

    def override(self, declaration: str, value: Quantity | float | str) -> ProfileBinding:
        """This binding with ``declaration`` set by the user instead of by the profile."""
        if declaration not in {supplied.declaration for supplied in self.values}:
            raise ValueError(
                f"profile {self.profile.id} supplies "
                f"{sorted(supplied.declaration for supplied in self.values)} and not "
                f"'{declaration}'; overriding a declaration it never supplied would record "
                "the profile as the source of a value it did not give"
            )
        return ProfileBinding(
            profile=self.profile,
            values=tuple(
                supplied.model_copy(update={"overridden": value})
                if supplied.declaration == declaration
                else supplied
                for supplied in self.values
            ),
        )

    def overrides(self) -> tuple[SuppliedValue, ...]:
        return tuple(supplied for supplied in self.values if supplied.overridden is not None)

    def __str__(self) -> str:
        lines = [str(self.profile)]
        for supplied in self.values:
            lines.append(f"  {supplied} [{supplied.attribution(self.profile)}]")
        return "\n".join(lines)
