from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from capacity.linear import solve_linear_system


@dataclass(frozen=True)
class PortRange:
    status: str
    lower: Fraction | None
    upper: Fraction | None

    def __post_init__(self):
        if self.status == 'infeasible' and self.lower is None and self.upper is None:
            return
        if (self.status == 'feasible' and isinstance(self.lower, Fraction)
                and isinstance(self.upper, Fraction) and 0 <= self.lower <= self.upper):
            return
        raise ValueError('invalid port range')


def _constraints(caps):
    """Yield the bounds not already implied by a split into smaller kept caps.

    x(S) = x(T) + x(S - T), so a cap at or above the tightest split sum adds
    nothing; dropping it leaves the feasible region unchanged.
    """
    effective = [None] * 16
    for mask in range(1, 16):
        split = min((effective[part] + effective[mask ^ part]
                     for part in range(1, mask) if part & ~mask == 0),
                    default=None)
        if split is None or caps[mask] < split:
            effective[mask] = caps[mask]
            yield tuple(Fraction(1) if mask & (1 << index) else Fraction(0) for index in range(4)), caps[mask]
        else:
            effective[mask] = split
    for index in range(4):
        yield tuple(Fraction(0) if bit != index else Fraction(-1) for bit in range(4)), Fraction(0)


def compute_port_range(total: Fraction, caps, target_index: int) -> PortRange:
    """Find the exact target range over the common full-batch port vectors.

    The common vectors are {x >= 0, sum(x) = total, x(S) <= caps[S]}; the
    optimum of a coordinate over that polytope is attained at a vertex, and
    every vertex is cut out by the batch equality plus three independent
    active bounds, so exact rational enumeration of those systems suffices.
    """
    if not 0 <= target_index < 4:
        raise ValueError("port coordinate is out of range")
    caps = tuple(Fraction(cap) for cap in caps)
    if len(caps) != 16:
        raise ValueError("capability requires sixteen subset caps")
    bounds = tuple(_constraints(caps))
    equality = (Fraction(1),) * 4
    vertices = []
    for active in combinations(bounds, 3):
        rows = [equality] + [row for row, _ in active]
        right_hand_side = [total] + [limit for _, limit in active]
        point = solve_linear_system(rows, right_hand_side)
        if point is None:
            continue
        if all(sum(term * value for term, value in zip(row, point)) <= limit
               for row, limit in bounds):
            vertices.append(point)
    if not vertices:
        return PortRange("infeasible", None, None)
    values = [vertex[target_index] for vertex in vertices]
    return PortRange("feasible", min(values), max(values))
