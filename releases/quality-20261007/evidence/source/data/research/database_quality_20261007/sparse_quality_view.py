"""Read the reviewed quality catalog without copying or overwriting its base.

Default counts retain all source representations. Optional account projection
only suppresses agreeing original-account republications within a selection.
No packed map, precomputed trace or analysis binary is exposed by this reader:
consumers must derive those outputs from these effective rows.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from collections import Counter

GUARD_FIELDS = {
    'source', 'sort_date_iso', 'location_raw', 'lat', 'lon',
    'coordinate_source', 'location_precision', 'has_coordinates',
}
EDIT_FIELDS = (GUARD_FIELDS - {'source', 'sort_date_iso'}) | {'city', 'country', 'state_province', 'date_precision'}
BASE_SHA = '242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def checked_path(root, pin):
    root = Path(root).resolve()
    artifact_root = Path(pin.get('artifact_root', root)).resolve()
    if artifact_root != root and artifact_root != root.parent / 'database_quality_20261006':
        raise ValueError('Undeclared shared artifact directory')
    path = (artifact_root / pin['path']).resolve()
    if not path.is_relative_to(artifact_root):
        raise ValueError('Artifact escapes its declared directory')
    if path.stat().st_size != pin['bytes'] or sha256(path) != pin['sha256']:
        raise ValueError(f'Artifact pin mismatch: {pin["path"]}')
    return path


def point_is_valid(row):
    lat, lon = row.get('lat'), row.get('lon')
    if row.get('has_coordinates') is not True:
        return row.get('has_coordinates') is False and lat is None and lon is None
    return (
        type(lat) in {int, float} and type(lon) in {int, float}
        and math.isfinite(lat) and math.isfinite(lon)
        and -90 <= lat <= 90 and -180 <= lon <= 180
    )


def apply_decisions(base_row, decisions):
    """All guards refer to the original row, never an earlier patch's output."""
    edits = {}
    before = {}
    trail = []
    for decision in decisions:
        if decision.get('status') != 'accepted_source_supported':
            raise ValueError('Unaccepted research candidate cannot edit the view')
        if decision.get('base_manifest_sha256') != BASE_SHA:
            raise ValueError('Decision base pin mismatch')
        if str(decision.get('event_id')) != str(base_row.get('event_id')):
            raise ValueError('Decision event ID mismatch')
        guard_keys = set(decision.get('guards', {}))
        if not GUARD_FIELDS.issubset(guard_keys) or not guard_keys.issubset(GUARD_FIELDS | {'date_precision'}):
            raise ValueError('Incomplete or unsupported decision guards')
        if 'date_precision' in decision.get('set_fields', {}) and 'date_precision' not in guard_keys:
            raise ValueError('Date precision edit requires its own exact before guard')
        if 'date_precision' in decision.get('set_fields', {}) and decision['set_fields']['date_precision'] != 'approximate':
            raise ValueError('Only source-confirmed precision downgrade is supported')
        if 'date_precision' in decision.get('set_fields', {}) and decision['guards']['date_precision'] != 'exact_day':
            raise ValueError('Date precision downgrade requires an exact-day before value')
        for field, value in decision['guards'].items():
            if base_row.get(field) != value:
                raise ValueError(f'Stale decision guard: {field}')
        fields = decision.get('set_fields', {})
        if not fields or not set(fields).issubset(EDIT_FIELDS):
            raise ValueError('Unsupported quality-view edit')
        for field, value in fields.items():
            if field in edits and edits[field] != value:
                raise ValueError(f'Conflicting decisions for {field}')
            edits[field] = value
            before[field] = base_row.get(field)
        trail.append({
            'decision_id': decision['decision_id'],
            'kind': decision.get('kind', decision.get('scope')),
            'confidence': decision['confidence'],
            'geographic_role': decision.get('geographic_role'),
            'evidence_artifact': decision['evidence_artifact'],
        })
    result = dict(base_row)
    result.update(edits)
    if not point_is_valid(result):
        raise ValueError('Inconsistent effective coordinate fields')
    if trail:
        result['quality_view_changes'] = {
            'original_values': before,
            'decisions': trail,
            'source_record_preserved': True,
        }
    return result


