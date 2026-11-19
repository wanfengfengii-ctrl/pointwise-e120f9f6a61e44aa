import json
import unittest
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from issue.publish import seal
from issue.transfer import get_packet
from run_station import describe_range, load_shift, open_center, open_station, record_layout, register_shift


def scenario(case_id, inputs, expected, actual, downstream_expected, downstream_actual, code_paths, oracle):
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id, 'input': inputs, 'expected': expected, 'actual': actual,
        'downstream_expected': downstream_expected, 'downstream_actual': downstream_actual,
        'code_paths': code_paths, 'oracle': oracle,
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def fail_commit_on_insert(db, table):
    if table not in ('packets', 'receipts'):
        raise ValueError(table)
    db.execute('CREATE TABLE commit_permits (permit INTEGER PRIMARY KEY)')
    db.execute('''CREATE TABLE commit_attempts (
        permit INTEGER NOT NULL REFERENCES commit_permits(permit) DEFERRABLE INITIALLY DEFERRED
    )''')
    db.execute(f'''CREATE TRIGGER require_commit_permit AFTER INSERT ON {table}
        BEGIN INSERT INTO commit_attempts (permit) VALUES (1); END''')


def rows(db, table):
    if table not in {'batches', 'revisions', 'measurements', 'qualifications', 'packets', 'pickups',
                     'accepted_packets', 'reports', 'receipts', 'commit_attempts'}:
        raise ValueError(table)
    return db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]


class ShiftCase(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(TemporaryDirectory(prefix='water-tests-')))
        self.sample = load_shift()
        self.supply_path = self.path / 'supply.db'
        self.receive_path = self.path / 'receive.db'
        self.center_path = self.path / 'center.db'
        self.supply = self.enterContext(open_station(self.supply_path))
        self.receive = self.enterContext(open_station(self.receive_path))
        self.center = self.enterContext(open_center(self.center_path))

    def close_sites(self):
        self.supply.close()
        self.receive.close()
        self.assert_closed(self.supply)
        self.assert_closed(self.receive)

    def assert_closed(self, db):
        import sqlite3
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute('SELECT 1')

    def reopen_center(self):
        self.center.close()
        self.center = self.enterContext(open_center(self.center_path))

    def issue(self, db, side, layout, **kwargs):
        revision_id = record_layout(db, self.sample, side, layout, **kwargs)
        return get_packet(db, seal(db, revision_id))

    def materials(self, receiver='b_required', *, corrected=False, scale=Fraction(1), receive_ports=None):
        register_shift(self.supply, self.sample, scale=scale)
        register_shift(self.receive, self.sample, scale=scale, ports=receive_ports)
        original = self.issue(self.supply, 'supply', 'initial', scale=scale)
        receiving = self.issue(self.receive, 'receive', receiver, scale=scale)
        changed = None
        if corrected:
            changed = self.issue(self.supply, 'supply', 'correction', parent_id=original.revision_id, scale=scale)
        return original, receiving, changed

    def assert_range(self, report, bounds):
        result = report.snapshot.result
        expected = {'status': 'infeasible', 'range': None}
        if bounds is not None:
            expected = {'status': 'feasible', 'range': [str(Fraction(value)) for value in bounds]}
        actual = describe_range(result)
        marker = 'A_PORT_RANGE_MISMATCH' if report.snapshot.port == 'A' else 'PORT_RANGE_MISMATCH'
        self.assertEqual(actual, expected, f'{marker} actual={actual} expected={expected}')
        if bounds is None:
            self.assertIsNone(result.lower)
            self.assertIsNone(result.upper)
        else:
            self.assertIsInstance(result.lower, Fraction)
            self.assertIsInstance(result.upper, Fraction)
            self.assertEqual((result.lower, result.upper), tuple(Fraction(value) for value in bounds))
        return actual
