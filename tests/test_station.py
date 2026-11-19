from dataclasses import replace
from fractions import Fraction

from run_station import measured_layout, record_layout, register_shift
from station.measurements import Measurement
from station.revisions import get_revision, revise
from tests.support import ShiftCase, rows, scenario


class TestRevisions(ShiftCase):
    def test_reject_negative(self):
        batch = register_shift(self.supply, self.sample)
        parent = record_layout(self.supply, self.sample, 'supply', 'initial')
        before = get_revision(self.supply, parent)
        changed = list(measured_layout(self.sample, 'supply', 'correction'))
        changed[0] = replace(changed[0], capacity='-1/2')
        counts = (rows(self.supply, 'revisions'), rows(self.supply, 'measurements'))
        with self.assertRaisesRegex(ValueError, 'nonnegative') as error:
            revise(self.supply, batch.batch_id, 'supply', 'pump', changed, parent_id=parent)
        after = get_revision(self.supply, parent)
        self.assertEqual(after, before)
        current = (rows(self.supply, 'revisions'), rows(self.supply, 'measurements'))
        self.assertEqual(current, counts)
        scenario('bad_capacity', {'correction_liters': '-1/2'}, 'ValueError', type(error.exception).__name__,
                 {'counts': counts, 'parent_retained': True},
                 {'counts': current, 'parent_retained': before == after},
                 ['station/volumes.py', 'station/measurements.py', 'station/revisions.py'],
                 'Capacity is nonnegative and the rejected correction leaves all parent rows intact.')

    def test_cross_batch_parent(self):
        register_shift(self.supply, self.sample)
        register_shift(self.supply, self.sample, batch_id='other')
        parent = record_layout(self.supply, self.sample, 'supply', 'initial')
        original = get_revision(self.supply, parent)
        with self.assertRaisesRegex(ValueError, 'same batch and side'):
            record_layout(self.supply, self.sample, 'supply', 'correction', batch_id='other', parent_id=parent)
        with self.assertRaisesRegex(ValueError, 'same batch and side'):
            record_layout(self.supply, self.sample, 'receive', 'b_required', parent_id=parent)
        with self.assertRaises(KeyError):
            record_layout(self.supply, self.sample, 'supply', 'correction', parent_id='missing')
        self.assertEqual(rows(self.supply, 'revisions'), 1)
        self.assertEqual(rows(self.supply, 'measurements'), 6)
        self.assertEqual(get_revision(self.supply, parent), original)

    def test_missing_measurements_and_invalid_flow(self):
        batch = register_shift(self.supply, self.sample)
        valid = Measurement('pump', 'A', '1/3', 'sheet:row 1')
        for measures in ([], [replace(valid, source=' ')], [replace(valid, capacity='')],
                         [replace(valid, start='')], [replace(valid, end='pump')],
                         [replace(valid, capacity=0.25)]):
            with self.subTest(measures=measures), self.assertRaises(ValueError):
                revise(self.supply, batch.batch_id, 'supply', 'pump', measures)
        with self.assertRaisesRegex(ValueError, 'distinct from the public ports'):
            revise(self.supply, batch.batch_id, 'supply', 'A', [valid])
        self.assertEqual(rows(self.supply, 'revisions'), 0)
        self.assertEqual(rows(self.supply, 'measurements'), 0)

    def test_record_parallel_measurements_and_zero(self):
        batch = register_shift(self.supply, self.sample)
        revision_id = revise(self.supply, batch.batch_id, 'supply', 'pump', [
            Measurement('pump', 'A', '1/3', 'worksheet: first'),
            Measurement('pump', 'A', '2/3', 'worksheet: second'),
            Measurement('pump', 'B', 0, 'worksheet: closed'),
        ])
        revision = get_revision(self.supply, revision_id)
        self.assertEqual(revision.measurements, (
            Measurement('pump', 'A', Fraction(1, 3), 'worksheet: first'),
            Measurement('pump', 'A', Fraction(2, 3), 'worksheet: second'),
            Measurement('pump', 'B', Fraction(0), 'worksheet: closed'),
        ))
        self.assertIsNone(revision.parent_id)
        self.assertEqual(revision.root, 'pump')
