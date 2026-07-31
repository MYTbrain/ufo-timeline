param(
  [string]$BucketName = 'ufo-timeline-data',
  [string[]]$AllowedOrigins = @(
    'https://ufo-timeline.pages.dev',
    'https://*.ufo-timeline.pages.dev'
  )
)

$ErrorActionPreference = 'Stop'
$Wrangler = Join-Path $PSScriptRoot 'cloudflare_wrangler.ps1'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$CorsPath = Join-Path $RepoRoot 'cloudflare_bundle_r2\r2_cors.json'

$CorsDir = Split-Path -Parent $CorsPath
if (!(Test-Path -LiteralPath $CorsDir)) {
  New-Item -ItemType Directory -Path $CorsDir | Out-Null
}

$corsConfig = @{
  rules = @(
    @{
      allowed = @{
        origins = $AllowedOrigins
        methods = @('GET', 'HEAD')
        headers = @('*')
      }
      exposeHeaders = @('ETag', 'Content-Length', 'Content-Range', 'Accept-Ranges')
      maxAgeSeconds = 86400
    }
  )
}

$corsConfig | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -Path $CorsPath
& $Wrangler r2 bucket cors set $BucketName --file $CorsPath
