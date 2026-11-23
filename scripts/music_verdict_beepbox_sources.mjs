// Inspect the published arrangements as notation. No playback or PCM rendering.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";
import { runInNewContext } from "node:vm";

const root = process.argv[2];
const bindings = {
    "four-original-midi-loops.html": "4fea1d4c7728e39e018101b724286ccec63156bf1c18fa37b730ca77fb9a6234",
    "random-retro-ish-music-tracks.html": "c39fcb3c78487a47b4f3b8c9a41c0f4e448affa0bd4a7b08c54240574c10ce27",
    "_beepbox.txt": "1af77141204647c9c4f6590daa5b9a4bf98b08cffaee2f984ca1dec266a77ba9",
    "beepbox-4.2.0.tgz": "e0848d3682b4d85308d10f7993fe9d907731bddb283304ea3fba9b591eb2433a",
};
const sha256 = data => createHash("sha256").update(data).digest("hex");
const files = {};
for (const [name, digest] of Object.entries(bindings)) {
    files[name] = readFileSync(join(root, name));
    assert.equal(sha256(files[name]), digest, name);
}
const library = execFileSync("tar", ["-xzOf", "-", "package/global/beepbox_synth.js"], {
    input: files["beepbox-4.2.0.tgz"], encoding: "utf8",
});
const { Song } = runInNewContext(library + "\nbeepbox", Object.create(null));
const revisions = {
    8: { folder: "legacy", rev: "1401fcf36520fcc1c489b3c9de48bf2699930524",
         build: "2856f04d31035bc72f5b69deb64cf6c9bcd9666b6910c678665492beebc005cf" },
    9: { folder: "v4_0", rev: "5c57650cabbe8dba6e21a533bb4ce7572f9000ac",
         build: "baedc3f8b1150418c42038d67c369895ccf3626bf7c00c2ef328929f4442acf0" },
};
const nativeDecoders = {};
const require = createRequire(import.meta.url);
for (const [version, revision] of Object.entries(revisions)) {
    const dir = resolve(root, revision.folder, "upstream-build");
    const manifest = readdirSync(dir).sort().map(name =>
        name + " " + sha256(readFileSync(join(dir, name))) + "\n").join("");
    assert.equal(sha256(manifest), revision.build);
    nativeDecoders[version] = require(join(dir, "synth.js")).Song;
}
const types = new Set(["chip", "FM", "noise", "spectrum", "drumset", "harmonics", "PWM",
                       "Picked String", "supersaw"]);
const items = [];
const missing = [];

// Compare the notes actually sequenced by each release, excluding sound design.
function noteDigest(data) {
    const timeline = data.channels.map(channel => channel.sequence.map(pattern =>
        pattern ? channel.patterns[pattern - 1].notes.map(note => [
            note.pitches, note.points.map(point => [point.tick, point.pitchBend]),
        ]) : []));
    return sha256(JSON.stringify([data.key, data.beatsPerMinute, data.beatsPerBar,
        data.ticksPerBeat, data.introBars, data.loopBars, timeline]));
}

function inspect(author, title, link) {
    const url = new URL(link);
    assert.match(url.origin, /^https:\/\/(www\.)?beepbox\.co$/);
    assert.equal(url.pathname, "/");
    assert.equal(url.search, "");
    const score = url.hash.slice(1);
    assert.match(score, /^[89][A-Za-z0-9_-]+$/);
    const song = new Song(score);
    const data = song.toJsonObject(true, 1, true);
    const native = new nativeDecoders[score[0]](score).toJsonObject(true, 1, true);
    assert.equal(native.version, Number(score[0]));
    const notes = noteDigest(data);
    assert.equal(notes, noteDigest(native), title);
    const instruments = new Set();
    const occupied = new Set();
    let lastNoteBeat = 0;
    for (const channel of data.channels) {
        assert.equal(channel.sequence.length, song.barCount);
        for (const instrument of channel.instruments) {
            assert.ok(types.has(instrument.type), instrument.type);
            instruments.add(instrument.type);
        }
        channel.sequence.forEach((pattern, bar) => {
            if (!pattern) return;
            for (const note of channel.patterns[pattern - 1].notes) {
                occupied.add(bar);
                const tick = note.points.at(-1).tick;
                assert.ok(tick > 0 && tick <= data.ticksPerBeat * data.beatsPerBar);
                lastNoteBeat = Math.max(lastNoteBeat, bar * data.beatsPerBar + tick / data.ticksPerBeat);
            }
        });
    }
    assert.ok(occupied.size);
    const seconds = song.barCount * data.beatsPerBar * 60 / data.beatsPerMinute;
    items.push({
        author, title, score_sha256: sha256(score), version: Number(score[0]), note_sha256: notes,
        channels: data.channels.length, instruments: [...instruments].sort(),
        bars: song.barCount, occupied_bars: occupied.size, final_occupied_bar: Math.max(...occupied) + 1,
        intro_bars: data.introBars, loop_bars: data.loopBars,
        beats_per_bar: data.beatsPerBar, bpm: data.beatsPerMinute, one_pass_seconds: seconds,
        last_note_end_seconds: lastNoteBeat * 60 / data.beatsPerMinute,
        reaches_30s: seconds >= 30,
    });
}

const first = files["four-original-midi-loops.html"].toString();
assert.ok(first.includes("/users/tapatilorenzo") && first.includes("creativecommons.org/publicdomain/zero/1.0/"));
for (const match of first.matchAll(/<strong>([^<]+)<\/strong>[^<]*<a title="Editable Source" href="([^"]+)"/g)) {
    inspect("tapatilorenzo", match[1], match[2]);
}
assert.equal(items.length, 4);
const second = files["random-retro-ish-music-tracks.html"].toString();
assert.ok(second.includes("/users/cubee") && second.includes("creativecommons.org/licenses/by/4.0/")
          && second.includes("https://opengameart.org/sites/default/files/_beepbox.txt"));
for (const section of files["_beepbox.txt"].toString().trim().split(/\r?\n\s*\r?\n/)) {
    const lines = section.trim().split(/\r?\n/);
    assert.equal(lines.length, 2);
    assert.match(lines[0], /^-- .+/);
    const title = lines[0].slice(3).trim();
    if (lines[1].trim() === "lost") missing.push(title);
    else inspect("cubee", title, lines[1].trim());
}
console.log(JSON.stringify({ bindings, decoder_js_sha256: sha256(library), revisions, items,
                             cubee_listed_missing: missing }, null, 2));
