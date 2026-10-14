import copy
import importlib
import tempfile
import unittest
from pathlib import Path

from fixtures.make_fixture import make_fixture
from src.common import ROOT, load_json, save_json
from src.dataset import prepare_dataset
from src.ai import APIError


class CandidateRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        ds = make_fixture(self.root / 'dataset')
        self.prepared = self.root / 'prepared'
        prepare_dataset(ds, self.prepared, 5, 1, mock=True)
        self.run_dir = self.root / 'run'

    def module(self, name):
        try:
            return importlib.import_module('candidate.' + name)
        except ModuleNotFoundError:
            self.fail('Candidate feature missing: ' + name)

    def run_mock(self, **kwargs):
        runner = self.module('run')
        return runner.run(self.prepared, runner.load_config(), self.run_dir, mock=True, **kwargs)

    def test_five_images_three_rounds_two_methods_and_45_calls(self):
        self.assertEqual(self.run_mock(), 30)
        report = self.module('evaluate').evaluate(self.run_dir, self.prepared / 'ground_truth.json')
        self.assertEqual(len(report['rows']), 30)
        self.assertEqual(sum(r['http_attempts'] for r in report['rows']), 45)
        self.assertEqual(report['selection']['status'], 'MOCK_NOT_ELIGIBLE')
        self.assertIsNone(report['selection']['selected_method'])
        self.assertTrue((self.run_dir / 'comparison/report.html').exists())

    def test_inference_never_requires_ground_truth_file(self):
        (self.prepared / 'ground_truth.json').unlink()
        self.assertEqual(self.run_mock(rounds=[1], methods=['single']), 5)

    def test_resume_is_idempotent_and_config_is_frozen(self):
        self.run_mock(rounds=[1], methods=['single'])
        path = self.run_dir / 'records/round_1/mock_0000_single.json'
        original = path.read_bytes()
        self.assertEqual(self.run_mock(rounds=[1], methods=['single']), 0)
        self.assertEqual(path.read_bytes(), original)
        runner = self.module('run')
        cfg = runner.load_config()
        cfg['temperature'] = 0.6
        with self.assertRaises(ValueError):
            runner.run(self.prepared, cfg, self.run_dir, mock=True)

    def test_second_member_failure_is_failed_not_single_downgrade(self):
        runner = self.module('run')
        from fixtures.candidate_mock import MockCandidateClient

        class FailSecond(MockCandidateClient):
            def chat(self, *args, **kwargs):
                if len(self.events) == 1:
                    self.events.append({'status': 'API_ERROR', 'model': 'MOCK', 'total_tokens': None})
                    raise APIError('TEST_SECOND_MEMBER_FAILURE')
                return super().chat(*args, **kwargs)

        runner.run(self.prepared, runner.load_config(), self.run_dir, mock=True,
                   rounds=[1], methods=['ensemble2'], client_factory=FailSecond)
        record = load_json(self.run_dir / 'records/round_1/mock_0000_ensemble2.json')
        self.assertEqual(record['status'], 'FAILED')
        self.assertIsNone(record['nutrition'])
        self.assertEqual(len(record['call_metadata']), 2)
        report = self.module('evaluate').evaluate(self.run_dir, self.prepared / 'ground_truth.json')
        self.assertIsNone(report['rows'][1]['kcal_abs_error'])

    def test_retry_retains_attempt_history_and_cost_events(self):
        self.run_mock(rounds=[1], methods=['single'])
        path = self.run_dir / 'records/round_1/mock_0000_single.json'
        record = load_json(path)
        record['status'] = 'FAILED'
        save_json(path, record)
        self.assertEqual(self.run_mock(rounds=[1], methods=['single'], retry_failed=True), 1)
        current = load_json(path)
        self.assertEqual(current['trial_attempt'], 2)
        self.assertEqual(len(current['call_metadata']), 2)
        self.assertEqual(len(list((path.parent / 'history').glob('*.json'))), 1)

    def test_three_member_config_rejected_before_api(self):
        runner = self.module('run')
        cfg = runner.load_config()
        cfg['ensemble_models'] *= 2
        with self.assertRaises(ValueError):
            runner.run(self.prepared, cfg, self.run_dir, mock=True)

    def test_changed_truth_is_rejected_by_evaluator(self):
        self.run_mock(rounds=[1], methods=['single'])
        path = self.prepared / 'ground_truth.json'
        obj = load_json(path)
        obj['records'][0]['kcal'] += 1
        save_json(path, obj)
        with self.assertRaises(ValueError):
            self.module('evaluate').evaluate(self.run_dir, path)


class SelectionTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module('candidate.evaluate')
        except ModuleNotFoundError:
            self.fail('Candidate evaluation feature missing')

    def rows(self, single_error=0.1, ensemble_error=0.3, mode='REAL'):
        rows = []
        for dish in range(5):
            for rnd in range(1, 4):
                for method, error in [('single', single_error), ('ensemble2', ensemble_error)]:
                    row = {'dish_id': 'dish_' + str(dish), 'round': rnd, 'method': method,
                           'status': 'COMPLETE_DATABASE', 'scaled_nutrient_error': error,
                           'ingredient_F1': 0.8, 'kcal_abs_error': error * 100,
                           'http_attempts': 1 if method == 'single' else 2,
                           'mode': mode}
                    rows.append(row)
        return rows

    def test_large_consistent_paired_improvement_selects_candidate(self):
        result = self.module().select_winner(self.rows(), {'mode': 'REAL', 'rounds': 3, 'config': {}},
                                            {'single_model': 'vision', 'ensemble_models': ['vision', 'vision']})
        self.assertEqual(result['selected_method'], 'single')
        self.assertEqual(result['status'], 'SELECTED_FOR_PILOT')
        self.assertEqual(result['paired_dishes'], 5)
        self.assertGreater(result['difference_ci95'][0], 0)

    def test_selection_exports_frozen_implementation_and_prompt_seals(self):
        frozen = {'mode': 'REAL', 'rounds': 3, 'config': {},
                  'code_sha256': {'candidate/pipeline.py': 'frozen-code-hash'},
                  'prompt_sha256': 'frozen-prompt-hash'}
        result = self.module().select_winner(self.rows(), frozen, {})
        self.assertEqual(result['code_sha256'], {'candidate/pipeline.py': 'frozen-code-hash'})
        self.assertEqual(result['prompt_sha256'], 'frozen-prompt-hash')

    def test_equal_errors_produce_no_clear_winner(self):
        result = self.module().select_winner(self.rows(.1, .1), {'mode': 'REAL', 'rounds': 3, 'config': {}}, {})
        self.assertEqual(result['status'], 'NO_CLEAR_WINNER')
        self.assertIsNone(result['selected_method'])

    def test_incomplete_run_cannot_select(self):
        result = self.module().select_winner(self.rows()[:10], {'mode': 'REAL', 'rounds': 3, 'config': {}}, {})
        self.assertEqual(result['status'], 'INSUFFICIENT_DATA')
        self.assertIsNone(result['selected_method'])

    def test_mock_never_selects_despite_perfect_score(self):
        result = self.module().select_winner(self.rows(0, .9, 'MOCK'), {'mode': 'MOCK', 'rounds': 3, 'config': {}}, {})
        self.assertEqual(result['status'], 'MOCK_NOT_ELIGIBLE')
        self.assertIsNone(result['selected_method'])


class SelectedAgentTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module('candidate.analyze')
        except ModuleNotFoundError:
            self.fail('Selected agent reuse feature missing')

    def test_mock_or_no_winner_selection_cannot_become_agent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'selection.json'
            save_json(path, {'mode': 'MOCK', 'status': 'MOCK_NOT_ELIGIBLE', 'selected_method': None})
            with self.assertRaises(ValueError):
                self.module().NutritionAgent(path)

    def test_selected_agent_reuses_calculator_and_checks_database_hash(self):
        runner = importlib.import_module('candidate.run')
        from src.common import sha256
        from fixtures.candidate_mock import MockCandidateClient
        from fixtures.make_fixture import write_png
        config = runner.load_config()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / 'dish.png'
            write_png(image, 1)
            path = root / 'selection.json'
            selection = self.selection(config)
            save_json(path, selection)
            with self.module().NutritionAgent(path) as agent:
                result = agent.analyze(image, client=MockCandidateClient())
            self.assertEqual(result['nutrition']['nutrients']['kcal'], 45.1)
            self.assertEqual(result['method'], 'ensemble2')
            self.assertEqual(len(result['call_metadata']), 2)
            selection['database_sha256'] = 'wrong'
            save_json(path, selection)
            with self.assertRaises(ValueError):
                self.module().NutritionAgent(path)

    def selection(self, config):
        from src.common import sha256
        from candidate.client import build_prompt
        from candidate.schema import VERSION
        from nutrition_engine.ingredient_matcher import IngredientMatcher
        import hashlib
        runner = importlib.import_module('candidate.run')
        matcher = IngredientMatcher(runner.database_path(config), config['source_priority'])
        try:
            prompt_hash = hashlib.sha256(build_prompt(matcher).encode()).hexdigest()
        finally:
            matcher.close()
        code = {str(p.relative_to(ROOT)).replace('\\', '/'): sha256(p)
                for folder in ('candidate', 'src', 'nutrition_engine', 'scripts', 'fixtures', 'evaluation')
                for p in sorted((ROOT / folder).rglob('*.py'))}
        return {'mode': 'REAL', 'status': 'SELECTED_FOR_PILOT', 'selected_method': 'ensemble2',
                'agent_config': config, 'database_sha256': sha256(runner.database_path(config)),
                'code_sha256': code, 'prompt_sha256': prompt_hash, 'prompt_version': VERSION}

    def test_selected_agent_rejects_changed_prompt_or_implementation(self):
        runner = importlib.import_module('candidate.run')
        config = runner.load_config()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'selection.json'
            for field in ('code_sha256', 'prompt_sha256', 'prompt_version'):
                with self.subTest(field=field):
                    selection = self.selection(config)
                    if field == 'code_sha256':
                        selection[field]['candidate/pipeline.py'] = 'changed-calculator'
                    else:
                        selection[field] = 'obsolete-prompt'
                    save_json(path, selection)
                    with self.assertRaises(ValueError):
                        with self.module().NutritionAgent(path):
                            pass


if __name__ == '__main__':
    unittest.main()
