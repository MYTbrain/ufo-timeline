"""Guard and schema regressions for incremental mapping Analysis recovery."""
import copy
import unittest

from scripts.build_mapping_analysis_delta import (
    encode_assignment, patch_macroregions, updated_counts, validate_decisions,
    update_live_denominators,
)


class MappingAnalysisDeltaTests(unittest.TestCase):
    def test_macroregions_translate_each_lane_and_leave_other_cells_unchanged(self):
        for codes in (['unknown', 'europe', 'oceania'], ['oceania', 'unknown', 'europe']):
            rows = [[9, 100, 4, codes.index('unknown')], [12, 101, 8, codes.index('europe')]]
            before = copy.deepcopy(rows)
            changed = patch_macroregions(rows, ['catalogRowIndex', 'eventId', 'valueCode', 'macroregionCode'],
                                         codes, {100: 'oceania'})
            self.assertEqual(changed, 1)
            self.assertEqual(rows[0], before[0][:-1] + [codes.index('oceania')])
            self.assertEqual(rows[1], before[1])

    def test_unsupported_country_does_not_expand_codebook(self):
        codes = {'country': ['known', 'unknown'], 'macroregion': ['europe', 'unknown'],
                 'assignmentSource': ['world_country_polygon'], 'assignmentConfidence': ['high', 'none'],
                 'boundaryStatus': ['inside_country'], 'coordinateEvidence': ['generalized_coordinates', 'source_coordinates']}
        before = copy.deepcopy(codes)
        values, unsupported = encode_assignment(('new-country', 'asia', 'world_country_polygon', 'high', 'inside_country'), codes)
        self.assertEqual(unsupported, 'new-country')
        self.assertEqual(values, [1, 1, 0, 1, 0, 0])
        self.assertEqual(codes, before)

    def test_source_eligibility_cannot_be_changed(self):
        decision = {'event_id': 1, 'accepted': True,
                    'guards': {'coordinate_source': 'raw_latlong'},
                    'set_fields': {'coordinate_source': 'reviewed_original_source_coordinate',
                                   'has_coordinates': True, 'location_precision': 'approximate', 'lat': 10, 'lon': 20}}
        with self.assertRaisesRegex(ValueError, 'precise coordinate eligibility'):
            validate_decisions([decision])
        decision['guards']['coordinate_source'] = 'unresolved'
        decision['set_fields']['location_precision'] = 'exact_coords'
        with self.assertRaisesRegex(ValueError, 'precise coordinate eligibility'):
            validate_decisions([decision])

    def test_counts_include_existing_mapped_correction_without_adding_event(self):
        decisions = {1: {'guards': {'coordinate_source': 'unresolved'},
                         'set_fields': {'coordinate_source': 'reviewed_area_reference'}},
                     2: {'guards': {'coordinate_source': 'geocoded'},
                         'set_fields': {'coordinate_source': 'reviewed_locality_reference'}}}
        actual = updated_counts({'unresolved': 2, 'geocoded': 3, 'raw_latlong': 4}, decisions, 'coordinate_source')
        self.assertEqual(actual, {'unresolved': 1, 'geocoded': 2, 'raw_latlong': 4,
                                 'reviewed_area_reference': 1, 'reviewed_locality_reference': 1})
        self.assertEqual(sum(actual.values()), 9)

    def test_readiness_adds_only_generalized_exclusions_and_is_idempotent(self):
        source_gate = {'gateId': 'ufo_neighbor_source_coordinates', 'inputN': 100,
                       'passedN': 40, 'failedN': 60, 'unknownN': 0}
        v2 = {'sources': {
            'ufoPointNeighbors': {'counts': {'packedRows': 100, 'eligiblePoints': 20},
                'exclusions': {'not_source_provided_coordinate': 60},
                'readiness': {'gates': [copy.deepcopy(source_gate)]}},
            'ufoSpatialPoints': {'counts': {'rows': 20}, 'readiness': {'gates': [copy.deepcopy(source_gate)]}},
            'ufoConfigurationPoints': {'counts': {'packedRows': 100, 'formationRows': 10, 'eligiblePoints': 2},
                'exclusions': {'not_formation_configuration': 90, 'not_source_provided_coordinate': 7},
                'readiness': {'gates': [
                    {'gateId': 'configuration_classification', 'inputN': 100, 'passedN': 10, 'unknownN': 0},
                    {'gateId': 'configuration_source_coordinates', 'inputN': 10, 'passedN': 3, 'unknownN': 0}]}}}}
        update_live_denominators(v2, 100, 12, 4, {'sha256': 'current'})
        self.assertEqual(v2['sources']['ufoPointNeighbors']['counts']['eligiblePoints'], 20)
        self.assertEqual(v2['sources']['ufoPointNeighbors']['exclusions']['not_source_provided_coordinate'], 72)
        config = v2['sources']['ufoConfigurationPoints']
        self.assertEqual(config['counts'], {'packedRows': 112, 'formationRows': 14, 'eligiblePoints': 2})
        self.assertEqual(config['exclusions'], {'not_formation_configuration': 98, 'not_source_provided_coordinate': 11})
        self.assertEqual(config['readiness']['gates'][1]['passedN'], 3)
        once = copy.deepcopy(v2)
        update_live_denominators(v2, 100, 12, 4, {'sha256': 'current'})
        self.assertEqual(v2, once)


if __name__ == '__main__':
    unittest.main()
