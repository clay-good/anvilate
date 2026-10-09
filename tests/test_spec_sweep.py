"""Every spec-level quantity in a broad corpus, made wrong: refused or screened, never a crash.

The element sweeps (`test_element_zero_sweep.py`) reach only `element_params`, and the six
example specs carry four quantities outside them. `spec_corpus.jsonl` holds the 147 distinct
documents the suite screens (regenerate it with `tests/harvest_specs.py`), carrying a few
hundred constraint, load-case, acceptance, tolerance and carbon quantities. Each one is
given a unit of the wrong dimension, then a zero, a negative, a huge and a tiny magnitude.
A document may be refused (a sentence) or screened. Anything else reaches `anvilate check`
as an internal error, which is what `allowable_twist: 0.5 kg` did until `Quantity.to`
stopped raising pint's TypeError.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from anvilate.screening import screen_spec
from anvilate.spec import parse_spec
from anvilate.units import Quantity

_CORPUS = Path(__file__).resolve().parent / "spec_corpus.jsonl"


def _documents() -> list[dict]:
    return [json.loads(line) for line in _CORPUS.read_text(encoding="utf-8").splitlines()]


def _quantities(node: object, path: tuple = ()) -> Iterator[tuple]:
    if isinstance(node, dict):
        if "magnitude" in node and "unit" in node:
            yield path
            return
        for key, value in node.items():
            if key != "element_params":  # the element sweeps own those
                yield from _quantities(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _quantities(value, (*path, index))


def _wrong_unit(unit: str) -> str:
    return "mm" if Quantity(magnitude=1.0, unit=unit).has_dimension("[mass]") else "kg"


def _crashes(mutate) -> tuple[list[str], int]:
    crashes, probes = [], 0
    for document in _documents():
        for path in _quantities(document):
            for field, value in mutate(document, path):
                changed = copy.deepcopy(document)
                target = changed
                for part in path:
                    target = target[part]
                target[field] = value
                probes += 1
                where = f"{'.'.join(map(str, path))}.{field} = {value!r}"
                try:
                    screen_spec(parse_spec(changed))
                except (ValidationError, ValueError, LookupError):
                    continue
                except Exception as failure:  # noqa: BLE001 - reporting what escaped is the point
                    crashes.append(f"{where} -> {type(failure).__name__}: {failure}")
    return crashes, probes


def _at(document: dict, path: tuple) -> dict:
    for part in path:
        document = document[part]
    return document


def test_the_corpus_is_broad_and_every_document_in_it_still_parses():
    documents = _documents()
    assert len(documents) >= 100, f"the corpus holds {len(documents)} documents"
    assert sum(1 for d in documents for _ in _quantities(d)) >= 100
    for document in documents:
        parse_spec(document)


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("wrong dimension", lambda d, p: [("unit", _wrong_unit(_at(d, p)["unit"]))]),
        ("reciprocal time", lambda d, p: [("unit", "1/s")]),
        ("extreme magnitude", lambda d, p: [("magnitude", m) for m in (0, -1.0, 1e15, 1e-15)]),
    ],
)
def test_no_spec_level_quantity_crashes_the_screen(label, mutate):
    crashes, probes = _crashes(mutate)
    assert probes >= 100, f"only {probes} {label} probes ran"
    assert not crashes, "\n".join(crashes[:20])


def test_the_sweep_finds_pints_own_error(monkeypatch):
    """The adversary: the spec's fields check their dimension before anything converts, so
    pint's TypeError is unreachable here. Switch those checks off and restore the
    unguarded conversion, and the wrong-dimension sweep must report what then escapes."""

    def unguarded(self, unit):
        return Quantity(magnitude=self.pint.to(unit).magnitude, unit=unit)

    monkeypatch.setattr(Quantity, "to", unguarded)
    monkeypatch.setattr(Quantity, "has_dimension", lambda self, expected: True)
    crashes, _probes = _crashes(lambda d, p: [("unit", _wrong_unit(_at(d, p)["unit"]))])
    assert any("DimensionalityError" in crash for crash in crashes), crashes[:5]
