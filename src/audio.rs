use crate::AnalysisError;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::Read;
use std::path::Path;
use symphonia::core::audio::AudioBufferRef;
use symphonia::core::codecs::DecoderOptions;
use symphonia::core::formats::FormatOptions;
use symphonia::core::io::MediaSourceStream;
use symphonia::core::meta::MetadataOptions;
use symphonia::core::probe::Hint;
use symphonia::default::get_probe;

#[derive(Debug, Clone, Serialize)]
pub struct SourceFacts {
    pub sample_rate_hz: u32,
    pub channel_count: Option<usize>,
    pub declared_bits_per_sample: Option<u32>,
    pub codec_debug: String,
    pub container_extension: Option<String>,
}

pub(crate) struct DecodedAudio {
    pub samples: Vec<f32>,
    pub source_facts: SourceFacts,
    pub truncated_by_limit: bool,
}

pub(crate) fn sha256_file(path: &Path) -> Result<String, AnalysisError> {
    let mut file = File::open(path).map_err(|error| {
        AnalysisError::InvalidInput(format!("open {}: {error}", path.display()))
    })?;
    let mut digest = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let count = file.read(&mut buffer).map_err(|error| {
            AnalysisError::InvalidInput(format!("read {}: {error}", path.display()))
        })?;
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn downmix(buffer: &AudioBufferRef<'_>, output: &mut Vec<f32>) {
    fn mix<T: Copy>(planes: &[&[T]], convert: impl Fn(T) -> f32, output: &mut Vec<f32>) {
        if planes.is_empty() {
            return;
        }
        for index in 0..planes[0].len() {
            let sum: f32 = planes.iter().map(|plane| convert(plane[index])).sum();
            output.push(sum / planes.len() as f32);
        }
    }
    match buffer {
        AudioBufferRef::F32(value) => mix(value.planes().planes(), |sample| sample, output),
        AudioBufferRef::F64(value) => mix(value.planes().planes(), |sample| sample as f32, output),
        AudioBufferRef::S8(value) => mix(
            value.planes().planes(),
            |sample| sample as f32 / 128.0,
            output,
        ),
        AudioBufferRef::S16(value) => mix(
            value.planes().planes(),
            |sample| sample as f32 / 32_768.0,
            output,
        ),
        AudioBufferRef::S24(value) => mix(
            value.planes().planes(),
            |sample| sample.inner() as f32 / 8_388_608.0,
            output,
        ),
        AudioBufferRef::S32(value) => mix(
            value.planes().planes(),
            |sample| sample as f32 / 2_147_483_648.0,
            output,
        ),
        AudioBufferRef::U8(value) => mix(
            value.planes().planes(),
            |sample| (sample as f32 - 128.0) / 128.0,
            output,
        ),
        AudioBufferRef::U16(value) => mix(
            value.planes().planes(),
            |sample| (sample as f32 - 32_768.0) / 32_768.0,
            output,
        ),
        AudioBufferRef::U24(value) => mix(
            value.planes().planes(),
            |sample| (sample.inner() as f32 - 8_388_608.0) / 8_388_608.0,
            output,
        ),
        AudioBufferRef::U32(value) => mix(
            value.planes().planes(),
            |sample| (sample as f32 - 2_147_483_648.0) / 2_147_483_648.0,
            output,
        ),
    }
}

pub(crate) fn decode(path: &Path, max_seconds: Option<f64>) -> Result<DecodedAudio, AnalysisError> {
    if let Some(seconds) = max_seconds {
        if !seconds.is_finite() || seconds <= 0.0 {
            return Err(AnalysisError::InvalidInput(
                "max_seconds must be finite and greater than zero".to_owned(),
            ));
        }
    }
    let file = File::open(path).map_err(|error| {
        AnalysisError::InvalidInput(format!("open {}: {error}", path.display()))
    })?;
    let source = MediaSourceStream::new(Box::new(file), Default::default());
    let mut hint = Hint::new();
    if let Some(extension) = path.extension().and_then(|value| value.to_str()) {
        hint.with_extension(extension);
    }
    let probed = get_probe()
        .format(
            &hint,
            source,
            &FormatOptions::default(),
            &MetadataOptions::default(),
        )
        .map_err(|error| {
            AnalysisError::DecodingError(format!("probe {}: {error}", path.display()))
        })?;
    let mut reader = probed.format;
    let track = reader.default_track().ok_or_else(|| {
        AnalysisError::DecodingError(format!("no default audio track in {}", path.display()))
    })?;
    let track_id = track.id;
    let sample_rate = track.codec_params.sample_rate.ok_or_else(|| {
        AnalysisError::DecodingError(format!("missing sample rate in {}", path.display()))
    })?;
    let source_facts = SourceFacts {
        sample_rate_hz: sample_rate,
        channel_count: track.codec_params.channels.map(|channels| channels.count()),
        declared_bits_per_sample: track.codec_params.bits_per_sample,
        codec_debug: format!("{:?}", track.codec_params.codec),
        container_extension: path
            .extension()
            .and_then(|value| value.to_str())
            .map(str::to_ascii_lowercase),
    };
    let mut decoder = symphonia::default::get_codecs()
        .make(&track.codec_params, &DecoderOptions::default())
        .map_err(|error| AnalysisError::DecodingError(format!("decoder: {error}")))?;
    let sample_limit = max_seconds
        .map(|seconds| (seconds * f64::from(sample_rate)) as usize)
        .unwrap_or(usize::MAX);
    let initial_capacity = sample_limit.min(sample_rate as usize * 60);
    let mut samples = Vec::with_capacity(initial_capacity);
    let mut reached_eof = false;

    while samples.len() < sample_limit {
        let packet = match reader.next_packet() {
            Ok(packet) => packet,
            Err(symphonia::core::errors::Error::IoError(error))
                if error.kind() == std::io::ErrorKind::UnexpectedEof =>
            {
                reached_eof = true;
                break;
            }
            Err(error) => {
                return Err(AnalysisError::DecodingError(format!(
                    "read packet: {error}"
                )))
            }
        };
        if packet.track_id() != track_id {
            continue;
        }
        match decoder.decode(&packet) {
            Ok(decoded) => downmix(&decoded, &mut samples),
            Err(symphonia::core::errors::Error::DecodeError(_)) => continue,
            Err(error) => {
                return Err(AnalysisError::DecodingError(format!(
                    "decode packet: {error}"
                )))
            }
        }
    }
    let truncated_by_limit = !reached_eof && samples.len() >= sample_limit;
    samples.truncate(sample_limit);
    if samples.is_empty() {
        return Err(AnalysisError::DecodingError(format!(
            "decoded zero audio samples from {}",
            path.display()
        )));
    }
    Ok(DecodedAudio {
        samples,
        source_facts,
        truncated_by_limit,
    })
}
