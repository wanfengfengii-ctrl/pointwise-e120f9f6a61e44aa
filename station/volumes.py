from fractions import Fraction


def parse_liters(value: Fraction | int | str, *, positive: bool = False) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (Fraction, int, str)):
        raise ValueError('liters require a Fraction, integer or rational string')
    try:
        amount = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError('invalid rational liters') from error
    if amount < 0 or (positive and amount == 0):
        raise ValueError('liters must be positive' if positive else 'liters must be nonnegative')
    return amount


def encode_liters(value: Fraction | int | str) -> str:
    return str(parse_liters(value))
