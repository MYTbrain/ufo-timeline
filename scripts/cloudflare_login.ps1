param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$LoginArgs
)

$ErrorActionPreference = 'Stop'
$ArgsForWrangler = @('login')
if ($LoginArgs.Count -eq 0) {
  $ArgsForWrangler += @('--browser=false', '--callback-port', '8976')
} else {
  $ArgsForWrangler += $LoginArgs
}
& (Join-Path $PSScriptRoot 'cloudflare_wrangler.ps1') @ArgsForWrangler
