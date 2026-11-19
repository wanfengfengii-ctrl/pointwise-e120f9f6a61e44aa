from dataclasses import dataclass
from fractions import Fraction
from typing import Hashable, Iterable

from station.batches import Batch
from station.revisions import Revision
from station.volumes import parse_liters


Arc = tuple[Hashable, Hashable, Fraction]


@dataclass(frozen=True)
class FlowNetwork:
    root: str
    ports: tuple[str, ...]
    total: Fraction
    arcs: tuple[Arc, ...]

    def with_outlets(self, ports: Iterable[str]) -> tuple[object, tuple[Arc, ...]]:
        sink = object()
        outlets = tuple((port, sink, self.total) for port in ports)
        return sink, self.arcs + outlets


def build_network(batch: Batch, revision: Revision) -> FlowNetwork:
    if revision.batch_id != batch.batch_id:
        raise ValueError('network requires the revision’s original batch')
    arcs = []
    for measurement in revision.measurements:
        start, end = measurement.start, measurement.end
        if revision.side == 'receive':
            start, end = end, start
        arcs.append((start, end, parse_liters(measurement.capacity)))
    return FlowNetwork(revision.root, batch.ports.ids, batch.total, tuple(arcs))
