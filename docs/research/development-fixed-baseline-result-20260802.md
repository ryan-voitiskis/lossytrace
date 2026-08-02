# Factorial benchmark v2 fixed-baseline result

Date: 2026-08-02

**Decision:** retain both fixed systems as failure probes, not candidates. The
published Cannam rule is highly sensitive but source- and bandwidth-dependent;
LossyTrace feature version 0 contains no measurement that meets the frozen
paired direction gate. Do not tune either system from these results, construct
a feature-v0 classifier, or open encoder/external transfer.

## Frozen scope

The
[`development-baseline preregistration`](development-baseline-preregistration-20260802.md)
was committed before either system decoded a benchmark waveform. It fixes the
9,653-case mechanism-development population: 4,988 controlled positives and
4,665 negatives from 527 source groups and six source domains. Exact decoded
PCM duplicates collapse to 7,701 analysis units; every one of the 9,513
distinct retained artifact representations is still scored so that wrapper
invariance can be checked.

Both runs passed exact wrapper invariance for all 1,398 PCM identities with
multiple retained wrappers. The 24 observationally identical factorial
aliases were collapsed under the frozen identity-first attribution rule. No
threshold, support rule, feature, population, or aggregation changed after a
score was opened. Encoder-transfer features and scores remain sealed;
external transfer remains negative-only; public verdicts remain disabled.

## Cannam fixed rule

The run replayed `cannam/vamp-lossy-encoding-detector` revision
`7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b` with its published weights and
fixed rule: a window is positive at `cf >= 0.5`, and a file is positive when
at least 25% of windows are positive. The reported score is the positive-window
fraction, not a probability.

| Population or comparison | Result |
| --- | ---: |
| Controlled-positive recall, factorial cells | 4,580/4,988 = 91.82% |
| Negative false-positive rate, factorial cells | 2,988/4,665 = 64.05% |
| Balanced accuracy, factorial cells | 63.88% |
| Selected-population accuracy | 64.82% |
| Selected-population precision | 60.52% |
| Controlled-positive recall, unique PCM | 4,556/4,964 = 91.78% |
| Negative false-positive rate, unique PCM | 1,840/2,737 = 67.23% |
| Negative source groups with any alert | 488/527 = 92.60% |
| Positive source groups with any detection | 527/527 = 100.00% |

The matched-reference statistic is much weaker than the headline recall. Only
246/527 source groups had a positive median positive-minus-reference score;
224 were tied and 57 reversed. The positive direction rate was 46.68%, its
one-sided 95% Wilson lower bound was 43.13%, and the median delta was zero.
This is far below the descriptive 90% direction and 85% lower-bound gate.

The domain split shows why. DEMAND/MAESTRO and MUSDB had positive paired
direction in 97.22% and 91.33% of source groups, but NSynth test had 0/53 and
NSynth train had 1/200 positive groups. At the case level, false-positive rates
were 29.16% and 32.17% in the first two domains, versus 99.68% in each NSynth
domain. A source-domain classifier can therefore look strong while the same
history comparison disappears or reverses within another source family.

Codec recall was also not mechanism stability: AAC-LC reached 76.34%, MP3
96.63%, Opus 96.79%, and Vorbis 97.60%, while the paired positive-direction
rates by codec were only 33.40%, 49.91%, 26.94%, and 51.99%. The rule also
alerted on 160/160 genuine-PCM 16 kHz low-pass controls, 112/120 32 kHz
resampling round trips, and 2,140/3,385 unmodified PCM references. Its
high-frequency evidence is useful for describing bandwidth, but it is not a
stable trace of lossy history.

This independently confirms the earlier 5,280-case v1 failure atlas rather
than merely repeating it. The selected populations differ, yet the central
failure persists: v1 had 67.53% negative-case false positives and alerts in
545/597 negative source groups; v2 has 64.05% and 488/527. The paired v2
design now shows directly that the detector's apparent signal is dominated by
source/content dependence.

## Feature-version-0 measurements

Feature version 0 remained descriptive. No classifier, threshold, ensemble,
or support filter was fitted. Each result below is the median direction of the
positive-minus-exact-matched-reference delta per source group.

