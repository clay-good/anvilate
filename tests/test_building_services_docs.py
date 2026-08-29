"""The building-services page, and the pack-documentation contract behind it.

`discipline-packs` says a pack bundles "check sets returning standard scorecard records ...
and user documentation", and its own scenario is explicit: a pack missing check citations,
golden-file tests, **or documentation** must be rejected with the missing items enumerated.
Four packs shipped and were tested with no page naming them and no README mention — a
capability a user has no way to discover.

Every figure on the page is read out of the page and recomputed from the pack, so the page
cannot drift from the library and a fixture cannot drift from the page.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

import pytest

from anvilate.units import Quantity

_REPO = Path(__file__).resolve().parent.parent
_PAGE = (_REPO / "docs" / "building-services-screening.md").read_text(encoding="utf-8")


def _quoted(pattern: str) -> float:
    match = re.search(pattern, _PAGE)
    assert match is not None, f"{pattern!r} has moved on the building-services page"
    return float(match.group(1))


def _factors(card):
    return {entry.name: entry.safety_factor for entry in card.entries}


def test_the_noise_example_is_the_packs_own_answer():
    from anvilate.packs.noise_exposure import WorkerNoiseExposure, screen_noise_exposure

    levels = tuple(
        float(value)
        for value in re.search(r"machine_levels=\(([\d., ]+)\)", _PAGE).group(1).split(",")
        if value.strip()
    )
    hours = re.search(r'exposure_duration=Quantity\.parse\("([^"]+)"\)', _PAGE).group(1)
    card = screen_noise_exposure(
        WorkerNoiseExposure(machine_levels=levels, exposure_duration=Quantity.parse(hours))
    )
    (entry,) = card.entries
    assert entry.safety_factor == pytest.approx(
        _quoted(r"noise dose\s+FAIL\s+safety factor ([\d.]+)"), abs=5e-3
    )
    # The page's argument: two machines combine logarithmically, so the pair is louder than
    # either. A screen that added them arithmetically would be worse, not better.
    louder = screen_noise_exposure(
        WorkerNoiseExposure(machine_levels=(max(levels),), exposure_duration=Quantity.parse(hours))
    )
    assert entry.safety_factor < louder.entries[0].safety_factor
    assert entry.reference is not None and "1910.95" in entry.reference


def _page_kwargs(block: str, fields: dict[str, str]) -> dict:
    """Each declared field read out of the page's own code block."""
    read = {}
    for name, kind in fields.items():
        if kind == "quantity":
            found = re.search(rf'{name}=Quantity\.parse\("([^"]+)"\)', block)
            read[name] = Quantity.parse(found.group(1))
        else:
            found = re.search(rf"{name}=([\d.]+)", block)
            read[name] = float(found.group(1)) if kind == "float" else int(float(found.group(1)))
        assert found is not None, f"{name} has moved on the page"
    return read


_LIGHTING_FIELDS = {
    "luminaire_count": "int",
    "lumens_per_luminaire": "quantity",
    "input_watts_per_luminaire": "quantity",
    "coefficient_of_utilization": "float",
    "light_loss_factor": "float",
    "floor_area": "quantity",
    "required_illuminance": "quantity",
    "allowable_power_density": "quantity",
}
_VENTILATION_FIELDS = {
    "people_outdoor_rate": "quantity",
    "occupancy": "float",
    "area_outdoor_rate": "quantity",
    "floor_area": "quantity",
    "zone_air_distribution_effectiveness": "float",
    "provided_outdoor_airflow": "quantity",
    "room_volume": "quantity",
    "required_air_changes": "float",
}
_FEEDER_FIELDS = {
    "load_power": "quantity",
    "power_factor": "float",
    "line_voltage": "quantity",
    "resistivity": "quantity",
    "one_way_length": "quantity",
    "conductor_area": "quantity",
    "conductor_ampacity": "quantity",
}


def _block(marker: str) -> str:
    start = _PAGE.index(marker)
    return _PAGE[start : _PAGE.index("```", _PAGE.index("```python", start) + 9)]


