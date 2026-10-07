"""Verify compact evidence bytes and accepted-decision contracts, read-only."""
from __future__ import annotations
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = {'source', 'sort_date_iso', 'location_raw', 'lat', 'lon',
        'coordinate_source', 'location_precision', 'has_coordinates'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, size, expected):
    target = (ROOT / path).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError('Unsafe package path')
    data = target.read_bytes()
    if len(data) != size or sha(data) != expected:
        raise ValueError(f'Package bytes disagree: {path}')
    return data


def verify():
    manifest = json.loads((ROOT / 'package_manifest.json').read_bytes())
    seen = set()
    kinds = Counter()
    accepted = 0
    date_downgrades = 0
    restored = {}
    for entry in manifest['files']:
        data = checked(entry['package_path'], entry['bytes'], entry['sha256'])
        if entry['storage_encoding'] == 'gzip-original-bytes':
            data = gzip.decompress(data)
        if len(data) != entry['source_bytes'] or sha(data) != entry['source_sha256']:
            raise ValueError(f'Decoded source pin disagrees: {entry["source_path"]}')
        restored[entry['source_path']] = data
        kinds[entry['role']] += 1
        if entry['role'] != 'accepted_sparse_decisions':
            continue
        rows = ([json.loads(line) for line in data.splitlines() if line.strip()]
                if entry['decision_encoding'] == 'jsonl' else json.loads(data)['decisions'])
        if len(rows) != entry['rows']:
            raise ValueError('Decision row count disagrees')
        for row in rows:
            if row['event_id'] in seen or row['status'] != 'accepted_source_supported':
                raise ValueError('Duplicate or non-accepted decision')
            seen.add(row['event_id'])
            if not CORE.issubset(row['guards']):
                raise ValueError('Missing original-record guards')
            if not row.get('provenance') or not row.get('evidence'):
                raise ValueError('Missing provenance/evidence')
            if row['set_fields'].get('date_precision') == 'approximate':
                if row['guards'].get('date_precision') != 'exact_day':
                    raise ValueError('Date downgrade lacks original precision guard')
                date_downgrades += 1
            accepted += 1
    for entry in manifest['generated_files']:
        checked(entry['package_path'], entry['bytes'], entry['sha256'])
    prefix = 'data/research/database_quality_20261007/'
    quality = restored[prefix + 'quality_view_manifest.json']
    if sha(quality) != manifest['quality_manifest_sha256']:
        raise ValueError('Quality manifest pin disagrees')
    validation = json.loads(restored[prefix + 'continuation_02/quality_view_validation.json'])
    if validation['quality_manifest_sha256'] != sha(quality):
        raise ValueError('Validation is for a different quality manifest')
    counts = validation['validation']
    if counts['accepted_decisions'] != accepted or counts['modified_records'] != len(seen):
        raise ValueError('Final validation accepted counts disagree')
    if counts['date_precision_transitions']['exact_day -> approximate'] != date_downgrades:
        raise ValueError('Final validation date precision count disagrees')
    map_receipt = json.loads(restored['data/releases/quality-20261007/map_delta/map_release_receipt.json'])
    analysis = json.loads(restored['data/releases/quality-20261007/analysis_delta/analysis_release_receipt.json'])
    if map_receipt['qualityManifestSha256'] != sha(quality):
        raise ValueError('Map receipt quality pin disagrees')
    if analysis['map_receipt_sha256'] != sha(restored['data/releases/quality-20261007/map_delta/map_release_receipt.json']):
        raise ValueError('Analysis map receipt pin disagrees')
    package_files = [p for p in ROOT.rglob('*') if p.is_file()]
    total = sum(p.stat().st_size for p in package_files)
    if total >= 10 * 1024 * 1024:
        raise ValueError('Package exceeds approved budget')
    if any(p.suffix.lower() in {'.zip', '.7z', '.db', '.sqlite', '.bin', '.pdf', '.png', '.jpg'} for p in package_files):
        raise ValueError('Prohibited archive/corpus/runtime/media copy')
    return {'status': 'pass', 'source_files_checked': len(manifest['files']),
            'accepted_decisions': accepted, 'distinct_changed_records': len(seen),
            'date_precision_downgrades': date_downgrades,
            'quality_manifest_sha256': sha(quality), 'package_manifest_sha256': sha((ROOT / 'package_manifest.json').read_bytes()),
            'effective_records': counts['effective_records'], 'effective_mapped': counts['effective_mapped'],
            'effective_unmapped': counts['effective_unmapped'], 'current_package_files': len(package_files),
            'current_package_bytes': total, 'archives_copied': False, 'full_catalog_verified_again': False,
            'scope': 'Byte preservation, sparse decision guards/counts and final validation/map/analysis receipt join. Full shared-catalog/source evidence is not reread by this bounded handoff check.'}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
