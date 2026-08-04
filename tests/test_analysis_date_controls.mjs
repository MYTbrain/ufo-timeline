import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

import {
  isoToOrdinal,
  normalizeDateBoundary,
} from "../webapp/static/app-utils.mjs";

const appSource = readFileSync(new URL("../webapp/static_public/app.js", import.meta.url), "utf8");
const indexSource = readFileSync(new URL("../webapp/static_public/index.html", import.meta.url), "utf8");

function extractNamedFunctionSource(source, name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `missing function ${name}`);
  const openingBrace = source.indexOf("{", start);
  let depth = 0;
  for (let index = openingBrace; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, index + 1);
    }
  }
  assert.fail(`unterminated function ${name}`);
}

function loadNamedFunction(name, contextOverrides = {}) {
  const context = vm.createContext({
    Array,
    Boolean,
    JSON,
    Map,
    Math,
    Number,
    Object,
    Set,
    String,
    ...contextOverrides,
  });
  vm.runInContext(
    `${extractNamedFunctionSource(appSource, name)}\nthis.__functionUnderTest = ${name};`,
    context
  );
  return context.__functionUnderTest;
}

const validateCandidate = loadNamedFunction("validateDateRangeCandidate", {
  isoToOrdinal,
  normalizeDateBoundary,
});

const valid = validateCandidate("2020-01", "2020-02");
assert.equal(valid.valid, true);
assert.equal(valid.startIso, "2020-01-01");
assert.equal(valid.endIso, "2020-02-29");
assert.ok(valid.startOrdinal < valid.endOrdinal);

const reversed = validateCandidate("2020-01-01", "2010-01-01");
assert.equal(reversed.valid, false);
assert.match(reversed.message, /Start date must be on or before End date/);

const malformed = validateCandidate("2020-13", "2021-01-01");
assert.equal(malformed.valid, false);
assert.match(malformed.message, /valid YYYY-MM-DD/);

function buildCommitHarness() {
  const counters = {
    clearPending: 0,
    invalidatePlayback: 0,
    schedule: 0,
    setTimeRange: 0,
  };
  const feedback = { analysis: [], shared: [] };
  const committedRanges = [];
  const runtime = { timeInputTimerId: 41 };
  const commit = loadNamedFunction("commitDateInputs", {
    clearPendingDateInputEdits() { counters.clearPending += 1; },
    els: {
      startDateInput: { value: "1900-01-01" },
      endDateInput: { value: "2025-12-31" },
    },
    invalidatePlaybackForTimeChange() { counters.invalidatePlayback += 1; },
    runtime,
    scheduleCurrentTimeRangeState() { counters.schedule += 1; },
    setAnalysisDateRangeFeedback(message) { feedback.analysis.push(message); },
    setDateRangeFeedback(message) { feedback.shared.push(message); },
    setTimeRange(startOrdinal, endOrdinal, options) {
      counters.setTimeRange += 1;
      committedRanges.push({ startOrdinal, endOrdinal, options });
    },
    validateDateRangeCandidate: validateCandidate,
    window: { clearTimeout() {} },
  });
  return { commit, committedRanges, counters, feedback, runtime };
}

const invalidHarness = buildCommitHarness();
const invalidResult = invalidHarness.commit({
  startValue: "2020-01-01",
  endValue: "2010-01-01",
  feedbackScope: "analysis",
});
assert.equal(invalidResult, false);
assert.equal(invalidHarness.counters.setTimeRange, 0, "an invalid Analysis draft cannot mutate shared date state");
assert.equal(invalidHarness.counters.schedule, 0, "an invalid Analysis draft cannot schedule a recomputation");
assert.equal(invalidHarness.counters.invalidatePlayback, 0, "an invalid Analysis draft preserves playback");
assert.equal(invalidHarness.counters.clearPending, 0, "the invalid local draft remains editable");
assert.equal(invalidHarness.feedback.shared.length, 0, "the valid shared controls are not marked invalid");
assert.match(invalidHarness.feedback.analysis[0], /last valid range is still active/);

const validHarness = buildCommitHarness();
const validResult = validHarness.commit({
  startValue: "2010-01-01",
  endValue: "2020-01-01",
  feedbackScope: "analysis",
});
assert.equal(validResult, true);
assert.equal(validHarness.counters.setTimeRange, 1, "a valid Analysis commit mutates shared date state once");
assert.equal(validHarness.counters.schedule, 1, "a valid Analysis commit schedules exactly one recomputation");
assert.equal(validHarness.counters.invalidatePlayback, 1);
assert.equal(validHarness.counters.clearPending, 1);
assert.equal(validHarness.committedRanges.length, 1);
assert.equal(validHarness.feedback.shared.at(-1), "");

assert.match(
  appSource,
  /input\.addEventListener\("blur", function \(event\) \{\s*if \(isAnalysisDateInputElement\(input\)\) \{\s*markDateInputPending\(input\);\s*return;/,
  "leaving an Analysis date field must not commit an interim range"
);
assert.match(
  appSource,
  /analysisApplyDateButton\.addEventListener\("click", function \(\) \{\s*if \(commitAnalysisDateInputs\(\)/,
  "Apply validates the two Analysis draft fields as one range"
);
assert.match(
  appSource,
  /if \(isAnalysisDateInputElement\(input\)\) \{\s*markDateInputPending\(input\);\s*commitAnalysisDateInputs\(\);\s*return;/,
  "Enter commits the Analysis draft through the same atomic path"
);
assert.match(
  indexSource,
  /id="analysis-date-feedback"[^>]*role="alert"[^>]*aria-live="assertive"/,
  "invalid Analysis ranges use an immediate inline alert"
);

console.log("Analysis sticky date control assertions passed");
