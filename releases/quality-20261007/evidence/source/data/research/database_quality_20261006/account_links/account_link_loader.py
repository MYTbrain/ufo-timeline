"""Fail-closed reader for optional original-account enrichment.

This helper is independent of the frontend and never edits events. Identity
relations cover every linked account; strict projection is optional, scoped
to selected records, and invalidated by changed view fields or composites.
"""
from __future__ import annotations
from collections.abc import Iterable, Mapping
import copy
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
from types import MappingProxyType

MAX_COMPRESSED=25*1024*1024
MAX_UNCOMPRESSED=256*1024*1024
MAX_LINE=256*1024
VIEW_FIELDS=('event_id','source','source_id','sort_date_iso','date_precision','has_coordinates','lat','lon','craft_type_inferred')

def _native(value,source):
    match=re.fullmatch(r'[Ss]?(\d+)' if source=='nuforc' else r'(\d+)',str(value or '').strip())
    return match.group(1) if match else ''

def _valid_point(fields):
    lat,lon=fields.get('lat'),fields.get('lon')
    return fields.get('has_coordinates') is True and type(lat) in {int,float} and type(lon) in {int,float} and math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180

def strict_row_is_eligible(row):
    """Recompute projection gates instead of trusting the eligibility flag."""
    if row.get('upstreamSource') not in {'mufon','nuforc'}:return False
    source,native=row['upstreamSource'],row.get('upstreamNativeId')
    if not isinstance(native,str) or not re.fullmatch(r'\d+',native):return False
    if row.get('accountKey')!=source+':'+native:return False
    try:
        primary,updb=row['primary'],row['updb'];p,u=primary['current'],updb['current']
        if p['source']!=source or u['source']!='phenomenainon_updb':return False
        if _native(p['source_id'],source)!=native:return False
        identity=updb['nativeIdentityEvidence']
        if identity['upstreamSource']!=source or _native(identity['upstreamNativeId'],source)!=native:return False
        for item in [primary,updb]:
            guard=item['memberGuard']
            if not all(guard.get(key) is True for key in ['ledgerConsistent','singleSourceMember','soleMemberAgreesWithPrimarySource']):return False
            if guard.get('retainedMemberCount')!=1 or guard.get('sourceProvenanceCount')!=1:return False
            if len(guard.get('canonicalInputIds',[]))!=1:return False
            if guard.get('memberSourceFamilies')!=[item['current']['source']]:return False
        date=p.get('sort_date_iso')
        if not date or date!=u.get('sort_date_iso'):return False
        if p.get('date_precision') not in {'day','exact_day'} or u.get('date_precision') not in {'day','exact_day'}:return False
        n=row['narrativeEvidence'];jac=n.get('significantTokenJaccard');tokens=n.get('sharedSignificantTokens')
        if n.get('priorScreen')!='strong_narrative_screen' or type(jac) not in {int,float} or not math.isfinite(jac) or not .80<=jac<=1:return False
        if type(tokens) is not int or tokens<20:return False
        if not _valid_point(p) or not _valid_point(u) or (p['lat'],p['lon'])!=(u['lat'],u['lon']):return False
        if not p.get('craft_type_inferred') or p['craft_type_inferred']!=u.get('craft_type_inferred'):return False
        return True
    except (KeyError,TypeError,ValueError):return False

def eligible_in_current_view(row,current_records):
    if not row.get('strictProjectionEligible') or not strict_row_is_eligible(row):return False
    for role in ['primary','updb']:
        item=row[role];current=current_records.get(item['eventId'])
        if not isinstance(current,Mapping):return False
        for field in VIEW_FIELDS:
            a,b=current.get(field),item['current'].get(field)
            if field=='event_id':a,b=str(a),str(b)
            if a!=b:return False
        # When a consumer supplies changed membership, it must match the pin.
        if 'canonical_input_ids' in current and list(current['canonical_input_ids'])!=item['memberGuard']['canonicalInputIds']:return False
        if 'duplicate_record_count' in current and current['duplicate_record_count']!=item['memberGuard']['retainedMemberCount']:return False
    return True

class AccountLinks:
    def __init__(self,manifest,rows):
        self.manifest=copy.deepcopy(manifest)
        self._rows=tuple(rows)
        by_event={}
        for index,row in enumerate(rows):
            for role in ['primary','updb']:
                eid=row[role]['eventId']
                if eid in by_event:raise ValueError('An event belongs to multiple account relations')
                by_event[eid]=(index,role)
        self.by_event=MappingProxyType(by_event)

    def __len__(self):return len(self._rows)

    def iter_links(self):
        for row in self._rows:yield copy.deepcopy(row)

    def relationship_for_event(self,event_id):
        match=self.by_event.get(str(event_id))
        if match is None:return None
        index,role=match
        return {'endpointRole':role,**copy.deepcopy(self._rows[index])}

    def account_key_for_event(self,event_id,strict=False):
        match=self.by_event.get(str(event_id))
        if match is None:return None
        row=self._rows[match[0]]
        return row['accountKey'] if not strict or row['strictProjectionEligible'] else None

    def project_selected_event_ids(self,selected_ids,current_records):
        """Optional view: suppress only eligible UPDB copies selected together.

        Primary-source preference applies only when both representations are
        already in the filtered cohort. All conflict/composite rows survive.
        """
        ordered=list(dict.fromkeys(str(eid) for eid in selected_ids));selected=set(ordered)
        suppressed={};used_groups=set()
        for eid in ordered:
            match=self.by_event.get(eid)
            if match is None:continue
            index,role=match
            if index in used_groups:continue
            used_groups.add(index);row=self._rows[index]
            p,u=row['primary']['eventId'],row['updb']['eventId']
            if p in selected and u in selected and eligible_in_current_view(row,current_records):suppressed[u]=p
        return {'keptEventIds':[eid for eid in ordered if eid not in suppressed],
                'suppressedRepresentations':suppressed,'selectedRepresentationCount':len(ordered),
                'projectedRepresentationCount':len(ordered)-len(suppressed),
                'policy':'optional_account_view_preserve_base_records_and_all_provenance'}

    def trace_pair_disposition(self,a_id,b_id,current_records):
        """Flag a copy-to-original trace only in the guarded current snapshot."""
        a,b=self.by_event.get(str(a_id)),self.by_event.get(str(b_id))
        if a is None or b is None or a[0]!=b[0]:return 'preserve'
        row=self._rows[a[0]]
        return 'same_account_republication_not_an_independent_trace' if eligible_in_current_view(row,current_records) else 'preserve'

