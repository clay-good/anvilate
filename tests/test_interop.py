"""Interop: the door is the design — conventions declared, nothing dropped in silence."""

from __future__ import annotations

import pydantic
import pytest

from anvilate.interop import (
    AxisMapping,
    ExternalSectionProperties,
    ForceComponent,
    ForceStation,
    MemberForceRecord,
    bind_demand,
    provenance_lines,
)
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _record(**overrides) -> MemberForceRecord:
    stations = tuple(
        ForceStation(
            position=Quantity(magnitude=position, unit="m"),
            components={
                "P": Quantity(magnitude=axial, unit="kN"),
                "M3": Quantity(magnitude=major, unit="kN*m"),
                "V2": Quantity(magnitude=shear, unit="kN"),
            },
        )
        for position, axial, major, shear in (
            (0.0, -180.0, -120.0, 95.0),
            (3.0, -176.0, 148.0, 12.0),
            (6.0, -172.0, -96.0, -88.0),
        )
    )
    kwargs = {
        "member": "C-12",
        "tool": "Pynite",
        "tool_version": "1.1.0",
        "load_case": "LRFD 2",
        "stations": stations,
    }
    kwargs.update(overrides)
    return MemberForceRecord(**kwargs)


def _mapping(**overrides) -> AxisMapping:
    kwargs = {
        "labels": {
            ForceComponent.AXIAL: "P",
            ForceComponent.MAJOR_BENDING: "M3",
            ForceComponent.MAJOR_SHEAR: "V2",
        },
        "axial_compression_positive": False,
    }
    kwargs.update(overrides)
    return AxisMapping(**kwargs)


def test_a_component_that_is_neither_mapped_nor_ignored_is_an_error():
    """Dropping a component silently is how a member gets screened without its moment."""
    with pytest.raises(ValueError, match="neither mapped nor"):
        bind_demand(
            _record(),
            _mapping(labels={ForceComponent.MAJOR_BENDING: "M3"}),
        )
    # Naming it in `ignored` is the act that makes dropping it deliberate.
    demand = bind_demand(
        _record(),
        _mapping(labels={ForceComponent.MAJOR_BENDING: "M3"}, ignored=("P", "V2")),
    )
    assert set(demand.components) == {ForceComponent.MAJOR_BENDING}
    # A mapping naming a label the tool never exported is a mismatch, not an empty read.
    with pytest.raises(ValueError, match="which Pynite did not export"):
        bind_demand(_record(), _mapping(labels={ForceComponent.MAJOR_BENDING: "Mz"}))


def test_the_axial_sign_convention_has_no_default_and_selects_the_clause():
    """A -180 kN compression imported unflipped is a 180 kN tension and a different clause.

    AISC routes combined axial-and-flexure to §H1.1 for compression and §H1.2 for
    tension, and the compression branch is the one that checks buckling. Both sign
    conventions are ordinary, so the declaration is required rather than defaulted.
    """
    with pytest.raises(pydantic.ValidationError):
        AxisMapping(labels={ForceComponent.AXIAL: "P"})

    flipped = bind_demand(_record(), _mapping())
    assert flipped.components[ForceComponent.AXIAL].to("kN").magnitude == pytest.approx(180.0)
    as_exported = bind_demand(_record(), _mapping(axial_compression_positive=True))
    assert as_exported.components[ForceComponent.AXIAL].to("kN").magnitude == pytest.approx(-180.0)
    # Only the axial sign is converted: bending and shear are screened on magnitude, so
    # their sign carries no capacity consequence.
    assert flipped.components[ForceComponent.MAJOR_BENDING].magnitude == pytest.approx(148.0)
    assert as_exported.components[ForceComponent.MAJOR_BENDING].magnitude == pytest.approx(148.0)


def test_each_component_governs_at_its_own_station():
    """Collapsing a member to one station screens every component at whichever one won."""
    demand = bind_demand(_record(), _mapping())
    assert demand.components[ForceComponent.MAJOR_BENDING].magnitude == pytest.approx(148.0)
    assert demand.stations[ForceComponent.MAJOR_BENDING].to("m").magnitude == 3.0
    assert demand.components[ForceComponent.MAJOR_SHEAR].magnitude == pytest.approx(95.0)
    assert demand.stations[ForceComponent.MAJOR_SHEAR].to("m").magnitude == 0.0
    # The governing value is the largest MAGNITUDE, and the sign is kept, not discarded.
    assert demand.stations[ForceComponent.AXIAL].to("m").magnitude == 0.0
    assert demand.get(ForceComponent.MINOR_BENDING) is None


