import json
import sqlite3

from reports.readback import Report
from reports.receipts import create_receipt, initialize_receipts, insert_receipt
from reports.snapshots import ReportSnapshot


def initialize_reports(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY,
            snapshot TEXT NOT NULL
        )
    ''')
    initialize_receipts(db)


def publish_report(db: sqlite3.Connection, snapshot: ReportSnapshot) -> Report:
    encoded = json.dumps(snapshot.to_record(), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    db.execute('BEGIN IMMEDIATE')
    with db:
        result = db.execute('INSERT INTO reports (snapshot) VALUES (?)', (encoded,))
        report_id = result.lastrowid
        receipt = create_receipt(report_id)
        insert_receipt(db, receipt)
    return Report(report_id, snapshot, receipt)
