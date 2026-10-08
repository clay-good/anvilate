# The bundled datasets

Anvilate's open reference data ships inside this repository, in
[`src/anvilate/standards/data/`](../src/anvilate/standards/data/), and installs with the
package. There is no separate data repository: one product, one checkout. Each file is a
plain YAML table you can read without Anvilate.

## What a table holds

Every file opens with a `dataset` header, then its records:

```yaml
dataset:
  name: anvilate-washers-seed      # stable identifier
  version: "0.1.0"                 # bumped whenever the bytes change
  source: "ISO 7089 plain washer dimensions (normal series, 200 HV)"
  license: "CC0-1.0 (dimension values only; source standard not redistributed)"
  retrieved: "2026-07-08"          # when the values were read from the source
washers:
  ...
```

`name`, `version`, `license` and `retrieved` are required in every file. Records carry
their own citations where a value comes from somewhere more specific than the header.

## Using a table without Anvilate

```python
import yaml

table = yaml.safe_load(open("src/anvilate/standards/data/washers.yaml"))
print(table["dataset"]["license"], len(table["washers"]))
```

A test reads every file this way in an isolated interpreter and requires that it never
imports Anvilate.

## Versions are pins

A version means fixed bytes. `tests/dataset_versions.json` records the SHA-256 of each
file under each version it has had, and the suite fails if a file changes without a new
version. Every evidence bundle (`anvilate export`, MCP `export_artifact`) lists each
table's name, version, file and digest under `datasets`, so a data change is a visible
provenance change.

## Contributing a correction or a record

1. Edit the table. Cite the source for every value you add or change.
2. Keep the licence rule: values only, never a copyrighted source document. A source that
   may be read but not shipped belongs behind `anvilate fetch` instead.
3. Bump `dataset.version` (patch for a correction, minor for new records, major for a
   changed meaning or removed record) and set `retrieved` to the date you read the source.
4. Add the new version's digest to `tests/dataset_versions.json`; the failing test prints
   it. Keep the earlier versions' entries.
5. Run the suite.
