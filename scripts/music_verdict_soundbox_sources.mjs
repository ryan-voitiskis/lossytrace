// Offline inspection of pinned, declarative musical scores. Game code is never evaluated.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { inflateRawSync } from "node:zlib";

const root = resolve(process.argv[2]);
const sha = b => createHash("sha256").update(b).digest("hex");
const read = (name, digest) => {
    const bytes = readFileSync(join(root, name));
    if (digest) assert.equal(sha(bytes), digest, name);
    return bytes;
};
const queries = {
    soundbox: "273a6216d2fc4caeeb207234fb76c9276c4f83071c8c9898818f33d00a46d036",
    zzfxm: "d3ae53437d86abef2fd4e3e54c092b66750d9cf912b71aba636645e6ffa03ae2",
};
const projects = new Map();
for (const [query, digest] of Object.entries(queries)) {
    const result = JSON.parse(read(query + ".json", digest));
    assert.equal(result.incomplete_results, false);
    assert.equal(result.items.length, result.total_count);
    for (const p of result.items) projects.set(p.full_name, p);
}
const reviewed = [...projects.values()].filter(p => p.license).map(p => p.name).sort();
const commitments = createHash("sha256");
const receipts = new Map();
function checkBlob(bytes, metadata) {
    assert.equal(bytes.length, metadata.size);
    assert.equal(createHash("sha1").update("blob " + bytes.length + "\0").update(bytes).digest("hex"), metadata.sha);
}
for (const name of reviewed) {
    const bytes = read(name + "/receipt.json");
    commitments.update(name + "\0").update(Buffer.from(sha(bytes), "hex"));
    const receipt = JSON.parse(bytes);
    assert.equal(receipt.repo, "js13kGames/" + name);
    const tree = JSON.parse(read(name + "/tree.json", receipt.tree_sha256));
    assert.equal(tree.truncated, false);
    const blobs = new Map(tree.tree.filter(f => f.type === "blob").map(f => [f.path, f]));
    for (const doc of receipt.docs) checkBlob(read(join(name, doc)), blobs.get(doc));
    receipts.set(name, { receipt, blobs });
}
assert.equal(commitments.digest("hex"), "7100b1b71d55909f730b915bdd60c77986f8cbe8d949974386e4b88c961c2802");
const parser = "parser/node_modules/acorn/dist/acorn.mjs";
read(parser, "b4c8c70200e72bae33cf1085e0ecb1e792c1b6924ed50cab817caf14f51bb249");
const { parse } = await import(pathToFileURL(join(root, parser)));

function literal(node) {
    if (node === null) return null; // A sparse row or pattern slot.
    if (node.type === "Literal" && Number.isInteger(node.value)) return node.value;
    if (node.type === "ArrayExpression") return node.elements.map(literal);
    assert.equal(node.type, "ObjectExpression", "score requires a nonliteral expression");
    const obj = Object.create(null);
    for (const p of node.properties) {
        assert.ok(p.type === "Property" && p.kind === "init" && !p.computed && !p.method && !p.shorthand);
        const key = p.key.name;
        assert.ok(typeof key === "string" && !Object.hasOwn(obj, key));
        obj[key] = literal(p.value);
    }
    return obj;
}

