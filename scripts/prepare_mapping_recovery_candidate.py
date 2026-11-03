"""Prepare a sparse reviewable release plan and serve it without a staging-tree copy.

Production URLs remain in the release plan. The optional local preview rewrites
only this candidate's unpublished URLs in small manifests, recalculating the v2
declaration hash. It never changes an existing source, release or user preview.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlparse

from audit_mapping_recovery import digest, read_json

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev'
PREFIX = 'releases/mapping-recovery-20261103'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def pin(path):
    return {'source': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def prepare(root):
    base_path = ROOT / 'releases/workspace-analysis-20261008/delivery_plan.json'
    base = read_json(base_path)
    map_root, analysis_root = root / 'map-delta', root / 'analysis-delta'
    receipt = read_json(map_root / 'map_release_receipt.json')
    analysis_receipt = read_json(analysis_root / 'analysis_delta_receipt.json')
    counts = receipt['counts']
    if analysis_receipt['inputs']['canonicalMapManifest']['sha256'] != digest(map_root / 'canonical_web_manifest.json'):
        raise ValueError('Analysis is pinned to another map candidate')
    if analysis_receipt['counts']['mapped'] != counts['mapped_events']:
        raise ValueError('Map and Analysis mapped counts disagree')
    candidate_root = root / 'candidate'
    candidate_root.mkdir(exist_ok=True)
    config = read_json(ROOT / 'data/app_config.json')
    map_url = ORIGIN + '/' + PREFIX + '/map_delta/'
    config.update(mappedCount=counts['mapped_events'], unresolvedCount=counts['unmapped_events'],
                  normalizedCount=counts['events'], precisionBreakdown=counts['location_precision_counts'],
                  staticAssetVersion='mapping-recovery-20261103')
    config['packedPoints'].update(binaryUrl=map_url + 'points.bin', metadataUrl=map_url + 'points_meta.json', rowCount=counts['mapped_events'])
    config['canonicalWebArtifacts'].update(manifestUrl=map_url + 'canonical_web_manifest.json',
        summaryManifestUrl=map_url + 'summary_manifest.json', summaryShardsBaseUrl=map_url + 'summary_shards/',
        chunkManifestUrl=map_url + 'event_chunk_manifest.json')
    config['mappingRecoveryDetailOverlay'] = {**receipt['detailOverlay'], 'enabled': True,
        'gzipUrl': './data/mapping_recovery_detail/patches.json.gz'}
    config['dataQualityRelease'].update(effectiveMappedCount=counts['mapped_events'], effectiveUnmappedCount=counts['unmapped_events'])
    config['mappingRecoveryRelease'] = {'id': 'mapping-recovery-20261103',
        'acceptedDecisionsSha256': receipt['inputs']['acceptedDecisions']['sha256'],
        'changedRecords': receipt['changedRecords'], 'newlyMappedRecords': receipt['newlyMappedRecords'],
        'referencePolicy': 'Approximate areas and locality markers remain generalized, not measured sighting positions.'}
    config_path = candidate_root / 'app_config.json'
    config_path.write_bytes(canonical(config) + b'\n')
    # Existing shell and data assets remain shared. Never copy the full bundle.
    pages = {r['path']: {**r, **pin(Path(r['source']))} for r in base['pages']}
    pages['data/app_config.json'] = {'path': 'data/app_config.json', **pin(config_path)}
    for filename in ('canonical_web_manifest.json', 'summary_manifest.json', 'event_chunk_manifest.json',
                     'points_meta.json', 'trace_event_index_meta.json', 'trace_segments_meta.json', 'trace_aggregate_bins_meta.json'):
        source = map_root / filename
        if filename == 'canonical_web_manifest.json':
            mirror = copy.deepcopy(read_json(source))
            for key, value in mirror['artifacts'].items():
                if not str(value).startswith('https://'):
                    mirror['artifacts'][key] = map_url + value
            source = candidate_root / filename
            source.write_bytes(canonical(mirror) + b'\n')
        path = 'data/canonical_web/' + filename
        pages[path] = {'path': path, **pin(source)}
    uploads = []
    for item in receipt['files']:
        source = map_root / item['path']
        actual = pin(source)
        if (actual['bytes'], actual['sha256']) != (item['bytes'], item['sha256']):
            raise ValueError('Map candidate receipt mismatch')
        if item['delivery'] == 'pages':
            path = item['publicPath']
            pages[path] = {'path': path, **actual}
        elif item['delivery'] == 'r2':
            key = item['immutableKey']
            uploads.append({'key': key, 'url': ORIGIN + '/' + key, **actual})
    for item in analysis_receipt['files']:
        relative = item['relativePath']
        source = analysis_root / relative
        actual = pin(source)
        if (actual['bytes'], actual['sha256']) != (item['bytes'], item['sha256']):
            raise ValueError('Analysis candidate receipt mismatch')
        if source.name == 'manifest.json':
            path = 'data/' + relative
            pages[path] = {'path': path, **actual}
        elif source.name.endswith('.gz'):
            key = PREFIX + '/analysis_delta/' + relative
            uploads.append({'key': key, 'url': ORIGIN + '/' + key, **actual})
    tree = hashlib.sha256(canonical([{k:r[k] for k in ('path','bytes','sha256')} for _,r in sorted(pages.items())])).hexdigest()
    plan = {'schema': 'ufo-mapping-recovery-delivery-plan-v1', 'release_id': 'mapping-recovery-20261103',
        'source_root': str(ROOT), 'base_deployment': read_json(ROOT / 'releases/workspace-analysis-20261008/current_production.json'),
        'counts': counts, 'pages': [r for _,r in sorted(pages.items())], 'pages_tree_sha256': tree,
        'pages_total_bytes': sum(r['bytes'] for r in pages.values()), 'uploads': uploads,
        'upload_total_bytes': sum(r['bytes'] for r in uploads),
        'inherited_runtime_objects': base.get('inherited_runtime_objects', []) + base['uploads'],
        'input_pins': {'basePlan': pin(base_path), 'mapReceipt': pin(map_root / 'map_release_receipt.json'),
                       'analysisReceipt': pin(analysis_root / 'analysis_delta_receipt.json')},
        'productionPublished': False,
        'retention': {'purpose': 'Current reviewed mapping candidate; files reference shared inputs and sparse generated deltas.',
                      'rebuild': 'Run the mapping map/analysis builders, then this script.',
                      'canonical': str(root), 'rollback': 'Existing production 90fa1b95; retained rollback 0ac7c2bc remains unchanged.',
                      'superseded': ['location-source-review is superseded by location-source-review-v2; retain as review history until cleanup is authorized.']}}
    plan_path = candidate_root / 'delivery_plan.json'
    plan_path.write_bytes(canonical(plan) + b'\n')
    print(json.dumps({'plan': str(plan_path), 'mapped': counts['mapped_events'], 'unmapped': counts['unmapped_events'],
                      'pagesBytesReferenced': plan['pages_total_bytes'], 'newUploadBytes': plan['upload_total_bytes'],
                      'stagingTreeCopied': False}), flush=True)
    return plan_path


def serve(plan_path, port):
    plan = read_json(plan_path)
    routes = {'/' + r['path']: Path(r['source']) for r in plan['pages']}
    routes.update({'/' + r['key']: Path(r['source']) for r in plan['uploads']})
    local_prefix = f'http://127.0.0.1:{port}/' + PREFIX
    public_prefix = ORIGIN + '/' + PREFIX
    def rebase(value):
        if isinstance(value, str):
            return value.replace(public_prefix, local_prefix)
        if isinstance(value, list):
            return [rebase(v) for v in value]
        if isinstance(value, dict):
            return {k:rebase(v) for k,v in value.items()}
        return value
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            request = unquote(urlparse(self.path).path)
            if request in ('/', '/index.html'):
                request = '/index.html'
            source = routes.get(request)
            # Raw binaries are intentionally not uploads; local preview may read
            # these generated siblings in place while gzip remains deployable.
            if source is None and request.startswith('/' + PREFIX + '/map_delta/'):
                relative = request.split('/map_delta/', 1)[1]
                base = plan_path.parent.parent / 'map-delta'
                candidate = (base / relative).resolve()
                if candidate.is_relative_to(base.resolve()) and candidate.is_file():
                    source = candidate
            if source is None:
                self.send_error(404)
                return
            payload = source.read_bytes()
            if request == '/data/app_config.json' or (request.startswith('/data/analysis_') and request.endswith('/manifest.json')):
                value = rebase(json.loads(payload))
                if 'contractHashes' in value and 'artifacts' in value:
                    value['contractHashes']['artifactDeclarationsSha256'] = hashlib.sha256(canonical(value['artifacts'])).hexdigest()
                payload = canonical(value) + b'\n'
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(source.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            for offset in range(0, len(payload), 65536):
                self.wfile.write(payload[offset:offset + 65536])
        def log_message(self, *args):
            pass
    print(f'Mapping candidate preview http://127.0.0.1:{port}/index.html', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8137)
    args = parser.parse_args()
    plan_path = prepare(args.root)
    if args.serve:
        serve(plan_path, args.port)
