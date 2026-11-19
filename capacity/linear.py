from fractions import Fraction


def _matrix(coefficients):
    rows = [[Fraction(value) for value in row] for row in coefficients]
    width = len(rows[0]) if rows else 0
    if any(len(row) != width for row in rows):
        raise ValueError('matrix rows must have the same width')
    return rows, width


def _reduce(rows, width):
    pivot_columns = []
    for column in range(width):
        pivot_row = len(pivot_columns)
        match = next((i for i in range(pivot_row, len(rows)) if rows[i][column]), None)
        if match is None:
            continue
        rows[pivot_row], rows[match] = rows[match], rows[pivot_row]
        pivot = rows[pivot_row][column]
        normalized = [value / pivot for value in rows[pivot_row]]
        rows[pivot_row] = normalized
        for index, row in enumerate(rows):
            if index == pivot_row or not row[column]:
                continue
            factor = row[column]
            rows[index] = [value - factor * term for value, term in zip(row, normalized)]
        pivot_columns.append(column)
    return pivot_columns


def matrix_rank(coefficients) -> int:
    rows, width = _matrix(coefficients)
    return len(_reduce(rows, width))


def solve_linear_system(coefficients, right_hand_side) -> tuple[Fraction, ...] | None:
    """Return the unique rational solution, or None for singular or inconsistent systems."""
    rows, width = _matrix(coefficients)
    values = tuple(Fraction(value) for value in right_hand_side)
    if len(values) != len(rows):
        raise ValueError('right-hand side must have one value per row')
    for row, value in zip(rows, values):
        row.append(value)
    pivots = _reduce(rows, width)
    if len(pivots) < width or any(not any(row[:width]) and row[width] for row in rows):
        return None
    return tuple(rows[index][width] for index in range(width))
