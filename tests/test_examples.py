"""Execute the bundled examples so they stay green in CI (a runnable quickstart)."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from anvilate.scorecard import CheckStatus

_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_cantilever_bracket_example_screens_to_a_failing_scorecard():
    # run_path executes the module without triggering its __main__ block.
    namespace = runpy.run_path(str(_EXAMPLES / "cantilever_bracket_check.py"))
    card = namespace["screen_cantilever_bracket"]()
    # The aluminum bracket passes yield but fails deflection -> overall FAIL.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["bending yield"].status is CheckStatus.PASS
    assert by_name["tip deflection"].status is CheckStatus.FAIL


def test_bolted_joint_example_screens_to_a_passing_scorecard():
    namespace = runpy.run_path(str(_EXAMPLES / "bolted_joint_check.py"))
    card = namespace["screen_bolted_joint"]()
    # The joint is sized so both bearing and shear pass -> overall PASS.
    assert card.status is CheckStatus.PASS
    assert {e.name for e in card.entries} == {"plate bearing", "bolt shear"}
    assert all(e.passed for e in card.entries)


def test_motor_mount_example_flags_a_resonance():
    namespace = runpy.run_path(str(_EXAMPLES / "motor_mount_resonance.py"))
    card = namespace["screen_motor_mount"]()
    # The flexible bracket resonates below the running speed -> FAIL.
    assert card.status is CheckStatus.FAIL
    assert [e.name for e in card.entries] == ["mount resonance"]


def test_mezzanine_structure_example_passes():
    namespace = runpy.run_path(str(_EXAMPLES / "mezzanine_structure.py"))
    card = namespace["screen_mezzanine"]()
    # A well-sized mezzanine: the beam (bending + deflection) and both posts pass.
    assert card.status is CheckStatus.PASS
    assert len(card.entries) == 4
    assert all(e.passed for e in card.entries)


def test_lifting_padeye_example_flags_pin_bearing():
    namespace = runpy.run_path(str(_EXAMPLES / "lifting_padeye.py"))
    card = namespace["screen_padeye"]()
    # Net tension and weld pass, but the pin bearing is short of the 2.0 rigging
    # safety factor -> the assembly FAILs, catching an under-sized pin/hole.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["padeye net tension"].passed
    assert by_name["padeye_weld weld shear"].passed
    assert not by_name["padeye pin bearing"].passed


def test_lug_drawing_example_checks_and_draws(tmp_path):
    pytest.importorskip("ezdxf")
    namespace = runpy.run_path(str(_EXAMPLES / "lug_drawing.py"))
    card, path = namespace["check_and_draw_lug"](tmp_path / "padeye.dxf")
    # The full white-space vertical: the lug passes its ASME BTH-1 checks and its
    # DXF outline is written.
    assert card.status is CheckStatus.PASS
    assert path.exists()
