from capacity.flow import max_flow
from capacity.model import FlowNetwork
from station.volumes import encode_liters


def _largest_delivery(network: FlowNetwork, ports):
    sink, arcs = network.with_outlets(ports)
    return min(network.total, max_flow(arcs, network.root, sink).value)


def build_boundary_evidence(network: FlowNetwork) -> dict:
    intervals = []
    for port in network.ports:
        other_ports = tuple(other for other in network.ports if other != port)
        lower = network.total - _largest_delivery(network, other_ports)
        upper = _largest_delivery(network, (port,))
        intervals.append([encode_liters(lower), encode_liters(upper)])
    return {"ranges": intervals}
