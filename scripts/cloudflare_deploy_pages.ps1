param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectName,

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

$CropRoot = Join-Path $BundlePath 'data\crop_circles'
$CropPoints = Join-Path $CropRoot 'points.json.gz'
$CropDetails = Join-Path $CropRoot 'details'
if (Test-Path -LiteralPath $CropPoints -PathType Leaf) {
  throw "Refusing Pages deploy containing R2-only crop payload: $CropPoints"
}
if ((Test-Path -LiteralPath $CropDetails -PathType Container) -and
    (Get-ChildItem -LiteralPath $CropDetails -File -Recurse | Select-Object -First 1)) {
  throw "Refusing Pages deploy containing R2-only crop detail payloads: $CropDetails"
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

& (Join-Path $PSScriptRoot 'cloudflare_wrangler.ps1') pages deploy $BundlePath --project-name $ProjectName
