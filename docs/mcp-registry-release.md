# Publishing the MCP server

Each GitHub release publishes `server.json` to the official MCP Registry. The registry
entry installs the matching PyPI package and runs its `anvilate-mcp` console script over
stdio.

## Release order

1. Set the same version in `pyproject.toml`, `server.json`, the package entry in
   `server.json`, and its `anvilate==<version>` runtime argument.
2. Build and publish that exact version to PyPI.
3. Create and publish the matching `vX.Y.Z` GitHub release.
4. Confirm the **Publish MCP registry metadata** workflow passes.

The workflow checks every version before it authenticates. It then waits up to 5 minutes
for the exact PyPI version, downloads the pinned MCP publisher, verifies its SHA-256 digest,
validates `server.json`, authenticates with GitHub OIDC, and publishes the entry. No registry
token is stored in the repository.

If PyPI propagation or a registry outage makes the release run fail, rerun the workflow
manually and supply the existing release tag. The workflow checks out that tag, so a retry
cannot silently publish metadata from a newer commit.

The registry namespace is `io.github.clay-good/anvilate`. Its ownership proof is the
`mcp-name` marker in the root README. Keep that marker synchronized with `server.json`.
