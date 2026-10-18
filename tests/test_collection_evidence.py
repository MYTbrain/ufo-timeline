import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location("collection_builder", Path(__file__).resolve().parents[1]/"scripts/build_collection_evidence.py")
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
class CollectionEvidenceTest(unittest.TestCase):
 def test_generic_review_text_never_becomes_collection_target(self):
  material, actions, _ = builder.codes({"action":"Retrieved narrative explicitly reports occupants/entities taking, collecting or examining named soil/plant material; claim classification only, not confirmation.", "dataset_excerpt":"The witness picked flowers beside a garden."})
  self.assertEqual(material,["unspecified"]); self.assertEqual(actions,["unspecified"])
 def test_negated_removal_stays_examination(self):
  materials, actions, _ = builder.codes({"target":"soil", "action":"A figure examined soil. No removed sample was seen."})
  self.assertEqual(materials,["soil"]); self.assertEqual(actions,["examining"])
 def test_context_mention_not_material(self):
  materials, _, _ = builder.codes({"target":"stones", "action":"A figure collects stones beside flowers and trees."})
  self.assertEqual(materials,["minerals"])
 def test_no_invented_partial_day(self):
  start,end = builder.date_bounds({"date_iso":"1954-01-01","date_precision":"year"})
  self.assertEqual(end-start,364)
  self.assertEqual(builder.date_bounds({"date_iso":"1954-01-01","date_precision":"approximate"}),(None,None))
 def test_region_codes_not_misreported_as_country(self):
  country,basis = builder.country({"raw_source_row":{"key_vals/Country":"EU"},"location_raw":"Paris, FRA, EU"})
  self.assertEqual(country,"France"); self.assertEqual(basis,"explicit_location_token")
  self.assertEqual(builder.country({"country":"SA","location_raw":"Unknown, SA"})[0],"Unknown / unresolved")
 def test_native_country_code_does_not_use_wrong_iso_convention(self):
  self.assertEqual(builder.country({"source":"ufocat","country":"CN","location_raw":"ATIKOKAN, ON, CN"})[0],"Canada")
  self.assertEqual(builder.country({"source":"mufon","country":"CN","location_raw":"Beijing"})[0],"China")
 def test_public_sources_only(self):
  self.assertEqual(builder.safe_url("C:/Users/private/report.pdf"),"")
  self.assertEqual(builder.safe_url("javascript:alert(1)"),"")
  self.assertEqual(builder.safe_url("https://nuforc.org/sighting/?id=198990"),"https://nuforc.org/sighting/?id=198990")
if __name__ == "__main__": unittest.main()
