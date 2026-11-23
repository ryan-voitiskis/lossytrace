// Render the reviewed score with its bundled player in memory, without starting the game.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [project, out] = process.argv.slice(2);
assert.deepEqual(process.execArgv, ["--random-seed=20260927"]);
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const bindings = {
    "text/src/game/lib/soundbox/music_game.js": "0daca73ccf86e4560b304c1b8ed7b956edee035c8d887d9b6958c5d6ffd81779",
    "text/src/game/lib/soundbox/soundboxplayer.js": "d71a0a8421a78669bdbeedcc9d9ced48061cbb5d9239fe73efc0eac1d555e412",
    "text/music_nd_Sound.md": "c1bb6260bcbb9b17169dceffecc01695c1070852b8de3d9a3a96f81018baebe0",
    "LICENSE": "7eb3cba0e0f53ec7b14712334e7009dbbbf54414a38d269989bad19a2db201dd",
};
const texts = {};
for (const [file, expected] of Object.entries(bindings)) {
    const raw = readFileSync(join(project, file));
    assert.equal(hash(raw), expected);
    texts[file] = raw.toString("utf8");
}
const player = texts["text/src/game/lib/soundbox/soundboxplayer.js"];
const importSource = async text => (await import("data:text/javascript;base64," +
    Buffer.from(text).toString("base64"))).default;
const Player = await importSource(player);
const song = await importSource(texts["text/src/game/lib/soundbox/music_game.js"]);
const mixer = new Player();
mixer.init(song);
for (let ch = 1; ch <= song.numChannels; ch++) assert.equal(mixer.generate(), ch / song.numChannels);

const wav = Buffer.from(mixer.createWave());
const frames = 4586816;
assert.equal(wav.subarray(0, 4).toString(), "RIFF");
assert.equal(wav.readUInt32LE(24), 44100);
assert.equal(wav.readUInt16LE(22), 2);
assert.equal(wav.readUInt16LE(34), 16);
assert.equal(wav.length, 44 + frames * 4);
// Exercise the player's two export methods on the SAME mix. This is an AudioBuffer
// stand-in, with no sound device, browser playback or game-side effects.
const planes = [new Float32Array(frames), new Float32Array(frames)];
mixer.createAudioBuffer({ createBuffer(channels, length, rate) {
    assert.deepEqual([channels, length, rate], [2, frames, 44100]);
    return { getChannelData: i => planes[i] };
}});
let saturated = 0;
let peak = 0;
let aboveOne = 0;
for (let i = 0; i < frames; i++) {
    for (let ch = 0; ch < 2; ch++) {
        const sample = planes[ch][i];
        const mix = sample * 65536;
        peak = Math.max(peak, Math.abs(mix));
        if (Math.abs(sample) > 1) aboveOne++;
        if (Math.abs(mix) > 32767) saturated++;
        assert.equal(wav.readInt16LE(44 + 2 * (i * 2 + ch)), Math.max(-32767, Math.min(32767, mix)));
    }
}
mkdirSync(out);
writeFileSync(join(out, "score.wav"), wav);
writeFileSync(join(out, "LICENSE-project.txt"), texts.LICENSE);
writeFileSync(join(out, "NOTICE-player.txt"), player.slice(0, player.indexOf('"use strict";')));
const receipt = { project_revision: "c5de969696e94c35a635f97f31faa94cb4a6b32c",
    inputs_sha256: bindings, node: process.version, v8: process.versions.v8, arch: process.arch,
    platform: process.platform, random_seed: 20260927, frames, rate: 44100, channels: 2, output_bits: 16,
    peak_absolute_mix_integer: peak, wav_saturated_channel_samples: saturated,
    audio_buffer_channel_samples_above_unit_magnitude: aboveOne, wav_sha256: hash(wav),
    s16le_sha256: hash(wav.subarray(44)) };
writeFileSync(join(out, "render.json"), JSON.stringify(receipt, null, 2) + "\n");
