"""Research-only calibration of complete, preallocated primary case matrices."""
from dataclasses import dataclass
import math


STATES = ("baseline", "mp3-128", "mp3-192", "mp3-320", "aac-128", "aac-192", "aac-256")
CONDITIONS = ("identity", "gain", "dither16", "resample", "lowpass16k", "eq_dynamics")
CASES = tuple((state, condition) for state in STATES for condition in CONDITIONS)


def _number(value):
    if type(value) not in (int, float):
        raise ValueError("finite numeric logit required")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError("unrepresentable numeric logit") from exc
    if not math.isfinite(value):
        raise ValueError("finite numeric logit required")
    return value


def _sigmoid(x):
    z = math.exp(-abs(x))
    return 1 / (1 + z) if x >= 0 else z / (1 + z)


@dataclass(frozen=True)
class Policy:
    temperature: float
    low_logit: float
    high_logit: float

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.temperature, self.low_logit, self.high_logit)):
            raise ValueError("unrepresentable calibration policy")
        if self.temperature <= 0 or self.low_logit >= self.high_logit:
            raise ValueError("degenerate calibration policy")

    def score(self, logit):
        x = _number(logit)
        if x >= self.high_logit:
            outcome = "likely_lossy_derived"
        elif x <= self.low_logit:
            outcome = "no_evidence_detected"
        else:
            outcome = "inconclusive"
        return outcome, _sigmoid(x / self.temperature)


def fit_policy(groups, expected_groups, *, partition):
    """Input is {component_id: {(state, condition): raw file logit}}.

    The caller binds expected_groups to a verified calibration allocation.
    Requiring it explicitly catches omitted complete groups. Source eligibility,
    split disjointness, model identity and artifact binding are caller checks.
    Equal group and class weights. Fit scalar temperature by solving the
    monotone derivative of weighted BCE with respect to inverse temperature.
    Threshold raw logits so probability saturation cannot change a verdict.
    """
    if partition != "calibration":
        raise ValueError("policy fitting requires the calibration partition")
    if (not isinstance(expected_groups, (list, tuple)) or not expected_groups
            or any(not isinstance(g, str) or not g.strip() for g in expected_groups)
            or len(set(expected_groups)) != len(expected_groups)
            or set(groups) != set(expected_groups)):
        raise ValueError("calibration group inventory mismatch")
    negatives, positives = [], []
    for group in sorted(expected_groups):
        cells = groups[group]
        if set(cells) != set(CASES):
            raise ValueError("incomplete or unexpected calibration case matrix")
        for state, condition in CASES:
            target = negatives if state == "baseline" else positives
            target.append(_number(cells[state, condition]))
    high = math.nextafter(max(negatives), math.inf)
    low = min(math.nextafter(min(positives), -math.inf), math.nextafter(high, -math.inf))
    if not math.isfinite(high) or not math.isfinite(low):
        raise ValueError("unrepresentable calibration threshold")
    scale = max(abs(x) for values in (positives, negatives) for x in values)
    if scale == 0:
        raise ValueError("temperature unidentified on zero logits")
    # All groups have identical case matrices. One negative carries the
    # same mass as six positives. Global constants cancel in the root.
    negative_weight = len(positives) // len(negatives)
    margins = [(x / scale, 1) for x in positives]
    margins.extend((-x / scale, negative_weight) for x in negatives)
    if not any(m < 0 for m, _ in margins):
        raise ValueError("BCE has no finite temperature minimum")

    def derivative(beta):
        return math.fsum(-weight * margin * _sigmoid(-beta * margin)
                         for margin, weight in margins)

    if derivative(0) >= 0:
        raise ValueError("BCE minimum at infinite temperature")
    left, right = 0., 1.
    while derivative(right) < 0:
        left, right = right, 2 * right
        if not math.isfinite(right):
            raise ValueError("inverse temperature is unrepresentable")
    # Bisection to adjacent floats, including minima near zero.
    while True:
        mid = left + (right - left) / 2
        if mid == left or mid == right:
            break
        if derivative(mid) < 0:
            left = mid
        else:
            right = mid
    return Policy(scale / right, low, high)
