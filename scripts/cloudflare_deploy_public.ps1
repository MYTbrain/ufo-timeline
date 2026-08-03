param(
  [string]$BucketName = 'ufo-timeline-data',
  [string]$ProjectName = 'ufo-timeline',
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[A-Za-z0-9._/-]+$')]
  [string]$Branch,
  [string]$R2BaseUrl = '',
  [switch]$UseR2DevUrl,
  [string]$Python = 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$Wrangler = Join-Path $PSScriptRoot 'cloudflare_wrangler.ps1'

function Invoke-WranglerText {
  param([string[]]$Arguments)
  $output = & $Wrangler @Arguments 2>&1
  $exit = $LASTEXITCODE
  $text = ($output | Out-String)
  if ($exit -ne 0) {
    throw $text
  }
  return $text
}

if (!(Test-Path -LiteralPath $Python)) {
  throw "Python was not found at $Python"
}

Write-Host "Checking Cloudflare authentication..."
& $Wrangler whoami

Write-Host "Ensuring R2 bucket exists: $BucketName"
$bucketList = Invoke-WranglerText @('r2', 'bucket', 'list')
if ($bucketList -notmatch [regex]::Escape($BucketName)) {
  & $Wrangler r2 bucket create $BucketName
}

if (-not $R2BaseUrl) {
  if (-not $UseR2DevUrl) {
    throw "Provide -R2BaseUrl, or pass -UseR2DevUrl to enable/use the bucket's public r2.dev URL."
  }
  Write-Host "Enabling public r2.dev URL for $BucketName..."
  & $Wrangler r2 bucket dev-url enable $BucketName
  $devUrlOutput = Invoke-WranglerText @('r2', 'bucket', 'dev-url', 'get', $BucketName)
  $urlMatch = [regex]::Match($devUrlOutput, 'https://[a-zA-Z0-9.-]+\.r2\.dev')
  if (!$urlMatch.Success) {
    Write-Host $devUrlOutput
    throw "Could not determine the public r2.dev URL from Wrangler output. Re-run with -R2BaseUrl."
  }
  $R2BaseUrl = $urlMatch.Value.TrimEnd('/')
}

Write-Host "Building Cloudflare bundle with R2 base URL: $R2BaseUrl"
& $Python scripts\build_public_cloudflare_bundle.py `
  --static-root static_bundle `
  --output-root cloudflare_bundle_r2 `
  --r2-base-url $R2BaseUrl

Write-Host "Validating Cloudflare bundle..."
& $Python scripts\validate_cloudflare_bundle.py --bundle-root cloudflare_bundle_r2

Write-Host "Uploading R2 artifacts..."
& (Join-Path $PSScriptRoot 'cloudflare_upload_r2.ps1') -BucketName $BucketName

Write-Host "Configuring R2 CORS for Pages origins..."
& (Join-Path $PSScriptRoot 'cloudflare_configure_r2_cors.ps1') -BucketName $BucketName

Write-Host "Deploying Cloudflare Pages project: $ProjectName on explicit branch: $Branch"
& (Join-Path $PSScriptRoot 'cloudflare_deploy_pages.ps1') `
  -ProjectName $ProjectName `
  -Branch $Branch
