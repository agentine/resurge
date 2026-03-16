"""Wait generators for retry backoff strategies."""

from __future__ import annotations

import itertools
from typing import Any, Generator, Iterable, Optional, Union


def expo(
    base: int = 2, factor: int = 1, max_value: Optional[float] = None
) -> Generator[float, Any, None]:
    """Exponential backoff: factor * base^n for n=0,1,2,..."""
    # Prime the generator for .send() protocol
    yield  # type: ignore[misc]
    n = 0
    while True:
        a: float = factor * base**n
        if max_value is not None and a >= max_value:
            a = max_value
        yield a
        n += 1


def fibo(max_value: Optional[float] = None) -> Generator[float, Any, None]:
    """Fibonacci backoff: 1, 1, 2, 3, 5, 8, 13, ..."""
    yield  # type: ignore[misc]
    a: float = 1
    b: float = 1
    while True:
        if max_value is not None and a >= max_value:
            a = max_value
        yield a
        a, b = b, a + b


def constant(
    interval: Union[float, Iterable[float]] = 1,
) -> Generator[float, Any, None]:
    """Constant wait: fixed interval or iterate through sequence."""
    yield  # type: ignore[misc]
    try:
        itr = iter(interval)  # type: ignore[arg-type]
    except TypeError:
        itr = itertools.repeat(interval)  # type: ignore[arg-type]
    for val in itr:
        yield val


def runtime(*, value: Any) -> Generator[float, Any, None]:
    """Derive wait time from return value or exception at runtime."""
    ret_or_exc = yield  # type: ignore[misc]
    while True:
        ret_or_exc = yield value(ret_or_exc)
