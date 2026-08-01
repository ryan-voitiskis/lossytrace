use crate::AnalysisError;
use rustfft::num_complex::Complex;
use rustfft::FftPlanner;

/// Compute the shared Hann-windowed magnitude STFT used by LossyTrace.
pub fn compute_stft(
    samples: &[f32],
    frame_size: usize,
    hop_size: usize,
) -> Result<Vec<Vec<f32>>, AnalysisError> {
    if frame_size < 2 || !frame_size.is_power_of_two() {
        return Err(AnalysisError::InvalidInput(
            "frame_size must be a power of two greater than one".to_owned(),
        ));
    }
    if hop_size == 0 {
        return Err(AnalysisError::InvalidInput(
            "hop_size must be greater than zero".to_owned(),
        ));
    }
    if samples.iter().any(|sample| !sample.is_finite()) {
        return Err(AnalysisError::InvalidInput(
            "audio samples must be finite".to_owned(),
        ));
    }
    if samples.len() < frame_size {
        return Ok(Vec::new());
    }

    let frame_count = 1 + (samples.len() - frame_size) / hop_size;
    let bin_count = frame_size / 2 + 1;
    let window: Vec<f32> = (0..frame_size)
        .map(|index| {
            let phase = 2.0 * std::f32::consts::PI * index as f32 / (frame_size - 1) as f32;
            0.5 * (1.0 - phase.cos())
        })
        .collect();
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(frame_size);
    let mut frames = Vec::with_capacity(frame_count);

    for frame_index in 0..frame_count {
        let start = frame_index * hop_size;
        let mut input: Vec<Complex<f32>> = samples[start..start + frame_size]
            .iter()
            .zip(&window)
            .map(|(sample, weight)| Complex::new(sample * weight, 0.0))
            .collect();
        fft.process(&mut input);
        frames.push(
            input[..bin_count]
                .iter()
                .map(|value| value.norm())
                .collect(),
        );
    }
    Ok(frames)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_shape_and_input() {
        assert!(compute_stft(&[0.0; 32], 1, 1).is_err());
        assert!(compute_stft(&[0.0; 32], 16, 0).is_err());
        assert!(compute_stft(&[f32::NAN; 32], 16, 4).is_err());
        assert!(compute_stft(&[0.0; 8], 16, 4).unwrap().is_empty());
        let frames = compute_stft(&[0.0; 32], 16, 4).unwrap();
        assert_eq!(frames.len(), 5);
        assert!(frames.iter().all(|frame| frame.len() == 9));
    }
}
