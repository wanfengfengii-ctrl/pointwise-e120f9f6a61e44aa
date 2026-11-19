import sqlite3

from issue.envelope import PacketEnvelope, decode_packet, encode_packet


def initialize_catalog(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS packets (
            packet_id TEXT PRIMARY KEY NOT NULL,
            revision_id TEXT NOT NULL UNIQUE REFERENCES qualifications(revision_id),
            envelope TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS pickups (
            pickup_id INTEGER PRIMARY KEY,
            packet_id TEXT NOT NULL REFERENCES packets(packet_id)
        )
    ''')


def insert_packet(db: sqlite3.Connection, packet: PacketEnvelope) -> None:
    db.execute(
        'INSERT INTO packets (packet_id, revision_id, envelope) VALUES (?, ?, ?)',
        (packet.packet_id, packet.revision_id, encode_packet(packet)),
    )


def find_packet(db: sqlite3.Connection, packet_id: str) -> PacketEnvelope | None:
    row = db.execute('SELECT envelope FROM packets WHERE packet_id = ?', (packet_id,)).fetchone()
    return decode_packet(row[0]) if row is not None else None


def record_pickup(db: sqlite3.Connection, packet_id: str) -> None:
    db.execute('INSERT INTO pickups (packet_id) VALUES (?)', (packet_id,))
