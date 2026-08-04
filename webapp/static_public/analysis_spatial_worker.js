(function () {
  "use strict";

  const ANALYSIS_RUNTIME_CACHE_KEY = "2026-08-03-analysis-visual-evidence-dashboard-v2-2-r4";

  let spatialApi = self.UfoAnalysisSpatial || null;
  let executionEpoch = 0;
  let artifacts = {
    edges: [],
    spatialPoints: [],
    configurationPoints: [],
    configurationEdges: [],
    contextNeighbors: [],
    facilities: [],
    relationships: [],
    codebooks: {},
    readiness: {},
    artifactHashes: {},
  };

  function ensureSpatialApi() {
    if (spatialApi && typeof spatialApi.computeSpatialAnalysis === "function") return spatialApi;
    if (typeof importScripts === "function") {
      importScripts("./analysis_spatial.js?v=" + ANALYSIS_RUNTIME_CACHE_KEY);
      spatialApi = self.UfoAnalysisSpatial || null;
    }
    if (!spatialApi || typeof spatialApi.computeSpatialAnalysis !== "function") {
      throw new Error("Analysis spatial statistics module is unavailable.");
    }
    return spatialApi;
  }

  function errorMessage(errorValue) {
    return errorValue && errorValue.message ? errorValue.message : String(errorValue || "Spatial analysis failed.");
  }

  self.onmessage = function (event) {
    const message = event && event.data || {};
    try {
      if (message.type === "initializeSpatialAnalysis") {
        const api = ensureSpatialApi();
        executionEpoch = Number(message.executionEpoch) || 0;
        artifacts = {
          edges: Array.isArray(message.edges) ? message.edges : [],
          spatialPoints: Array.isArray(message.spatialPoints) ? message.spatialPoints : [],
          configurationPoints: Array.isArray(message.configurationPoints) ? message.configurationPoints : [],
          configurationEdges: Array.isArray(message.configurationEdges) ? message.configurationEdges : [],
          contextNeighbors: Array.isArray(message.contextNeighbors) ? message.contextNeighbors : [],
          facilities: Array.isArray(message.facilities) ? message.facilities : [],
          relationships: Array.isArray(message.relationships) ? message.relationships : [],
          codebooks: message.codebooks && typeof message.codebooks === "object" ? message.codebooks : {},
          readiness: message.readiness && typeof message.readiness === "object" ? message.readiness : {},
          artifactHashes: message.artifactHashes && typeof message.artifactHashes === "object"
            ? message.artifactHashes
            : {},
        };
        self.postMessage({
          type: "spatialAnalysisReady",
          executionEpoch,
          estimatorVersion: api.ESTIMATOR_VERSION,
          rowCounts: {
            neighbors: artifacts.edges.length,
            spatialPoints: artifacts.spatialPoints.length,
            configurationPoints: artifacts.configurationPoints.length,
            configurationNeighbors: artifacts.configurationEdges.length,
            contextNeighbors: artifacts.contextNeighbors.length,
            facilities: artifacts.facilities.length,
            relationships: artifacts.relationships.length,
          },
        });
        return;
      }
      if (message.type !== "computeSpatialAnalysis") return;
      const api = ensureSpatialApi();
      const baselineMode = String(message.baselineMode || "other_dates_balanced");
      const wholeCorpusStructure = String(message.analysisMode || "") === "whole_corpus_structure" ||
        String(message.comparisonState || "") === "whole_corpus_structure";
      const inferenceEnabled = message.inferenceEnabled !== false &&
        (wholeCorpusStructure || baselineMode !== "full_catalog");
      const result = api.computeSpatialAnalysis({
        rows: Array.isArray(message.rows) ? message.rows : [],
        edges: artifacts.edges,
        spatialPoints: artifacts.spatialPoints,
        configurationPoints: artifacts.configurationPoints,
        configurationEdges: artifacts.configurationEdges,
        contextNeighbors: artifacts.contextNeighbors,
        facilities: artifacts.facilities,
        relationships: artifacts.relationships,
        codebooks: artifacts.codebooks,
        readiness: artifacts.readiness,
        eligibilityFunnel: message.eligibilityFunnel && typeof message.eligibilityFunnel === "object"
          ? message.eligibilityFunnel
          : null,
        artifactHashes: artifacts.artifactHashes,
        seed: String(message.seed || "catalog"),
        baselineMode,
        analysisMode: String(message.analysisMode || "cohort_comparison"),
        comparisonState: String(message.comparisonState || (baselineMode === "full_catalog" ? "descriptive_overlap" : "inferential")),
        inferenceEnabled,
        permutationCount: message.permutationCount,
        bootstrapCount: message.bootstrapCount,
        minimumStratumSize: message.minimumStratumSize,
      });
      result.baselineMode = baselineMode;
      result.analysisMode = String(message.analysisMode || result.analysisMode || "cohort_comparison");
      result.comparisonState = String(message.comparisonState || result.comparisonState || (baselineMode === "full_catalog" ? "descriptive_overlap" : "inferential"));
      result.inferenceEnabled = inferenceEnabled;
      self.postMessage({
        type: "spatialAnalysisComputed",
        executionEpoch,
        jobId: String(message.jobId || ""),
        cancellationGeneration: Number(message.cancellationGeneration) || 0,
        estimatorVersion: api.ESTIMATOR_VERSION,
        result,
      });
    } catch (error) {
      self.postMessage({
        type: "spatialAnalysisError",
        executionEpoch,
        jobId: String(message.jobId || ""),
        cancellationGeneration: Number(message.cancellationGeneration) || 0,
        errorCode: "spatial_analysis_failed",
        error: errorMessage(error),
      });
    }
  };
})();
