"use strict";

(function install(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.LossyTraceLosslessWav = api;
}(typeof globalThis === "object" ? globalThis : this, () => {
  const allowedDepths = new Set([16, 24, 32]);

  function assert(condition, message) {
    if (!condition) throw new Error(message);
  }

  function bytesToHex(bytes) {
    return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  }

  async function sha256Hex(buffer) {
    assert(globalThis.crypto && globalThis.crypto.subtle, "Web Crypto is unavailable");
    const digest = await globalThis.crypto.subtle.digest("SHA-256", buffer);
    return bytesToHex(new Uint8Array(digest));
  }

  function chunkName(view, offset) {
    return String.fromCharCode(
      view.getUint8(offset),
      view.getUint8(offset + 1),
      view.getUint8(offset + 2),
      view.getUint8(offset + 3),
    );
  }

  function parsePcmWav(buffer, expected = {}) {
    const view = new DataView(buffer);
    assert(view.byteLength >= 44, "WAV is shorter than the minimum header");
    assert(chunkName(view, 0) === "RIFF" && chunkName(view, 8) === "WAVE", "WAV RIFF signature differs");
    assert(view.getUint32(4, true) + 8 === view.byteLength, "WAV RIFF length differs");
    let offset = 12;
    let format = null;
    let dataOffset = null;
    let dataLength = null;
    while (offset + 8 <= view.byteLength) {
      const name = chunkName(view, offset);
      const length = view.getUint32(offset + 4, true);
      const start = offset + 8;
      const end = start + length;
      assert(end <= view.byteLength, "WAV chunk exceeds file length");
      if (name === "fmt ") {
        assert(format === null && length >= 16, "WAV format chunk differs");
        format = {
          audioFormat: view.getUint16(start, true),
          channelCount: view.getUint16(start + 2, true),
          sampleRateHz: view.getUint32(start + 4, true),
          byteRate: view.getUint32(start + 8, true),
          blockAlign: view.getUint16(start + 12, true),
          bitDepth: view.getUint16(start + 14, true),
        };
      } else if (name === "data") {
        assert(dataOffset === null, "Multiple WAV data chunks are unsupported");
        dataOffset = start;
        dataLength = length;
      }
      offset = end + (length & 1);
    }
    assert(offset === view.byteLength, "WAV chunk padding differs");
    assert(format !== null && dataOffset !== null && dataLength !== null, "Required WAV chunks are absent");
    assert(format.audioFormat === 1, "Only integer PCM WAV is supported");
    assert(format.channelCount === 1 || format.channelCount === 2, "WAV channel count is unsupported");
    assert(format.sampleRateHz === 44100 || format.sampleRateHz === 48000, "WAV sample rate is unsupported");
    assert(allowedDepths.has(format.bitDepth), "WAV bit depth is unsupported");
    const bytesPerSample = format.bitDepth / 8;
    const expectedAlign = format.channelCount * bytesPerSample;
    assert(format.blockAlign === expectedAlign, "WAV block alignment differs");
    assert(format.byteRate === format.sampleRateHz * expectedAlign, "WAV byte rate differs");
    assert(dataLength > 0 && dataLength % expectedAlign === 0, "WAV PCM payload is empty or misaligned");
    for (const [key, actual] of [
      ["sampleRateHz", format.sampleRateHz],
      ["channelCount", format.channelCount],
      ["bitDepth", format.bitDepth],
    ]) {
      if (expected[key] !== undefined) assert(expected[key] === actual, `WAV ${key} binding differs`);
    }

    const frameCount = dataLength / expectedAlign;
    const channels = Array.from({ length: format.channelCount }, () => new Float32Array(frameCount));
    for (let frame = 0; frame < frameCount; frame += 1) {
      for (let channel = 0; channel < format.channelCount; channel += 1) {
        const cursor = dataOffset + frame * expectedAlign + channel * bytesPerSample;
        let sample;
        if (format.bitDepth === 16) {
          sample = view.getInt16(cursor, true) / 32768;
        } else if (format.bitDepth === 24) {
          let integer = view.getUint8(cursor) | (view.getUint8(cursor + 1) << 8) | (view.getUint8(cursor + 2) << 16);
          if (integer & 0x800000) integer -= 0x1000000;
          sample = integer / 8388608;
        } else {
          sample = view.getInt32(cursor, true) / 2147483648;
        }
        channels[channel][frame] = sample;
      }
    }
    return Object.freeze({
      sampleRateHz: format.sampleRateHz,
      channelCount: format.channelCount,
      bitDepth: format.bitDepth,
      frameCount,
      durationSeconds: frameCount / format.sampleRateHz,
      channels,
    });
  }

  async function fetchVerifiedPcmWav(url, binding) {
    assert(/^\/[a-z0-9/-]+\.wav$/.test(url), "Stimulus URL must be same-origin and opaque");
    assert(/^[0-9a-f]{64}$/.test(binding.privateAudioSha256), "Stimulus SHA-256 binding differs");
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
    });
    assert(response.ok && !response.redirected, "Stimulus request failed or redirected");
    assert(response.headers.get("content-type") === "audio/wav", "Stimulus content type differs");
    const buffer = await response.arrayBuffer();
    assert(buffer.byteLength === binding.byteLength, "Stimulus byte length differs");
    assert(await sha256Hex(buffer) === binding.privateAudioSha256, "Stimulus SHA-256 differs");
    return parsePcmWav(buffer, binding);
  }

  return Object.freeze({ bytesToHex, fetchVerifiedPcmWav, parsePcmWav, sha256Hex });
}));
