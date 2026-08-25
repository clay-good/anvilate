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
    from_sectionproperties,
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


# --- the sectionproperties adapter -------------------------------------------------------


class _StubSection:
    """A stand-in for a meshed ``sectionproperties`` section.

    **This stub proves the mapping decisions, not the API.** A test whose fixture and code
    under test were written by the same hand in the same hour proves they agree with each
    other; what it cannot prove is that either agrees with the package. That is what
    ``test_the_adapter_reads_a_real_sectionproperties_section`` below is for — opt-in here,
    run for real in CI — and the getter names and return shapes used here were read from
    the package's published API reference rather than recalled.
    """

    def __init__(self, *, area, ic, z, j=None, composite=False):
        self._area = area
        self._ic = ic
        self._z = z
        self._j = j
        self._composite = composite

    def is_composite(self):
        return self._composite

    def get_area(self):
        return self._area

    def get_ic(self):
        return self._ic

    def get_z(self):
        return self._z

    def get_j(self):
        if self._j is None:
            raise RuntimeError("run a warping analysis first")
        return self._j


def _rectangle_stub(width=50.0, height=100.0, **kwargs):
    return _StubSection(
        area=width * height,
        ic=(width * height**3 / 12, height * width**3 / 12, 0.0),
        z=(
            width * height**2 / 6,
            width * height**2 / 6,
            height * width**2 / 6,
            height * width**2 / 6,
        ),
        **kwargs,
    )


def test_the_adapter_carries_the_constants_and_the_provenance():
    imported = from_sectionproperties(
        _rectangle_stub(j=1.0e6), name="custom plate", length_unit="mm"
    )
    assert imported.area.to("mm**2").magnitude == pytest.approx(5000.0)
    assert imported.second_moment.to("mm**4").magnitude == pytest.approx(50 * 100**3 / 12)
    assert imported.extreme_fibre.to("mm").magnitude == pytest.approx(50.0)
    assert imported.torsion_constant is not None
    assert imported.source == "sectionproperties"
    assert imported.source_version.strip()


def test_the_extreme_fibre_comes_from_the_governing_modulus():
    """An asymmetric section has two section moduli, and only one of them is safe.

    ``c = I / min(z⁺, z⁻)`` is the far fibre. Taking the larger modulus yields a smaller
    c, a smaller bending stress, and a capacity the section does not have.
    """
    second_moment = 4.0e6
    asymmetric = _StubSection(
        area=5000.0,
        ic=(second_moment, 1.0e6, 0.0),
        z=(1.0e5, 5.0e4, 4.0e4, 4.0e4),  # z⁻ is the smaller, so it governs
    )
    imported = from_sectionproperties(asymmetric, name="tee", length_unit="mm")
    assert imported.extreme_fibre.to("mm").magnitude == pytest.approx(second_moment / 5.0e4)


def test_the_shear_form_factor_is_not_derived_from_the_shear_area():
    """The trap this adapter exists to not fall into.

    ``get_as()`` returns the Timoshenko shear area, and A/A_s is 1.2 for a rectangle.
    ``shear_form_factor`` is the peak-over-average ratio, 1.5 for a rectangle. Both read
    as "the shear factor for this shape"; substituting one for the other understates the
    peak shear stress by 25%. Left unset, the shear screen reports not_evaluated, which is
    the honest answer.
    """
    imported = from_sectionproperties(_rectangle_stub(j=1.0e6), name="r", length_unit="mm")
    assert imported.shear_form_factor is None
    assert imported.cross_section().shear_form_factor is None


def test_a_composite_section_is_refused():
    with pytest.raises(ValueError, match="modulus-weighted"):
        from_sectionproperties(_rectangle_stub(composite=True), name="r", length_unit="mm")


def test_a_section_with_no_warping_analysis_imports_without_a_torsion_constant():
    imported = from_sectionproperties(_rectangle_stub(), name="r", length_unit="mm")
    assert imported.torsion_constant is None
    # And it says so where a reader looking at provenance will see it, rather than leaving
    # the absence to be inferred from a null.
    assert "no warping analysis" in imported.method


def test_the_length_unit_is_required_because_the_package_has_none():
    with pytest.raises(ValueError, match="length_unit is required"):
        from_sectionproperties(_rectangle_stub(), name="r", length_unit="  ")


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_a_constant_that_is_not_a_positive_finite_number_is_refused(bad):
    # `<= 0` is False for NaN, so the finiteness half is not redundant.
    with pytest.raises(ValueError, match="positive finite number"):
        from_sectionproperties(
            _StubSection(area=bad, ic=(1.0, 1.0, 0.0), z=(1.0, 1.0, 1.0, 1.0)),
            name="r",
            length_unit="mm",
        )


def test_the_unit_the_caller_declares_is_the_unit_the_numbers_carry():
    # The same bare numbers, declared as inches. Millimetres read as inches would
    # understate a second moment by 4.2e5 and the screen would pass.
    imported = from_sectionproperties(_rectangle_stub(), name="r", length_unit="inch")
    assert imported.area.unit == "inch**2"
    assert imported.second_moment.to("inch**4").magnitude == pytest.approx(50 * 100**3 / 12)


def test_the_adapter_reads_a_real_sectionproperties_section():
    """The anchor: the same rectangle, meshed and integrated by the real package.

    Opt-in, because ``sectionproperties`` is not a runtime dependency. Skipped when it is
    absent — an unrunnable check is reported as not run, never as a pass — and CI installs
    it and runs this by name so the stub above is never the only thing holding the adapter.
    """
    pytest.importorskip("sectionproperties")
    from sectionproperties.analysis import Section
    from sectionproperties.pre.library import rectangular_section

    geometry = rectangular_section(b=50, d=100)
    geometry.create_mesh(mesh_sizes=[10])
    section = Section(geometry=geometry)
    section.calculate_geometric_properties()
    section.calculate_warping_properties()

    imported = from_sectionproperties(section, name="50x100", length_unit="mm")
    # Closed-form values for a rectangle, written out here rather than read back from the
    # package: a test that takes its expected values from the thing under test passes on
    # its own drift.
    assert imported.area.to("mm**2").magnitude == pytest.approx(5000.0, rel=1e-3)
    assert imported.second_moment.to("mm**4").magnitude == pytest.approx(50 * 100**3 / 12, rel=1e-3)
    assert imported.second_moment_transverse is not None
    assert imported.second_moment_transverse.to("mm**4").magnitude == pytest.approx(
        100 * 50**3 / 12, rel=1e-3
    )
    assert imported.extreme_fibre.to("mm").magnitude == pytest.approx(50.0, rel=1e-3)
    # Roark's torsion constant for a 2:1 rectangle: beta = 0.229 for b/a = 2.
    assert imported.torsion_constant is not None
    assert imported.torsion_constant.to("mm**4").magnitude == pytest.approx(
        0.229 * 100 * 50**3, rel=0.05
    )
    assert imported.shear_form_factor is None
    assert "warping" in imported.method
