// Render the shipped music modules alone. Node must start with a fixed V8 noise seed.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { join } from "node:path";

assert.deepEqual(process.execArgv, ["--random-seed=20260927"]);
const [base, output] = process.argv.slice(2);
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const bindings = {
    "LICENSE": "b6bb9e1e8f0842643ede8c2568113b4ef77f18b734e8f9483d0439cf4d04c13c",
    "text/src/music.ts": "3474df775eee55526ac4cf2556966f32028af7ae4aaa0f8c03d269bda20a8303",
    "text/src/math/scalar.ts": "5cffa1f3e4ed33fe489d147b7c8b7cbc64d17eb6b1daa4efe0bbfa5e5cd44ecb",
    "text/src/soundbox/song.js": "a836f598ad0a97e9d5c044163eb245e88796fb6adcf823f1e279e6c13ccf3489",
    "text/src/soundbox/player.ts": "cb1a652f44ba2db25378720f2ba0bc9cda4399731165334bf9a76ebb07bc9894",
};
const sources = {};
for (const [path, digest] of Object.entries(bindings)) {
    const bytes = readFileSync(join(base, path));
    assert.equal(sha(bytes), digest, path);
    sources[path] = bytes.toString("utf8");
}
// Preserve both modules and the project's Math.random dependency. Rewrite only import paths.
const dataUrl = source => "data:text/javascript;base64," + Buffer.from(source).toString("base64");
const player = sources["text/src/soundbox/player.ts"];
const code = stripTypeScriptTypes(player)
    .replace("'../math/scalar'", JSON.stringify(dataUrl(stripTypeScriptTypes(sources["text/src/math/scalar.ts"]))))
    .replace("'./song'", JSON.stringify(dataUrl(sources["text/src/soundbox/song.js"])));
const { musicInit, musicGenerate, musicCreateWave } = await import(dataUrl(code));
musicInit();
for (let channel = 1; channel <= 4; channel++) assert.equal(musicGenerate(), channel / 4);
const wave = Buffer.from(musicCreateWave());
assert.equal(wave.length, 44 + 5292000 * 4);
assert.equal(wave.readUInt32LE(24), 44100);
assert.equal(wave.readUInt16LE(22), 2);
assert.equal(wave.readUInt16LE(34), 16);

mkdirSync(output); // Refuse to replace any prior render.
writeFileSync(join(output, "score.wav"), wave);
writeFileSync(join(output, "LICENSE-project.txt"), sources.LICENSE);
writeFileSync(join(output, "NOTICE-player.txt"), player.slice(0, player.indexOf("'use strict'")));
const receipt = { project_commit: "ed6d3e43e1f5460e6f7d3c38d27dd7328b8adff6",
    inputs_sha256: bindings, node: process.version, v8: process.versions.v8, arch: process.arch,
    platform: process.platform, v8_random_seed: 20260927, frames: 5292000, rate_hz: 44100,
    channels: 2, bits_per_sample: 16, wav_sha256: sha(wave), s16le_sha256: sha(wave.subarray(44)) };
writeFileSync(join(output, "render.json"), JSON.stringify(receipt, null, 2) + "\n");
