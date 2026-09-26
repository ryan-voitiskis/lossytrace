"use strict";

(() => {
  const core = globalThis.LOSSYTRACE_PAIRED_STATE;
  const fixtures = globalThis.LOSSYTRACE_PAIRED_FIXTURES;
  const byId = (id) => document.getElementById(id);
  const positions = ["A", "B"];
  const inputs = { A: byId("grade-a"), B: byId("grade-b") };
  const statuses = { A: byId("grade-a-status"), B: byId("grade-b-status") };
  let index = 0;
  let events = [];
  let ended = false;
  let failed = false;
  const records = [];

  if (!core || !Array.isArray(fixtures) || fixtures.length !== 2 || fixtures.some((item) =>
    item.state !== "generated_synthetic_assignment_only" || item.fixture_only !== true)) {
    byId("choice-field").disabled = true;
    byId("end-incomplete").disabled = true;
    byId("trial-status").textContent = "Unsupported fixture. This interface is unavailable.";
    return;
  }

  function append(event) {
    if (ended || failed) return false;
    const next = [...events, { sequence: events.length, ...event }];
    try {
      core.reduce(next);
    } catch {
      failed = true;
      byId("choice-field").disabled = true;
      byId("grade-field").disabled = true;
      byId("submit-pair").disabled = true;
      byId("trial-status").textContent = "Event sequence or limit failed. End this trial incomplete; submission is unavailable.";
      return false;
    }
    events = next;
    return true;
  }

  function refreshGrades() {
    const state = core.reduce(events);
    const valid = positions.every((p) => core.gradeTicks(inputs[p].value) !== null);
    byId("submit-pair").disabled = ended || failed || state.forced_choice_position === null || !valid;
  }

  document.querySelectorAll("input[name=choice]").forEach((radio) => {
    radio.addEventListener("change", () => {
      if (!ended && core.reduce(events).forced_choice_position === null) byId("lock-choice").disabled = false;
    });
  });
  byId("lock-choice").addEventListener("click", () => {
    if (ended || core.reduce(events).forced_choice_position !== null) return;
    const selected = document.querySelector("input[name=choice]:checked");
    if (!selected) return;
    if (!append({ kind: "lock_choice", position: selected.value })) return;
    byId("choice-field").disabled = true;
    byId("grade-field").disabled = false;
    byId("choice-status").textContent = `Choice ${selected.value} locked. Grade both candidates; no correctness feedback is shown.`;
    inputs.A.focus();
  });

  positions.forEach((position) => {
    inputs[position].addEventListener("input", () => {
      if (ended || core.reduce(events).forced_choice_position === null) return;
      const ticks = core.gradeTicks(inputs[position].value);
      inputs[position].setAttribute("aria-invalid", String(ticks === null && inputs[position].value !== ""));
      statuses[position].textContent = ticks === null ? "Not entered: use 1.0–5.0 in tenths" : `Entered ${(ticks / 10).toFixed(1)}`;
      // Invalid drafts disable submission, even if a previous valid grade exists.
      // The current DOM values are revalidated and synchronized on submission.
      if (ticks !== null && core.reduce(events).grade_ticks_by_position[position] !== ticks) {
        append({ kind: "grade", position, grade_ticks: ticks });
      }
      refreshGrades();
    });
  });

  function finish(submit) {
    if (ended) return;
    if (submit) {
      if (failed || core.reduce(events).forced_choice_position === null) return;
      const ticks = positions.map((p) => core.gradeTicks(inputs[p].value));
      if (ticks.some((value) => value === null)) { refreshGrades(); return; }
      positions.forEach((position, i) => {
        if (core.reduce(events).grade_ticks_by_position[position] !== ticks[i]) append({ kind: "grade", position, grade_ticks: ticks[i] });
      });
      if (!append({ kind: "submit" })) return;
    }
    ended = true;
    byId("choice-field").disabled = true;
    byId("grade-field").disabled = true;
    byId("end-incomplete").disabled = true;
    byId("submit-pair").disabled = true;
    const accepted = core.reduce(events).grade_ticks_by_position;
    const finalGrades = Object.fromEntries(positions.map((p) => {
      const draft = core.gradeTicks(inputs[p].value);
      return [p, draft !== null && draft === accepted[p] ? draft : null];
    }));
    records.push({
      schema_version: 1,
      state: "synthetic_paired_ui_events_only",
      fixture_only: true,
      human_collection_authorized: false,
      presentation: fixtures[index],
      events: events.map((event) => ({ ...event })),
      final_grade_ticks_by_position: finalGrades,
    });
    byId("synthetic-record").textContent = JSON.stringify(records, null, 2);
    byId("record-section").hidden = false;
    byId("next-trial").hidden = index === fixtures.length - 1;
    byId("trial-status").textContent = submit ? "Synthetic pair submitted and locked. This is not listener evidence." : "Trial ended incomplete. Entered events remain explicit; missing grades are not imputed.";
  }
  byId("submit-pair").addEventListener("click", () => finish(true));
  byId("end-incomplete").addEventListener("click", () => finish(false));
  byId("next-trial").addEventListener("click", () => {
    if (!ended || index >= fixtures.length - 1) return;
    index += 1;
    events = [];
    ended = false;
    failed = false;
    byId("trial-number").textContent = String(index + 1);
    byId("choice-field").disabled = false;
    byId("grade-field").disabled = true;
    byId("lock-choice").disabled = true;
    byId("submit-pair").disabled = true;
    byId("end-incomplete").disabled = false;
    byId("next-trial").hidden = true;
    document.querySelectorAll("input[name=choice]").forEach((radio) => { radio.checked = false; });
    positions.forEach((p) => { inputs[p].value = ""; inputs[p].removeAttribute("aria-invalid"); statuses[p].textContent = "Not entered"; });
    byId("choice-status").textContent = "No choice locked. Grades are unavailable.";
    byId("trial-status").textContent = "This test validates controls only, not playback or perception.";
  });
})();
