from collections import defaultdict, deque
from dataclasses import dataclass
from fractions import Fraction
from typing import Hashable, Iterable

from capacity.model import Arc


@dataclass(frozen=True)
class FlowResult:
    value: Fraction


def max_flow(arcs: Iterable[Arc], source: Hashable, sink: Hashable) -> FlowResult:
    if source == sink:
        raise ValueError('flow terminals must be distinct')
    residual = defaultdict(dict)
    for start, end, capacity in arcs:
        capacity = Fraction(capacity)
        if capacity < 0:
            raise ValueError('negative flow capacity')
        if start == end or capacity == 0:
            continue
        residual[start][end] = residual[start].get(end, Fraction(0)) + capacity
        residual[end].setdefault(start, Fraction(0))

    value = Fraction(0)
    while True:
        parent = {source: source}
        queue = deque([source])
        while queue and sink not in parent:
            start = queue.popleft()
            for end, remaining in residual[start].items():
                if remaining > 0 and end not in parent:
                    parent[end] = start
                    queue.append(end)
        if sink not in parent:
            return FlowResult(value)

        path = []
        end = sink
        while end != source:
            start = parent[end]
            path.append((start, end))
            end = start
        stride = min(residual[start][end] for start, end in path)
        for start, end in path:
            residual[start][end] -= stride
            residual[end][start] += stride
        value += stride
