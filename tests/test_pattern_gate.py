"""Every registered pattern is held to the same five things (expand-drawable-parts 5.4).

A pattern is one line in the registry, and before this each family of patterns had its own
sweep: the everyday parts were rebuilt and drawn, the screened ones were written to STEP and
read back, and the four first patterns had neither as a sweep. So a pattern could be
registered into whichever family asked least. These read the registry instead, and a new
pattern is under all five the moment it is registered:

1. its worked example is its own and builds one valid solid;
2. building it twice gives the same solid, and its summary survives a round trip;
3. every face has a name;
4. every view draws;
5. its STEP file is one part and reads back at the volume that was built.

The catalog page is held to the registry in ``tests/test_parts_catalog.py``. The STEP referee
job is held to it here, by the floor it asserts on its own list.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path

import pytest
import yaml

pytest.importorskip("build123d")

from anvilate import projection  # noqa: E402
from anvilate.geometry import build_spec  # noqa: E402
from anvilate.patterns import patterns  # noqa: E402
from anvilate.spec import load_spec_yaml  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]
_PATTERNS = sorted(patterns())


def _spec(element_type: str):
    path = _REPO / "examples" / patterns()[element_type].example
    return load_spec_yaml(path.read_text(encoding="utf-8"))


@functools.cache
def _built(element_type: str):
    return build_spec(_spec(element_type))


def test_the_registry_is_the_population():
    """The floor: a sweep over an emptied registry would pass every test below."""
    assert len(_PATTERNS) >= 31
    assert all(patterns()[name].element_type == name for name in _PATTERNS)


@pytest.mark.parametrize("element_type", _PATTERNS)
def test_the_example_is_the_patterns_own_and_builds_one_valid_solid(element_type):
    pattern = patterns()[element_type]
    document = yaml.safe_load((_REPO / "examples" / pattern.example).read_text(encoding="utf-8"))
    assert document["element_type"] == element_type
    built = _built(element_type)
    assert built.is_valid and built.pattern == pattern.name
    assert built.volume_mm3 > 0 and built.envelope is pattern.envelope
    assert len(built.shape.solids()) == 1


@pytest.mark.parametrize("element_type", _PATTERNS)
def test_a_rebuild_is_the_same_solid_and_its_summary_round_trips(element_type):
    first, second = _built(element_type), build_spec(_spec(element_type))
    assert first is not second
    assert first.signature == second.signature and first.volume_mm3 == second.volume_mm3
    summary = first.summary()
    assert type(summary).model_validate_json(summary.model_dump_json(by_alias=True)) == summary
    assert summary.face_tags == tuple(sorted(first.faces))
    assert [feature.tag for feature in summary.features] == [f.tag for f in first.features]


@pytest.mark.parametrize("element_type", _PATTERNS)
def test_every_face_has_a_name(element_type):
    built = _built(element_type)
    assert built.faces and all(tag and faces for tag, faces in built.faces.items())
    assert sum(len(faces) for faces in built.faces.values()) == len(built.shape.faces())


@pytest.mark.parametrize("element_type", _PATTERNS)
def test_every_view_draws(element_type):
    built = _built(element_type)
    for view in projection.VIEWS:
        svg, height = projection.render_view(
            built.shape, built.faces, name=built.name, view=view, width_px=480
        )
        assert height > 0 and b"<path" in svg, (element_type, view)


@pytest.mark.parametrize("element_type", _PATTERNS)
def test_the_step_file_is_one_part_and_reads_back(element_type, tmp_path):
    from anvilate.export.gate import authorize_export
    from anvilate.geometry import read_step_validation_properties, write_step

    built = _built(element_type)
    path = write_step(
        built, tmp_path / "part.step", authorization=authorize_export(None, override=True)
    )
    assert path.read_text(encoding="utf-8").count("PRODUCT(") == 1
    assert read_step_validation_properties(path).volume_mm3 == pytest.approx(
        built.volume_mm3, rel=1e-9
    )


def test_the_step_referee_reads_every_pattern_and_cannot_quietly_read_fewer():
    """The scheduled job builds its list from the registry and asserts a floor on it.

    The list being the registry's is what covers a new pattern. The floor is what stops the
    list shrinking: an import that fails soft, or a registry module nobody imports, would
    referee fewer files and stay green. So the floor is the registry's own size, and
    registering a pattern means raising it in the workflow.
    """
    workflow = (_REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    referee = workflow[workflow.index("  step-referee:") :]
    assert "from anvilate.patterns import patterns" in referee
    assert "for pattern in patterns().values()" in referee
    (floor,) = re.findall(r"assert len\(found\) >= (\d+) and not missing", referee)
    assert int(floor) == len(_PATTERNS)
