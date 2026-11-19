import sqlite3
from fractions import Fraction

from issue.envelope import decode_packet, encode_packet
from issue.publish import seal
from issue.transfer import get_packet
from review.admission import admit
from review.reconcile import review
from run_station import initialize_station, open_station, record_layout, register_shift
from station.batches import get_batch, register
from station.measurements import Measurement
from station.revisions import get_revision, revise
from tests.support import ShiftCase, fail_commit_on_insert, rows, scenario


class TestIssuance(ShiftCase):
    def test_two_sites(self):
        supplying, receiving, _ = self.materials()
        sides = []
        packets_match = []
        for db, packet, side in ((self.supply, supplying, 'supply'), (self.receive, receiving, 'receive')):
            revision = get_revision(db, packet.revision_id)
            self.assertEqual((revision.side, packet.side), (side, side))
            self.assertEqual(revision.batch_id, self.sample['batch_id'])
            self.assertEqual(packet.batch_id, revision.batch_id)
            self.assertEqual(packet.total, Fraction(2))
            self.assertEqual(packet.ports.ids, ('A', 'B', 'C', 'D'))
            self.assertEqual(seal(db, revision.revision_id), packet.packet_id)
            persisted = get_packet(db, packet.packet_id)
            self.assertEqual(persisted, packet)
            encoded = encode_packet(persisted)
            self.assertEqual(decode_packet(encoded), packet)
            self.assertNotIn(revision.root, encoded)
            for measurement in revision.measurements:
                self.assertNotIn(measurement.source, encoded)
                for node in (measurement.start, measurement.end):
                    if node not in packet.ports.ids:
                        self.assertNotIn(node, encoded)
            self.assertEqual(rows(db, 'packets'), 1)
            self.assertEqual(rows(db, 'qualifications'), 1)
            self.assertEqual(rows(db, 'pickups'), 2)
            with self.assertRaises(KeyError):
                get_packet(db, 'unknown-packet')
            self.assertEqual(rows(db, 'pickups'), 2)
            sides.append(persisted.side)
            packets_match.append(persisted == packet)
        self.assertNotEqual(supplying.packet_id, receiving.packet_id)
        scenario('seal_receive', {'batch': supplying.batch_id, 'total_liters': '2'},
                 ['supply', 'receive'], sides, [True, True], packets_match,
                 ['station/revisions.py', 'capacity/qualification.py', 'issue/publish.py', 'issue/transfer.py'],
                 'Each fixture has two disjoint one-liter routes and each retrieved record binds its own revision.')

    def test_invalid_registration(self):
        for ports, liters in ((['A', 'A', 'C', 'D'], 2), (['A', '', 'C', 'D'], 2),
                              (['A', 'B', 'C'], 2), ('ABCD', 2), (['A', 'B', 'C', 'D'], 0),
                              (['A', 'B', 'C', 'D'], '1/0'), (['A', 'B', 'C', 'D'], True)):
            with self.subTest(ports=ports, liters=liters), self.assertRaises(ValueError):
                register(self.supply, 'registration', ports, liters)
        self.assertEqual(rows(self.supply, 'batches'), 0)
        batch = register(self.supply, 'registration', ['D', 'B', 'A', 'C'], '3/2')
        with self.assertRaisesRegex(ValueError, 'already registered'):
            register(self.supply, batch.batch_id, ['A', 'B', 'C', 'D'], 2)
        self.assertEqual(get_batch(self.supply, batch.batch_id), batch)

    def test_insufficient(self):
        register_shift(self.supply, self.sample)
        revision_id = record_layout(self.supply, self.sample, 'supply', 'insufficient')
        with self.assertRaisesRegex(ValueError, '1 L for 2 L') as error:
            seal(self.supply, revision_id)
        self.assertEqual(rows(self.supply, 'packets'), 0)
        self.assertEqual(rows(self.supply, 'qualifications'), 0)
        self.assertEqual(get_revision(self.supply, revision_id).measurements[0].capacity, 1)
        scenario('no_standing_capacity', {'total_liters': '2', 'single_route_liters': '1'}, 'ValueError',
                 type(error.exception).__name__, 0, rows(self.supply, 'packets'),
                 ['capacity/flow.py', 'capacity/qualification.py', 'issue/publish.py'],
                 'The only outgoing route carries at most one liter.')

    def test_shared_feed_limit(self):
        packet, _, _ = self.materials()
        revision_id = record_layout(self.supply, self.sample, 'supply', 'shared_feed', parent_id=packet.revision_id)
        with self.assertRaisesRegex(ValueError, '1 L for 2 L'):
            seal(self.supply, revision_id)
        self.assertEqual(rows(self.supply, 'packets'), 1)
        self.assertEqual(rows(self.supply, 'qualifications'), 1)
        self.assertEqual(get_packet(self.supply, packet.packet_id), packet)

    def test_same_marginals_distinct_joint(self):
        original, free, corrected = self.materials('free', corrected=True)
        forced = self.issue(self.receive, 'receive', 'ab_required', parent_id=free.revision_id)
        original = get_packet(self.supply, original.packet_id)
        corrected = get_packet(self.supply, corrected.packet_id)
        self.close_sites()
        first, second, open_receive, fixed_ab = [admit(self.center, packet)
                                                for packet in (original, corrected, free, forced)]
        self.assertEqual(original.total, corrected.total)
        for packet_id in (first, second):
            for port in ('A', 'B', 'C', 'D'):
                self.assert_range(review(self.center, packet_id, open_receive, port), (0, 1))
        self.assertNotEqual(original.evidence, corrected.evidence)
        before = review(self.center, first, fixed_ab, 'A')
        after = review(self.center, second, fixed_ab, 'A')
        self.assert_range(before, None)
        self.assert_range(after, (1, 1))

    def test_commit_failure(self):
        register_shift(self.supply, self.sample)
        original = self.issue(self.supply, 'supply', 'initial')
        candidate = record_layout(self.supply, self.sample, 'supply', 'correction', parent_id=original.revision_id)
        fail_commit_on_insert(self.supply, 'packets')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY'):
            seal(self.supply, candidate)
        self.supply.close()
        with open_station(self.supply_path) as db:
            self.assertEqual(rows(db, 'qualifications'), 1)
            self.assertEqual(rows(db, 'packets'), 1)
            self.assertEqual(rows(db, 'commit_attempts'), 0)
            self.assertEqual(get_packet(db, original.packet_id), original)
            self.assertEqual(get_revision(db, candidate).parent_id, original.revision_id)
            db.execute('DROP TRIGGER require_commit_permit')
            recovered_id = seal(db, candidate)
            self.assertEqual(get_packet(db, recovered_id).revision_id, candidate)

    def test_reinitialize_station(self):
        original, _, changed = self.materials(corrected=True)
        measurement_rows = get_revision(self.supply, changed.revision_id).measurements
        initialize_station(self.supply)
        self.supply.close()
        with open_station(self.supply_path) as db:
            self.assertEqual(rows(db, 'batches'), 1)
            self.assertEqual(rows(db, 'revisions'), 2)
            self.assertEqual(rows(db, 'measurements'), 12)
            self.assertEqual(rows(db, 'qualifications'), 2)
            self.assertEqual(rows(db, 'packets'), 2)
            self.assertEqual(rows(db, 'pickups'), 2)
            self.assertEqual(get_packet(db, original.packet_id), original)
            self.assertEqual(get_packet(db, changed.packet_id), changed)
            self.assertEqual(get_revision(db, changed.revision_id).measurements, measurement_rows)

    def test_flow_can_reroute_parallel_and_opposed_segments(self):
        batch = register_shift(self.supply, self.sample)
        # One unit can go through x to B and the other through y to A.
        supply = revise(self.supply, batch.batch_id, 'supply', 'pump', [
            Measurement('pump', 'x', '1/2', 'reroute:01'),
            Measurement('pump', 'x', '1/2', 'reroute:02'),
            Measurement('pump', 'y', 1, 'reroute:03'),
            Measurement('x', 'A', 1, 'reroute:04'),
            Measurement('x', 'B', 1, 'reroute:05'),
            Measurement('y', 'A', 1, 'reroute:06'),
            Measurement('A', 'x', '1/4', 'reroute:07'),
        ])
        register_shift(self.receive, self.sample)
        receiving = self.issue(self.receive, 'receive', 'ab_required')
        supplying = get_packet(self.supply, seal(self.supply, supply))
        self.close_sites()
        first = admit(self.center, supplying)
        second = admit(self.center, receiving)
        self.assert_range(review(self.center, first, second, 'A'), (1, 1))
