# Security

## Reporting a vulnerability

Open a [private security advisory](https://github.com/clay-good/anvilate/security/advisories/new).
Please do not open a public issue for a vulnerability.

Anvilate is pre-alpha and has no release cadence to promise against, so the honest
commitment is a narrow one: an acknowledgement within a week, and a fix or a written
decision not to fix before any public disclosure.

## What this tool touches

Anvilate reads engineering documents and writes engineering documents. It runs no
generated code and opens no network connection unless a caller consents to a dataset fetch
or explicitly invokes a loopback-only local-model adapter. It is designed to be run against
files that arrived from somebody else — an RFQ sheet, a calibration certificate, a QIF
result.

Each row below is a property the suite holds, not a description of intent. The test named
is the one that fails if the property stops being true.

| Property | Held by |
| --- | --- |
| Every YAML document — spec files and the bundled datasets alike — is read with `yaml.safe_load`. No document can construct a Python object. | `tests/test_contract.py` sweeps the package for the unsafe loaders |
| The library never calls `eval`, `exec`, `pickle`, `os.system` or any other way of running what it read — the `os` exec/spawn/fork family, `runpy`, `pty`, `ctypes`. The sole `subprocess` import is `_mcp_tasks.py`, whose fixed argv launches Anvilate's own worker; no document field chooses an executable or command argument. Calls are judged on what they **resolve** to, so `from os import system` is the same finding as `os.system`. | `test_the_library_runs_nothing_it_reads`, `test_the_task_worker_is_the_only_process_boundary`, and `test_the_resolver_reads_a_call_written_the_other_way` |
| `anvilate.fetch` and `anvilate.compilation` are the only modules that may import a network client: the former requires fetch consent, and the latter accepts only explicitly invoked loopback Ollama or llama.cpp origins. A new module importing any of twenty-three stdlib or third-party clients fails the build. | `test_only_explicit_transports_import_a_network_client` |
| The package's third-party imports are exactly the dependencies `pyproject.toml` declares, so a client nobody thought to blocklist fails too. | `test_the_packages_third_party_imports_are_exactly_its_declared_dependencies` |
| No module is imported by a literal string handed to `import_module`, which would carry a client past every sweep that reads import statements. | `test_no_module_is_imported_by_a_name_assembled_at_run_time` |
| Nothing fetches without the caller stating consent, and a fetch refuses before it reaches the transport. | `test_the_one_network_capable_path_refuses_before_it_reaches_the_transport` |
| Constructing the local-model adapter makes no request, its endpoint must be loopback, and the complete two-pass compile runs under the closed socket layer when an embedded transport is supplied. | `test_local_model_compilation_can_run_with_the_socket_layer_closed`, `tests/test_compilation.py` |
| A fetched payload's digest is verified on download **and on every later read**; a mismatch raises rather than being used. | `tests/test_fetch.py` |
| The whole screening path completes with the socket layer closed. | `test_the_golden_path_completes_with_the_socket_layer_closed` |
| An XML document from outside — a DCC or a QIF result — cannot read a file off the host through an external entity, and cannot hang the reader through entity expansion. | `test_a_malformed_certificate_is_refused_by_the_documented_exception`, `test_a_hostile_document_is_a_complaint_rather_than_a_read_or_a_hang` |
| No third-party dataset ships inside the package without a redistributable licence recorded against it. | `test_nothing_ships_inside_the_package_that_is_not_code_a_dataset_or_a_named_exemption` |

## What this tool is not

**Anvilate is a screening tool, and a screening result is not an engineering
disposition.** Every scorecard says so, and a check that could not run reports
`not_evaluated` rather than a pass — but no software property makes a design safe. A
licensed engineer signs the work.

The roadmap in [`openspec/specs/`](openspec/specs/) describes a complete natural-language
front end around the model adapter now shipped. Its remaining threat model is written down
in `openspec/specs/sandbox-security`; the loopback and bounded-response controls implemented
so far are the start, not a claim that the whole front end exists.
