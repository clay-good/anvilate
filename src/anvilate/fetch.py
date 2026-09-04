"""Fetch-on-first-use for datasets this library may read but must not redistribute.

Some reference data is free to download and not free to ship: a publisher's section
database, a benchmark's case archive, a registration-gated materials table. The rule the
standards-data specification sets is that such a dataset is fetched to the user's own
machine once, with their explicit consent, verified against a checksum, cached with its
provenance, and read offline from then on — and that no release artifact contains any of
it, only the recipe and the digest.

Three properties this module is built around, each of them a refusal:

* **Consent is an argument, not a default.** A library cannot prompt, so it does not
  guess: :func:`fetch_dataset` downloads only when the caller passes ``consent=True``,
  and otherwise raises :class:`ConsentRequired` naming the source and its licence, which
  is what a caller needs to ask a person.
* **A checksum that does not match is not data.** The payload is verified before it is
  cached and again every time it is read, so a truncated download, a mirror serving
  something else, or a file edited in the cache is refused rather than parsed. A failed
  fetch leaves nothing behind.
* **The date is the caller's.** Nothing here reads the clock — a bundle's digest has to
  be reproducible, so ``retrieved`` is passed in, exactly as a calculation report's date
  is. The provenance sidecar records what was fetched, from where, under what licence,
  and on the date the caller stated.

The transport is injectable (``opener``), so the flow is exercised offline in full: the
tests fetch from a function, not from the network.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from ._models import Named, Provenance, RevalidatedModel

__all__ = [
    "ConsentRequired",
    "attribution",
    "DatasetRecipe",
    "FetchProvenance",
    "IntegrityError",
    "cache_root",
    "cached_dataset",
    "fetch_dataset",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ConsentRequired(RuntimeError):
    """A fetch was attempted without the caller stating that the user agreed to it."""


class IntegrityError(RuntimeError):
    """A payload's digest is not the one its recipe declares."""


class Opener(Protocol):
    """What :func:`fetch_dataset` needs of a transport: a URL in, bytes out."""

    def __call__(self, url: str) -> bytes: ...  # pragma: no cover - a typing shape


# `RevalidatedModel`, not `BaseModel`, and `name` is why. Its validator exists because the
# name becomes a path in the download cache, so a separator or a traversal in it is a write
# outside the cache — and `model_copy` runs no validators, so
# `recipe.model_copy(update={"name": "../escape"})` produced exactly the recipe the validator
# was written to refuse. The same bypass reached `sha256` (a digest that verifies nothing) and
# `url` (http instead of https). A rule stated per field is still a rule an update can break.
class DatasetRecipe(RevalidatedModel):
    """What it takes to fetch one dataset, and to say afterwards what was fetched.

    ``name`` is the cache key and the sidecar's stem; ``url`` the publisher's own
    location; ``sha256`` the digest the payload must have; ``license`` the SPDX
    identifier the source is offered under; ``source`` the human description a citation
    needs; and ``redistributable`` whether the licence would let *us* ship it — recorded
    because "we may read it" and "we may republish it" are different questions and the
    second one is the one that keeps data out of releases.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Named
    url: str
    sha256: str
    license: Provenance
    source: Provenance
    redistributable: bool = False

    @field_validator("sha256")
    @classmethod
    def _lowercase_hex(cls, value: str) -> str:
        if not _SHA256.match(value):
            raise ValueError(
                f"sha256 must be 64 lowercase hex characters; got {value!r}. A recipe "
                "without a real digest cannot verify anything."
            )
        return value

    @field_validator("name")
    @classmethod
    def _safe_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
            raise ValueError(
                f"name must be a plain file-safe token; got {value!r}. It becomes a path "
                "in the cache, so a separator or a traversal in it is a write outside it."
            )
        return value

    @field_validator("url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError(
                f"the source URL must be https; got {value!r}. A checksum proves the "
                "bytes, and the transport should not be the weak half."
            )
        return value


class FetchProvenance(RevalidatedModel):
    """What was fetched, from where, under what licence, and when the caller says.

    Written beside the payload as ``<name>.provenance.json`` so a cache directory is
    self-describing: an evidence roll-up reads the licence and the retrieval date from
    here rather than from the recipe that happens to be in the running build.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Named
    url: str
    sha256: str
    license: Provenance
    source: Provenance
    redistributable: bool
    retrieved: str

    @field_validator("retrieved")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        if not _ISO_DATE.match(value):
            raise ValueError(
                f"retrieved must be an ISO date the caller states; got {value!r}. This "
                "module never reads the clock — a bundle's digest has to be reproducible."
            )
        return value


def attribution(provenance: FetchProvenance) -> str:
    """The credit line a fetched dataset has to be cited with.

    An attribution licence is a condition, not a formality: CC BY 4.0 permits the use in
    exchange for the credit, so the flow that fetches the data is the one that has to be
    able to state it. The line names the source, where it came from, the licence and the
    date the caller recorded — and, for a source we may read but not ship, says so, since
    that is the fact a reader of an evidence bundle most needs and the recipe's
    ``redistributable`` flag is otherwise a field nothing consumes.
    """
    shipping = (
        "redistributable"
        if provenance.redistributable
        else "not redistributable: fetched to this machine, never shipped"
    )
    return (
        f"{provenance.source} — {provenance.url}, {provenance.license}, "
        f"retrieved {provenance.retrieved} ({shipping})"
    )


