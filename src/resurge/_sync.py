"""Synchronous retry loop."""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Callable, Generator, Iterable, Optional, Tuple, Type, Union

from ._jitter import full_jitter
from ._types import Details, _Handler, _Jitterer, _Predicate


def _call_handlers(
    hdlrs: Iterable[_Handler],
    target: Callable[..., Any],
    args: Tuple[Any, ...],
    kwargs: dict[str, Any],
    tries: int,
    elapsed: float,
    **extra: Any,
) -> None:
    details: dict[str, Any] = {
        "target": target,
        "args": args,
        "kwargs": kwargs,
        "tries": tries,
        "elapsed": elapsed,
    }
    details.update(extra)
    for hdlr in hdlrs:
        hdlr(details)  # type: ignore[arg-type]


def _maybe_call(value: Any) -> Any:
    """If value is callable, call it; otherwise return as-is."""
    if callable(value):
        return value()
    return value


def _init_wait_gen(
    wait_gen: Callable[..., Generator[float, Any, None]],
    wait_gen_kwargs: dict[str, Any],
) -> Generator[float, Any, None]:
    """Instantiate and prime a wait generator."""
    # Evaluate any callable kwargs
    kwargs = {k: _maybe_call(v) for k, v in wait_gen_kwargs.items()}
    gen = wait_gen(**kwargs)
    gen.send(None)  # prime
    return gen


def _next_wait(
    wait: Generator[float, Any, None],
    send_value: Any,
    jitter: Optional[_Jitterer],
    elapsed: float,
    max_time: Optional[float],
) -> Optional[float]:
    """Get next wait time from generator, apply jitter, clamp to max_time."""
    try:
        value = wait.send(send_value)
    except StopIteration:
        return None

    if jitter is not None:
        seconds = jitter(value)
    else:
        seconds = value

    if max_time is not None:
        remaining = max_time - elapsed
        if remaining <= 0:
            return None
        seconds = min(seconds, remaining)

    return max(seconds, 0)


def _log_backoff(
    logger: logging.Logger,
    level: int,
    target: Callable[..., Any],
    tries: int,
    wait: float,
    **extra: Any,
) -> None:
    exc = extra.get("exception")
    if exc:
        exc_fmt = traceback.format_exception_only(type(exc), exc)[-1].rstrip()
        logger.log(
            level,
            "Backing off %s(...) for %.1fs (%s)",
            target.__qualname__,
            wait,
            exc_fmt,
        )
    else:
        value = extra.get("value")
        logger.log(
            level,
            "Backing off %s(...) for %.1fs (%s)",
            target.__qualname__,
            wait,
            repr(value),
        )


def _log_giveup(
    logger: logging.Logger,
    level: int,
    target: Callable[..., Any],
    tries: int,
    **extra: Any,
) -> None:
    exc = extra.get("exception")
    if exc:
        exc_fmt = traceback.format_exception_only(type(exc), exc)[-1].rstrip()
        logger.log(
            level,
            "Giving up %s(...) after %d tries (%s)",
            target.__qualname__,
            tries,
            exc_fmt,
        )
    else:
        value = extra.get("value")
        logger.log(
            level,
            "Giving up %s(...) after %d tries (%s)",
            target.__qualname__,
            tries,
            repr(value),
        )


def _ensure_list(
    value: Union[_Handler, Iterable[_Handler], None],
) -> list[_Handler]:
    if value is None:
        return []
    if callable(value):
        return [value]
    return list(value)


