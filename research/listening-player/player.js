"use strict";

const BUILD_ID = "player-synthetic-v1";
const SAMPLE_RATE = 48000;
const DURATION_SECONDS = 4;
const allocationIndex = 0;
const subtleOrder = allocationIndex % 2 === 0 ? ["reference", "condition"] : ["condition", "reference"];
const mushraOrder = ["condition", "anchor-low", "reference", "anchor-mid"];
const state = {
  audio: null,
  currentSource: null,
  channelChecks: { left: false, right: false },
  subtleHeard: new Set(),
  subtleChoice: null,
  subtleGrade: null,
  mushraHeard: new Set(),
  mushraRatings: {},
  replayCounts: {},
};

const byId = (id) => document.getElementById(id);
const markReplay = (id) => { state.replayCounts[id] = (state.replayCounts[id] || 0) + 1; };

function deterministicNoise(frame) {
  const value = Math.sin(frame * 12.9898 + 78.233) * 43758.5453;
  return (value - Math.floor(value)) * 2 - 1;
}

function sample(kind, frame, channel) {
  const t = frame / SAMPLE_RATE;
  const base = 0.22 * Math.sin(2 * Math.PI * 440 * t) + 0.08 * Math.sin(2 * Math.PI * 2800 * t + channel * 0.2);
  if (kind === "reference") return base;
  if (kind === "condition") return base + 0.018 * Math.sin(2 * Math.PI * 6900 * t) * (Math.sin(2 * Math.PI * 2.2 * t) > 0 ? 1 : 0);
  if (kind === "anchor-mid") return 0.23 * Math.sin(2 * Math.PI * 440 * t) + 0.025 * deterministicNoise(frame);
  if (kind === "anchor-low") return Math.max(-0.12, Math.min(0.12, 0.34 * Math.sin(2 * Math.PI * 440 * t))) + 0.045 * deterministicNoise(frame);
  return base;
}

function makeBuffer(kind, channelOnly = null) {
  const frames = SAMPLE_RATE * DURATION_SECONDS;
  const buffer = state.audio.createBuffer(2, frames, SAMPLE_RATE);
  for (let channel = 0; channel < 2; channel += 1) {
    const output = buffer.getChannelData(channel);
    for (let frame = 0; frame < frames; frame += 1) {
      const gate = channelOnly === null || channelOnly === channel ? 1 : 0;
      output[frame] = gate * sample(kind, frame, channel);
    }
  }
  return buffer;
}

function play(kind, channelOnly = null, replayId = kind) {
  if (!state.audio) return;
  if (state.currentSource) state.currentSource.stop();
  const source = state.audio.createBufferSource();
  source.buffer = makeBuffer(kind, channelOnly);
  source.connect(state.audio.destination);
  source.start();
  state.currentSource = source;
  markReplay(replayId);
}

function qualificationReady() {
  const checks = ["confirm-channels", "confirm-level", "confirm-effects"].every((id) => byId(id).checked);
  byId("begin-trials").disabled = !(checks && state.channelChecks.left && state.channelChecks.right);
}

byId("start-audio").addEventListener("click", async () => {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  state.audio = new AudioContextClass({ sampleRate: SAMPLE_RATE, latencyHint: "playback" });
  await state.audio.resume();
  const supported = state.audio.sampleRate === SAMPLE_RATE && state.audio.state === "running";
  byId("audio-diagnostic").textContent = `context=${state.audio.state}; sample_rate=${state.audio.sampleRate}; required=${SAMPLE_RATE}`;
  if (!supported) {
    byId("audio-diagnostic").textContent += "; unsupported playback context";
    return;
  }
  byId("start-audio").disabled = true;
  byId("channel-actions").hidden = false;
  byId("qualification-checks").disabled = false;
});

byId("play-left").addEventListener("click", () => { play("reference", 0, "channel-left"); state.channelChecks.left = true; qualificationReady(); });
byId("play-right").addEventListener("click", () => { play("reference", 1, "channel-right"); state.channelChecks.right = true; qualificationReady(); });
["confirm-channels", "confirm-level", "confirm-effects"].forEach((id) => byId(id).addEventListener("change", qualificationReady));
byId("begin-trials").addEventListener("click", () => { byId("qualification").hidden = true; byId("subtle").hidden = false; });

document.querySelectorAll("[data-play]").forEach((button) => {
  button.addEventListener("click", () => {
    const id = button.dataset.play;
    let kind = "reference";
    if (id === "candidate-a") kind = subtleOrder[0];
    if (id === "candidate-b") kind = subtleOrder[1];
    play(kind, null, id);
    button.classList.add("played");
    if (id !== "reference") state.subtleHeard.add(id);
    byId("forced-choice").disabled = state.subtleHeard.size !== 2;
  });
});

document.querySelectorAll("input[name=choice]").forEach((radio) => radio.addEventListener("change", () => { byId("lock-choice").disabled = false; }));
byId("lock-choice").addEventListener("click", () => {
  const selected = document.querySelector("input[name=choice]:checked");
  if (!selected) return;
  state.subtleChoice = selected.value;
  byId("forced-choice").disabled = true;
  byId("grade-field").disabled = false;
});
byId("sdg").addEventListener("input", (event) => { byId("sdg-value").textContent = Number(event.target.value).toFixed(1).replace("-", "−"); });
byId("submit-subtle").addEventListener("click", () => {
  state.subtleGrade = Number(byId("sdg").value);
  byId("grade-field").disabled = true;
  byId("subtle").hidden = true;
  byId("mushra").hidden = false;
});

function renderMushra() {
  const host = byId("mushra-candidates");
  mushraOrder.forEach((kind, index) => {
    const candidateId = `candidate-${index + 1}`;
    const row = document.createElement("div");
    row.className = "rating-row";
    row.innerHTML = `<button type="button" data-kind="${kind}" data-candidate="${candidateId}">Play candidate ${index + 1}</button><input aria-label="Candidate ${index + 1} quality" type="range" min="0" max="100" step="1" value="50" disabled><output>not rated</output>`;
    const playButton = row.querySelector("button");
    const slider = row.querySelector("input");
    const output = row.querySelector("output");
    playButton.addEventListener("click", () => { play(kind, null, candidateId); state.mushraHeard.add(candidateId); slider.disabled = false; });
    slider.addEventListener("input", () => { state.mushraRatings[candidateId] = Number(slider.value); output.textContent = slider.value; byId("submit-mushra").disabled = Object.keys(state.mushraRatings).length !== mushraOrder.length; });
    host.appendChild(row);
  });
}

document.querySelector("[data-mushra-play=reference]").addEventListener("click", () => play("reference", null, "mushra-visible-reference"));
byId("submit-mushra").addEventListener("click", () => {
  byId("mushra").hidden = true;
  byId("complete").hidden = false;
  const record = {
    schema_version: 1,
    state: "synthetic_dry_run_not_listener_evidence",
    build_id: BUILD_ID,
    sample_rate_hz: SAMPLE_RATE,
    qualification: { channel_order_confirmed: true, comfortable_fixed_level: true, effects_disabled: true },
    subtle: { forced_choice_position: state.subtleChoice, subjective_difference_grade: state.subtleGrade },
    mushra: { basic_audio_quality_by_position: state.mushraRatings },
    replay_counts: state.replayCounts,
    identity_included: false,
    network_storage_used: false,
  };
  byId("synthetic-record").textContent = JSON.stringify(record, null, 2);
});

renderMushra();
