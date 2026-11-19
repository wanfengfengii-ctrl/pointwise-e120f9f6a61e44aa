import json
import sqlite3
from dataclasses import dataclass

from reports.receipts import Receipt, load_receipt
from reports.snapshots import ReportSnapshot


@dataclass(frozen=True)
class Report:
    report_id: int
    snapshot: ReportSnapshot
    receipt: Receipt


def get_report(db: sqlite3.Connection, report_id: int) -> Report:
    row = db.execute('SELECT report_id, snapshot FROM reports WHERE report_id = ?', (report_id,)).fetchone()
    if row is None:
        raise KeyError(report_id)
    fixed_id, encoded = row
    return Report(fixed_id, ReportSnapshot.from_record(json.loads(encoded)), load_receipt(db, fixed_id))
