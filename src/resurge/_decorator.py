"""Decorator factories: on_exception and on_predicate."""

from __future__ import annotations

import functools
import logging
import operator
from typing import Any, Callable, Iterable, Optional, Sequence, Type, TypeVar, Union

from ._jitter import full_jitter
from ._sync import _ensure_list, _maybe_call, retry_exception, retry_predicate
from ._types import _Handler, _Jitterer, _MaybeLogger, _Predicate

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])
_MaybeCallable = Union[Any, Callable[[], Any]]


def _resolve_logger(logger: _MaybeLogger) -> logging.Logger:
    if logger is None:
        return logging.getLogger("backoff")
    if isinstance(logger, str):
        return logging.getLogger(logger)
    return logger


def on_exception(
    wait_gen: Callable[..., Any],
    exception: Union[Type[Exception], Sequence[Type[Exception]]],
    *,
    max_tries: Optional[_MaybeCallable] = None,
    max_time: Optional[_MaybeCallable] = None,
    jitter: Optional[_Jitterer] = full_jitter,
    giveup: _Predicate[Exception] = lambda e: False,
    on_success: Union[_Handler, Iterable[_Handler], None] = None,
    on_backoff: Union[_Handler, Iterable[_Handler], None] = None,
    on_giveup: Union[_Handler, Iterable[_Handler], None] = None,
    raise_on_giveup: bool = True,
    logger: _MaybeLogger = "backoff",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    **wait_gen_kwargs: Any,
) -> Callable[[_CallableT], _CallableT]:
    """Retry decorator that retries when a specified exception is raised.

    Args:
        wait_gen: Generator yielding wait times between retries.
        exception: Exception class or tuple of classes to catch.
        max_tries: Max number of attempts (None = unlimited).
        max_time: Max total seconds (None = unlimited).
        jitter: Jitter function applied to wait times.
        giveup: Predicate; if True for exception, stop retrying.
        on_success: Handler(s) called on success.
        on_backoff: Handler(s) called before each retry sleep.
        on_giveup: Handler(s) called when giving up.
        raise_on_giveup: Re-raise exception on giveup (default True).
        logger: Logger name or instance.
        backoff_log_level: Log level for backoff events.
        giveup_log_level: Log level for giveup events.
        **wait_gen_kwargs: Passed to wait_gen.
    """
    log = _resolve_logger(logger)
    success_hdlrs = _ensure_list(on_success)
    backoff_hdlrs = _ensure_list(on_backoff)
    giveup_hdlrs = _ensure_list(on_giveup)

    # Normalize exception to tuple
    if isinstance(exception, type) and issubclass(exception, BaseException):
        exc_types: tuple[Type[Exception], ...] = (exception,)
    else:
        exc_types = tuple(exception)  # type: ignore[arg-type]

    def decorate(target: _CallableT) -> _CallableT:
        @functools.wraps(target)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return retry_exception(
                target,
                args,
                kwargs,
                wait_gen=wait_gen,
                exception=exc_types,
                max_tries=_maybe_call(max_tries),
                max_time=_maybe_call(max_time),
                jitter=jitter,
                giveup=giveup,
                on_success=success_hdlrs,
                on_backoff=backoff_hdlrs,
                on_giveup=giveup_hdlrs,
                raise_on_giveup=raise_on_giveup,
                logger=log,
                backoff_log_level=backoff_log_level,
                giveup_log_level=giveup_log_level,
                wait_gen_kwargs=wait_gen_kwargs,
            )

        return wrapper  # type: ignore[return-value]

    return decorate


def on_predicate(
    wait_gen: Callable[..., Any],
    predicate: _Predicate[Any] = operator.not_,
    *,
    max_tries: Optional[_MaybeCallable] = None,
    max_time: Optional[_MaybeCallable] = None,
    jitter: Optional[_Jitterer] = full_jitter,
    on_success: Union[_Handler, Iterable[_Handler], None] = None,
    on_backoff: Union[_Handler, Iterable[_Handler], None] = None,
    on_giveup: Union[_Handler, Iterable[_Handler], None] = None,
    logger: _MaybeLogger = "backoff",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    **wait_gen_kwargs: Any,
) -> Callable[[_CallableT], _CallableT]:
    """Retry decorator that retries when predicate returns True for return value.

    Args:
        wait_gen: Generator yielding wait times between retries.
        predicate: Callable; retry if predicate(return_value) is truthy.
        max_tries: Max number of attempts (None = unlimited).
        max_time: Max total seconds (None = unlimited).
        jitter: Jitter function applied to wait times.
        on_success: Handler(s) called on success.
        on_backoff: Handler(s) called before each retry sleep.
        on_giveup: Handler(s) called when giving up.
        logger: Logger name or instance.
        backoff_log_level: Log level for backoff events.
        giveup_log_level: Log level for giveup events.
        **wait_gen_kwargs: Passed to wait_gen.
    """
    log = _resolve_logger(logger)
    success_hdlrs = _ensure_list(on_success)
    backoff_hdlrs = _ensure_list(on_backoff)
    giveup_hdlrs = _ensure_list(on_giveup)

    def decorate(target: _CallableT) -> _CallableT:
        @functools.wraps(target)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return retry_predicate(
                target,
                args,
                kwargs,
                wait_gen=wait_gen,
                predicate=predicate,
                max_tries=_maybe_call(max_tries),
                max_time=_maybe_call(max_time),
                jitter=jitter,
                on_success=success_hdlrs,
                on_backoff=backoff_hdlrs,
                on_giveup=giveup_hdlrs,
                logger=log,
                backoff_log_level=backoff_log_level,
                giveup_log_level=giveup_log_level,
                wait_gen_kwargs=wait_gen_kwargs,
            )

        return wrapper  # type: ignore[return-value]

    return decorate