def test_the_lighting_example_is_the_packs_own_answer():
    from anvilate.packs.lighting import LightingInstallation, screen_lighting

    block = _block("## Lighting")
    declared = _page_kwargs(block, _LIGHTING_FIELDS)
    card = screen_lighting(LightingInstallation(**declared))
    factors = _factors(card)
    assert factors["task illuminance"] == pytest.approx(
        _quoted(r"task illuminance\s+PASS\s+safety factor ([\d.]+)"), abs=5e-3
    )
    assert factors["lighting power density"] == pytest.approx(
        _quoted(r"lighting power density\s+PASS\s+safety factor ([\d.]+)"), abs=5e-3
    )
    # The page's claim that the two pull against each other: more luminaires lifts the
    # illuminance and pushes the power density the other way.
    more = screen_lighting(LightingInstallation(**{**declared, "luminaire_count": 30}))
    lifted = _factors(more)
    assert lifted["task illuminance"] > factors["task illuminance"]
    assert lifted["lighting power density"] < factors["lighting power density"]


def test_the_ventilation_example_is_the_packs_own_answer():
    from anvilate.packs.ventilation import VentilationZone, screen_ventilation

    block = _block("## Ventilation")
    fields = {
        "people_outdoor_rate": "quantity",
        "occupancy": "float",
        "area_outdoor_rate": "quantity",
        "floor_area": "quantity",
        "zone_air_distribution_effectiveness": "float",
        "provided_outdoor_airflow": "quantity",
        "room_volume": "quantity",
        "required_air_changes": "float",
    }
    declared = _page_kwargs(block, fields)
    factors = _factors(screen_ventilation(VentilationZone(**declared)))
    assert factors["outdoor air"] == pytest.approx(
        _quoted(r"outdoor air\s+PASS\s+safety factor ([\d.]+)"), abs=5e-3
    )
    assert factors["air changes per hour"] == pytest.approx(
        _quoted(r"air changes per hour\s+PASS\s+safety factor ([\d.]+)"), abs=5e-3
    )
    # "E_z is a divisor, so a poorly distributed zone needs MORE air, not less."
    mixed = _factors(
        screen_ventilation(
            VentilationZone(**{**declared, "zone_air_distribution_effectiveness": 1.0})
        )
    )
    assert mixed["outdoor air"] > factors["outdoor air"]
    claimed = _quoted(r"raises the requirement by (\d+)% over a perfectly mixed zone") / 100.0
    ratio = mixed["outdoor air"] / factors["outdoor air"] - 1.0
    assert ratio == pytest.approx(claimed, abs=5e-3), (ratio, claimed)


def test_the_feeder_example_is_the_packs_own_answer():
    from anvilate.packs.electrical import Feeder, screen_feeder

    block = _block("## Feeder")
    declared = _page_kwargs(block, _FEEDER_FIELDS)
    factors = _factors(screen_feeder(Feeder(**declared)))
    assert factors["voltage drop"] == pytest.approx(
        _quoted(r"voltage drop\s+PASS\s+safety factor ([\d.]+)"), abs=5e-3
    )
    assert factors["conductor ampacity"] == pytest.approx(
        _quoted(r"conductor ampacity\s+PASS\s+safety factor ([\d.]+)"), abs=5e-3
    )
    # "a 37 kW load at 0.85 pf draws more than the same load at unity" — the classic
    # undersizing, and the page says so, so it is asserted.
    unity = _factors(screen_feeder(Feeder(**{**declared, "power_factor": 1.0})))
    assert unity["conductor ampacity"] > factors["conductor ampacity"]


# --- the contract behind the page ----------------------------------------------------------


def _pack_modules() -> list[str]:
    import anvilate.packs as packs

    return sorted(
        info.name for info in pkgutil.iter_modules(packs.__path__) if not info.name.startswith("_")
    )


# Packs documented on pages that do not carry their module name: the page(s) to look at,
# and the reason. Listing the exceptions rather than the pages is the direction that
# survives a rename — and each exemption is *verified* rather than believed, because the
# first version of this list excused `industrial` with "pressure-equipment.md covers the
# pressure-loaded cover plate it screens" and that page never mentions a cover plate. An
# exemption whose reason nothing checks is a hole with a sentence in front of it.
_DOCUMENTED_ELSEWHERE = {
    "structural": (
        ("hot-rolled-steel.md", "lifting-devices.md", "load-combinations.md"),
        "documented across three pages by member rather than on one page of its own",
    ),
}


