param(
  [Parameter(Mandatory = $true)]
  [string]$PagesRoot,

  [Parameter(Mandatory = $true)]
  [string]$PagesDeploymentId,

  [Parameter(Mandatory = $true)]
  [string]$ReleaseId,

  [string]$BucketName = 'ufo-timeline-data',
  [string]$PublicR2BaseUrl = 'https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev',
  [string]$ArchiveKey = '',
  [string]$CanonicalProductionUrl = 'https://ufo-timeline.pages.dev',
  [string]$Python = '.venv\Scripts\python.exe',
  [switch]$SkipUpload
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$ResolvedPagesRoot = Resolve-Path (Join-Path $RepoRoot $PagesRoot)

$ParsedDeploymentId = [Guid]::Empty
if (![Guid]::TryParse($PagesDeploymentId, [ref]$ParsedDeploymentId)) {
  throw 'PagesDeploymentId must be the full immutable Cloudflare Pages deployment UUID.'
}
if ($ReleaseId -notmatch '^[a-z0-9][a-z0-9._-]*$') {
  throw 'ReleaseId must contain only lowercase letters, numbers, periods, underscores, and hyphens.'
}

$RepoPython = Join-Path $RepoRoot $Python
if ([IO.Path]::IsPathRooted($Python)) {
  $PythonCommand = $Python
} elseif (Test-Path -LiteralPath $RepoPython) {
  $PythonCommand = (Resolve-Path -LiteralPath $RepoPython).Path
} else {
  $PythonCommand = $Python
}

& $PythonCommand -c 'import truststore'
if ($LASTEXITCODE -ne 0) {
  throw 'The selected Python environment is not locked. Install requirements.lock before publishing.'
}

if (!$ArchiveKey) {
  $ArchiveKey = "releases/reproduction/$ReleaseId/pages-bundle.zip"
}

$BuildRoot = Join-Path $RepoRoot '.reproduction\build'
$ArchivePath = Join-Path $BuildRoot "$ReleaseId-pages-bundle.zip"
$ArchiveUrl = "$($PublicR2BaseUrl.TrimEnd('/'))/$($ArchiveKey.TrimStart('/'))"
$PagesUrl = "https://$($PagesDeploymentId.Substring(0, 8)).ufo-timeline.pages.dev"

New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null

Write-Host "Building deterministic reproduction contract for $ReleaseId..."
& $PythonCommand scripts\reproduction.py build `
  --pages-root $ResolvedPagesRoot `
  --pages-base-url $PagesUrl `
  --pages-deployment-id $PagesDeploymentId `
  --canonical-production-url $CanonicalProductionUrl `
  --release-id $ReleaseId `
  --archive-output $ArchivePath `
  --archive-url $ArchiveUrl `
  --output reproduction\release.json
if ($LASTEXITCODE -ne 0) {
  throw "Reproduction contract build failed."
}

if (!$SkipUpload) {
  Write-Host "Uploading immutable Pages archive to R2: $BucketName/$ArchiveKey"
  & (Join-Path $PSScriptRoot 'cloudflare_wrangler.ps1') r2 object put "$BucketName/$ArchiveKey" `
    --file $ArchivePath `
    --remote `
    --content-type 'application/zip' `
    --cache-control 'public, max-age=31536000, immutable'
  if ($LASTEXITCODE -ne 0) {
    throw "R2 archive upload failed."
  }

  Write-Host "Verifying the uploaded archive through the public reproduction path..."
  & $PythonCommand scripts\reproduction.py hydrate `
    --manifest reproduction\release.json `
    --output .reproduction\upload-smoke-site `
    --cache .reproduction\upload-smoke-cache
  if ($LASTEXITCODE -ne 0) {
    throw "Uploaded reproduction archive verification failed."
  }
}

Write-Host "Reproduction manifest refreshed: reproduction/release.json"
Write-Host "Commit that manifest with the source change it reproduces."
