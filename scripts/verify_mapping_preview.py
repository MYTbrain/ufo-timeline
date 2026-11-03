"""Check the real local HTTP delivery contract without claiming a visual UI test."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import ProxyHandler, build_opener


def verify(root, origin):
    plan = json.loads((root / 'candidate/delivery_plan.json').read_bytes())
    checked = []
    retries = []
    client = build_opener(ProxyHandler({}))
    def fetch(url):
        for attempt in range(2):
            try:
                with client.open(url, timeout=30) as response:
                    data = b''.join(iter(lambda: response.read(1024 * 1024), b''))
                    assert response.status == 200
                break
            except ConnectionResetError:
                retries.append(url)
                if attempt:
                    raise
        checked.append({'url': url, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        return data
    def document(url):
        return json.loads(fetch(url))
    config = document(origin + '/data/app_config.json')
    assert config['mappedCount'] == 595356 and config['unresolvedCount'] == 107537
    manifest_url = config['canonicalWebArtifacts']['manifestUrl']
    assert manifest_url.startswith(origin + '/releases/mapping-recovery-20261103/')
    manifest = document(manifest_url)
    uploads = {row['key']: row for row in plan['uploads']}
    def immutable(path, raw_bytes=None):
        key = path.lstrip('/')
        pin = uploads[key]
        data = fetch(origin + '/' + key)
        assert len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256']
        if raw_bytes is not None:
            assert len(gzip.decompress(data)) == raw_bytes
        return data
    for key, count_key in [('points', 'mapped_events'), ('trace_event_index', 'trace_events'),
                           ('trace_segments', 'trace_segments'), ('trace_aggregate_bins', 'trace_aggregate_bins')]:
        metadata = document(urljoin(manifest_url, manifest['artifacts'][key + '_metadata']))
        assert metadata['row_count'] == manifest['counts'][count_key]
        binary_url = urljoin(manifest_url, manifest['artifacts'][key]) + '.gz'
        immutable(urlparse(binary_url).path, metadata['row_count'] * metadata['bytes_per_row'])
    overlay = config['mappingRecoveryDetailOverlay']
    data = fetch(urljoin(origin + '/', overlay['gzipUrl']))
    assert hashlib.sha256(data).hexdigest() == overlay['gzipSha256']
    assert len(json.loads(gzip.decompress(data))['patches']) == 12480
    analysis = document(origin + '/data/analysis_v2/manifest.json')
    assert analysis['counts']['ufoGeographyRows'] == config['mappedCount']
    geography = analysis['artifacts']['ufoGeography']
    for entry in (geography, geography['binary']):
        data = immutable(urlparse(entry['gzipFile']).path)
        assert hashlib.sha256(data).hexdigest() == entry['gzipSha256']
    for lane in ['analysis_duration_v1', 'analysis_time_of_day_v1', 'analysis_witness_count_v1',
                 'analysis_reporting_delay_v1', 'analysis_color_v1', 'analysis_coordinate_evidence_v1']:
        auxiliary = document(origin + '/data/' + lane + '/manifest.json')
        assert auxiliary['inputs']['canonicalManifest']['sha256'] == hashlib.sha256(fetch(manifest_url)).hexdigest()
    profile = document(urljoin(origin + '/', config['startupProfile']['manifestUrl']))
    assert profile['mappingRecoverySourcePins']['acceptedDecisions'] == overlay['qualityManifestSha256']
    index = fetch(origin + '/index.html').decode()
    assert '2026-11-03-mapping-recovery-v1' in index
    assert max(row['bytes'] for row in plan['pages']) < 25 * 1024**2
    result = {'status': 'passed', 'preview': origin + '/index.html', 'requests': checked, 'transportRetries': retries,
              'gzipProductionPathsChecked': True, 'mapAnalysisAndStartupCountsAligned': True,
              'browserVisualInspection': 'unavailable: browser and native computer-use kernels failed to write kernel assets (path not found)',
              'productionPublished': False}
    (root / 'preview-delivery-review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'status': 'passed', 'httpRequests': len(checked), 'mapped': config['mappedCount'],
                      'unmapped': config['unresolvedCount'], 'gzipProductionPathsChecked': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--origin', default='http://127.0.0.1:8137')
    args = parser.parse_args()
    verify(args.root, args.origin)