| Measurement | Supported groups | Positive / zero / negative | Positive direction | One-sided 95% lower | Median delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| spectral edge, Hz | 269 | 236 / 10 / 23 | 87.73% | 84.06% | +559.863 Hz |
| spectral-edge drop | 269 | 228 / 0 / 41 | 84.76% | 80.81% | +0.879 dB |
| transform alignment | 519 | 374 / 6 / 139 | 72.06% | 68.71% | +0.005241 |
| small-coefficient fraction | 519 | 340 / 28 / 151 | 65.51% | 62.01% | +0.003906 |
| edge persistence | 269 | 127 / 3 / 139 | 47.21% | 42.26% | -0.000724 |
| median active-bin fraction | 527 | 216 / 156 / 155 | 40.99% | 37.52% | 0 |
| spectral-hole ratio | 519 | 208 / 26 / 285 | 40.08% | 36.60% | -0.000007 |
| isolated-hole ratio | 519 | 208 / 26 / 285 | 40.08% | 36.60% | -0.000007 |
| edge spread | 269 | 107 / 24 / 138 | 39.78% | 34.99% | -2.930 Hz |
| band rupture | 519 | 135 / 99 / 285 | 26.01% | 22.97% | -0.000252 |

No measurement meets both parts of the frozen gate. Spectral-edge height is
the closest, but it is supported in only 269/527 groups, misses the 90%
direction requirement, and misses the 85% lower-bound requirement. Its domain
breakdown is not uniform: MUSDB reaches 93.33% direction with an 89.16% lower
bound, while NSynth train reverses to 36.36% direction and a -145.35 Hz median
delta. The related edge-drop measurement ranges from 100% direction in the
small DEMAND/MAESTRO subset to 33.33% in NSynth test. Transform alignment has
broader support but ranges from 91.67% direction in DEMAND/MAESTRO to 62.50%
in the private full-mix domain, with every domain lower bound below 85%.

These observations are valuable mechanism clues, but not candidates. They say
that lossy codecs often move a detectable spectral boundary or transform
statistic within some content domains. They do not show a source-independent
historical residue, and they provide no basis for choosing a threshold from
this consumed development population.

## Consequence for the research program

The fixed-baseline stage remains incomplete until the preregistered naive and
random-high-frequency-mask Koops-style CRNN folds and the retained explainable
controls are frozen. The learned comparison is now especially informative:
if masking reduces domain-fold collapse without creating paired stability, it
will demonstrate a better shortcut control rather than history
identifiability. If it does create stable paired separation across every
source-domain fold, it will justify a more focused mechanism study, not a
verdict.

The two possible new physical representations remain gated. They may be
implemented only after the full baseline failure atlas is frozen and only if
the preregistered paired discovery conditions warrant them. Nothing in these
fixed results alone authorizes a representation, encoder-transfer opening, or
external positive-score opening.

## Reproducibility commitments

| Artifact | SHA-256 |
| --- | --- |
| development-baseline plan | `9d483ec87365aa4253fa5997458f2fab604b27f029ce42ca20d917f79caa51b0` |
| private analysis manifest | `0937dfec3f9d5d203ec3d8c1700a3ae947226999e72a379b226c4c825fab96f9` |
| Cannam private raw report | `545765e947f5b467197c4544ea44fab1ca218d4087c20a58dfd4d968357296b7` |
| Cannam path-free aggregate | `6531911c06f6ceaa7567e16a24bfba135b9aeabedbd6b15b1063d17d79de20ff` |
| feature-v0 private raw report | `e578f321f3118da055de3835b026e72c1ca61b0ba868a3f89ef08e16463400d2` |
| feature-v0 path-free aggregate | `62bd6ce9c6f104b91b682ce07216760471cab7c87cded0016cc8153577a1132a` |
| shared analyzer | `e1ea36124d12b8692988efd18eb8864ab9aa7d33190b5b8a79eb145096cc658e` |
| detector plugin | `9e989b81061fcc5b6186f7a0ed2534400f6b8de1e1ee711a1f76aee1c547c9e6` |
| Vamp host | `a9c197e1d10a4d03748ad2b9a3712013cf9ac8c46dd797dbba44f7f809904a64` |

The committed aggregates contain only path-free counts and summaries. Private
case rows, source-group identities, audio hashes, paths, audio, logs, and
partials remain outside Git.
