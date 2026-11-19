import sqlite3
from dataclasses import dataclass

from issue.envelope import PacketEnvelope, decode_packet, encode_packet


@dataclass(frozen=True)
class AcceptedPacket:
    accepted_id: int
    packet: PacketEnvelope


def initialize_admissions(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS accepted_packets (
            accepted_id INTEGER PRIMARY KEY,
            envelope TEXT NOT NULL
        )
    ''')


def admit(db: sqlite3.Connection, material: PacketEnvelope | str | bytes) -> int:
    packet = material if isinstance(material, PacketEnvelope) else decode_packet(material)
    encoded = encode_packet(packet)
    db.execute('BEGIN IMMEDIATE')
    with db:
        cursor = db.execute('INSERT INTO accepted_packets (envelope) VALUES (?)', (encoded,))
        accepted_id = cursor.lastrowid
    return accepted_id


def get_accepted(db: sqlite3.Connection, accepted_id: int) -> AcceptedPacket:
    row = db.execute(
        'SELECT accepted_id, envelope FROM accepted_packets WHERE accepted_id = ?', (accepted_id,),
    ).fetchone()
    if row is None:
        raise KeyError(accepted_id)
    return AcceptedPacket(row[0], decode_packet(row[1]))
