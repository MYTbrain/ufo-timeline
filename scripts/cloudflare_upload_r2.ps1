param(
  [Parameter(Mandatory = $true)]
  [string]$BucketName
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$UploadScript = Join-Path $RepoRoot 'cloudflare_bundle_r2\upload_r2_assets.ps1'
$Node = Join-Path $env:ProgramFiles 'nodejs\node.exe'
$WranglerJs = Join-Path $RepoRoot 'node_modules\wrangler\bin\wrangler.js'

if (!(Test-Path -LiteralPath $UploadScript)) {
  throw "Missing generated R2 upload script: $UploadScript"
}

& $UploadScript -BucketName $BucketName -Node $Node -WranglerJs $WranglerJs
