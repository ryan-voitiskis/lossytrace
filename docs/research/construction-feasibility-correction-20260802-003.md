# Factorial benchmark v2 construction-feasibility correction 003

Date: 2026-08-02

State: audit recipe `004` is frozen before new source-header inspection; no
waveform sample, benchmark audio, feature, score, or unopened label was read

## Trigger

Construction-feasibility recipe `003` correctly stopped because 11 groups in
fractional-assignment recipe `003` could not meet a frozen transform minimum.
Its retained public result has SHA-256
`2791c0e5c64bffae89412418693295be7b0ddd4ce8ad18eb323106bbe09bd3b4`.

The separately frozen and replayed fractional-assignment recipe `004` applies
that same minimum only as a Boolean group-transform eligibility predicate.
Its private assignment has SHA-256
`46039d6fc22a6764daf81684d109e43a9f96b97af7d85e99258b1efe0449c5bb`,
and its path-free public result has SHA-256
`05fa5c09c90a2fd8404c8afa08f7515032c1f3633cc7bfcc17e58526f984a25d`.

## Corrected audit binding

Construction-feasibility recipe `004` changes only the assignment binding and
the audit ID. It also makes the existing public-assignment-result binding an
explicit command input and verifies that it names the exact private
assignment. The source allocation, candidate index, factor levels, source
archives, provider windows, FFprobe binary, header fields, lossless codec
scope, 12-second cap, transform minima, reporting boundary, one-worker limit,
and 15 GiB work-volume reserve remain unchanged.

The audit must reverify every source archive and probe all 793 exact selected
source headers twice. It may inspect only codec name, sample rate, channel
count, duration timestamp, and time base. It must stop on any assigned trim
input below 500 ms, any assigned duration-prefix input below three seconds, or
any unsupported channel count. Waveform decoding, reassignment, padding,
feature computation, score opening, and benchmark-audio construction remain
forbidden.

## Disposition

Recipe `004` must be committed before either replay. Byte-identical passing
audits would authorize only a separately frozen construction recipe, not audio
generation under this audit plan.
