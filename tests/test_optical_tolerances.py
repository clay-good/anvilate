"""Optical tolerances, declared once and rendered as ISO 10110 indications."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.optical_tolerances import (
    BubblesAndInclusions,
    Centring,
    ImperfectionConvention,
    Inhomogeneity,
    OpticalElementTolerances,
    StressBirefringence,
    SurfaceForm,
    SurfaceImperfections,
)
from anvilate.units import Quantity

ISO = ImperfectionConvention.ISO_10110_7
MIL = ImperfectionConvention.MIL_PRF_13830B


def _lens(power: float = 2.0) -> OpticalElementTolerances:
    return OpticalElementTolerances(
        element="L1",
        optical_surfaces=("S1", "S2"),
        birefringence=StressBirefringence(nanometres_per_centimetre=20),
        bubbles=BubblesAndInclusions(count=3, grade=0.16),
        inhomogeneity=Inhomogeneity(inhomogeneity_class=1, striae_class=1),
        surface_form=(
            SurfaceForm(surface="S1", power_fringes=power, irregularity_fringes=0.5),
            SurfaceForm(
                surface="S2",
                power_fringes=3,
                irregularity_fringes=1,
                rotational_irregularity_fringes=0.5,
            ),
        ),
        centring=(Centring(surface="S1", tilt=Quantity(magnitude=1, unit="arcmin")),),
        imperfections=(SurfaceImperfections(surface="S1", convention=ISO, count=3, grade=0.16),),
    )


def test_every_characteristic_renders_under_its_iso_10110_code() -> None:
    assert _lens().indications() == (
        "L1: 0/20",
        "L1: 1/3×0.16",
        "L1: 2/1;1",
        "S1: 3/2(0.5)",
        "S1: 4/1'",
        "S1: 5/3×0.16",
        "S2: 3/3(1/0.5)",
    )


def test_a_tightened_tolerance_reaches_the_drawing_from_the_one_declaration() -> None:
    assert "S1: 3/1(0.5)" in _lens(power=1.0).indications()
    assert "S1: 3/2(0.5)" not in _lens(power=1.0).indications()


def test_a_scratch_dig_is_rendered_in_its_own_convention_and_named() -> None:
    lens = _lens().model_copy(
        update={
            "imperfections": (
                SurfaceImperfections(surface="S2", convention=MIL, scratch=60, dig=40),
            )
        }
    )
    assert "S2: 60-40 scratch-dig (MIL-PRF-13830B)" in lens.indications()
    # Each convention carries only its own fields: nothing converts one into the other.
    with pytest.raises(ValidationError, match="no ISO count or grade"):
        SurfaceImperfections(surface="S2", convention=MIL, scratch=60, dig=40, count=3)
    with pytest.raises(ValidationError, match="no scratch-dig"):
        SurfaceImperfections(surface="S2", convention=ISO, count=3, grade=0.16, dig=40)


def test_an_optical_tolerance_on_a_surface_that_is_not_optical_is_refused() -> None:
    with pytest.raises(ValidationError, match="attached to 'flange'"):
        OpticalElementTolerances(
            element="L1",
            optical_surfaces=("S1",),
            surface_form=(SurfaceForm(surface="flange", power_fringes=2, irregularity_fringes=1),),
        )


def test_a_centring_tolerance_is_an_angle_in_minutes_or_seconds() -> None:
    assert (
        Centring(surface="S1", tilt=Quantity(magnitude=30, unit="arcsec")).indication() == '4/30"'
    )
    with pytest.raises(ValidationError, match="arcminutes or arcseconds"):
        Centring(surface="S1", tilt=Quantity(magnitude=0.1, unit="mm"))
    bare = OpticalElementTolerances(element="L2", optical_surfaces=("S1",))
    assert str(bare) == "L2: no optical tolerances declared"
    assert str(_lens()).startswith("L1: 0/20")
