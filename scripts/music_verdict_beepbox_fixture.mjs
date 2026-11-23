// Emit one newly constructed technical fixture as interleaved stereo float32 LE.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const [archive, rateText, seedText] = process.argv.slice(2);
const rate = Number(rateText);
const seed = Number(seedText);
assert.ok([44100, 48000].includes(rate));
assert.ok(Number.isInteger(seed) && seed > 0 && seed <= 0xffffffff);
const hash = data => createHash("sha256").update(data).digest("hex");
const pkg = readFileSync(archive);
const packageHash = hash(pkg);
assert.equal(packageHash, "e0848d3682b4d85308d10f7993fe9d907731bddb283304ea3fba9b591eb2433a");
const library = execFileSync("tar", ["-xzOf", "-", "package/global/beepbox_synth.js"], {
    input: pkg, encoding: "utf8",
});

// xorshift32. Keep the renderer's noise table and random phase state private to each run.
let state = seed;
let draws = 0;
function random() {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    draws++;
    return (state >>> 0) / 4294967296;
}
const math = Object.create(Math);
Object.defineProperty(math, "random", { value: random });
const { Song, Synth } = runInNewContext(library + "\nbeepbox", { Math: math });

const timbres = ["chip", "FM", "harmonics", "PWM", "Picked String", "noise", "spectrum", "drumset"];
const channels = timbres.map((type, index) => {
    const pitch = index < 5;
    const notes = [0, 4, 8, 12].map((tick, step) => ({
        pitches: [pitch ? 36 + step * 2 : 2 + step],
        points: [{ tick, volume: 100, pitchBend: 0 }, { tick: tick + 3, volume: 75, pitchBend: 0 }],
    }));
    const instrument = { type, volume: 60 };
    if (type === "noise") instrument.wave = "white";
    if (type === "FM") instrument.operators = [{ amplitude: 12 }, { amplitude: 5 }];
    return {
        type: pitch ? "pitch" : "drum", instruments: [instrument], patterns: [{ notes }],
        sequence: Array.from({ length: 16 }, (_, bar) => Math.floor(bar / 2) === index ? 1 : 0),
    };
});
const fixture = {
    format: "BeepBox", version: 9, beatsPerBar: 4, ticksPerBeat: 4, beatsPerMinute: 120,
    introBars: 2, loopBars: 12, channels,
};
const song = new Song();
song.fromJsonObject(fixture);
const encoded = song.toBase64String();
const decoded = new Song(encoded);
const arrangement = decoded.toJsonObject(true, 1, true);
assert.deepEqual(Array.from(arrangement.channels, c => c.instruments[0].type), timbres);
assert.equal(decoded.barCount, 16);
const synth = new Synth(decoded);
synth.samplesPerSecond = rate;
synth.computeDelayBufferSizes();
synth.loopRepeatCount = 0;
synth.snapToStart();
const frames = Math.round(synth.getSamplesPerBar() * synth.getTotalBars(true, true));
assert.equal(frames, rate * 32);
const left = new Float32Array(frames);
const right = new Float32Array(frames);
synth.synthesize(left, right, frames, true);
const bytes = Buffer.alloc(frames * 8);
for (let i = 0; i < frames; i++) {
    bytes.writeFloatLE(left[i], i * 8);
    bytes.writeFloatLE(right[i], i * 8 + 4);
}
console.error(JSON.stringify({
    node: process.version, v8: process.versions.v8, platform: process.platform, arch: process.arch,
    package_sha256: packageHash, library_sha256: hash(library), score_sha256: hash(encoded),
    rate, frames, timbres, seed, random_draws: draws, f32le_sha256: hash(bytes),
}));
process.stdout.write(bytes);
