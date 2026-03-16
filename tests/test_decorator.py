"""Integration tests for on_exception and on_predicate decorators."""

from unittest.mock import patch

import resurge


class TestOnException:
    @patch("resurge._sync.time.sleep")
    def test_basic_retry(self, mock_sleep):
        calls = [0]

        @resurge.on_exception(resurge.expo, ValueError, max_tries=5, jitter=None)
        def flaky():
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("fail")
            return "ok"

        assert flaky() == "ok"
        assert calls[0] == 3

    @patch("resurge._sync.time.sleep")
    def test_max_tries_raises(self, mock_sleep):
        @resurge.on_exception(resurge.constant, ValueError, max_tries=3, interval=0)
        def always_fails():
            raise ValueError("always")

        try:
            always_fails()
            assert False, "Should have raised"
        except ValueError as e:
            assert str(e) == "always"

    @patch("resurge._sync.time.sleep")
    def test_raise_on_giveup_false(self, mock_sleep):
        @resurge.on_exception(
            resurge.constant, ValueError,
            max_tries=2, raise_on_giveup=False, interval=0,
        )
        def always_fails():
            raise ValueError("always")

        result = always_fails()
        assert result is None

    @patch("resurge._sync.time.sleep")
    def test_event_handlers(self, mock_sleep):
        backoffs = []
        successes = []
        giveups = []

        calls = [0]

        @resurge.on_exception(
            resurge.constant,
            ValueError,
            on_backoff=lambda d: backoffs.append(d),
            on_success=lambda d: successes.append(d),
            on_giveup=lambda d: giveups.append(d),
            interval=0,
        )
        def flaky():
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("fail")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert len(backoffs) == 2
        assert len(successes) == 1
        assert len(giveups) == 0
        # Verify handler dict structure
        assert backoffs[0]["target"] is flaky.__wrapped__
        assert "wait" in backoffs[0]
        assert "exception" in backoffs[0]
        assert successes[0]["tries"] == 3

    @patch("resurge._sync.time.sleep")
    def test_giveup_predicate(self, mock_sleep):
        @resurge.on_exception(
            resurge.constant,
            ValueError,
            giveup=lambda e: "fatal" in str(e),
            interval=0,
        )
        def fails_fatal():
            raise ValueError("fatal error")

        try:
            fails_fatal()
            assert False
        except ValueError:
            pass

    @patch("resurge._sync.time.sleep")
    def test_with_args_kwargs(self, mock_sleep):
        calls = [0]

        @resurge.on_exception(resurge.constant, ValueError, max_tries=5, interval=0)
        def add(a, b, c=0):
            calls[0] += 1
            if calls[0] < 2:
                raise ValueError("not yet")
            return a + b + c

        assert add(1, 2, c=3) == 6

    @patch("resurge._sync.time.sleep")
    def test_fibo_wait(self, mock_sleep):
        calls = [0]

        @resurge.on_exception(resurge.fibo, ValueError, max_tries=4, jitter=None)
        def flaky():
            calls[0] += 1
            if calls[0] < 4:
                raise ValueError("fail")
            return "ok"

        flaky()
        # fibo yields 1, 1, 2 — three sleeps
        sleep_values = [c[0][0] for c in mock_sleep.call_args_list]
        assert sleep_values == [1, 1, 2]

    @patch("resurge._sync.time.sleep")
    def test_expo_with_max_value(self, mock_sleep):
        calls = [0]

        @resurge.on_exception(
            resurge.expo, ValueError,
            max_tries=5, jitter=None, max_value=3,
        )
        def flaky():
            calls[0] += 1
            if calls[0] < 5:
                raise ValueError("fail")
            return "ok"

        flaky()
        sleep_values = [c[0][0] for c in mock_sleep.call_args_list]
        # expo: 1, 2, 3, 3 (capped at max_value=3)
        assert sleep_values == [1, 2, 3, 3]

    @patch("resurge._sync.time.sleep")
    def test_exception_tuple(self, mock_sleep):
        calls = [0]

        @resurge.on_exception(
            resurge.constant,
            (ValueError, TypeError),
            max_tries=5,
            interval=0,
        )
        def mixed_errors():
            calls[0] += 1
            if calls[0] == 1:
                raise ValueError("v")
            if calls[0] == 2:
                raise TypeError("t")
            return "ok"

        assert mixed_errors() == "ok"

    def test_unmatched_exception_propagates(self):
        @resurge.on_exception(resurge.constant, ValueError, interval=0)
        def raises_runtime():
            raise RuntimeError("wrong type")

        try:
            raises_runtime()
            assert False
        except RuntimeError:
            pass

    @patch("resurge._sync.time.sleep")
    def test_multiple_handlers(self, mock_sleep):
        h1_calls = []
        h2_calls = []

        calls = [0]

        @resurge.on_exception(
            resurge.constant,
            ValueError,
            on_backoff=[lambda d: h1_calls.append(1), lambda d: h2_calls.append(1)],
            max_tries=3,
            interval=0,
        )
        def flaky():
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("fail")
            return "ok"

        flaky()
        assert len(h1_calls) == 2
        assert len(h2_calls) == 2


