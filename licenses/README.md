# License text provenance

`MPL-2.0.txt` is the Mozilla Public License 2.0 text supplied by
[Symphonia at revision 6d533f2](https://github.com/pdeljanov/Symphonia/blob/6d533f26150953a882a6a111ebd13f0abf7129d5/LICENSE),
the upstream revision recorded by the pinned 0.5.5 crates. Trailing whitespace
and the final newline are normalized; license wording is unchanged.

Binary RC bundles additionally contain dependency copyright/license notices
extracted from registry archives whose SHA-256 values match `Cargo.lock`.
The exact unmodified archives for all included MPL-2.0 Symphonia crates are
provided under `covered-source/`. The package's `THIRD_PARTY_NOTICES.md`
explains where they are and that their source remains governed by MPL-2.0.
This implements the source-availability and notice requirements described in
[MPL 2.0 sections 3.1–3.4](https://www.mozilla.org/en-US/MPL/2.0/), without
altering upstream source notices or imposing additional source restrictions.

The Rust standard-library copyright report and license texts are taken from
the pinned build toolchain. Target-specific Cargo normal/build dependencies
are listed separately from these standard-library notices. The broader
CycloneDX SBOM includes development and target-conditional dependencies and
must not be read as a list of every library linked into one binary.

Lossprint source, binaries and model weights are not redistributed by this RC.
