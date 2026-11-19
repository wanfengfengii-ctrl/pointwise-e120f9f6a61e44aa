import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    report_id: int
    receipt_id: str


def initialize_receipts(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            report_id INTEGER PRIMARY KEY REFERENCES reports(report_id),
            receipt_id TEXT NOT NULL UNIQUE
        )
    ''')


def create_receipt(report_id: int) -> Receipt:
    return Receipt(report_id, f'receipt-{report_id}')


def insert_receipt(db: sqlite3.Connection, receipt: Receipt) -> None:
    db.execute('INSERT INTO receipts (report_id, receipt_id) VALUES (?, ?)',
               (receipt.report_id, receipt.receipt_id))


def load_receipt(db: sqlite3.Connection, report_id: int) -> Receipt:
    row = db.execute('SELECT receipt_id FROM receipts WHERE report_id = ?', (report_id,)).fetchone()
    if row is None:
        raise KeyError(f'no receipt for report {report_id}')
    return Receipt(report_id, row[0])
