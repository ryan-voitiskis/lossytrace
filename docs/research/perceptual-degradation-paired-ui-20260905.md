# Silent paired-rating UI integration — 2026-09-05

Status: synthetic UI implemented, exercised in a real browser and connected to
the frozen paired-rating processor. This is not a listening player: there is
no audio delivery, playback API, microphone access or participant collection.
The previous player and all predecessor protocols and evidence are unchanged.

## Implemented path

The [interface](../../research/listening-paired-ui/index.html) presents two empty
candidate grade fields. An arbitrary test choice must be locked before either
grade is available. Both current fields must contain a valid 1.0–5.0 grade in
tenths before submission. Equal grades are allowed. The choice stays locked;
grade revisions remain possible until submission. Submitted and explicitly
ended trials cannot be edited through the interface. A second synthetic trial
starts with a fresh choice and empty fields.

The public fixture contains only the two generated assignment projections from
the [paired protocol](perceptual-degradation-paired-rating-protocol-20260905.md).
It contains no roles, condition recipe, source group, participant ID or metric
score. This structural concealment is not a cryptographic or double-blind
qualification: these are public software fixtures, not real stimuli.

The page exports an ephemeral event record, not a correctness label or SDG.
The [Python adapter](../../scripts/perceptual_degradation_paired_ui.py) verifies
the exact generated assignment and asset bindings, replays the events through
the frozen Python reducer and resolves candidate roles on the analysis side.
Unknown, duplicate or mismatched assignments, observed-data flags, injected
fields, invalid grades and incomplete submissions fail closed. No observed-file
command-line input or response-storage endpoint exists.

## Cleared-field correction

An event history can contain a valid grade that the interface user subsequently
clears. Looking only at the last valid grade event would misrepresent the final
field state. The interface therefore records `final_grade_ticks_by_position`
separately. Cleared, invalid or unaccepted final drafts are null. Every non-null
final grade must match an accepted grade event; a submitted pair cannot have a
null final field. Incomplete targets remain null and ineligible for paired
analysis, even if an earlier valid grade remains in their event history.

The old reducer is not modified. The UI adapter preserves its event history
while exposing the final accepted grade fields. In particular, it does not
silently assume a cleared hidden-reference grade is five or reuse a stale grade.

## Evidence and scope

The [deterministic parity report](../../research/toolchains/evidence/perceptual-degradation-paired-ui-synthetic-20260905-001.json)
replays the generated events through JavaScript and Python and is byte-identical
across two independent CLI invocations. JavaScript/Python unit checks cover 360
valid event prefixes and invalid types, ordering, fields and limits. These
checks verify event semantics, not DOM behavior or listening quality.

The separate [browser observation](../../research/toolchains/evidence/perceptual-degradation-paired-ui-browser-observed-20260905-001.json)
records actual controls exercised with Playwright CLI 0.1.19 in an isolated,
headed Chromium-family browser reporting Chrome major version 152. The complete
two-trial browser event records exactly matched the declared test fixtures and
produced signed differences +0.6 and -0.6 in Python. Both choices were incorrect
under their assignment roles and were retained. A separate cleared-grade
termination replay preserved the final missing grade and a null paired target.
All values were arbitrary automation inputs, not human ratings.

Browser checks also covered initial defaults, choice locking, single-grade,
cleared and out-of-range drafts, post-submission disabling, trial reset and
reload clearing. Full-page screenshots were inspected at actual 390×844 and
1280×900 viewports without horizontal overflow. The inspected request inventory
contained only loopback static-asset GETs; the browser console reported zero
errors and warnings. The browser session and temporary server were closed.
Screenshots and transient browser artifacts remain outside the public file set.

The browser observation is manually observed QA bound to the tested source
hashes. CI verifies those bindings and deterministic event semantics; it does
not rerun browser interaction. Browser binary closure, timing, accessible-use
qualification, atomic persistent submission, consent, retention, secure
concealment and audio-delivery validation are not established by this work.

## Reproduction and next research boundary

Python and Node.js are required for the deterministic integration checks:

```sh
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_paired_ui.py'
python3 scripts/perceptual_degradation_paired_ui.py --synthetic
```

The [UI plan](../../benchmarks/perceptual-degradation-v1/paired-rating-ui-plan.json)
allows only silent synthetic browser testing. Its static assets may be served
from their dedicated directory on loopback for that purpose; they must not be
used as a participant collection interface. No threshold, materiality decision,
paired-target variance, human calibration or oracle conclusion is selected.
The next statistical work must address paired-target uncertainty, population
and per-source estimands, missingness and nonmateriality evidence before a
real study is authorized. Source qualification and all original oracle and
grouped-transfer prerequisites remain open.
