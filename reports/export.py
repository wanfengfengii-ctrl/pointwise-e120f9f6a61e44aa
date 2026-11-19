import json
import sqlite3
from dataclasses import asdict

from reports.readback import get_report


def export(db: sqlite3.Connection, report_id: int) -> str:
    report = get_report(db, report_id)
    return json.dumps({
        'report_id': report.report_id,
        'snapshot': report.snapshot.to_record(),
        'receipt': asdict(report.receipt),
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
