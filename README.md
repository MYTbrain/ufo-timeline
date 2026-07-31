# UFO Timeline Map Tool

Local parser + map explorer for the UFO/UAP chronology text files in this workspace. The project preserves every event block, logs anything ambiguous or weakly parsed, writes normalized JSON outputs, and serves an interactive Leaflet map for the map-ready subset.

## Project Layout

- `parser/` contains event parsing, date normalization, location heuristics, geocoder abstractions, caching, and the end-to-end pipeline.
- `data/` holds generated JSON outputs, unresolved-location reports, manual overrides, and a small sample chronology file.
- `cache/` stores the persistent geocode cache as JSONL.
- `webapp/` contains the FastAPI app and static Leaflet frontend.
- `scripts/` contains the CLI entry points for parsing and running the local app.
- `tests/` contains parser/date/geocoder/backend tests plus a small Node-based frontend utility test.

## Git Repository Scope

The repository contains the product source, tests, documentation, configuration examples, and small static overlay assets. Large source corpora, generated datasets, caches, release bundles, and local deployment state are intentionally excluded from Git. Full-catalog parsing requires separately provisioned chronology inputs; production-scale static data should remain in external object storage such as Cloudflare R2.

## Setup

1. Install Python 3.11+.
2. Install the Python dependencies:

```powershell
py -m pip install -r requirements.txt
```

3. Copy `config.example.yaml` to your own config file if you want to customize paths, geocoder settings, rate limits, or tile providers.

## Parse The Chronology Files

Run the full pipeline:

```powershell
py scripts/parse_ufo_files.py --config config.example.yaml
```

Run a resumable live-geocoding batch with an explicit cap:

```powershell
py scripts/parse_ufo_files.py --config config.example.yaml --max-geocode-queries 500
```

Run a fast dry-run on a subset:

```powershell
py scripts/parse_ufo_files.py --config config.example.yaml --limit 250 --disable-geocoding
```

Process a specific input file:

```powershell
py scripts/parse_ufo_files.py --config config.example.yaml --input-file "ufos 1950_1959.txt"
```

## Launch The Local Web App

After generating `data/map_events.json`, start the app:

```powershell
py scripts/run_webapp.py --config config.example.yaml
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Open The Static Browser Bundle

If you want a browser-usable version without running a backend, open `static_bundle/index.html` directly in a browser. The bundle includes:

- local HTML/CSS/JS
- vendored Leaflet + MarkerCluster assets under `static_bundle/vendor/`
- prebuilt catalog shards, lazy event chunks, and packed point-index artifacts under `static_bundle/data/`
- copied unresolved-location reports under `static_bundle/reports/`

The current public bundle defaults to a no-basemap world view with a reference grid, so it works reliably from `file://` and static hosts without tile blocking. If you later want optional hosted tiles, add a `web.tile_url` and `web.tile_attribution` value in config and rebuild.

## Where The JSON Lives

- Full normalized event dataset: `data/normalized_events.json`
- Map-ready event dataset: `data/map_events.json`
- Unresolved or weakly resolved locations: `data/reports/unresolved_locations.json`
- Spreadsheet-friendly unresolved report: `data/reports/unresolved_locations.csv`
- Parse warnings and hard parse failures: `data/reports/parse_failures.jsonl`
- Geocoder failures / no-result attempts: `data/reports/geocode_failures.jsonl`

The normalized dataset keeps every event block, raw fields, parse warnings, uncertainty metadata, and mapping metadata. The map-ready dataset is a lighter projection intended for the frontend.

## How The Geocoding Cache Works

- Cache file: `cache/geocode_cache.jsonl`
- Cache key: provider id + normalized query text
- Cached entries store the original query, normalized query, timestamp, and chosen result payload
- Successful and no-result geocodes are cached so repeated runs do not re-query the same place text
- Network/transport failures are logged to `data/reports/geocode_failures.jsonl` and are not silently treated as resolved
- Batched runs are resumable: rerun the parser with another `--max-geocode-queries` budget and it will continue from the cache instead of starting over
- Higher-frequency structured queries are prioritized before vague or country-only strings so each live batch improves map coverage more efficiently

## Public Bundle Data Layout

The deployable static site in `static_bundle/` is split so static hosts do not need a backend:

- `data/catalog_shards/` contains the lightweight browser catalog split across multiple small files
- `data/event_chunks/` contains full normalized event records split across multiple chunks for on-demand deep search and full-event inspection
- `data/app_config.json`, `data/event_chunk_manifest.json`, and `data/event_catalog_manifest.json` tell the browser how to load those chunks
- `data/points.bin` and `data/points_meta.json` are generated packed point-index artifacts for the scale migration path; the current frontend still uses catalog shards until packed runtime parity is implemented.
- `vendor/` contains local Leaflet and MarkerCluster assets
- `.nojekyll` is included for GitHub Pages compatibility

If you want to force a fresh lookup for a particular place, remove the matching line from `cache/geocode_cache.jsonl` and rerun the parser.

## Ambiguous And Weakly Resolved Records

The parser intentionally keeps ambiguity visible:

- Events with `Locations:` or semicolon-separated places are marked as multi-location candidates and keep every original location string in `all_locations_raw`.
- Vague inputs such as `near X`, `off coast of Y`, directional prefixes, or description-derived fallback locations get `location_precision: "approximate"` and explanatory `mapping_notes`.
- Events that cannot be safely mapped keep `coordinate_source: "unresolved"` in the full dataset and are listed in `data/reports/unresolved_locations.json`.
- Parse oddities such as unknown field labels or unlabeled lines are preserved in `extra_data.unparsed_lines` and echoed to `data/reports/parse_failures.jsonl`.

If you want to manually fix a record, add an override entry to `data/manual_location_overrides.json` keyed by `event_id`, then rerun the parser.

Example override:

```json
{
  "12345": {
    "lat": 33.3943,
    "lon": -104.523,
    "location_precision": "approximate",
    "geocode_display_name": "Roswell, New Mexico, USA",
    "geocode_query_used": "Roswell, New Mexico",
    "mapping_notes": "Manual correction after reviewing unresolved report."
  }
}
```

## Swapping Map Providers Or Geocoders

### Map tiles

- Edit the `web.tile_url` and `web.tile_attribution` values in your config file.
- The frontend reads those values from `/api/app-config`, so no JavaScript edits are required for a basic tile-provider swap.

### Geocoders

- Change the provider settings under `geocoder:` in your config file.
- Provider construction is centralized in `parser/geocoders/factory.py`.
- The Nominatim implementation lives in `parser/geocoders/nominatim.py`.
- If you want to add another provider, add a new module in `parser/geocoders/`, return it from `factory.py`, and keep the rest of the pipeline unchanged.

## Tests

Run the Python tests:

```powershell
py -m pytest
```

Run the frontend utility checks if Node 18+ is available:

```powershell
node tests/test_frontend_utils.mjs
```

## Notes

- Public Nominatim endpoints are slow for large bulk runs. The project caches aggressively, but for tens of thousands of text-location lookups you may eventually want a keyed provider or your own Nominatim instance.
- The frontend filters entirely client-side against the generated browser catalog shards, which keeps the app easy to run locally without a database. A packed point index is now generated for the scale migration path, but the runtime has not switched to it yet.
- Duplicates are intentionally preserved because the chronology contains overlapping source records by design.
