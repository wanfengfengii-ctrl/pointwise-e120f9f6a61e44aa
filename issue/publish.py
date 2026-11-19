import sqlite3

from capacity.qualification import qualify, store_qualification
from issue.catalog import find_packet, insert_packet
from issue.envelope import PacketEnvelope
from station.ports import validate_identity


def seal(db: sqlite3.Connection, revision_id: str) -> str:
    validate_identity(revision_id, 'revision')
    packet_id = 'packet-' + revision_id
    db.execute('BEGIN IMMEDIATE')
    with db:
        existing = find_packet(db, packet_id)
        if existing is not None:
            return existing.packet_id
        qualification = qualify(db, revision_id)
        batch = qualification.batch
        packet = PacketEnvelope(
            packet_id, batch.batch_id, qualification.side, revision_id,
            batch.ports, batch.total, qualification.evidence,
        )
        store_qualification(db, qualification)
        insert_packet(db, packet)
    return packet_id
