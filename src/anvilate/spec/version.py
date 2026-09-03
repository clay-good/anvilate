"""Schema versioning and migration.

The Spec IR schema is semantically versioned. Anvilate loads any spec whose
major version it supports, applying registered migrations to bring older minor
versions up to the current schema. A spec from an unsupported major version is
refused rather than silently misread.
"""

from __future__ import annotations

from collections.abc import Callable

from .ir import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION", "UnsupportedSchemaVersion", "migrate_to_current"]

# Migrations transform a raw dict from one version to the next. Register the
# next entry here when the schema gains a minor version.
_MIGRATIONS: dict[str, tuple[str, Callable[[dict], dict]]] = {}


class UnsupportedSchemaVersion(ValueError):
    """A spec declares a schema version this release cannot load."""


def _major(version: str) -> int:
    return int(version.split(".")[0])


def _parts(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


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
    declared = data.get("anvilate_spec", SCHEMA_VERSION)
    if _major(declared) != _major(SCHEMA_VERSION):
        raise UnsupportedSchemaVersion(
            f"spec declares schema {declared}; this release supports major "
            f"version {_major(SCHEMA_VERSION)} (current {SCHEMA_VERSION})"
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
            f"once you have checked the document against it"
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
