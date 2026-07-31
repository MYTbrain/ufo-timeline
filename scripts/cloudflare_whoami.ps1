param()

$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'cloudflare_wrangler.ps1') whoami
