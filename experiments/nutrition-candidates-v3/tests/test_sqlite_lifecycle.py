"""Connection lifetime checks that expose Windows temporary-file lock failures."""
import sqlite3
import unittest
from unittest.mock import patch

from scripts.import_reviewed_thai import import_reviewed_thai
from nutrition_engine.portion_conversion import convert_measure
import tests.test_engine as engine_tests
import tests.test_thai_import as thai_tests
from src.common import write_csv


class TrackedConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.explicitly_closed = False

    def close(self):
        super().close()
        self.explicitly_closed = True


class SqliteLifetimeTests(unittest.TestCase):
    setUp = engine_tests.EngineTests.setUp

    def capture_connections(self):
        real_connect = sqlite3.connect
        connections = []

        def connect(*args, **kwargs):
            conn = real_connect(*args, **kwargs, factory=TrackedConnection)
            connections.append(conn)
            return conn

        return connections, connect

    def test_ambiguous_measure_closes_database_before_raising(self):
        connections, connect = self.capture_connections()
        try:
            with patch('nutrition_engine.portion_conversion.sqlite3.connect', side_effect=connect):
                with self.assertRaises(ValueError):
                    convert_measure(self.db, 'missing_food', 'cup', 1)
            self.assertTrue(connections)
            self.assertTrue(all(c.explicitly_closed for c in connections), 'Read connection stays open after an ambiguous measure')
        finally:
            for conn in connections:
                conn.close()

    def test_verified_import_commits_and_closes_database(self):
        row = thai_tests.ThaiImportTests().row()
        path = self.root / 'reviewed.csv'
        write_csv(path, list(row), [row])
        connections, connect = self.capture_connections()
        try:
            with patch('scripts.import_reviewed_thai.sqlite3.connect', side_effect=connect):
                self.assertEqual(import_reviewed_thai(self.db, path), 1)
            self.assertTrue(all(c.explicitly_closed for c in connections), 'Import leaves SQLite file locked')
            check = sqlite3.connect(self.db)
            try:
                self.assertEqual(check.execute('SELECT COUNT(*) FROM foods WHERE source_id="THAI_FCT:2018"').fetchone()[0], 1)
            finally:
                check.close()
        finally:
            for conn in connections:
                conn.close()

    def test_failed_duplicate_import_rolls_back_and_closes_database(self):
        row = thai_tests.ThaiImportTests().row()
        path = self.root / 'duplicate.csv'
        write_csv(path, list(row), [row, row])
        connections, connect = self.capture_connections()
        try:
            with patch('scripts.import_reviewed_thai.sqlite3.connect', side_effect=connect):
                with self.assertRaises(sqlite3.IntegrityError):
                    import_reviewed_thai(self.db, path)
            self.assertTrue(all(c.explicitly_closed for c in connections), 'Failed import leaves SQLite file locked')
            check = sqlite3.connect(self.db)
            try:
                self.assertEqual(check.execute('SELECT COUNT(*) FROM foods WHERE source_id="THAI_FCT:2018"').fetchone()[0], 0)
            finally:
                check.close()
        finally:
            for conn in connections:
                conn.close()

    def test_windows_error_cases_release_all_database_handles(self):
        cases = [engine_tests.EngineTests('test_ambiguous_measure_requires_review'),
                 engine_tests.EngineTests('test_negative_source_nutrient_quarantined_not_zero'),
                 thai_tests.ThaiImportTests('test_verified_thai_name_searchable')]
        for case in cases:
            with self.subTest(test=case.id()):
                connections, connect = self.capture_connections()
                try:
                    result = unittest.TestResult()
                    with patch('sqlite3.connect', side_effect=connect):
                        case.run(result)
                    self.assertTrue(result.wasSuccessful(), str(result.errors) + str(result.failures))
                    self.assertTrue(all(c.explicitly_closed for c in connections),
                                    'Temporary database still has an open connection at cleanup')
                finally:
                    for conn in connections:
                        conn.close()


if __name__ == '__main__':
    unittest.main()
