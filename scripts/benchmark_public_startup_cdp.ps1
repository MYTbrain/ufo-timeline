param(
  [string]$Url = "http://127.0.0.1:8130/index.html",
  [string]$BrowserPath = "C:\Program Files\Google\Chrome\Application\chrome.exe",
  [int]$DebugPort = 9391,
  [int]$TimeoutSeconds = 180,
  [switch]$ProbeStaticTraces,
  [switch]$ProbeFilterControls,
  [switch]$ProbeTraceFacilityControls,
  [switch]$ProbeTraceModeCycling,
  [string]$MapMode = "",
  [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:CdpEventLog = New-Object System.Collections.Generic.List[string]

function Receive-CdpMessage {
  param(
    [System.Net.WebSockets.ClientWebSocket]$Socket,
    [System.Threading.CancellationToken]$Token
  )
  $buffer = New-Object byte[] 32768
  $builder = New-Object System.Text.StringBuilder
  while ($true) {
    $segment = [System.ArraySegment[byte]]::new($buffer)
    $result = $Socket.ReceiveAsync($segment, $Token).GetAwaiter().GetResult()
    if ($result.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) {
      throw "CDP websocket closed unexpectedly."
    }
    if ($result.Count -gt 0) {
      $builder.Append([System.Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)) | Out-Null
    }
    if ($result.EndOfMessage) {
      return $builder.ToString()
    }
  }
}

function Send-CdpCommand {
  param(
    [System.Net.WebSockets.ClientWebSocket]$Socket,
    [int]$Id,
    [string]$Method,
    [hashtable]$Params,
    [System.Threading.CancellationToken]$Token
  )
  $payload = @{
    id = $Id
    method = $Method
    params = $Params
  } | ConvertTo-Json -Depth 10 -Compress
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
  $segment = [System.ArraySegment[byte]]::new($bytes)
  $Socket.SendAsync($segment, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $Token).GetAwaiter().GetResult() | Out-Null

  while ($true) {
    $raw = Receive-CdpMessage -Socket $Socket -Token $Token
    $message = $raw | ConvertFrom-Json
    if ($message.PSObject.Properties.Name -contains "id" -and [int]$message.id -eq $Id) {
      if ($message.PSObject.Properties.Name -contains "error") {
        throw ("CDP error for " + $Method + ": " + ($message.error | ConvertTo-Json -Compress))
      }
      return $message.result
    }
    if ($message.PSObject.Properties.Name -contains "method") {
      $method = [string]$message.method
      if ($method -in @("Runtime.exceptionThrown", "Runtime.consoleAPICalled", "Log.entryAdded")) {
        $script:CdpEventLog.Add(($message | ConvertTo-Json -Depth 8 -Compress))
        if ($script:CdpEventLog.Count -gt 100) {
          $script:CdpEventLog.RemoveAt(0)
        }
      }
    }
  }
}

function Invoke-CdpEval {
  param(
    [System.Net.WebSockets.ClientWebSocket]$Socket,
    [ref]$IdCounter,
    [string]$Expression,
    [System.Threading.CancellationToken]$Token
  )
  $IdCounter.Value += 1
  $result = Send-CdpCommand -Socket $Socket -Id $IdCounter.Value -Method "Runtime.evaluate" -Params @{
    expression = $Expression
    returnByValue = $true
    awaitPromise = $true
  } -Token $Token
  if ($result.PSObject.Properties.Name -contains "exceptionDetails" -and $result.exceptionDetails) {
    throw ("Evaluation failed: " + ($result.exceptionDetails | ConvertTo-Json -Compress))
  }
  return $result.result.value
}

function Wait-ForCondition {
  param(
    [System.Net.WebSockets.ClientWebSocket]$Socket,
    [ref]$IdCounter,
    [string]$Expression,
    [int]$TimeoutSeconds,
    [string]$Description,
    [System.Threading.CancellationToken]$Token
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $value = Invoke-CdpEval -Socket $Socket -IdCounter $IdCounter -Expression $Expression -Token $Token
    if ($value) {
      return $value
    }
    Start-Sleep -Milliseconds 500
  }
  throw "Timed out waiting for $Description."
}

function Wait-ForHttpJson {
  param(
    [string]$JsonUrl,
    [int]$TimeoutSeconds
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing $JsonUrl
      if ($response.StatusCode -eq 200) {
        return $response.Content | ConvertFrom-Json
      }
    } catch {
    }
    Start-Sleep -Milliseconds 300
  }
  throw "Timed out waiting for $JsonUrl."
}

if (-not (Test-Path -LiteralPath $BrowserPath)) {
  throw "Browser executable not found: $BrowserPath"
}

if ($MapMode -and $MapMode -notin @("points", "clusters", "heatmap")) {
  throw "Unsupported MapMode '$MapMode'. Expected one of: points, clusters, heatmap."
}

$browser = $null
$socket = $null
$tokenSource = [System.Threading.CancellationTokenSource]::new()
$idCounter = 0
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

try {
  $browserStdout = Join-Path $PWD ".tmp\benchmark-public-startup-browser.out.log"
  $browserStderr = Join-Path $PWD ".tmp\benchmark-public-startup-browser.err.log"
  New-Item -ItemType Directory -Force -Path (Split-Path $browserStdout -Parent) | Out-Null
  Remove-Item -LiteralPath $browserStdout, $browserStderr -Force -ErrorAction SilentlyContinue

  $browser = Start-Process -FilePath $BrowserPath -ArgumentList @(
    "--headless=new",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-component-extensions-with-background-pages",
    "--disable-crash-reporter",
    "--disable-breakpad",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-session-crashed-bubble",
    "--no-sandbox",
    "--remote-debugging-port=$DebugPort",
    "about:blank"
  ) -WindowStyle Hidden -RedirectStandardOutput $browserStdout -RedirectStandardError $browserStderr -PassThru

  Wait-ForHttpJson -JsonUrl "http://127.0.0.1:$DebugPort/json/version" -TimeoutSeconds 30 | Out-Null

  $encodedUrl = [Uri]::EscapeDataString($Url)
  $targetResponse = Invoke-WebRequest -UseBasicParsing -Method Put "http://127.0.0.1:$DebugPort/json/new?$encodedUrl"
  $target = $targetResponse.Content | ConvertFrom-Json
  if (-not $target.webSocketDebuggerUrl) {
    throw "No websocket debugger URL was available for the benchmark target."
  }

  $socket = [System.Net.WebSockets.ClientWebSocket]::new()
  $socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, $tokenSource.Token).GetAwaiter().GetResult() | Out-Null

  $idCounter += 1
  Send-CdpCommand -Socket $socket -Id $idCounter -Method "Page.enable" -Params @{} -Token $tokenSource.Token | Out-Null
  $idCounter += 1
  Send-CdpCommand -Socket $socket -Id $idCounter -Method "Runtime.enable" -Params @{} -Token $tokenSource.Token | Out-Null
  $idCounter += 1
  Send-CdpCommand -Socket $socket -Id $idCounter -Method "Log.enable" -Params @{} -Token $tokenSource.Token | Out-Null

  $ready = Wait-ForCondition -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => {
  const phase = document.documentElement.getAttribute('data-startup-phase');
  const initialViewReady = document.documentElement.getAttribute('data-startup-initial-view-ready');
  const startupOverlay = document.querySelector('#map-startup-overlay');
  const startupOverlayHidden = startupOverlay ? startupOverlay.hidden : null;
  if (phase === 'Ready' && initialViewReady === 'true' && startupOverlayHidden === true) {
    return { status: 'ready', phase, initialViewReady, startupOverlayHidden, now: performance.now() };
  }
  if (phase === 'Failed') return { status: 'failed', phase, now: performance.now() };
  return false;
})()
"@ -TimeoutSeconds $TimeoutSeconds -Description "startup Ready with the initial visual gate complete and loading cover hidden, or Failed" -Token $tokenSource.Token

  if ($ready.status -ne "ready") {
    $diagnostic = Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => ({
  href: location.href,
  readyState: document.readyState,
  startupPhase: document.documentElement.getAttribute('data-startup-phase'),
  bodyText: (document.body && document.body.innerText || '').slice(0, 6000),
  startupErrorText: window.__UFO_TIMELINE_DEBUG__?.getStartupErrorText?.() || null,
  startupTiming: window.__UFO_TIMELINE_DEBUG__?.getStartupTimingSummary?.() || null,
  canonicalWebArtifacts: window.__UFO_TIMELINE_DEBUG__?.getCanonicalWebArtifactsStatus?.() || null,
  hasDebug: !!window.__UFO_TIMELINE_DEBUG__
}))()
"@ -Token $tokenSource.Token
    throw ("Startup did not reach Ready. diagnostic=" + ($diagnostic | ConvertTo-Json -Depth 8 -Compress))
  }

  if ($ProbeStaticTraces) {
    if ($MapMode) {
      $escapedMapMode = $MapMode.Replace("\", "\\").Replace("'", "\'")
      Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(async () => {
  const select = document.querySelector('#map-mode');
  if (!select) return false;
  select.value = '$escapedMapMode';
  select.dispatchEvent(new Event('change', { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 500));
  return window.__UFO_TIMELINE_DEBUG__?.getStateSnapshot?.() || null;
})()
"@ -Token $tokenSource.Token | Out-Null

      Wait-ForCondition -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => {
  const state = window.__UFO_TIMELINE_DEBUG__?.getStateSnapshot?.();
  return state && state.mapMode === '$escapedMapMode' ? state : false;
})()
"@ -TimeoutSeconds $TimeoutSeconds -Description "map mode override $MapMode" -Token $tokenSource.Token | Out-Null
    }

    Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(async () => {
  const debug = window.__UFO_TIMELINE_DEBUG__;
  if (!debug) return false;
  const traceMode = document.querySelector('#trace-mode');
  if (traceMode) {
    traceMode.value = 'static';
    traceMode.dispatchEvent(new Event('change', { bubbles: true }));
  }
  await debug.loadCanonicalTraceArtifact?.('trace_event_index');
  debug.forceStaticTraceRender?.();
  return true;
})()
"@ -Token $tokenSource.Token | Out-Null

    Wait-ForCondition -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => {
  const metrics = window.__UFO_TIMELINE_DEBUG__?.getTraceFacilityFilterMetrics?.();
  const snapshot = window.__UFO_TIMELINE_DEBUG__?.getStaticTraceLayerSnapshot?.();
  if (!metrics || !snapshot) return false;
  if (metrics.enabled && !metrics.worker?.pendingKey && (metrics.worker?.traceIndexLoadMode || metrics.worker?.lastError)) {
    return { metrics, snapshot, now: performance.now() };
  }
  if (!metrics.enabled && snapshot.metrics) {
    return { metrics, snapshot, now: performance.now() };
  }
  return false;
})()
"@ -TimeoutSeconds $TimeoutSeconds -Description "static trace probe" -Token $tokenSource.Token | Out-Null
  }

  $traceFacilityProbe = $null
  if ($ProbeTraceFacilityControls) {
    $traceFacilityProbe = Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(async () => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const debug = window.__UFO_TIMELINE_DEBUG__;
  if (!debug) throw new Error('Debug API is not available.');

  async function waitUntil(predicate, description, timeoutMs = 30000) {
    const started = Date.now();
    let lastValue = null;
    while (Date.now() - started < timeoutMs) {
      lastValue = predicate();
      if (lastValue) return lastValue;
      await sleep(250);
    }
    throw new Error('Timed out waiting for ' + description + '; last=' + JSON.stringify(lastValue));
  }

  async function ensureStaticTraceReady() {
    const traceMode = document.querySelector('#trace-mode');
    if (traceMode && traceMode.value !== 'static') {
      traceMode.value = 'static';
      traceMode.dispatchEvent(new Event('change', { bubbles: true }));
      await sleep(300);
    }
    const enabled = document.querySelector('#trace-facility-filter-enabled');
    if (enabled && !enabled.checked) {
      enabled.checked = true;
      enabled.dispatchEvent(new Event('change', { bubbles: true }));
      await sleep(300);
    }
    await debug.loadCanonicalTraceArtifact?.('trace_event_index');
    debug.forceStaticTraceRender?.();
    return waitTraceReady('initial static trace ready');
  }

  function summarize(label) {
    const metrics = debug.getTraceFacilityFilterMetrics?.();
    const snapshot = debug.getStaticTraceLayerSnapshot?.();
    const radiusInput = document.querySelector('#trace-facility-radius');
    return {
      label,
      radiusInputValue: radiusInput ? Number(radiusInput.value) : null,
      radiusKm: metrics?.radiusKm ?? null,
      activeClasses: metrics?.activeClasses || [],
      enabled: Boolean(metrics?.enabled),
      workerPendingKey: metrics?.worker?.pendingKey || '',
      workerLastError: metrics?.worker?.lastError || '',
      candidateSegments: metrics?.stats?.candidateSegments ?? null,
      matchedSegments: metrics?.stats?.matchedSegments ?? null,
      startSegments: metrics?.stats?.startSegments ?? null,
      endSegments: metrics?.stats?.endSegments ?? null,
      betweenSegments: metrics?.stats?.betweenSegments ?? null,
      passesSegments: metrics?.stats?.passesSegments ?? null,
      layerExists: snapshot?.layerExists ?? null,
      layerVisible: snapshot?.layerVisible ?? null,
      segmentCount: snapshot?.segmentCount ?? null,
      reason: snapshot?.metrics?.reason || '',
    };
  }

  async function waitTraceReady(label) {
    return waitUntil(() => {
      const summary = summarize(label);
      if (!summary.enabled) return false;
      if (summary.workerPendingKey) return false;
      if (summary.workerLastError) throw new Error('Trace facility worker error: ' + summary.workerLastError);
      if (summary.layerExists == null || summary.layerVisible == null) return false;
      return summary;
    }, label, 120000);
  }

  async function setRadius(value) {
    const button = document.querySelector('[data-trace-facility-radius-preset="' + value + '"]');
    const input = document.querySelector('#trace-facility-radius');
    if (!button || !input) throw new Error('Missing trace radius control ' + value);
    button.click();
    await sleep(200);
    debug.forceStaticTraceRender?.();
    const summary = await waitTraceReady('radius ' + value);
    if (summary.radiusInputValue !== value || Math.round(Number(summary.radiusKm)) !== value) {
      throw new Error('Trace radius did not apply: ' + JSON.stringify(summary));
    }
    return summary;
  }

  async function setClassAction(action, expectedClasses) {
    const button = document.querySelector('[data-trace-facility-class-action="' + action + '"]');
    if (!button) throw new Error('Missing trace class action ' + action);
    button.click();
    await sleep(200);
    debug.forceStaticTraceRender?.();
    const summary = await waitTraceReady('class action ' + action);
    const actual = (summary.activeClasses || []).slice().sort().join(',');
    const expected = expectedClasses.slice().sort().join(',');
    if (actual !== expected) {
      throw new Error('Trace class action did not apply: expected ' + expected + ' got ' + actual + '; summary=' + JSON.stringify(summary));
    }
    return summary;
  }

  function linkedFacilityDisplaySnapshot(label) {
    const metrics = debug.getTraceFacilityFilterMetrics?.();
    const trace = debug.getStaticTraceLayerSnapshot?.();
    return {
      label,
      onlyShowTraceLinkedFacilities: Boolean(metrics?.onlyShowTraceLinkedFacilities),
      filteredEvents: Number(String(document.querySelector('#results-count')?.textContent || '').replace(/[^0-9]/g, '')),
      filteredMapped: Number(String(document.querySelector('#mapped-results-count')?.textContent || '').replace(/[^0-9]/g, '')),
      facilityMarkerDomCopies: document.querySelectorAll('.overlay-marker-icon').length,
      traceSegmentCount: trace?.segmentCount ?? null,
    };
  }

  async function probeLinkedFacilityDisplay() {
    const input = document.querySelector('#trace-facility-linked-only');
    if (!input) throw new Error('Missing linked-facility display control.');
    if (!input.checked) {
      input.checked = true;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const linkedOnly = await waitUntil(() => {
      const value = linkedFacilityDisplaySnapshot('linked facilities only');
      return value.onlyShowTraceLinkedFacilities && value.facilityMarkerDomCopies > 0 ? value : false;
    }, 'linked facility markers', 15000);

    input.checked = false;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    const allEnabled = await waitUntil(() => {
      const value = linkedFacilityDisplaySnapshot('all enabled facilities');
      return !value.onlyShowTraceLinkedFacilities && value.facilityMarkerDomCopies > linkedOnly.facilityMarkerDomCopies
        ? value
        : false;
    }, 'all enabled facility markers', 15000);

    input.checked = true;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    const restored = await waitUntil(() => {
      const value = linkedFacilityDisplaySnapshot('linked facilities restored');
      return value.onlyShowTraceLinkedFacilities && value.facilityMarkerDomCopies === linkedOnly.facilityMarkerDomCopies
        ? value
        : false;
    }, 'linked facility marker restoration', 15000);

    for (const value of [allEnabled, restored]) {
      if (value.filteredEvents !== linkedOnly.filteredEvents || value.filteredMapped !== linkedOnly.filteredMapped) {
        throw new Error('Facility marker display changed sighting counts: ' + JSON.stringify({ linkedOnly, value }));
      }
      if (value.traceSegmentCount !== linkedOnly.traceSegmentCount) {
        throw new Error('Facility marker display reclassified traces: ' + JSON.stringify({ linkedOnly, value }));
      }
    }
    return { linkedOnly, allEnabled, restored, sightingsPreserved: true, traceClassificationPreserved: true };
  }

  const initial = await ensureStaticTraceReady();
  const linkedFacilityDisplay = await probeLinkedFacilityDisplay();
  const radiusResults = [];
  for (const value of [1, 2, 3, 4, 5, 25]) {
    radiusResults.push(await setRadius(value));
  }
  const classResults = [];
  classResults.push(await setClassAction('only:start', ['start']));
  classResults.push(await setClassAction('only:end', ['end']));
  classResults.push(await setClassAction('only:between', ['between']));
  classResults.push(await setClassAction('only:passes', ['passes']));
  classResults.push(await setClassAction('all', ['start', 'end', 'between', 'passes']));
  classResults.push(await setClassAction('none', []));
  classResults.push(await setClassAction('all', ['start', 'end', 'between', 'passes']));

  return {
    initial,
    linkedFacilityDisplay,
    radiusResults,
    classResults,
  };
})()
"@ -Token $tokenSource.Token
  }

  $traceModeCycleProbe = $null
  if ($ProbeTraceModeCycling) {
    $traceModeCycleProbe = Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(async () => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const debug = window.__UFO_TIMELINE_DEBUG__;
  if (!debug) throw new Error('Debug API is not available.');

  async function waitUntil(predicate, description, timeoutMs = 120000) {
    const started = Date.now();
    let lastValue = null;
    while (Date.now() - started < timeoutMs) {
      lastValue = predicate();
      if (lastValue) return lastValue;
      await sleep(250);
    }
    throw new Error('Timed out waiting for ' + description + '; last=' + JSON.stringify(lastValue));
  }

  function snapshot(label) {
    const state = debug.getStateSnapshot?.();
    const trace = debug.getStaticTraceLayerSnapshot?.();
    const facility = debug.getTraceFacilityFilterMetrics?.();
    return {
      label,
      traceMode: state?.traceMode || document.querySelector('#trace-mode')?.value || '',
      mapMode: state?.mapMode || document.querySelector('#map-mode')?.value || '',
      layerExists: trace?.layerExists ?? null,
      layerVisible: trace?.layerVisible ?? null,
      segmentCount: trace?.segmentCount ?? null,
      workerPendingKey: facility?.worker?.pendingKey || '',
      workerLastError: facility?.worker?.lastError || '',
      matchedSegments: facility?.stats?.matchedSegments ?? null,
      reason: trace?.metrics?.reason || '',
    };
  }

  function setFacilityDefaults() {
    const enabled = document.querySelector('#trace-facility-filter-enabled');
    if (enabled && !enabled.checked) {
      enabled.checked = true;
      enabled.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const radius = document.querySelector('#trace-facility-radius');
    if (radius && radius.value !== '5') {
      radius.value = '5';
      radius.dispatchEvent(new Event('change', { bubbles: true }));
    }
    for (const input of document.querySelectorAll('[data-trace-facility-class]')) {
      const key = input.getAttribute('data-trace-facility-class');
      const expected = key === 'start' || key === 'end' || key === 'between';
      if (input.checked !== expected) {
        input.checked = expected;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }
  }

  async function waitStatic(label) {
    return waitUntil(() => {
      const summary = snapshot(label);
      if (summary.workerLastError) throw new Error('Trace facility worker error: ' + summary.workerLastError);
      if (summary.workerPendingKey) return false;
      if (summary.traceMode !== 'static') return false;
      if (summary.layerVisible !== true) return false;
      if (!(Number(summary.segmentCount) > 0)) return false;
      return summary;
    }, label);
  }

  async function setTraceMode(value, label) {
    const select = document.querySelector('#trace-mode');
    if (!select) throw new Error('Missing #trace-mode');
    select.value = value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    await sleep(300);
    debug.forceStaticTraceRender?.();
    if (value === 'static') {
      return waitStatic(label);
    }
    return waitUntil(() => {
      const summary = snapshot(label);
      return summary.traceMode === value ? summary : false;
    }, label, 10000);
  }

  async function setMapMode(value) {
    const select = document.querySelector('#map-mode');
    if (!select) throw new Error('Missing #map-mode');
    select.value = value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    await sleep(300);
    debug.forceStaticTraceRender?.();
    return waitUntil(() => {
      const summary = snapshot('map ' + value);
      if (summary.workerLastError) throw new Error('Trace facility worker error: ' + summary.workerLastError);
      if (summary.workerPendingKey) return false;
      if (summary.traceMode !== 'static' || summary.mapMode !== value) return false;
      if (summary.layerVisible !== true || !(Number(summary.segmentCount) > 0)) return false;
      return summary;
    }, 'map mode ' + value + ' static traces');
  }

  await debug.loadCanonicalTraceArtifact?.('trace_event_index');
  setFacilityDefaults();
  const results = [];
  results.push(await setTraceMode('static', 'static initial'));
  results.push(await setTraceMode('off', 'trace off'));
  results.push(await setTraceMode('playback', 'trace playback'));
  results.push(await setTraceMode('static', 'static restored'));
  results.push(await setMapMode('points'));
  results.push(await setMapMode('clusters'));
  results.push(await setMapMode('heatmap'));
  return { results };
})()
"@ -Token $tokenSource.Token
  }

  $filterProbe = $null
  if ($ProbeFilterControls) {
    $filterProbe = Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(async () => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const text = (selector) => (document.querySelector(selector)?.textContent || '').trim();
  const numberText = (selector) => Number((text(selector).match(/[0-9,]+/) || ['0'])[0].replace(/,/g, ''));
  const selectedOptions = () => Array.from(document.querySelectorAll('#type-filter option:checked')).map((option) => option.value);
  const checkedBoxes = () => Array.from(document.querySelectorAll('#type-filter-pane input[type="checkbox"]:checked')).map((box) => box.getAttribute('data-filter-value') || box.value || '');
  const typeStateMode = () => {
    const stateEl = document.querySelector('#type-filter-state');
    if (!stateEl) return '';
    if (stateEl.classList.contains('mode-all')) return 'all';
    if (stateEl.classList.contains('mode-none')) return 'none';
    if (stateEl.classList.contains('mode-subset')) return 'subset';
    return '';
  };
  async function waitUntil(predicate, description, timeoutMs = 8000) {
    const started = Date.now();
    let lastError = null;
    while (Date.now() - started < timeoutMs) {
      try {
        if (predicate()) return true;
      } catch (error) {
        lastError = error;
      }
      await sleep(150);
    }
    throw new Error('Timed out waiting for ' + description + (lastError ? ': ' + lastError.message : ''));
  }
  async function slowType(selector, value) {
    const input = document.querySelector(selector);
    if (!input) throw new Error('Missing input ' + selector);
    input.focus();
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    for (const char of value) {
      input.value += char;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      await sleep(225);
    }
    const valueBeforeCommit = input.value;
    await sleep(650);
    const valueAfterIdleBeforeCommit = input.value;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.blur();
    await sleep(900);
    return {
      selector,
      target: value,
      valueBeforeCommit,
      valueAfterIdleBeforeCommit,
      valueAfterCommit: input.value,
    };
  }
  async function clickTypeAction(action) {
    const button = document.querySelector('[data-filter-target="type-filter"] [data-filter-action="' + action + '"]');
    if (!button) throw new Error('Missing type action ' + action);
    button.click();
    if (action === 'none') {
      await waitUntil(() => typeStateMode() === 'none' && selectedOptions().length === 0 && checkedBoxes().length === 0, 'type none action');
    } else if (action === 'all') {
      await waitUntil(() => typeStateMode() === 'all', 'type all action');
    } else {
      await waitUntil(() => typeStateMode() === 'subset' && selectedOptions().length > 0, 'type ' + action + ' action');
    }
    await sleep(300);
    return {
      action,
      stateText: text('#type-filter-state'),
      stateMode: typeStateMode(),
      selectedOptions: selectedOptions(),
      checkedBoxes: checkedBoxes(),
      resultCount: numberText('#results-count'),
      mappedResultCount: numberText('#mapped-results-count'),
    };
  }
  const startDate = await slowType('#start-date', '1954-09-04');
  const endDate = await slowType('#end-date', '1954-10-08');
  const beforeType = {
    stateText: text('#type-filter-state'),
    stateMode: typeStateMode(),
    selectedOptions: selectedOptions(),
    checkedBoxes: checkedBoxes(),
    resultCount: numberText('#results-count'),
  };
  const none = await clickTypeAction('none');
  const firstPositive = Array.from(document.querySelectorAll('#type-filter-pane label')).map((label) => {
    const box = label.querySelector('input[type="checkbox"]');
    const countSource = label.querySelector('.filter-option-count')?.textContent || label.textContent || '';
    const countText = countSource.match(/([0-9,]+)/);
    return {
      label,
      box,
      value: box ? (box.getAttribute('data-filter-value') || box.value || '') : '',
      count: countText ? Number(countText[1].replace(/,/g, '')) : 0,
    };
  }).find((item) => item.box && item.count > 0);
  if (!firstPositive) throw new Error('No positive-count type checkbox was available.');
  firstPositive.box.click();
  await waitUntil(() => {
    const selected = selectedOptions();
    const checked = checkedBoxes();
    return selected.length === 1 && checked.length === 1 && selected[0] === firstPositive.value && checked[0] === firstPositive.value && numberText('#results-count') > 0;
  }, 'single positive-count type checkbox result');
  await sleep(300);
  const oneType = {
    selectedValue: firstPositive.value,
    stateText: text('#type-filter-state'),
    stateMode: typeStateMode(),
    selectedOptions: selectedOptions(),
    checkedBoxes: checkedBoxes(),
    resultCount: numberText('#results-count'),
    mappedResultCount: numberText('#mapped-results-count'),
  };
  const invert = await clickTypeAction('invert');
  const craftOnly = await clickTypeAction('craft_only');
  const all = await clickTypeAction('all');
  const result = {
    dateEntry: {
      startDate,
      endDate,
      timelineStart: document.querySelector('#timeline-start-date')?.value || '',
      timelineEnd: document.querySelector('#timeline-end-date')?.value || '',
      startStableBeforeCommit: startDate.valueBeforeCommit === startDate.target && startDate.valueAfterIdleBeforeCommit === startDate.target,
      endStableBeforeCommit: endDate.valueBeforeCommit === endDate.target && endDate.valueAfterIdleBeforeCommit === endDate.target,
      startCommitted: startDate.valueAfterCommit === startDate.target,
      endCommitted: endDate.valueAfterCommit === endDate.target,
    },
    typeFilter: {
      beforeType,
      none,
      oneType,
      invert,
      craftOnly,
      all,
      noneHasZeroSelected: none.stateMode === 'none' && none.selectedOptions.length === 0 && none.checkedBoxes.length === 0,
      oneTypeHasResults: oneType.stateMode === 'subset' && oneType.selectedOptions.length === 1 && oneType.checkedBoxes.length === 1 && oneType.resultCount > 0,
      allRestored: all.stateMode === 'all' && all.checkedBoxes.length === document.querySelectorAll('#type-filter option').length,
    },
  };
  if (!result.dateEntry.startStableBeforeCommit || !result.dateEntry.endStableBeforeCommit || !result.dateEntry.startCommitted || !result.dateEntry.endCommitted) {
    throw new Error('Date entry smoke failed: ' + JSON.stringify(result.dateEntry));
  }
  if (!result.typeFilter.noneHasZeroSelected || !result.typeFilter.oneTypeHasResults || !result.typeFilter.allRestored) {
    throw new Error('Type filter smoke failed: ' + JSON.stringify(result.typeFilter));
  }
  return result;
})()
"@ -Token $tokenSource.Token
  }

  $snapshot = Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => {
  const debug = window.__UFO_TIMELINE_DEBUG__;
  const nav = performance.getEntriesByType('navigation')[0];
  return {
    href: location.href,
    userAgent: navigator.userAgent,
    startupPhase: document.documentElement.getAttribute('data-startup-phase'),
    startupPreviewInteractive: document.documentElement.getAttribute('data-startup-preview-interactive'),
    startupInitialViewReady: document.documentElement.getAttribute('data-startup-initial-view-ready'),
    mapStartupOverlayHidden: document.querySelector('#map-startup-overlay') ? document.querySelector('#map-startup-overlay').hidden : null,
    mapStartupOverlayAriaHidden: document.querySelector('#map-startup-overlay') ? document.querySelector('#map-startup-overlay').getAttribute('aria-hidden') : null,
    startupPanelHidden: document.querySelector('#startup-panel') ? document.querySelector('#startup-panel').hidden : null,
    navigation: nav ? nav.toJSON() : null,
    startupTiming: debug?.getStartupTimingSummary?.() || null,
    state: debug?.getStateSnapshot?.() || null,
    packedPoints: debug?.getPackedPointsStatus?.() || null,
    canonicalTrace: debug?.getCanonicalTraceRuntimeStatus?.() || null,
    staticTrace: debug?.getStaticTraceLayerSnapshot?.() || null,
    traceFacility: debug?.getTraceFacilityFilterMetrics?.() || null
  };
})()
"@ -Token $tokenSource.Token

  $result = @{
    status = "passed"
    url = $Url
    browserPath = $BrowserPath
    wallClockMs = [math]::Round($stopwatch.Elapsed.TotalMilliseconds)
    startupReadyPerformanceNowMs = [math]::Round([double]$ready.now)
    probeStaticTraces = [bool]$ProbeStaticTraces
    probeFilterControls = [bool]$ProbeFilterControls
    probeTraceFacilityControls = [bool]$ProbeTraceFacilityControls
    probeTraceModeCycling = [bool]$ProbeTraceModeCycling
    mapModeOverride = $MapMode
    filterProbe = $filterProbe
    traceFacilityProbe = $traceFacilityProbe
    traceModeCycleProbe = $traceModeCycleProbe
    snapshot = $snapshot
    cdpEvents = @($script:CdpEventLog | Select-Object -Last 20)
  }
  $json = $result | ConvertTo-Json -Depth 20
  if ($OutputPath) {
    if ([System.IO.Path]::IsPathRooted($OutputPath)) {
      $resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
    } else {
      $resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $PWD $OutputPath))
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $resolvedOutput -Parent) | Out-Null
    Set-Content -LiteralPath $resolvedOutput -Value $json -Encoding UTF8
  }
  $json
}
finally {
  if ($socket) {
    try { $socket.Dispose() } catch {}
  }
  $tokenSource.Dispose()
  if ($browser) {
    try { Stop-Process -Id $browser.Id -Force -ErrorAction SilentlyContinue } catch {}
  }
}
