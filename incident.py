"""Check A on the 2 L shift before and after the branch change, using one receiving packet."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from issue.publish import seal
from issue.transfer import get_packet
from review.admission import admit
from review.reconcile import review
from run_station import describe_range, load_shift, open_center, open_station, record_layout, register_shift


def main() -> int:
    sample = load_shift()
    with TemporaryDirectory(prefix="water-incident-") as directory:
        path = Path(directory)
        with open_station(path / "supply.db") as supply, open_station(path / "receive.db") as receive:
            register_shift(supply, sample)
            register_shift(receive, sample)
            before = record_layout(supply, sample, "supply", "initial")
            after = record_layout(supply, sample, "supply", "correction", parent_id=before)
            intake = record_layout(receive, sample, "receive", "b_required")
            first = get_packet(supply, seal(supply, before))
            second = get_packet(supply, seal(supply, after))
            receiving = get_packet(receive, seal(receive, intake))

        with open_center(path / "center.db") as center:
            receive_id = admit(center, receiving)
            actual = {
                name: describe_range(review(center, admit(center, packet), receive_id, "A").snapshot.result)
                for name, packet in (("before", first), ("after", second))
            }

    expected = {
        "before": {"status": "feasible", "range": ["0", "0"]},
        "after": {"status": "feasible", "range": ["0", "1"]},
    }
    result = json.dumps({"actual": actual, "expected": expected, "port": "A", "unit": "L"}, sort_keys=True)
    if actual != expected:
        print("A_PORT_RANGE_MISMATCH " + result)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
