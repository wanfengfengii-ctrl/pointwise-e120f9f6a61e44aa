import json
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path

from issue.envelope import encode_packet, read_capability, read_ranges
from issue.publish import seal
from issue.transfer import get_packet
from review.admission import admit
from review.ranges import compute_port_range
from review.reconcile import review
from run_station import register_shift
from station.measurements import Measurement
from station.revisions import revise
from tests.support import ShiftCase, scenario


ROOT = Path(__file__).resolve().parent.parent

# Subset caps for the sample layouts, indexed by roster bit masks (A=1, B=2, C=4, D=8).
INITIAL_CAPS = ('0', '1', '1', '1', '1', '2', '2', '2', '1', '2', '2', '2', '1', '2', '2', '2')
CORRECTION_CAPS = ('0', '1', '1', '2', '1', '1', '2', '2', '1', '2', '1', '2', '2', '2', '2', '2')
B_REQUIRED_CAPS = ('0', '1', '1', '2', '1', '1', '2', '2', '1', '1', '2', '2', '1', '1', '2', '2')


class TestCapabilityBody(ShiftCase):
    def test_body_preserves_all_reachable_vectors(self):
        original, receiving, corrected = self.materials(corrected=True)
        expectations = ((original, INITIAL_CAPS), (corrected, CORRECTION_CAPS),
                        (receiving, B_REQUIRED_CAPS))
        for packet, subsets in expectations:
            with self.subTest(packet=packet.packet_id):
                self.assertEqual(packet.evidence['extensions']['subsets'], list(subsets))
                caps = read_capability(packet.evidence, packet.total)
                self.assertEqual(caps, tuple(Fraction(value) for value in subsets))
                intervals = read_ranges(packet.evidence, packet.total)
                for index, (lower, upper) in enumerate(intervals):
                    self.assertEqual(upper, caps[1 << index])
                    self.assertEqual(lower, packet.total - caps[15 ^ (1 << index)])
        self.assertNotEqual(original.evidence, corrected.evidence)
        scenario('capability_body', {'layouts': ['initial', 'correction', 'b_required']},
                 [list(INITIAL_CAPS), list(CORRECTION_CAPS), list(B_REQUIRED_CAPS)],
                 [packet.evidence['extensions']['subsets'] for packet, _ in expectations],
                 True, all(packet.evidence['extensions']['subsets'] == list(subsets)
                           for packet, subsets in expectations),
                 ['capacity/boundary.py', 'issue/envelope.py'],
                 'The sixteen subset caps bound every reachable full-batch vector and nothing else.')

    def test_tampered_capability_rejected(self):
        _, receiving, _ = self.materials()
        self.close_sites()
        good = json.loads(encode_packet(receiving))
        ranges = good['evidence']['ranges']
        subsets = good['evidence']['extensions']['subsets']
        broken = [
            {'ranges': ranges},
            {'ranges': ranges, 'extensions': []},
            {'ranges': ranges, 'extensions': {'subsets': subsets[:15]}},
            {'ranges': ranges, 'extensions': {'subsets': ['0'] * 16}},
            {'ranges': ranges, 'extensions': {'subsets': ['1'] + subsets[1:]}, },
            {'ranges': ranges, 'extensions': {'subsets': subsets[:1] + ['3'] + subsets[2:]}},
            {'ranges': ranges, 'extensions': {'subsets': subsets[:3] + ['0'] + subsets[4:]}},
            {'ranges': ranges, 'extensions': {'subsets': subsets[:15] + ['1']}},
            {'ranges': ranges, 'extensions': {'subsets': subsets[:1] + ['2/2'] + subsets[2:]}},
            {'ranges': [ranges[1], ranges[0], ranges[2], ranges[3]],
             'extensions': {'subsets': subsets}},
            {'ranges': ranges, 'extensions': {'subsets': subsets}, 'extra': {}},
        ]
        for evidence in broken:
            record = {**good, 'evidence': evidence}
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                admit(self.center, json.dumps(record))
        self.assertEqual(admit(self.center, json.dumps(good)), 1)

    def test_shared_branch_bounds_are_exact(self):
        # A and B share one liter upstream; the receiver caps B at 1/2, so A is [1/2, 1].
        register_shift(self.supply, self.sample)
        register_shift(self.receive, self.sample)
        supplying = self.issue(self.supply, 'supply', 'initial')
        batch_id = self.sample['batch_id']
        revision_id = revise(self.receive, batch_id, 'receive', 'tank', [
            Measurement('B', 'tank', '1/2', 'half:01'),
            Measurement('A', 'tank', 2, 'half:02'),
            Measurement('C', 'tank', 2, 'half:03'),
            Measurement('D', 'tank', 2, 'half:04'),
        ])
        receiving = get_packet(self.receive, seal(self.receive, revision_id))
        self.close_sites()
        supply_id, receive_id = admit(self.center, supplying), admit(self.center, receiving)
        actual = self.assert_range(review(self.center, supply_id, receive_id, 'A'), ('1/2', '1'))
        self.assert_range(review(self.center, supply_id, receive_id, 'B'), (0, '1/2'))
        scenario('shared_branch_exact', {'supply_groups': ['AB', 'CD'], 'receive_B_limit': '1/2'},
                 {'status': 'feasible', 'range': ['1/2', '1']}, actual, True, True,
                 ['capacity/boundary.py', 'review/reconcile.py', 'review/ranges.py'],
                 'The shared one-liter AB branch forces A to at least half a liter once B is capped.')

    def test_target_coordinate_validated(self):
        caps = [Fraction(0)] * 16
        with self.assertRaises(ValueError):
            compute_port_range(Fraction(2), caps, 4)
        with self.assertRaises(ValueError):
            compute_port_range(Fraction(2), caps, -1)
        with self.assertRaises(ValueError):
            compute_port_range(Fraction(2), caps[:15], 0)


class TestIncidentEntry(unittest.TestCase):
    def test_incident_script(self):
        completed = subprocess.run(
            [sys.executable, '-B', 'incident.py'], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output['actual'], output['expected'])
        self.assertEqual(output['actual']['before'], {'status': 'feasible', 'range': ['0', '0']})
        self.assertEqual(output['actual']['after'], {'status': 'feasible', 'range': ['0', '1']})
