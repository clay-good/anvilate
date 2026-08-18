"""Semantic GD&T: the frame's grammar, enforced where a drawing leaves it to a reader."""

from __future__ import annotations

import pydantic
import pytest

from anvilate.gdt import (
    Characteristic,
    CharacteristicClass,
    DatumBoundary,
    DatumReference,
    FeatureControlFrame,
    FeatureType,
    FrameModifier,
    MaterialCondition,
    Y14Edition,
    position_stack_contribution,
)
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _position(**overrides) -> FeatureControlFrame:
    kwargs = {
        "characteristic": Characteristic.POSITION,
        "tolerance": _q("0.2 mm"),
        "feature_type": FeatureType.FEATURE_OF_SIZE,
        "material_condition": MaterialCondition.MMC,
        "modifiers": (FrameModifier.DIAMETER,),
        "datums": (DatumReference(letter="A"), DatumReference(letter="B")),
    }
    kwargs.update(overrides)
    return FeatureControlFrame(**kwargs)


def test_every_characteristic_is_classified_and_the_class_decides_the_datum_rule():
    """The five families cover all fourteen characteristics, with no gaps or overlaps."""
    families: dict[CharacteristicClass, list[Characteristic]] = {}
    for characteristic in Characteristic:
        families.setdefault(characteristic.characteristic_class, []).append(characteristic)
    assert len(families) == 5
    assert sum(len(v) for v in families.values()) == 14
    assert len(families[CharacteristicClass.FORM]) == 4
    assert len(families[CharacteristicClass.RUNOUT]) == 2
    # Every characteristic has a distinct symbol, so a rendered frame is unambiguous.
    symbols = [c.symbol for c in Characteristic]
    assert len(set(symbols)) == 14


def test_a_form_control_takes_no_datum_and_a_relationship_control_requires_one():
    """The two halves of the datum rule, and the error names what the author meant."""
    flat = FeatureControlFrame(
        characteristic=Characteristic.FLATNESS,
        tolerance=_q("0.05 mm"),
        feature_type=FeatureType.SURFACE,
    )
    assert flat.datums == ()
    with pytest.raises(pydantic.ValidationError, match="is an orientation callout"):
        FeatureControlFrame(
            characteristic=Characteristic.FLATNESS,
            tolerance=_q("0.05 mm"),
            feature_type=FeatureType.SURFACE,
            datums=(DatumReference(letter="A"),),
        )
    for characteristic in (
        Characteristic.PERPENDICULARITY,
        Characteristic.POSITION,
        Characteristic.TOTAL_RUNOUT,
    ):
        with pytest.raises(pydantic.ValidationError, match="does not say what it is relative to"):
            FeatureControlFrame(
                characteristic=characteristic,
                tolerance=_q("0.05 mm"),
                feature_type=FeatureType.FEATURE_OF_SIZE,
            )
    # Profile is the one family that may go either way, and both build.
    for datums in ((), (DatumReference(letter="A"),)):
        FeatureControlFrame(
            characteristic=Characteristic.PROFILE_OF_A_SURFACE,
            tolerance=_q("0.1 mm"),
            feature_type=FeatureType.SURFACE,
            datums=datums,
        )


def test_material_condition_modifiers_need_a_feature_of_size():
    """A surface has no size, so Ⓜ on one does not tighten the control — it fails to parse."""
    for condition in (MaterialCondition.MMC, MaterialCondition.LMC):
        with pytest.raises(pydantic.ValidationError, match="fails to parse"):
            FeatureControlFrame(
                characteristic=Characteristic.FLATNESS,
                tolerance=_q("0.05 mm"),
                feature_type=FeatureType.SURFACE,
                material_condition=condition,
            )
    # RFS is the default and is legal everywhere, because it is the absence of a modifier.
    assert (
        FeatureControlFrame(
            characteristic=Characteristic.FLATNESS,
            tolerance=_q("0.05 mm"),
            feature_type=FeatureType.SURFACE,
        ).material_condition
        is MaterialCondition.RFS
    )
    # A datum's material BOUNDARY has the same rule: a datum plane has none to shift.
    with pytest.raises(pydantic.ValidationError, match="no boundary to shift"):
        DatumReference(letter="B", boundary=DatumBoundary.MMB)
    DatumReference(letter="B", boundary=DatumBoundary.MMB, is_feature_of_size=True)


def test_the_2018_edition_no_longer_has_concentricity_or_symmetry():
    """The edition is not decoration: the two editions do not share a characteristic set."""
    for characteristic in (Characteristic.CONCENTRICITY, Characteristic.SYMMETRY):
        with pytest.raises(pydantic.ValidationError, match="was eliminated in ASME Y14.5-2018"):
            FeatureControlFrame(
                characteristic=characteristic,
                tolerance=_q("0.05 mm"),
                feature_type=FeatureType.FEATURE_OF_SIZE,
                datums=(DatumReference(letter="A"),),
            )
        legacy = FeatureControlFrame(
            characteristic=characteristic,
            tolerance=_q("0.05 mm"),
            feature_type=FeatureType.FEATURE_OF_SIZE,
            edition=Y14Edition.Y14_5_2009,
            datums=(DatumReference(letter="A"),),
        )
        assert legacy.edition is Y14Edition.Y14_5_2009
    # Everything else builds on both editions, so the gate is those two and nothing else.
    for edition in Y14Edition:
        FeatureControlFrame(
            characteristic=Characteristic.POSITION,
            tolerance=_q("0.2 mm"),
            feature_type=FeatureType.FEATURE_OF_SIZE,
            edition=edition,
            datums=(DatumReference(letter="A"),),
        )


