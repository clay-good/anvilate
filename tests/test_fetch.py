"""The fetch-on-first-use flow: consent, checksum, provenance, and offline afterwards.

Every test here runs without a network. The transport is an argument, so a fetch is a
call to a function that returns bytes — which is also how the refusals are exercised:
a mirror serving something else is a lambda returning other bytes.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from anvilate.fetch import (
    ConsentRequired,
    DatasetRecipe,
    FetchProvenance,
    IntegrityError,
    attribution,
    cache_root,
    cached_dataset,
    fetch_dataset,
)

_PAYLOAD = b"case_id,material\nbookshelf,timber\n"


def _recipe(**overrides) -> DatasetRecipe:
    fields = {
        "name": "cases.csv",
        "url": "https://example.invalid/cases.csv",
        "sha256": hashlib.sha256(_PAYLOAD).hexdigest(),
        "license": "CC-BY-4.0",
        "source": "The example benchmark's case index",
        "redistributable": False,
    }
    fields.update(overrides)
    return DatasetRecipe(**fields)


def test_a_fetch_without_consent_is_refused_and_says_what_it_would_have_downloaded(tmp_path):
    with pytest.raises(ConsentRequired) as refused:
        fetch_dataset(_recipe(), retrieved="2026-08-27", cache_dir=tmp_path)
    message = str(refused.value)
    # The caller has to ask a person, so the refusal carries what the person needs.
    assert "https://example.invalid/cases.csv" in message
    assert "CC-BY-4.0" in message
    assert not list(tmp_path.iterdir()), "a refused fetch wrote something"


def test_a_consented_fetch_caches_the_payload_with_its_provenance(tmp_path):
    path, provenance = fetch_dataset(
        _recipe(),
        retrieved="2026-08-27",
        consent=True,
        cache_dir=tmp_path,
        opener=lambda url: _PAYLOAD,
    )
    assert path.read_bytes() == _PAYLOAD
    assert provenance.license == "CC-BY-4.0"
    assert provenance.retrieved == "2026-08-27"
    assert provenance.redistributable is False

    sidecar = tmp_path / "cases.csv.provenance.json"
    written = json.loads(sidecar.read_text())
    assert written["url"] == "https://example.invalid/cases.csv"
    assert written["sha256"] == hashlib.sha256(_PAYLOAD).hexdigest()
    # The record is the cache's own, not the running build's recipe.
    assert FetchProvenance.model_validate(written) == provenance


def test_every_lookup_after_the_first_is_offline(tmp_path):
    def _once(url: str) -> bytes:
        return _PAYLOAD

    fetch_dataset(_recipe(), retrieved="2026-08-27", consent=True, cache_dir=tmp_path, opener=_once)

    def _refuse(url: str) -> bytes:
        raise AssertionError("the cached dataset was fetched again")

    # No consent either: a cached dataset is a read, not a download.
    path, provenance = fetch_dataset(
        _recipe(), retrieved="2026-08-28", cache_dir=tmp_path, opener=_refuse
    )
    assert path.read_bytes() == _PAYLOAD
    # The retrieval date is the one it was actually fetched on, not today's argument.
    assert provenance.retrieved == "2026-08-27"


def test_a_payload_that_is_not_the_digest_is_refused_and_nothing_is_written(tmp_path):
    with pytest.raises(IntegrityError) as refused:
        fetch_dataset(
            _recipe(),
            retrieved="2026-08-27",
            consent=True,
            cache_dir=tmp_path,
            opener=lambda url: _PAYLOAD[:-1],
        )
    assert "as downloaded" in str(refused.value)
    assert not list(tmp_path.iterdir()), "a failed fetch left a partial file in the cache"


def test_a_cached_payload_that_changed_under_the_cache_is_refused(tmp_path):
    fetch_dataset(
        _recipe(),
        retrieved="2026-08-27",
        consent=True,
        cache_dir=tmp_path,
        opener=lambda url: _PAYLOAD,
    )
    (tmp_path / "cases.csv").write_bytes(_PAYLOAD + b"chair,PLA\n")
    with pytest.raises(IntegrityError, match="in the cache"):
        cached_dataset(_recipe(), cache_dir=tmp_path)


def test_a_payload_with_no_provenance_beside_it_is_refused(tmp_path):
    (tmp_path / "cases.csv").write_bytes(_PAYLOAD)
    with pytest.raises(IntegrityError, match="provenance"):
        cached_dataset(_recipe(), cache_dir=tmp_path)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("sha256", "not-a-digest", "64 lowercase hex"),
        ("sha256", "A" * 64, "64 lowercase hex"),
        ("name", "../escape", "file-safe"),
        ("name", "nested/name", "file-safe"),
        ("url", "http://example.invalid/cases.csv", "https"),
    ],
)
def test_a_recipe_that_could_not_verify_or_could_write_outside_the_cache_is_refused(
    field, value, message
):
    with pytest.raises(ValueError, match=message):
        _recipe(**{field: value})


def test_the_retrieval_date_is_stated_not_read_from_the_clock():
    # The whole package is gated against wall-clock calls because a bundle's digest has
    # to be reproducible; this is the same rule at the field.
    with pytest.raises(ValueError, match="ISO date"):
        FetchProvenance(
            name="cases.csv",
            url="https://example.invalid/cases.csv",
            sha256=hashlib.sha256(_PAYLOAD).hexdigest(),
            license="CC-BY-4.0",
            source="s",
            redistributable=False,
            retrieved="August 2026",
        )


def test_the_cache_root_prefers_the_explicit_path_then_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVILATE_DATA_HOME", str(tmp_path / "from-env"))
    assert cache_root(tmp_path / "explicit") == tmp_path / "explicit"
    assert cache_root() == tmp_path / "from-env"
    monkeypatch.delenv("ANVILATE_DATA_HOME")
    assert cache_root().parts[-2:] == ("anvilate", "datasets")


def test_nothing_in_the_module_reads_the_clock_or_the_network_by_default():
    """The two dependencies this flow must not acquire quietly.

    A wall-clock call would break the reproducible digest the attestation layer rests on,
    and an import-time network call would make an offline build hang rather than refuse.
    """
    import inspect

    from anvilate import fetch

    source = inspect.getsource(fetch)
    for forbidden in ("datetime.now", "date.today", "time.time"):
        assert forbidden not in source
    # urlopen is imported inside the default transport, so importing the module — or
    # using it with an injected opener — pulls in no network stack at all.
    assert "from urllib.request import urlopen" in source
    assert source.index("def _https_get") < source.index("from urllib.request import urlopen")


def test_a_recipe_pointed_at_a_new_version_refuses_the_stale_cache(tmp_path):
    """The likeliest integrity failure is not tampering, it is a bumped recipe.

    The cache is keyed by name, so a recipe that has been re-pointed at a new release
    with the same filename must not read the old payload back as though it were the new
    one — and the message has to say that, because that is the case a caller will hit.
    """
    fetch_dataset(
        _recipe(),
        retrieved="2026-08-27",
        consent=True,
        cache_dir=tmp_path,
        opener=lambda url: _PAYLOAD,
    )
    bumped = _recipe(sha256=hashlib.sha256(_PAYLOAD + b"v2\n").hexdigest())
    with pytest.raises(IntegrityError, match="pointed at a new version"):
        cached_dataset(bumped, cache_dir=tmp_path)


def test_the_attribution_line_carries_the_credit_the_licence_asks_for(tmp_path):
    _path, provenance = fetch_dataset(
        _recipe(),
        retrieved="2026-08-27",
        consent=True,
        cache_dir=tmp_path,
        opener=lambda url: _PAYLOAD,
    )
    line = attribution(provenance)
    for expected in (
        "The example benchmark's case index",
        "https://example.invalid/cases.csv",
        "CC-BY-4.0",
        "2026-08-27",
    ):
        assert expected in line
    # And the fact a bundle's reader most needs about a source we may read and not ship.
    assert "never shipped" in line
    shippable = FetchProvenance(**{**provenance.model_dump(), "redistributable": True})
    assert "never shipped" not in attribution(shippable)
    assert "redistributable" in attribution(shippable)


def test_an_empty_cache_path_is_a_mistake_rather_than_the_current_directory():
    # `Path("")` is `.`, so a caller who computed a path badly would write the cache into
    # whatever directory the process happens to be in.
    with pytest.raises(ValueError, match="empty cache path"):
        cache_root("")
