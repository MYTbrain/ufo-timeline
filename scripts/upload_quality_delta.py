"""Publish only frozen quality deltas, refusing conflicting immutable keys."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def remote_exists(row):
    request = urllib.request.Request(row['url'], headers={'Accept-Encoding': 'identity', 'User-Agent': 'UFO-Timeline-release-verification'})
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise
    digest = hashlib.sha256()
    size = 0
    with response:
        if response.status != 200 or response.headers.get('Content-Encoding', 'identity') not in ('', 'identity'):
            raise ValueError('Unexpected immutable object response: ' + row['key'])
        while True:
            block = response.read(1048576)
            if not block:
                break
            size += len(block)
            if size > row['bytes']:
                raise ValueError('Conflicting immutable object: ' + row['key'])
            digest.update(block)
    if size != row['bytes'] or digest.hexdigest() != row['sha256']:
        raise ValueError('Conflicting immutable object: ' + row['key'])
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--node', type=Path, required=True)
    parser.add_argument('--wrangler', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 5))
    parser.add_argument('--release-id', default='quality-20261007')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_bytes())
    assert manifest['bucket'] == 'ufo-timeline-data'
    assert re.fullmatch(r'[a-z0-9][a-z0-9-]{1,80}', args.release_id)
    assert manifest['release_id'] == args.release_id
    assert manifest['key_prefix'] == 'releases/' + args.release_id
    rows = manifest['uploads']
    assert len({row['key'] for row in rows}) == len(rows)
    for row in rows:
        path = Path(row['source']).resolve()
        assert row['key'].startswith(manifest['key_prefix'] + '/') and '..' not in row['key'].split('/')
        assert row['url'] == 'https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/' + row['key']
        assert path.stat().st_size == row['bytes'] and digest_file(path) == row['sha256']
    environment = os.environ.copy()
    if '--use-system-ca' not in environment.get('NODE_OPTIONS', ''):
        environment['NODE_OPTIONS'] = (environment.get('NODE_OPTIONS', '') + ' --use-system-ca').strip()

    def publish(row):
        for attempt in range(3):
            try:
                if remote_exists(row):
                    return {'key': row['key'], 'status': 'reused_identical', 'sha256': row['sha256'], 'bytes': row['bytes']}
                content_type = row.get('content_type', 'application/gzip' if row['key'].endswith('.gz') else 'application/json')
                command = [str(args.node), str(args.wrangler), 'r2', 'object', 'put',
                           manifest['bucket'] + '/' + row['key'], '--remote', '--file', row['source'],
                           '--content-type', content_type, '--cache-control', 'public,max-age=31536000,immutable']
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', env=environment, timeout=240)
                if result.returncode:
                    raise RuntimeError('Cloudflare object upload failed for ' + row['key'] + ': ' + (result.stderr or result.stdout)[-1600:])
                return {'key': row['key'], 'status': 'uploaded', 'sha256': row['sha256'], 'bytes': row['bytes']}
            except ValueError:
                raise
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))

    completed = []
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(publish, row): row['key'] for row in rows}
        for future in as_completed(futures):
            try:
                completed.append(future.result())
            except Exception as error:
                failures.append({'key': futures[future], 'error': str(error)})
            if len(completed) % 10 == 0 or failures or len(completed) == len(rows):
                print(f'Objects published: {len(completed)}/{len(rows)}; failures: {len(failures)}', flush=True)
    receipt = {'release_id': args.release_id, 'manifest_sha256': digest_file(args.manifest),
               'passed': not failures, 'objects': sorted(completed, key=lambda row: row['key']), 'failures': failures,
               'published_bytes': sum(row['bytes'] for row in completed), 'original_objects_replaced': False}
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8')
    if failures:
        print(json.dumps(failures, indent=2))
        return 1
    print(json.dumps({'passed': True, 'objects': len(completed), 'bytes': receipt['published_bytes']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
