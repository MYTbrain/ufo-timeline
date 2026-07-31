param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectName,

  [string]$BundleRoot = 'cloudflare_bundle_r2'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$BundlePath = Join-Path $RepoRoot $BundleRoot

if (!(Test-Path -LiteralPath $BundlePath)) {
  throw "Missing Pages bundle: $BundlePath"
}

& (Join-Path $PSScriptRoot 'cloudflare_wrangler.ps1') pages deploy $BundlePath --project-name $ProjectName
