param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectName,

  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[A-Za-z0-9._/-]+$')]
  [string]$Branch,

  [string]$BundleRoot = 'cloudflare_bundle_r2',

  [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BundleCandidate = if ([IO.Path]::IsPathRooted($BundleRoot)) {
  $BundleRoot
} else {
  Join-Path $RepoRoot $BundleRoot
}

if (!(Test-Path -LiteralPath $BundleCandidate -PathType Container)) {
  throw "Missing Pages bundle: $BundleCandidate"
}
$BundlePath = (Resolve-Path -LiteralPath $BundleCandidate).Path
$RawSourcePath = (Resolve-Path -LiteralPath (Join-Path $RepoRoot 'webapp\static_public')).Path
if ([StringComparer]::OrdinalIgnoreCase.Equals($BundlePath, $RawSourcePath)) {
  throw 'Refusing to deploy raw webapp/static_public. Hydrate the frozen Pages release first.'
}

$Validator = Join-Path $RepoRoot 'scripts\validate_cloudflare_bundle.py'
$ReleaseManifest = Join-Path $RepoRoot 'reproduction\release.json'
& $Python $Validator `
  --bundle-root $BundlePath `
  --release-manifest $ReleaseManifest `
  --source-root $RawSourcePath
if ($LASTEXITCODE -ne 0) {
  throw "Pages release validation failed with exit code $LASTEXITCODE. Wrangler was not invoked."
}

& (Join-Path $PSScriptRoot 'cloudflare_wrangler.ps1') pages deploy $BundlePath --project-name $ProjectName --branch $Branch
