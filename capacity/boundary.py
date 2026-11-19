from capacity.flow import max_flow
from capacity.model import FlowNetwork
from station.volumes import encode_liters


def _largest_delivery(network: FlowNetwork, ports):
    sink, arcs = network.with_outlets(ports)
    return min(network.total, max_flow(arcs, network.root, sink).value)


def build_boundary_evidence(network: FlowNetwork) -> dict:
    # The full-batch vectors reachable on the public ports are exactly
    # {x >= 0, sum(x) = total, x(S) <= caps[S] for every port subset S},
    # so the sixteen subset caps preserve all and only those vectors.
    caps = []
    for mask in range(16):
        subset = tuple(port for index, port in enumerate(network.ports) if mask & (1 << index))
        caps.append(_largest_delivery(network, subset))
    intervals = []
    for index in range(4):
        lower = network.total - caps[15 ^ (1 << index)]
        upper = caps[1 << index]
        intervals.append([encode_liters(lower), encode_liters(upper)])
    return {
        "ranges": intervals,
        "extensions": {"subsets": [encode_liters(cap) for cap in caps]},
    }
