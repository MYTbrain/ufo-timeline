"""Derive a bounded map release from the guarded quality view.

The immutable full-detail chunks are read in place and never copied. Only
gzip summary shards, regenerated packed indexes, small startup profiles, and
guarded detail corrections are written. Run --self-test for synthetic checks.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import math
import shutil
import struct
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from parser.chronology import canonical_playback_sort_tuple, derive_event_chronology
from parser.packed_points import MISSING_INT64, ROW_STRUCT, export_packed_points
from parser.trace_segments import export_trace_artifacts
from scripts.build_startup_profile_artifacts import DEFAULT_PROFILES, build_trace_preview_segments

DEFAULT_MANIFEST = REPO_ROOT / 'data/research/database_quality_20261007/quality_view_manifest.json'
DEFAULT_OUTPUT = REPO_ROOT / 'data/releases/quality-20261007/map_delta'
DEFAULT_PREFIX = 'releases/quality-20261007/map_delta'
GUARD_FIELDS = ('source', 'sort_date_iso', 'location_raw', 'lat', 'lon',
                'coordinate_source', 'location_precision', 'has_coordinates')
PROTECTED_FIELDS = ('event_id', 'canonical_event_id', 'source_id', 'source',
                    'source_native_id', 'date_raw', 'date_iso', 'sort_date_iso',
                    'time_raw', 'raw_fields', 'raw_source_row', 'source_provenance',
                    'raw_event_block')
SUMMARY_METADATA = ('quality_view_changes', 'quality_date_review',
                    'quality_incident_relationships', 'quality_original_account')
BIN_NAMES = ('points.bin', 'trace_event_index.bin', 'trace_segments.bin',
             'trace_aggregate_bins.bin')
META_NAMES = ('points_meta.json', 'trace_event_index_meta.json',
              'trace_segments_meta.json', 'trace_aggregate_bins_meta.json')
COUNT_FIELDS = {
    'source_counts': ('source', 'unknown'),
    'type_counts': ('type', 'unknown'),
    'shape_counts': ('shape_normalized', 'unknown'),
    'craft_type_counts': ('craft_type_inferred', 'unknown'),
    'craft_type_confidence_counts': ('craft_type_confidence', 'none'),
    'craft_type_source_counts': ('craft_type_source', 'none'),
    'same_day_match_strength_counts': ('same_day_match_strength', 'none'),
    'date_precision_counts': ('date_precision', 'unknown'),
    'location_precision_counts': ('location_precision', 'unknown'),
    'coordinate_source_counts': ('coordinate_source', 'unknown'),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    if path.suffix == '.gz':
        with gzip.open(path, 'rt', encoding='utf8') as handle:
            return json.load(handle)
    return json.loads(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        handle.write('\n')


def write_gzip_json(path: Path, value: Any) -> None:
    """Write deterministic gzip directly, without a raw JSON staging copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as sink:
        with gzip.GzipFile(filename='', mode='wb', fileobj=sink, mtime=0, compresslevel=9) as compressed:
            with io.TextIOWrapper(compressed, encoding='utf8', newline='\n') as handle:
                json.dump(value, handle, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
                handle.write('\n')


def gzip_file(path: Path) -> None:
    with path.open('rb') as source, path.with_suffix(path.suffix + '.gz').open('wb') as sink:
        with gzip.GzipFile(filename='', mode='wb', fileobj=sink, mtime=0, compresslevel=9) as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)


