// Render the two preselected, digest-bound authored scores, from the retained snapshot only.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";

const [root, title] = process.argv.slice(2);
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const manifest = JSON.parse(readFileSync(new URL("../research/music-verdict-v1/beepbox-arrangements-20261123.json", import.meta.url)));
const files = {};
for (const [path, digest] of Object.entries(manifest.bindings)) {
    files[path] = readFileSync(join(root, path));
    assert.equal(sha(files[path]), digest, path);
}
const scoreHashes = {
    "Confrontation": "12947bd27b0a4f935bf845bd9faadcd9cb34035e085f6731ce27ecaee2ab9764",
    "radio city": "0f6ced7d163dabd2c789cadb42537887cfbd7947374e96760a98f25fa5cb3c25",
};
assert.ok(Object.hasOwn(scoreHashes, title));
const entry = manifest.items.find(item => item.score_sha256 === scoreHashes[title]);
assert.equal(entry.title, title);
const scoreText = title === "Confrontation" ? "four-original-midi-loops.html" : "_beepbox.txt";
const scores = Array.from(files[scoreText].toString().matchAll(/beepbox\.co\/#([89][A-Za-z0-9_-]+)/g), m => m[1]);
const score = scores.find(value => sha(value) === entry.score_sha256);
assert.ok(score, "expected published score");
const library = execFileSync("tar", ["-xzOf", "-", "package/global/beepbox_synth.js"], {
    input: files["beepbox-4.2.0.tgz"], encoding: "utf8",
});
assert.equal(sha(library), manifest.decoder_js_sha256);
const seed = 20261123;
let state = seed;
let draws = 0;
const math = Object.create(Math);
Object.defineProperty(math, "random", { value() {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    draws++;
    return (state >>> 0) / 4294967296;
} });
const { Song, Synth } = runInNewContext(library + "\nbeepbox", { Math: math });
const synth = new Synth(new Song(score));
synth.samplesPerSecond = 44100;
synth.computeDelayBufferSizes();
synth.loopRepeatCount = 0;
synth.snapToStart();
const frames = Math.round(synth.getSamplesPerBar() * synth.getTotalBars(true, true));
assert.equal(frames, Math.round(entry.one_pass_seconds * 44100));
const left = new Float32Array(frames);
const right = new Float32Array(frames);
synth.synthesize(left, right, frames, true);
const bytes = Buffer.alloc(8 * frames);
for (let i = 0; i < frames; i++) {
    bytes.writeFloatLE(left[i], 8 * i);
    bytes.writeFloatLE(right[i], 8 * i + 4);
}
console.error(JSON.stringify({ title, author: entry.author, score_sha256: entry.score_sha256,
    node: process.version, v8: process.versions.v8, platform: process.platform, arch: process.arch,
    synth_sha256: sha(library), seed, random_draws: draws, rate: 44100, frames, f32le_sha256: sha(bytes) }));
process.stdout.write(bytes);
