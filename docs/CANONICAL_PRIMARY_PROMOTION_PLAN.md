# Canonical Primary Catalog Promotion Plan

This is the controlled path for promoting the guarded canonical primary catalog and trace runtime from preview-only to default runtime behavior.

Do not use this plan to mutate `data/canonical_full/deduped_events.jsonl`. This plan covers frontend/static runtime defaults only.

## Current State

- Canonical runtime defaults are now promoted in `static_bundle/data/app_config.json`.
- `canonicalWebArtifacts.enabled`, `primaryCatalog`, `traceRuntime`, and `filteredTraceAggregation` are all `true`.
- `static_bundle/data/canonical_web` contains the full-detail promoted payload from `data/canonical_web_remaining_lower_time_format_apply`.
- `data/reports/runtime_integration_readiness_gate.json` reports `default_promoted_ready`.
- The production-like browser smoke passed against the actual promoted `static_bundle` on `8181/9411`.
- Canonical corpus mutation remains separate and has not rewritten `data/canonical_full/deduped_events.jsonl`.

## Promotion Scope

The smallest promotion branch should only change checked-in runtime config after the smoke gates pass.

Candidate config flags:

```json
{
  "canonicalWebArtifacts": {
    "enabled": true,
    "primaryCatalog": true,
    "traceRuntime": true,
    "filteredTraceAggregation": true
  }
}
```

Do not combine this with:

- new dedupe decisions
- canonical corpus mutation
- backend/server changes
- event parser changes
- UI redesign

## Required Pre-Promotion Checks

Run these before changing defaults:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -ExecutionPolicy Bypass -File 'scripts\smoke_guarded_canonical_preview_cdp.ps1' -CanonicalWebDir 'data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_smoke' -PreviewPort 8150 -DebugPort 9384 -TimeoutSeconds 120 -StartupAttempts 3
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -ExecutionPolicy Bypass -File 'scripts\smoke_guarded_canonical_preview_cdp.ps1' -CanonicalWebDir 'data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_static_primary_trace_payload\data\canonical_web' -PreviewPort 8162 -DebugPort 9392 -TimeoutSeconds 900 -StartupAttempts 3
```

Expected current full-payload smoke result:

- `catalogSource`: `canonical_web`
- `traceMode`: `static`
- `trace_event_index` cached
- trace runtime rows: `286,582`
- render mode: `budgeted`
- rendered/source segments: `11,135 / 11,135`

Expected current full temporary static-config smoke result:

- `catalogSource`: `canonical_web`
- `startupPhase`: `Ready`
- `trace_event_index` cached
- trace runtime rows: `286,582`
- render mode: `budgeted`
- rendered/source segments: `11,135 / 11,135`
- checked-in defaults changed: `false`

## Completed Promotion Steps

1. Changed only the canonical runtime flags in the checked-in static app config.
2. Restaged the full-detail canonical web payload into `static_bundle/data/canonical_web`.
3. Refreshed `static_bundle.zip`.
4. Ran runtime readiness and static-payload readiness checks.
5. Ran a browser smoke against the actual promoted static bundle, not only the preview override server.
6. Regenerated `runtime_integration_readiness_gate.json`.

Current promoted smoke result:

- `catalogSource`: `canonical_web`
- `startupPhase`: `Ready`
- `trace_event_index` cached: `true`
- trace runtime rows: `286,570`
- render mode: `budgeted`
- rendered/source segments: `11,135 / 11,135`

For the production-like static-config smoke, use `-UseStaticAppConfig` against a temporary static root whose `data/app_config.json` already contains the promoted canonical flags. This avoids preview-server config injection and verifies the same config path a deployed bundle would use:

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -ExecutionPolicy Bypass -File 'scripts\smoke_guarded_canonical_preview_cdp.ps1' -StaticRoot '.tmp\promoted_static_bundle' -CanonicalWebDir '.tmp\promoted_static_bundle\data\canonical_web' -PreviewPort 8170 -DebugPort 9400 -TimeoutSeconds 900 -StartupAttempts 3 -UseStaticAppConfig
```

Keep `.tmp\promoted_static_bundle` out of source control. The checked-in `static_bundle/data/app_config.json` is now promoted, so future smoke should target the actual `static_bundle` unless testing rollback or alternate payloads.

The smoke script normalizes duplicate Windows `PATH`/`Path` environment keys before launching child processes and the preview server accepts UTF-8 BOM JSON configs, so temporary configs written by Windows tooling are valid inputs for this check.

## Rollback

Rollback is config-only if no corpus mutation is mixed into the promotion branch:

```json
{
  "canonicalWebArtifacts": {
    "enabled": false,
    "primaryCatalog": false,
    "traceRuntime": false,
    "filteredTraceAggregation": false
  }
}
```

After rollback, rebuild `static_bundle`, refresh `static_bundle.zip`, and rerun the full test suite.

## Non-Promotion Work Still Separate

Manual-review mutation remains preview-only. If canonical mutation is later approved, design that as a separate contract with:

- explicit `--mode promote` semantics
- immutable input/output audit reports
- rollback corpus path
- suppressed-ID verification
- replacement-row verification
- no silent writes to `data/canonical_full/deduped_events.jsonl`
