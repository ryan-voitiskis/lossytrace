"""Prospective rank calculation for the frozen upper cutoff; no audio or model scores."""
from fractions import Fraction
from itertools import combinations
import json
from math import comb

from music_verdict_study import PARTITIONS, exact_lower, exact_upper


def alert_allowance(groups):
    # Upper confidence limit <= .01 iff Pr[Binomial(groups, .01) <= alerts] <= .05.
    # Work with integers to avoid rounding a discrete acceptance boundary.
    denominator = 100 ** groups
    total = 0
    for alerts in range(groups + 1):
        total += comb(groups, alerts) * 99 ** (groups - alerts)
        if 20 * total > denominator:
            return alerts - 1
    raise ArithmeticError("CDF did not reach one")


def pass_fraction(cal, evaluation, allowance):
    if allowance < 0:
        return Fraction(0)
    if allowance >= evaluation:
        return Fraction(1)
    # More than k alerts iff the largest k+1 maxima all belong to evaluation.
    k = allowance + 1
    return 1 - Fraction(comb(evaluation, k), comb(cal + evaluation, k))


def verify_combinations():
    checked = 0
    for c in range(1, 7):
        for e in range(1, 7):
            frequencies = [0] * (e + 1)
            for calibration_ranks in combinations(range(c + e), c):
                alerts = c + e - 1 - max(calibration_ranks)
                frequencies[alerts] += 1
            n = sum(frequencies)
            for k in range(-1, e + 1):
                if Fraction(sum(frequencies[:k+1]), n) != pass_fraction(c, e, k):
                    raise ArithmeticError("rank enumeration disagrees")
            if sum(j * count for j, count in enumerate(frequencies)) * (c + 1) != e * n:
                raise ArithmeticError("unexpected mean number of alerts")
            checked += n
    return checked


def summarize():
    c, e = PARTITIONS["calibration"], PARTITIONS["evaluation"]
    rows = []
    for evaluation in (e, 500, 1000):
        k = alert_allowance(evaluation)
        if not exact_upper(k, evaluation) <= .01 < exact_upper(k + 1, evaluation):
            raise ArithmeticError("study implementation and independent acceptance count disagree")
        for calibration in (c, 300, 600, 1200):
            chance = pass_fraction(calibration, evaluation, k)
            rows.append(dict(calibration=calibration, evaluation=evaluation, allowed_alert_groups=k,
                             rank_subgate_pass_probability=float(chance),
                             exact_pass_fraction=str(chance),
                             expected_alert_groups=evaluation / (calibration + 1)))
    # At p=.70, the exact upper binomial tail at the acceptance count is <=.05.
    terms = [comb(e, n) * 7**n * 3**(e-n) for n in range(e + 1)]
    tail = sum(terms)
    for hits, term in enumerate(terms):
        if tail * 20 <= 10**e:
            break
        tail -= term
    if not exact_lower(hits-1, e) < .70 <= exact_lower(hits, e):
        raise ArithmeticError("study and independent detection boundaries disagree")
    return dict(model="exchangeable distinct negative group maxima, fixed score function",
                small_rank_allocations_enumerated=verify_combinations(),
                planned_calibration_minimum=c, planned_evaluation_minimum=e,
                minimum_group_successes_per_codec=hits, success_lower_95=exact_lower(hits,e),
                one_fewer_success_lower_95=exact_lower(hits-1,e),
                ci_upper_at_zero_alerts=exact_upper(0,e), ci_upper_at_one_alert=exact_upper(1,e),
                iid_continuous_probability_calibrated_alert_risk_at_most_one_percent=1-.99**c,
                iid_continuous_95th_percentile_calibrated_alert_risk=1-.05**(1/c),
                fixed_one_percent_risk_probability_of_zero_evaluation_alerts=.99**e,
                scenarios=rows)


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