class QualityView:
    def __init__(self, manifest_path, base_dir=None):
        self.manifest_path = Path(manifest_path).resolve()
        self.root = self.manifest_path.parent
        self.manifest = json.loads(self.manifest_path.read_bytes())
        if self.manifest.get('schema_version') != 1 or self.manifest.get('policy') != 'guarded_sparse_quality_view_v2':
            raise ValueError('Unsupported quality-view manifest')
        checked_path(self.root, self.manifest['reader'])
        self.base = Path(base_dir or self.manifest['base']['path']).resolve()
        if self.manifest['base']['manifest_sha256'] != BASE_SHA:
            raise ValueError('Unsupported canonical base')
        self.pins = self.manifest['base']['files']
        if self.pins['canonical_web_manifest.json']['sha256'] != BASE_SHA:
            raise ValueError('Verified canonical file does not match declared base pin')
        for name in ['canonical_web_manifest.json', 'summary_manifest.json', 'event_chunk_manifest.json']:
            self._base_file(name)
        self.base_metadata = json.loads((self.base / 'canonical_web_manifest.json').read_bytes())
        self.shards = json.loads((self.base / 'summary_manifest.json').read_bytes())
        self.chunk_metadata = {
            row['id']: row for row in json.loads((self.base / 'event_chunk_manifest.json').read_bytes())
        }
        self.decisions = {}
        self.annotations = {}
        self.locators = {}
        decision_ids = set()
        for artifact in self.manifest['decision_artifacts']:
            target = checked_path(self.root, artifact)
            if artifact['encoding'] == 'jsonl':
                with target.open(encoding='utf8') as handle:
                    rows = [json.loads(line) for line in handle if line.strip()]
            elif artifact['encoding'] == 'json-decisions':
                rows = json.loads(target.read_bytes())['decisions']
            else:
                raise ValueError('Unsupported decision encoding')
            if len(rows) != artifact['rows']:
                raise ValueError('Decision artifact row count mismatch')
            for row in rows:
                row = copy.deepcopy(row)
                eid = str(row['event_id'])
                if row['decision_id'] in decision_ids:
                    raise ValueError('Repeated decision ID')
                decision_ids.add(row['decision_id'])
                declared_base = row.get('base_manifest_sha256', row.get('provenance', {}).get('base_manifest_sha256'))
                if declared_base != BASE_SHA:
                    raise ValueError('Decision base pin mismatch')
                row['base_manifest_sha256'] = declared_base
                row['evidence_artifact'] = artifact['path']
                provenance = row['provenance']
                locator = provenance.get('detail_locator', provenance)
                chunk = locator.get('chunk_id')
                index = locator.get('detail_index')
                pin = locator.get('compressed_sha256', locator.get('detail_gzip_sha256'))
                self._check_locator(chunk, index, pin)
                if eid in self.locators and self.locators[eid] != (chunk, index):
                    raise ValueError('Conflicting decision locator')
                self.locators[eid] = (chunk, index)
                self.decisions.setdefault(eid, []).append(row)
        self.incident_relationships = {}
        if 'incident_relationships' in self.manifest:
            relationship_pin = self.manifest['incident_relationships']
            relationships = json.loads(checked_path(self.root, relationship_pin).read_bytes())
            if not isinstance(relationships, list) or len(relationships) != relationship_pin['rows']:
                raise ValueError('Incident relationship row count mismatch')
            relationship_ids = set()
            for row in relationships:
                if (row.get('status') != 'accepted_source_supported_incident_identity'
                    or row.get('do_not_merge_records') is not True
                    or row.get('not_independent_incident_count') is not True
                    or row.get('retain_all_narratives_conflicts_and_member_provenance') is not True):
                    raise ValueError('Unsupported incident relationship policy')
                if not row.get('link_id') or row['link_id'] in relationship_ids:
                    raise ValueError('Repeated or missing incident relationship ID')
                relationship_ids.add(row['link_id'])
                members = [str(eid) for eid in row['member_event_ids']]
                if len(members) < 2 or len(set(members)) != len(members) or not set(members).issubset(self.decisions):
                    raise ValueError('Relationship member lacks guarded source evidence')
                for eid in members:
                    self.incident_relationships.setdefault(eid, []).append(row)
        annotation_pin = self.manifest['date_review_annotations']
        target = checked_path(self.root, annotation_pin)
        with target.open(encoding='utf8') as handle:
            for line in handle:
                row = json.loads(line)
                eid = str(row['event_id'])
                if row.get('status') != 'review_only_no_date_correction' or 'set_fields' in row:
                    raise ValueError('Date review annotations cannot overwrite dates')
                if row.get('base_manifest_sha256') != BASE_SHA:
                    raise ValueError('Date annotation base pin mismatch')
                if set(row.get('guards', {})) != {'source', 'sort_date_iso', 'date_precision'} or row['guards']['source'] != 'phenomenainon_updb':
                    raise ValueError('Incomplete date annotation guards')
                if eid in self.annotations:
                    raise ValueError('Repeated date review annotation')
                self.annotations[eid] = row
                loc = (row['updb_locator']['chunk_id'], row['updb_locator']['detail_index'])
                self._check_locator(*loc, row['updb_locator']['compressed_sha256'])
                primary = row['primary_locator']
                self._check_locator(primary['chunk_id'], primary['detail_index'], primary['compressed_sha256'])
                if eid in self.locators and self.locators[eid] != loc:
                    raise ValueError('Conflicting date annotation locator')
                self.locators[eid] = loc
        if len(self.annotations) != annotation_pin['rows']:
            raise ValueError('Date annotation row count mismatch')
        self._chunk_cache = None
        # Read all small summaries before exposing a view, not the full corpus.
        self.validation = self._validate_summaries()
        loader_pin = self.manifest['account_loader']
        loader_path = checked_path(self.root, loader_pin)
        module_spec = importlib.util.spec_from_file_location('quality_account_loader', loader_path)
        self.account_loader = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(self.account_loader)
        self.account_manifest_path = checked_path(self.root, self.manifest['account_manifest'])
        account_manifest = json.loads(self.account_manifest_path.read_bytes())
        for chunk, pin in account_manifest['detailChunkPins'].items():
            if self.pins[f'event_chunks/{chunk}.json.gz']['sha256'] != pin['sha256']:
                raise ValueError('Account detail pin differs from canonical contract')
        self.accounts = {}
        eligible = invalidated = 0
        # Exhaust the validating stream before making any metadata available.
        for row in self.account_loader.iter_account_links(self.account_manifest_path, BASE_SHA):
            p, u = row['primary']['eventId'], row['updb']['eventId']
            strict = row['strictProjectionEligible']
            changed = p in self.decisions or u in self.decisions
            eligible += int(strict and not changed)
            invalidated += int(strict and changed)
            key = row['accountKey']
            partition = sys.intern(row['partition'])
            flags = tuple(sys.intern(flag) for flag in row['reviewFlags'])
            for role, other in [('primary', u), ('updb', p)]:
                item = row[role]
                self._check_locator(item['chunk'], item['index'], account_manifest['detailChunkPins'][item['chunk']]['sha256'])
                self.accounts[item['eventId']] = (
                    key, other, role, partition, flags, bool(strict and not changed),
                    sys.intern(item['chunk']), item['index'],
                )
        self.validation.update({
            'original_account_links': len(self.accounts) // 2,
            'strict_base_projection_candidates': account_manifest['counts']['strictProjectionEligible'],
            'strict_effective_projection_candidates': eligible,
            'strict_candidates_invalidated_by_quality_edits': invalidated,
        })

    def _base_file(self, name):
        if name not in self.pins:
            raise ValueError('Unpinned base artifact')
        return checked_path(self.base, {'path': name, **self.pins[name]})

    def _check_locator(self, chunk, index, pin):
        if chunk not in self.chunk_metadata or type(index) is not int or not 0 <= index < self.chunk_metadata[chunk]['event_count']:
            raise ValueError('Invalid detail locator')
        if self.pins[f'event_chunks/{chunk}.json.gz']['sha256'] != pin:
            raise ValueError('Decision detail pin differs from canonical contract')

    def _iter_base_summaries(self):
        for shard in self.shards:
            path = self._base_file(f'summary_shards/{shard["id"]}.json.gz')
            with gzip.open(path, 'rt', encoding='utf8') as handle:
                rows = json.load(handle)
            if len(rows) != shard['event_count']:
                raise ValueError('Summary shard count mismatch')
            yield from rows

    def _validate_summaries(self):
        expected = self.base_metadata['counts']
        seen = set()
        modified = set()
        annotated = set()
        mapped_before = mapped_after = 0
        precision_changes = Counter()
        date_precision_changes = Counter()
        for row in self._iter_base_summaries():
            eid = str(row['event_id'])
            if eid in seen:
                raise ValueError('Repeated base summary ID')
            seen.add(eid)
            effective = row
            if eid in self.decisions:
                if (row['chunk_id'], row['detail_index']) != self.locators[eid]:
                    raise ValueError('Decision summary/detail locator mismatch')
                effective = apply_decisions(row, self.decisions[eid])
                modified.add(eid)
                if row.get('location_precision') != effective.get('location_precision'):
                    precision_changes[f'{row.get("location_precision")} -> {effective.get("location_precision")}'] += 1
                if row.get('date_precision') != effective.get('date_precision'):
                    date_precision_changes[f'{row.get("date_precision")} -> {effective.get("date_precision")}'] += 1
            if eid in self.annotations:
                annotation_locator = self.annotations[eid]['updb_locator']
                if (row['chunk_id'], row['detail_index']) != (annotation_locator['chunk_id'], annotation_locator['detail_index']):
                    raise ValueError('Date annotation summary/detail locator mismatch')
                self._validate_annotation(row, self.annotations[eid])
                annotated.add(eid)
            mapped_before += int(row['has_coordinates'])
            mapped_after += int(effective['has_coordinates'])
        if len(seen) != expected['events'] or mapped_before != expected['mapped_events']:
            raise ValueError('Base summary census mismatch')
        if modified != set(self.decisions) or annotated != set(self.annotations):
            raise ValueError('Accepted decision or annotation refers to a missing event')
        return {
            'base_records': len(seen), 'effective_records': len(seen),
            'base_mapped': mapped_before, 'effective_mapped': mapped_after,
            'effective_unmapped': len(seen) - mapped_after,
            'modified_records': len(modified), 'accepted_decisions': sum(map(len, self.decisions.values())),
            'date_review_annotations': len(annotated), 'precision_transitions': dict(precision_changes),
            'date_precision_transitions': dict(date_precision_changes),
            'incident_relationship_members': len(self.incident_relationships),
            'summary_shards_validated': len(self.shards),
        }

    @staticmethod
    def _validate_annotation(row, annotation):
        if annotation.get('base_manifest_sha256') != BASE_SHA:
            raise ValueError('Date annotation base pin mismatch')
        if set(annotation.get('guards', {})) != {'source', 'sort_date_iso', 'date_precision'}:
            raise ValueError('Incomplete date annotation guards')
        for field, value in annotation['guards'].items():
            if row.get(field) != value:
                raise ValueError('Stale date review annotation')

    def _enrich(self, base_row):
        eid = str(base_row['event_id'])
        result = apply_decisions(base_row, self.decisions[eid]) if eid in self.decisions else dict(base_row)
        if eid in self.annotations:
            self._validate_annotation(base_row, self.annotations[eid])
            result['quality_date_review'] = copy.deepcopy(self.annotations[eid])
        if eid in self.incident_relationships:
            result['quality_incident_relationships'] = copy.deepcopy(self.incident_relationships[eid])
        relation = self.accounts.get(eid)
        if relation:
            key, other, role, partition, flags, eligible, _, _ = relation
            result['quality_original_account'] = {
                'account_key': key, 'other_event_id': other, 'endpoint_role': role,
                'partition': partition, 'review_flags': list(flags),
                'strict_current_view_candidate': eligible,
                'policy': 'original_account_reference_not_physical_incident_merge',
            }
        return result

    def iter_summaries(self):
        """Stream effective rows; retain all base records and representations."""
        for row in self._iter_base_summaries():
            yield self._enrich(row)

    def get_detail(self, event_id, chunk_id=None, detail_index=None):
        eid = str(event_id)
        locator = self.locators.get(eid)
        if locator is None and eid in self.accounts:
            locator = self.accounts[eid][6:8]
        if chunk_id is not None or detail_index is not None:
            explicit = (chunk_id, detail_index)
            if locator is not None and locator != explicit:
                raise ValueError('Supplied detail locator differs from pinned evidence')
            locator = explicit
        if locator is None:
            for row in self._iter_base_summaries():
                if str(row['event_id']) == eid:
                    locator = (row['chunk_id'], row['detail_index'])
                    break
        if locator is None:
            raise KeyError(eid)
        chunk, index = locator
        if chunk not in self.chunk_metadata or type(index) is not int or not 0 <= index < self.chunk_metadata[chunk]['event_count']:
            raise ValueError('Invalid detail locator')
        path = self._base_file(f'event_chunks/{chunk}.json.gz')
        if self._chunk_cache is None or self._chunk_cache[0] != chunk:
            with gzip.open(path, 'rt', encoding='utf8') as handle:
                rows = json.load(handle)
            if len(rows) != self.chunk_metadata[chunk]['event_count']:
                raise ValueError('Detail chunk count mismatch')
            self._chunk_cache = (chunk, rows)
        row = self._chunk_cache[1][index]
        if str(row['event_id']) != eid:
            raise ValueError('Detail index event ID mismatch')
        # Detail callers may edit their returned nested source evidence; never
        # let that mutate the shared, pinned chunk held in this reader's cache.
        return self._enrich(copy.deepcopy(row))

    def get_decisions(self, event_id):
        return copy.deepcopy(self.decisions.get(str(event_id), []))

    def project_selected_event_ids(self, selected_ids):
        """Optional guarded account view; never hide copies outside selection."""
        ordered = list(dict.fromkeys(str(eid) for eid in selected_ids))
        if len(ordered) > 10000:
            raise ValueError('Project selections in cohorts of at most 10,000 representations')
        selected = set(ordered)
        requested_keys = {
            self.accounts[eid][0] for eid in ordered
            if eid in self.accounts and self.accounts[eid][5] and self.accounts[eid][1] in selected
        }
        suppressed = {}
        if requested_keys:
            requested_rows = []
            by_chunk = {}
            for row in self.account_loader.iter_account_links(self.account_manifest_path, BASE_SHA):
                if row['accountKey'] not in requested_keys:
                    continue
                requested_rows.append(row)
                for role in ['primary', 'updb']:
                    item = row[role]
                    by_chunk.setdefault(item['chunk'], []).append((item['eventId'], item['index']))
            # One decode per requested chunk, even for large selected cohorts.
            # Keep only current eligibility fields, not expanded narratives.
            current = {}
            for chunk, items in by_chunk.items():
                path = self._base_file(f'event_chunks/{chunk}.json.gz')
                with gzip.open(path, 'rt', encoding='utf8') as handle:
                    details = json.load(handle)
                if len(details) != self.chunk_metadata[chunk]['event_count']:
                    raise ValueError('Detail chunk count mismatch')
                for eid, index in items:
                    detail = details[index]
                    if str(detail['event_id']) != eid:
                        raise ValueError('Projection detail locator event mismatch')
                    detail = self._enrich(detail)
                    fields = (*self.account_loader.VIEW_FIELDS, 'canonical_input_ids', 'duplicate_record_count')
                    current[eid] = {field: copy.deepcopy(detail[field]) for field in fields if field in detail}
            for row in requested_rows:
                p, u = row['primary']['eventId'], row['updb']['eventId']
                if self.account_loader.eligible_in_current_view(row, current):
                    suppressed[u] = p
        return {
            'kept_event_ids': [eid for eid in ordered if eid not in suppressed],
            'suppressed_representations': suppressed,
            'selected_representation_count': len(ordered),
            'projected_representation_count': len(ordered) - len(suppressed),
            'all_source_records_and_provenance_preserved': True,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default=str(Path(__file__).with_name('quality_view_manifest.json')))
    parser.add_argument('--event-id')
    args = parser.parse_args()
    view = QualityView(args.manifest)
    value = view.get_detail(args.event_id) if args.event_id else view.validation
    sys.stdout.reconfigure(encoding='utf8')
    print(json.dumps(value, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
