import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nutrition_engine.ingredient_matcher import IngredientMatcher
from scripts.prepare_database import build_database
from src.ai import PredictionError
from src.common import write_csv
from fixtures.make_fixture import write_png


def item(name='Rice, white, long-grain, cooked', state='cooked', grams=150, estimate=None):
    return {'name': name, 'name_th': '', 'state': state, 'grams': grams,
            'evidence': 'visible', 'confidence': 0.8, 'uncertainty': 'Image estimate',
            'estimated_per_100g': estimate or {'kcal': 100, 'protein_g': 2, 'carbs_g': 20, 'fat_g': 1}}


def prediction(items=None):
    return {'dish_name': 'test meal', 'ingredients': items or [item()]}


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        sources = self.root / 'sources'
        sources.mkdir()
        rows = [dict(source='TEST', release='1', fdc_id='1', name_en='Rice, white, long-grain, cooked',
                     kcal_100g=130, protein_g_100g=2.7, carbs_g_100g=28, fat_g_100g=0.3),
                dict(source='TEST', release='1', fdc_id='2', name_en='Mystery food',
                     kcal_100g='', protein_g_100g=0, carbs_g_100g=0, fat_g_100g=0)]
        write_csv(sources / 'nouriva_usda_food_nutrition.csv', list(rows[0]), rows)
        db = self.root / 'ingredients.sqlite'
        build_database(sources, db)
        self.matcher = IngredientMatcher(db)
        self.addCleanup(self.matcher.close)

    def module(self, name):
        try:
            return __import__('candidate.' + name, fromlist=['*'])
        except ModuleNotFoundError:
            self.fail('Candidate feature is not implemented: ' + name)

    def test_database_values_override_ai_estimates_and_use_grams(self):
        result = self.module('pipeline').calculate([item()], self.matcher)
        self.assertEqual(result['status'], 'COMPLETE_DATABASE')
        self.assertEqual(result['nutrients']['kcal'], 195)
        self.assertAlmostEqual(result['nutrients']['protein_g'], 4.05)
        self.assertEqual(result['ingredients'][0]['nutrient_sources']['kcal'], 'DATABASE')

    def test_unknown_identity_uses_explicit_ai_fallback(self):
        result = self.module('pipeline').calculate([item('unseen special sauce', 'unspecified', 50)], self.matcher)
        self.assertEqual(result['status'], 'COMPLETE_WITH_ESTIMATES')
        self.assertEqual(result['nutrients']['kcal'], 50)
        self.assertEqual(result['ingredients'][0]['nutrient_sources']['kcal'], 'AI_ESTIMATE')
        self.assertEqual(result['database_mass_coverage'], 0)

    def test_raw_cooked_mismatch_cannot_use_database_reference(self):
        result = self.module('pipeline').calculate([item(state='raw')], self.matcher)
        self.assertEqual(result['ingredients'][0]['match_reason'], 'name_state_conflict')
        self.assertEqual(result['nutrients']['kcal'], 150)
        self.assertEqual(result['status'], 'COMPLETE_WITH_ESTIMATES')

    def test_missing_field_fallback_preserves_real_database_zero(self):
        result = self.module('pipeline').calculate([item('Mystery food', 'unspecified', 100)], self.matcher)
        row = result['ingredients'][0]
        self.assertEqual(result['status'], 'COMPLETE_WITH_ESTIMATES')
        self.assertEqual(result['nutrients'], {'kcal': 100, 'protein_g': 0, 'carbs_g': 0, 'fat_g': 0})
        self.assertEqual(row['nutrient_sources']['protein_g'], 'DATABASE')
        self.assertEqual(row['nutrient_sources']['kcal'], 'AI_ESTIMATE')

    def test_null_fallback_stays_missing_and_cannot_be_scored(self):
        estimate = {'kcal': None, 'protein_g': 1, 'carbs_g': 2, 'fat_g': 3}
        result = self.module('pipeline').calculate([item('unknown ingredient', 'unspecified', 100, estimate)], self.matcher)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertIsNone(result['nutrients'])
        self.assertIsNone(result['partial_nutrients']['kcal'])

    def test_ensemble_union_and_contributions_average_both_members(self):
        p1 = prediction([item(grams=100), item('unknown sauce', 'unspecified', 20)])
        p2 = prediction([item(grams=200)])
        result = self.module('pipeline').combine([p1, p2], self.matcher)
        self.assertEqual(result['nutrition']['nutrients']['kcal'], 205)
        self.assertEqual(result['nutrition']['total_estimated_mass_g'], 160)
        sauce = next(r for r in result['prediction']['ingredients'] if r['name'] == 'unknown sauce')
        self.assertEqual(sauce['grams'], 10)
        self.assertEqual(result['merge_trace'][1]['support_count'], 1)
        self.assertEqual(len(result['members']), 2)

    def test_ensemble_never_silently_accepts_one_member(self):
        with self.assertRaises(ValueError):
            self.module('pipeline').combine([prediction()], self.matcher)

    def test_zero_mass_missing_member_does_not_hide_ai_estimate_source(self):
        absent = item('unknown sauce', 'unspecified', 0,
                      {'kcal': None, 'protein_g': None, 'carbs_g': None, 'fat_g': None})
        present = item('unknown sauce', 'unspecified', 100)
        result = self.module('pipeline').combine([prediction([absent]), prediction([present])], self.matcher)
        self.assertEqual(result['nutrition']['nutrients']['kcal'], 50)
        self.assertEqual(result['nutrition']['status'], 'COMPLETE_WITH_ESTIMATES')
        self.assertEqual(result['nutrition']['database_mass_coverage'], 0)

    def test_schema_rejects_impossible_and_nonfinite_fallback(self):
        schema = self.module('schema')
        for value in [-1, float('nan'), True, 1001]:
            p = prediction()
            p['ingredients'][0]['estimated_per_100g']['kcal'] = value
            with self.assertRaises(PredictionError):
                schema.validate_prediction(p)

    def test_transport_preserves_fallback_and_never_sends_truth_or_filename(self):
        client_module = self.module('client')
        image = self.root / 'private-label-999.png'
        write_png(image, 1)
        payloads = []

        def transport(payload, headers, timeout, url):
            payloads.append(payload)
            return {'id': 'test', 'choices': [{'message': {'content': json.dumps(prediction())}}],
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}}

        client = client_module.CandidateClient({}, self.matcher, transport=transport)
        with patch.dict(os.environ, {'GROQ_API_KEY': 'TEST_SECRET'}):
            result = client.chat('model', image, 'candidate', temperature=0.7)
            client.chat('model', image, 'candidate', temperature=0.7)
        self.assertEqual(result['ingredients'][0]['estimated_per_100g']['kcal'], 100)
        self.assertEqual(payloads[0]['messages'], payloads[1]['messages'])
        wire = json.dumps(payloads)
        self.assertNotIn('private-label-999', wire)
        self.assertNotIn('total_calories', wire)
        self.assertNotIn('TEST_SECRET', json.dumps(client.events))
        self.assertEqual(client.events[0]['total_tokens'], 150)


if __name__ == '__main__':
    unittest.main()
