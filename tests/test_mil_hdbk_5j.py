"""The MIL-HDBK-5J design-allowables pack (expand-open-design-data 2.1).

The values are held against the handbook's own tables as transcribed column by column, not
against the data file, so a typo in the file fails here rather than agreeing with itself.
The two spec scenarios are run through the front door: a spec naming a B-basis record is
screened, and the scorecard and the provenance trail are read for the basis, the table and
the superseded note.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvilate.evidence import provenance_for
from anvilate.scorecard import CheckStatus
from anvilate.screening import screen_spec
from anvilate.spec import load_spec_yaml
from anvilate.standards import AllowableBasis
from anvilate.standards.materials import default_materials_db

_REPO = Path(__file__).resolve().parent.parent

# (Fty L, Ftu L) in ksi per record, and (E in 10^3 ksi, density in lb/in^3) per alloy/form,
# read off MIL-HDBK-5J Table 3.2.3.0(b1) (2024) and Table 3.7.6.0(b1) (7075).
_STRENGTHS = {
    "MIL5J-2024-T3-SHEET-A": (47, 64),
    "MIL5J-2024-T3-SHEET-B": (48, 65),
    "MIL5J-2024-T351-PLATE-A": (48, 63),
    "MIL5J-2024-T351-PLATE-B": (50, 65),
    "MIL5J-7075-T6-SHEET-A": (70, 78),
    "MIL5J-7075-T6-SHEET-B": (72, 80),
    "MIL5J-7075-T651-PLATE-A": (70, 77),
    "MIL5J-7075-T651-PLATE-B": (72, 79),
}
_ELASTIC = {
    "MIL5J-2024-T3-SHEET": (10.5, 0.100),
    "MIL5J-2024-T351-PLATE": (10.7, 0.100),
    "MIL5J-7075-T6-SHEET": (10.3, 0.101),
    "MIL5J-7075-T651-PLATE": (10.3, 0.101),
}
_TABLE = {"2024": "Table 3.2.3.0(b1)", "7075": "Table 3.7.6.0(b1)"}


def _pack() -> list[str]:
    return [m for m in default_materials_db().known_materials() if m.startswith("MIL5J-")]


def test_the_pack_is_exactly_the_transcribed_slice():
    assert sorted(_pack()) == sorted(_STRENGTHS)


@pytest.mark.parametrize("material_id", sorted(_STRENGTHS))
def test_each_value_is_the_handbook_table_value(material_id):
    record = default_materials_db().get(material_id)
    fty, ftu = _STRENGTHS[material_id]
    modulus, density = _ELASTIC[material_id.rsplit("-", 1)[0]]
    assert record.yield_strength.quantity.to("ksi").magnitude == pytest.approx(fty, rel=1e-12)
    assert record.ultimate_strength.quantity.to("ksi").magnitude == pytest.approx(ftu, rel=1e-12)
    assert record.elastic_modulus.quantity.to("ksi").magnitude == pytest.approx(
        modulus * 1e3, rel=1e-12
    )
    assert record.density.quantity.to("lb/inch**3").magnitude == pytest.approx(density, rel=1e-12)
    assert record.poisson_ratio.value == 0.33


@pytest.mark.parametrize("material_id", sorted(_STRENGTHS))
def test_each_strength_cites_its_table_its_basis_and_the_superseding_edition(material_id):
    record = default_materials_db().get(material_id)
    expected = AllowableBasis.A_BASIS if material_id.endswith("-A") else AllowableBasis.B_BASIS
    table = _TABLE[material_id.split("-")[1]]
    for name in ("yield_strength", "ultimate_strength"):
        citation = getattr(record, name).citation
        assert citation.basis is expected, (material_id, name)
        assert citation.source == f"MIL-HDBK-5J {table}"
        assert "L direction" in citation.condition
        assert " in." in citation.condition, "the thickness range the value holds for"
    for citation in record.citations().values():
        assert citation.superseded is not None and "MMPDS" in citation.superseded


def test_b_basis_is_never_below_a_basis_and_yield_never_above_ultimate():
    """The two orderings the handbook's statistics guarantee, over every pair in the pack."""
    database = default_materials_db()

    def ksi(material_id: str) -> tuple[float, float]:
        record = database.get(material_id)
        return (
            record.yield_strength.quantity.to("ksi").magnitude,
            record.ultimate_strength.quantity.to("ksi").magnitude,
        )

    pairs = 0
    for material_id in _pack():
        fty, ftu = ksi(material_id)
        assert fty < ftu, material_id
        if material_id.endswith("-A"):
            b_fty, b_ftu = ksi(material_id[:-1] + "B")
            assert b_fty >= fty and b_ftu >= ftu, material_id
            pairs += 1
    assert pairs == 4


def _padeye(material_id: str):  # type: ignore[no-untyped-def]
    text = (_REPO / "examples" / "padeye.spec.yaml").read_text(encoding="utf-8")
    assert text.count("ASTM-A36") == 2, "the padeye example no longer names its material twice"
    return load_spec_yaml(text.replace("ASTM-A36", material_id))


def test_a_screen_on_a_b_basis_allowable_states_the_basis_and_the_table():
    """Scenario: basis visible in the verdict."""
    card = screen_spec(_padeye("MIL5J-2024-T351-PLATE-B"))
    strength_entries = [e for e in card.entries if e.name.startswith("padeye ")]
    assert len(strength_entries) == 2
    for entry in strength_entries:
        assert entry.status is CheckStatus.PASS
        assert "yield strength is B-basis, MIL-HDBK-5J Table 3.2.3.0(b1)" in entry.detail
        assert "A-basis" not in entry.detail


def test_an_a_basis_screen_says_a_basis_and_a_specification_minimum_says_nothing_new():
    """Distinguishable: the same screen on the A-basis record, and on a spec-minimum one."""
    card = screen_spec(_padeye("MIL5J-2024-T351-PLATE-A"))
    assert all("is A-basis" in e.detail for e in card.entries if e.name.startswith("padeye "))
    card = screen_spec(_padeye("ASTM-A36"))
    for entry in card.entries:
        assert "basis" not in entry.detail and "superseded" not in entry.detail


def test_a_value_from_the_superseded_edition_says_so_in_the_verdict_and_the_provenance():
    """Scenario: superseded status disclosed, in both places a reader meets the value."""
    spec = _padeye("MIL5J-7075-T651-PLATE-B")
    card = screen_spec(spec)
    for entry in (e for e in card.entries if e.name.startswith("padeye ")):
        assert "superseded by MMPDS" in entry.detail
        assert "certification-grade work" in entry.detail
    (material, *_rest) = provenance_for(spec)
    assert material.ref == "MIL5J-7075-T651-PLATE-B"
    assert "MIL-HDBK-5J Table 3.7.6.0(b1) (b basis) [superseded: " in "; ".join(material.sources)
    assert all("superseded by MMPDS" in source for source in material.sources)
