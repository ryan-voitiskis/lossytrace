"use strict";

// This reducer has no browser, media, identity, network or storage dependency.
// It mirrors the frozen Python paired-rating event rules, not delivery checks.
(() => {
  const positions = ["A", "B"];
  const fields = (value, names) => {
    if (!value || typeof value !== "object" || Array.isArray(value) ||
        JSON.stringify(Object.keys(value).sort()) !== JSON.stringify([...names].sort())) {
      throw new Error("Unexpected event fields");
    }
  };
  const position = (value) => {
    if (!positions.includes(value)) throw new Error("Unknown candidate position");
    return value;
  };
  function reduce(events) {
    if (!Array.isArray(events) || events.length > 100) throw new Error("Invalid event stream");
    let choice = null;
    const grades = { A: null, B: null };
    let submitted = false;
    events.forEach((event, sequence) => {
      if (submitted || !event || !Number.isInteger(event.sequence) || event.sequence !== sequence) {
        throw new Error("Event sequence differs or trial already submitted");
      }
      if (event.kind === "lock_choice") {
        fields(event, ["sequence", "kind", "position"]);
        if (choice !== null) throw new Error("Forced choice already locked");
        choice = position(event.position);
      } else if (event.kind === "grade") {
        fields(event, ["sequence", "kind", "position", "grade_ticks"]);
        if (choice === null) throw new Error("Forced choice must precede grades");
        position(event.position);
        if (!Number.isInteger(event.grade_ticks) || event.grade_ticks < 10 || event.grade_ticks > 50) {
          throw new Error("Grade must be integer ticks from 10 to 50");
        }
        grades[event.position] = event.grade_ticks;
      } else if (event.kind === "submit") {
        fields(event, ["sequence", "kind"]);
        if (choice === null || positions.some((p) => grades[p] === null)) {
          throw new Error("Both explicit grades are required");
        }
        submitted = true;
      } else {
        throw new Error("Unknown event kind");
      }
    });
    return { forced_choice_position: choice, grade_ticks_by_position: grades, trial_status: submitted ? "submitted" : "incomplete" };
  }
  function gradeTicks(text) {
    // Empty/partial input never becomes zero or a default response.
    if (typeof text !== "string" || !/^[1-5](?:\.[0-9])?$/.test(text.trim())) return null;
    const ticks = Math.round(Number(text) * 10);
    return ticks <= 50 ? ticks : null;
  }
  const api = Object.freeze({ reduce, gradeTicks });
  globalThis.LOSSYTRACE_PAIRED_STATE = api;
  if (typeof module !== "undefined") module.exports = api;
})();
