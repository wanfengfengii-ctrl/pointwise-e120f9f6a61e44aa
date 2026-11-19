import sqlite3
from dataclasses import dataclass
from uuid import uuid4

from station.batches import get_batch
from station.measurements import (
    Measurement, initialize_measurements, load_measurements, store_measurements, validate_measurements,
)
from station.ports import validate_identity


@dataclass(frozen=True)
class Revision:
    revision_id: str
    batch_id: str
    side: str
    root: str
    parent_id: str | None
    measurements: tuple[Measurement, ...]


def initialize_revisions(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS revisions (
            revision_id TEXT PRIMARY KEY NOT NULL,
            batch_id TEXT NOT NULL REFERENCES batches(batch_id),
            side TEXT NOT NULL CHECK (side IN ('supply', 'receive')),
            root TEXT NOT NULL,
            parent_id TEXT REFERENCES revisions(revision_id)
        )
    ''')
    initialize_measurements(db)


def revise(db: sqlite3.Connection, batch_id: str, side: str, root: str,
           measurements, *, parent_id: str | None = None) -> str:
    batch = get_batch(db, batch_id)
    if side not in ('supply', 'receive'):
        raise ValueError('site side must be supply or receive')
    root = validate_identity(root, 'station root')
    if root in batch.ports.ids:
        raise ValueError('the station root must be distinct from the public ports')
    rows = validate_measurements(measurements)

    db.execute('BEGIN IMMEDIATE')
    with db:
        if parent_id is not None:
            parent = db.execute(
                'SELECT batch_id, side FROM revisions WHERE revision_id = ?', (parent_id,),
            ).fetchone()
            if parent is None:
                raise KeyError(parent_id)
            if tuple(parent) != (batch_id, side):
                raise ValueError('parent revision must belong to the same batch and side')
        revision_id = 'rev-' + uuid4().hex
        db.execute(
            'INSERT INTO revisions (revision_id, batch_id, side, root, parent_id) VALUES (?, ?, ?, ?, ?)',
            (revision_id, batch_id, side, root, parent_id),
        )
        store_measurements(db, revision_id, rows)
    return revision_id


def get_revision(db: sqlite3.Connection, revision_id: str) -> Revision:
    row = db.execute(
        'SELECT batch_id, side, root, parent_id FROM revisions WHERE revision_id = ?', (revision_id,),
    ).fetchone()
    if row is None:
        raise KeyError(revision_id)
    batch_id, side, root, parent_id = row
    return Revision(revision_id, batch_id, side, root, parent_id, load_measurements(db, revision_id))
