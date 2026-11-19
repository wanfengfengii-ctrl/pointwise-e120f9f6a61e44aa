import json
from fractions import Fraction

from capacity.linear import matrix_rank, solve_linear_system
from issue.envelope import encode_packet
from reports.export import export
from reports.readback import get_report
from review.admission import admit, get_accepted
from review.reconcile import review
from run_station import open_station, register_shift
from tests.support import ShiftCase, rows, scenario


class TestReview(ShiftCase):
    def test_offline_zero(self):
        supplying, receiving, _ = self.materials()
        supply_id = admit(self.center, encode_packet(supplying))
        receive_id = admit(self.center, encode_packet(receiving).encode('utf-8'))
        self.close_sites()
        issued = review(self.center, supply_id, receive_id, 'A')
        actual = self.assert_range(issued, (0, 0))
        stored = get_report(self.center, issued.report_id)
        self.assertEqual(stored, issued)
        self.assertEqual(stored.snapshot.port, 'A')
        self.assertEqual(stored.snapshot.supply.packet_id, supplying.packet_id)
        self.assertEqual(stored.snapshot.receive.packet_id, receiving.packet_id)
        self.assertEqual(stored.receipt.report_id, issued.report_id)
        scenario('offline_zero', {'supply_groups': ['AB', 'CD'], 'receive_B': '1', 'total_liters': '2'},
                 {'status': 'feasible', 'range': ['0', '0']}, actual, True, stored == issued,
                 ['issue/publish.py', 'review/reconcile.py', 'review/ranges.py', 'reports/readback.py'],
                 'The one-liter AB branch is fully used by B. C and D can take the other liter.')

    def test_offline_incompatible(self):
        supplying, receiving, _ = self.materials('ab_required')
        self.close_sites()
        issued = review(self.center, admit(self.center, supplying), admit(self.center, receiving), 'A')
        actual = self.assert_range(issued, None)
        read = get_report(self.center, issued.report_id)
        self.assertEqual(read, issued)
        self.assertEqual(rows(self.center, 'receipts'), 1)
        encoded = json.loads(export(self.center, issued.report_id))
        self.assertEqual(encoded['snapshot']['result'], {'status': 'infeasible', 'lower': None, 'upper': None})
        scenario('offline_incompatible', {'supply_AB_limit': '1', 'receive_A': '1', 'receive_B': '1'},
                 {'status': 'infeasible', 'range': None}, actual, 1, rows(self.center, 'receipts'),
                 ['review/reconcile.py', 'review/ranges.py', 'reports/publish.py'],
                 'The receiver requires two liters through the one-liter AB branch.')

    def test_mixed_batch(self):
        register_shift(self.supply, self.sample)
        register_shift(self.receive, self.sample, batch_id='second-shift')
        supplying = self.issue(self.supply, 'supply', 'initial')
        receiving = self.issue(self.receive, 'receive', 'b_required', batch_id='second-shift')
        self.close_sites()
        supply_id, receive_id = admit(self.center, supplying), admit(self.center, receiving)
        with self.assertRaisesRegex(ValueError, 'different batches') as error:
            review(self.center, supply_id, receive_id, 'A')
        counts = [rows(self.center, 'reports'), rows(self.center, 'receipts')]
        self.assertEqual(counts, [0, 0])
        self.assertEqual(rows(self.center, 'accepted_packets'), 2)
        scenario('mixed_pair', {'supply': supplying.batch_id, 'receive': receiving.batch_id}, 'ValueError',
                 type(error.exception).__name__, [0, 0], counts,
                 ['review/admission.py', 'review/selection.py', 'review/reconcile.py'],
                 'Two different batch identities are incompatible even with identical public layouts.')

    def test_invalid_selection(self):
        supplying, receiving, _ = self.materials()
        with open_station(self.path / 'bad-roster.db') as other:
            register_shift(other, self.sample, ports=['A', 'B', 'C', 'E'])
            bad_roster = self.issue(other, 'receive', 'free')
        with open_station(self.path / 'bad-volume.db') as other:
            half = Fraction(1, 2)
            register_shift(other, self.sample, scale=half)
            bad_total = self.issue(other, 'receive', 'free', scale=half)
        self.close_sites()
        s, r, roster, total = [admit(self.center, p) for p in (supplying, receiving, bad_roster, bad_total)]
        cases = [(r, s, 'A', 'supply packet'), (s, roster, 'A', 'rosters disagree'),
                 (s, total, 'A', 'batch volume'), (s, r, 'X', 'unknown public port')]
        for supply_id, receive_id, target, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                review(self.center, supply_id, receive_id, target)
        with self.assertRaises(KeyError):
            review(self.center, s, 999, 'A')
        self.assertEqual(rows(self.center, 'reports'), 0)
        self.assertEqual(rows(self.center, 'receipts'), 0)

    def test_invalid_envelope(self):
        supplying, receiving, _ = self.materials()
        good = json.loads(encode_packet(receiving))
        alternatives = [{**good, 'version': True}, {**good, 'revision_id': ''}, {**good, 'packet_id': ' '},
                        {**good, 'side': 'monitor'}, {**good, 'ports': ['A', 'A', 'C', 'D']},
                        {**good, 'total': '2/0'}, {**good, 'evidence': []}]
        for record in alternatives:
            with self.subTest(record=record), self.assertRaises(ValueError):
                admit(self.center, json.dumps(record))
        with self.assertRaises(ValueError):
            admit(self.center, '{"version":1,"version":1}')
        self.assertEqual(rows(self.center, 'accepted_packets'), 0)
        supply_id = admit(self.center, supplying)
        self.assertEqual(get_accepted(self.center, supply_id).packet, supplying)

    def test_permuted_receive(self):
        supplying, receiving, _ = self.materials(receive_ports=['B', 'A', 'C', 'D'])
        self.assertEqual(receiving.ports.ids, ('B', 'A', 'C', 'D'))
        self.close_sites()
        supply_id = admit(self.center, supplying)
        receive_id = admit(self.center, receiving)
        issued = review(self.center, supply_id, receive_id, 'A')
        self.assert_range(issued, (0, 0))
        self.assertEqual(issued.snapshot.receive.packet_id, receiving.packet_id)
        self.assert_range(review(self.center, supply_id, receive_id, 'B'), (1, 1))

    def test_fractional_crossing(self):
        supplying, receiving, _ = self.materials('fractional')
        self.close_sites()
        supply_id, receive_id = admit(self.center, supplying), admit(self.center, receiving)
        report = review(self.center, supply_id, receive_id, 'A')
        exact = self.assert_range(report, ('1/2', '1/2'))
        stored = get_report(self.center, report.report_id)
        self.assertEqual(stored, report)
        expected = {'status': 'feasible', 'range': ['1/2', '1/2']}
        roundtrip = self.assert_range(stored, ('1/2', '1/2'))
        scenario('fractional_crossing', {'supply_groups': ['AB', 'CD'], 'B': '1/2', 'D': '1'},
                 expected, exact, expected, roundtrip,
                 ['review/reconcile.py', 'capacity/linear.py', 'reports/snapshots.py', 'reports/readback.py'],
                 'AB and CD each sum to one. B=1/2 fixes A=1/2 and D=1 fixes C=0.')

    def test_fractional_exact_roundtrip(self):
        supplying, receiving, _ = self.materials('fractional')
        self.close_sites()
        issued = review(self.center, admit(self.center, supplying), admit(self.center, receiving), 'A')
        self.reopen_center()
        stored = get_report(self.center, issued.report_id)
        self.assertEqual(stored, issued)
        self.assert_range(stored, ('1/2', '1/2'))
        record = json.loads(export(self.center, issued.report_id))
        self.assertEqual(record['snapshot']['result'], {'status': 'feasible', 'lower': '1/2', 'upper': '1/2'})
        self.assertEqual(record['receipt']['report_id'], issued.report_id)

    def test_fractional_permuted_receive(self):
        supplying, receiving, _ = self.materials('fractional', receive_ports=['A', 'C', 'B', 'D'])
        self.assertEqual(receiving.ports.ids, ('A', 'C', 'B', 'D'))
        self.close_sites()
        report = review(self.center, admit(self.center, supplying), admit(self.center, receiving), 'A')
        self.assert_range(report, ('1/2', '1/2'))

    def test_exact_linear_primitives(self):
        self.assertEqual(matrix_rank(((0, 1, 2), (0, 2, 4), (1, 0, 0))), 2)
        self.assertEqual(solve_linear_system(((1, 1), (1, -1), (2, 0)), (1, 0, 1)),
                         (Fraction(1, 2), Fraction(1, 2)))
        self.assertIsNone(solve_linear_system(((1, 1), (2, 2)), (1, 3)))
        self.assertIsNone(solve_linear_system(((1, 1), (2, 2)), (1, 2)))
