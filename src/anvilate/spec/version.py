"""Schema versioning and migration.

The Spec IR schema is semantically versioned. Anvilate loads any spec whose
major version it supports, applying registered migrations to bring older minor
versions up to the current schema. A spec from an unsupported major version is
refused rather than silently misread.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from ..refusal import RefusalError, Remedy
from .ir import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION", "UnsupportedSchemaVersion", "migrate_to_current"]

# Migrations transform a raw dict from one version to the next. Register the
# next entry here when the schema gains a minor version.
_MIGRATIONS: dict[str, tuple[str, Callable[[dict], dict]]] = {}


class UnsupportedSchemaVersion(RefusalError, ValueError):
    """A spec declares a schema version this release cannot load."""

    def __init__(
        self,
        message: str,
        *,
        declared: str = "the declared version",
        current: str = SCHEMA_VERSION,
    ) -> None:
        super().__init__(
            message,
            remedies=(
                Remedy(
                    action="upgrade or migrate",
                    subject=f"the Design Spec schema declaration {declared}",
                    source=(
                        f"an Anvilate release supporting {declared}, or schema {current} "
                        "after reviewing the document against it"
                    ),
                ),
            ),
        )


_VERSION = re.compile(r"\d+(\.\d+)*")


def _require_version_text(declared: object) -> str:
    """``declared`` as dotted digits, or a refusal saying what is wrong with it.

    Unquoted, ``anvilate_spec: 1.18`` is a YAML float, and ``1.10`` is the float ``1.1``: the
    version is changed by the time it arrives, so it is refused with the quoting that keeps
    it, not coerced. Both shapes used to reach ``int()`` — a float as an internal
    ``AttributeError``, and a malformed string as "invalid literal for int() with base 10".
    """
    if not isinstance(declared, str):
        unquoted = (
            ". Unquoted, YAML reads 1.10 as 1.1"
            if isinstance(declared, int | float) and not isinstance(declared, bool)
            else ""
        )
        raise UnsupportedSchemaVersion(
            f"anvilate_spec must be a quoted version string; got {declared!r}{unquoted}, "
            f'so write it as anvilate_spec: "{SCHEMA_VERSION}"',
            declared=repr(declared),
        )
    if not _VERSION.fullmatch(declared):
        raise UnsupportedSchemaVersion(
            f"anvilate_spec must be a version of dotted numbers such as {SCHEMA_VERSION}; "
            f"got {declared!r}",
            declared=repr(declared),
        )
    return declared


def _major(version: str) -> int:
    return int(version.split(".")[0])


def _parts(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


class _SpecNotAMapping(RefusalError, ValueError):
    """A Design Spec document that is not a mapping."""


def migrate_to_current(data: dict) -> dict:
    """Return ``data`` at the schema version it actually reaches.

    Refuses specs from a different major version, and from a *later* minor version
    than this release knows; walks registered minor migrations forward otherwise.

    The returned ``anvilate_spec`` is the version the document reached, which for a
    document needing no migration is the one its author declared. It used to be
    overwritten with :data:`SCHEMA_VERSION` unconditionally, after the walk, which made
    the field an assertion instead of a record: a 1.1.0 document came back claiming to be
    1.3.0 with nothing having transformed it, and that claim travelled into the evidence
    bundle, where the spec section is the reproducibility record a reviewer reads. The
    same line would have covered a migration chain that stalled halfway.
    """
    if not isinstance(data, dict):
        # The same refusal `parse_spec` gives, because this is reachable on its own: it is
        # exported, and a caller migrating a document before validating it comes here first.
        raise _SpecNotAMapping(
            f"a spec is a mapping; got {type(data).__name__}. A JSON file that reads back "
            f"as a list, a bare string or null is the ordinary way to hand a tool the "
            f"wrong file, and the answer to it is a sentence",
            remedies=(
                Remedy(
                    action="replace",
                    subject="data",
                    source="the Design Spec document, read as a YAML or JSON mapping",
                ),
            ),
        )

    # A document that declares nothing is read as the current version, and that is a
    # deliberate residual rather than an oversight: the directory sweep's recognition rule is
    # "ask the loader", `examples/padeye.spec.yaml` is the versionless spec it is built on,
    # and `test_a_spec_that_declares_no_version_is_screened_by_a_sweep_and_a_stray_file_is_not`
    # pins both. Requiring the field refuses seventeen documents this repository ships or
    # builds.
    #
    # **It is safe only while there are no migrations.** The moment one is registered below,
    # a versionless document silently skips it — it is already at the version the walk starts
    # from — and comes out screened under a schema nobody chose for it. That is the same
    # shape as the overwrite this docstring describes: a reader supplying the answer to its
    # own question. `test_the_versionless_default_is_only_safe_while_nothing_migrates` is the
    # tripwire, and it fails on the first registered migration rather than after the first
    # document is misread.
    declared = _require_version_text(data.get("anvilate_spec", SCHEMA_VERSION))
    if _major(declared) != _major(SCHEMA_VERSION):
        raise UnsupportedSchemaVersion(
            f"spec declares schema {declared}; this release supports major "
            f"version {_major(SCHEMA_VERSION)} (current {SCHEMA_VERSION})",
            declared=declared,
        )
    # A minor bump is backward compatible, not forward: a 1.3.0 reader is promised nothing
    # about a 1.9.0 document. Its new fields would be caught by `extra="forbid"` only if it
    # used them, so one that happens not to slips through — and this release cannot know
    # whether a later minor changed what an existing field MEANS. Refusing says so; the old
    # behaviour loaded it and relabelled it 1.3.0, which left no trace for a reviewer.
    if _parts(declared) > _parts(SCHEMA_VERSION):
        raise UnsupportedSchemaVersion(
            f"spec declares schema {declared}, which is later than this release knows "
            f"({SCHEMA_VERSION}). A minor version is backward compatible, not forward: "
            f"this build cannot tell whether {declared} changed the meaning of a field it "
            f"reads. Upgrade anvilate, or set anvilate_spec to {SCHEMA_VERSION} or below "
            f"once you have checked the document against it",
            declared=declared,
        )
    version = declared
    migrated = dict(data)
    while version != SCHEMA_VERSION and version in _MIGRATIONS:
        next_version, migration = _MIGRATIONS[version]
        migrated = migration(migrated)
        migrated["anvilate_spec"] = next_version
        version = next_version
    migrated["anvilate_spec"] = version
    return migrated
