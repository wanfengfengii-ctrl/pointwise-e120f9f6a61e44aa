import sqlite3

from issue.envelope import PacketEnvelope, read_ranges
from reports.publish import publish_report
from reports.readback import Report
from reports.snapshots import build_snapshot
from review.ranges import PortRange, compute_port_range
from review.selection import ReviewSelection, select_pair


def _common_ranges(packet: PacketEnvelope, coordinates: tuple[int, ...]):
    local_ranges = read_ranges(packet.evidence, packet.total)
    return {common: local_ranges[local] for local, common in enumerate(coordinates)}


def reconcile_evidence(selection: ReviewSelection) -> PortRange:
    alignment = selection.alignment
    supply = selection.supply.packet
    receive = selection.receive.packet
    supply_ranges = _common_ranges(supply, alignment.supply_to_common)
    receive_ranges = _common_ranges(receive, alignment.receive_to_common)
    joint = [
        (max(supply_ranges[i][0], receive_ranges[i][0]), min(supply_ranges[i][1], receive_ranges[i][1]))
        for i in range(len(alignment.common_ids))
    ]
    return compute_port_range(supply.total, joint, alignment.target_index)


def review(db: sqlite3.Connection, supply_id: int, receive_id: int, port: str) -> Report:
    selection = select_pair(db, supply_id, receive_id, port)
    result = reconcile_evidence(selection)
    return publish_report(db, build_snapshot(selection, result))
