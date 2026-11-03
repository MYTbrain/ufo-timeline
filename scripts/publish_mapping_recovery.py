"""Publish only the frozen reviewed mapping allowlist; never overwrite different immutable data."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from prepare_quality_release import verify_remote_record

ROOT = Path(__file__).resolve().parents[1]
NODE = Path('C:/Program Files/nodejs/node.exe')
WRANGLER = Path('C:/Users/jarod/Desktop/UFO Timeline map tool/node_modules/wrangler/bin/wrangler.js')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_file(row):
    path = Path(row['source'])
    if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
        raise ValueError('Frozen candidate mismatch: ' + str(path))
    return path


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf8', newline='\n')


def upload(plan, root):
    env = dict(os.environ)
    env['NODE_OPTIONS'] = (env.get('NODE_OPTIONS', '') + ' --use-system-ca').strip()
    rows = plan['uploads']
    def one(row):
        source = frozen_file(row)
        if not row['key'].startswith('releases/mapping-recovery-20261103/'):
            raise ValueError('Upload escaped the new immutable prefix')
        probe = row['url'] + '?preflight=' + row['sha256']
        try:
            verify_remote_record(probe, row, 45)
            status = 'reused_identical'
        except HTTPError as error:
            if error.code != 404:
                raise
            result = subprocess.run([str(NODE), str(WRANGLER), 'r2', 'object', 'put',
                'ufo-timeline-data/' + row['key'], '--file', str(source), '--remote',
                '--content-type', 'application/gzip' if source.suffix == '.gz' else 'application/json',
                '--cache-control', 'public, max-age=31536000, immutable'],
                env=env, cwd=ROOT, text=True, encoding='utf-8', errors='replace', capture_output=True)
            if result.returncode:
                raise RuntimeError('Upload failed: ' + row['key'] + '\n' + result.stdout[-1800:] + result.stderr[-1800:])
            status = 'uploaded_new'
        for attempt in range(3):
            try:
                verify_remote_record(row['url'] + '?verified=' + row['sha256'] + str(attempt), row, 60)
                break
            except (OSError, ValueError):
                if attempt == 2:
                    raise
                time.sleep(2)
        return {'key': row['key'], 'bytes': row['bytes'], 'sha256': row['sha256'], 'status': status}
    done = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(one, row) for row in rows]
        for future in as_completed(futures):
            done.append(future.result())
            save(root / 'r2-publication-progress.json', {'completed': len(done), 'objects': sorted(done, key=lambda x:x['key'])})
            if len(done) % 10 == 0 or len(done) == len(rows):
                print(f'Uploaded and verified {len(done)}/{len(rows)} immutable data objects', flush=True)
    save(root / 'r2-publication.json', {'status': 'uploaded_and_public_hash_verified', 'objects': sorted(done, key=lambda x:x['key']),
        'bytes': sum(row['bytes'] for row in rows), 'existingDifferentObjectsOverwritten': False,
        'contentEncodingForExplicitGzip': None, 'newLocalLargeCopies': 0})


def materialize(plan, root):
    stage = root / 'pages-stage'
    expected = {row['path'] for row in plan['pages']}
    if stage.exists() and any(p.relative_to(stage).as_posix() not in expected for p in stage.rglob('*') if p.is_file()):
        raise ValueError('Unexpected existing staging files; no automatic deletion')
    stage.mkdir(exist_ok=True)
    changed, growth = [], 0
    for row in plan['pages']:
        source = frozen_file(row)
        for base in (ROOT, stage):
            destination = (base / row['path']).resolve()
            if not destination.is_relative_to(base.resolve()):
                raise ValueError('Invalid Pages destination')
            if destination == source.resolve():
                continue
            before = destination.stat().st_size if destination.exists() else 0
            if destination.exists() and sha(destination) == row['sha256']:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if sha(destination) != row['sha256']:
                raise ValueError('Materialized file mismatch')
            if base == ROOT:
                changed.append(row['path'])
                growth += row['bytes'] - before
    # Track a self-contained allowlist pointing to committed runtime inputs.
    release = ROOT / 'releases/mapping-recovery-20261103'
    runtime_plan = dict(plan)
    runtime_plan['pages'] = [{**row, 'source': str(ROOT / row['path'])} for row in plan['pages']]
    runtime_plan['stage'] = str(stage)
    runtime_plan['bucket'] = 'ufo-timeline-data'
    runtime_plan['retained_rollback'] = plan['base_deployment']['deploymentId']
    save(release / 'delivery_plan.json', runtime_plan)
    receipt = {'status': 'frozen_allowlist_materialized', 'stage': str(stage), 'files': len(expected),
        'bytes': sum(row['bytes'] for row in plan['pages']), 'pagesTreeSha256': plan['pages_tree_sha256'],
        'changedRuntimePaths': changed, 'approximateCNetGrowthBytes': growth,
        'newFilesAbove100MiB': [], 'sourceCorpusOrDatabaseCopied': False,
        'retention': 'New canonical Pages candidate; prior .tmp/workspace-analysis-20261008-pages retains current production as rollback.'}
    save(root / 'pages-stage-receipt.json', receipt)
    print(json.dumps(receipt), flush=True)


def verify_pages(plan, base, output):
    done = []
    rows = [r for r in plan['pages'] if r['path'] not in ('_headers', '.nojekyll')]
    def one(row):
        needs_fresh = (row['path'] in ('index.html', 'app.js', 'quality_detail_overlay.js', 'data/app_config.json')
            or row['path'].endswith('/manifest.json') or row['path'].startswith('data/mapping_recovery_detail/'))
        verify_remote_record(base.rstrip('/') + '/' + row['path'], {**row, 'requires_revalidation': needs_fresh,
            'allow_pages_analytics': row['path'].endswith('.html')}, 60)
        return row['path']
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one, r) for r in rows]):
            done.append(future.result())
            if len(done) % 40 == 0 or len(done) == len(rows):
                print(f'Verified {len(done)}/{len(rows)} published Pages files', flush=True)
    result = {'status': 'all_pages_hashes_and_required_cache_headers_verified', 'base': base,
              'verifiedFiles': len(done), 'paths': sorted(done), 'pagesTreeSha256': plan['pages_tree_sha256']}
    save(output, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--materialize', action='store_true')
    parser.add_argument('--verify-pages')
    parser.add_argument('--verification-output', type=Path)
    args = parser.parse_args()
    plan = json.loads((args.root / 'candidate/delivery_plan.json').read_bytes())
    if args.upload:
        upload(plan, args.root)
    if args.materialize:
        materialize(plan, args.root)
    if args.verify_pages:
        verify_pages(plan, args.verify_pages, args.verification_output)
