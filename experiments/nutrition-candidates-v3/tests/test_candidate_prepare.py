import importlib
import tempfile
import unittest
from pathlib import Path
from fixtures.make_fixture import make_fixture
from src.common import load_json


class PreparationTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module('candidate.prepare')
        except ModuleNotFoundError:
            self.fail('Candidate preparation feature missing')

    def test_reuse_requires_same_dataset_and_selected_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ds = make_fixture(root / 'dataset')
            out = root / 'prepared'
            module = self.module()
            module.prepare(ds, out, 5, 1, mock=True)
            before = (out / 'manifest.json').read_bytes()
            module.prepare(ds, out, 5, 1, mock=True)
            self.assertEqual(before, (out / 'manifest.json').read_bytes())
            other = make_fixture(root / 'other')
            with self.assertRaises(ValueError):
                module.prepare(other, out, 5, 1, mock=True)
            manifest = load_json(out / 'manifest.json')
            Path(manifest['images'][0]['image_path']).write_bytes(b'changed')
            with self.assertRaises(ValueError):
                module.prepare(ds, out, 5, 1, mock=True)

    def test_synthetic_fixtures_cannot_be_prepared_as_real(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ds = make_fixture(root / 'dataset')
            with self.assertRaises(ValueError):
                self.module().prepare(ds, root / 'real', 5, 1)


if __name__ == '__main__':
    unittest.main()
