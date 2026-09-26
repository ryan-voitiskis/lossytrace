# Listening privacy-readiness audit - 2026-08-14

**Status:** the current response field surface and offline player are
data-minimized enough to inform a successor design, but the response data are
pseudonymous rather than de-identified and the operational privacy package is
not ready. Response storage, participant contact, recruitment, consent and
human collection remain unauthorized.

## Classification correction

The existing schema is titled `LossyTrace de-identified listening response
envelope`. Its `participant_id` is repeated across session and response
records, intentionally supporting listener-aware analysis. That stable linkage
means the dataset is pseudonymous research response data. The absence of names,
email addresses and other direct identifiers does not make linkable data
anonymous or de-identified.

The existing schema is preserved as historical score-blind preparation
evidence. Any operational successor must use accurate pseudonymous terminology
and must not silently relabel the current linkable structure.

## Structural audit

The deterministic audit found:

- a closed-world JSON Schema with 39 unique field names;
- no forbidden direct-identity, contact, payment, location, raw-IP, microphone
  recording or device-serial field;
- participant codes in both sessions and responses, preserving intentional
  cross-record linkage;
- no consent-version, consent-timestamp, withdrawal-code or withdrawal-cutoff
  field in the trial envelope;
- no network, cookie, browser-persistence or microphone API in the local
  qualification player; and
- public individual-response and small-cell release disabled.

Keeping consent and withdrawal linkage outside the trial envelope is the
correct structural direction, but those separate successor records do not yet
exist. The local player's offline behavior is a qualification property, not
evidence about a future deployed collection system.

## Unresolved operational controls

All ten required operational values remain deliberately unset:

1. responsible researcher and contact;
2. complaints or independent contact, if applicable;
3. governing organization and ethics/privacy basis;
4. eligibility jurisdiction and minimum age;
5. storage system, region, encryption, access and incident process;
6. raw and aggregate retention periods and deletion method;
7. withdrawal contact, code procedure and de-identification cutoff;
8. compensation, partial-session rule and payment operator;
9. minimum public aggregation cell size and suppression policy; and
10. protocol, software, consent, privacy and analysis version hashes.

The allocation-journal audit also still lacks frozen privacy ownership and
backup policy. It does not prove response atomicity, power-loss durability or
a deployment boundary.

## Next gate

A responsible human must resolve every operational value and approve a
successor package that:

- calls linkable response data pseudonymous;
- stores consent and the time-bounded withdrawal link separately from trial
  data;
- freezes storage, access, retention, deletion, incident, compensation and
  publication controls; and
- receives separate explicit storage and collection authorization.

This audit does not choose any value, provide ethics or legal approval,
authorize participant contact, recruitment, consent, response storage or
collection, satisfy human calibration, enable no-reference work, or change the
public CLI.

Two fresh report generations were byte-identical at SHA-256
`fd900bdf474124d154c10565bbfcec4cbb345bb2290dbb0bb868a101e168d89a`.
The report binds plan SHA-256
`b8c9b10568dfd04b8a8ac1c1b0d2012204aa336dd53c9d46e12c6590e2b9f074`
and implementation SHA-256
`502880fbe8e26dfd29acdac2d23527cc6b77c8ff5dabf903e34828373ed0bd5e`.

Machine-readable artifacts:

- [`privacy audit plan`](../../benchmarks/perceptual-degradation-v1/listening-privacy-readiness-audit-plan.json)
- [`privacy readiness report`](../../research/toolchains/evidence/perceptual-degradation-listening-privacy-readiness-20260814-001.json)
- [`deterministic audit`](../../scripts/perceptual_degradation_listening_privacy_readiness.py)
- [`mutation tests`](../../scripts/tests/test_perceptual_degradation_listening_privacy_readiness.py)