def test_a_mapped_component_of_the_wrong_dimension_dies_at_the_door():
    """A kip-inch read as a kip-foot cannot get three functions downstream."""
    with pytest.raises(ValueError, match=r"must be \[force\]\*\[length\]"):
        bind_demand(
            _record(),
            _mapping(labels={ForceComponent.MAJOR_BENDING: "P"}, ignored=("M3", "V2")),
        )
    with pytest.raises(ValueError, match=r"must be \[force\]"):
        bind_demand(
            _record(),
            _mapping(labels={ForceComponent.AXIAL: "M3"}, ignored=("P", "V2")),
        )


def test_a_record_missing_its_provenance_or_varying_its_components_is_refused():
    for blank in ("member", "tool", "tool_version", "load_case"):
        with pytest.raises(pydantic.ValidationError, match=f"needs a {blank}"):
            _record(**{blank: "  "})
    # A component present at some stations and absent at others reads as zero at the rest.
    ragged = (
        ForceStation(position=_q("0 m"), components={"P": _q("10 kN"), "M3": _q("5 kN*m")}),
        ForceStation(position=_q("3 m"), components={"P": _q("11 kN")}),
    )
    with pytest.raises(pydantic.ValidationError, match="different components"):
        _record(stations=ragged)
    with pytest.raises(pydantic.ValidationError, match="no stations"):
        _record(stations=())


def test_a_mapping_that_double_books_or_contradicts_itself_is_refused():
    with pytest.raises(pydantic.ValidationError, match="mapped to two"):
        AxisMapping(
            labels={ForceComponent.MAJOR_BENDING: "M3", ForceComponent.MINOR_BENDING: "M3"},
            axial_compression_positive=True,
        )
    with pytest.raises(pydantic.ValidationError, match="both mapped and ignored"):
        AxisMapping(
            labels={ForceComponent.MAJOR_BENDING: "M3"},
            ignored=("M3",),
            axial_compression_positive=True,
        )
    with pytest.raises(pydantic.ValidationError, match="declares nothing"):
        AxisMapping(labels={}, axial_compression_positive=True)


def _section(**overrides) -> ExternalSectionProperties:
    kwargs = {
        "name": "BU-350x200",
        "source": "sectionproperties",
        "source_version": "3.2.1",
        "method": "warping analysis",
        "area": _q("9600 mm**2"),
        "second_moment": _q("2.05e8 mm**4"),
        "extreme_fibre": _q("175 mm"),
        "second_moment_transverse": _q("2.67e7 mm**4"),
    }
    kwargs.update(overrides)
    return ExternalSectionProperties(**kwargs)


def test_imported_section_axes_swapped_is_refused_because_both_numbers_look_plausible():
    """The major axis is the one with the larger I; the swap is the survivable mistake."""
    with pytest.raises(pydantic.ValidationError, match="so the axes are swapped"):
        _section(second_moment=_q("2.67e7 mm**4"), second_moment_transverse=_q("2.05e8 mm**4"))
    with pytest.raises(pydantic.ValidationError, match=r"must be a \[length\]\*\*4 quantity"):
        _section(second_moment=_q("2.05e8 mm**2"))
    with pytest.raises(pydantic.ValidationError, match="must be positive"):
        _section(area=_q("0 mm**2"))
    for blank in ("name", "source", "source_version", "method"):
        with pytest.raises(pydantic.ValidationError, match=f"need a {blank}"):
            _section(**{blank: " "})


def test_an_imported_section_never_guesses_a_shear_form_factor():
    """An imported section is exactly where assuming a rectangle's 1.5 would be wrong."""
    section = _section()
    assert section.shear_form_factor is None
    assert section.cross_section().shear_form_factor is None
    lines = provenance_lines(section=section)
    assert any("no shear form factor supplied" in line for line in lines)
    # The converted section carries both second moments through unchanged.
    converted = section.cross_section()
    assert converted.second_moment == section.second_moment
    assert converted.second_moment_transverse == section.second_moment_transverse


def test_provenance_says_who_computed_the_numbers_and_what_went_unscreened():
    demand = bind_demand(_record(), _mapping(ignored=()))
    lines = provenance_lines(
        demand=demand,
        section=_section(),
        ignored={"T": "resisted through the slab diaphragm"},
    )
    joined = "\n".join(lines)
    assert "Pynite 1.1.0" in joined
    assert "LRFD 2" in joined
    assert "it did not compute them" in joined
    assert "sectionproperties 3.2.1" in joined
    assert "warping analysis" in joined
    # What was NOT screened has to be as visible as what was.
    assert "not screened: T — resisted through the slab diaphragm" in joined