def test_every_discipline_pack_has_a_documentation_page_and_a_test_file():
    """`discipline-packs`: a pack missing citations, tests **or documentation** is rejected
    with the missing items enumerated. Four packs shipped with no page naming them."""
    modules = _pack_modules()
    assert len(modules) >= 9, modules
    docs = {path: path.read_text(encoding="utf-8") for path in (_REPO / "docs").glob("*.md")}
    tests = "\n".join(path.name for path in (_REPO / "tests").glob("*.py"))

    def _documented(name: str) -> bool:
        """A page importing the pack, or a page named after it.

        The three older packs are documented by `<pack>-screening.md`, which walks the
        *analysis* functions behind the screen rather than importing the pack module. Both
        count, and the difference is worth naming: this gate asks whether a pack has a page,
        not whether its own entry point appears on it.
        """
        stem = name.replace("_", "-")
        if any(path.stem == stem or path.stem.startswith(f"{stem}-") for path in docs):
            return True
        return any(
            f"packs.{name}" in text or f"packs import {name}" in text for text in docs.values()
        )

    missing: list[str] = []
    for name in modules:
        if not _documented(name) and name not in _DOCUMENTED_ELSEWHERE:
            missing.append(f"{name}: no documentation page names it")
        if name not in tests:
            missing.append(f"{name}: no test file names it")
    assert not missing, "packs missing contract items:\n  " + "\n  ".join(missing)

    # An exemption has to be true. Each names its pages, every page must exist, and their
    # text must name at least one symbol the pack exports — otherwise the entry is a
    # sentence in front of a hole, which is exactly what `industrial`'s first entry was.
    for name, (pages, reason) in _DOCUMENTED_ELSEWHERE.items():
        assert name in modules, f"{name} is excused and is no longer a pack"
        assert len(reason.split()) >= 5, f"{name} is excused without a reason"
        module = importlib.import_module(f"anvilate.packs.{name}")
        exported = {
            symbol
            for symbol in dir(module)
            if not symbol.startswith("_") and (symbol[0].isupper() or symbol.startswith("screen"))
        }
        text = ""
        for page in pages:
            path = _REPO / "docs" / page
            assert path.exists(), f"{name} is excused to {page}, which does not exist"
            text += path.read_text(encoding="utf-8")
        named = sorted(symbol for symbol in exported if symbol in text)
        assert named, (
            f"{name} is excused to {list(pages)}, and none of its {len(exported)} exported "
            f"symbols appears there — the exemption is not true"
        )


def test_every_check_in_these_packs_cites_its_clause():
    """The other half of the same requirement: every entry names the standard it applies."""
    from anvilate.packs.electrical import Feeder, screen_feeder
    from anvilate.packs.lighting import LightingInstallation, screen_lighting
    from anvilate.packs.noise_exposure import WorkerNoiseExposure, screen_noise_exposure
    from anvilate.packs.ventilation import VentilationZone, screen_ventilation

    cards = [
        screen_noise_exposure(
            WorkerNoiseExposure(machine_levels=(92.0,), exposure_duration=Quantity.parse("6 hour"))
        ),
        screen_lighting(
            LightingInstallation(**_page_kwargs(_block("## Lighting"), _LIGHTING_FIELDS))
        ),
        screen_ventilation(
            VentilationZone(**_page_kwargs(_block("## Ventilation"), _VENTILATION_FIELDS))
        ),
        screen_feeder(Feeder(**_page_kwargs(_block("## Feeder"), _FEEDER_FIELDS))),
    ]
    entries = [entry for card in cards for entry in card.entries]
    assert len(entries) >= 7, entries
    for entry in entries:
        assert entry.reference, f"{entry.name} names no standard"
        assert entry.reference in _PAGE, (
            f"{entry.name} cites {entry.reference!r}, absent from the page"
        )
