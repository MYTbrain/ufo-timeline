param(
  [string]$StaticRoot = "webapp/static_public",
  [string]$OutputDir = "data/reports",
  [int]$ChunkSize = 80,
  [int]$RequestDelayMs = 200
)

$ErrorActionPreference = "Stop"

function Normalize-NameTokenText {
  param([string]$Value)
  if (-not $Value) { return "" }
  return ($Value.ToLowerInvariant() -replace "[^a-z0-9]+", " ").Trim()
}

function Get-TokenOverlapScore {
  param([string]$Left, [string]$Right)
  $leftTokens = @(Normalize-NameTokenText $Left -split "\s+" | Where-Object { $_ -and $_.Length -gt 1 })
  $rightTokens = @(Normalize-NameTokenText $Right -split "\s+" | Where-Object { $_ -and $_.Length -gt 1 })
  if ($leftTokens.Count -eq 0 -or $rightTokens.Count -eq 0) { return 0.0 }
  $leftSet = @{}
  foreach ($token in $leftTokens) { $leftSet[$token] = $true }
  $rightSet = @{}
  foreach ($token in $rightTokens) { $rightSet[$token] = $true }
  $intersection = 0
  foreach ($token in $leftSet.Keys) {
    if ($rightSet.ContainsKey($token)) { $intersection += 1 }
  }
  $denominator = [Math]::Max($leftSet.Count, $rightSet.Count)
  if ($denominator -eq 0) { return 0.0 }
  return [Math]::Round($intersection / $denominator, 3)
}

function Get-YearFromDateLiteral {
  param([string]$Value)
  if (-not $Value) { return $null }
  if ($Value -match "^-?(\d{1,4})-") {
    return [int]$Matches[1]
  }
  if ($Value -match "^(\d{4})$") {
    return [int]$Matches[1]
  }
  return $null
}

function Get-WikidataEntityUrl {
  param([string]$Uri)
  if (-not $Uri) { return "" }
  return ($Uri -replace "http://www.wikidata.org/entity/", "https://www.wikidata.org/wiki/")
}

$root = (Resolve-Path ".").Path
$overlayPath = Join-Path $root (Join-Path $StaticRoot "data/map_overlays/military_bases.geojson")
$overridePath = Join-Path $root (Join-Path $StaticRoot "data/map_overlays/military_base_temporal_overrides.json")
$outputPath = Join-Path $root $OutputDir
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$overlay = Get-Content -Raw -Path $overlayPath | ConvertFrom-Json
$existingOverrideIds = @{}
if (Test-Path $overridePath) {
  $overridePayload = Get-Content -Raw -Path $overridePath | ConvertFrom-Json
  foreach ($entry in @($overridePayload.overrides)) {
    if ($entry.source_id) { $existingOverrideIds[[string]$entry.source_id] = $true }
  }
}

$records = @()
foreach ($feature in @($overlay.features)) {
  $props = $feature.properties
  $sourceId = [string]$props.source_id
  if ($sourceId -notmatch "^geonames:(\d+)$") { continue }
  $records += [pscustomobject]@{
    source_id = $sourceId
    geonames_id = $Matches[1]
    name = [string]$props.name
    country_code = [string]$props.country_code
    branch = [string]$props.branch
  }
}

