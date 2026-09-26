/* Research-only extension of the unchanged PSF-licensed bounded sum kernel.
 * See research/licenses/alignment-kernel-PSF-LICENSE.txt. The included source
 * and this extension are separately hash-bound by the qualification protocol.
 * New: normalize both strided vectors and accumulate three independent sums.
 * No changed partial-sum algorithm, fast math, FFT or approximate search.
 */
#include "perceptual_degradation_correlation_native.c"

int lt_global_cosine(const double *a, const double *b, size_t count, size_t stride,
                     double *numerator, double *energy_a, double *energy_b) {
    if (!lt_environment() || count == 0 || count > 576008 || stride == 0) return -1;
    double scale_a = 0.0, scale_b = 0.0;
    for (size_t i = 0; i < count; ++i) {
        double x = a[i * stride], y = b[i * stride];
        if (!isfinite(x) || !isfinite(y)) return 2;
        if (fabs(x) > scale_a) scale_a = fabs(x);
        if (fabs(y) > scale_b) scale_b = fabs(y);
    }
    if (scale_a == 0.0 || scale_b == 0.0) return 1;
    Sum dot = {{0}, 0}, norm_a = {{0}, 0}, norm_b = {{0}, 0};
    for (size_t i = 0; i < count; ++i) {
        double x = a[i * stride] / scale_a, y = b[i * stride] / scale_b;
        if (add(&norm_a, x * x) || add(&norm_b, y * y) || add(&dot, x * y)) return -1;
    }
    *numerator = finish(&dot);
    *energy_a = finish(&norm_a);
    *energy_b = finish(&norm_b);
    return 0;
}