function inspect(song) {
    const { rowLen, patternLen, endPattern, numChannels, songData } = Object.fromEntries(
        Object.entries(song).map(([k, v]) => [k.replace(/^_/, ""), v]));
    assert.ok(rowLen > 0 && patternLen > 0 && endPattern >= 0 && numChannels === songData.length);
    const notes = [];
    const channelPrograms = [];
    const expandedPrograms = [];
    songData.forEach((channel, index) => {
        assert.ok(channel.i.length > 0 && channel.i.every(Number.isInteger));
        const schedule = Array.from({ length: endPattern + 1 }, (_, p) => channel.p[p] || 0);
        const playedColumns = [...new Set(schedule.filter(Boolean))].sort((a, b) => a - b);
        const padded = (values, length) => Array.from({ length }, (_, i) => values[i] || 0);
        const columns = playedColumns.map(p => [
            p, padded(channel.c[p - 1].n, 4 * patternLen), padded(channel.c[p - 1].f, 2 * patternLen),
        ]);
        channelPrograms.push([channel.i, schedule, columns]);
        const byId = new Map(columns.map(([id, n, f]) => [id, [n, f]]));
        const empty = [Array(4 * patternLen).fill(0), Array(2 * patternLen).fill(0)];
        expandedPrograms.push([channel.i, schedule.map(p => p ? byId.get(p) : empty)]);
        for (let p = 0; p <= endPattern; p++) {
            const pat = channel.p[p];
            if (!pat) continue;
            const column = channel.c[pat - 1];
            assert.ok(column && column.n.length <= 4 * patternLen);
            column.n.forEach((value, position) => {
                if (value) notes.push([(p * patternLen + position % patternLen) * rowLen,
                                       index, Math.floor(position / patternLen), value]);
            });
        }
    });
    assert.ok(notes.length > 0);
    notes.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
    const frames = (endPattern + 1) * patternLen * rowLen;
    return { rowLen, patternLen, endPattern, numChannels, frames,
             seconds_at_44100: frames / 44100, notes: notes.length,
             last_onset_seconds_at_44100: notes.at(-1)[0] / 44100,
             expanded_program_sha256: sha(JSON.stringify([rowLen, patternLen, endPattern, expandedPrograms])),
             program_sha256: sha(JSON.stringify([rowLen, patternLen, endPattern, channelPrograms])),
             note_event_sha256: sha(JSON.stringify(notes)) };
}
function visit(node, record, output) {
    if (!node || typeof node !== "object") return;
    if (node.type === "ObjectExpression" && node.properties.some(p => ["songData", "_songData"].includes(p.key?.name))) {
        output.push({ ...record, source_line: node.loc.start.line, ...inspect(literal(node)) });
        return;
    }
    for (const child of Object.values(node)) visit(child, record, output);
}
// Named files selected for the case review. Some contain both music and a short cue.
const paths = {
    "island-not-found": "src/soundbox/song.js", "miami-mice": "src/game/lib/soundbox/music_game.js",
    "submersible-warship-2063": "src/js/songs.js", lemmicorns: "src/js/sound/music.js",
    "witchcup1276": "src/b_racesong.js", poopicorn: "src/js/sounds/song.js",
    "tanky-mctankface": "src/sounds/background.ts",
};
const scores = [];
for (const [name, path] of Object.entries(paths)) {
    const { receipt, blobs } = receipts.get(name);
    const bytes = read(join(name, "text", path));
    checkBlob(bytes, blobs.get(path));
    const count = scores.length;
    visit(parse(bytes.toString("utf8"), { ecmaVersion: 2024, sourceType: "module", locations: true }),
          { name, commit: receipt.commit, path, score_file_sha256: sha(bytes) }, scores);
    assert.ok(scores.length > count);
}
const historyRoot = "island-not-found";
for (const path of ["src/math/scalar.ts", "src/music.ts", "src/soundbox/player.ts"]) {
    checkBlob(read(join(historyRoot, "text", path)), receipts.get(historyRoot).blobs.get(path));
}
const history = JSON.parse(read(historyRoot + "/music-history.json",
    "11f4fa7123e9012117d53910b7106bbff83c195ea87fcd544229ded785fc46c6"));
const postMortem = read(historyRoot + "/post-mortem.md", "1df389954ae6bf6f5b10e8a11a9ab77bd13cbe9cca72c92241ed8f0d2aa554b1");
const [, encoded] = postMortem.toString().match(/\[Play\/modify the track\]\(https:\/\/sb\.bitsnbites\.eu\/\?data=([A-Za-z0-9_-]+)\)/);
const packed = Buffer.from(encoded, "base64url");
assert.equal(packed.subarray(0, 6).toString("hex"), "53426f780c02"); // SBox version 12, DEFLATE.
const raw = inflateRawSync(packed.subarray(6), { maxOutputLength: 65536 });
const score = { rowLen: raw.readUInt32LE(0), endPattern: raw.readUInt16LE(4),
                patternLen: raw[6], numChannels: raw[7], songData: [] };
let at = 8;
function take(n) {
    assert.ok(at + n <= raw.length);
    const bytes = Array.from(raw.subarray(at, at + n));
    at += n;
    return bytes;
}
for (let i = 0; i < score.numChannels; i++) {
    const instrument = { i: take(28), p: take(score.endPattern + 1), c: [] };
    for (let k = 0; k < 36; k++)
        instrument.c.push({ n: take(4 * score.patternLen), f: take(2 * score.patternLen) });
    score.songData.push(instrument);
}
assert.equal(at, raw.length);
const editable = inspect(score);
assert.equal(editable.note_event_sha256, scores[0].note_event_sha256);
assert.equal(editable.expanded_program_sha256, scores[0].expanded_program_sha256);
const versions = [];
const historyBindings = createHash("sha256");
for (const commit of history.map(x => x.sha).sort()) {
    const bytes = read(historyRoot + "/history/" + commit + ".js");
    historyBindings.update(commit).update(Buffer.from(sha(bytes), "hex"));
    visit(parse(bytes.toString("utf8"), { ecmaVersion: 2024, sourceType: "module", locations: true }),
          { commit }, versions);
}
assert.equal(historyBindings.digest("hex"), "517a7447540529f81cadc369a8277516d496d76ccd6072ae95bfd62f108d6e8d");
assert.equal(versions.length, history.length);
const chronological = history.slice().reverse().map(c => versions.find(v => v.commit === c.sha));
assert.equal(chronological.at(-1).note_event_sha256, scores[0].note_event_sha256);
console.log(JSON.stringify({ island_editable_project: editable, island_score_history: chronological, distinct_search_hits: projects.size, reviewed_repositories: reviewed.length,
                             arrangements: scores }, null, 2));