class TestOnPredicate:
    @patch("resurge._sync.time.sleep")
    def test_basic_retry(self, mock_sleep):
        calls = [0]

        @resurge.on_predicate(resurge.constant, max_tries=5, interval=0)
        def eventually_truthy():
            calls[0] += 1
            return calls[0] >= 3

        assert eventually_truthy() is True

    @patch("resurge._sync.time.sleep")
    def test_custom_predicate(self, mock_sleep):
        calls = [0]

        @resurge.on_predicate(
            resurge.constant,
            predicate=lambda x: x < 10,
            max_tries=5,
            interval=0,
        )
        def counting():
            calls[0] += 5
            return calls[0]

        assert counting() == 10

    @patch("resurge._sync.time.sleep")
    def test_max_tries_returns_last(self, mock_sleep):
        @resurge.on_predicate(resurge.constant, max_tries=3, interval=0)
        def always_falsy():
            return False

        assert always_falsy() is False

    @patch("resurge._sync.time.sleep")
    def test_event_handlers(self, mock_sleep):
        backoffs = []
        successes = []
        giveups = []
        calls = [0]

        @resurge.on_predicate(
            resurge.constant,
            on_backoff=lambda d: backoffs.append(d),
            on_success=lambda d: successes.append(d),
            on_giveup=lambda d: giveups.append(d),
            max_tries=5,
            interval=0,
        )
        def eventually_truthy():
            calls[0] += 1
            return calls[0] >= 3

        eventually_truthy()
        assert len(backoffs) == 2
        assert len(successes) == 1
        assert "value" in backoffs[0]
        assert "value" in successes[0]
        assert successes[0]["value"] is True

    @patch("resurge._sync.time.sleep")
    def test_giveup_handler(self, mock_sleep):
        giveups = []

        @resurge.on_predicate(
            resurge.constant,
            on_giveup=lambda d: giveups.append(d),
            max_tries=2,
            interval=0,
        )
        def always_falsy():
            return False

        always_falsy()
        assert len(giveups) == 1
        assert giveups[0]["value"] is False

    def test_immediate_success(self):
        @resurge.on_predicate(resurge.constant, interval=0)
        def truthy():
            return True

        assert truthy() is True


class TestPublicAPI:
    def test_all_exports(self):
        expected = {
            "on_exception", "on_predicate",
            "expo", "fibo", "constant", "runtime",
            "full_jitter", "random_jitter",
        }
        assert set(resurge.__all__) == expected

    def test_import_style_backoff_compat(self):
        """Verify that 'import resurge as backoff' usage pattern works."""
        import resurge as backoff

        assert hasattr(backoff, "on_exception")
        assert hasattr(backoff, "on_predicate")
        assert hasattr(backoff, "expo")
        assert hasattr(backoff, "fibo")
        assert hasattr(backoff, "constant")
        assert hasattr(backoff, "runtime")
        assert hasattr(backoff, "full_jitter")
        assert hasattr(backoff, "random_jitter")
