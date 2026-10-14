"""Focused scientific gates on the actual source-reviewed pilot artifact."""
import copy, gzip, importlib.util, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/encounter_enrichment_build_pilot.py"
spec=importlib.util.spec_from_file_location("encounter_enrichment_build_pilot",SCRIPT)
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
PILOT=builder.RESEARCH/"validated/reviewed/evidence.json.gz"

class ScientificPilotGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload=json.loads(gzip.decompress(PILOT.read_bytes()))

    def test_actual_pilot_schema_and_scientific_guards(self):
        self.assertTrue(builder.validate_payload(self.payload))
        self.assertTrue(builder.case_guards(self.payload))

    def test_unverified_civil_clock_cannot_become_utc(self):
        p=copy.deepcopy(self.payload);p['episodes'][0]['time']['utcVerified']=True
        with self.assertRaises(AssertionError):builder.validate_payload(p)

    def test_locality_cannot_become_exact_site(self):
        p=copy.deepcopy(self.payload);p['episodes'][0]['site']['lat']=-29.7
        with self.assertRaises(AssertionError):builder.validate_payload(p)

    def test_relative_day_cannot_receive_invented_calendar_date(self):
        p=copy.deepcopy(self.payload)
        next(e for e in p['episodes'] if e['scope']=='relative_episode')['date']['startIso']='1954-03-02'
        with self.assertRaises(AssertionError):builder.validate_payload(p)

    def test_identity_conflict_cannot_be_promoted(self):
        p=copy.deepcopy(self.payload)
        next(r for r in p['reportLinks'] if r['status']=='candidate')['acceptedForRuntime']=True
        with self.assertRaises(AssertionError):builder.validate_payload(p)

    def test_phenotype_must_use_existing_taxonomy(self):
        p=copy.deepcopy(self.payload);p['entityObservations'][0]['reportedTypes'].append('verified_alien_species')
        with self.assertRaises(AssertionError):builder.validate_payload(p)

    def test_staff_length_is_not_body_height(self):
        p=copy.deepcopy(self.payload)
        for e in p['entityObservations']:
            if e['episodeId']=='episode:wauwatosa':
                for a in e['attributes']:
                    if a['field']=='carried_object_length':a['field']='height'
        with self.assertRaises(AssertionError):builder.case_guards(p)

    def test_different_walton_crews_do_not_inherit_height(self):
        p=copy.deepcopy(self.payload)
        e=next(e for e in p['entityObservations'] if e['episodeId']=='episode:walton' and 'human_like' in e['reportedTypes'])
        e['attributes'].append(dict(field='height',value=5,unit='ft',raw='5 ft',entryId='entry:walton',attribution='explicit_group'))
        with self.assertRaises(AssertionError):builder.case_guards(p)

    def test_refused_hypnosis_not_labelled_performed(self):
        p=copy.deepcopy(self.payload)
        next(e for e in p['episodes'] if e['episodeId']=='episode:pinhal')['recallMethod']='hypnotic'
        with self.assertRaises(AssertionError):builder.case_guards(p)

    def test_invitation_does_not_establish_onboard_transport(self):
        p=copy.deepcopy(self.payload)
        next(e for e in p['episodes'] if e['episodeId']=='episode:hellwig-second')['onboardStatus']='reported'
        with self.assertRaises(AssertionError):builder.case_guards(p)

    def test_room_account_does_not_establish_craft_interior(self):
        p=copy.deepcopy(self.payload)
        next(e for e in p['episodes'] if e['episodeId']=='episode:stalnaker')['onboardStatus']='reported'
        with self.assertRaises(AssertionError):builder.case_guards(p)

if __name__=='__main__':unittest.main()
