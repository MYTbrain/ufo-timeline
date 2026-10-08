"""Portable source-flag precedence, code whitelist, and raw-field provenance tests."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ufocat_source_fields',ROOT/'scripts/audit_ufocat_timezone_source_fields.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class UfocatSourceFieldTests(unittest.TestCase):
    def test_date_warning_supersedes_clock_markers_and_unknowns_fail_closed(self):
        self.assertEqual(audit.flag_class('+='),'date_believed_erroneous')
        self.assertEqual(audit.flag_class("*'"),'publication_date_not_occurrence')
        self.assertEqual(audit.flag_class('.-'),'approximate_date_plusminus_one_or_two_days')
        self.assertEqual(audit.flag_class('*'),'explicit_GMT_date_and_time')
        self.assertEqual(audit.flag_class('.'),'explicit_standard_time')
        self.assertEqual(audit.flag_class('+'),'explicit_one_hour_daylight_time')
        self.assertEqual(audit.flag_class(''),'unspecified_time_scale')
        for value in ['Z','..','0','12','C','I']:
            self.assertEqual(audit.flag_class(value),'undocumented_or_combined_flag_requires_review')

    def test_numeric_code_is_whitelisted_standard_zone_index(self):
        self.assertEqual(int((audit.code('4')-12)*60),-480)
        self.assertEqual(int((audit.code('6')-12)*60),-360)
        self.assertEqual(int((audit.code('12')-12)*60),0)
        self.assertEqual(int((audit.code('21.5')-12)*60),570)
        for value in ['','0','16.5','17.75','1705','44','66','77']:
            self.assertIsNone(audit.code(value))

    def test_source_reopening_rejects_hash_identity_date_and_flag_tampering(self):
        with tempfile.TemporaryDirectory(prefix='ufocat-source-field-fixture-') as folder:
            root=Path(folder);chunk_root=root/'data/canonical_web/event_chunks';chunk_root.mkdir(parents=True)
            source={'TZ':'.','TZONE':'6','TIME':'2130','YEAR':'1952','MO':'07','DAY':'19','REGION':'US','STATE':'MO','PRN':'42','COUNTY':'Example','LOCATION':'Exampletown'}
            event={'event_id':123,'source':'ufocat','source_id':'42','source_row_number':1,'sort_date_iso':'1952-07-19','date_precision':'exact_day','time_raw':'2130','raw_source_row':source}
            path=chunk_root/'chunk_000000.json';raw=json.dumps([event]).encode();path.write_bytes(raw)
            fields=audit.selected_fields(source)
            row={'eventId':123,'source':'ufocat','sourceId':'42','sourceRowNumber':1,'date':'1952-07-19','datePrecision':'exact_day','rawTime':'2130','sourceChunk':path.stem,'sourceChunkPath':str(path),'sourceChunkSha256':hashlib.sha256(raw).hexdigest(),'sourceChunkBytes':len(raw),'detailIndex':0,'rawSourceField':'raw_source_row','fields':fields,'sourceFieldsSha256':hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'flagClass':'explicit_standard_time'}
            self.assertEqual(len(audit.validate_source_fields([row],root)),1)
            for key,value in [('sourceChunkSha256','0'*64),('sourceId','43'),('date','1952-07-20'),('rawTime','2230'),('flagClass','explicit_GMT_date_and_time')]:
                bad=deepcopy(row);bad[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):audit.validate_source_fields([bad],root)
            bad=deepcopy(row);bad['fields']['TZ']='*'
            with self.assertRaises(ValueError):audit.validate_source_fields([bad],root)
            with self.assertRaises(ValueError):audit.validate_source_fields([row,row],root)

if __name__=='__main__':unittest.main()
