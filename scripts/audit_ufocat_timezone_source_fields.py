"""Read-only whole-corpus/source UFOCAT TZ and TZONE inventory.

Writes one bounded audit, without accepting new UTC intervals, changing sources,
or copying the corpus. The CUFOS codebook is already preserved in shared storage.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time

SHARED = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
FRONTEND = Path(__file__).resolve().parents[1]
OUTPUT = SHARED / "data/research/trace-chronology-20261008/corpus-recovery/ufocat_timezone_sourcefield_audit.json"
VALID_CODES = {Decimal(str(value)) for value in [1,2,3,4,5,6,7,8,8.5,9,10,11,12,13,14,15,15.5,16,17,17.5,18,18.5,19,20,21,21.5,22,23,24]}
URL = "https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf"
FIELD_KEYS=('TZ','TZONE','TIME','YEAR','MO','DAY','REGION','STATE','PRN','COUNTY','LOCATION')

def selected_fields(raw):
    return {key:str(raw.get(key) or '') for key in FIELD_KEYS}

def validate_source_fields(rows,root=SHARED):
    source_root=(Path(root)/'data/canonical_web/event_chunks').resolve()
    grouped=defaultdict(list);seen=set()
    for row in rows:
        event_id=row.get('eventId')
        if type(event_id) is not int or not 0<event_id<=9_007_199_254_740_991 or event_id in seen:raise ValueError('Invalid or repeated UFOCAT source-field event ID')
        seen.add(event_id);path=Path(row.get('sourceChunkPath') or '').resolve()
        if path.parent!=source_root or path.stem!=row.get('sourceChunk') or path.suffix!='.json':raise ValueError('UFOCAT source path outside shared canonical chunks')
        grouped[path].append(row)
    pins=[]
    for path,group in sorted(grouped.items(),key=lambda item:str(item[0])):
        raw_bytes=path.read_bytes();h=hashlib.sha256(raw_bytes).hexdigest();events=json.loads(raw_bytes)
        for row in group:
            if row.get('sourceChunkSha256')!=h or row.get('sourceChunkBytes')!=len(raw_bytes):raise ValueError('UFOCAT source chunk hash or size drift')
            index=row.get('detailIndex')
            if type(index) is not int or not 0<=index<len(events):raise ValueError('UFOCAT source detail index invalid')
            event=events[index]
            if event.get('event_id')!=row['eventId'] or event.get('source')!='ufocat' or row.get('source')!='ufocat' or event.get('source_id')!=row.get('sourceId') or event.get('source_row_number')!=row.get('sourceRowNumber'):raise ValueError('UFOCAT source identity drift')
            if (event.get('sort_date_iso') or event.get('date_iso'))!=row.get('date') or event.get('date_precision')!=row.get('datePrecision') or str(event.get('time_raw') or '')!=row.get('rawTime'):raise ValueError('UFOCAT canonical source date or time drift')
            field=row.get('rawSourceField')
            if field not in {'raw_source_row','raw_fields'} or not isinstance(event.get(field),dict):raise ValueError('UFOCAT raw source field unavailable')
            actual=selected_fields(event[field])
            if actual!=row.get('fields') or not actual['TZ'].strip():raise ValueError('UFOCAT raw source TZ/TZONE/date/time/jurisdiction fields drift or blank flag')
            if row.get('flagClass')!=flag_class(actual['TZ'].strip()):raise ValueError('UFOCAT source flag interpretation drift')
            digest=hashlib.sha256(json.dumps(actual,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if digest!=row.get('sourceFieldsSha256'):raise ValueError('UFOCAT selected source fields hash drift')
        pins.append({'path':str(path),'bytes':len(raw_bytes),'sha256':h,'role':'ufocat_nonblank_time_date_flag_source','sourceFieldRecordsVerified':len(group)})
    return pins

def load(path):
    raw=Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if Path(path).suffix==".gz" else raw)

def pin(path):
    path=Path(path);h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return {'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':h.hexdigest()}

def code(raw):
    try:value=Decimal(raw)
    except (InvalidOperation,ValueError):return None
    return value if value in VALID_CODES else None

def flag_class(tz):
    if not tz:return 'unspecified_time_scale'
    if "'" in tz:return 'publication_date_not_occurrence'
    if '=' in tz:return 'date_believed_erroneous'
    if '-' in tz:return 'approximate_date_plusminus_one_or_two_days'
    if tz in {'.','+','*'}:return {'.':'explicit_standard_time','+':'explicit_one_hour_daylight_time','*':'explicit_GMT_date_and_time'}[tz]
    return 'undocumented_or_combined_flag_requires_review'

def measure(source_rows):
    counts=Counter();tzs=Counter();zones=Counter();pairs=Counter();classes=Counter();regions=Counter()
    for raw in source_rows:
        counts['rows']+=1
        tz=str(raw.get('TZ') or '').strip();zone=str(raw.get('TZONE') or '').strip()
        tzs[tz]+=1;zones[zone]+=1;pairs[(zone,tz)]+=1;classes[flag_class(tz)]+=1
        regions[str(raw.get('REGION') or '').strip()]+=1
        if code(zone) is not None:counts['documented_tzone_code']+=1
        elif zone:counts['undocumented_nonempty_tzone_code']+=1
        else:counts['empty_tzone_code']+=1
    return {'counts':dict(counts),'TZ_counts':dict(sorted(tzs.items())),'TZONE_counts':dict(sorted(zones.items())),'codeFlagPairs':[{'TZONE':zone,'TZ':tz,'count':n} for (zone,tz),n in sorted(pairs.items())],'flagClasses':dict(classes),'REGION_counts':dict(regions)}

def audit(root, runtime_path):
    start=time.monotonic();root=Path(root)
    attribute=root/'data/research/analysis-repairs-20261007/attributes/analysis_time_of_day_v1'
    manifest=load(attribute/'manifest.json')
    values=load(attribute/'time_of_day_value_dictionary_v1.json.gz')
    dictionary={(manifest['codes']['source'][v[0]],v[2]):manifest['codes']['status'][v[3]] for v in values}
    runtime=load(runtime_path)
    active_ids={r[0] for r in runtime['rows']}
    runtime_kinds={r[0]:runtime['codes']['evidence'][r[3]]['kind'] for r in runtime['rows']}
    runtime_intervals={r[0]:(r[1],r[2]) for r in runtime['rows']}
    source_ledger=[];offset_comparison=Counter();offset_samples=[]
    all_counts=Counter();quality=Counter();eligible=Counter();active_flags=Counter();inactive_flags=Counter()
    by_flag_status=defaultdict(Counter);by_code_region=defaultdict(Counter);samples=defaultdict(list);chunk_pins=[]
    def detail_rows():
        for path in sorted((root/'data/canonical_web/event_chunks').glob('*.json')):
            raw_bytes=path.read_bytes();events=json.loads(raw_bytes)
            chunk_hash=hashlib.sha256(raw_bytes).hexdigest()
            chunk_pins.append({'file':path.name,'bytes':len(raw_bytes),'sha256':chunk_hash})
            for index,event in enumerate(events):
                all_counts['all_corpus_rows_scanned']+=1
                if event.get('source')!='ufocat':continue
                all_counts['ufocat_catalog_rows']+=1
                raw=event.get('raw_source_row') or event.get('raw_fields') or {}
                tz=str(raw.get('TZ') or '').strip();zone=str(raw.get('TZONE') or '').strip();cls=flag_class(tz);z=code(zone)
                status=dictionary.get(('ufocat',str(event.get('time_raw') or '').strip()),'empty_or_unclassified')
                by_flag_status[tz][status]+=1
                by_code_region[zone][str(raw.get('REGION') or '').strip()]+=1
                if 'TZ' in raw:quality['raw_TZ_key_present']+=1
                if 'TZONE' in raw:quality['raw_TZONE_key_present']+=1
                if str(raw.get('TIME') or '').strip()!=str(event.get('time_raw') or '').strip():quality['canonical_TIME_drift']+=1
                if str(raw.get('PRN') or '').strip()!=str(event.get('source_id') or '').strip():quality['canonical_source_id_PRN_drift']+=1
                active=event['event_id'] in active_ids
                if tz:
                    field='raw_source_row' if event.get('raw_source_row') else 'raw_fields';fields=selected_fields(raw)
                    source_ledger.append({'eventId':event['event_id'],'source':'ufocat','sourceId':event.get('source_id'),'sourceRowNumber':event.get('source_row_number'),'date':event.get('sort_date_iso') or event.get('date_iso'),'datePrecision':event.get('date_precision'),'rawTime':str(event.get('time_raw') or ''),'sourceChunk':path.stem,'sourceChunkPath':str(path.resolve()),'sourceChunkSha256':chunk_hash,'sourceChunkBytes':len(raw_bytes),'detailIndex':index,'rawSourceField':field,'fields':fields,'sourceFieldsSha256':hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'flagClass':cls})
                (active_flags if active else inactive_flags)[cls]+=1
                if event.get('date_precision')=='exact_day':
                    eligible['exact_date_'+cls]+=1
                    if active:eligible['currently_accepted_exact_date_'+cls]+=1
                    if status=='exact_clock':
                        eligible['exact_clock_exact_date_'+cls]+=1
                        if cls=='explicit_GMT_date_and_time' or cls in {'explicit_standard_time','explicit_one_hour_daylight_time'} and z is not None:
                            eligible['documented_explicit_clock_timebase_total']+=1
                            eligible['documented_explicit_clock_timebase_'+('active' if active else 'not_in_current_runtime')]+=1
                            if str(event.get('sort_date_iso') or '')<'1970-01-01':eligible['documented_explicit_clock_timebase_pre1970']+=1
                            if not event.get('has_coordinates'):eligible['documented_explicit_clock_timebase_original_detail_unmapped']+=1
                            clock=str(raw.get('TIME') or '').strip();event_date=event.get('sort_date_iso') or event.get('date_iso')
                            if active and len(clock)==4 and clock.isdigit() and int(clock[:2])<24 and int(clock[2:])<60:
                                offset=0 if tz=='*' else int((z-12)*60)+(60 if tz=='+' else 0)
                                try:
                                    wall=datetime.fromisoformat(event_date).replace(tzinfo=timezone.utc)+timedelta(minutes=int(clock[:2])*60+int(clock[2:])-offset)
                                except (ValueError,TypeError):offset_comparison['invalid_calendar_date']+=1
                                else:
                                    expected_start=int(wall.timestamp()*1000);expected_end=expected_start+59_999
                                    current_start,current_end=runtime_intervals[event['event_id']]
                                    if (expected_start,expected_end)==(current_start,current_end):lane='matches_source_explicit_offset'
                                    elif current_start<=expected_start and current_end>=expected_end:lane='source_explicit_offset_contained_in_broader_current_interval'
                                    else:lane='current_interval_does_not_contain_source_explicit_offset'
                                    offset_comparison[tz+'_'+lane]+=1
                                    if lane=='current_interval_does_not_contain_source_explicit_offset' and len(offset_samples)<12:offset_samples.append({'eventId':event['event_id'],'TZ':tz,'TZONE':zone,'standardOffsetMinutes':None if tz=='*' else int((z-12)*60),'expectedOffsetMinutes':offset,'currentKind':runtime_kinds[event['event_id']],'expectedUtcStartMs':expected_start,'expectedUtcEndMs':expected_end,'currentUtcStartMs':current_start,'currentUtcEndMs':current_end,'sourceChunk':path.stem,'detailIndex':index})
                if cls in {'publication_date_not_occurrence','date_believed_erroneous','approximate_date_plusminus_one_or_two_days'} and active:
                    quality['current_runtime_includes_source_date_warning_flags']+=1
                    quality['current_runtime_flagged_kind_'+runtime_kinds[event['event_id']]]+=1
                if len(samples[cls])<4 or event['event_id']==3448855352240391:
                    samples[cls].append({'eventId':event['event_id'],'sourceId':event.get('source_id'),'sourceRowNumber':event.get('source_row_number'),'date':event.get('sort_date_iso'),'datePrecision':event.get('date_precision'),'TIME':raw.get('TIME'),'typedClockStatus':status,'TZ':tz,'TZONE':zone,'REGION':raw.get('REGION'),'STATE':raw.get('STATE'),'COUNTY':raw.get('COUNTY'),'LOCATION':raw.get('LOCATION'),'sourceChunk':path.stem,'detailIndex':index,'currentlyAccepted':active,'runtimeKind':runtime_kinds.get(event['event_id'])})
                yield raw
    corpus_measure=measure(detail_rows())
    csv_path=root/'UFO Databases/ufocat2023.csv'
    with csv_path.open('r',encoding='utf-8-sig',newline='',errors='strict') as stream:
        csv_measure=measure(csv.DictReader(stream))
    result={'schemaId':'ufocat-source-timezone-field-audit-v1','scope':{'allCorpus':dict(all_counts),'wholeProtectedCSV':csv_measure['counts']['rows'],'runtimeRelease':runtime.get('releaseId')},'catalogInventory':corpus_measure,'sourceCSVInventory':csv_measure,'sourceQuality':dict(quality),'currentRuntimeByFlagClass':dict(active_flags),'heldRuntimeByFlagClass':dict(inactive_flags),'eligibilityBeforeIndependentGeographicAndDateChecks':dict(eligible),'TZByTypedClockStatus':{k:dict(v) for k,v in by_flag_status.items()},'TZONEByREGION':{k:dict(v) for k,v in by_code_region.items()},'samples':dict(samples),'primaryCodebook':{'url':URL,'pageLocators':{'TIME':17,'TZ':18,'TZONE':19,'REGION':24},'numericOffsetInference':'For listed codebook TZONE values only, standard UTC offset minutes = (TZONE - 12) * 60. This mapping is inferred from the code table; TZONE itself is not an hours-west offset.','knownFlagPolicy':{'*':'GMT date/time; no TZONE adjustment','+':'local time at documented standard code offset plus exactly 60 minutes','.':'explicit source standard time at documented code offset','-':'date uncertainty of one or two days; do not accept exact occurrence day',"'":'publication date; exclude from occurrence chronology','=':'date believed erroneous; exclude from occurrence chronology','blank':'unspecified time scale; do not assert DST or standard','other':'hold combined/undocumented flags for source review'},'defaultPolicy':'No TZONE missing/default/sentinel code is defined in Table 3; blank, zero, and unlisted values remain unresolved. Existing TIME sentinel safeguards remain pending original export-lineage review.','regionPolicy':'REGION CA is Central America; CN is Canada. STATE is country/state code; REGION is not an ISO country code.'},'inputs':{'script':pin(Path(__file__)),'rawCSV':pin(csv_path),'localCodebookPDF':pin(root/'data/reports/ufocat_codebook_extract/UFOCAT Codebook 2023.pdf'),'localCodebookText':pin(root/'data/reports/ufocat_codebook_extract/UFOCAT Codebook 2023.txt'),'typedManifest':pin(attribute/'manifest.json'),'typedDictionary':pin(attribute/'time_of_day_value_dictionary_v1.json.gz'),'runtime':pin(runtime_path),'canonicalManifest':pin(root/'data/canonical_web/canonical_web_manifest.json'),'canonicalSourceChunks':chunk_pins},'policy':{'sourceMutated':False,'runtimeMutated':False,'newUTCEvidenceAccepted':False,'offsetSignGuessedFromLongitude':False,'missingDSTInvented':False,'sourceNoonMidnightDefaultsPromoted':False},'storage':{'purpose':'Whole-source TZ/TZONE inventory and codebook acceptance/holdout policy evidence for a future source-field chronology gate','rebuild':'Run audit_ufocat_timezone_source_fields.py against these pinned shared inputs; one source chunk and CSV stream at a time','canonicalArtifact':'this small audit JSON','rollback':'existing validated v2 artifact and retained v1 rollback remain unchanged','retention':'retain this unique scientific audit with chronology evidence; no staging/corpus/backup copy created','supersededArtifacts':[],'newFilesLargerThan100MiB':[]},'elapsedSeconds':round(time.monotonic()-start,3)}
    result['explicitFlagCurrentRuntimeOffsetComparison']=dict(offset_comparison)
    result['explicitFlagCurrentRuntimeOffsetConflictSamples']=offset_samples
    result['_sourceLedger']={'schemaId':'ufocat-source-time-date-fields-v1','policy':{'scope':'every retained UFOCAT record with any nonblank TZ flag; all flags retained including unknown and combined','sourceMutated':False,'newUTCEvidenceAccepted':False,'blankTimeScalePromoted':False,'sourceSentinelsPromoted':False,'publicationErrorApproximationFlagsOverrideClockMarkers':True},'primaryCodebook':{'url':URL,'printedPages':[17,18,19,24],'validStandardCodeOffsetMinutes':{str(z):int((z-12)*60) for z in sorted(VALID_CODES)}},'rows':source_ledger}
    result['_sourceLedger']['storage']={'purpose':'Sparse pinned own-source TZ/TZONE/date/time fields for chronology acceptance and holdout gates; not a corpus copy','canonicalArtifact':'fields.json.gz with the adjacent source_verification_receipt.json','provenance':'Every row pins its original shared canonical source chunk and exact selected raw source fields; code semantics cite the original CUFOS codebook','rebuild':'Run scripts/audit_ufocat_timezone_source_fields.py against the shared protected chunks and source CSV, then run --verify-only on fields.json.gz','retention':'Retain while used by chronology and preserve the unique audit/verification receipts; existing validated v2 and retained rollback are unchanged','supersededArtifacts':[],'newFilesLargerThan100MiB':[]}
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=SHARED)
    parser.add_argument('--runtime',type=Path,default=FRONTEND/'data/trace_chronology/evidence.json.gz')
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--verify-only',type=Path)
    args=parser.parse_args()
    if args.verify_only:
        ledger=load(args.verify_only);pins=validate_source_fields(ledger['rows'],args.root)
        receipt={'schemaId':'ufocat-source-field-verification-receipt-v1','ledger':pin(args.verify_only),'extractor':pin(Path(__file__)),'verifiedSourceRows':len(ledger['rows']),'verifiedSourceChunks':len(pins),'sourceHashesIdentityDateClockAndSelectedFieldsVerified':True,'purpose':'Retain source reopening receipt with sparse nonblank TZ-field ledger; rebuild using helper --verify-only.'}
        receipt_path=args.verify_only.parent/'source_verification_receipt.json';receipt_path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt,indent=2));return
    result=audit(args.root,args.runtime);ledger=result.pop('_sourceLedger')
    raw=(json.dumps(result,indent=2,sort_keys=True)+'\n').encode('utf-8')
    if len(raw)>1024*1024:raise ValueError('Audit exceeds the explicit 1 MiB budget; nothing written')
    ledger_raw=gzip.compress(json.dumps(ledger,sort_keys=True,separators=(',',':')).encode(),mtime=0)
    if len(ledger_raw)>3*1024*1024:raise ValueError('Sparse flag ledger exceeds 3 MiB budget; nothing written')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(raw)
    ledger_path=args.output.parent/'ufocat-source-fields/fields.json.gz';ledger_path.parent.mkdir(parents=True,exist_ok=True);ledger_path.write_bytes(ledger_raw)
    print(json.dumps({'path':str(args.output),'bytes':len(raw),'ledger':str(ledger_path),'ledgerRows':len(ledger['rows']),'ledgerBytes':len(ledger_raw),'scope':result['scope'],'catalogCounts':result['catalogInventory']['counts'],'TZ':result['catalogInventory']['TZ_counts'],'quality':result['sourceQuality'],'eligibility':result['eligibilityBeforeIndependentGeographicAndDateChecks'],'offsetComparison':result['explicitFlagCurrentRuntimeOffsetComparison'],'elapsedSeconds':result['elapsedSeconds']},indent=2))

if __name__=='__main__':main()
