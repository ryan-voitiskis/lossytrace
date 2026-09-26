# Changelog

All notable changes to this project will be documented here.

## 0.1.0-rc.1 - 2026-09-27

- Add `lossytrace explain`, an offline guide to every current measurement and
  its limitations, without changing the analysis JSON or enabling verdicts.
- Record the codec-history direction review and external-baseline shortlist.
- Preserve the failed fixed Lossprint challenge: 317/381 positive detections
  and 53/336 benchmark-negative alerts; no detector, codec-family estimate or
  source-bitrate estimate is shipped.
- Separate byte-bound historical audit replay from current software regression.
- Add native RC packaging, reproducibility checks, packaged-binary smoke tests,
  dependency notices and exact unmodified MPL-covered dependency sources.
- Keep schema version 1, feature version 0 and public verdicts disabled.

## 0.1.0-alpha.1 - 2026-08-01

- Extract the verdict-free feature-version-0 measurement prototype.
- Add a standalone `lossytrace analyze` JSON interface.
- Preserve the controlled-transcode benchmark and research harness.
- Preserve exact-transform research source and record the v28-v33 stop gate.
- Explicitly keep all public provenance verdicts disabled.