def iter_account_links(manifest_path,expected_canonical_manifest_sha256):
    """Validate and stream links; exhaust iteration for total/count guarantees.

    Keeps only compact key/endpoint sets, not the expanded record collection.
    """
    path=Path(manifest_path).resolve();manifest=json.loads(path.read_bytes())
    expected=expected_canonical_manifest_sha256
    if not isinstance(expected,str) or not re.fullmatch(r'[0-9a-f]{64}',expected):raise ValueError('An explicit canonical manifest SHA256 pin is required')
    if manifest.get('schemaVersion')!=1 or manifest.get('policy')!='original_account_identity_enrichment_v1':raise ValueError('Unsupported account sidecar schema/policy')
    if manifest.get('canonicalOutputsMutated') is not False:raise ValueError('Unexpected destructive account policy')
    if manifest.get('canonicalDataset',{}).get('manifestSha256')!=expected:raise ValueError('Account sidecar canonical pin mismatch')
    artifact=manifest.get('artifacts',{}).get('accountLinks',{})
    name=artifact.get('path')
    if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.jsonl.gz'):raise ValueError('Unsafe account artifact path')
    target=(path.parent/name).resolve()
    if target.parent!=path.parent:raise ValueError('Account artifact escapes manifest directory')
    if artifact.get('encoding')!='gzip-jsonl-utf8':raise ValueError('Unsupported account artifact encoding')
    declared=artifact.get('bytes');expanded=artifact.get('uncompressedBytes')
    if type(declared) is not int or not 0<declared<=MAX_COMPRESSED:raise ValueError('Account compressed size exceeds guard')
    if type(expanded) is not int or not 0<expanded<=MAX_UNCOMPRESSED:raise ValueError('Account decoded size exceeds guard')
    if target.stat().st_size!=declared:raise ValueError('Account artifact byte count mismatch')
    blob=target.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=artifact.get('sha256'):raise ValueError('Account artifact SHA256 mismatch')
    keys=set();endpoints=set();row_count=0;expanded_count=0;eligible_count=0
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
        while True:
            raw=stream.readline(MAX_LINE+1)
            if not raw:break
            if len(raw)>MAX_LINE:raise ValueError('Account evidence row exceeds bound')
            expanded_count+=len(raw)
            if expanded_count>expanded:raise ValueError('Account expanded byte count exceeds pin')
            row=json.loads(raw)
            if row.get('schemaVersion')!=1:raise ValueError('Unsupported account row schema')
            source,native=row.get('upstreamSource'),row.get('upstreamNativeId')
            if source not in {'mufon','nuforc'} or not isinstance(native,str) or not re.fullmatch(r'\d+',native) or row.get('accountKey')!=source+':'+native:raise ValueError('Malformed original-account key')
            if row['accountKey'] in keys:raise ValueError('Repeated original-account key')
            keys.add(row['accountKey'])
            for role in ['primary','updb']:
                endpoint=row.get(role,{})
                if not isinstance(endpoint.get('eventId'),str) or not endpoint['eventId'].isdigit() or str(endpoint.get('current',{}).get('event_id'))!=endpoint['eventId']:raise ValueError('Malformed account endpoint ID')
                if endpoint['eventId'] in endpoints:raise ValueError('An event belongs to multiple account relations')
                endpoints.add(endpoint['eventId'])
                if endpoint.get('chunk') not in manifest.get('detailChunkPins',{}) or type(endpoint.get('index')) is not int or endpoint['index']<0:raise ValueError('Malformed account endpoint locator')
            if row['primary']['eventId']==row['updb']['eventId']:raise ValueError('Account representations must have distinct event IDs')
            eligibility=strict_row_is_eligible(row)
            if row.get('strictProjectionEligible') is not eligibility:raise ValueError('Account projection eligibility contradicts guarded evidence')
            if eligibility and (row.get('reviewFlags') or row.get('partition')!='agreeing_republication'):raise ValueError('Conflicting account projection policy')
            eligible_count+=int(eligibility);row_count+=1
            yield row
    if expanded_count!=expanded or row_count!=artifact.get('rows'):raise ValueError('Account artifact decoded byte/row mismatch')
    if eligible_count!=manifest.get('counts',{}).get('strictProjectionEligible'):raise ValueError('Account projection count mismatch')

def load_account_links(manifest_path,expected_canonical_manifest_sha256):
    """Optional complete in-memory index; large consumers should stream."""
    path=Path(manifest_path).resolve();manifest=json.loads(path.read_bytes())
    rows=list(iter_account_links(path,expected_canonical_manifest_sha256))
    return AccountLinks(manifest,rows)