def load_quality_view(manifest_path: Path | str = DEFAULT_MANIFEST):
    """Load the manifest-pinned reader; do not execute an unverified reader."""
    path = Path(manifest_path).resolve()
    manifest = read_json(path)
    pin = manifest['reader']
    reader_path = (path.parent / pin['path']).resolve()
    if not reader_path.is_relative_to(path.parent) or reader_path.stat().st_size != pin['bytes'] or sha256(reader_path) != pin['sha256']:
        raise ValueError('Quality reader pin mismatch')
    spec = importlib.util.spec_from_file_location('release_sparse_quality_view', reader_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.QualityView(path)


def effective_detail_from_source_row(view, raw: dict[str, Any]) -> dict[str, Any]:
    """Apply validated edits, deriving changed chronology from FULL source detail.

    Callers must read a manifest-pinned base detail chunk, retaining the original
    locator. Unchanged chronology stays byte-for-byte semantically unchanged.
    All source identity, original dates, narrative and provenance are protected.
    """
    effective = view._enrich(copy.deepcopy(raw))
    if str(raw['event_id']) in view.decisions:
        effective.update(derive_event_chronology(effective))
        if 'sort_time_ms' in raw:
            effective['sort_time_ms'] = effective.get('estimated_utc_timestamp_ms')
    for field in PROTECTED_FIELDS:
        if effective.get(field) != raw.get(field) or (field in effective) != (field in raw):
            raise ValueError(f'Quality release changed a protected source field: {field}')
    return effective


def make_detail_patch(view, raw: dict[str, Any], effective: dict[str, Any], chunk: str, index: int) -> dict[str, Any]:
    fields = {}
    eid = str(raw['event_id'])
    for decision in view.decisions.get(eid, []):
        fields.update(decision['set_fields'])
    if eid in view.decisions:
        for field in derive_event_chronology(effective):
            if raw.get(field) != effective.get(field) or (field in raw) != (field in effective):
                fields[field] = effective.get(field)
        if 'sort_time_ms' in raw and raw.get('sort_time_ms') != effective.get('sort_time_ms'):
            fields['sort_time_ms'] = effective.get('sort_time_ms')
    for field in SUMMARY_METADATA:
        if field in effective and effective.get(field) != raw.get(field):
            fields[field] = effective[field]
    if set(fields).intersection(PROTECTED_FIELDS):
        raise ValueError('Detail patch attempts to change protected source values')
    guards = {field: raw.get(field) for field in GUARD_FIELDS}
    for field in ('event_id', 'canonical_event_id', 'source_id', 'chunk_id', 'detail_index'):
        guards[field] = raw.get(field)
    if 'date_precision' in raw:
        guards['date_precision'] = raw['date_precision']
    return {'eventId': raw['event_id'], 'chunkId': chunk, 'detailIndex': index,
            'guards': guards, 'setFields': fields}


def build_effective_detail_updates(view) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Decode each affected source chunk once; retain sparse projected updates."""
    ids = set(view.decisions) | set(view.annotations) | set(view.incident_relationships)
    by_chunk = {}
    for eid in ids:
        chunk, index = view.locators[eid]
        by_chunk.setdefault(chunk, []).append((index, eid))
    updates, patches, source_receipts = {}, [], []
    for chunk, items in sorted(by_chunk.items()):
        source_name = f'event_chunks/{chunk}.json.gz'
        source_path = view._base_file(source_name)
        rows = read_json(source_path)
        if len(rows) != view.chunk_metadata[chunk]['event_count']:
            raise ValueError('Source detail chunk count mismatch')
        for index, eid in sorted(items):
            raw = rows[index]
            if str(raw['event_id']) != eid or raw.get('chunk_id') != chunk or raw.get('detail_index') != index:
                raise ValueError('Source detail locator mismatch')
            effective = effective_detail_from_source_row(view, raw)
            patch = make_detail_patch(view, raw, effective, chunk, index)
            if not patch['setFields']:
                raise ValueError('Expected detail patch is empty')
            patches.append(patch)
            if eid in view.decisions:
                update = {}
                for decision in view.decisions[eid]:
                    update.update(decision['set_fields'])
                update.update(derive_event_chronology(effective))
                if 'sort_time_ms' in effective:
                    update['sort_time_ms'] = effective['sort_time_ms']
                updates[eid] = update
        source_receipts.append({'path': source_name, **view.pins[source_name],
                                'usedEventCount': len(items)})
        print(f'Detail sources {len(source_receipts)}/{len(by_chunk)}; sparse patches {len(patches)}', flush=True)
    return updates, patches, source_receipts


def apply_summary_update(row: dict[str, Any], updates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Keep the compact base schema; do not expand 227k account annotations."""
    compact = {key: value for key, value in row.items() if key not in SUMMARY_METADATA}
    compact.update(updates.get(str(row['event_id']), {}))
    return compact


def point_projection_from_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Recover the omitted UTC midpoint from its authoritative playback key.

    Chronology group 1 uses precisely estimated_utc_timestamp_ms as the key's
    primary value. Group 2 is local minutes and group 3 is fallback, so neither
    can supply a UTC timestamp. Explicit None in changed rows remains None.
    """
    if 'estimated_utc_timestamp_ms' in row:
        return row
    key = row.get('playback_sort_key')
    if (isinstance(key, list) and len(key) >= 2 and key[0] == 1
            and type(key[1]) in (int, float) and math.isfinite(key[1])):
        return {**row, 'estimated_utc_timestamp_ms': key[1]}
    return row


def ensure_new_output(output: Path, base: Path) -> None:
    output, base = output.resolve(), base.resolve()
    if output == base or output.is_relative_to(base) or base.is_relative_to(output):
        raise ValueError('Release output overlaps the protected base catalog')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Release output must be absent or empty; no implicit replacement/deletion')


def estimate_output_bytes(base: Path) -> int:
    # Four raw binary artifacts plus gzip, all gzip summaries, bounded profiles
    # and sparse patches. Twenty percent is added for new rows/metadata.
    packed = sum((base / name).stat().st_size + (base / (name + '.gz')).stat().st_size for name in BIN_NAMES)
    summaries = sum(path.stat().st_size for path in (base / 'summary_shards').glob('*.json.gz'))
    return int((packed + summaries + 12 * 1024 * 1024) * 1.20)


def verify_storage(output: Path, estimate: int, max_output_bytes: int) -> int:
    if estimate >= 1024**3:
        raise ValueError('Estimated output exceeds 1 GiB; report and obtain an explicit layout decision')
    if estimate > max_output_bytes:
        raise ValueError('Estimated output exceeds the declared build cap')
    ancestor = output.resolve()
    while not ancestor.exists():
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free
    if ancestor.drive.lower() == 'c:' and free - estimate < 100 * 1024**3:
        raise ValueError('Build would violate the 100 GiB C: reserve')
    return free


def build_profiles(point_rows: list[dict[str, Any]], chunks: list[dict[str, Any]], output: Path, quality_sha: str) -> list[dict[str, Any]]:
    profiles = []
    for profile in DEFAULT_PROFILES:
        root = output / 'startup_profiles' / profile['profile_id']
        root.mkdir(parents=True, exist_ok=True)
        scoped = [dict(row) for row in point_rows
                  if profile['start_date'] <= str(row.get('sort_date_iso') or '') <= profile['end_date']]
        scoped.sort(key=canonical_playback_sort_tuple)
        # Retain craft/date/chronology fields from effective compact summaries.
        # This fixes the old profile projection omitting craft match metadata.
        write_json(root / 'events.json', scoped)
        gzip_file(root / 'events.json')
        points = export_packed_points(scoped, root, chunk_manifest=chunks)
        traces = export_trace_artifacts(scoped, root)
        for name in BIN_NAMES + META_NAMES:
            gzip_file(root / name)
        preview = build_trace_preview_segments(scoped, 12000)
        write_json(root / 'trace_preview_segments.json', preview)
        gzip_file(root / 'trace_preview_segments.json')
        files = {'events': 'events.json', 'events_gzip': 'events.json.gz',
                 'points': 'points.bin', 'points_gzip': 'points.bin.gz',
                 'points_metadata': 'points_meta.json',
                 'trace_event_index': 'trace_event_index.bin',
                 'trace_event_index_gzip': 'trace_event_index.bin.gz',
                 'trace_event_index_metadata': 'trace_event_index_meta.json',
                 'trace_aggregate_bins': 'trace_aggregate_bins.bin',
                 'trace_aggregate_bins_gzip': 'trace_aggregate_bins.bin.gz',
                 'trace_aggregate_bins_metadata': 'trace_aggregate_bins_meta.json',
                 'trace_preview_segments': 'trace_preview_segments.json',
                 'trace_preview_segments_gzip': 'trace_preview_segments.json.gz'}
        manifest = {'schema_version': 1, 'profile_id': profile['profile_id'],
                    'label': profile['label'], 'date_range': {'start': profile['start_date'], 'end': profile['end_date']},
                    'generated_at_utc': datetime.now(timezone.utc).isoformat(),
                    'qualityManifestSha256': quality_sha,
                    'counts': {'events': len(scoped), 'mapped_events': points['row_count'],
                               'trace_events': traces['trace_events']['row_count'],
                               'trace_segments': traces['trace_segments']['row_count'],
                               'trace_preview_segments': len(preview)},
                    'files': files,
                    'full_detail_policy': 'Shared immutable canonical detail chunks plus the guarded quality detail overlay.',
                    'trace_preview_policy': 'Diagnostic chronological adjacency; not a measured craft flight path.'}
        write_json(root / 'manifest.json', manifest)
        gzip_file(root / 'manifest.json')
        profile_public = 'data/startup_profiles/' + profile['profile_id'] + '/'
        profiles.append({'id': profile['profile_id'], 'label': profile['label'],
                         'baseUrl': './' + profile_public,
                         'manifestUrl': './' + profile_public + 'manifest.json',
                         'date_range': manifest['date_range'], 'counts': manifest['counts']})
    write_json(output / 'startup_profiles/manifest.json',
               {'schema_version': 1, 'qualityManifestSha256': quality_sha,
                'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'profiles': profiles})
    gzip_file(output / 'startup_profiles/manifest.json')
    return profiles


def artifact_receipts(output: Path, prefix: str) -> list[dict[str, Any]]:
    result = []
    for path in sorted(output.rglob('*')):
        if not path.is_file() or path.name == 'map_release_receipt.json':
            continue
        relative = path.relative_to(output).as_posix()
        if relative == 'detail_patches.json.gz':
            delivery, public, key = 'pages', 'data/quality_detail_patches.json.gz', None
        elif relative.startswith('startup_profiles/'):
            delivery, public, key = 'pages', 'data/' + relative, None
        elif relative in BIN_NAMES:
            delivery, public, key = 'local', None, None
        else:
            delivery, public, key = 'r2', prefix + '/' + relative, prefix + '/' + relative
        result.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': sha256(path),
                       'delivery': delivery, 'publicPath': public, 'immutableKey': key})
    return result


def verify_unchanged_packed_points(base: Path, output: Path, changed_ids: set[str]) -> int:
    """Compare unchanged decoded values, allowing lookup IDs to be rebuilt."""
    old_meta, new_meta = read_json(base / 'points_meta.json'), read_json(output / 'points_meta.json')
    def rows(path):
        with path.open('rb') as handle:
            while block := handle.read(ROW_STRUCT.size * 8192):
                for row in ROW_STRUCT.iter_unpack(block):
                    if str(row[0]) not in changed_ids:
                        yield row
    def decode(row, metadata):
        values = list(row)
        for index, field in enumerate(metadata['fields']):
            if field.get('lookup_table'):
                values[index] = metadata['lookup_tables'][field['lookup_table']][row[index]]
        return values
    count = 0
    for before, after in zip_longest(rows(base / 'points.bin'), rows(output / 'points.bin')):
        if before is None or after is None or decode(before, old_meta) != decode(after, new_meta):
            raise ValueError(f'Unchanged packed point differs at row {count}')
        count += 1
    return count


def build_quality_map_release(manifest_path: Path, output: Path, prefix: str = DEFAULT_PREFIX,
                              max_output_bytes: int = 350 * 1024**2) -> dict[str, Any]:
    manifest_path, output = manifest_path.resolve(), output.resolve()
    declared = read_json(manifest_path)
    base = Path(declared['base']['path']).resolve()
    ensure_new_output(output, base)
    estimate = estimate_output_bytes(base)
    free_before = verify_storage(output, estimate, max_output_bytes)
    quality_sha = sha256(manifest_path)
    prefix = prefix.strip('/')
    if not prefix or '..' in prefix.split('/') or '\\' in prefix:
        raise ValueError('Invalid immutable release prefix')
    print(f'Planned bounded output {estimate / 1024**2:.1f} MiB; quality manifest {quality_sha}', flush=True)
    view = load_quality_view(manifest_path)
    updates, patches, source_receipts = build_effective_detail_updates(view)
    if set(updates) != set(view.decisions):
        raise ValueError('Changed-detail projection does not cover every accepted event')
    output.mkdir(parents=True, exist_ok=True)
    patch_payload = {'schemaVersion': 1, 'baseManifestSha256': declared['base']['manifest_sha256'],
                     'qualityManifestSha256': quality_sha, 'patchCount': len(patches), 'patches': patches}
    write_gzip_json(output / 'detail_patches.json.gz', patch_payload)
    chunks = list(view.chunk_metadata.values())
    write_json(output / 'event_chunk_manifest.json', chunks)
    summaries, point_rows = [], []
    counters = {name: Counter() for name in COUNT_FIELDS}
    total, mapped = 0, 0
    bounds = None
    source_iter = iter(view.iter_summaries())
    for shard in view.shards:
        rows = []
        for _ in range(shard['event_count']):
            try:
                effective = next(source_iter)
            except StopIteration as error:
                raise ValueError('Effective summary stream ended early') from error
            row = apply_summary_update(effective, updates)
            total += 1
            for name, (field, default) in COUNT_FIELDS.items():
                counters[name][row.get(field) or default] += 1
            if row.get('has_coordinates'):
                mapped += 1
                point_rows.append(point_projection_from_summary(row))
                if bounds is None:
                    bounds = {'west': row['lon'], 'east': row['lon'], 'south': row['lat'], 'north': row['lat']}
                else:
                    bounds['west'] = min(bounds['west'], row['lon'])
                    bounds['east'] = max(bounds['east'], row['lon'])
                    bounds['south'] = min(bounds['south'], row['lat'])
                    bounds['north'] = max(bounds['north'], row['lat'])
            rows.append(row)
        if rows[0]['event_id'] != shard['start_event_id'] or rows[-1]['event_id'] != shard['end_event_id']:
            raise ValueError('Summary order/identity changed')
        write_gzip_json(output / 'summary_shards' / (shard['id'] + '.json.gz'), rows)
        summaries.append(dict(shard))
        print(f'Summary shards {len(summaries)}/{len(view.shards)}; events {total}', flush=True)
    if next(source_iter, None) is not None or total != view.validation['effective_records'] or mapped != view.validation['effective_mapped']:
        raise ValueError('Release census differs from validated quality view')
    write_json(output / 'summary_manifest.json', summaries)
    points = export_packed_points(point_rows, output, chunk_manifest=chunks)
    if points['row_count'] != mapped:
        raise ValueError('Packed map census differs from corrected summaries')
    traces = export_trace_artifacts(point_rows, output)
    for name in BIN_NAMES + META_NAMES:
        metadata_path = output / name
        if name in META_NAMES:
            metadata = read_json(metadata_path)
            metadata['qualityManifestSha256'] = quality_sha
            metadata['baseManifestSha256'] = declared['base']['manifest_sha256']
            write_json(metadata_path, metadata)
        gzip_file(metadata_path)
    profiles = build_profiles(point_rows, chunks, output, quality_sha)
    counts = {'events': total, 'mapped_events': mapped, 'unmapped_events': total - mapped,
              'event_chunks': len(chunks), 'summary_shards': len(summaries), 'mapped_bounds': bounds,
              'trace_events': traces['trace_events']['row_count'],
              'trace_segments': traces['trace_segments']['row_count'],
              'trace_aggregate_bins': traces['trace_aggregate_bins']['row_count'],
              **{name: dict(sorted(counter.items())) for name, counter in counters.items()}}
    canonical = copy.deepcopy(view.base_metadata)
    canonical['counts'] = counts
    canonical['source'] = {'quality_manifest_sha256': quality_sha,
                           'base_manifest_sha256': declared['base']['manifest_sha256'],
                           'quality_manifest': str(manifest_path)}
    canonical['quality_release'] = {'schema_version': 1, 'detail_overlay_required': True,
                                    'detail_chunks_shared_from_base': True, 'summary_gzip_only': True,
                                    'source_dates_and_ids_preserved': True,
                                    'changed_chronology_from_full_details': True,
                                    'original_account_projection_applied': False}
    canonical['policy']['quality_detail_overlay_required'] = True
    for destination, metadata in (('packed_points', points), ('packed_trace_events', traces['trace_events']),
                                   ('packed_trace_segments', traces['trace_segments']),
                                   ('packed_trace_aggregate_bins', traces['trace_aggregate_bins'])):
        canonical[destination].update({key: metadata[key] for key in ('schema_version', 'row_count', 'bytes_per_row')})
    write_json(output / 'canonical_web_manifest.json', canonical)
    for name in ('canonical_web_manifest.json', 'event_chunk_manifest.json', 'summary_manifest.json'):
        gzip_file(output / name)
    if sha256(manifest_path) != quality_sha:
        raise ValueError('Quality manifest changed during the build')
    unchanged_packed_rows = verify_unchanged_packed_points(base, output, set(view.decisions))
    files = artifact_receipts(output, prefix)
    total_bytes = sum(item['bytes'] for item in files)
    if total_bytes > max_output_bytes or total_bytes >= 1024**3:
        raise ValueError('Generated output exceeds approved cap; retain partial output for inspection')
    overlay_file = next(item for item in files if item['path'] == 'detail_patches.json.gz')
    receipt = {'schemaVersion': 1, 'generatedAtUtc': datetime.now(timezone.utc).isoformat(),
               'qualityManifestSha256': quality_sha,
               'baseManifestSha256': declared['base']['manifest_sha256'],
               'output': str(output), 'immutablePrefix': prefix,
               'counts': counts, 'qualityValidation': view.validation,
               'chronologyRecomputedRecords': len(updates), 'sourceChunkReads': source_receipts,
               'packedUnchangedRowsVerified': unchanged_packed_rows,
               'detailGuardContract': 'core8_plus_event_id_canonical_event_id_source_id_chunk_id_detail_index_with_explicit_null',
               'files': files, 'profiles': profiles,
               'detailOverlay': {**overlay_file, 'patchCount': len(patches),
                                 'baseManifestSha256': declared['base']['manifest_sha256'],
                                 'qualityManifestSha256': quality_sha},
               'storage': {'estimatedBytes': estimate, 'totalOutputBytes': total_bytes,
                           'r2UploadBytes': sum(item['bytes'] for item in files if item['delivery'] == 'r2'),
                           'pagesBytes': sum(item['bytes'] for item in files if item['delivery'] == 'pages'),
                           'freeBytesBefore': free_before, 'freeBytesAfter': shutil.disk_usage(output).free,
                           'filesLargerThan100MiB': [item['path'] for item in files if item['bytes'] > 100 * 1024**2],
                           'sourceCorpusCopied': False},
               'retention': {'purpose': 'Current quality map deployment delta; protected shared source chunks remain in place.',
                             'rebuild': 'py -3 scripts/build_quality_map_release.py --manifest ' + str(manifest_path) + ' --output ' + str(output),
                             'canonicalArtifact': 'This map delta plus the pinned quality manifest and guarded shared source detail chunks.',
                             'rollback': declared['retention'], 'supersededStaging': []},
               'productionPublished': False}
    write_json(output / 'map_release_receipt.json', receipt)
    print(json.dumps({'output': str(output), 'counts': counts, 'storage': receipt['storage'],
                      'detailOverlay': receipt['detailOverlay']}, ensure_ascii=True), flush=True)
    return receipt


def self_test() -> None:
    reader_spec = importlib.util.spec_from_file_location('quality_reader_test', DEFAULT_MANIFEST.parent / 'sparse_quality_view.py')
    reader = importlib.util.module_from_spec(reader_spec)
    reader_spec.loader.exec_module(reader)

    class FakeView:
        annotations = {}
        incident_relationships = {}
        def __init__(self, decision):
            self.decisions = {'123': [decision]}
        def _enrich(self, row):
            return reader.apply_decisions(row, self.decisions.get(str(row['event_id']), []))

    def sample():
        row = {'event_id': 123, 'canonical_event_id': 'native-123', 'source_id': '123',
               'chunk_id': 'chunk_000000', 'detail_index': 0, 'source': 'nuforc',
               'date_raw': '2001-01-02', 'date_iso': '2001-01-02', 'sort_date_iso': '2001-01-02',
               'date_precision': 'exact_day', 'time_raw': '20:00 UTC', 'location_raw': 'Town, WA, US',
               'lat': 47.0, 'lon': -122.0, 'coordinate_source': 'geocoded', 'location_precision': 'city',
               'has_coordinates': True, 'craft_type_inferred': 'disc_saucer',
               'craft_type_confidence': 'high', 'craft_type_source': 'shape_normalized',
               'same_day_match_strength': 'strong', 'raw_source_row': {'Occurred': 'Date is Approximate'},
               'source_provenance': [{'source_native_id': '123'}]}
        row.update(derive_event_chronology(row))
        decision = {'event_id': 123, 'decision_id': 'test-123', 'status': 'accepted_source_supported',
                    'base_manifest_sha256': reader.BASE_SHA, 'confidence': 'high',
                    'evidence_artifact': 'test.jsonl', 'guards': {key: row.get(key) for key in GUARD_FIELDS},
                    'set_fields': {'date_precision': 'approximate'}}
        decision['guards']['date_precision'] = 'exact_day'
        return row, decision

    class Tests(unittest.TestCase):
        def test_precision_downgrade_resets_time_preserves_native_date(self):
            raw, decision = sample()
            self.assertIsNotNone(raw['estimated_utc_timestamp_ms'])
            effective = effective_detail_from_source_row(FakeView(decision), raw)
            self.assertEqual(effective['date_precision'], 'approximate')
            self.assertIsNone(effective['estimated_utc_timestamp_ms'])
            self.assertEqual(effective['time_sort_kind'], 'unknown')
            self.assertEqual(effective['playback_sort_reason'], 'stable_fallback')
            for key in PROTECTED_FIELDS:
                self.assertEqual(effective.get(key), raw.get(key))
            patch = make_detail_patch(FakeView(decision), raw, effective, 'chunk_000000', 0)
            self.assertIsNone(patch['setFields']['estimated_utc_timestamp_ms'])
            self.assertEqual(patch['guards']['date_precision'], 'exact_day')
            self.assertEqual(patch['guards']['chunk_id'], 'chunk_000000')
            self.assertEqual(patch['guards']['detail_index'], 0)
            self.assertEqual(patch['guards']['canonical_event_id'], 'native-123')
            self.assertFalse(set(patch['setFields']).intersection(PROTECTED_FIELDS))

        def test_guard_mismatch_and_protected_edit_rejected(self):
            raw, decision = sample()
            wrong = copy.deepcopy(raw)
            wrong['location_raw'] = 'Another town'
            with self.assertRaises(ValueError):
                effective_detail_from_source_row(FakeView(decision), wrong)
            decision['set_fields']['source'] = 'mufon'
            with self.assertRaises(ValueError):
                effective_detail_from_source_row(FakeView(decision), raw)

        def test_full_detail_date_anchor_not_lost_in_summary(self):
            raw, decision = sample()
            decision['set_fields'] = {'lat': 48.0, 'lon': -123.0}
            view = FakeView(decision)
            detail = effective_detail_from_source_row(view, raw)
            summary = {key: value for key, value in raw.items() if key not in ('date_iso', 'raw_source_row', 'source_provenance')}
            updates = {'123': {**decision['set_fields'], **derive_event_chronology(detail)}}
            compact = apply_summary_update(summary, updates)
            self.assertEqual(compact['estimated_utc_timestamp_ms'], raw['estimated_utc_timestamp_ms'])
            self.assertNotIn('date_iso', compact)
            self.assertEqual(compact['sort_date_iso'], raw['sort_date_iso'])
            self.assertEqual(compact['lat'], 48.0)

        def test_gzip_summary_binary_and_delivery_contract(self):
            raw, decision = sample()
            effective = effective_detail_from_source_row(FakeView(decision), raw)
            with tempfile.TemporaryDirectory(prefix='quality-map-selftest-') as directory:
                root = Path(directory)
                write_gzip_json(root / 'summary_shards/summary_000000.json.gz', [effective])
                self.assertFalse((root / 'summary_shards/summary_000000.json').exists())
                self.assertEqual(read_json(root / 'summary_shards/summary_000000.json.gz')[0]['event_id'], 123)
                chunks = [{'id': 'chunk_000000', 'file': 'chunk_000000.json', 'event_count': 1,
                           'start_event_id': 123, 'end_event_id': 123}]
                metadata = export_packed_points([effective], root, chunk_manifest=chunks)
                packed = ROW_STRUCT.unpack((root / 'points.bin').read_bytes())
                self.assertEqual(packed[0], 123)
                self.assertEqual(packed[4], MISSING_INT64)
                self.assertEqual(metadata['lookup_tables']['date_precisions'][packed[13]], 'approximate')
                write_gzip_json(root / 'detail_patches.json.gz', {'patches': []})
                receipts = artifact_receipts(root, DEFAULT_PREFIX)
                overlay = next(item for item in receipts if item['path'] == 'detail_patches.json.gz')
                self.assertEqual(overlay['delivery'], 'pages')
                self.assertEqual(overlay['publicPath'], 'data/quality_detail_patches.json.gz')
                self.assertEqual(next(item for item in receipts if item['path'] == 'points.bin')['delivery'], 'local')
                self.assertEqual(next(item for item in receipts if item['path'].startswith('summary_shards/'))['immutableKey'],
                                 DEFAULT_PREFIX + '/summary_shards/summary_000000.json.gz')
                with self.assertRaises(ValueError):
                    ensure_new_output(root, root / 'protected')

        def test_omitted_utc_midpoint_restored_only_from_utc_key(self):
            raw, _ = sample()
            summary = {key: value for key, value in raw.items() if key != 'estimated_utc_timestamp_ms'}
            projection = point_projection_from_summary(summary)
            self.assertEqual(projection['estimated_utc_timestamp_ms'], raw['estimated_utc_timestamp_ms'])
            self.assertNotIn('estimated_utc_timestamp_ms', summary)
            summary['playback_sort_key'] = [2, 1200, 0, 0, 0, 123]
            self.assertNotIn('estimated_utc_timestamp_ms', point_projection_from_summary(summary))
            summary['estimated_utc_timestamp_ms'] = None
            summary['playback_sort_key'] = raw['playback_sort_key']
            self.assertIsNone(point_projection_from_summary(summary)['estimated_utc_timestamp_ms'])

        def test_no_silent_overwrite(self):
            with tempfile.TemporaryDirectory(prefix='quality-map-selftest-') as directory:
                root = Path(directory)
                (root / 'keep.txt').write_text('protected')
                with self.assertRaises(ValueError):
                    ensure_new_output(root, root.parent / 'base')
                self.assertEqual((root / 'keep.txt').read_text(), 'protected')

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful():
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--immutable-prefix', default=DEFAULT_PREFIX)
    parser.add_argument('--max-output-mib', type=int, default=350)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        build_quality_map_release(args.manifest, args.output, args.immutable_prefix, args.max_output_mib * 1024**2)


if __name__ == '__main__':
    main()
