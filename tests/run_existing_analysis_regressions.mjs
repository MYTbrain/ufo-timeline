// Run retained baseline tests against the repaired release assets without
// copying a corpus, restoring historical payloads, or overwriting other checkouts.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const shared = "C:/Users/jarod/Desktop/UFO Timeline map tool";
const product = path.resolve(".").replaceAll("\\", "/");
for (const name of ["test_analysis_stats.mjs", "test_analysis_view.mjs", "test_analysis_spatial_worker_concurrency.mjs"]) {
  const original = path.join(shared, "tests", name);
  let source = fs.readFileSync(original, "utf8");
  source = source.replaceAll("createRequire(import.meta.url)", `createRequire(${JSON.stringify(pathToFileURL(original).href)})`);
  for (const asset of ["analysis_stats.js", "analysis_view.js", "analysis_spatial.js", "analysis_spatial_worker.js", "catalog_filter_worker.js"]) {
    source = source.replaceAll(`../webapp/static_public/${asset}`, `${product}/${asset}`);
    source = source.replaceAll(`webapp/static_public/${asset}`, `${product}/${asset}`);
  }
  // The baseline fixture is still a single collection. Its wording must follow
  // the repaired source-aware renderer rather than classifying every missing
  // or nonpositive count as a source sentinel.
  if (name === "test_analysis_view.mjs") {
    source = source.replace("10 source sentinels remain excluded", "10 unresolved or nonpositive values remain untyped");
    source = source.replace(".*NUFORC.*never coerced.*Credential suffixes are metadata", ".*documented source-field contracts.*never coerced.*Credential suffixes are metadata");
    // The accepted renderer exports the snapshot that produced its result,
    // rather than relabeling that result with newer pending shared controls.
    source = source.replaceAll("controller.renderAnalysisResult(result);",
      "controller.renderAnalysisResult(result, { filterSnapshot: controller.callbacks.getFilterSnapshot() });");
    source = source.replace('document.getElementById("analysis-export-json").emit("click");\nassert.equal(evidenceExports.at(-1).format, "json");',
      'const renderedSnapshotCallback = controller.callbacks.getFilterSnapshot;\ncontroller.callbacks.getFilterSnapshot = () => ({ generation: 13, dateRange: { start: "1955-01-01", end: "1955-01-31" } });\ndocument.getElementById("analysis-export-json").emit("click");\nassert.equal(evidenceExports.at(-1).format, "json");');
    source = source.replace("assert.equal(evidenceExports.at(-1).package.filterSnapshot.generation, 12);",
      'assert.equal(controller.callbacks.getFilterSnapshot().generation, 13, "the shared controls already describe the pending cohort");\nassert.equal(evidenceExports.at(-1).package.filterSnapshot.generation, 12, "the export retains the rendered cohort");\ncontroller.callbacks.getFilterSnapshot = renderedSnapshotCallback;');
  }
  if (name === "test_analysis_spatial_worker_concurrency.mjs") {
    source = source.replaceAll("2026-08-12-context-evidence-v2", "2026-10-08-workspace-analysis-release-v1");
  }
  console.log(`Retained regression: ${name}`);
  try {
    await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
  } catch (error) {
    console.error(`${name}: ${error.message}`);
    process.exitCode = 1;
    break;
  }
}
