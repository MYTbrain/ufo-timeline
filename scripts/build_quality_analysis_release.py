"""Build gzip-only quality analysis deltas from shared guarded source records.

The established analysis algorithms remain the classifiers. Their two detail
input expressions are adapted in memory to a validated source stream; their
serialization hook emits only changed gzip artifacts. No corpus/DB copy is made.
The default command estimates storage; --build is an explicit release operation.
"""
from __future__ import annotations
import argparse
import ast
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'webapp/static_public/data'
QUALITY=ROOT/'data/research/database_quality_20261007/quality_view_manifest.json'
MAP=ROOT/'data/releases/quality-20261007/map_delta'
OUTPUT=ROOT/'data/releases/quality-20261007/analysis_delta'
ORIGIN='https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev'
PREFIX='releases/quality-20261007/analysis_delta'
CAP=65*1024*1024
LANES=('analysis_duration_v1','analysis_reporting_delay_v1','analysis_time_of_day_v1',
       'analysis_witness_count_v1','analysis_color_v1','analysis_coordinate_evidence_v1')
GENERALIZED_SOURCES={'geocoded','reviewed_location_authority','source_account_city_reference',
 'reviewed_source_coordinates','source_grid_reference','independent_source_named_place_reference',
 'reviewed_observer_installation_reference','reviewed_locality_reference'}
SOURCE_KEYS=('event_id','canonical_event_id','source','sort_date_iso','date_iso','date_precision',
 'reported_date_raw','posted_date_raw','coordinate_source','location_precision','location_raw',
 'country','lat','lon','duplicate_record_count','duration_raw','time_raw')
RAW_COORD_KEYS=('LATITUDE','Latitude','latitude','lat','LONGITUDE','Longitude','longitude','lon','lng',
 'key_vals/LatLong','LatLong','coordinates','Coordinates','key_vals/LatLongDMS','LatLongDMS')