def test_the_datum_reference_frame_is_ordered_bounded_and_free_of_repeats():
    with pytest.raises(pydantic.ValidationError, match="at most three references"):
        _position(datums=tuple(DatumReference(letter=x) for x in "ABCD"))
    with pytest.raises(pydantic.ValidationError, match="appears twice in the frame"):
        _position(datums=(DatumReference(letter="A"), DatumReference(letter="A")))
    # Order is meaning: A|B|C is a different constraint from B|A|C, so it is a tuple.
    first = _position(datums=(DatumReference(letter="A"), DatumReference(letter="B")))
    second = _position(datums=(DatumReference(letter="B"), DatumReference(letter="A")))
    assert first.render() != second.render()
    assert first.render().endswith("| A | B")
    with pytest.raises(pydantic.ValidationError, match="upper-case letters"):
        DatumReference(letter="a")
    with pytest.raises(pydantic.ValidationError, match="upper-case letters"):
        DatumReference(letter="1")


def test_projected_and_diametral_zones_belong_to_a_feature_of_size():
    """A Ø zone is the zone of an axis, and a projected zone projects one."""
    with pytest.raises(pydantic.ValidationError, match="a surface has no axis"):
        FeatureControlFrame(
            characteristic=Characteristic.FLATNESS,
            tolerance=_q("0.05 mm"),
            feature_type=FeatureType.SURFACE,
            modifiers=(FrameModifier.DIAMETER,),
        )
    with pytest.raises(pydantic.ValidationError, match="no axis to project"):
        FeatureControlFrame(
            characteristic=Characteristic.PERPENDICULARITY,
            tolerance=_q("0.05 mm"),
            feature_type=FeatureType.SURFACE,
            modifiers=(FrameModifier.PROJECTED,),
            datums=(DatumReference(letter="A"),),
        )
    with pytest.raises(pydantic.ValidationError, match="belongs on a position or orientation"):
        FeatureControlFrame(
            characteristic=Characteristic.CYLINDRICITY,
            tolerance=_q("0.05 mm"),
            feature_type=FeatureType.FEATURE_OF_SIZE,
            modifiers=(FrameModifier.PROJECTED,),
        )
    with pytest.raises(pydantic.ValidationError, match="modifier appears twice"):
        _position(modifiers=(FrameModifier.DIAMETER, FrameModifier.DIAMETER))


def test_a_frame_renders_as_a_drawing_reads_it():
    frame = _position(
        datums=(
            DatumReference(letter="A"),
            DatumReference(letter="B", boundary=DatumBoundary.MMB, is_feature_of_size=True),
            DatumReference(letter="C"),
        )
    )
    assert frame.render() == "⌖ | Ø0.2 mm Ⓜ | A | B Ⓜ | C"
    assert str(frame) == frame.render()
    assert frame.zone_is_diametral is True
    plain = FeatureControlFrame(
        characteristic=Characteristic.FLATNESS,
        tolerance=_q("0.05 mm"),
        feature_type=FeatureType.SURFACE,
    )
    assert plain.render() == "▱ | 0.05 mm"
    assert plain.zone_is_diametral is False


def test_the_position_stack_contribution_is_half_the_zone_and_says_it_is_worst_case():
    """Ø0.2 contributes ±0.1 in any one direction; bonus adds only on an MMC frame."""
    frame = _position()
    assert position_stack_contribution(frame).to("mm").magnitude == pytest.approx(0.1)
    with_bonus = position_stack_contribution(frame, bonus=_q("0.1 mm"))
    assert with_bonus.to("mm").magnitude == pytest.approx(0.15)
    # A non-diametral zone of the same total width contributes the same half-band.
    width_zone = _position(modifiers=())
    assert position_stack_contribution(width_zone).to("mm").magnitude == pytest.approx(0.1)
    # Bonus on an RFS callout is tolerance the drawing did not grant.
    rfs = _position(material_condition=MaterialCondition.RFS, modifiers=())
    with pytest.raises(ValueError, match="the drawing did not grant"):
        position_stack_contribution(rfs, bonus=_q("0.1 mm"))
    assert position_stack_contribution(rfs).to("mm").magnitude == pytest.approx(0.1)
    # Only a location tolerance enters a location stack.
    orientation = FeatureControlFrame(
        characteristic=Characteristic.PERPENDICULARITY,
        tolerance=_q("0.05 mm"),
        feature_type=FeatureType.FEATURE_OF_SIZE,
        datums=(DatumReference(letter="A"),),
    )
    with pytest.raises(ValueError, match="does not locate a feature"):
        position_stack_contribution(orientation)
    with pytest.raises(ValueError, match="must be non-negative"):
        position_stack_contribution(frame, bonus=_q("-0.1 mm"))


def test_a_tolerance_that_is_not_a_positive_length_is_refused():
    with pytest.raises(pydantic.ValidationError, match=r"must be a \[length\] quantity"):
        _position(tolerance=_q("0.2 kg"))
    with pytest.raises(pydantic.ValidationError, match="positive, finite"):
        _position(tolerance=_q("0 mm"))
    # `<= 0` is False for NaN, so a NaN tolerance used to walk past the positivity guard
    # and build a frame whose every downstream comparison then failed safe and silently.
    for poison in (float("nan"), float("inf")):
        with pytest.raises(pydantic.ValidationError, match="positive, finite"):
            _position(tolerance=Quantity(magnitude=poison, unit="mm"))
