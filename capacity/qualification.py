import json
import sqlite3
from dataclasses import dataclass

from capacity.boundary import build_boundary_evidence
from capacity.flow import max_flow
from capacity.model import build_network
from station.batches import Batch, get_batch
from station.revisions import get_revision
from station.volumes import encode_liters


@dataclass(frozen=True)
class Qualification:
    revision_id: str
    side: str
    batch: Batch
    evidence: dict


def initialize_qualifications(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS qualifications (
            revision_id TEXT PRIMARY KEY NOT NULL REFERENCES revisions(revision_id),
            qualified_liters TEXT NOT NULL,
            evidence TEXT NOT NULL
        )
    ''')


def qualify(db: sqlite3.Connection, revision_id: str) -> Qualification:
    revision = get_revision(db, revision_id)
    batch = get_batch(db, revision.batch_id)
    network = build_network(batch, revision)
    sink, arcs = network.with_outlets(network.ports)
    available = max_flow(arcs, network.root, sink).value
    if available < batch.total:
        raise ValueError(f'insufficient full-batch capacity: {available} L for {batch.total} L')
    return Qualification(revision_id, revision.side, batch, build_boundary_evidence(network))


def store_qualification(db: sqlite3.Connection, qualification: Qualification) -> None:
    db.execute(
        'INSERT INTO qualifications (revision_id, qualified_liters, evidence) VALUES (?, ?, ?)',
        (qualification.revision_id, encode_liters(qualification.batch.total),
         json.dumps(qualification.evidence, sort_keys=True, separators=(',', ':'))),
    )
