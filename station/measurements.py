import sqlite3
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from station.ports import validate_identity
from station.volumes import encode_liters, parse_liters


@dataclass(frozen=True)
class Measurement:
    start: str
    end: str
    capacity: Fraction | int | str
    source: str


def initialize_measurements(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS measurements (
            revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
            row_number INTEGER NOT NULL CHECK (row_number > 0),
            start_node TEXT NOT NULL,
            end_node TEXT NOT NULL,
            capacity TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (revision_id, row_number)
        )
    ''')


def validate_measurements(rows: Iterable[Measurement]) -> tuple[Measurement, ...]:
    try:
        records = tuple(rows)
    except TypeError as error:
        raise ValueError('provide measured segments') from error
    if not records:
        raise ValueError('at least one measured segment is required')

    checked = []
    for row in records:
        if not isinstance(row, Measurement):
            raise ValueError('each measured segment must be a Measurement')
        start = validate_identity(row.start, 'segment start')
        end = validate_identity(row.end, 'segment end')
        if start == end:
            raise ValueError('a segment must connect two distinct nodes')
        if not isinstance(row.source, str) or not row.source.strip():
            raise ValueError('each measured segment needs a source row')
        checked.append(Measurement(start, end, parse_liters(row.capacity), row.source))
    return tuple(checked)


def store_measurements(db: sqlite3.Connection, revision_id: str, rows: tuple[Measurement, ...]) -> None:
    db.executemany(
        '''INSERT INTO measurements
           (revision_id, row_number, start_node, end_node, capacity, source)
           VALUES (?, ?, ?, ?, ?, ?)''',
        ((revision_id, number, row.start, row.end, encode_liters(row.capacity), row.source)
         for number, row in enumerate(rows, start=1)),
    )


def load_measurements(db: sqlite3.Connection, revision_id: str) -> tuple[Measurement, ...]:
    rows = db.execute(
        '''SELECT start_node, end_node, capacity, source FROM measurements
           WHERE revision_id = ? ORDER BY row_number''',
        (revision_id,),
    )
    return tuple(Measurement(start, end, parse_liters(capacity), source)
                 for start, end, capacity, source in rows)
