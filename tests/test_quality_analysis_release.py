"""Focused source-role, sparse delivery and builder adaptation controls."""
import ast
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts import build_quality_analysis_release as q
from scripts.analysis_reporting_delay import normalize_reporting_delay

class QualityAnalysisTests(unittest.TestCase):
 def test_all_six_algorithms_have_exact_input_adapter_contract(self):
  for lane in q.LANES:
   m=q.adapted_builder(q.ROOT/'scripts'/('build_'+lane+'.py'))
   self.assertTrue(callable(m.build))
   self.assertIn('quality_detail_rows',m.build.__code__.co_names)
   self.assertIn('quality_detail_paths',m.build.__code__.co_names)

 def test_source_adapter_contract_drift_is_detectable(self):
  tree=ast.parse("def build(args):\n chunk_paths=sorted(detail_root.glob('changed*.json'))\n rows=json.loads(chunk_path.read_text(encoding='utf-8'))\n")
  adapter=q.DetailInputTransformer();adapter.visit(tree)
  self.assertEqual((adapter.paths,adapter.rows),(0,1))

 def test_precise_day_downgrade_invalidates_computed_delay(self):
  before=normalize_reporting_delay('1989-11-14','exact_day','1989-11-15','')
  after=normalize_reporting_delay('1989-11-14','approximate','1989-11-15','')
  self.assertTrue(before.typed);self.assertFalse(after.typed)
  self.assertIsNone(after.delay_days)
  self.assertEqual(after.status,'occurrence_precision_incompatible')

 def test_unchanged_projection_reuses_existing_immutable_payload(self):
  rows=[[0,123,1]];raw=q.compact(rows)
  old={'sha256':q.sha_bytes(raw),'gzipSha256':'a'*64,'gzipBytes':100,'gzipFile':'https://example.invalid/old.json.gz'}
  with tempfile.TemporaryDirectory() as d:
   w=q.DeltaWriter(d,cap=1000);result=w.projection('lane','same',rows,old)
   self.assertTrue(result['reused']);self.assertEqual(w.files,[])
   self.assertEqual(list(Path(d).iterdir()),[])

 def test_changed_projection_writes_only_gzip_with_decoded_hash(self):
  with tempfile.TemporaryDirectory() as d:
   w=q.DeltaWriter(d,origin='https://example.invalid',cap=1000)
   rows=[[0,123,2]];result=w.projection('lane','new',rows,None)
   self.assertFalse(result['reused']);p=Path(d)/'lane/new.json.gz'
   self.assertEqual(gzip.decompress(p.read_bytes()),q.compact(rows))
   self.assertFalse(p.with_suffix('').exists())
   self.assertEqual(result['rawSha256'],hashlib.sha256(q.compact(rows)).hexdigest())
   self.assertEqual(w.files[0]['public_key'],'releases/quality-20261007/analysis_delta/lane/new.json.gz')

 def test_storage_cap_rejects_before_write(self):
  with tempfile.TemporaryDirectory() as d:
   w=q.DeltaWriter(d,cap=1)
   with self.assertRaisesRegex(ValueError,'storage cap'):w.put(Path(d)/'new.bin',b'xx')
   self.assertEqual(list(Path(d).iterdir()),[])

 def test_compact_source_keeps_consumed_raw_evidence_without_narrative_copy(self):
  raw={'event_id':1,'source':'nuforc','date_precision':'approximate','sort_date_iso':'1989-11-14','description':'full account','raw_fields':{'Color':'red','No. of Witnesses':'2','Narrative':'source narrative'},'raw_source_row':{'LATITUDE':'1','LONGITUDE':'2','DESCRIPTION':'source narrative'}}
  r=q.compact_source_record(raw,'No. of Witnesses')
  self.assertEqual(r['raw_fields'],{'Color':'red','No. of Witnesses':'2'})
  self.assertEqual(r['raw_source_row'],{'LATITUDE':'1','LONGITUDE':'2'})
  self.assertEqual(r['date_precision'],'approximate');self.assertEqual(r['sort_date_iso'],'1989-11-14')
  self.assertNotIn('description',r);self.assertEqual(raw['description'],'full account')

 def test_reference_roles_cannot_be_promoted_to_source_coordinates(self):
  self.assertNotIn('raw_latlong',q.GENERALIZED_SOURCES)
  for value in ('source_account_city_reference','source_grid_reference','reviewed_observer_installation_reference','reviewed_source_coordinates'):
   self.assertIn(value,q.GENERALIZED_SOURCES)

 def test_freshness_advertises_effective_manifest_and_preserves_base_pin(self):
  old={'path':'base.json','sha256':'a'*64};current={'path':'effective.json','bytes':12,'sha256':'b'*64}
  m={'inputs':{'canonicalManifest':old},'sources':{'ufoCatalog':{'canonicalWebManifest':'base.json','canonicalWebManifestSha256':'a'*64,'sha256':'a'*64,'hashRole':'served_catalog_manifest'}}}
  q.refresh_catalog_input(m,current)
  self.assertEqual(m['inputs']['canonicalManifest']['sha256'],'b'*64)
  self.assertEqual(m['inputs']['baseCanonicalManifest']['sha256'],'a'*64)
  self.assertEqual(m['sources']['ufoCatalog']['sha256'],'b'*64)
  self.assertEqual(m['sources']['ufoCatalog']['baseCanonicalWebManifest']['sha256'],'a'*64)

if __name__=='__main__':unittest.main()
