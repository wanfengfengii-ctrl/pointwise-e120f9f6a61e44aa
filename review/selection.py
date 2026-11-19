import sqlite3
from dataclasses import dataclass

from review.admission import AcceptedPacket, get_accepted
from review.alignment import PortAlignment, align_ports


@dataclass(frozen=True)
class ReviewSelection:
    supply: AcceptedPacket
    receive: AcceptedPacket
    target: str
    alignment: PortAlignment


def select_pair(db: sqlite3.Connection, supply_id: int, receive_id: int, port: str) -> ReviewSelection:
    for accepted_id in (supply_id, receive_id):
        if type(accepted_id) is not int or accepted_id <= 0:
            raise ValueError('accepted material numbers must be positive integers')
    supply = get_accepted(db, supply_id)
    receive = get_accepted(db, receive_id)
    if (supply.packet.side, receive.packet.side) != ('supply', 'receive'):
        raise ValueError('select a supply packet followed by a receive packet')
    if supply.packet.batch_id != receive.packet.batch_id:
        raise ValueError('selected packets belong to different batches')
    if supply.packet.total != receive.packet.total:
        raise ValueError('selected packets disagree on the full batch volume')
    alignment = align_ports(supply.packet.ports, receive.packet.ports, port)
    return ReviewSelection(supply, receive, port, alignment)
