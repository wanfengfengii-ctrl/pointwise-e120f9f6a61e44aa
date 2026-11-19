import json
import sqlite3
from fractions import Fraction

from issue.transfer import get_packet
from reports.export import export
from reports.readback import get_report
from review.admission import admit, get_accepted
from review.reconcile import review
from run_station import initialize_center, open_station
from station.revisions import get_revision
from tests.support import ShiftCase, fail_commit_on_insert, rows, scenario


class TestReports(ShiftCase):
    def correction_history(self):
        supplying, receiving, _ = self.materials()
        self.close_sites()
        supply_id, receive_id = admit(self.center, supplying), admit(self.center, receiving)
        first = review(self.center, supply_id, receive_id, 'A')
        self.assert_range(first, (0, 0))
        original_export = export(self.center, first.report_id)
        with open_station(self.supply_path) as station:
            corrected = self.issue(station, 'supply', 'correction', parent_id=supplying.revision_id)
            self.assertEqual(get_revision(station, corrected.revision_id).parent_id, supplying.revision_id)
        revised_id = admit(self.center, corrected)
        second = review(self.center, revised_id, receive_id, 'A')
        self.assert_range(second, (0, 1))
        return first, second, original_export, supplying, receiving, corrected

    def test_correction_readback(self):
        first, second, original_export, _, _, _ = self.correction_history()
        self.reopen_center()
        old = get_report(self.center, first.report_id)
        new = get_report(self.center, second.report_id)
        self.assertEqual(old, first)
        self.assertEqual(new, second)
        self.assertNotEqual(new.receipt, old.receipt)
        self.assertEqual(new.snapshot.receive, old.snapshot.receive)
        same_export = export(self.center, old.report_id) == original_export
        self.assertTrue(same_export)
        actual = [self.assert_range(old, (0, 0)), self.assert_range(new, (0, 1))]
        scenario('historical', {'supply_before': ['AB', 'CD'], 'supply_after': ['AC', 'BD'], 'receive_B': '1'},
                 [{'status': 'feasible', 'range': ['0', '0']}, {'status': 'feasible', 'range': ['0', '1']}],
                 actual, True, same_export,
                 ['station/revisions.py', 'review/reconcile.py', 'reports/readback.py', 'reports/export.py'],
                 'After the change B uses BD and A can use up to one liter on the independent AC branch.')

    def test_original_provenance(self):
        first, second, original_export, supplying, receiving, corrected = self.correction_history()
        self.reopen_center()
        old = json.loads(export(self.center, first.report_id))
        new = json.loads(export(self.center, second.report_id))
        self.assertEqual(export(self.center, first.report_id), original_export)
        for item, original_supply, report in ((old, supplying, first), (new, corrected, second)):
            snapshot = item['snapshot']
            self.assertEqual(snapshot['port'], 'A')
            self.assertEqual(snapshot['total'], '2')
            for side, packet in (('supply', original_supply), ('receive', receiving)):
                reference = snapshot[side]
                self.assertEqual(reference['packet_id'], packet.packet_id)
                self.assertEqual(reference['revision_id'], packet.revision_id)
                self.assertEqual(reference['batch_id'], packet.batch_id)
                self.assertEqual(reference['side'], side)
                self.assertEqual(get_accepted(self.center, reference['accepted_id']).packet, packet)
            self.assertEqual(item['receipt'], {'report_id': report.report_id, 'receipt_id': report.receipt.receipt_id})
        with self.assertRaises(KeyError):
            get_report(self.center, 999)
        with self.assertRaises(KeyError):
            export(self.center, 999)

    def test_reinitialize_preserves_records(self):
        first, second, original_export, supplying, receiving, corrected = self.correction_history()
        self.reopen_center()
        initialize_center(self.center)
        self.reopen_center()
        self.assertEqual(rows(self.center, 'accepted_packets'), 3)
        self.assertEqual(rows(self.center, 'reports'), 2)
        self.assertEqual(rows(self.center, 'receipts'), 2)
        self.assertEqual(get_report(self.center, first.report_id), first)
        self.assertEqual(get_report(self.center, second.report_id), second)
        self.assertEqual(export(self.center, first.report_id), original_export)
        for reference, packet in ((first.snapshot.supply, supplying), (second.snapshot.supply, corrected),
                                  (first.snapshot.receive, receiving)):
            self.assertEqual(get_accepted(self.center, reference.accepted_id).packet, packet)
        with open_station(self.supply_path) as station:
            self.assertEqual(rows(station, 'batches'), 1)
            self.assertEqual(rows(station, 'revisions'), 2)
            self.assertEqual(rows(station, 'measurements'), 12)
            self.assertEqual(rows(station, 'qualifications'), 2)
            self.assertEqual(get_packet(station, supplying.packet_id), supplying)
            self.assertEqual(get_packet(station, corrected.packet_id), corrected)
            changed = get_revision(station, corrected.revision_id)
            self.assertEqual(changed.parent_id, supplying.revision_id)
            self.assertEqual((changed.measurements[3].end, changed.measurements[3].source), ('C', 'recheck-supply:04'))
        with open_station(self.receive_path) as station:
            self.assertEqual(rows(station, 'revisions'), 1)
            self.assertEqual(get_packet(station, receiving.packet_id), receiving)

    def test_atomic_failure(self):
        first, second, original_export, _, _, _ = self.correction_history()
        supply_id = second.snapshot.supply.accepted_id
        receive_id = second.snapshot.receive.accepted_id
        before = [rows(self.center, 'reports'), rows(self.center, 'receipts')]
        fail_commit_on_insert(self.center, 'receipts')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY') as error:
            review(self.center, supply_id, receive_id, 'B')
        self.reopen_center()
        after = [rows(self.center, 'reports'), rows(self.center, 'receipts')]
        self.assertEqual(after, before)
        self.assertEqual(rows(self.center, 'commit_attempts'), 0)
        self.assertEqual(get_report(self.center, first.report_id), first)
        self.assertEqual(get_report(self.center, second.report_id), second)
        self.assertEqual(export(self.center, first.report_id), original_export)
        with self.assertRaises(KeyError):
            get_report(self.center, second.report_id + 1)
        scenario('report_rollback', {'request_port': 'B', 'reports_before_failure': before[0]},
                 'IntegrityError', type(error.exception).__name__, before, after,
                 ['review/reconcile.py', 'reports/publish.py', 'reports/receipts.py', 'reports/readback.py'],
                 'SQLite checks the absent permit at commit after both rows have been inserted.')
        self.center.execute('DROP TRIGGER require_commit_permit')
        recovered = review(self.center, supply_id, receive_id, 'B')
        self.assert_range(recovered, (1, 1))
        self.assertEqual(get_report(self.center, recovered.report_id), recovered)

    def test_forced_ab_pair(self):
        original, receiving, corrected = self.materials('ab_required', corrected=True)
        self.close_sites()
        first, receive, second = [admit(self.center, packet) for packet in (original, receiving, corrected)]
        impossible = review(self.center, first, receive, 'A')
        feasible = review(self.center, second, receive, 'A')
        self.assert_range(impossible, None)
        self.assert_range(feasible, (1, 1))
        self.assertEqual(get_report(self.center, impossible.report_id), impossible)
        self.assertEqual(get_report(self.center, feasible.report_id), feasible)

    def test_scaled_half(self):
        original, receiving, corrected = self.materials(corrected=True, scale=Fraction(1, 2))
        self.assertEqual(original.total, Fraction(1))
        self.assertEqual(receiving.total, Fraction(1))
        self.close_sites()
        first, receive, second = [admit(self.center, packet) for packet in (original, receiving, corrected)]
        before = review(self.center, first, receive, 'A')
        after = review(self.center, second, receive, 'A')
        self.assert_range(before, (0, 0))
        self.assert_range(after, (0, '1/2'))
        self.assertEqual(get_report(self.center, before.report_id), before)
        self.assertEqual(get_report(self.center, after.report_id), after)
