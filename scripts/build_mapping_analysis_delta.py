"""Incremental descriptive Analysis projection for reviewed mapping recovery.

Reads the current runtime manifests, verifies their pinned input artifacts, and
writes only changed gzip projections plus manifests. Existing inferential,
context, temporal and evidence artifacts remain immutable references. No full
catalog, static bundle or source corpus is copied or rebuilt.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import mmap
import struct
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LANES = ('analysis_v1', 'analysis_v2', 'analysis_duration_v1',
         'analysis_time_of_day_v1', 'analysis_witness_count_v1',
         'analysis_reporting_delay_v1', 'analysis_color_v1',
         'analysis_coordinate_evidence_v1')
ALLOWED_ORIGINS = {'reviewed_original_source_coordinate',
                   'reviewed_area_reference', 'reviewed_locality_reference'}
GEO_KEYS = ('country', 'macroregion', 'assignmentSource',
            'assignmentConfidence', 'boundaryStatus', 'coordinateEvidence')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                      sort_keys=True, allow_nan=False).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size,
            'sha256': value.hexdigest()}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_helper(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PinnedResolver:
    def __init__(self, runtime, shared, plan):
        self.runtime, self.shared, self.plan = runtime, shared, plan
        self.receipts = {}

    def read(self, declaration):
        url = declaration['gzipFile']
        rel = urlparse(url).path.lstrip('/')
        candidates = [Path(item['source']) for item in self.plan.get('uploads', [])
                      if item.get('url') == url or item.get('key') == rel]
        candidates += [self.shared / rel, self.shared / 'data' / rel,
                       self.shared / 'webapp/static_public' / rel,
                       self.runtime / rel]
        mismatch = []
        for path in dict.fromkeys(candidates):
            if not path.is_file():
                continue
            packed = path.read_bytes()
            if len(packed) != declaration['gzipBytes'] or digest(packed) != declaration['gzipSha256']:
                mismatch.append(str(path))
                continue
            raw = gzip.decompress(packed)
            if len(raw) != declaration['bytes'] or digest(raw) != declaration['sha256']:
                raise ValueError(f'Decoded input pin mismatch: {path}')
            rows = json.loads(raw)
            if not isinstance(rows, list) or len(rows) != declaration['rowCount']:
                raise ValueError(f'Input row count mismatch: {path}')
            self.receipts[url] = {**pin(path), 'decodedSha256': digest(raw),
                                  'decodedBytes': len(raw), 'rowCount': len(rows)}
            return rows
        raise FileNotFoundError(f'No hash-matching local artifact: {url}; mismatches={mismatch}')


class Output:
    def __init__(self, root, origin, prefix, limit):
        self.root, self.origin, self.prefix, self.limit = root, origin.rstrip('/'), prefix.strip('/'), limit
        self.bytes = 0
        self.files = []

    def write(self, relative, raw):
        if self.bytes + len(raw) > self.limit:
            raise ValueError('Analysis delta output budget exceeded')
        path = self.root / relative
        if path.exists():
            raise FileExistsError(f'Refusing to overwrite output: {path}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        self.bytes += len(raw)
        self.files.append({**pin(path), 'relativePath': relative.replace('\\', '/')})
        return f'{self.origin}/{self.prefix}/{relative}'

    def compressed(self, relative, raw):
        stream = io.BytesIO()
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0, compresslevel=9) as handle:
            handle.write(raw)
        packed = stream.getvalue()
        url = self.write(relative + '.gz', packed)
        return {'bytes': len(raw), 'sha256': digest(raw),
                'gzipBytes': len(packed), 'gzipSha256': digest(packed),
                'file': url[:-3], 'gzipFile': url}


def validate_decisions(decisions):
    seen = set()
    for row in decisions:
        event_id = row['event_id']
        if event_id in seen or row.get('accepted') is not True:
            raise ValueError('Duplicate or unaccepted mapping decision')
        seen.add(event_id)
        fields, old = row['set_fields'], row['guards']
        if fields['coordinate_source'] not in ALLOWED_ORIGINS or not fields['has_coordinates']:
            raise ValueError(f'Unsupported mapping origin: {event_id}')
        if fields['location_precision'] == 'exact_coords' or old.get('coordinate_source') == 'raw_latlong':
            raise ValueError(f'Incremental delta cannot alter precise coordinate eligibility: {event_id}')
        if not (-90 <= fields['lat'] <= 90 and -180 <= fields['lon'] <= 180):
            raise ValueError(f'Invalid mapped coordinates: {event_id}')
    return {row['event_id']: row for row in decisions}


def encode_assignment(assignment, codebooks):
    values = list(assignment) + ['generalized_coordinates']
    unsupported = values[0] if values[0] not in codebooks['country'] else None
    if unsupported:
        # Keep the polygon result's status but withhold unsupported taxonomy.
        values[0], values[1], values[3] = 'unknown', 'unknown', 'none'
    return [codebooks[key].index(value) for key, value in zip(GEO_KEYS, values)], unsupported


def patch_macroregions(rows, schema, codebook, event_regions):
    event_column, region_column = schema.index('eventId'), schema.index('macroregionCode')
    changes = 0
    for row in rows:
        region = event_regions.get(row[event_column])
        if region is None:
            continue
        if region not in codebook:
            raise ValueError(f'Unsupported descriptive macroregion: {region}')
        value = codebook.index(region)
        if row[region_column] != value:
            row[region_column] = value
            changes += 1
    return changes


def updated_counts(original, decisions, field):
    counts = Counter(original)
    for decision in decisions.values():
        counts[decision['guards'].get(field) or 'unknown'] -= 1
        counts[decision['set_fields'].get(field) or 'unknown'] += 1
    if any(n < 0 for n in counts.values()):
        raise ValueError(f'Invalid delta counts for {field}')
    return dict(sorted((k, v) for k, v in counts.items() if v))


def refresh_gate(gate, input_n, passed_n):
    gate.update(inputN=input_n, passedN=passed_n,
                failedN=input_n - passed_n - gate.get('unknownN', 0))
    gate.pop('evidenceHash', None)
    gate['evidenceHash'] = digest(canonical(gate))


def update_live_denominators(v2, old_mapped, newly_mapped, new_formations, canonical_pin):
    """Adjust only first-stage generalized exclusions; keep strict rows frozen."""
    delta = {'oldMapped': old_mapped, 'newMapped': newly_mapped,
             'currentMapped': old_mapped + newly_mapped, 'newGeneralizedFormationRows': new_formations,
             'qualifiedPointCountsUnchanged': True,
             'policy': 'guarded_incremental_generalized_exclusion_counts_no_strict_data_rebuild'}
    prior = v2.get('liveReadinessDenominatorDelta')
    if prior:
        if prior != delta:
            raise ValueError('Different readiness denominator delta already applied')
        return delta
    sources = v2['sources']
    for key in ('ufoPointNeighbors', 'ufoSpatialPoints', 'ufoConfigurationPoints'):
        source = sources[key]
        source['inputSnapshotRole'] = 'inherited_original_artifact_build_inputs_unchanged'
        source['currentCatalogDenominatorInput'] = canonical_pin
        source['readiness']['catalogDenominatorRole'] = 'current_mapped_catalog_with_new_generalized_references_excluded'
    neighbors = sources['ufoPointNeighbors']
    configuration = sources['ufoConfigurationPoints']
    if neighbors['counts']['packedRows'] != old_mapped or configuration['counts']['packedRows'] != old_mapped:
        raise ValueError('Inherited readiness denominator differs from mapped base')
    neighbors['counts']['packedRows'] += newly_mapped
    neighbors['exclusions']['not_source_provided_coordinate'] += newly_mapped
    configuration['counts']['packedRows'] += newly_mapped
    configuration['counts']['formationRows'] += new_formations
    configuration['exclusions']['not_formation_configuration'] += newly_mapped - new_formations
    configuration['exclusions']['not_source_provided_coordinate'] += new_formations
    for key in ('ufoPointNeighbors', 'ufoSpatialPoints'):
        for gate in sources[key]['readiness']['gates']:
            if gate['gateId'] == 'ufo_neighbor_source_coordinates':
                if gate['inputN'] != old_mapped:
                    raise ValueError('Inherited source-coordinate gate denominator mismatch')
                refresh_gate(gate, old_mapped + newly_mapped, gate['passedN'])
    for gate in configuration['readiness']['gates']:
        if gate['gateId'] == 'configuration_classification':
            refresh_gate(gate, old_mapped + newly_mapped, gate['passedN'] + new_formations)
        elif gate['gateId'] == 'configuration_source_coordinates':
            refresh_gate(gate, gate['inputN'] + new_formations, gate['passedN'])
    v2['liveReadinessDenominatorDelta'] = delta
    return delta


def build(args):
    output = Output(args.output, args.origin, args.prefix, int(args.max_output_mib * 1048576))
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError('Use an empty dedicated delta output directory')
    plan_path = args.runtime_root / 'releases/workspace-analysis-20261008/delivery_plan.json'
    plan = load(plan_path)
    resolver = PinnedResolver(args.runtime_root, args.shared_root, plan)
    manifests = {lane: load(args.runtime_root / 'data' / lane / 'manifest.json') for lane in LANES}
    bases = copy.deepcopy(manifests)
    decision_pin = pin(args.decisions)
    if args.decisions_sha256 and decision_pin['sha256'] != args.decisions_sha256:
        raise ValueError('Merged decision artifact pin mismatch')
    with gzip.open(args.decisions, 'rt', encoding='utf-8') as stream:
        decisions = validate_decisions([json.loads(line) for line in stream if line.strip()])
    map_manifest_path = args.map_root / 'canonical_web_manifest.json'
    map_manifest = load(map_manifest_path)
    map_pin = pin(map_manifest_path)
    map_url = f'{args.origin.rstrip("/")}/{args.map_prefix.strip("/")}/canonical_web_manifest.json'
    canonical_pin = {**map_pin, 'path': map_url,
                     'hashRole': 'effective_guarded_mapping_recovery_map_and_summary_manifest'}
    helper_root = args.shared_root / 'scripts'
    sys.path.insert(0, str(helper_root))
    helper = load_helper(helper_root / 'build_analysis_v2_artifacts.py', '_mapping_geography_helper')
    binary_helper = load_helper(helper_root / 'build_analysis_geography_binary_v1.py', '_mapping_binary_helper')
    meta, meta_path, points_path = helper.packed_metadata(args.map_root)
    if meta.get('input', {}).get('row_order') != 'input_order':
        raise ValueError('Packed point input order is required')
    world_path = args.shared_root / 'webapp/static_public/data/world_countries.geojson'
    parts, buckets, taxonomy, world_pin = helper.world_country_index(world_path)
    v2 = manifests['analysis_v2']
    geography = v2['artifacts']['ufoGeography']
    if world_pin['sha256'] != v2['sources']['ufoGeography']['worldCountries']['sha256']:
        raise ValueError('Current country polygon input differs from active Analysis')
    old_rows = resolver.read(geography)
    old_by_id = {row[1]: row for row in old_rows}
    if len(old_by_id) != len(old_rows):
        raise ValueError('Duplicate original geography IDs')
    codes = v2['codes']['ufoGeography']
    fields = {field['name']: index for index, field in enumerate(meta['fields'])}
    row_struct = struct.Struct(meta['struct_format'])
    new_rows, seen, coordinate_keys = [], set(), set()
    accepted_regions, unsupported_countries, assignment_cache = {}, [], {}
    new_count = 0
    new_formations = 0
    with points_path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as packed:
        for index, row in enumerate(row_struct.iter_unpack(packed)):
            event_id = int(row[fields['event_id']])
            if event_id in seen:
                raise ValueError('Duplicate new mapped event ID')
            seen.add(event_id)
            lat, lon = row[fields['lat']], row[fields['lon']]
            coordinate_keys.add((round(lat, 7), round(helper.normalize_longitude(lon), 7)))
            if event_id not in decisions:
                if event_id not in old_by_id:
                    raise ValueError(f'Unreviewed new mapped row: {event_id}')
                new_rows.append([index, *old_by_id[event_id][1:]])
                continue
            decision = decisions[event_id]
            expected = decision['set_fields']
            origin = helper.lookup(meta, 'coordinate_sources', row[fields['coordinate_source_id']])
            if (lat, lon, origin) != (expected['lat'], expected['lon'], expected['coordinate_source']):
                raise ValueError(f'Applied map point does not match reviewed decision: {event_id}')
            key = (lat, lon)
            if key not in assignment_cache:
                assignment_cache[key] = helper.assign_world_country(lat, lon, parts, buckets, taxonomy)
            coded, unsupported = encode_assignment(assignment_cache[key], codes)
            if unsupported:
                unsupported_countries.append({'eventId': event_id, 'country': unsupported})
            new_rows.append([index, event_id, *coded])
            accepted_regions[event_id] = codes['macroregion'][coded[1]]
            new_count += event_id not in old_by_id
            if event_id not in old_by_id and helper.lookup(meta, 'craft_types', row[fields['craft_type_id']]) == 'formation':
                new_formations += 1
    if not set(old_by_id) <= seen or not set(decisions) <= seen:
        raise ValueError('New geography omitted an old mapped or reviewed accepted ID')
    if len(new_rows) != meta['row_count'] or len(new_rows) != map_manifest['counts']['mapped_events']:
        raise ValueError('New geography does not match canonical mapped count')
    expected_new = sum(not row['guards']['has_coordinates'] for row in decisions.values())
    if new_count != expected_new or len(new_rows) != len(old_rows) + expected_new:
        raise ValueError('New mapped delta disagrees with reviewed guards')
    geography.update(output.compressed('analysis_v2/ufo_geography_v1.json', canonical(new_rows) + b'\n'))
    geography['rowCount'] = len(new_rows)
    geography['rowOrdering'] = helper.row_ordering_declaration(new_rows, geography['rowSchema'],
        ['pointRowIndex', 'eventId'], policy_id='packed_point_row_alignment_order_v1')
    encoded = binary_helper.encode_rows(new_rows)
    view = memoryview(encoded)
    if any(binary_helper.decoded_row(view, index, len(new_rows)) != row for index, row in enumerate(new_rows)):
        raise ValueError('Geography binary/JSON parity failed')
    geography['binary'].update(output.compressed('analysis_v2/ufo_geography_v1.bin', encoded))
    geography['binary'].update(decodedJsonSha256=geography['sha256'],
        decodedCanonicalJsonSha256=digest(canonical(new_rows)))
    v2['artifactReleases']['ufoGeography'] = f'{args.release_id}.ufo_geography_v1'
    v2['rowOrderingHashes']['ufoGeography'] = geography['rowOrdering']['sha256']
    country_counts = Counter(codes['country'][row[2]] for row in new_rows)
    region_counts = Counter(codes['macroregion'][row[3]] for row in new_rows)
    boundary_counts = Counter(codes['boundaryStatus'][row[6]] for row in new_rows)
    assigned = len(new_rows) - country_counts['unknown']
    geo_source = v2['sources']['ufoGeography']
    geo_source['pointsMetadata'] = {**pin(meta_path), 'label': 'data/canonical_web/points_meta.json'}
    geo_source['pointsBinary'] = {**pin(points_path), 'label': 'data/canonical_web/points.bin'}
    geo_source['counts'].update(rows=len(new_rows), uniqueCoordinateMarkers=len(coordinate_keys),
        countryAssigned=assigned, countryUnknown=country_counts['unknown'],
        byBoundaryStatus=dict(sorted(boundary_counts.items())), byMacroregion=dict(sorted(region_counts.items())))
    for gate in geo_source['readiness']['gates']:
        if gate['gateId'] == 'geography_row_alignment':
            refresh_gate(gate, len(new_rows), len(new_rows))
        elif gate['gateId'] == 'country_polygon_assignment':
            refresh_gate(gate, len(new_rows), assigned)
        elif gate['gateId'] == 'macroregion_assignment':
            refresh_gate(gate, assigned, assigned)
    v2['counts'].update(ufoGeographyRows=len(new_rows), ufoGeographyCountryAssigned=assigned)
    denominator_delta = update_live_denominators(v2, len(old_rows), new_count, new_formations, canonical_pin)
    geo_input = {'path': geography['gzipFile'], 'bytes': geography['gzipBytes'],
        'sha256': geography['gzipSha256'], 'decodedBytes': geography['bytes'],
        'decodedSha256': geography['sha256'], 'rowCount': len(new_rows),
        'releaseId': v2['artifactReleases']['ufoGeography']}
    projection_changes = {}
    for lane, manifest in manifests.items():
        if lane in {'analysis_v1', 'analysis_v2', 'analysis_coordinate_evidence_v1'}:
            continue
        for key, artifact in manifest['artifacts'].items():
            schema = artifact.get('rowSchema', [])
            if 'macroregionCode' not in schema or 'eventId' not in schema:
                continue
            rows = resolver.read(artifact)
            changes = patch_macroregions(rows, schema, manifest['codes']['macroregion'], accepted_regions)
            projection_changes[f'{lane}/{key}'] = changes
            if changes:
                filename = Path(urlparse(artifact['gzipFile']).path).name.removesuffix('.gz')
                artifact.update(output.compressed(f'{lane}/{filename}', canonical(rows) + b'\n'))
            if lane == 'analysis_color_v1':
                position = schema.index('macroregionCode')
                manifest['counts']['byMacroregionRaw'] = dict(sorted(Counter(
                    manifest['codes']['macroregion'][row[position]] for row in rows).items()))
    coordinate = manifests['analysis_coordinate_evidence_v1']
    # This is a source-coordinate typed projection, not a list of all map markers.
    coordinate_rows = resolver.read(coordinate['artifacts']['coordinateEvidenceProjection'])
    if any(row[1] in decisions for row in coordinate_rows):
        raise ValueError('A generalized mapping correction overlaps the strict coordinate projection')
    for field, count_key, map_key in [('location_precision', 'byLocationPrecision', 'location_precision_counts'),
                                     ('coordinate_source', 'byCoordinateOrigin', 'coordinate_source_counts')]:
        expected = updated_counts(coordinate['counts'][count_key], decisions, field)
        actual = dict(sorted((k, v) for k, v in map_manifest['counts'][map_key].items() if v))
        if expected != actual:
            raise ValueError(f'Canonical map counts differ from guarded Analysis delta: {field}')
        coordinate['counts'][count_key] = actual
    source = manifests['analysis_v1']['sources']['ufoCatalog']
    source.update(canonicalWebManifest=map_url, canonicalWebManifestBytes=map_pin['bytes'],
        canonicalWebManifestSha256=map_pin['sha256'], sha256=map_pin['sha256'],
        mappedRowCount=len(new_rows), releaseId=args.release_id,
        effectiveCatalogRole='guarded_mapping_recovery_over_current_served_catalog',
        hashRole=canonical_pin['hashRole'])
    generated = datetime.now(timezone.utc).isoformat()
    metadata = {'decisionArtifact': decision_pin, 'acceptedDecisionCount': len(decisions),
        'newlyMappedCount': new_count, 'correctedMappedCount': len(decisions) - new_count,
        'coordinatePolicy': 'all_recovery_references_generalized_no_point_inference_promotion',
        'inheritedArtifacts': 'current_active_pins_preserved_including_temporal_and_context_repairs'}
    unchanged = []
    for lane, manifest in manifests.items():
        manifest['generatedAt'], manifest['releaseId'] = generated, f'{args.release_id}.{lane}'
        manifest['inputs']['canonicalManifest'] = canonical_pin
        if 'geography' in manifest['inputs']:
            manifest['inputs']['geography'] = geo_input
        manifest['mappingRecovery'] = {**metadata, 'baseManifest': pin(args.runtime_root / 'data' / lane / 'manifest.json')}
        manifest['delivery'] = {'gzipOnly': True, 'inheritedImmutableArtifacts': True,
            'immutablePrefix': f'{args.prefix}/{lane}', 'pagesFiles': ['manifest.json']}
        manifest['payloads'] = {item['relativePath'].split('/', 1)[1]: {
            'bytes': item['bytes'], 'sha256': item['sha256']}
            for item in output.files if item['relativePath'].startswith(lane + '/')}
        if manifest['codes'] != bases[lane]['codes']:
            raise ValueError('Codebook preservation invariant failed')
        for key, artifact in manifest['artifacts'].items():
            if artifact == bases[lane]['artifacts'][key]:
                unchanged.append({'lane': lane, 'artifact': key, 'sha256': artifact['sha256'],
                                  'gzipSha256': artifact['gzipSha256'], 'gzipFile': artifact['gzipFile']})
        if lane == 'analysis_v2':
            manifest['contractHashes']['artifactDeclarationsSha256'] = digest(canonical(manifest['artifacts']))
            if manifest['contractHashes']['dictionaryCodebooksSha256'] != digest(canonical(manifest['codes'])):
                raise ValueError('Inherited dictionary contract hash mismatch')
            if manifest['contractHashes']['rootPolicySha256'] != digest(canonical(manifest['policy'])):
                raise ValueError('Inherited policy contract hash mismatch')
        output.write(f'{lane}/manifest.json', canonical(manifest) + b'\n')
    # No inferred neighborhood, context or source-evidence artifact may change.
    allowed = {'ufoGeography'}
    for key in v2['artifacts']:
        if key not in allowed and v2['artifacts'][key] != bases['analysis_v2']['artifacts'][key]:
            raise ValueError(f'Unexpected inferential/context artifact mutation: {key}')
    receipt = {'schema': 'mapping_analysis_incremental_receipt_v1', 'generatedAt': generated,
        'releaseId': args.release_id, 'inputs': {'deliveryPlan': pin(plan_path),
            'builder': pin(Path(__file__)),
            'canonicalMapManifest': map_pin, 'decisions': decision_pin,
            'helpers': [pin(helper_root / name) for name in ('build_analysis_v2_artifacts.py',
                        'build_analysis_geography_binary_v1.py', 'context_evidence_contract.py')],
            'countryPolygons': pin(world_path), 'resolvedArtifacts': resolver.receipts},
        'counts': {'oldMapped': len(old_rows), 'mapped': len(new_rows), 'newMapped': new_count,
            'acceptedCorrections': len(decisions), 'countryAssigned': assigned,
            'countryUnknown': country_counts['unknown'], 'binaryParityRows': len(new_rows)},
        'projectionChangedRows': projection_changes, 'unsupportedCountryCodebookRows': unsupported_countries,
        'liveReadinessDenominatorDelta': denominator_delta,
        'unchangedArtifactPins': unchanged, 'files': output.files.copy(),
        'storage': {'canonicalCandidate': str(args.output), 'retainedRollback': 'current active immutable Analysis artifact pins',
            'newBytesBeforeReceipt': output.bytes, 'maximumBytes': output.limit, 'newFilesOver100MiB': [],
            'retention': 'retain candidate and receipt through root integration; no source or rollback copies made'},
        'validation': {'generalizedOnly': True, 'currentCodebooksPreserved': True,
            'oldMappedIdsPreserved': True, 'acceptedMapCoordinatesMatch': True,
            'unchangedGeographyClassPreserved': True, 'inferentialAndContextPinsUnchanged': True,
            'coordinateEvidenceRowsUnchanged': True, 'canonicalCountsMatchDecisionDelta': True}}
    output.write('analysis_delta_receipt.json', canonical(receipt) + b'\n')
    print(json.dumps({'output': str(args.output), 'bytes': output.bytes,
                      'counts': receipt['counts'], 'projectionChangedRows': projection_changes}))
    return receipt


def refresh_map_pin(args):
    """Reseal metadata after a root-only map-manifest URL repair.

    No projection bytes may change; all existing delta files and the pinned
    points inputs are verified before the manifest metadata is rewritten.
    """
    receipt_path = args.output / 'analysis_delta_receipt.json'
    receipt = load(receipt_path)
    for item in receipt['files']:
        actual = pin(args.output / item['relativePath'])
        if (actual['bytes'], actual['sha256']) != (item['bytes'], item['sha256']):
            raise ValueError(f'Existing delta file changed: {item["relativePath"]}')
    map_path = args.map_root / 'canonical_web_manifest.json'
    current = pin(map_path)
    if not args.map_sha256 or current['sha256'] != args.map_sha256:
        raise ValueError('Explicit final map manifest hash is required for metadata reseal')
    map_manifest = load(map_path)
    if map_manifest['counts']['mapped_events'] != receipt['counts']['mapped']:
        raise ValueError('Reseal cannot change mapped count')
    geography_manifest = load(args.output / 'analysis_v2/manifest.json')
    for filename, key in [('points.bin', 'pointsBinary'), ('points_meta.json', 'pointsMetadata')]:
        before = geography_manifest['sources']['ufoGeography'][key]
        actual = pin(args.map_root / filename)
        if (actual['bytes'], actual['sha256']) != (before['bytes'], before['sha256']):
            raise ValueError('Reseal cannot change geography input data')
    old = receipt['inputs']['canonicalMapManifest']
    with gzip.open(args.decisions, 'rt', encoding='utf-8') as stream:
        decisions = validate_decisions([json.loads(line) for line in stream if line.strip()])
    if pin(args.decisions)['sha256'] != receipt['inputs']['decisions']['sha256']:
        raise ValueError('Decision artifact changed before metadata reseal')
    new_ids = {event_id for event_id, row in decisions.items() if not row['guards']['has_coordinates']}
    meta = load(args.map_root / 'points_meta.json')
    fields = {field['name']: index for index, field in enumerate(meta['fields'])}
    row_struct = struct.Struct(meta['struct_format'])
    new_formations = 0
    with (args.map_root / 'points.bin').open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        for row in row_struct.iter_unpack(mapped):
            if row[fields['event_id']] in new_ids and meta['lookup_tables']['craft_types'][row[fields['craft_type_id']]] == 'formation':
                new_formations += 1
    denominator_delta = None
    for lane in LANES:
        path = args.output / lane / 'manifest.json'
        manifest = load(path)
        if manifest['inputs']['canonicalManifest']['sha256'] != old['sha256']:
            raise ValueError('Analysis manifests do not share the prior canonical map pin')
        manifest['inputs']['canonicalManifest'].update(bytes=current['bytes'], sha256=current['sha256'])
        if lane == 'analysis_v1':
            manifest['sources']['ufoCatalog'].update(canonicalWebManifestBytes=current['bytes'],
                canonicalWebManifestSha256=current['sha256'], sha256=current['sha256'])
        if lane == 'analysis_v2':
            denominator_delta = update_live_denominators(manifest, receipt['counts']['oldMapped'],
                len(new_ids), new_formations, manifest['inputs']['canonicalManifest'])
        path.write_bytes(canonical(manifest) + b'\n')
    receipt['inputs']['canonicalMapManifest'] = current
    receipt['inputs']['builder'] = pin(Path(__file__))
    if old['sha256'] != current['sha256']:
        receipt['mapManifestMetadataReseal'] = {'previousPin': old, 'finalPin': current,
            'projectionBytesUnchanged': True, 'reason': 'current_map_manifest_artifact_URL_repair'}
    receipt['liveReadinessDenominatorDelta'] = denominator_delta
    for item in receipt['files']:
        item.update(pin(args.output / item['relativePath']))
    receipt['storage']['newBytesBeforeReceipt'] = sum(item['bytes'] for item in receipt['files'])
    receipt_path.write_bytes(canonical(receipt) + b'\n')
    print(json.dumps({'receipt': pin(receipt_path), 'canonicalMap': current,
                      'projectionBytesUnchanged': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    parser.add_argument('--shared-root', type=Path, default=Path('C:/Users/jarod/Desktop/UFO Timeline map tool'))
    parser.add_argument('--map-root', type=Path, required=True)
    parser.add_argument('--decisions', type=Path, required=True)
    parser.add_argument('--decisions-sha256')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--release-id', default='mapping-recovery-20261103')
    parser.add_argument('--prefix', default='releases/mapping-recovery-20261103/analysis_delta')
    parser.add_argument('--map-prefix', default='releases/mapping-recovery-20261103/map_delta')
    parser.add_argument('--origin', default='https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev')
    parser.add_argument('--max-output-mib', type=float, default=65)
    parser.add_argument('--refresh-map-pin', action='store_true')
    parser.add_argument('--map-sha256')
    args = parser.parse_args()
    refresh_map_pin(args) if args.refresh_map_pin else build(args)


if __name__ == '__main__':
    main()
