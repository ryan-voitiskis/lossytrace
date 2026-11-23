"""Research-only primary metrics for one frozen policy on a fixed group allocation."""

from collections import Counter

import numpy as np

from music_verdict_calibration import CASES, CONDITIONS, STATES
from music_verdict_study import PARTITIONS, exact_lower, exact_upper


OUTCOMES = ("likely_lossy_derived", "no_evidence_detected", "inconclusive", "unsupported", "missing")
FLAG, NO_EVIDENCE, INCONCLUSIVE, UNSUPPORTED, MISSING = range(len(OUTCOMES))


def _counts(values):
    totals = np.bincount(values.ravel(), minlength=len(OUTCOMES))
    return dict(zip(OUTCOMES, map(int, totals)))


def _case_rates(values):
    counts = _counts(values)
    number = values.size
    return {
        "cases": number,
        "outcomes": counts,
        "flag_rate": counts["likely_lossy_derived"] / number,
        "no_evidence_rate": counts["no_evidence_detected"] / number,
        "inconclusive_rate": counts["inconclusive"] / number,
        "decision_coverage": (counts["likely_lossy_derived"] + counts["no_evidence_detected"]) / number,
    }


def _bounds_by_group(decisions):
    groups = len(decisions)
    negatives = decisions[:, 0]
    alerted = np.any(negatives == FLAG, axis=1)
    hits = int(alerted.sum())
    unresolved = int((~alerted & np.any(negatives == MISSING, axis=1)).sum())
    # With a lost output, either assignment is possible. An explicit unsupported
    # decision is observed and did not alert. Both stay in the class denominator.
    false_alerts = {
        "groups": groups,
        "known_alerts": hits,
        "unresolved_groups": unresolved,
        "upper_95_observed": exact_upper(hits, groups),
        "upper_95_if_all_unresolved_alerted": exact_upper(hits + unresolved, groups),
    }
    detections = {}
    for index, state in enumerate(STATES[1:], start=1):
        flagged = (decisions[:, index] == FLAG).sum(axis=1)
        successes = int((flagged >= 5).sum())
        detections[state] = {
            "groups": groups,
            "groups_with_at_least_five_flags": successes,
            "lower_95": exact_lower(successes, groups),
        }
    return false_alerts, detections


def _bootstrap(group_brier, group_bin_residual, strata):
    # Resample independent components within their preallocated production strata.
    # All cases from a selected component travel together.
    if any(count < 2 for count in Counter(strata).values()):
        return None
    rng = np.random.default_rng(20260927)
    n = len(strata)
    strata = np.asarray(strata)
    weights = np.zeros((1000, n), dtype=np.int32)
    for label in np.unique(strata):
        indexes = np.flatnonzero(strata == label)
        size = len(indexes)
        weights[:, indexes] = rng.multinomial(size, np.full(size, 1 / size), size=len(weights))
    brier = (weights @ group_brier) / n
    ece = np.abs(weights @ group_bin_residual).sum(axis=1) / n
    return {
        "replicates": len(weights),
        "seed": 20260927,
        "brier_95_percentile": np.quantile(brier, [.025, .975]).tolist(),
        "ece_95_percentile": np.quantile(ece, [.025, .975]).tolist(),
    }


def _calibration(probabilities, strata):
    n = len(strata)
    truth = np.zeros((len(STATES), len(CONDITIONS)))
    truth[1:] = 1
    valid = np.isfinite(probabilities)
    report = {
        "expected_cases": probabilities.size,
        "scored_cases": int(valid.sum()),
        "brier": None,
        "ece_10": None,
        "bins": [],
        "group_bootstrap": None,
    }
    # Never renormalize the complete-case subset to manufacture a full-case metric.
    if not valid.all():
        return report

    # The complete design gives every group the same primary case matrix.
    weights = np.where(truth == 1, .5 / truth.sum(), .5 / (truth == 0).sum())
    group_brier = np.sum(weights * (probabilities - truth) ** 2, axis=(1, 2))
    residual = np.empty((n, 10))
    bins = np.minimum((10 * probabilities).astype(int), 9)
    for i in range(10):
        mask = bins == i
        mass = np.sum(mask * weights)
        predicted = np.sum(mask * weights * probabilities)
        observed = np.sum(mask * weights * truth)
        residual[:, i] = np.sum(mask * weights * (probabilities - truth), axis=(1, 2))
        report["bins"].append({
            "index": i, "cases": int(mask.sum()), "balanced_mass": float(mass / n),
            "mean_probability": float(predicted / mass) if mass else None,
            "encoded_fraction": float(observed / mass) if mass else None,
        })
    report["brier"] = float(group_brier.mean())
    report["ece_10"] = float(np.abs(residual.mean(axis=0)).sum())
    report["group_bootstrap"] = _bootstrap(group_brier, residual, strata)
    return report


