# Verified MP3 successor research

Run ID:
`audio-integrity-verified-mp3-successor-research-20260731-001`

This cycle begins after the frozen `conservative-two-grid-edge-v28` candidate
failed its one-use MUSDB18-HQ external-transfer gate with three PCM low-pass
false positives. MUSDB18-HQ and every earlier public, SQAM, and retained corpus
are now observed development evidence. They may be used to diagnose and
develop a materially different successor, but must never be described as
untouched validation again.

The v29 research direction keeps the conservative MP3 and Vorbis discovery
grids but replaces the loose MP3 aggregate decision with a second,
multi-candidate confirmation pass. Discovery scans ten separated one-frame
regions. Confirmation tests only the discovered phase neighbourhoods against
24 control phases over up to four separated sixteen-frame regions. A
confirmation is omitted when fewer than three complete measurable regions
remain. A future policy must require both discovery and confirmation evidence
before the MP3 branch can fire.

The observed development screen now covers 3,404 unique cases from 321 source
groups: 990 negatives and 2,414 positives. The development policy uses an
exclusive MP3 confirmation median threshold of 3.0 and requires the confirmed
phase to land within the discovery candidate radius. It produced zero false
positives across 796 supported negatives, passed every predeclared scoped
recall class at 90% or better, and had zero mismatches across 48 public PCM,
70 SQAM AAC, and 30 MUSDB AAC invariant groups. The largest phase-matched
supported-negative MP3 confirmation median was 2.0659048331, leaving a
0.9340951669 observed margin below the development threshold.

These are post-transfer development measurements, not validation. Candidate
thresholds are not frozen and the observed screen does not open or pass
either external gate. Transform-only p95 timing of 129.1985 ms is diagnostic.
The separate paired isolated-process audit reused the predeclared 16-case
public stratification and three alternating repetitions per mode. V29 added
1.5353% median and 3.8123% p95 wall time, and 5.8241% p95 peak RSS. It passes
the predeclared 10% p95 runtime ceiling as development performance evidence.

The canonical observed evaluation is
`observed-v29-policy-evaluation.json` (SHA-256
`c807190b0700177efc80cd4685c6b72bacd47b91166182bed814c9404013441c`).
The paired performance report is `performance-public-stratified-v29.json`
(SHA-256
`e660eb777dc0d99a30b9c36a569b0aee570d29aec42bb0f020cabbd3647cf129`).
The superseded evaluator output with the archived-support reconstruction bug
is retained under `superseded/` (SHA-256
`43dd0b28778257542468e71e015f877580f47864977d1bfff6b711ca07e3ab5e`)
and must not be used as evidence. A compact, independently sourced and
provenance-locked corpus will be acquired and sealed before the next one-use
gate.

The separate release-held-out corpus remains sealed. Feature version `0`,
Stratum cache schema `21`, and the disabled public verdict remain unchanged.
No public verdict or release claim is permitted unless a future frozen
candidate passes the new external-transfer gate and the separate release gate.
