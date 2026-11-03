"""Inventory every served record and retain only unresolved evidence, without copying the corpus."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    with (gzip.open(path, 'rt', encoding='utf-8') if path.suffix == '.gz'
          else path.open(encoding='utf-8')) as f:
        return json.load(f)


def usable(row):
    return all(isinstance(row.get(k), (int, float)) and not isinstance(row[k], bool)
               and math.isfinite(row[k]) and abs(row[k]) <= limit
               for k, limit in [('lat', 90), ('lon', 180)])


def audit(plan_path, quality_path, output):
    output.mkdir(parents=True, exist_ok=True)
    targets = [output / name for name in ('unmapped-summary.jsonl.gz', 'unmapped-details.jsonl.gz', 'audit.json')]
    if any(p.exists() for p in targets):
        raise ValueError('Refusing to replace a previous audit')
    plan = read_json(plan_path)
    quality = read_json(quality_path)
    base = Path(quality['base']['path'])
    shards = [r for r in plan['uploads'] if '/summary_shards/' in r['key']]
    counts, sources, precisions, anomalies = Counter(), defaultdict(Counter), Counter(), Counter()
    labels, sample_anomalies, seen, unresolved = Counter(), [], set(), defaultdict(list)
    pinned = []
    with gzip.open(targets[0], 'wt', encoding='utf-8', newline='\n', compresslevel=6) as out:
        for n, pin in enumerate(shards):
            path = Path(pin['source'])
            if path.stat().st_size != pin['bytes'] or digest(path) != pin['sha256']:
                raise ValueError('Current served summary pin mismatch: ' + str(path))
            pinned.append({k: pin[k] for k in ('source', 'bytes', 'sha256', 'url')})
            for row in read_json(path):
                eid = row['event_id']
                if eid in seen:
                    raise ValueError('Duplicate event ID: ' + str(eid))
                seen.add(eid)
                has_point = usable(row)
                flag = bool(row.get('has_coordinates'))
                counts['events'] += 1
                status = 'mapped' if flag and has_point else 'unmapped'
                counts[status] += 1
                sources[row.get('source', 'unknown')][status] += 1
                if has_point != flag:
                    anomalies['coordinate_flag_disagreement'] += 1
                    if len(sample_anomalies) < 30:
                        sample_anomalies.append({k: row.get(k) for k in ('event_id', 'source', 'location_raw', 'lat', 'lon', 'has_coordinates')})
                if status == 'mapped':
                    continue
                precisions[str(row.get('location_precision'))] += 1
                labels[(row.get('source', 'unknown'), str(row.get('location_raw') or '').strip())] += 1
                unresolved[row['chunk_id']].append(row)
                out.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
            if (n + 1) % 10 == 0:
                print(json.dumps({'phase':'summaries', 'shards': n + 1, **counts}), flush=True)
    if counts['events'] != plan['counts']['events'] or counts['mapped'] != plan['counts']['mapped']:
        raise ValueError('Served count mismatch')
    details = 0
    detail_pins = []
    with gzip.open(targets[1], 'wt', encoding='utf-8', newline='\n', compresslevel=6) as out:
        for n, (chunk_id, needed) in enumerate(sorted(unresolved.items())):
            relative = 'event_chunks/' + chunk_id + '.json.gz'
            pin = quality['base']['files'][relative]
            path = base / relative
            if path.stat().st_size != pin['bytes'] or digest(path) != pin['sha256']:
                raise ValueError('Original source chunk pin mismatch: ' + str(path))
            rows = read_json(path)
            if isinstance(rows, dict):
                rows = rows['events']
            detail_pins.append(dict(path=str(path), **pin))
            for summary in needed:
                row = rows[summary['detail_index']]
                if row['event_id'] != summary['event_id'] or row['source'] != summary['source']:
                    raise ValueError('Original detail identity mismatch')
                record = {'summary': summary, 'source_detail': row,
                          'provenance': {'source_chunk': str(path), 'sha256': pin['sha256'],
                                         'detail_index': summary['detail_index'],
                                         'source_detail_is_immutable_original': True,
                                         'summary_is_current_effective_view': True}}
                out.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
                details += 1
            if sum(p.stat().st_size for p in targets[:2]) > 256 * 1024**2:
                raise ValueError('Sparse evidence output exceeded 256 MiB cap')
            if (n + 1) % 30 == 0:
                print(json.dumps({'phase': 'original_details', 'chunks': n + 1, 'unmapped_details': details}), flush=True)
    if details != counts['unmapped']:
        raise ValueError('Incomplete original detail inventory')
    result = {'schema': 'ufo-full-unmapped-audit-v1', 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'Every current served source representation; map locations are not independent incident counts.',
              'plan': {'path': str(plan_path.resolve()), 'sha256': digest(plan_path)},
              'source_quality_manifest': {'path': str(quality_path.resolve()), 'sha256': digest(quality_path)},
              'counts': counts, 'by_source': sources, 'unmapped_by_declared_precision': precisions,
              'coordinate_anomalies': anomalies, 'anomaly_examples': sample_anomalies,
              'unmapped_unique_source_labels': len(labels),
              'top_unmapped_labels': [{'source': s, 'location': l, 'records': c} for (s, l), c in labels.most_common(100)],
              'current_summary_pins': pinned, 'original_detail_pins': detail_pins,
              'outputs': [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in targets[:2]],
              'source_or_runtime_mutated': False, 'accepted_new_coordinates': 0,
              'retention': 'Retain this sparse evidence and audit for the recovery; reconstruct with pinned inputs and scripts/audit_mapping_recovery.py. No full corpus or release copy created.'}
    targets[2].write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: result[k] for k in ('counts', 'by_source', 'coordinate_anomalies', 'unmapped_unique_source_labels', 'outputs')}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--quality-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.plan, args.quality_manifest, args.output)