def retry_exception(
    target: Callable[..., Any],
    args: Tuple[Any, ...],
    kwargs: dict[str, Any],
    wait_gen: Callable[..., Generator[float, Any, None]],
    exception: Union[Type[Exception], Tuple[Type[Exception], ...]],
    *,
    max_tries: Optional[int] = None,
    max_time: Optional[float] = None,
    jitter: Optional[_Jitterer] = full_jitter,
    giveup: _Predicate[Exception] = lambda e: False,
    on_success: list[_Handler],
    on_backoff: list[_Handler],
    on_giveup: list[_Handler],
    raise_on_giveup: bool = True,
    logger: logging.Logger,
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    wait_gen_kwargs: dict[str, Any],
) -> Any:
    """Sync retry loop for on_exception."""
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)
    start = time.monotonic()
    tries = 0

    while True:
        tries += 1
        elapsed = time.monotonic() - start

        # Check max_time before attempt
        if max_time is not None and elapsed >= max_time and tries > 1:
            break

        try:
            ret = target(*args, **kwargs)
        except exception as e:
            elapsed = time.monotonic() - start

            # giveup predicate
            if giveup(e):
                _call_handlers(on_giveup, target, args, kwargs, tries, elapsed, exception=e)
                _log_giveup(logger, giveup_log_level, target, tries, exception=e)
                if raise_on_giveup:
                    raise
                return None

            # max_tries check
            if max_tries is not None and tries >= max_tries:
                _call_handlers(on_giveup, target, args, kwargs, tries, elapsed, exception=e)
                _log_giveup(logger, giveup_log_level, target, tries, exception=e)
                if raise_on_giveup:
                    raise
                return None

            # Get next wait
            seconds = _next_wait(wait, e, jitter, elapsed, max_time)
            if seconds is None:
                _call_handlers(on_giveup, target, args, kwargs, tries, elapsed, exception=e)
                _log_giveup(logger, giveup_log_level, target, tries, exception=e)
                if raise_on_giveup:
                    raise
                return None

            _call_handlers(
                on_backoff, target, args, kwargs, tries, elapsed, wait=seconds, exception=e
            )
            _log_backoff(logger, backoff_log_level, target, tries, seconds, exception=e)
            time.sleep(seconds)
        else:
            elapsed = time.monotonic() - start
            _call_handlers(on_success, target, args, kwargs, tries, elapsed)
            return ret

    return None


def retry_predicate(
    target: Callable[..., Any],
    args: Tuple[Any, ...],
    kwargs: dict[str, Any],
    wait_gen: Callable[..., Generator[float, Any, None]],
    predicate: _Predicate[Any],
    *,
    max_tries: Optional[int] = None,
    max_time: Optional[float] = None,
    jitter: Optional[_Jitterer] = full_jitter,
    on_success: list[_Handler],
    on_backoff: list[_Handler],
    on_giveup: list[_Handler],
    logger: logging.Logger,
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    wait_gen_kwargs: dict[str, Any],
) -> Any:
    """Sync retry loop for on_predicate."""
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)
    start = time.monotonic()
    tries = 0

    while True:
        tries += 1
        elapsed = time.monotonic() - start

        # Check max_time before attempt
        if max_time is not None and elapsed >= max_time and tries > 1:
            break

        ret = target(*args, **kwargs)
        elapsed = time.monotonic() - start

        if not predicate(ret):
            # Success
            _call_handlers(on_success, target, args, kwargs, tries, elapsed, value=ret)
            return ret

        # max_tries check
        if max_tries is not None and tries >= max_tries:
            _call_handlers(on_giveup, target, args, kwargs, tries, elapsed, value=ret)
            _log_giveup(logger, giveup_log_level, target, tries, value=ret)
            return ret

        # Get next wait
        seconds = _next_wait(wait, ret, jitter, elapsed, max_time)
        if seconds is None:
            _call_handlers(on_giveup, target, args, kwargs, tries, elapsed, value=ret)
            _log_giveup(logger, giveup_log_level, target, tries, value=ret)
            return ret

        _call_handlers(
            on_backoff, target, args, kwargs, tries, elapsed, wait=seconds, value=ret
        )
        _log_backoff(logger, backoff_log_level, target, tries, seconds, value=ret)
        time.sleep(seconds)

    return None
