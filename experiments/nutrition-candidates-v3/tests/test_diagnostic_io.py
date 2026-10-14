import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from candidate.schema import parse_prediction
from src.ai import GroqClient, PredictionError
from src.common import load_json, save_json
from fixtures.make_fixture import write_png
from tests.test_methods import prediction


class AtomicSaveTests(unittest.TestCase):
    def test_transient_replace_denial_preserves_old_record_until_success(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'record.json'
            save_json(target, {'attempt': 1})
            original_replace = Path.replace
            attempts = []

            def replace(source, destination):
                attempts.append(source)
                self.assertEqual(load_json(target), {'attempt': 1})
                if len(attempts) < 3:
                    raise PermissionError(13, 'sharing violation', str(destination))
                return original_replace(source, destination)

            with patch.object(Path, 'replace', replace), patch('src.common.time.sleep') as sleep:
                save_json(target, {'attempt': 2})
            self.assertEqual(load_json(target), {'attempt': 2})
            self.assertEqual(len(attempts), 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(list(Path(td).iterdir()), [target])

    def test_permanent_denial_is_bounded_and_leaves_original_intact(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'record.json'
            save_json(target, {'attempt': 1})
            with patch.object(Path, 'replace', side_effect=PermissionError(13, 'denied', str(target))) as replace, \
                    patch('src.common.time.sleep'):
                with self.assertRaises(PermissionError):
                    save_json(target, {'attempt': 2})
            self.assertGreater(replace.call_count, 1)
            self.assertLessEqual(replace.call_count, 7)
            self.assertEqual(load_json(target), {'attempt': 1})
            self.assertEqual(list(Path(td).iterdir()), [target])

    def test_other_os_errors_are_not_retried_and_temp_is_removed(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'record.json'
            with patch.object(Path, 'replace', side_effect=OSError(28, 'disk full')) as replace, \
                    patch('src.common.time.sleep') as sleep:
                with self.assertRaises(OSError):
                    save_json(target, {'attempt': 2})
            self.assertEqual(replace.call_count, 1)
            sleep.assert_not_called()
            self.assertEqual(list(Path(td).iterdir()), [])


class PredictionDiagnosticsTests(unittest.TestCase):
    def test_invalid_json_reports_position_without_echoing_content(self):
        with self.assertRaises(PredictionError) as caught:
            parse_prediction('{"SECRET_RAW": ')
        self.assertIn('line 1, column', str(caught.exception))
        self.assertNotIn('SECRET_RAW', str(caught.exception))

    def test_schema_reason_and_usage_are_retained_without_raw_prediction(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / 'dish.png'
            write_png(image, 1)
            value = prediction()
            value['ingredients'][0]['state'] = 'UNSAFE_RAW_RESPONSE_SECRET'

            def transport(*args):
                return {'choices': [{'message': {'content': json.dumps(value)}}],
                        'usage': {'prompt_tokens': 12, 'completion_tokens': 8, 'total_tokens': 20}}

            client = GroqClient({}, transport=transport, prediction_parser=parse_prediction)
            with patch.dict(os.environ, {'GROQ_API_KEY': 'SECRET_TEST_KEY'}):
                with self.assertRaises(PredictionError) as caught:
                    client.chat('vision', image, 'single')
            self.assertIn('preparation state', str(caught.exception))
            event = client.events[0]
            self.assertIn('preparation state', event['validation_error'])
            self.assertEqual(event['total_tokens'], 20)
            self.assertEqual(event['status'], 'PREDICTION_ERROR')
            self.assertEqual(len(client.events), 1)
            self.assertNotIn('UNSAFE_RAW_RESPONSE_SECRET', json.dumps(event) + str(caught.exception))
            self.assertNotIn('SECRET_TEST_KEY', json.dumps(event))

    def test_checkpoint_permission_error_is_not_retried_as_network_failure(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / 'dish.png'
            write_png(image, 1)
            calls = []
            client = GroqClient({'max_retries': 2}, transport=lambda *a: calls.append(a) or
                                {'choices': [{'message': {'content': json.dumps(prediction())}}]})
            checkpoints = []

            def checkpoint():
                checkpoints.append(1)
                if len(checkpoints) == 2:
                    raise PermissionError(13, 'file locked', 'record.json')

            client.on_event = checkpoint
            with patch.dict(os.environ, {'GROQ_API_KEY': 'SECRET_TEST_KEY'}):
                with self.assertRaises(PermissionError):
                    client.chat('vision', image, 'single')
            self.assertEqual(len(calls), 1)
            self.assertNotEqual(client.events[0]['status'], 'API_ERROR')


class SavedDiagnosticsTests(unittest.TestCase):
    def test_probe_saves_schema_failure_and_closes_matcher(self):
        from candidate import check
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            matcher = Mock()
            client = Mock(events=[{'status': 'PREDICTION_ERROR', 'validation_error': 'Invalid confidence'}])
            with patch.object(check, 'ROOT', Path(td)), \
                    patch.object(check, 'IngredientMatcher', return_value=matcher), \
                    patch.object(check, 'CandidateClient', return_value=client), \
                    patch.object(check, 'predict', side_effect=PredictionError('Invalid confidence')), \
                    patch('sys.argv', ['candidate.check', '--probe-image', 'dish.png']), \
                    redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    check.main()
            record = load_json(Path(td) / 'results/setup/real_vision_probe.json')
            self.assertEqual(record['error_type'], 'PREDICTION_ERROR')
            self.assertIn('Invalid confidence', str(caught.exception))
            self.assertEqual(record['call_metadata'], client.events)
            matcher.close.assert_called_once()

    def test_run_saves_file_error_details_without_exception_text(self):
        from candidate.run import load_config, run
        from fixtures.make_fixture import make_fixture
        from fixtures.candidate_mock import MockCandidateClient
        from src.dataset import prepare_dataset

        class FileDenied(MockCandidateClient):
            def chat(self, *args, **kwargs):
                raise PermissionError(13, 'SECRET_DO_NOT_LOG', '/private/user/dish.png')

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prepared = root / 'prepared'
            prepare_dataset(make_fixture(root / 'dataset'), prepared, 5, 1, mock=True)
            run(prepared, load_config(), root / 'run', mock=True,
                rounds=[1], methods=['single'], client_factory=FileDenied)
            record = load_json(root / 'run/records/round_1/mock_0000_single.json')
            self.assertEqual(record['error_type'], 'INTERNAL_ERROR')
            self.assertEqual(record['error_details'], {'errno': 13, 'filename': 'dish.png'})
            self.assertNotIn('SECRET_DO_NOT_LOG', json.dumps(record))
            self.assertNotIn('/private/user', json.dumps(record))


if __name__ == '__main__':
    unittest.main()
