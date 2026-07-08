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


def migrate_to_current(data: dict) -> dict:
    """Return ``data`` migrated to the current schema version.

    Refuses specs from a different major version; walks registered minor
    migrations forward otherwise.
    """
    declared = data.get("anvilate_spec", SCHEMA_VERSION)
    if _major(declared) != _major(SCHEMA_VERSION):
        raise UnsupportedSchemaVersion(
            f"spec declares schema {declared}; this release supports major "
            f"version {_major(SCHEMA_VERSION)} (current {SCHEMA_VERSION})"
        )
    version = declared
    migrated = dict(data)
    while version != SCHEMA_VERSION and version in _MIGRATIONS:
        next_version, migration = _MIGRATIONS[version]
        migrated = migration(migrated)
        migrated["anvilate_spec"] = next_version
        version = next_version
    migrated["anvilate_spec"] = SCHEMA_VERSION
    return migrated
