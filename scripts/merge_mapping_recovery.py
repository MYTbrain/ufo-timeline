"""Combine reviewed recovery lanes, preserving every decision's evidence and priority."""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import gzip
import json
from pathlib import Path
from audit_mapping_recovery import digest

LANES = [
    ('area', 'area-reference-candidates/accepted-area-decisions.jsonl.gz'),
    ('locality', 'location-source-review-v2/accepted-decisions.jsonl.gz'),
    ('source_coordinate', 'source-coordinates/accepted-decisions.jsonl.gz'),
    ('manual', 'manual-examples/accepted-decisions.jsonl.gz'),
]


def normalize(row, lane, evidence_path):
    row = copy.deepcopy(row)
    row['guards'] = row.get('guards', row.get('guard', {}))
    row['guards'].update(row.get('source_identity', {}))
    row['decision_id'] = row.get('decision_id', row.get('evidence_id'))
    row['status'] = 'accepted_source_supported'
    row['accepted'] = True
    fields = row['set_fields']
    if 'location_reference' not in fields:
        evidence = row['location_reference_evidence']
        kind = 'source_coordinate' if lane == 'source_coordinate' else ('compound_area' if fields['location_precision'] == 'approximate' else 'locality')
        note = evidence.get('uncertaintyStatement') or evidence.get('uncertaintyNote')
        if not note:
            note = ('Source-reported position; accuracy and datum are not independently established.' if kind == 'source_coordinate'
                    else 'Approximate locality reference; not the exact observer or object position.')
        ref = {'kind': kind, 'label': evidence.get('label') or evidence.get('originalLocationLabel') or row['guards']['location_raw'],
               'note': note, 'evidence_id': row['decision_id'],
               'authority_ids': ['geonames:' + str(f['geonameId']) for f in evidence.get('authorityFeatures', [])]}
        if evidence.get('radiusKm'):
            ref['radius_km'] = evidence['radiusKm']
        fields['location_reference'] = ref
        fields['coordinate_source'] = ('reviewed_original_source_coordinate' if kind == 'source_coordinate' else
                                       'reviewed_area_reference' if kind == 'compound_area' else 'reviewed_locality_reference')
    ref = fields['location_reference']
    if len(json.dumps(ref, ensure_ascii=False).encode()) > 1024 or len(ref['label']) > 160 or len(ref['note']) > 600:
        raise ValueError('Reference exceeds compact runtime contract: ' + str(row['event_id']))
    # Runtime only needs the compact note; the complete per-lane ledger remains pinned.
    return {'event_id': row['event_id'], 'decision_id': row['decision_id'], 'status': row['status'],
            'accepted': True, 'guards': row['guards'], 'set_fields': fields,
            'evidence_artifact': evidence_path, 'review_lane': lane}


def merge(root):
    result, overrides, inputs = {}, [], []
    target = root / 'accepted-decisions.jsonl.gz'
    if target.exists():
        raise ValueError('Refusing to replace merged accepted decisions')
    for lane, relative in LANES:
        path = root / relative
        count = 0
        with gzip.open(path, 'rt', encoding='utf8') as stream:
            for line in stream:
                row = normalize(json.loads(line), lane, relative)
                eid = row['event_id']
                if eid in result:
                    overrides.append({'event_id': eid, 'replaced': result[eid]['decision_id'],
                                      'chosen': row['decision_id'], 'reason': 'independently reviewed more specific source evidence'})
                    for key in ('source', 'sort_date_iso', 'location_raw', 'lat', 'lon', 'has_coordinates'):
                        if row['guards'].get(key) != result[eid]['guards'].get(key):
                            raise ValueError('Conflicting baseline guards')
                result[eid] = row
                count += 1
        inputs.append({'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size, 'decisions': count})
    with gzip.open(target, 'wt', encoding='utf8', newline='\n') as stream:
        for _, row in sorted(result.items()):
            stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    new = sum(not r['guards']['has_coordinates'] for r in result.values())
    receipt = {'inputs': inputs, 'accepted_records': len(result), 'newly_mapped': new,
               'corrected_existing_points': len(result) - new, 'remaining_unmapped': 120016-new,
               'mapped_after': 582877+new,
               'by_reference_kind': dict(Counter(r['set_fields']['location_reference']['kind'] for r in result.values())),
               'by_source': dict(Counter(r['guards']['source'] for r in result.values())), 'overrides': overrides,
               'output': {'path': str(target), 'bytes': target.stat().st_size, 'sha256': digest(target)},
               'policy': 'All current records screened; conservative source-supported mappings only. Mapped counts are source representations, not independent incidents.'}
    (root / 'accepted-decisions-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('inputs','overrides')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    merge(parser.parse_args().root)
