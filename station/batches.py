import json
import sqlite3
from dataclasses import dataclass
from fractions import Fraction

from station.ports import PortRoster, validate_identity, validate_roster
from station.volumes import encode_liters, parse_liters


@dataclass(frozen=True)
class Batch:
    batch_id: str
    ports: PortRoster
    total: Fraction


def initialize_batches(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS batches (
            batch_id TEXT PRIMARY KEY NOT NULL,
            ports TEXT NOT NULL,
            total TEXT NOT NULL
        )
    ''')


def register(db: sqlite3.Connection, batch_id: str, ports, total) -> Batch:
    batch = Batch(
        validate_identity(batch_id, 'batch'),
        validate_roster(ports),
        parse_liters(total, positive=True),
    )
    db.execute('BEGIN IMMEDIATE')
    with db:
        row = db.execute('SELECT 1 FROM batches WHERE batch_id = ?', (batch_id,)).fetchone()
        if row is not None:
            raise ValueError(f'batch already registered: {batch_id}')
        db.execute(
            'INSERT INTO batches (batch_id, ports, total) VALUES (?, ?, ?)',
            (batch.batch_id, json.dumps(batch.ports.ids), encode_liters(batch.total)),
        )
    return batch


def get_batch(db: sqlite3.Connection, batch_id: str) -> Batch:
    row = db.execute('SELECT ports, total FROM batches WHERE batch_id = ?', (batch_id,)).fetchone()
    if row is None:
        raise KeyError(batch_id)
    return Batch(batch_id, validate_roster(json.loads(row[0])), parse_liters(row[1], positive=True))
