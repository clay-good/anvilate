# Security

## Reporting a vulnerability

Open a [private security advisory](https://github.com/clay-good/anvilate/security/advisories/new).
Please do not open a public issue for a vulnerability.

Anvilate is pre-alpha and has no release cadence to promise against, so the honest
commitment is a narrow one: an acknowledgement within a week, and a fix or a written
decision not to fix before any public disclosure.

## What this tool touches

Anvilate reads engineering documents and writes engineering documents. It runs no
generated code, opens no network connection on any ordinary path, and is designed to be
run against files that arrived from somebody else — an RFQ sheet, a calibration
certificate, a QIF result.

Each row below is a property the suite holds, not a description of intent. The test named
is the one that fails if the property stops being true.

| Property | Held by |
| --- | --- |
| Every YAML document — spec files and the bundled datasets alike — is read with `yaml.safe_load`. No document can construct a Python object. | `tests/test_contract.py` sweeps the package for the unsafe loaders |
| The library never calls `eval`, `exec`, `pickle`, `subprocess` or `os.system`. | `tests/test_contract.py` |
| `anvilate.fetch` is the only module that may import a network client, and a new module importing `socket`, `urllib`, `http`, or a third-party client fails the build. | `test_fetch_is_the_only_module_that_imports_a_network_client` |
| Nothing fetches without the caller stating consent, and a fetch refuses before it reaches the transport. | `test_the_one_network_capable_path_refuses_before_it_reaches_the_transport` |
| A fetched payload's digest is verified on download **and on every later read**; a mismatch raises rather than being used. | `tests/test_fetch.py` |
| The whole screening path completes with the socket layer closed. | `test_the_golden_path_completes_with_the_socket_layer_closed` |
| An XML document from outside — a DCC or a QIF result — cannot read a file off the host through an external entity, and cannot hang the reader through entity expansion. | `test_a_malformed_certificate_is_refused_by_the_documented_exception`, `test_a_hostile_document_is_a_complaint_rather_than_a_read_or_a_hang` |
| No third-party dataset ships inside the package without a redistributable licence recorded against it. | `test_nothing_ships_inside_the_package_that_is_not_code_a_dataset_or_a_named_exemption` |

## What this tool is not

**Anvilate is a screening tool, and a screening result is not an engineering
disposition.** Every scorecard says so, and a check that could not run reports
`not_evaluated` rather than a pass — but no software property makes a design safe. A
licensed engineer signs the work.

The roadmap in [`openspec/specs/`](openspec/specs/) describes a natural-language front end
that will run a model over untrusted text. Its threat model is written down in
`openspec/specs/sandbox-security` and none of it is shipped. When it is, this page changes
with it.
