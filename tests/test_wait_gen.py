"""Tests for wait generators."""

from resurge._wait_gen import constant, expo, fibo, runtime


def _take(gen, n):
    """Consume n values from a primed generator."""
    gen.send(None)  # prime
    return [next(gen) for _ in range(n)]


def test_expo_defaults():
    g = expo()
    vals = _take(g, 6)
    assert vals == [1, 2, 4, 8, 16, 32]


def test_expo_custom_base_factor():
    g = expo(base=3, factor=2)
    vals = _take(g, 4)
    assert vals == [2, 6, 18, 54]


def test_expo_max_value():
    g = expo(max_value=10)
    vals = _take(g, 6)
    assert vals == [1, 2, 4, 8, 10, 10]


def test_fibo_defaults():
    g = fibo()
    vals = _take(g, 7)
    assert vals == [1, 1, 2, 3, 5, 8, 13]


def test_fibo_max_value():
    g = fibo(max_value=5)
    vals = _take(g, 7)
    assert vals == [1, 1, 2, 3, 5, 5, 5]


def test_constant_default():
    g = constant()
    vals = _take(g, 3)
    assert vals == [1, 1, 1]


def test_constant_custom():
    g = constant(interval=5)
    vals = _take(g, 3)
    assert vals == [5, 5, 5]


def test_constant_iterable():
    g = constant(interval=[1, 2, 3])
    vals = _take(g, 3)
    assert vals == [1, 2, 3]


def test_constant_iterable_exhaustion():
    g = constant(interval=[1, 2])
    g.send(None)
    assert next(g) == 1
    assert next(g) == 2
    try:
        next(g)
        assert False, "Should have raised StopIteration"
    except StopIteration:
        pass


def test_runtime():
    g = runtime(value=lambda x: x * 2)
    g.send(None)  # prime
    assert g.send(3) == 6
    assert g.send(5) == 10


def test_runtime_with_exception():
    def get_retry_after(exc):
        return getattr(exc, "retry_after", 1)

    g = runtime(value=get_retry_after)
    g.send(None)  # prime

    exc = Exception()
    exc.retry_after = 5  # type: ignore[attr-defined]
    assert g.send(exc) == 5
