"""Semantic GD&T: a feature control frame as data, not as a glyph on a drawing.

A drawing's feature control frame is a sentence with a grammar, and the grammar is
enforceable: a flatness callout may not reference a datum, a perpendicularity callout must
reference at least one, and a maximum-material modifier means nothing on a planar surface
because a surface has no material condition. Drawings carry these as symbols and the
checking is left to a human. This carries them as a typed model with the legality rules
in the constructor, so an illegal frame does not get built.

The niche is genuinely open: outside two small 1D stack-up tools, there is no
license-clean, open feature-control-frame data model.

Sources: ASME Y14.5 for the characteristic vocabulary, the datum-reference rules and the
material-condition modifiers, with ISO 1101 using the same symbols and a different default
for features of size. The characteristic set is edition-dependent and this module says so:
**Y14.5-2018 eliminated concentricity and symmetry**, which the 2009 edition carried, so
the edition is a declared input and a 2018 frame using either is refused with the reason.

Screening scope: this models and validates the callout. It does not verify that a part
meets it, does not resolve a datum reference frame into a coordinate system, and does not
compute a virtual condition boundary. What it does do is convert a position tolerance into
a 1D stack contribution with the conversion method stated, because that is the one place a
GD&T callout has to talk to the tolerance-stack layer.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite

from pydantic import ConfigDict, model_validator

from ._models import RevalidatedModel
from .units import Quantity

__all__ = [
    "Y14Edition",
    "CharacteristicClass",
    "Characteristic",
    "FeatureType",
    "MaterialCondition",
    "DatumBoundary",
    "FrameModifier",
    "DatumReference",
    "FeatureControlFrame",
    "position_stack_contribution",
]


class Y14Edition(StrEnum):
    """Which edition of ASME Y14.5 a frame is written to.

    Not decoration: the two editions do not share a characteristic set. **Y14.5-2018
    eliminated concentricity and symmetry**, both of which the 2009 edition carried, on
    the grounds that they are median-point controls that a position or runout callout
    expresses better and that almost nobody inspects correctly. A drawing that uses
    either is a 2009 drawing, and saying so is the difference between a legacy callout
    and a mistake.
    """

    Y14_5_2009 = "ASME Y14.5-2009"
    Y14_5_2018 = "ASME Y14.5-2018"


class CharacteristicClass(StrEnum):
    """The five families, which is what decides the datum rules."""

    FORM = "form"
    PROFILE = "profile"
    ORIENTATION = "orientation"
    LOCATION = "location"
    RUNOUT = "runout"


class Characteristic(StrEnum):
    """The geometric characteristics of ASME Y14.5 / ISO 1101."""

    STRAIGHTNESS = "straightness"
    FLATNESS = "flatness"
    CIRCULARITY = "circularity"
    CYLINDRICITY = "cylindricity"
    PROFILE_OF_A_LINE = "profile of a line"
    PROFILE_OF_A_SURFACE = "profile of a surface"
    ANGULARITY = "angularity"
    PERPENDICULARITY = "perpendicularity"
    PARALLELISM = "parallelism"
    POSITION = "position"
    CONCENTRICITY = "concentricity"
    SYMMETRY = "symmetry"
    CIRCULAR_RUNOUT = "circular runout"
    TOTAL_RUNOUT = "total runout"

    @property
    def characteristic_class(self) -> CharacteristicClass:
        """The family this characteristic belongs to."""
        return _CLASSES[self]

    @property
    def symbol(self) -> str:
        """The drawing symbol, for rendering a frame back as a human reads it."""
        return _SYMBOLS[self]


_CLASSES: dict[Characteristic, CharacteristicClass] = {
    Characteristic.STRAIGHTNESS: CharacteristicClass.FORM,
    Characteristic.FLATNESS: CharacteristicClass.FORM,
    Characteristic.CIRCULARITY: CharacteristicClass.FORM,
    Characteristic.CYLINDRICITY: CharacteristicClass.FORM,
    Characteristic.PROFILE_OF_A_LINE: CharacteristicClass.PROFILE,
    Characteristic.PROFILE_OF_A_SURFACE: CharacteristicClass.PROFILE,
    Characteristic.ANGULARITY: CharacteristicClass.ORIENTATION,
    Characteristic.PERPENDICULARITY: CharacteristicClass.ORIENTATION,
    Characteristic.PARALLELISM: CharacteristicClass.ORIENTATION,
    Characteristic.POSITION: CharacteristicClass.LOCATION,
    Characteristic.CONCENTRICITY: CharacteristicClass.LOCATION,
    Characteristic.SYMMETRY: CharacteristicClass.LOCATION,
    Characteristic.CIRCULAR_RUNOUT: CharacteristicClass.RUNOUT,
    Characteristic.TOTAL_RUNOUT: CharacteristicClass.RUNOUT,
}

_SYMBOLS: dict[Characteristic, str] = {
    Characteristic.STRAIGHTNESS: "—",
    Characteristic.FLATNESS: "▱",
    Characteristic.CIRCULARITY: "○",
    Characteristic.CYLINDRICITY: "⌭",
    Characteristic.PROFILE_OF_A_LINE: "⌒",
    Characteristic.PROFILE_OF_A_SURFACE: "⌓",
    Characteristic.ANGULARITY: "∠",
    Characteristic.PERPENDICULARITY: "⊥",
    Characteristic.PARALLELISM: "∥",
    Characteristic.POSITION: "⌖",
    Characteristic.CONCENTRICITY: "◎",
    Characteristic.SYMMETRY: "⌯",
    Characteristic.CIRCULAR_RUNOUT: "↗",
    Characteristic.TOTAL_RUNOUT: "⌰",
}

# Concentricity and symmetry were removed in the 2018 edition. Everything else is common
# to both, so the edition gate is a two-entry set rather than a per-edition table.
_REMOVED_IN_2018 = (Characteristic.CONCENTRICITY, Characteristic.SYMMETRY)


class FeatureType(StrEnum):
    """What the frame is applied to, which decides whether modifiers mean anything.

    :attr:`SURFACE` is a planar or curved surface — it has no size, so it has no maximum
    or least material condition, and an Ⓜ on a surface callout is not a tighter control,
    it is a callout that does not parse.

    :attr:`FEATURE_OF_SIZE` is a hole, pin, slot or width: something with two opposed
    points and therefore an actual mating envelope that material-condition modifiers
    describe.
    """

    SURFACE = "surface"
    FEATURE_OF_SIZE = "feature of size"


class MaterialCondition(StrEnum):
    """The material-condition modifier on the tolerance value.

    :attr:`RFS` (regardless of feature size) is the default and carries no symbol —
    Y14.5 dropped the Ⓢ symbol in 1994, so an explicit RFS in a frame is a frame written
    to a pre-1994 drawing.
    """

    RFS = "RFS"
    MMC = "MMC"
    LMC = "LMC"


class DatumBoundary(StrEnum):
    """The material-boundary modifier on a datum feature reference.

    RMB (regardless of material boundary) is the default. MMB and LMB apply only where
    the datum feature is itself a feature of size — a datum plane has no boundary to
    shift.
    """

    RMB = "RMB"
    MMB = "MMB"
    LMB = "LMB"


class FrameModifier(StrEnum):
    """The other modifiers a frame can carry.

    :attr:`PROJECTED` is the one with a hard rule attached: a projected tolerance zone
    exists to control the *orientation of a fastener above the surface*, so it belongs on
    a position or orientation callout for a feature of size and nowhere else.
    """

    DIAMETER = "diameter"
    PROJECTED = "projected"
    FREE_STATE = "free state"
    TANGENT_PLANE = "tangent plane"
    STATISTICAL = "statistical"


class DatumReference(RevalidatedModel):
    """One datum feature reference in the frame's ordered datum reference frame.

    Order carries meaning and is not cosmetic: the primary datum takes precedence, and
    A|B|C constrains a part differently from B|A|C. That is why references are a tuple
    and not a set.
    """

    model_config = ConfigDict(frozen=True)

    letter: str
    boundary: DatumBoundary = DatumBoundary.RMB
    is_feature_of_size: bool = False

    @model_validator(mode="after")
    def _well_formed(self) -> DatumReference:
        letter = self.letter.strip()
        if not letter or not letter.isalpha() or not letter.isupper():
            raise ValueError(
                f"a datum letter is one or more upper-case letters; got {self.letter!r}"
            )
        if self.boundary is not DatumBoundary.RMB and not self.is_feature_of_size:
            raise ValueError(
                f"datum {letter} carries {self.boundary.value}, but a material boundary "
                f"can only shift on a datum that is a feature of size; a datum plane has "
                f"no boundary to shift"
            )
        return self

    def __str__(self) -> str:
        suffix = {"RMB": "", "MMB": " Ⓜ", "LMB": " Ⓛ"}[self.boundary.value]
        return f"{self.letter}{suffix}"


class FeatureControlFrame(RevalidatedModel):
    """A feature control frame, with Y14.5's grammar enforced at construction.

    The legality rules, each of which is a real drawing error this refuses to represent:

    * **Form characteristics take no datum reference.** Flatness is a control of the
      surface against itself; a datum in the frame means the author meant parallelism.
    * **Orientation, location and runout characteristics require at least one.** They are
      relationships, and a relationship needs the other end.
    * **Profile takes datums or not**, and the two mean different things: with datums it
      locates, without them it controls form only.
    * **At most three datum references**, since three is what fully constrains six degrees
      of freedom, and no letter twice.
    * **Ⓜ and Ⓛ apply only to a feature of size.** A surface has no material condition,
      so the modifier does not tighten the callout, it fails to parse.
    * **A projected tolerance zone belongs to position and orientation of a feature of
      size** — it exists to control a fastener's attitude above the surface.
    * **A diametral zone belongs to a feature of size**, because a Ø zone is the zone of
      an axis, and a surface has no axis.
    * **Concentricity and symmetry are 2009-only**, removed by the 2018 edition.
    """

    model_config = ConfigDict(frozen=True)

    characteristic: Characteristic
    tolerance: Quantity
    feature_type: FeatureType
    edition: Y14Edition = Y14Edition.Y14_5_2018
    material_condition: MaterialCondition = MaterialCondition.RFS
    modifiers: tuple[FrameModifier, ...] = ()
    datums: tuple[DatumReference, ...] = ()

    @model_validator(mode="after")
    def _legal(self) -> FeatureControlFrame:
        if not self.tolerance.has_dimension("[length]"):
            raise ValueError(f"the tolerance must be a [length] quantity; got {self.tolerance}")
        # `<= 0` is False for NaN, so a NaN tolerance walked past the positivity guard and
        # built a frame whose every downstream comparison then silently failed safe.
        if not isfinite(self.tolerance.magnitude) or self.tolerance.magnitude <= 0:
            raise ValueError(
                f"the tolerance must be a positive, finite length; got {self.tolerance}"
            )
        family = self.characteristic.characteristic_class
        if self.edition is Y14Edition.Y14_5_2018 and self.characteristic in _REMOVED_IN_2018:
            raise ValueError(
                f"{self.characteristic.value} was eliminated in {self.edition.value}; it "
                f"exists only in {Y14Edition.Y14_5_2009.value}. Declare the earlier "
                f"edition for a legacy drawing, or use position or runout, which is what "
                f"the removal intended"
            )
        if family is CharacteristicClass.FORM and self.datums:
            raise ValueError(
                f"{self.characteristic.value} is a form control — the surface against "
                f"itself — and takes no datum reference; "
                f"{[str(d) for d in self.datums]} was given. A form callout that needs a "
                f"datum is an orientation callout"
            )
        if (
            family
            in (
                CharacteristicClass.ORIENTATION,
                CharacteristicClass.LOCATION,
                CharacteristicClass.RUNOUT,
            )
            and not self.datums
        ):
            raise ValueError(
                f"{self.characteristic.value} is a relationship to a datum reference "
                f"frame and none was given; a control of {family.value} without a datum "
                f"does not say what it is relative to"
            )
        if len(self.datums) > 3:
            raise ValueError(
                f"a datum reference frame holds at most three references — three is what "
                f"constrains six degrees of freedom — and {len(self.datums)} were given"
            )
        letters = [d.letter for d in self.datums]
        if len(set(letters)) != len(letters):
            raise ValueError(f"a datum letter appears twice in the frame: {letters}")
        if (
            self.material_condition is not MaterialCondition.RFS
            and self.feature_type is not FeatureType.FEATURE_OF_SIZE
        ):
            raise ValueError(
                f"{self.material_condition.value} applies to a feature of size; this "
                f"frame is applied to a {self.feature_type.value}, which has no material "
                f"condition, so the modifier does not tighten the control — it fails to "
                f"parse"
            )
        if FrameModifier.PROJECTED in self.modifiers:
            if family not in (CharacteristicClass.LOCATION, CharacteristicClass.ORIENTATION):
                raise ValueError(
                    f"a projected tolerance zone controls a fastener's attitude above the "
                    f"surface, so it belongs on a position or orientation callout, not on "
                    f"{self.characteristic.value}"
                )
            if self.feature_type is not FeatureType.FEATURE_OF_SIZE:
                raise ValueError(
                    "a projected tolerance zone projects the axis of a feature of size; "
                    "a surface has no axis to project"
                )
        if (
            FrameModifier.DIAMETER in self.modifiers
            and self.feature_type is not FeatureType.FEATURE_OF_SIZE
        ):
            raise ValueError(
                "a diametral tolerance zone is the zone of an axis, and a surface has no "
                "axis; drop the Ø or apply the frame to a feature of size"
            )
        if len(set(self.modifiers)) != len(self.modifiers):
            raise ValueError(f"a modifier appears twice: {[m.value for m in self.modifiers]}")
        return self

    @property
    def zone_is_diametral(self) -> bool:
        """Whether the tolerance zone is a cylinder (Ø) rather than a width."""
        return FrameModifier.DIAMETER in self.modifiers

    def render(self) -> str:
        """The frame as a drawing reads it: ``⌖ | Ø0.2 Ⓜ | A | B Ⓜ | C``."""
        value = f"{self.tolerance.magnitude:g} {self.tolerance.unit}"
        if self.zone_is_diametral:
            value = f"Ø{value}"
        suffix = {"RFS": "", "MMC": " Ⓜ", "LMC": " Ⓛ"}[self.material_condition.value]
        extra = "".join(
            {"projected": " Ⓟ", "free state": " Ⓕ", "tangent plane": " Ⓣ", "statistical": " ⟨ST⟩"}[
                modifier.value
            ]
            for modifier in self.modifiers
            if modifier is not FrameModifier.DIAMETER
        )
        cells = [self.characteristic.symbol, f"{value}{suffix}{extra}"]
        cells.extend(str(datum) for datum in self.datums)
        return " | ".join(cells)

    def __str__(self) -> str:
        return self.render()


def position_stack_contribution(
    frame: FeatureControlFrame, *, bonus: Quantity | None = None
) -> Quantity:
    """The ± half-band a position tolerance contributes to a **1D** stack-up.

    **The conversion method, stated because it is a choice and not a fact.** A position
    tolerance is a zone the feature's axis must lie within. Projected onto any one
    direction, a zone of total width t permits the axis to sit anywhere within ±t/2 of
    basic — and for a *diametral* zone Ø t, the extreme in any single direction is
    likewise ±t/2, at the point where the axis touches the cylinder along that direction.
    So the contribution is t/2 either way.

    That is the **worst-case** conversion and it is conservative for a diametral zone,
    deliberately. The true 2D distribution puts most of the probability well inside the
    extreme, so an RSS or Monte Carlo stack fed this half-band as though it were a 1D
    uniform band overstates the spread. Feeding a statistical stack a worst-case
    conversion is a known way to get a number that is neither worst case nor statistical;
    the honest use is a worst-case stack, and a statistical one wants the 2D distribution
    rather than this scalar.

    ``bonus`` is the bonus tolerance available at MMC — the difference between the
    feature's actual mating size and its maximum material size — and is **only** accepted
    on an MMC frame. Adding a bonus to an RFS callout is not a conservative simplification
    of anything; it is tolerance the drawing did not grant.
    """
    if frame.characteristic is not Characteristic.POSITION:
        raise ValueError(
            f"this conversion is defined for a position tolerance; got "
            f"{frame.characteristic.value}. An orientation or form zone does not locate "
            f"a feature and does not enter a location stack"
        )
    total = frame.tolerance.to("mm").magnitude
    if bonus is not None:
        if frame.material_condition is not MaterialCondition.MMC:
            raise ValueError(
                f"a bonus tolerance is earned by departure from maximum material "
                f"condition, and this frame is {frame.material_condition.value}; adding "
                f"one would be tolerance the drawing did not grant"
            )
        if not bonus.has_dimension("[length]"):
            raise ValueError(f"bonus must be a [length] quantity; got {bonus}")
        if bonus.magnitude < 0:
            raise ValueError(f"bonus must be non-negative; got {bonus}")
        total += bonus.to("mm").magnitude
    return Quantity(magnitude=total / 2.0, unit="mm")
