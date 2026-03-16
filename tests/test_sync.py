"""Tests for the sync retry loop."""

import logging
from unittest.mock import patch

from resurge._jitter import full_jitter
from resurge._sync import retry_exception, retry_predicate, _ensure_list
from resurge._wait_gen import constant, expo


def _make_logger():
    return logging.getLogger("resurge.test")


class TestRetryException:
    def test_no_exception_succeeds(self):
        def fn():
            return 42

        result = retry_exception(
            fn, (), {},
            wait_gen=constant,
            exception=ValueError,
            on_success=[], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert result == 42

    @patch("resurge._sync.time.sleep")
    def test_retries_on_exception(self, mock_sleep):
        calls = [0]

        def fn():
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("fail")
            return "ok"

        result = retry_exception(
            fn, (), {},
            wait_gen=constant,
            exception=ValueError,
            on_success=[], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert result == "ok"
        assert calls[0] == 3
        assert mock_sleep.call_count == 2

    @patch("resurge._sync.time.sleep")
    def test_max_tries_giveup_raises(self, mock_sleep):
        def fn():
            raise ValueError("always fail")

        try:
            retry_exception(
                fn, (), {},
                wait_gen=constant,
                exception=ValueError,
                max_tries=3,
                raise_on_giveup=True,
                on_success=[], on_backoff=[], on_giveup=[],
                logger=_make_logger(),
                wait_gen_kwargs={"interval": 0},
            )
            assert False, "Should have raised"
        except ValueError:
            pass

    @patch("resurge._sync.time.sleep")
    def test_max_tries_giveup_no_raise(self, mock_sleep):
        def fn():
            raise ValueError("always fail")

        result = retry_exception(
            fn, (), {},
            wait_gen=constant,
            exception=ValueError,
            max_tries=3,
            raise_on_giveup=False,
            on_success=[], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert result is None

    @patch("resurge._sync.time.sleep")
    def test_giveup_predicate(self, mock_sleep):
        def fn():
            raise ValueError("fatal")

        giveup_calls = []

        def on_giveup(details):
            giveup_calls.append(details)

        try:
            retry_exception(
                fn, (), {},
                wait_gen=constant,
                exception=ValueError,
                giveup=lambda e: "fatal" in str(e),
                on_success=[], on_backoff=[], on_giveup=[on_giveup],
                logger=_make_logger(),
                wait_gen_kwargs={"interval": 0},
            )
        except ValueError:
            pass

        assert len(giveup_calls) == 1
        assert giveup_calls[0]["tries"] == 1

    @patch("resurge._sync.time.sleep")
    def test_on_backoff_handler(self, mock_sleep):
        calls = [0]
        backoff_events = []

        def fn():
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("fail")
            return "ok"

        def on_backoff(details):
            backoff_events.append(details)

        retry_exception(
            fn, (), {},
            wait_gen=constant,
            exception=ValueError,
            on_success=[], on_backoff=[on_backoff], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert len(backoff_events) == 2
        assert "wait" in backoff_events[0]
        assert "exception" in backoff_events[0]
        assert backoff_events[0]["tries"] == 1
        assert backoff_events[1]["tries"] == 2

    @patch("resurge._sync.time.sleep")
    def test_on_success_handler(self, mock_sleep):
        success_events = []

        def fn():
            return 42

        def on_success(details):
            success_events.append(details)

        retry_exception(
            fn, (), {},
            wait_gen=constant,
            exception=ValueError,
            on_success=[on_success], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert len(success_events) == 1
        assert success_events[0]["tries"] == 1

    @patch("resurge._sync.time.sleep")
    def test_exception_tuple(self, mock_sleep):
        calls = [0]

        def fn():
            calls[0] += 1
            if calls[0] == 1:
                raise ValueError("v")
            if calls[0] == 2:
                raise TypeError("t")
            return "ok"

        result = retry_exception(
            fn, (), {},
            wait_gen=constant,
            exception=(ValueError, TypeError),
            on_success=[], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert result == "ok"
        assert calls[0] == 3

    def test_unmatched_exception_propagates(self):
        def fn():
            raise RuntimeError("unhandled")

        try:
            retry_exception(
                fn, (), {},
                wait_gen=constant,
                exception=ValueError,
                on_success=[], on_backoff=[], on_giveup=[],
                logger=_make_logger(),
                wait_gen_kwargs={"interval": 0},
            )
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass

    @patch("resurge._sync.time.sleep")
    def test_passes_args_kwargs(self, mock_sleep):
        def fn(a, b, c=None):
            if c is None:
                raise ValueError("need c")
            return a + b + c

        # First call will fail (c=None default won't be used since we pass it)
        result = retry_exception(
            fn, (1, 2), {"c": 3},
            wait_gen=constant,
            exception=ValueError,
            on_success=[], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert result == 6


class TestRetryPredicate:
    @patch("resurge._sync.time.sleep")
    def test_retries_until_truthy(self, mock_sleep):
        calls = [0]

        def fn():
            calls[0] += 1
            return calls[0] >= 3

        # predicate=operator.not_ means retry while return is falsy
        import operator
        result = retry_predicate(
            fn, (), {},
            wait_gen=constant,
            predicate=operator.not_,
            on_success=[], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert result is True
        assert calls[0] == 3

    @patch("resurge._sync.time.sleep")
    def test_max_tries_returns_last_value(self, mock_sleep):
        def fn():
            return False

        import operator
        result = retry_predicate(
            fn, (), {},
            wait_gen=constant,
            predicate=operator.not_,
            max_tries=3,
            on_success=[], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert result is False

    @patch("resurge._sync.time.sleep")
    def test_on_backoff_has_value(self, mock_sleep):
        calls = [0]
        backoff_events = []

        def fn():
            calls[0] += 1
            return calls[0] >= 3

        import operator

        def on_backoff(details):
            backoff_events.append(details)

        retry_predicate(
            fn, (), {},
            wait_gen=constant,
            predicate=operator.not_,
            on_success=[], on_backoff=[on_backoff], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert len(backoff_events) == 2
        assert "value" in backoff_events[0]
        assert backoff_events[0]["value"] is False

    @patch("resurge._sync.time.sleep")
    def test_on_success_has_value(self, mock_sleep):
        success_events = []

        def fn():
            return True

        import operator

        def on_success(details):
            success_events.append(details)

        retry_predicate(
            fn, (), {},
            wait_gen=constant,
            predicate=operator.not_,
            on_success=[on_success], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert len(success_events) == 1
        assert success_events[0]["value"] is True

    def test_immediate_success(self):
        def fn():
            return True

        import operator
        result = retry_predicate(
            fn, (), {},
            wait_gen=constant,
            predicate=operator.not_,
            on_success=[], on_backoff=[], on_giveup=[],
            logger=_make_logger(),
            wait_gen_kwargs={"interval": 0},
        )
        assert result is True


class TestEnsureList:
    def test_none(self):
        assert _ensure_list(None) == []

    def test_single_callable(self):
        fn = lambda d: None
        assert _ensure_list(fn) == [fn]

    def test_list(self):
        fn1 = lambda d: None
        fn2 = lambda d: None
        assert _ensure_list([fn1, fn2]) == [fn1, fn2]