$bindings = @()
for ($offset = 0; $offset -lt $records.Count; $offset += $ChunkSize) {
  $chunk = @($records[$offset..([Math]::Min($offset + $ChunkSize - 1, $records.Count - 1))])
  $values = ($chunk | ForEach-Object { '"' + $_.geonames_id + '"' }) -join " "
  $query = @"
SELECT ?item ?itemLabel ?geonamesId ?inception ?dissolved ?start ?end ?coord ?countryLabel ?instanceOfLabel WHERE {
  VALUES ?geonamesId { $values }
  ?item wdt:P1566 ?geonamesId .
  OPTIONAL { ?item wdt:P571 ?inception. }
  OPTIONAL { ?item wdt:P576 ?dissolved. }
  OPTIONAL { ?item wdt:P580 ?start. }
  OPTIONAL { ?item wdt:P582 ?end. }
  OPTIONAL { ?item wdt:P625 ?coord. }
  OPTIONAL { ?item wdt:P17 ?country. }
  OPTIONAL { ?item wdt:P31 ?instanceOf. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"@
  try {
    $response = Invoke-RestMethod `
      -Uri "https://query.wikidata.org/sparql" `
      -Method Get `
      -Body @{ query = $query; format = "json" } `
      -Headers @{ "User-Agent" = "UfoTimelineTemporalBackfill/0.1 local research" } `
      -TimeoutSec 90
    $bindings += @($response.results.bindings)
  } catch {
    Write-Warning "Wikidata chunk starting at $offset failed: $($_.Exception.Message)"
  }
  Start-Sleep -Milliseconds $RequestDelayMs
}

$recordsByGeonamesId = @{}
foreach ($record in $records) {
  $recordsByGeonamesId[$record.geonames_id] = $record
}

$grouped = @{}
foreach ($row in $bindings) {
  $geonamesId = [string]$row.geonamesId.value
  $item = [string]$row.item.value
  if (-not $geonamesId -or -not $item) { continue }
  $key = "$geonamesId|$item"
  if (-not $grouped.ContainsKey($key)) {
    $grouped[$key] = [ordered]@{
      geonames_id = $geonamesId
      wikidata_item = Get-WikidataEntityUrl $item
      wikidata_label = [string]$row.itemLabel.value
      country_label = [string]$row.countryLabel.value
      instance_of = @{}
      inception_years = @{}
      dissolved_years = @{}
      start_years = @{}
      end_years = @{}
    }
  }
  if ($row.instanceOfLabel.value) { $grouped[$key].instance_of[[string]$row.instanceOfLabel.value] = $true }
  foreach ($field in @("inception", "start")) {
    if ($row.$field.value) {
      $year = Get-YearFromDateLiteral ([string]$row.$field.value)
      if ($year) {
        if ($field -eq "inception") { $grouped[$key].inception_years[[string]$year] = $true }
        else { $grouped[$key].start_years[[string]$year] = $true }
      }
    }
  }
  foreach ($field in @("dissolved", "end")) {
    if ($row.$field.value) {
      $year = Get-YearFromDateLiteral ([string]$row.$field.value)
      if ($year) {
        if ($field -eq "dissolved") { $grouped[$key].dissolved_years[[string]$year] = $true }
        else { $grouped[$key].end_years[[string]$year] = $true }
      }
    }
  }
}

$candidates = @()
$allMatches = @()
foreach ($group in $grouped.Values) {
  $record = $recordsByGeonamesId[$group.geonames_id]
  if (-not $record) { continue }
  $sourceId = "geonames:$($group.geonames_id)"
  $startYears = @($group.inception_years.Keys + $group.start_years.Keys | Where-Object { $_ } | ForEach-Object { [int]$_ } | Sort-Object -Unique)
  $endYears = @($group.dissolved_years.Keys + $group.end_years.Keys | Where-Object { $_ } | ForEach-Object { [int]$_ } | Sort-Object -Unique)
  $startYear = if ($startYears.Count) { ($startYears | Measure-Object -Minimum).Minimum } else { $null }
  $endYear = if ($endYears.Count) { ($endYears | Measure-Object -Maximum).Maximum } else { $null }
  $score = Get-TokenOverlapScore $record.name $group.wikidata_label
  $hasDate = $null -ne $startYear -or $null -ne $endYear
  $alreadyOverridden = $existingOverrideIds.ContainsKey($sourceId)
  $confidence = "medium"
  if ($score -ge 0.45) { $confidence = "high" }
  if ($score -lt 0.25) { $confidence = "low" }

  $match = [ordered]@{
    source_id = $sourceId
    name = $record.name
    country_code = $record.country_code
    wikidata_label = $group.wikidata_label
    wikidata_item = $group.wikidata_item
    instance_of = @($group.instance_of.Keys | Sort-Object)
    token_overlap_score = $score
    start_year = $startYear
    end_year = $endYear
    temporal_confidence = $confidence
    has_temporal_date = $hasDate
    already_overridden = $alreadyOverridden
  }
  $allMatches += [pscustomobject]$match

  if (-not $hasDate) { continue }
  if ($alreadyOverridden) { continue }
  if ($confidence -eq "low") { continue }

  $candidates += [pscustomobject][ordered]@{
    source_id = $sourceId
    name = $record.name
    country_code = $record.country_code
    start_year = $startYear
    end_year = $endYear
    date_precision_start = if ($null -ne $startYear) { "year" } else { "unknown" }
    date_precision_end = if ($null -ne $endYear) { "year" } else { "open" }
    historical_status = if ($null -ne $endYear) { "closed_or_transferred" } else { "active_or_unknown" }
    temporal_confidence = $confidence
    temporal_source = "wikidata_p1566_backfill"
    wikidata_item = $group.wikidata_item
    source_urls = @($group.wikidata_item)
    source_notes = "Exact GeoNames ID match via Wikidata P1566. Wikidata label: $($group.wikidata_label). Instance of: $((@($group.instance_of.Keys | Sort-Object)) -join ', ')."
  }
}

$summary = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  overlay_records = $records.Count
  wikidata_matches = $allMatches.Count
  dated_candidate_overrides = $candidates.Count
  existing_override_count = $existingOverrideIds.Count
}

$result = [ordered]@{
  summary = $summary
  candidates = $candidates
  all_matches = $allMatches
}

$jsonPath = Join-Path $outputPath "military_base_temporal_wikidata_candidates.json"
$overridePathOut = Join-Path $outputPath "military_base_temporal_wikidata_candidate_overrides.json"
$csvPath = Join-Path $outputPath "military_base_temporal_wikidata_matches.csv"

$result | ConvertTo-Json -Depth 12 | Set-Content -Path $jsonPath -Encoding UTF8
[ordered]@{
  schema_version = 1
  generated_at = $summary.generated_at
  description = "Candidate temporal military base overrides generated from exact Wikidata P1566 GeoNames ID matches. Review before merging."
  match_key = "source_id"
  overrides = $candidates
} | ConvertTo-Json -Depth 12 | Set-Content -Path $overridePathOut -Encoding UTF8
$allMatches | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8

$summary | ConvertTo-Json -Depth 4
