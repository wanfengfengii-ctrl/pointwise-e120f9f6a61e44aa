import json
from dataclasses import dataclass
from fractions import Fraction

from station.ports import PortRoster, validate_identity, validate_roster
from station.volumes import encode_liters, parse_liters


@dataclass(frozen=True)
class PacketEnvelope:
    packet_id: str
    batch_id: str
    side: str
    revision_id: str
    ports: PortRoster
    total: Fraction
    evidence: dict
    version: int = 1


_FIELDS = {'version', 'packet_id', 'batch_id', 'side', 'revision_id', 'ports', 'total', 'evidence'}


def _wire_liters(value, *, positive=False) -> Fraction:
    if not isinstance(value, str):
        raise ValueError('encoded liters must be a rational string')
    amount = parse_liters(value, positive=positive)
    if encode_liters(amount) != value:
        raise ValueError('encoded liters must be reduced and canonical')
    return amount


def read_ranges(evidence: dict, total: Fraction) -> tuple[tuple[Fraction, Fraction], ...]:
    if not isinstance(evidence, dict) or set(evidence) not in ({"ranges"}, {"ranges", "extensions"}):
        raise ValueError("invalid capability evidence")
    if "extensions" in evidence and not isinstance(evidence["extensions"], dict):
        raise ValueError("invalid capability extensions")
    rows = evidence["ranges"]
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("capability requires four port ranges")
    intervals = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("invalid capability range row")
        lower, upper = map(_wire_liters, row)
        if not lower <= upper <= total:
            raise ValueError("invalid capability range endpoints")
        intervals.append((lower, upper))
    if not sum(lower for lower, _ in intervals) <= total <= sum(upper for _, upper in intervals):
        raise ValueError("port ranges cannot carry the packet total")
    return tuple(intervals)


def validate_envelope(packet: PacketEnvelope) -> None:
    if not isinstance(packet, PacketEnvelope) or type(packet.version) is not int or packet.version != 1:
        raise ValueError('unsupported station packet version')
    validate_identity(packet.packet_id, 'packet')
    validate_identity(packet.batch_id, 'batch')
    validate_identity(packet.revision_id, 'source revision')
    if packet.side not in ('supply', 'receive'):
        raise ValueError('invalid station side')
    if not isinstance(packet.ports, PortRoster):
        raise ValueError('invalid packet port roster')
    validate_roster(packet.ports)
    if not isinstance(packet.total, Fraction):
        raise ValueError('packet total must be a Fraction')
    total = parse_liters(packet.total, positive=True)
    read_ranges(packet.evidence, total)


def encode_packet(packet: PacketEnvelope) -> str:
    validate_envelope(packet)
    return json.dumps({
        'version': packet.version,
        'packet_id': packet.packet_id,
        'batch_id': packet.batch_id,
        'side': packet.side,
        'revision_id': packet.revision_id,
        'ports': packet.ports.ids,
        'total': encode_liters(packet.total),
        'evidence': packet.evidence,
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _unique_fields(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError(f'duplicate packet field: {key}')
        record[key] = value
    return record


def decode_packet(encoded: str | bytes) -> PacketEnvelope:
    try:
        record = json.loads(encoded, object_pairs_hook=_unique_fields)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid station packet JSON') from error
    if not isinstance(record, dict) or set(record) != _FIELDS or not isinstance(record['ports'], list):
        raise ValueError('invalid station packet fields')
    packet = PacketEnvelope(
        record['packet_id'], record['batch_id'], record['side'], record['revision_id'],
        validate_roster(record['ports']), _wire_liters(record['total'], positive=True),
        record['evidence'], record['version'],
    )
    validate_envelope(packet)
    return packet
