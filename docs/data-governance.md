# Data governance

## Repository boundary

The public repository may contain:

- source code and deterministic transform recipes;
- public-source registries containing licensing and provenance metadata;
- content hashes and corpus fingerprints;
- small synthetic fixtures created by the project; and
- aggregate or sanitized research reports.

It must not contain copyrighted corpus audio, privately supplied music,
credentials, private manifests, machine-specific absolute paths, model caches,
or per-case output that exposes source locations.

## Local corpus store

Real-audio datasets are retained outside Git. On macOS, the canonical store is
`~/Library/Application Support/lossytrace/benchmarks/audio-integrity-v1/`.
Other platforms should use their normal per-user application-data directory.

Every retained corpus must have a manifest with provenance, license or terms,
generation commands, encoder versions, source-group identity, and SHA-256
fingerprints. Controlled lossy-to-lossless outputs remain linked to their PCM
parents.

## Publication check

Before any push or release:

1. enumerate all tracked files;
2. reject known audio extensions and files above the documented size budget;
3. scan for credentials and absolute home-directory paths;
4. verify that tracked manifests contain no private source locations; and
5. inspect the exact staged diff.
