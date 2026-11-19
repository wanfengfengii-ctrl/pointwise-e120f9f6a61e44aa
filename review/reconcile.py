import sqlite3
from fractions import Fraction

from issue.envelope import PacketEnvelope, read_capability
from reports.publish import publish_report
from reports.readback import Report
from reports.snapshots import build_snapshot
from review.ranges import PortRange, compute_port_range
from review.selection import ReviewSelection, select_pair


def _common_capability(packet: PacketEnvelope, coordinates: tuple[int, ...]):
    local_caps = read_capability(packet.evidence, packet.total)
    common = [Fraction(0)] * 16
    for mask in range(16):
        common_mask = 0
        for local in range(4):
            if mask & (1 << local):
                common_mask |= 1 << coordinates[local]
        common[common_mask] = local_caps[mask]
    return common


def reconcile_evidence(selection: ReviewSelection) -> PortRange:
    alignment = selection.alignment
    supply = _common_capability(selection.supply.packet, alignment.supply_to_common)
    receive = _common_capability(selection.receive.packet, alignment.receive_to_common)
    joint = [min(supply_cap, receive_cap) for supply_cap, receive_cap in zip(supply, receive)]
    return compute_port_range(selection.supply.packet.total, joint, alignment.target_index)


def review(db: sqlite3.Connection, supply_id: int, receive_id: int, port: str) -> Report:
    selection = select_pair(db, supply_id, receive_id, port)
    result = reconcile_evidence(selection)
    return publish_report(db, build_snapshot(selection, result))
