from dataclasses import dataclass

from station.ports import PortRoster, canonical_port_ids, validate_identity, validate_roster


@dataclass(frozen=True)
class PortAlignment:
    common_ids: tuple[str, ...]
    supply_to_common: tuple[int, ...]
    receive_to_common: tuple[int, ...]
    target_index: int


def align_ports(supply: PortRoster, receive: PortRoster, target: str) -> PortAlignment:
    supply = validate_roster(supply)
    receive = validate_roster(receive)
    common = canonical_port_ids(supply)
    if common != canonical_port_ids(receive):
        raise ValueError('public port rosters disagree')
    coordinates = {port: index for index, port in enumerate(common)}
    validate_identity(target, 'requested port')
    if target not in coordinates:
        raise ValueError(f'unknown public port: {target}')
    return PortAlignment(
        common,
        tuple(coordinates[port] for port in supply.ids),
        tuple(coordinates[port] for port in receive.ids),
        coordinates[target],
    )
