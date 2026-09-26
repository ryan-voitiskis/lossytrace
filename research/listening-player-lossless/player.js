"use strict";

const BUILD_ID = "player-lossless-qualification-v1";
const byId = (id) => document.getElementById(id);
const state = { session: null, audio: null, currentSource: null, verified: new Map() };

function requireExactKeys(value, expected, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be an object`);
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index])) throw new Error(`${label} fields differ`);
}

function validateSession(session) {
  requireExactKeys(session, [
    "schema_version",
    "state",
    "manifest_id",
    "sample_rate_hz",
    "human_collection_authorized",
    "listener_response_collection_enabled",
    "metric_score_included",
    "condition_recipe_included",
    "private_path_included",
    "stimuli",
  ], "session");
  if (session.schema_version !== 1 || session.state !== "private_lossless_delivery_qualification_only") throw new Error("Session schema or state differs");
  if (!/^[a-z][a-z0-9-]{7,63}$/.test(session.manifest_id)) throw new Error("Manifest identifier differs");
  if (![44100, 48000].includes(session.sample_rate_hz)) throw new Error("Session sample rate differs");
  const boundaries = [
    session.human_collection_authorized,
    session.listener_response_collection_enabled,
    session.metric_score_included,
    session.condition_recipe_included,
    session.private_path_included,
  ];
  if (boundaries.some((value) => value !== false)) throw new Error("Session boundary differs");
  if (!Array.isArray(session.stimuli) || session.stimuli.length < 1 || session.stimuli.length > 12) throw new Error("Session stimulus count differs");
  const identifiers = new Set();
  session.stimuli.forEach((binding) => {
    requireExactKeys(binding, [
      "stimulus_id",
      "private_audio_sha256",
      "byte_length",
      "container",
      "sample_rate_hz",
      "channel_count",
      "bit_depth",
    ], "stimulus binding");
    if (!/^[a-z][a-z0-9-]{7,63}$/.test(binding.stimulus_id) || identifiers.has(binding.stimulus_id)) throw new Error("Stimulus identifier differs");
    identifiers.add(binding.stimulus_id);
    if (!/^[0-9a-f]{64}$/.test(binding.private_audio_sha256)) throw new Error("Stimulus hash differs");
    if (!Number.isInteger(binding.byte_length) || binding.byte_length < 44 || binding.byte_length > 33554432) throw new Error("Stimulus byte length differs");
    if (binding.container !== "wav" || binding.sample_rate_hz !== session.sample_rate_hz) throw new Error("Stimulus container or rate differs");
    if (![1, 2].includes(binding.channel_count) || ![16, 24, 32].includes(binding.bit_depth)) throw new Error("Stimulus PCM geometry differs");
  });
}

function setStatus(id, value) {
  byId(id).textContent = value;
}

function stopCurrent() {
  if (state.currentSource) {
    state.currentSource.stop();
    state.currentSource = null;
  }
}

function play(stimulusId, channelOnly = null) {
  const parsed = state.verified.get(stimulusId);
  if (!parsed || !state.audio) throw new Error("Stimulus or exact-rate audio context is unavailable");
  stopCurrent();
  const output = state.audio.createBuffer(parsed.channelCount, parsed.frameCount, parsed.sampleRateHz);
  parsed.channels.forEach((channel, index) => {
    const target = output.getChannelData(index);
    if (channelOnly === null || channelOnly === index) target.set(channel);
  });
  const source = state.audio.createBufferSource();
  source.buffer = output;
  source.connect(state.audio.destination);
  source.start();
  state.currentSource = source;
}

function renderStimuli() {
  const host = byId("stimuli");
  state.session.stimuli.forEach((binding) => {
    const row = document.createElement("article");
    row.className = "stimulus";
    const title = document.createElement("h3");
    title.textContent = binding.stimulus_id;
    const detail = document.createElement("p");
    detail.textContent = `${binding.sample_rate_hz} Hz · ${binding.channel_count} channel(s) · ${binding.bit_depth}-bit · ${binding.byte_length} bytes`;
    const status = document.createElement("p");
    status.className = "diagnostic";
    status.textContent = "Not verified.";
    const controls = document.createElement("div");
    controls.className = "controls";
    const verify = document.createElement("button");
    verify.type = "button";
    verify.textContent = "Verify bytes";
    const playAll = document.createElement("button");
    playAll.type = "button";
    playAll.textContent = "Play";
    playAll.disabled = true;
    const playLeft = document.createElement("button");
    playLeft.type = "button";
    playLeft.textContent = "Left only";
    playLeft.disabled = true;
    const playRight = document.createElement("button");
    playRight.type = "button";
    playRight.textContent = "Right only";
    playRight.disabled = true;
    verify.addEventListener("click", async () => {
      verify.disabled = true;
      status.textContent = "Verifying exact bytes and PCM geometry…";
      try {
        const parsed = await globalThis.LossyTraceLosslessWav.fetchVerifiedPcmWav(
          `/stimuli/${binding.stimulus_id}.wav`,
          {
            privateAudioSha256: binding.private_audio_sha256,
            byteLength: binding.byte_length,
            sampleRateHz: binding.sample_rate_hz,
            channelCount: binding.channel_count,
            bitDepth: binding.bit_depth,
          },
        );
        if (!state.audio || state.audio.sampleRate !== parsed.sampleRateHz) throw new Error("Exact-rate audio context differs");
        state.verified.set(binding.stimulus_id, parsed);
        status.textContent = `Verified SHA-256 and ${parsed.frameCount} PCM frames; no resampling requested.`;
        playAll.disabled = false;
        playLeft.disabled = parsed.channelCount !== 2;
        playRight.disabled = parsed.channelCount !== 2;
      } catch (error) {
        status.textContent = `Unsupported: ${error.message}`;
        verify.disabled = false;
      }
    });
    playAll.addEventListener("click", () => play(binding.stimulus_id));
    playLeft.addEventListener("click", () => play(binding.stimulus_id, 0));
    playRight.addEventListener("click", () => play(binding.stimulus_id, 1));
    controls.append(verify, playAll, playLeft, playRight);
    row.append(title, detail, status, controls);
    host.appendChild(row);
  });
}

byId("start-audio").addEventListener("click", async () => {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  state.audio = new AudioContextClass({ sampleRate: state.session.sample_rate_hz, latencyHint: "playback" });
  await state.audio.resume();
  const exact = state.audio.state === "running" && state.audio.sampleRate === state.session.sample_rate_hz;
  setStatus("audio-status", `build=${BUILD_ID}; context=${state.audio.state}; sample_rate=${state.audio.sampleRate}; required=${state.session.sample_rate_hz}`);
  if (!exact) {
    setStatus("audio-status", `${byId("audio-status").textContent}; unsupported exact-rate context`);
    return;
  }
  byId("start-audio").disabled = true;
  renderStimuli();
});

(async () => {
  try {
    if (location.protocol !== "http:" || location.hostname !== "127.0.0.1") throw new Error("Qualification origin must be numeric loopback HTTP");
    const response = await fetch("/session.json", { cache: "no-store", credentials: "omit", redirect: "error" });
    if (!response.ok || response.redirected) throw new Error("Session request failed or redirected");
    if (response.headers.get("content-type") !== "application/json") throw new Error("Session content type differs");
    const session = await response.json();
    validateSession(session);
    state.session = session;
    setStatus("session-status", `manifest=${session.manifest_id}; stimuli=${session.stimuli.length}; sample_rate=${session.sample_rate_hz}; collection=false`);
    byId("start-audio").disabled = false;
  } catch (error) {
    setStatus("session-status", `Unsupported: ${error.message}`);
  }
})();
