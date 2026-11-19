from dataclasses import dataclass
from fractions import Fraction


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


def compute_port_range(total: Fraction, intervals, target_index: int) -> PortRange:
    """Find the target range under the stated port intervals and full batch volume."""
    if not 0 <= target_index < 4:
        raise ValueError("port coordinate is out of range")
    if any(lower > upper for lower, upper in intervals):
        return PortRange("infeasible", None, None)

    total_lower = sum(lower for lower, _ in intervals)
    total_upper = sum(upper for _, upper in intervals)
    if not total_lower <= total <= total_upper:
        return PortRange("infeasible", None, None)

    lower, upper = intervals[target_index]
    return PortRange(
        "feasible",
        max(lower, total - (total_upper - upper)),
        min(upper, total - (total_lower - lower)),
    )
