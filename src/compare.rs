//! Exact native-rate PCM identity for complete integer WAV and FLAC streams.
use crate::AnalysisError;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{ErrorKind, Read, Seek, SeekFrom};
use std::path::Path;
use symphonia::core::audio::SampleBuffer;
use symphonia::core::codecs::{
    DecoderOptions, CODEC_TYPE_FLAC, CODEC_TYPE_PCM_S16LE, CODEC_TYPE_PCM_S24LE,
};
use symphonia::core::errors::Error;
use symphonia::core::formats::FormatReader;
use symphonia::core::io::MediaSourceStream;
use symphonia::default::formats::{FlacReader, WavReader};

// Byte-compatible with scripts/music_verdict_pcm_identity.py.
const DOMAIN: &[u8] = b"lossytrace:music-verdict-v1:native-s32le:v1\0";

#[derive(Debug, Serialize)]
pub struct PcmIdentity {
    pub sample_rate_hz: u32,
    pub channel_count: u16,
    pub frames: u64,
    pub bits_per_sample: u32,
    pub canonical_pcm_sha256: String,
}

#[derive(Debug, Serialize)]
pub struct Comparison {
    pub schema_version: u16,
    pub same_decoded_audio: bool,
    pub left: PcmIdentity,
    pub right: PcmIdentity,
}

fn decode_error(error: impl std::fmt::Display) -> AnalysisError {
    AnalysisError::DecodingError(error.to_string())
}

// The decoder rounds the data chunk down to whole frames. Check its byte
// length independently so a partial final frame cannot disappear in a match.
fn check_wav_layout(file: &mut File) -> Result<(), AnalysisError> {
    let mut header = [0; 8]; // RIFF size and form follow the four-byte magic.
    file.read_exact(&mut header).map_err(decode_error)?;
    let riff_end = 8 + u64::from(u32::from_le_bytes(header[..4].try_into().unwrap()));
    if &header[4..] != b"WAVE" || riff_end > file.metadata().map_err(decode_error)?.len() {
        return Err(decode_error("invalid or incomplete RIFF WAV"));
    }
    let mut pos = 12;
    let mut frame_bytes = None;
    let mut data_len = None;
    while pos < riff_end {
        file.seek(SeekFrom::Start(pos)).map_err(decode_error)?;
        file.read_exact(&mut header).map_err(decode_error)?;
        let size = u64::from(u32::from_le_bytes(header[4..].try_into().unwrap()));
        let end = pos + 8 + size;
        if end > riff_end {
            return Err(decode_error("WAV chunk exceeds the RIFF boundary"));
        }
        match &header[..4] {
            b"fmt " => {
                if frame_bytes.is_some() || size < 16 {
                    return Err(decode_error("invalid WAV format chunk"));
                }
                let mut fmt = [0; 16];
                file.read_exact(&mut fmt).map_err(decode_error)?;
                let tag = u16::from_le_bytes([fmt[0], fmt[1]]);
                let channels = u16::from_le_bytes([fmt[2], fmt[3]]);
                let rate = u32::from_le_bytes(fmt[4..8].try_into().unwrap());
                let align = u16::from_le_bytes([fmt[12], fmt[13]]);
                let bits = u16::from_le_bytes([fmt[14], fmt[15]]);
                if !matches!(tag, 1 | 0xfffe)
                    || !matches!(channels, 1 | 2)
                    || rate == 0
                    || !matches!(bits, 16 | 24)
                    || align != channels * (bits / 8)
                {
                    return Err(decode_error(
                        "expected mono or stereo 16/24-bit integer WAV",
                    ));
                }
                frame_bytes = Some(u64::from(align));
            }
            b"data" if data_len.is_some() => {
                return Err(decode_error("multiple WAV data chunks are unsupported"));
            }
            b"data" => data_len = Some(size),
            _ => (),
        }
        pos = end + size % 2;
    }
    let width = frame_bytes.ok_or_else(|| decode_error("missing WAV format chunk"))?;
    let size = data_len.ok_or_else(|| decode_error("missing WAV data chunk"))?;
    if !size.is_multiple_of(width) {
        return Err(decode_error("incomplete final WAV frame"));
    }
    Ok(())
}

