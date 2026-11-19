import argparse
import json
import sqlite3
from contextlib import closing, contextmanager
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from capacity.qualification import initialize_qualifications
from issue.catalog import initialize_catalog
from issue.publish import seal
from issue.transfer import get_packet
from reports.export import export
from reports.publish import initialize_reports
from reports.readback import get_report
from review.admission import admit, initialize_admissions
from review.reconcile import review
from station.batches import initialize_batches, register
from station.measurements import Measurement
from station.revisions import initialize_revisions, revise
from station.volumes import parse_liters


_SAMPLE = Path(__file__).resolve().parent / 'samples' / 'shift.json'


def initialize_station(db):
    db.execute('PRAGMA foreign_keys = ON')
    db.execute('BEGIN IMMEDIATE')
    with db:
        initialize_batches(db)
        initialize_revisions(db)
        initialize_qualifications(db)
        initialize_catalog(db)


def initialize_center(db):
    db.execute('PRAGMA foreign_keys = ON')
    db.execute('BEGIN IMMEDIATE')
    with db:
        initialize_admissions(db)
        initialize_reports(db)


@contextmanager
def open_station(path):
    with closing(sqlite3.connect(path)) as db:
        initialize_station(db)
        yield db


@contextmanager
def open_center(path):
    with closing(sqlite3.connect(path)) as db:
        initialize_center(db)
        yield db


def load_shift():
    return json.loads(_SAMPLE.read_text(encoding='utf-8'))


def register_shift(db, sample, *, batch_id=None, ports=None, scale=Fraction(1)):
    return register(
        db, sample['batch_id'] if batch_id is None else batch_id,
        sample['ports'] if ports is None else ports, parse_liters(sample['total']) * scale,
    )


def measured_layout(sample, side, layout, *, scale=Fraction(1)):
    return tuple(Measurement(start, end, parse_liters(amount) * scale, source)
                 for start, end, amount, source in sample[side]['layouts'][layout])


def record_layout(db, sample, side, layout, *, batch_id=None, parent_id=None, scale=Fraction(1)):
    return revise(
        db, sample['batch_id'] if batch_id is None else batch_id, side, sample[side]['root'],
        measured_layout(sample, side, layout, scale=scale), parent_id=parent_id,
    )


def describe_range(result):
    amounts = None if result.lower is None else [str(result.lower), str(result.upper)]
    return {'status': result.status, 'range': amounts}


def _require_a(report, lower, upper):
    actual = describe_range(report.snapshot.result)
    expected = {'status': 'feasible', 'range': [lower, upper]}
    if actual != expected:
        raise AssertionError(f'A_PORT_RANGE_MISMATCH actual={actual} expected={expected}')
    return actual


def demo():
    sample = load_shift()
    with TemporaryDirectory(prefix='water-shift-') as directory:
        path = Path(directory)
        supply_path, receive_path, center_path = (path / name for name in ('supply.db', 'receive.db', 'center.db'))
        with open_station(supply_path) as supply, open_station(receive_path) as receive:
            register_shift(supply, sample)
            register_shift(receive, sample)
            original = record_layout(supply, sample, 'supply', 'initial')
            original_packet = get_packet(supply, seal(supply, original))
            receive_revision = record_layout(receive, sample, 'receive', 'b_required')
            receive_packet = get_packet(receive, seal(receive, receive_revision))

        with open_center(center_path) as center:
            old_id = admit(center, original_packet)
            receive_id = admit(center, receive_packet)
            old_report = review(center, old_id, receive_id, 'A')
            before = _require_a(old_report, '0', '0')
            old_export = export(center, old_report.report_id)

        with open_station(supply_path) as supply:
            changed = record_layout(supply, sample, 'supply', 'correction', parent_id=original)
            changed_packet = get_packet(supply, seal(supply, changed))

        with open_center(center_path) as center:
            new_id = admit(center, changed_packet)
            new_report = review(center, new_id, receive_id, 'A')
            after = _require_a(new_report, '0', '1')

        with open_center(center_path) as center:
            archived = get_report(center, old_report.report_id)
            retained = archived == old_report and export(center, archived.report_id) == old_export
            if not retained or get_report(center, new_report.report_id) != new_report:
                raise AssertionError('the signed reports changed on reopen')
            print(json.dumps({
                'batch': sample['batch_id'], 'port': archived.snapshot.port, 'unit': 'L',
                'before': before, 'after': after, 'original_retrieved': retained,
                'old_report': archived.report_id, 'new_report': new_report.report_id,
                'old_receipt': archived.receipt.receipt_id, 'new_receipt': new_report.receipt.receipt_id,
            }, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description='Reuse water station handover')
    parser.add_argument('command', choices=['demo'])
    parser.parse_args()
    demo()


if __name__ == '__main__':
    main()
