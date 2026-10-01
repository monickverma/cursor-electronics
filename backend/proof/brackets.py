"""
Rigorous rational enclosures of transcendental numbers. Stage 4.

z3 decides polynomial arithmetic over the rationals exactly; it cannot reason
about π or a logarithm. So each transcendental enters a query as a variable
constrained to a rational interval that is **guaranteed** to contain the true
value, computed with `mpmath.iv` — interval arithmetic with outward rounding.
If the negated property is UNSAT for every value in the bracket, it is UNSAT
for the true value inside it. This is v2's "π rationally bracketed", and it is
what eliminates defeater D8.

The endpoints are converted to exact binary rationals from mpmath's internal
(sign, mantissa, exponent) form — never through a decimal string, which would
round and could step outside the enclosure.
"""

from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from typing import Tuple

from mpmath import iv

#: Working precision. 128 bits puts the bracket width near 1e-38, far below
#: anything a tolerance box can resolve, so a proof never fails on the
#: bracket and never succeeds because of it.
PRECISION_BITS = 128

Bracket = Tuple[Fraction, Fraction]


def _exact(raw) -> Fraction:
    sign, man, exp, _ = raw
    value = Fraction(man) * (Fraction(2) ** exp)
    return -value if sign else value


def _bracket(interval) -> Bracket:
    lo, hi = interval._mpi_
    a, b = _exact(lo), _exact(hi)
    if a > b:  # pragma: no cover - mpmath guarantees ordering
        raise ArithmeticError("interval endpoints out of order")
    return a, b


def _iv(value: Fraction):
    """An exact rational as a (possibly non-degenerate) mpmath interval."""
    return iv.mpf(value.numerator) / iv.mpf(value.denominator)


@lru_cache(maxsize=None)
def pi() -> Bracket:
    iv.prec = PRECISION_BITS
    return _bracket(iv.pi)


@lru_cache(maxsize=None)
def ln(value: Fraction) -> Bracket:
    """ln(value) for a positive rational."""
    if value <= 0:
        raise ValueError("ln of a non-positive number")
    iv.prec = PRECISION_BITS
    return _bracket(iv.log(_iv(value)))


@lru_cache(maxsize=None)
def expm1_ratio(numerator: Fraction, denominator: Fraction) -> Bracket:
    """exp(numerator/denominator) − 1, enclosed."""
    iv.prec = PRECISION_BITS
    return _bracket(iv.exp(_iv(numerator) / _iv(denominator)) - 1)


def contains(bracket: Bracket, value: float) -> bool:
    return bracket[0] <= Fraction(value) <= bracket[1]
