(function () {
  "use strict";

  let spatialApi = self.UfoAnalysisSpatial || null;
  let executionEpoch = 0;
  let artifacts = {
    edges: [],
    facilities: [],
    readiness: {},
    artifactHashes: {},
  };

  function ensureSpatialApi() {
    if (spatialApi && typeof spatialApi.computeSpatialAnalysis === "function") return spatialApi;
    if (typeof importScripts === "function") {
      importScripts("./analysis_spatial.js");
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
          facilities: Array.isArray(message.facilities) ? message.facilities : [],
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
            facilities: artifacts.facilities.length,
          },
        });
        return;
      }
      if (message.type !== "computeSpatialAnalysis") return;
      const api = ensureSpatialApi();
      const baselineMode = String(message.baselineMode || "other_dates_balanced");
      const inferenceEnabled = message.inferenceEnabled !== false && baselineMode !== "full_catalog";
      const result = api.computeSpatialAnalysis({
        rows: Array.isArray(message.rows) ? message.rows : [],
        edges: artifacts.edges,
        facilities: artifacts.facilities,
        readiness: artifacts.readiness,
        artifactHashes: artifacts.artifactHashes,
        seed: String(message.seed || "catalog"),
        baselineMode,
        inferenceEnabled,
        permutationCount: message.permutationCount,
        bootstrapCount: message.bootstrapCount,
        minimumStratumSize: message.minimumStratumSize,
      });
      result.baselineMode = baselineMode;
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
