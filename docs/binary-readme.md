# LossyTrace release candidate

This is an experimental **verdict-free audio inspector**, not a detector of
prior lossy encoding. It does not estimate historical codec or bitrate,
certify never-lossy provenance, or judge audible quality.

## Use

After verifying this archive against the release's `SHA256SUMS`, extract it
and run the native executable:

```sh
./lossytrace --version
./lossytrace explain
./lossytrace analyze /path/to/track.flac --pretty
./lossytrace analyze /path/to/track.flac --max-seconds 0 --pretty
```

The default analysis limit is 120 seconds. Zero requests the complete file
and can require substantial memory and computation. Audio is opened read-only;
reports go to standard output. The executable does not fetch models or make
network requests. Nothing should be deleted or retagged based on these
experimental measurements.

See [inspection-guide.md](inspection-guide.md) for every field, support limits,
mono downmixing, null values and alternative explanations. Read
[release-notes.md](release-notes.md) for the failed detector screen and scope.

## Platforms and provenance

Select `aarch64-apple-darwin` for Apple Silicon macOS, or
`x86_64-unknown-linux-gnu` for Linux x86-64. Native release smoke tests run on
macOS 15 and Ubuntu 24.04 respectively. Other OS versions, Intel Macs, Windows
and other architectures are not qualified by this RC. macOS binaries are not
Developer-ID signed or notarized; organization/device security policy may
prevent execution. Building from the pinned source is an alternative, not a
reason to disable your security controls.

`build-info.json` identifies the source commit, compiler and executable hash.
The source, benchmark recipes and aggregate research records are available at
[the LossyTrace repository](https://github.com/ryan-voitiskis/lossytrace).
Private corpora and per-file research predictions are not distributed.

## Notices and dependency source

LossyTrace's own code is MIT OR Apache-2.0. Read `THIRD_PARTY_NOTICES.md` and
`dependency-inventory.json` for dependency terms, source URLs and checksums.
Exact unmodified MPL-covered source archives are included in `covered-source/`;
the MPL text is in `licenses/MPL-2.0.txt`. Rust standard-library notices are
under `licenses/rust/`. No Lossprint model or inference implementation is
included.
