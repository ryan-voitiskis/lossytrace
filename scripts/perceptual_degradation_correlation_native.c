/* Research-only bounded cosine kernel. Not part of the public CLI.
 * The partial-sum insertion and rounding steps are adapted from CPython
 * v3.14.7 Modules/mathmodule.c math_fsum, Copyright Python Software Foundation.
 * See research/licenses/alignment-kernel-PSF-LICENSE.txt and the v4 plan.
 * Changes: bounded finite products only, explicit capacity failure, split
 * accumulation/finalization, and no Python object or special-value machinery.
 */
#include <float.h>
#include <fenv.h>
#include <math.h>
#include <stddef.h>

typedef struct { double part[64]; size_t size; } Sum;

static int add(Sum *s, double x) {
    size_t kept = 0;
    for (size_t j = 0; j < s->size; ++j) {
        double y = s->part[j];
        if (fabs(x) < fabs(y)) { double tmp = x; x = y; y = tmp; }
        double hi = x + y;
        double lo = y - (hi - x);
        if (lo != 0.0) s->part[kept++] = lo;
        x = hi;
    }
    if (!isfinite(x) || (x != 0.0 && kept == 64)) return -1;
    if (x != 0.0) s->part[kept++] = x;
    s->size = kept;
    return 0;
}

static double finish(Sum *s) {
    size_t n = s->size;
    double hi = 0.0, lo = 0.0;
    if (n) hi = s->part[--n];
    while (n) {
        double x = hi, y = s->part[--n];
        hi = x + y;
        lo = y - (hi - x);
        if (lo != 0.0) break;
    }
    if (n && ((lo < 0.0 && s->part[n-1] < 0.0) ||
              (lo > 0.0 && s->part[n-1] > 0.0))) {
        double y = lo * 2.0, x = hi + y;
        if (x - hi == y) hi = x;
    }
    return hi;
}

int lt_environment(void) {
    volatile double tiny = 0x1p-1074;
    volatile double twice = 0x1p-1073, half = 0.5;
    return sizeof(double) == 8 && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024 &&
           FLT_EVAL_METHOD == 0 && fegetround() == FE_TONEAREST && twice * half == tiny && tiny > 0;
}

/* Direct bounded-summation test seam; not used by alignment. */
int lt_test_sum(const double *values, size_t count, double *out) {
    if (!lt_environment() || count > 576008) return -1;
    Sum s = {{0}, 0};
    for (size_t i = 0; i < count; ++i) {
        if (!isfinite(values[i]) || fabs(values[i]) > 1.0 || add(&s, values[i])) return -1;
    }
    *out = finish(&s);
    return 0;
}

/* x is already scaled exactly as v3, sampled once in Python. y is raw.
 * Returns 0 valid, 1 zero energy, 2 invalid numeric input, -1 use Python.
 * Validation precedes zero energy, including when reference energy is zero.
 */
int lt_cosine(const double *x, const double *y, size_t count, size_t stride,
              int reference_zero, double *numerator, double *energy) {
    if (!lt_environment() || count == 0 || count > 576008 || stride == 0) return -1;
    double scale = 0.0;
    for (size_t i = 0; i < count; ++i) {
        double value = y[i * stride];
        if (!isfinite(value)) return 2;
        if (fabs(value) > scale) scale = fabs(value);
    }
    if (reference_zero || scale == 0.0) return 1;
    Sum dot = {{0}, 0}, norm = {{0}, 0};
    for (size_t i = 0; i < count; ++i) {
        double value = y[i * stride] / scale;
        if (add(&norm, value * value) || add(&dot, x[i] * value)) return -1;
    }
    *numerator = finish(&dot);
    *energy = finish(&norm);
    return 0;
}
