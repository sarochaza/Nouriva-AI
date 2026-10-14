import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from src.ai import APIError, GroqClient
from src.common import load_json, save_json
from src.dataset import prepare_dataset
from fixtures.make_fixture import make_fixture, write_png
from candidate.run import load_config, run


class ClientHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / 'sample.png'
        write_png(self.image, 1)

    def test_authenticated_requests_identify_the_application(self):
        with patch.dict(os.environ, {'GROQ_API_KEY': 'SECRET_TEST_KEY'}):
            headers = GroqClient({}).headers()
        self.assertTrue(headers.get('User-Agent'), 'API requests need an explicit application identity')
        self.assertFalse(headers['User-Agent'].lower().startswith('python-urllib'))
        self.assertEqual(headers.get('Accept'), 'application/json')
        self.assertEqual(headers['Authorization'], 'Bearer SECRET_TEST_KEY')

    def test_cloudflare_response_is_classified_and_closed(self):
        stream = io.BytesIO(b'error code: 1010')
        failure = urllib.error.HTTPError('https://api.groq.com', 403, 'Forbidden', {}, stream)
        self.addCleanup(failure.close)

        def transport(*args):
            raise failure

        client = GroqClient({}, transport=transport)
        with patch.dict(os.environ, {'GROQ_API_KEY': 'SECRET_TEST_KEY'}):
            with self.assertRaises(APIError) as caught:
                client.chat('vision', self.image, 'single')
        self.assertIn('CLOUDFLARE_1010', str(caught.exception))
        self.assertEqual(client.events[0]['provider_error_code'], 'CLOUDFLARE_1010')
        self.assertTrue(stream.closed)
        self.assertEqual(len(client.events), 1)

    def test_permission_error_code_is_retained_without_echoing_keys(self):
        body = {'error': {'code': 'model_permission_blocked_project', 'type': 'permissions_error',
                          'message': 'Unsafe server echo: SECRET_TEST_KEY'}}
        failure = urllib.error.HTTPError('https://api.groq.com', 403, 'Forbidden', {},
                                        io.BytesIO(json.dumps(body).encode()))
        self.addCleanup(failure.close)

        def transport(*args):
            raise failure

        client = GroqClient({}, transport=transport)
        with patch.dict(os.environ, {'GROQ_API_KEY': 'SECRET_TEST_KEY'}):
            with self.assertRaises(APIError) as caught:
                client.chat('vision', self.image, 'single')
        self.assertIn('model_permission_blocked_project', str(caught.exception))
        self.assertNotIn('SECRET_TEST_KEY', str(caught.exception) + json.dumps(client.events))


class RunAccessFailureTests(unittest.TestCase):
    def test_real_permission_failure_stops_after_one_saved_trial(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = make_fixture(root / 'dataset')
            prepared = root / 'prepared'
            prepare_dataset(fixture, prepared, 5, 1, mock=True)
            manifest = load_json(prepared / 'manifest.json')
            manifest['mode'] = 'REAL'
            save_json(prepared / 'manifest.json', manifest)
            config = load_config()
            for status in (401, 403):
                with self.subTest(http_status=status):
                    calls = []

                    class DeniedClient:
                        def __init__(self):
                            self.events = []
                            self.on_event = None

                        def chat(self, model, *args, **kwargs):
                            calls.append(model)
                            self.events.append({'model': model, 'status': 'API_ERROR',
                                                'http_status': status, 'total_tokens': None})
                            raise APIError('HTTP_' + str(status))

                    directory = root / ('run_' + str(status))
                    count = run(prepared, config, directory, mock=False, client_factory=DeniedClient)
                    self.assertEqual(count, 1, 'Permanent access denial must not repeat for all planned trials')
                    self.assertEqual(len(calls), 1)
                    records = list((directory / 'records').rglob('*.json'))
                    self.assertEqual(len(records), 1)
                    self.assertEqual(load_json(records[0])['status'], 'FAILED')
                    self.assertEqual(load_json(directory / 'run_status.json')['status'], 'STOPPED_ACCESS_DENIED')


if __name__ == '__main__':
    unittest.main()
