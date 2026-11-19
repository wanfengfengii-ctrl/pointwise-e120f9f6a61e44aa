from dataclasses import dataclass


@dataclass(frozen=True)
class PortRoster:
    ids: tuple[str, ...]


def validate_identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f'{field} must be a nonblank identity without surrounding whitespace')
    return value


def validate_roster(ports) -> PortRoster:
    if isinstance(ports, PortRoster):
        ports = ports.ids
    if isinstance(ports, (str, bytes)):
        raise ValueError('provide four separate port identities')
    try:
        ids = tuple(validate_identity(port, 'port') for port in ports)
    except TypeError as error:
        raise ValueError('provide four port identities') from error
    if len(ids) != 4 or len(set(ids)) != 4:
        raise ValueError('four distinct public ports are required')
    return PortRoster(ids)


def canonical_port_ids(roster: PortRoster) -> tuple[str, ...]:
    return tuple(sorted(validate_roster(roster).ids))
