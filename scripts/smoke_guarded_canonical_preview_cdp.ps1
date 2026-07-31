param(
  [string]$StaticRoot = "static_bundle",
  [string]$CanonicalWebDir = "data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_static_primary_trace_payload\data\canonical_web",
  [string]$HostName = "127.0.0.1",
  [int]$PreviewPort = 8146,
  [int]$DebugPort = 9381,
  [int]$TimeoutSeconds = 240,
  [int]$StartupAttempts = 3,
  [string]$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe",
  [string]$PythonPath = "C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
  [switch]$ServeGzip,
  [switch]$UseStaticAppConfig
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:CdpEventLog = New-Object System.Collections.Generic.List[string]

function Normalize-ProcessPathEnvironment {
  $pathValue = [System.Environment]::GetEnvironmentVariable("Path", "Process")
  if (-not $pathValue) {
    $pathValue = [System.Environment]::GetEnvironmentVariable("PATH", "Process")
  }
  if ($pathValue) {
    [System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")
    [System.Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
  }
}

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
      if ($method -in @("Runtime.exceptionThrown", "Runtime.consoleAPICalled", "Log.entryAdded", "Page.loadEventFired", "Page.domContentEventFired")) {
        $script:CdpEventLog.Add(($message | ConvertTo-Json -Depth 8 -Compress))
        if ($script:CdpEventLog.Count -gt 80) {
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
    [string]$Url,
    [int]$TimeoutSeconds
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing $Url
      if ($response.StatusCode -eq 200) {
        return $response.Content | ConvertFrom-Json
      }
    } catch {
    }
    Start-Sleep -Milliseconds 500
  }
  throw "Timed out waiting for $Url."
}

function Read-TextFileIfPresent {
  param(
    [string]$Path
  )
  if (Test-Path -LiteralPath $Path) {
    return Get-Content -LiteralPath $Path -Raw
  }
  return ""
}

$preview = $null
$chrome = $null
$socket = $null
$tokenSource = [System.Threading.CancellationTokenSource]::new()
$idCounter = 0

try {
  Normalize-ProcessPathEnvironment

  $workspace = (Get-Location).Path
  $previewUrl = "http://${HostName}:$PreviewPort/index.html"
  $env:PYTHONPATH = "$workspace\.python_packages;$workspace"

  $previewArgs = @(
    "scripts\serve_static_bundle_with_canonical_web.py",
    "--static-root", $StaticRoot,
    "--canonical-web-dir", $CanonicalWebDir,
    "--host", $HostName,
    "--port", "$PreviewPort"
  )
  if (-not $UseStaticAppConfig) {
    $previewArgs += @(
      "--enable-canonical-web",
      "--enable-primary-catalog",
      "--enable-trace-runtime",
      "--enable-filtered-trace-aggregation"
    )
  }
  if (-not $ServeGzip) {
    $previewArgs += "--no-gzip"
  }
  $previewStdout = Join-Path $PWD ".tmp\canonical-preview-server-cdp.out.log"
  $previewStderr = Join-Path $PWD ".tmp\canonical-preview-server-cdp.err.log"
  Remove-Item -LiteralPath $previewStdout, $previewStderr -Force -ErrorAction SilentlyContinue
  $preview = Start-Process -FilePath $PythonPath -ArgumentList $previewArgs -WindowStyle Hidden -RedirectStandardOutput $previewStdout -RedirectStandardError $previewStderr -PassThru

  try {
    $config = Wait-ForHttpJson -Url "http://${HostName}:$PreviewPort/data/app_config.json" -TimeoutSeconds 30
  } catch {
    $previewStatus = if ($preview.HasExited) { "exited:$($preview.ExitCode)" } else { "running" }
    $stdoutText = Read-TextFileIfPresent -Path $previewStdout
    $stderrText = Read-TextFileIfPresent -Path $previewStderr
    throw ("Preview server did not expose app_config on port $PreviewPort. status=$previewStatus stdout=" + $stdoutText + " stderr=" + $stderrText)
  }
  if (-not $config.canonicalWebArtifacts.enabled -or -not $config.canonicalWebArtifacts.primaryCatalog -or -not $config.canonicalWebArtifacts.traceRuntime -or -not $config.canonicalWebArtifacts.filteredTraceAggregation) {
    if ($UseStaticAppConfig) {
      throw "Static app_config did not provide the expected promoted canonical config."
    }
    throw "Preview server did not provide the expected guarded canonical config override."
  }

  $chromeStdout = Join-Path $PWD ".tmp\chrome-guarded-canonical-preview-cdp.out.log"
  $chromeStderr = Join-Path $PWD ".tmp\chrome-guarded-canonical-preview-cdp.err.log"
  Remove-Item -LiteralPath $chromeStdout, $chromeStderr -Force -ErrorAction SilentlyContinue

  $chrome = Start-Process -FilePath $ChromePath -ArgumentList @(
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
  ) -WindowStyle Hidden -RedirectStandardOutput $chromeStdout -RedirectStandardError $chromeStderr -PassThru

  try {
    Wait-ForHttpJson -Url "http://127.0.0.1:$DebugPort/json/version" -TimeoutSeconds 30 | Out-Null
  } catch {
    $stdoutText = Read-TextFileIfPresent -Path $chromeStdout
    $stderrText = Read-TextFileIfPresent -Path $chromeStderr
    throw ("Chrome did not expose CDP on port $DebugPort. stdout=" + $stdoutText + " stderr=" + $stderrText)
  }

  $encodedUrl = [Uri]::EscapeDataString($previewUrl)
  $targetResponse = Invoke-WebRequest -UseBasicParsing -Method Put "http://127.0.0.1:$DebugPort/json/new?$encodedUrl"
  $target = $targetResponse.Content | ConvertFrom-Json
  if (-not $target.webSocketDebuggerUrl) {
    throw "No websocket debugger URL was available for the preview page target."
  }

  $socket = [System.Net.WebSockets.ClientWebSocket]::new()
  $socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, $tokenSource.Token).GetAwaiter().GetResult() | Out-Null

  $idCounter += 1
  Send-CdpCommand -Socket $socket -Id $idCounter -Method "Page.enable" -Params @{} -Token $tokenSource.Token | Out-Null
  $idCounter += 1
  Send-CdpCommand -Socket $socket -Id $idCounter -Method "Runtime.enable" -Params @{} -Token $tokenSource.Token | Out-Null
  $idCounter += 1
  Send-CdpCommand -Socket $socket -Id $idCounter -Method "Log.enable" -Params @{} -Token $tokenSource.Token | Out-Null

  $ready = $false
  for ($attempt = 1; $attempt -le $StartupAttempts; $attempt += 1) {
    if ($attempt -gt 1) {
      $idCounter += 1
      Send-CdpCommand -Socket $socket -Id $idCounter -Method "Page.reload" -Params @{ ignoreCache = $true } -Token $tokenSource.Token | Out-Null
    }
    try {
      $startupResult = Wait-ForCondition -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => {
  const phase = document.documentElement.getAttribute('data-startup-phase');
  if (phase === 'Ready') return { status: 'ready', phase };
  if (phase === 'Failed') return { status: 'failed', phase };
  return false;
})()
"@ -TimeoutSeconds $TimeoutSeconds -Description "startup ready attempt $attempt" -Token $tokenSource.Token
      if ($startupResult.status -eq "ready") {
        $ready = $true
        break
      }
      if ($attempt -lt $StartupAttempts) {
        continue
      }
    } catch {
      if ($attempt -lt $StartupAttempts) {
        continue
      }
    }
    $diagnostic = Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => ({
  href: location.href,
  readyState: document.readyState,
  startupPhase: document.documentElement.getAttribute('data-startup-phase'),
  title: document.title,
  bodyText: (document.body && document.body.innerText || '').slice(0, 1200),
  hasDebug: !!window.__UFO_TIMELINE_DEBUG__,
  appConfigCanonical: (window.__APP_CONFIG__ || window.APP_CONFIG || null)?.canonicalWebArtifacts || null,
  mapChildren: document.querySelector('#map')?.children.length || 0
}))()
"@ -Token $tokenSource.Token
    throw ("Timed out waiting for startup ready. diagnostic=" + ($diagnostic | ConvertTo-Json -Depth 8 -Compress) + " cdpEvents=" + (($script:CdpEventLog | Select-Object -Last 20) | ConvertTo-Json -Depth 8 -Compress))
  }

  Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => {
  document.querySelector('#reset-time-range')?.click();
  const traceMode = document.querySelector('#trace-mode');
  if (traceMode) {
    traceMode.value = 'static';
    traceMode.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return true;
})()
"@ -Token $tokenSource.Token | Out-Null

  Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(async () => {
  const debug = window.__UFO_TIMELINE_DEBUG__;
  let artifact = null;
  if (debug && debug.loadCanonicalTraceArtifact) {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        artifact = await debug.loadCanonicalTraceArtifact('trace_event_index');
        if (artifact && artifact.rowCount > 0) break;
      } catch (error) {
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
    }
  }
  const traceMode = document.querySelector('#trace-mode');
  if (traceMode) {
    traceMode.value = 'static';
    traceMode.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return {
    artifactCached: !!artifact,
    rowCount: artifact ? artifact.rowCount : 0
  };
})()
"@ -Token $tokenSource.Token | Out-Null

  try {
    $status = Wait-ForCondition -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => {
  const debug = window.__UFO_TIMELINE_DEBUG__;
  if (!debug) return false;
  const state = debug.getStateSnapshot();
  const trace = debug.getCanonicalTraceRuntimeStatus();
  const aggregate = debug.getStaticTraceAggregationStatus();
  if (!state || state.catalogSource !== 'canonical_web') return false;
  if (!trace || !trace.filteredAggregationRequested || !trace.artifactCached) return false;
  if (!aggregate || !aggregate.requested || aggregate.sourceSegments <= 0) return false;
  if (!aggregate.active) return false;
  return {
    catalogSource: state.catalogSource,
    eventCount: state.totalEvents,
    mappedEventCount: state.totalMappedEvents,
    traceMode: state.traceMode,
    traceRuntime: trace,
    aggregation: aggregate,
    startupPhase: document.documentElement.getAttribute('data-startup-phase')
  };
})()
"@ -TimeoutSeconds $TimeoutSeconds -Description "canonical trace aggregation status" -Token $tokenSource.Token
  } catch {
    $diagnostic = Invoke-CdpEval -Socket $socket -IdCounter ([ref]$idCounter) -Expression @"
(() => {
  const debug = window.__UFO_TIMELINE_DEBUG__;
  return {
    startupPhase: document.documentElement.getAttribute('data-startup-phase'),
    hasDebug: !!debug,
    state: debug?.getStateSnapshot?.() || null,
    trace: debug?.getCanonicalTraceRuntimeStatus?.() || null,
    aggregation: debug?.getStaticTraceAggregationStatus?.() || null,
    bodyText: (document.body && document.body.innerText || '').slice(0, 1200)
  };
})()
"@ -Token $tokenSource.Token
    throw ("Timed out waiting for canonical trace aggregation status. diagnostic=" + ($diagnostic | ConvertTo-Json -Depth 12 -Compress) + " cdpEvents=" + (($script:CdpEventLog | Select-Object -Last 20) | ConvertTo-Json -Depth 8 -Compress))
  }

  @{
    status = "passed"
    previewUrl = $previewUrl
    startupReady = [bool]$ready
    result = $status
    checkedInDefaultsChanged = $false
  } | ConvertTo-Json -Depth 12
}
finally {
  if ($socket) {
    try { $socket.Dispose() } catch {}
  }
  $tokenSource.Dispose()
  if ($chrome) {
    try { Stop-Process -Id $chrome.Id -Force -ErrorAction SilentlyContinue } catch {}
  }
  if ($preview) {
    try { Stop-Process -Id $preview.Id -Force -ErrorAction SilentlyContinue } catch {}
  }
}
