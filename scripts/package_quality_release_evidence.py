"""Package byte-pinned sparse quality evidence; never copy the source corpus.

The package is a review handoff, not a relocated runnable QualityView. Original
manifests retain their exact bytes and absolute shared-input references.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Q06 = Path('data/research/database_quality_20261006')
Q07 = Path('data/research/database_quality_20261007')
RELEASE = Path('data/releases/quality-20261007')
DEST = RELEASE / 'release_metadata_evidence'
CAP = 10 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')


def plan():
    quality = json.loads((ROOT / Q07 / 'quality_view_manifest.json').read_bytes())
    entries = {}

    def add(relative, role, expected=None, rows=None, encoding=None):
        relative = Path(relative)
        if relative in entries:
            return
        source = ROOT / relative
        raw = source.read_bytes()
        if len(raw) > 6 * 1024 * 1024 or source.suffix.lower() in {'.zip', '.7z', '.sqlite', '.db', '.bin'}:
            raise ValueError(f'Large/archive/corpus input is prohibited: {relative}')
        if expected and (digest(raw) != expected['sha256'] or ('bytes' in expected and len(raw) != expected['bytes'])):
            raise ValueError(f'Pinned source changed: {relative}')
        compress = len(raw) > 100_000 and source.suffix != '.gz'
        content = gzip.compress(raw, compresslevel=9, mtime=0) if compress else raw
        stored = 'source/' + relative.as_posix() + ('.gz' if compress else '')
        entries[relative] = ({'source_path': relative.as_posix(), 'package_path': stored,
                              'bytes': len(content), 'sha256': digest(content),
                              'source_bytes': len(raw), 'source_sha256': digest(raw),
                              'storage_encoding': 'gzip-original-bytes' if compress else 'original-bytes',
                              'role': role, 'rows': rows, 'decision_encoding': encoding}, content)

    def pin(relative, item, role):
        root = Path(item.get('artifact_root', ROOT / relative))
        source = root / item['path']
        add(source.relative_to(ROOT), role, item, item.get('rows'), item.get('encoding'))

    add(Q07 / 'quality_view_manifest.json', 'current_guarded_quality_manifest')
    for item in quality['decision_artifacts']:
        pin(Q07, item, 'accepted_sparse_decisions')
    for key in ['date_review_annotations', 'reader', 'account_manifest', 'account_loader', 'incident_relationships']:
        pin(Q07, quality[key], key)
    add(Path(quality['previous_quality_view']['path']).relative_to(ROOT), 'frozen_local_quality_rollback_manifest', quality['previous_quality_view'])
    for item in quality['continuation_provenance'].values():
        if isinstance(item, dict) and 'path' in item and 'sha256' in item:
            pin(Q07, item, 'continuation_input_pin')

    allow06 = ['README.md', 'REPORT.md', 'quality_view_test_receipt.json',
               'account_links/account_link_quality_receipt.json',
               'location_corrections/decision_manifest.json', 'location_corrections/REPORT.md',
               'unmapped_recovery/reviewed_authorities.json', 'unmapped_recovery/UNMAPPED_RECOVERY_REPORT.md']
    allow07 = ['README.md', 'REPORT.md', 'CONTINUATION_REPORT.md', 'parallel_reader_review.json',
               'continuation_02/README.md', 'continuation_02/quality_view_validation.json',
               'continuation_02/quality_view_test_receipt.json', 'continuation_02/coordinate_peer_review.json',
               'account_recovery/README.md', 'account_recovery/REPORT.md', 'account_recovery/validation_receipt.json',
               'account_recovery/official_source_receipts.json', 'account_recovery/source_date_uncertainty_reviews.jsonl',
               'account_reverse_recovery/README.md', 'account_reverse_recovery/REPORT.md',
               'account_reverse_recovery/accepted_source_context_review.jsonl.gz',
               'account_reverse_recovery/original_source_evidence.jsonl.gz', 'account_reverse_recovery/online_source_receipts.json',
               'gazetteer_recovery/REPORT.md', 'gazetteer_recovery/verification_receipt.json',
               'gazetteer_recovery/full_source_review_census.json', 'gazetteer_recovery/representative_online_fact_receipts.json',
               'gazetteer_recovery/online_authority_receipts.json', 'gazetteer_recovery/admin2_gb_authority_receipt.json',
               'online_sources/README.md', 'online_sources/decision_manifest.json', 'online_sources/validation_receipt.json',
               'online_sources/online_retrieval_receipts.json', 'online_sources/reviewed_online_specs.json',
               'online_sources/online_source_abstentions.json', 'online_sources/ukab_case_extracts.json',
               'online_sources/facility_review_extracts.json',
               'grid_reference_recovery/README.md', 'grid_reference_recovery/REPORT.md',
               'grid_reference_recovery/validation_receipt.json', 'grid_reference_recovery/projection_validation.json',
               'grid_reference_recovery/named_grid_place_references.json', 'grid_reference_recovery/source_grid_candidates.json',
               'international_source_recovery/README.md', 'international_source_recovery/REPORT.md',
               'international_source_recovery/verification_receipt.json', 'international_source_recovery/focused_date_amendment_receipt.json',
               'international_source_recovery/online_source_fact_receipts.json',
               'international_source_recovery/mufon_reporting_field_pdf_receipt.json', 'international_source_recovery/accepted_context_qc.json',
               'extended_online_recovery/README.md', 'extended_online_recovery/REPORT.md',
               'extended_online_recovery/extended_decision_manifest.json', 'extended_online_recovery/extended_validation_receipt.json',
               'extended_online_recovery/primary_geographic_fact_receipts.json', 'extended_online_recovery/primary_source_retrieval_receipts.json',
               'extended_online_recovery/reviewed_primary_authority_specs.json',
               'extended_online_recovery/british_grid_full_review_records.json', 'extended_online_recovery/fort_huachuca_full_review_records.json',
               'coordinate_notation_recovery/REPORT.md', 'coordinate_notation_recovery/validation_receipt.json',
               'coordinate_notation_recovery/online_authority_facts.json', 'coordinate_notation_recovery/place_authorities.json',
               'coordinate_notation_recovery/publisher_contexts.json']
    for relative in allow06:
        add(Q06 / relative, 'bounded_research_report_or_source_receipt')
    for relative in allow07:
        add(Q07 / relative, 'bounded_research_report_or_source_receipt')
    add('data/reports/ufocat_codebook_extract/UFOCAT Codebook 2023.txt', 'source_coordinate_and_location_role_codebook')
    for relative in ['map_delta/map_release_receipt.json', 'map_delta/canonical_web_manifest.json',
                     'analysis_delta/analysis_release_receipt.json', 'analysis_delta/analysis_validation_receipt.json',
                     'analysis_delta/README.md']:
        add(RELEASE / relative, 'validated_current_release_receipt')

    citations = {}
    referenced = []
    for metadata, data in entries.values():
        raw = gzip.decompress(data) if metadata['storage_encoding'] == 'gzip-original-bytes' else data
        if metadata['source_path'].endswith('.gz'):
            raw = gzip.decompress(raw)
        text = raw.decode('utf-8')
        for url in re.findall(r'https?://[^\s<>\"\)\]]+', text):
            url = url.rstrip('.,;')
            citations.setdefault(url, set()).add(metadata['source_path'])
        if metadata['source_path'].endswith('.json'):
            def walk(value, pointer=''):
                if isinstance(value, dict):
                    if 'path' in value and ('sha256' in value or 'bytes' in value):
                        referenced.append({'citing_source_path': metadata['source_path'], 'pointer': pointer, 'reference': value})
                    for key, item in value.items():
                        walk(item, pointer + '/' + key)
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        walk(item, pointer + '/' + str(index))
            walk(json.loads(text))
    account = json.loads((ROOT / Q06 / 'account_links/account_links_manifest.json').read_bytes())
    omitted = {'purpose': 'Required shared artifacts are pinned, never copied into this review handoff.',
               'canonical_base': quality['base'], 'release_contract': quality['data_release_contract'],
               'account_link_inputs': account['inputs'], 'account_link_artifacts': account['artifacts'],
               'source_archive_policy': 'GeoNames allCountries.zip and OS developers ZIP remain shared local authority inputs. Native detail chunks/source corpus, runtime binaries and PDFs/images/archives are omitted; exact local source locators, hashes and source URLs remain in the accepted decisions and receipts.',
               'cited_file_references': referenced,
               'source_archive_pins': [
                   {'path': (Q07 / 'grid_reference_recovery/OSTN15-OSGM15-Lite-DevelopersPack.zip').as_posix(),
                    'bytes': 1260148, 'sha256': '0594285d3b4b8042558c42a5084f54db01c544332e417a63b0dea2b1ae977ed8'},
                   {'authority': 'GeoNames allCountries.zip', 'sha256': '310d96cddfec6c9d7a6ca901707473e7a0e03ec442487c0ddba69e33076cc748',
                    'url': 'https://download.geonames.org/export/dump/allCountries.zip'}]}
    generated = {'source_citation_ledger.json': dump({'scope': 'URL navigation index extracted from included evidence. A link is not an independent verification; individual receipts specify retrieval method, fact scope and time.',
                                                      'citations': [{'url': key, 'citing_source_paths': sorted(value)} for key, value in sorted(citations.items())]}),
                 'shared_dependencies.json.gz': gzip.compress(dump(omitted), compresslevel=9, mtime=0)}
    inventory = {'schema': 'quality-release-evidence-package-v1', 'quality_manifest_sha256': digest((ROOT / Q07 / 'quality_view_manifest.json').read_bytes()),
                 'role': 'Git-ready review handoff; original byte hashes retained; not a portable runnable catalog.',
                 'files': [item[0] for _, item in sorted(entries.items())],
                 'generated_files': [{'package_path': name, 'bytes': len(data), 'sha256': digest(data)} for name, data in generated.items()],
                 'retention': 'Retain with the current quality release; the protected original research evidence stays canonical for research provenance. This bounded compressed handoff replaces no source and creates no additional deployment or corpus rollback.',
                 'archives_copied': False, 'full_corpus_copy_created': False, 'source_mutated': False}
    generated['package_manifest.json'] = dump(inventory)
    total = sum(item[0]['bytes'] for item in entries.values()) + sum(map(len, generated.values()))
    if total > CAP - 64 * 1024:
        raise ValueError(f'Package exceeds storage budget: {total}')
    return entries, generated, total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    entries, generated, total = plan()
    print(json.dumps({'destination': str(ROOT / DEST), 'planned_source_and_inventory_bytes': total,
                      'files': len(entries) + len(generated), 'source_archives_copied': False,
                      'files_over_100MiB': [], 'cap_bytes': CAP}))
    if not args.write:
        return
    for metadata, data in entries.values():
        target = ROOT / DEST / metadata['package_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f'Refusing to replace changed evidence file: {target}')
        target.write_bytes(data)
    for name, data in generated.items():
        target = ROOT / DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f'Refusing to replace changed generated evidence file: {target}')
        target.write_bytes(data)


if __name__ == '__main__':
    main()
