import sqlite3

from issue.catalog import find_packet, record_pickup
from issue.envelope import PacketEnvelope


def get_packet(db: sqlite3.Connection, packet_id: str) -> PacketEnvelope:
    db.execute('BEGIN IMMEDIATE')
    with db:
        packet = find_packet(db, packet_id)
        if packet is None:
            raise KeyError(packet_id)
        record_pickup(db, packet_id)
    return packet
