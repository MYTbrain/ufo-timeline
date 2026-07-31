param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$WranglerArgs
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$Node = Join-Path $env:ProgramFiles 'nodejs\node.exe'
$WranglerJs = Join-Path $RepoRoot 'node_modules\wrangler\bin\wrangler.js'

if (!(Test-Path -LiteralPath $Node)) {
  throw "Node was not found at $Node. Install Node.js LTS or update scripts/cloudflare_wrangler.ps1."
}
if (!(Test-Path -LiteralPath $WranglerJs)) {
  throw "Wrangler was not found at $WranglerJs. Run: & '$env:ProgramFiles\nodejs\npm.cmd' install"
}

$nodeOptions = [Environment]::GetEnvironmentVariable('NODE_OPTIONS', 'Process')
if (-not $nodeOptions) {
  $env:NODE_OPTIONS = '--use-system-ca'
} elseif ($nodeOptions -notmatch '(^|\s)--use-system-ca(\s|$)') {
  $env:NODE_OPTIONS = "$nodeOptions --use-system-ca"
}

& $Node $WranglerJs @WranglerArgs
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