def cache_root(explicit: str | Path | None = None) -> Path:
    """Where fetched datasets live: ``explicit``, else ``$ANVILATE_DATA_HOME``, else
    ``~/.cache/anvilate/datasets``.

    A cache path is a place this library writes, so it is resolved in one function and
    every caller shares it — including the tests, which pass a temporary directory and so
    never touch the user's own cache.
    """
    if explicit is not None:
        if str(explicit) == "":
            raise ValueError(
                "an empty cache path is not the current directory: pass a real path, or "
                "None to use $ANVILATE_DATA_HOME or the default cache."
            )
        return Path(explicit)
    from_env = os.environ.get("ANVILATE_DATA_HOME")
    if from_env:
        return Path(from_env)
    return Path.home() / ".cache" / "anvilate" / "datasets"


def _payload_path(recipe: DatasetRecipe, root: Path) -> Path:
    return root / recipe.name


def _provenance_path(recipe: DatasetRecipe, root: Path) -> Path:
    return root / f"{recipe.name}.provenance.json"


def _verify(payload: bytes, recipe: DatasetRecipe, *, where: str) -> None:
    digest = hashlib.sha256(payload).hexdigest()
    if digest != recipe.sha256:
        raise IntegrityError(
            f"{recipe.name} {where} hashes to {digest}, and its recipe declares "
            f"{recipe.sha256}. Refusing it: a payload that is not the one the digest "
            "names is not the dataset — truncated, mirrored, edited in the cache, or "
            "left over from a recipe that has since been pointed at a new version."
        )


def cached_dataset(
    recipe: DatasetRecipe, *, cache_dir: str | Path | None = None
) -> tuple[Path, FetchProvenance] | None:
    """The cached payload and its provenance, or ``None`` if it has not been fetched.

    The digest is re-checked on every read, so a file that changed under the cache is
    refused with :class:`IntegrityError` rather than returned. A payload with no
    provenance sidecar is also refused: the licence and the retrieval date are part of
    the record, and data whose origin the cache cannot state is data nothing should cite.
    """
    root = cache_root(cache_dir)
    payload, sidecar = _payload_path(recipe, root), _provenance_path(recipe, root)
    if not payload.exists():
        return None
    if not sidecar.exists():
        raise IntegrityError(
            f"{payload} is cached with no {sidecar.name} beside it, so nothing can say "
            "where it came from or under what licence. Delete it and fetch again."
        )
    _verify(payload.read_bytes(), recipe, where="in the cache")
    try:
        text = sidecar.read_text(encoding="utf-8")
    except UnicodeDecodeError as unreadable:
        # A sidecar that is present and undecodable is the same fact as one that is absent —
        # nothing can say where the payload came from — so it gets the same exception and the
        # same remedy. Unguarded, `UnicodeDecodeError` reached the caller as a `ValueError`
        # from a function documented to refuse with `IntegrityError`.
        raise IntegrityError(
            f"{sidecar} is beside {payload.name} and is not UTF-8 text ({unreadable}), so "
            "nothing can say where it came from or under what licence. Delete both and "
            "fetch again."
        ) from unreadable
    return payload, FetchProvenance.model_validate_json(text)


def fetch_dataset(
    recipe: DatasetRecipe,
    *,
    retrieved: str,
    consent: bool = False,
    cache_dir: str | Path | None = None,
    opener: Callable[[str], bytes] | None = None,
) -> tuple[Path, FetchProvenance]:
    """Fetch ``recipe`` once, verify it, cache it with its provenance, and return both.

    A cached copy is returned without touching the network, which is what makes every
    lookup after the first one offline. ``consent`` must be ``True`` for a download —
    the caller states that the user agreed to it, because a library cannot ask. ``opener``
    replaces the transport, which is how this is tested without a network.

    Raises :class:`ConsentRequired` when a download is needed and not consented to, and
    :class:`IntegrityError` when the payload's digest is not the recipe's, in which case
    nothing is written.
    """
    root = cache_root(cache_dir)
    already = cached_dataset(recipe, cache_dir=root)
    if already is not None:
        return already

    if not consent:
        raise ConsentRequired(
            f"{recipe.name} is not cached and would be downloaded from {recipe.url} "
            f"({recipe.source}, {recipe.license}). Anvilate does not fetch anything "
            "without being told the user agreed: pass consent=True once they have."
        )

    payload = (opener or _https_get)(recipe.url)
    _verify(payload, recipe, where="as downloaded")

    provenance = FetchProvenance(
        name=recipe.name,
        url=recipe.url,
        sha256=recipe.sha256,
        license=recipe.license,
        source=recipe.source,
        redistributable=recipe.redistributable,
        retrieved=retrieved,
    )
    root.mkdir(parents=True, exist_ok=True)
    _payload_path(recipe, root).write_bytes(payload)
    _provenance_path(recipe, root).write_text(
        json.dumps(provenance.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return _payload_path(recipe, root), provenance


def _https_get(url: str) -> bytes:  # pragma: no cover - exercised by the scheduled job
    """The default transport: one https GET, no redirect to another scheme."""
    from urllib.request import urlopen

    with urlopen(url) as response:  # noqa: S310 - the recipe's validator requires https
        return response.read()
