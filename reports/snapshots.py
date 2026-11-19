from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

from review.ranges import PortRange
from station.volumes import encode_liters, parse_liters

if TYPE_CHECKING:
    from review.admission import AcceptedPacket
    from review.selection import ReviewSelection


@dataclass(frozen=True)
class PacketProvenance:
    accepted_id: int
    packet_id: str
    batch_id: str
    side: str
    revision_id: str


@dataclass(frozen=True)
class ReportSnapshot:
    port: str
    total: Fraction
    supply: PacketProvenance
    receive: PacketProvenance
    result: PortRange

    def to_record(self) -> dict:
        return {
            'port': self.port,
            'total': encode_liters(self.total),
            'supply': asdict(self.supply),
            'receive': asdict(self.receive),
            'result': {
                'status': self.result.status,
                'lower': None if self.result.lower is None else encode_liters(self.result.lower),
                'upper': None if self.result.upper is None else encode_liters(self.result.upper),
            },
        }

    @classmethod
    def from_record(cls, record: dict) -> ReportSnapshot:
        verdict = record['result']
        lower = None if verdict['lower'] is None else parse_liters(verdict['lower'])
        upper = None if verdict['upper'] is None else parse_liters(verdict['upper'])
        return cls(
            record['port'], parse_liters(record['total'], positive=True),
            PacketProvenance(**record['supply']), PacketProvenance(**record['receive']),
            PortRange(verdict['status'], lower, upper),
        )


def _provenance(accepted: AcceptedPacket) -> PacketProvenance:
    packet = accepted.packet
    return PacketProvenance(
        accepted.accepted_id, packet.packet_id, packet.batch_id, packet.side, packet.revision_id,
    )


def build_snapshot(selection: ReviewSelection, result: PortRange) -> ReportSnapshot:
    return ReportSnapshot(
        selection.target, selection.supply.packet.total,
        _provenance(selection.supply), _provenance(selection.receive), result,
    )
