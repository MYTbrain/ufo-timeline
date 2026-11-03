"""Resolve the five reported examples and their explicitly identified source copies.

This is a seven-record, source-specific adjudication, never a fuzzy name rule.
Original records, dates, narratives, and source identities remain unchanged.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from audit_mapping_recovery import digest, read_json

TARGETS = {198690462474303, 1228969906984748, 1953936209449515,
           3426756551886707, 4173291518594354, 4102805855565119,
           2425738473207061}
GUARDS = ('source', 'sort_date_iso', 'location_raw', 'lat', 'lon',
          'coordinate_source', 'location_precision', 'has_coordinates')
IDENTITY = ('event_id', 'canonical_event_id', 'source_id', 'chunk_id', 'detail_index')


def build(repo: Path, shared: Path, evidence: Path):
    output = evidence / 'manual-examples'
    output.mkdir(exist_ok=True)
    if (output / 'accepted-decisions.jsonl.gz').exists():
        raise ValueError('Manual decisions already exist')
    examples_path = repo / 'docs/qa/mapping-recovery-20261103/examples/screenshot-case-review.json'
    examples = {r['event_id']: r for r in read_json(examples_path)['records']}
    quality = read_json(shared / 'data/research/database_quality_20261007/quality_view_manifest.json')
    plan = read_json(repo / 'releases/workspace-analysis-20261008/delivery_plan.json')
    found = {}
    for pin in plan['uploads']:
        if '/summary_shards/' not in pin['key']:
            continue
        path = Path(pin['source'])
        if digest(path) != pin['sha256']:
            raise ValueError('Current summary pin mismatch')
        for row in read_json(path):
            if row['event_id'] in TARGETS:
                found[row['event_id']] = row
    if set(found) != TARGETS:
        raise ValueError('Missing reviewed record')
    # Independently check both original merged members, not just the chosen text.
    csv_path = shared / 'UFO Databases/mufonpy.csv'
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        members = [r for r in csv.DictReader(stream) if r.get('No') in ('54548', '54592')]
    if len(members) != 2 or any('Kaloli' not in r['Long Description'] or
            'Keaau-Pahoa' not in r['Location of Event'] or
            not r['Date/Time of Event'].startswith('2014-03-08') for r in members):
        raise ValueError('Merged Hawaiian source members do not agree on locality')
    updb_path = shared / 'UFO Databases/phenomenAInon_UPDB.csv'
    with updb_path.open(encoding='utf-8-sig', newline='') as stream:
        copies = [r for r in csv.DictReader(stream) if r.get('id') in ('5504302', '5504346')]
    if len(copies) != 2 or {r['source_id'] for r in copies} != {'54548', '54592'} or any(
            'Kaloli' not in r['description'] or r['country'] != 'US' for r in copies):
        raise ValueError('Merged UPDB source members do not agree on locality')
    query_path = evidence / 'qualified-location-candidates/query-evidence.jsonl.gz'
    anchors = {}
    with gzip.open(query_path, 'rt', encoding='utf8') as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('country') == 'US' and row.get('admin1') == 'NM' and row.get('locality') in ('Albuquerque', 'Los Lunas'):
                if len(row['features']) != 1:
                    raise ValueError('Compound reference anchor is ambiguous')
                anchors[row['locality']] = row['features'][0]
    if len(anchors) != 2:
        raise ValueError('Missing independently matched New Mexico anchors')
    decisions, originals = [], []
    for eid, summary in sorted(found.items()):
        relative = 'event_chunks/' + summary['chunk_id'] + '.json.gz'
        pin = quality['base']['files'][relative]
        path = Path(quality['base']['path']) / relative
        if digest(path) != pin['sha256']:
            raise ValueError('Source detail pin mismatch')
        raw = read_json(path)[summary['detail_index']]
        assert raw['event_id'] == eid
        evidence_id = 'manual-location-20261103-' + str(eid)
        review = {'evidence_id': evidence_id, 'original_summary': summary,
                  'original_detail': raw, 'source_pin': {'path': str(path), **pin}}
        if eid in (4173291518594354, 2425738473207061):
            if eid == 2425738473207061:
                native = raw['raw_source_row']
                assert native['source_id'] == 'S107728' and native['name'] == 'NUFORC'
                review['source_identity_basis'] = 'Explicit NUFORC S107728 identity, matching date and preserved narrative; linked original report supplies NM jurisdiction.'
            a, b = anchors['Los Lunas'], anchors['Albuquerque']
            lat, lon = round((a['lat'] + b['lat']) / 2, 3), round((a['lon'] + b['lon']) / 2, 3)
            ref = {'kind': 'compound_area', 'label': 'Los Lunas / Albuquerque, New Mexico',
                   'note': 'Approximate area reference between the two named places; the observer location is unspecified. Original spelling is retained in the report.',
                   'authority_ids': [a['geonameId'], b['geonameId']], 'evidence_id': evidence_id}
            precision = 'approximate'
            review.update(authorities=anchors, source_url='https://nuforc.org/sighting/?id=107728',
                          decision='Interpret Albuqerque as Albuquerque only for this explicitly NM-scoped original report and its identified source copy. Midpoint is a display reference, not a measured location or boundary.')
        else:
            original_id = 198690462474303 if eid == 4102805855565119 else eid
            proposal = examples[original_id]['proposal']
            lat, lon = proposal['lat'], proposal['lon']
            precision = 'city'
            ref = {'kind': 'locality', 'label': proposal['matched_place'],
                   'note': 'Approximate locality reference; the marker is not the exact observer or object position.',
                   'authority_ids': [proposal['geoname_id']], 'evidence_id': evidence_id}
            review['proposal_evidence'] = proposal
            if original_id == 198690462474303:
                review['merged_member_review'] = {'mufon_members': members, 'updb_members': copies,
                    'basis': 'Both native submissions describe the observer on Kaloli Avenue on the same date. County police geography identifies the locality. Source members reviewed separately.'}
            if eid == 4102805855565119:
                ref['note'] += ' Corrected a previous marker on the wrong Hawaiian island.'
        guards = {key: summary.get(key) for key in GUARDS}
        guards.update({key: raw.get(key) for key in IDENTITY})
        decisions.append({'event_id': eid, 'decision_id': evidence_id, 'status': 'accepted_source_supported',
            'accepted': True, 'guards': guards,
            'set_fields': {'lat': lat, 'lon': lon, 'has_coordinates': True,
                'location_precision': precision, 'coordinate_source': 'reviewed_area_reference' if precision == 'approximate' else 'reviewed_locality_reference',
                'location_reference': ref},
            'evidence_artifact': 'manual-examples/review-evidence.json.gz'})
        originals.append(review)
    with gzip.open(output / 'accepted-decisions.jsonl.gz', 'wt', encoding='utf8') as stream:
        for row in decisions:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    with gzip.open(output / 'review-evidence.json.gz', 'wt', encoding='utf8') as stream:
        json.dump({'reviews': originals, 'example_review_sha256': digest(examples_path),
                   'source_csv_pins': [{'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in (csv_path, updb_path)]}, stream, ensure_ascii=False)
    print(json.dumps({'decisions': len(decisions), 'newly_mapped': sum(not r['guards']['has_coordinates'] for r in decisions), 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shared', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.shared, args.evidence)
