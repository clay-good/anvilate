"""Tests for the scorecard entry vocabulary and the No-silent-green rule."""

from __future__ import annotations

from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry


def test_safety_factor_pass_and_fail():
    ok = ScorecardEntry.from_safety_factor("bending", computed=2.0, required=1.5)
    assert ok.status is CheckStatus.PASS
    assert ok.passed and ok.evaluated
    assert "2.00" in ok.detail

    bad = ScorecardEntry.from_safety_factor("bending", computed=1.2, required=1.5)
    assert bad.status is CheckStatus.FAIL
    assert not bad.passed
    assert bad.evaluated  # it ran; it just failed


def test_boundary_equal_to_required_passes():
    entry = ScorecardEntry.from_safety_factor("axial", computed=1.5, required=1.5)
    assert entry.status is CheckStatus.PASS


def test_missing_safety_factor_is_not_evaluated_not_a_silent_pass():
    # No silent green: an unavailable safety factor is NOT_EVALUATED, never PASS.
    entry = ScorecardEntry.from_safety_factor("fatigue", computed=None, required=2.0)
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert not entry.passed
    assert not entry.evaluated
    assert "not evaluated" in entry.detail


def test_entry_is_frozen_and_renders():
    entry = ScorecardEntry.from_safety_factor("torsion", computed=3.1, required=2.0)
    assert str(entry).startswith("[PASS] torsion:")


def _entry(name: str, status: CheckStatus) -> ScorecardEntry:
    return ScorecardEntry(name=name, status=status, detail="d")


def test_scorecard_passes_only_when_all_checks_pass():
    card = Scorecard(entries=(_entry("a", CheckStatus.PASS), _entry("b", CheckStatus.PASS)))
    assert card.status is CheckStatus.PASS
    assert card.passed
    assert card.failures() == ()
    assert card.not_evaluated() == ()


def test_scorecard_fails_if_any_check_fails():
    card = Scorecard(
        entries=(
            _entry("a", CheckStatus.PASS),
            _entry("b", CheckStatus.FAIL),
            _entry("c", CheckStatus.NOT_EVALUATED),
        )
    )
    # A failure dominates even when another check is unevaluated.
    assert card.status is CheckStatus.FAIL
    assert not card.passed
    assert [e.name for e in card.failures()] == ["b"]
    assert [e.name for e in card.not_evaluated()] == ["c"]


def test_scorecard_not_evaluated_blocks_a_pass_no_silent_green():
    # All non-failing but one unevaluated: not a pass.
    card = Scorecard(
        entries=(_entry("a", CheckStatus.PASS), _entry("b", CheckStatus.NOT_EVALUATED))
    )
    assert card.status is CheckStatus.NOT_EVALUATED
    assert not card.passed


def test_empty_scorecard_is_not_a_silent_pass():
    card = Scorecard()
    assert card.status is CheckStatus.NOT_EVALUATED
    assert not card.passed