def evaluate(policy, allocation, scores, *, partition):
    """Summarize one model. Caller binds policy, file logits and independent allocation.

    allocation maps every expected component ID to its production stratum.
    scores maps component IDs to {(state, condition): logit or "unsupported"}.
    An absent component or cell is counted as missing. No fitting is performed.
    """
    if partition != "evaluation":
        raise ValueError("evaluation partition required")
    if not isinstance(allocation, dict) or not allocation or not all(
        isinstance(x, str) and x.strip() for pair in allocation.items() for x in pair
    ):
        raise ValueError("expected a nonempty group to stratum allocation")
    if not isinstance(scores, dict) or scores.keys() - allocation.keys():
        raise ValueError("unexpected score inventory")
    ids = sorted(allocation)
    strata = [allocation[group] for group in ids]
    shape = (len(ids), len(STATES), len(CONDITIONS))
    decisions = np.full(shape, MISSING, dtype=np.uint8)
    probabilities = np.full(shape, np.nan)
    for i, group in enumerate(ids):
        cells = scores.get(group, {})
        if not isinstance(cells, dict) or cells.keys() - set(CASES):
            raise ValueError("unexpected evaluation case")
        for (state, condition), value in cells.items():
            index = (i, STATES.index(state), CONDITIONS.index(condition))
            if isinstance(value, str) and value == "unsupported":
                decisions[index] = UNSUPPORTED
            else:
                outcome, probability = policy.score(value)
                decisions[index] = OUTCOMES.index(outcome)
                probabilities[index] = probability

    false_alerts, detections = _bounds_by_group(decisions)
    negative = _case_rates(decisions[:, 0])
    positive = _case_rates(decisions[:, 1:])
    calibration = _calibration(probabilities, strata)
    by_stratum = {}
    stratum_labels = np.asarray(strata)
    for label, size in sorted(Counter(strata).items()):
        subset = decisions[stratum_labels == label]
        controls = subset[:, 0]
        alerts = np.any(controls == FLAG, axis=1)
        possible_alerts = np.any((controls == FLAG) | (controls == MISSING), axis=1)
        detection = float(np.mean(subset[:, 1:] == FLAG))
        by_stratum[label] = {
            "groups": size,
            "observed_group_alert_rate": float(alerts.mean()),
            "maximum_group_alert_rate": float(possible_alerts.mean()),
            "encoded_detection_rate": detection,
            "negative": _case_rates(controls),
            "positive": _case_rates(subset[:, 1:]),
            "meets_stratum_limits": bool(possible_alerts.mean() <= .05 and detection >= .5)
            if size >= 30 else None,
        }

    # Positive predictive value if only class prevalence changes. No individual
    # posterior is inferred. Missing outputs prevent a complete sensitivity table.
    flag_precision = {}
    if not (decisions == MISSING).any():
        for prior in (.01, .1, .5):
            true_flags = prior * positive["flag_rate"]
            flags = true_flags + (1 - prior) * negative["flag_rate"]
            flag_precision[str(prior)] = true_flags / flags if flags else None

    eligible_stratum_checks = [s["meets_stratum_limits"] for s in by_stratum.values() if s["groups"] >= 30]
    return {
        "groups": len(ids),
        "negative": negative, "positive": positive,
        "group_false_alerts": false_alerts, "group_detection_by_setting": detections,
        "outcomes_by_case": {
            state: {cond: _counts(decisions[:, s, c]) for c, cond in enumerate(CONDITIONS)}
            for s, state in enumerate(STATES)
        },
        "strata": by_stratum,
        "calibration_at_equal_class_prior": calibration,
        "flag_precision_by_assumed_encoded_prior": flag_precision,
        "metric_checks": {
            "evaluation_size": len(ids) >= PARTITIONS["evaluation"],
            "evaluation_strata": len(by_stratum) >= 3 and all(s["groups"] >= 30 for s in by_stratum.values()),
            "negative_group_upper_bound": false_alerts["upper_95_if_all_unresolved_alerted"] <= .01,
            "each_setting_lower_bound": all(d["lower_95"] >= .7 for d in detections.values()),
            "negative_no_evidence": negative["no_evidence_rate"] >= .7,
            "encoded_detection": positive["flag_rate"] >= .7,
            "large_strata_limits": all(eligible_stratum_checks) if eligible_stratum_checks else None,
            "brier": calibration["brier"] <= .15 if calibration["brier"] is not None else None,
            "ece": calibration["ece_10"] <= .1 if calibration["ece_10"] is not None else None,
        },
    }