fn identify(path: &Path) -> Result<PcmIdentity, AnalysisError> {
    let mut file = File::open(path).map_err(decode_error)?;
    let mut magic = [0; 4];
    file.read_exact(&mut magic).map_err(decode_error)?;
    if &magic == b"RIFF" {
        check_wav_layout(&mut file)?;
    }
    file.rewind().map_err(decode_error)?;
    let source = MediaSourceStream::new(Box::new(file), Default::default());
    let options = Default::default();
    let mut reader: Box<dyn FormatReader> = match &magic {
        b"RIFF" => Box::new(WavReader::try_new(source, &options).map_err(decode_error)?),
        b"fLaC" => Box::new(FlacReader::try_new(source, &options).map_err(decode_error)?),
        _ => return Err(decode_error("expected RIFF WAV or native FLAC")),
    };

    let track = reader
        .default_track()
        .ok_or_else(|| decode_error("missing audio track"))?;
    let params = &track.codec_params;
    let sample_rate_hz = params.sample_rate.unwrap_or(0);
    let channel_count = params.channels.map_or(0, |channels| channels.count()) as u16;
    let bits_per_sample = params.bits_per_sample.unwrap_or(0);
    if !matches!(
        params.codec,
        CODEC_TYPE_FLAC | CODEC_TYPE_PCM_S16LE | CODEC_TYPE_PCM_S24LE
    ) || !matches!(bits_per_sample, 16 | 24)
        || params
            .bits_per_coded_sample
            .is_some_and(|coded| coded != bits_per_sample)
        || !matches!(channel_count, 1 | 2)
        || sample_rate_hz == 0
    {
        return Err(decode_error(
            "comparison requires mono or stereo 16/24-bit integer audio",
        ));
    }
    let frames = params
        .n_frames
        .filter(|n| *n > 0)
        .ok_or_else(|| decode_error("comparison requires a declared nonzero frame count"))?;
    let mut decoder = symphonia::default::get_codecs()
        .make(params, &DecoderOptions { verify: true })
        .map_err(decode_error)?;
    let mut hash = Sha256::new();
    hash.update(DOMAIN);
    hash.update(sample_rate_hz.to_le_bytes());
    hash.update(channel_count.to_le_bytes());
    hash.update(frames.to_le_bytes());

    let mut decoded_frames = 0;
    let mut bytes = Vec::new();
    loop {
        let packet = match reader.next_packet() {
            Ok(packet) => packet,
            Err(Error::IoError(e)) if e.kind() == ErrorKind::UnexpectedEof => break,
            Err(e) => return Err(decode_error(e)),
        };
        let decoded = decoder.decode(&packet).map_err(decode_error)?;
        let count = decoded.frames() as u64;
        if decoded.spec().rate != sample_rate_hz
            || decoded.spec().channels.count() != usize::from(channel_count)
            || count != packet.dur()
            || packet.ts() != decoded_frames
            || decoded_frames + count > frames
        {
            return Err(decode_error(
                "inconsistent audio format, packet position or length",
            ));
        }
        let mut samples = SampleBuffer::<i32>::new(count, *decoded.spec());
        samples.copy_interleaved_ref(decoded);
        bytes.clear();
        bytes.extend(
            samples
                .samples()
                .iter()
                .flat_map(|sample| sample.to_le_bytes()),
        );
        hash.update(&bytes);
        decoded_frames += count;
    }
    if decoded_frames != frames {
        return Err(decode_error(format!(
            "decoded {decoded_frames} of {frames} declared frames"
        )));
    }
    if decoder.finalize().verify_ok == Some(false) {
        return Err(decode_error("audio checksum mismatch"));
    }
    Ok(PcmIdentity {
        sample_rate_hz,
        channel_count,
        frames,
        bits_per_sample,
        canonical_pcm_sha256: format!("{:x}", hash.finalize()),
    })
}

/// Compare complete streams using the same canonical PCM fingerprint as the research inventory.
pub fn compare_files(left: &Path, right: &Path) -> Result<Comparison, AnalysisError> {
    let left =
        identify(left).map_err(|e| AnalysisError::InvalidInput(format!("left input: {e}")))?;
    let right =
        identify(right).map_err(|e| AnalysisError::InvalidInput(format!("right input: {e}")))?;
    Ok(Comparison {
        schema_version: 1,
        same_decoded_audio: left.canonical_pcm_sha256 == right.canonical_pcm_sha256,
        left,
        right,
    })
}
