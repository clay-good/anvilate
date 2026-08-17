"""Tests for the noise pack: WorkerNoiseExposure declaration and OSHA/NIOSH dose screen."""

from __future__ import annotations

import pytest

from anvilate.packs.noise_exposure import WorkerNoiseExposure, screen_noise_exposure
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def test_noise_exposure_over_osha_pel_fails():
    # 92 + 90 dBA combine to ~94.1 dBA; OSHA permits ~4.5 h, so a 6 h shift is over dose.
    exposure = WorkerNoiseExposure(machine_levels=(92.0, 90.0), exposure_duration=_q("6 hour"))
    card = screen_noise_exposure(exposure)
    assert card.status is CheckStatus.FAIL
    (entry,) = card.entries
    assert entry.name == "noise dose"
    assert entry.safety_factor < 1.0  # dose > 100%
    assert entry.reference is not None and "1910.95" in entry.reference


def test_noise_exposure_niosh_is_stricter_than_osha():
    exposure = WorkerNoiseExposure(machine_levels=(92.0, 90.0), exposure_duration=_q("6 hour"))
    osha = screen_noise_exposure(exposure).entries[0].safety_factor
    niosh = (
        screen_noise_exposure(exposure, criterion_level=85.0, exchange_rate=3.0)
        .entries[0]
        .safety_factor
    )
    # The 85 dBA / 3 dB NIOSH criterion is far more conservative: smaller safety factor.
    assert niosh < osha


def test_quiet_exposure_passes_with_margin():
    exposure = WorkerNoiseExposure(machine_levels=(80.0,), exposure_duration=_q("8 hour"))
    card = screen_noise_exposure(exposure)
    assert card.status is CheckStatus.PASS
    assert card.passed
    # 80 dBA is 10 dB below the OSHA criterion -> 4x the permissible dose headroom.
    assert card.entries[0].safety_factor == 4.0


def test_empty_machine_levels_raises():
    exposure = WorkerNoiseExposure(machine_levels=(), exposure_duration=_q("8 hour"))
    try:
        screen_noise_exposure(exposure)
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty machine_levels")


def test_the_default_required_safety_factor_is_the_osha_dose_of_one():
    # A mutation moving this default from 1.0 to 1.5 left the whole suite green. The 1.0 is
    # the OSHA 1910.95 criterion itself — a dose of exactly 1 is the permissible limit, and
    # screening it at 1.5 would silently impose a stricter rule than the one cited.
    exposure = WorkerNoiseExposure(machine_levels=(90.0,), exposure_duration=_q("7 hour"))
    card = screen_noise_exposure(exposure)
    entry = card.entries[0]
    # 90 dBA permits 8 h, so a 7 h shift runs at 8/7 = 1.143 — between 1.0 and 1.5, so the
    # verdict flips if the default moves.
    assert entry.safety_factor == pytest.approx(8.0 / 7.0, rel=1e-6)
    assert entry.required_safety_factor == pytest.approx(1.0, rel=1e-12)
    assert card.status is CheckStatus.PASS
    # And the argument is honoured, not decorative.
    assert screen_noise_exposure(exposure, required_safety_factor=1.5).status is CheckStatus.FAIL