def sha_bytes(value):return hashlib.sha256(value).hexdigest()
def sha_file(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def compact(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def read_json(path):return json.loads(Path(path).read_bytes())
def load_module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
 sys.modules[name]=m;spec.loader.exec_module(m);return m

class DetailInputTransformer(ast.NodeTransformer):
 """Two exact input-only substitutions; drift fails instead of broad rewriting."""
 def __init__(self):self.paths=0;self.rows=0
 def visit_Assign(self,node):
  target=node.targets[0] if len(node.targets)==1 else None
  if isinstance(target,ast.Name) and target.id=='chunk_paths' and ast.unparse(node.value)=='sorted(detail_root.glob(\'chunk_*.json\'))':
   node.value=ast.parse('quality_detail_paths(detail_root)',mode='eval').body;self.paths+=1
  if isinstance(target,ast.Name) and target.id=='rows' and ast.unparse(node.value)=='json.loads(chunk_path.read_text(encoding=\'utf-8\'))':
   node.value=ast.parse('quality_detail_rows(chunk_path)',mode='eval').body;self.rows+=1
  return self.generic_visit(node)

def adapted_builder(path):
 source=Path(path).read_text(encoding='utf8');tree=ast.parse(source);adapter=DetailInputTransformer()
 # Only build() is adapted, so unrelated JSON/authority reads stay unchanged.
 for node in tree.body:
  if isinstance(node,ast.FunctionDef) and node.name=='build':adapter.visit(node)
 if (adapter.paths,adapter.rows)!=(1,1):raise ValueError(f'Builder source input contract changed: {path}')
 m=types.ModuleType('scripts.quality_adapted_'+Path(path).stem);m.__file__=str(path);m.__package__='scripts'
 exec(compile(ast.fix_missing_locations(tree),str(path),'exec'),m.__dict__)
 return m

def compact_source_record(event,witness_field):
 """Only fields consumed by the frozen algorithms; narrative/raw originals stay shared."""
 row={k:event.get(k) for k in SOURCE_KEYS}
 raw=event.get('raw_fields') or {};row['raw_fields']={k:raw[k] for k in ('Color','COLOR',witness_field) if k in raw}
 raw_source=event.get('raw_source_row') or {};row['raw_source_row']={k:raw_source[k] for k in RAW_COORD_KEYS if k in raw_source}
 return row

class SharedEffectiveDetails:
 """One shared source pass, compact in-memory fields, no persistent detail copy."""
 def __init__(self,view,adapter,witness_field):self.view=view;self.adapter=adapter;self.witness_field=witness_field;self.rows={};self.chunks_checked=0
 def paths(self,root):
  if Path(root).resolve()!=(self.view.base/'event_chunks').resolve():raise ValueError('Unexpected detail root')
  return [self.view.base/'event_chunks'/(r['id']+'.json.gz') for r in self.view.chunk_metadata.values()]
 def get(self,path):
  name=Path(path).name
  if name not in self.rows:
   checked=self.view._base_file('event_chunks/'+name);full=json.loads(gzip.decompress(checked.read_bytes()));projected=[]
   for event in full:
    effective=self.adapter(self.view,event) if str(event['event_id']) in self.view.decisions else event
    projected.append(compact_source_record(effective,self.witness_field))
   self.rows[name]=projected;self.chunks_checked+=1
  return self.rows[name]

class DeltaWriter:
 def __init__(self,root,origin=ORIGIN,prefix=PREFIX,cap=CAP):
  self.root=Path(root);self.origin=origin.rstrip('/');self.prefix=prefix.strip('/');self.cap=cap;self.written=0;self.files=[];self.reused=[]
 def put(self,path,data,delivery='r2'):
  path=Path(path);rel=path.relative_to(self.root).as_posix()
  if self.written+len(data)>self.cap:raise ValueError('Analysis delta storage cap exceeded before writing')
  if path.exists():raise ValueError('Refusing to replace an existing candidate artifact: '+str(path))
  path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);self.written+=len(data)
  item={'path':rel,'bytes':len(data),'sha256':sha_bytes(data),'delivery':delivery}
  if delivery=='r2':item.update(public_key=self.prefix+'/'+rel,public_url=self.origin+'/'+self.prefix+'/'+rel)
  else:item['pages_path']='data/'+rel
  self.files.append(item);return item
 def projection(self,lane,stem,rows,old,serializer=compact):
  raw=serializer(rows);h=sha_bytes(raw)
  if old and h==old['sha256']:
   self.reused.append({'lane':lane,'artifact':stem,'sha256':h,'gzip_url':old.get('gzipFile')})
   return {'rawBytes':len(raw),'rawSha256':h,'gzipBytes':old['gzipBytes'],'gzipSha256':old['gzipSha256'],'reused':True}
  compressed=gzip.compress(raw,compresslevel=9,mtime=0);self.put(self.root/lane/(stem+'.json.gz'),compressed)
  return {'rawBytes':len(raw),'rawSha256':h,'gzipBytes':len(compressed),'gzipSha256':sha_bytes(compressed),'reused':False}
 def manifest(self,lane,manifest):
  path=self.root/lane/'manifest.json';data=compact(manifest)
  if not path.exists():return self.put(path,data,'pages')
  # The established builder creates this small candidate manifest before final
  # inheritance. The enclosing build requires an initially empty output tree.
  if path.stat().st_size>1048576 or any(f['path']==lane+'/manifest.json' for f in self.files):raise ValueError('Unexpected existing manifest')
  if self.written+len(data)>self.cap:raise ValueError('Analysis delta storage cap exceeded')
  path.write_bytes(data);self.written+=len(data)
  item={'path':lane+'/manifest.json','bytes':len(data),'sha256':sha_bytes(data),'delivery':'pages','pages_path':'data/'+lane+'/manifest.json'}
  self.files.append(item);return item

def inherited_artifact(lane,entry,old_manifest):
 entry=copy.deepcopy(entry)
 # v1 context entries are Pages-relative; retain their actual previous release.
 for field in ('file','gzipFile'):
  if entry.get(field) and not str(entry[field]).startswith('http'):
   base=old_manifest.get('assetBaseUrl')
   if base:entry[field]=base.rstrip('/')+'/'+Path(entry[field]).name
 return entry

def decode_projection(rows,schema,codes):
 result=[]
 for row in rows:
  item={}
  for field,value in zip(schema,row):
   if field.endswith('Code'):value=codes[field[:-4]][value]
   elif field=='exclusionReasonCodes':value=[codes['exclusionReason'][i] for i in value]
   item[field]=value
  result.append(item)
 return result

def old_rows(lane,entry):
 p=SOURCE/lane/Path(urlparse(entry['file']).path).name
 raw=p.read_bytes() if p.exists() else gzip.decompress(p.with_suffix(p.suffix+'.gz').read_bytes())
 if sha_bytes(raw)!=entry['sha256']:raise ValueError('Inherited artifact pin mismatch: '+str(p))
 return json.loads(raw)

def finalize_manifest(writer,lane,manifest,old,quality_pin):
 for key,entry in list(manifest.get('artifacts',{}).items()):
  previous=old.get('artifacts',{}).get(key)
  if previous and entry['sha256']==previous['sha256']:
   manifest['artifacts'][key]=inherited_artifact(lane,previous,old)
 manifest.setdefault('inputs',{})['qualityView']=quality_pin
 manifest['qualityProjection']={'qualityManifestSha256':quality_pin['sha256'],'baseRecordsRetained':True,'originalSourceFieldsPreserved':True,'fullDetailCopyWritten':False,'delivery':'changed_gzip_only_inherited_immutable_artifacts'}
 manifest['generatedAt']='2026-10-07T00:00:00Z'
 # Describe only real retained/uploaded objects, not uncreated raw files.
 manifest['payloads']={}
 manifest['delivery']={'pagesFiles':['manifest.json'],'immutablePrefix':writer.prefix+'/'+lane,'r2OnlyPaths':[Path(f['path']).name for f in writer.files if f['delivery']=='r2' and f['path'].startswith(lane+'/')],'cacheControl':'public, max-age=31536000, immutable','inheritedImmutableArtifacts':True,'gzipOnly':True}
 writer.manifest(lane,manifest)
 return manifest

def refresh_catalog_input(manifest,map_manifest_pin):
 inputs=manifest.setdefault('inputs',{})
 if 'canonicalManifest' in inputs:inputs['baseCanonicalManifest']=copy.deepcopy(inputs['canonicalManifest'])
 inputs['canonicalManifest']=copy.deepcopy(map_manifest_pin)
 catalog=manifest.get('sources',{}).get('ufoCatalog')
 if catalog:
  catalog['baseCanonicalWebManifest']={'path':catalog.get('canonicalWebManifest'),'sha256':catalog.get('canonicalWebManifestSha256'),'hashRole':catalog.get('hashRole')}
  catalog.update(canonicalWebManifest=map_manifest_pin['path'],canonicalWebManifestBytes=map_manifest_pin['bytes'],canonicalWebManifestSha256=map_manifest_pin['sha256'],sha256=map_manifest_pin['sha256'],hashRole='effective_guarded_quality_map_and_summary_manifest',releaseId='quality-20261007')

def build_v2(view,map_root,writer,quality_pin,map_manifest_pin):
 from scripts import build_analysis_v2_artifacts as v2
 from scripts import build_analysis_geography_binary_v1 as binary
 lane='analysis_v2';old=read_json(SOURCE/lane/'manifest.json');m=copy.deepcopy(old);release='quality-analysis-v2-20261007'
 spatial,pairs,neighbors_source=v2.build_ufo_spatial_projections(map_root)
 geography,geography_source=v2.build_ufo_geography_projection(map_root,SOURCE)
 effective={str(row['event_id']):row for row in view.iter_summaries() if str(row['event_id']) in view.decisions}
 for row in geography:
  event=effective.get(str(row['eventId']))
  if event and event.get('coordinate_source') in GENERALIZED_SOURCES:row['coordinateEvidenceCode']='generalized_coordinates'
 geography_source['policy']['qualityReferenceCoordinateClasses']='Reviewed locality, nominal grid and bounded source reference roles remain generalized for analysis; source coordinate eligibility is not promoted.'
 config,config_pairs,config_source,config_pair_source=v2.build_ufo_configuration_projections(map_root,spatial)
 crop=decode_projection(old_rows(lane,old['artifacts']['cropContextReadiness']),old['artifacts']['cropContextReadiness']['rowSchema'],old['codes']['cropContextReadiness'])
 animal=decode_projection(old_rows(lane,old['artifacts']['animalContextReadiness']),old['artifacts']['animalContextReadiness']['rowSchema'],old['codes']['animalContextReadiness'])
 context,context_source=v2.build_context_ufo_neighbor_projection(spatial,crop,animal)
 updates={'ufoSpatialPoints':(spatial,v2.UFO_SPATIAL_POINT_ROW_SCHEMA),'ufoGeography':(geography,v2.UFO_GEOGRAPHY_ROW_SCHEMA),'ufoConfigurationPoints':(config,v2.UFO_CONFIGURATION_POINT_ROW_SCHEMA),'contextUfoNeighbors':(context,v2.CONTEXT_UFO_NEIGHBOR_ROW_SCHEMA),'ufoPointNeighbors':(pairs,v2.NEIGHBOR_ROW_SCHEMA),'ufoConfigurationNeighbors':(config_pairs,v2.NEIGHBOR_ROW_SCHEMA)}
 macroregion_by_event={str(r['eventId']):r['macroregionCode'] for r in geography}
 for key,(rows,schema) in updates.items():
  encoded,codes=v2.encoded_projection(rows,schema) if rows and isinstance(rows[0],dict) else (rows,None)
  if codes is not None:m['codes'][key]=codes
  entry=old['artifacts'][key];stem=Path(urlparse(entry['file']).path).stem
  files=writer.projection(lane,stem,encoded,entry,v2.canonical_json_document)
  declaration=copy.deepcopy(entry);declaration.update(bytes=files['rawBytes'],sha256=files['rawSha256'],gzipBytes=files['gzipBytes'],gzipSha256=files['gzipSha256'],rowCount=len(encoded),releaseId=release+'.'+entry['artifactId'])
  declaration['rowOrdering']=v2.row_ordering_declaration(encoded,schema,entry['rowOrdering']['keyFields'],policy_id=entry['rowOrdering']['policyId'])
  declaration['file']=writer.origin+'/'+writer.prefix+'/'+lane+'/'+stem+'.json';declaration['gzipFile']=declaration['file']+'.gz'
  if key=='ufoGeography' and not files['reused']:
   raw=binary.encode_rows(encoded);gz=gzip.compress(raw,compresslevel=9,mtime=0)
   url=writer.origin+'/'+writer.prefix+'/'+lane+'/'+stem+'.bin'
   writer.put(writer.root/lane/(stem+'.bin.gz'),gz)
   declaration['binary']={'version':1,'format':'ufo_geography_columnar_v1','file':url,'gzipFile':url+'.gz','bytes':len(raw),'gzipBytes':len(gz),'sha256':sha_bytes(raw),'gzipSha256':sha_bytes(gz),'decodedJsonSha256':files['rawSha256'],'decodedCanonicalJsonSha256':sha_bytes(v2.canonical_json_bytes(encoded))}
  m['artifacts'][key]=declaration
 m['sources'].update(ufoPointNeighbors=neighbors_source,ufoGeography=geography_source,ufoConfigurationPoints=config_source,ufoConfigurationNeighbors=config_pair_source,contextUfoNeighbors=context_source)
 m['sources']['ufoSpatialPoints']['counts']={'rows':len(spatial)};m['sources']['ufoSpatialPoints']['readiness']=neighbors_source['readiness']
 m['counts'].update(ufoNeighborEligiblePoints=len(spatial),ufoSpatialPoints=len(spatial),ufoNeighborPairs=len(pairs),ufoGeographyRows=len(geography),ufoGeographyCountryAssigned=geography_source['counts']['countryAssigned'],ufoConfigurationPoints=len(config),ufoConfigurationNeighborPairs=len(config_pairs),contextUfoNeighborRows=len(context),contextObservedNeighborRows=context_source['counts']['observedRows'],contextIndependentObservedRows=context_source['counts']['independentObservedRows'],contextLocationDateClusters=context_source['counts']['locationDateClusters'])
 m['releaseId']=release;m['assetBaseUrl']=writer.origin+'/'+writer.prefix+'/'+lane
 m['dictionaries']['artifactSha256']={k:sha_bytes(v2.canonical_json_bytes(c)) for k,c in sorted(m['codes'].items())};m['dictionaries']['sha256']=sha_bytes(v2.canonical_json_bytes(m['codes']))
 # Finalize artifact inheritance before hashing dependent declarations.
 for key,entry in list(m['artifacts'].items()):
  if entry['sha256']==old['artifacts'][key]['sha256']:m['artifacts'][key]=copy.deepcopy(old['artifacts'][key])
 m['artifactReleases']={k:a['releaseId'] for k,a in m['artifacts'].items()};m['rowOrderingHashes']={k:a['rowOrdering']['sha256'] for k,a in m['artifacts'].items()}
 m['contractHashes'].update(artifactDeclarationsSha256=sha_bytes(v2.canonical_json_bytes(m['artifacts'])),dictionaryCodebooksSha256=m['dictionaries']['sha256'])
 refresh_catalog_input(m,map_manifest_pin)
 finalize_manifest(writer,lane,m,old,quality_pin)
 return m,macroregion_by_event

def build_attribute(lane,details,writer,quality_pin,geography,macroregions,map_manifest_pin):
 path=ROOT/'scripts'/('build_'+lane+'.py');module=adapted_builder(path)
 old=read_json(SOURCE/lane/'manifest.json');by_stem={Path(urlparse(a['file']).path).stem:a for a in old['artifacts'].values()}
 module.quality_detail_paths=details.paths;module.quality_detail_rows=details.get
 module.RELEASE_ID='quality-'+lane.replace('_','-')+'-20261007';module.ASSET_BASE_URL=writer.origin+'/'+writer.prefix+'/'+lane
 def compressed_only(output_root,stem,value):
  result=writer.projection(lane,stem,value,by_stem.get(stem),module.compact_json_bytes)
  result.update(rawPath=Path(output_root)/(stem+'.json'),gzipPath=Path(output_root)/(stem+'.json.gz'))
  return result
 module.write_raw_and_gzip=compressed_only
 geo_entry=geography['artifacts']['ufoGeography']
 module.load_macroregions=lambda *_:(macroregions,{'path':geo_entry['gzipFile'],'bytes':geo_entry['gzipBytes'],'sha256':geo_entry['gzipSha256'],'decodedBytes':geo_entry['bytes'],'decodedSha256':geo_entry['sha256'],'rowCount':geo_entry['rowCount'],'releaseId':geo_entry['releaseId'],'qualityViewSha256':quality_pin['sha256']})
 # Existing build writes only a small manifest/audit; projections use the hook.
 args=argparse.Namespace(detail_root=details.view.base/'event_chunks',geography=writer.root/'analysis_v2/ufo_geography_v1.json.gz',analysis_manifest=writer.root/'analysis_v2/manifest.json',output_root=writer.root/lane,audit_path=writer.root/lane/'build_audit.json')
 if hasattr(module,'DEFAULT_CONFLICT_REPORT'):args.conflict_report=module.DEFAULT_CONFLICT_REPORT
 if hasattr(module,'DEFAULT_RAW_AUDIT'):args.raw_audit=module.DEFAULT_RAW_AUDIT;args.parser_contract=module.DEFAULT_PARSER_CONTRACT
 Path(args.output_root).mkdir(parents=True,exist_ok=True);result=module.build(args)
 if not result.get('ok'):raise ValueError('Established material analysis gates failed: '+lane)
 m=read_json(args.output_root/'manifest.json')
 refresh_catalog_input(m,map_manifest_pin)
 # Finalize only the small manifest created inside this new candidate tree.
 finalize_manifest(writer,lane,m,old,quality_pin)
 audit=args.audit_path;a=read_json(audit);a['effectiveQualityView']=quality_pin;a['manifest']['sha256']=sha_file(args.output_root/'manifest.json');a['manifest']['bytes']=(args.output_root/'manifest.json').stat().st_size
 audit.write_bytes(compact(a));writer.written+=audit.stat().st_size
 return {'lane':lane,'counts':m['counts'],'status':m['readiness']['status'],'builder_sha256':sha_file(path),'source_input_substitutions':2,'classifiers_changed':False}

def estimate(source=SOURCE):
 total=0;rows=[]
 for lane in ('analysis_v1','analysis_v2')+LANES:
  m=read_json(Path(source)/lane/'manifest.json');gz=sum(a['gzipBytes'] for a in m['artifacts'].values())
  if lane=='analysis_v2':gz+=m['artifacts']['ufoGeography']['binary']['gzipBytes']
  rows.append({'lane':lane,'worst_case_existing_gzip_bytes':gz,'manifest_bytes':(Path(source)/lane/'manifest.json').stat().st_size});total+=gz+rows[-1]['manifest_bytes']
 return {'schema':'quality-analysis-layout-estimate-v1','destination':str(OUTPUT),'gzip_only':True,'unchanged_artifacts_reused':True,'existing_gzip_upper_baseline_bytes':total,'proposed_cap_bytes':CAP,'expected_growth_mib':round(total/1048576,3),'full_corpus_copy':False,'analysis_database_copy':False,'lanes':rows,'cleanup':'Candidate becomes canonical release delta after parent validation/publication; previous validated release remains rollback. No duplicated raw data.'}

def build(args):
 if Path(args.output).exists() and any(Path(args.output).iterdir()):raise ValueError('Analysis candidate output must be new or empty')
 from scripts.build_quality_map_release import load_quality_view,effective_detail_from_source_row
 view=load_quality_view(Path(args.quality_manifest));quality_pin={'path':str(Path(args.quality_manifest).resolve()),'bytes':Path(args.quality_manifest).stat().st_size,'sha256':sha_file(args.quality_manifest),'policy':view.manifest['policy']}
 map_receipt=Path(args.map_root)/'map_release_receipt.json'
 if not map_receipt.is_file():raise ValueError('Map release must be sealed before analysis')
 sealed=read_json(map_receipt)
 if sealed['qualityManifestSha256']!=quality_pin['sha256']:raise ValueError('Map and analysis quality views differ')
 sealed_files={f['path']:f for f in sealed['files']}
 for name in ('points_meta.json','points.bin','canonical_web_manifest.json'):
  p=Path(args.map_root)/name;pin=sealed_files[name]
  if p.stat().st_size!=pin['bytes'] or sha_file(p)!=pin['sha256']:raise ValueError('Map input pin mismatch: '+name)
 point_metadata=read_json(Path(args.map_root)/'points_meta.json')
 if point_metadata['row_count']!=view.validation['effective_mapped'] or point_metadata.get('qualityManifestSha256')!=quality_pin['sha256']:raise ValueError('Packed points do not match the effective quality census')
 map_manifest=Path(args.map_root)/'canonical_web_manifest.json'
 map_manifest_pin={'path':args.origin.rstrip('/')+'/releases/quality-20261007/map_delta/canonical_web_manifest.json','bytes':map_manifest.stat().st_size,'sha256':sha_file(map_manifest),'hashRole':'effective_guarded_quality_map_and_summary_manifest'}
 writer=DeltaWriter(args.output,args.origin,args.prefix,args.cap)
 geography,regions=build_v2(view,Path(args.map_root),writer,quality_pin,map_manifest_pin)
 from scripts.build_analysis_witness_count_v1 import RAW_FIELD_NAME
 details=SharedEffectiveDetails(view,effective_detail_from_source_row,RAW_FIELD_NAME)
 results=[]
 for lane in LANES:
  print('Building '+lane,flush=True);results.append(build_attribute(lane,details,writer,quality_pin,geography,regions,map_manifest_pin))
 context=read_json(SOURCE/'analysis_v1/manifest.json');old=copy.deepcopy(context);context['releaseId']='quality-analysis-context-v1-20261007'
 catalog=context['sources']['ufoCatalog'];catalog.update(mappedRowCount=view.validation['effective_mapped'],qualityManifestSha256=quality_pin['sha256'],effectiveCatalogRole='guarded_quality_view_over_unchanged_canonical_base')
 refresh_catalog_input(context,map_manifest_pin)
 finalize_manifest(writer,'analysis_v1',context,old,quality_pin)
 # Inventory every actual file, including established small build audits.
 declared={f['path']:f for f in writer.files}
 for p in sorted(writer.root.rglob('*')):
  if not p.is_file():continue
  rel=p.relative_to(writer.root).as_posix()
  if rel not in declared:declared[rel]={'path':rel,'bytes':p.stat().st_size,'sha256':sha_file(p),'delivery':'retained_analysis_receipt'}
 receipt={'schema':'quality-analysis-release-receipt-v1','quality_manifest':quality_pin,'map_receipt_sha256':sha_file(map_receipt),'effective_catalog_manifest':map_manifest_pin,'map_points':{'path':str(Path(args.map_root)/'points.bin'),'sha256':sha_file(Path(args.map_root)/'points.bin')},'map_points_metadata':{'path':str(Path(args.map_root)/'points_meta.json'),'sha256':sha_file(Path(args.map_root)/'points_meta.json')},'files':list(declared.values()),'bytes':sum(x['bytes'] for x in declared.values()),'storage_cap_bytes':args.cap,'reuse':writer.reused,'builders':results,'source_chunks_read_once':details.chunks_checked,'canonical_source_mutated':False,'full_detail_copy_created':False,'classifiers_changed':False,'scientific_policy':'New locality/grid/observer reference points remain generalized; existing exact source-coordinate/date eligibility gates remain unchanged.','retention':{'canonical_artifact':'This analysis delta and its manifest-pinned inherited immutable artifacts after parent validation/publication.','rollback':'Previous validated analysis release remains unchanged until the parent designates its retained rollback.','rebuild':'py -3 scripts/build_quality_analysis_release.py --build --output <new empty candidate directory>','superseded_staging':[],'new_files_over_100_mib':[]}}
 if receipt['bytes']>args.cap:raise ValueError('Final analysis release exceeds approved cap')
 receipt_path=writer.root/'analysis_release_receipt.json';receipt_path.write_bytes(compact(receipt));print(json.dumps({'receipt':str(receipt_path),'bytes':receipt['bytes'],'reused_artifacts':len(writer.reused)}))
 return receipt

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');p.add_argument('--quality-manifest',type=Path,default=QUALITY);p.add_argument('--map-root',type=Path,default=MAP);p.add_argument('--output',type=Path,default=OUTPUT);p.add_argument('--origin',default=ORIGIN);p.add_argument('--prefix',default=PREFIX);p.add_argument('--cap',type=int,default=CAP);args=p.parse_args()
 if args.build:build(args)
 else:print(json.dumps(estimate(),indent=2))
if __name__=='__main__':main()
